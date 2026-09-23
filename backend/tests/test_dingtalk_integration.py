from datetime import datetime, timezone
import json

from fastapi.testclient import TestClient

from app.integrations.dingtalk.client import DingTalkAuthenticationError, get_dingtalk_client
from app.integrations.dingtalk.schemas import DingTalkApprovalInstance, DingTalkUser
from app.main import app
from app.core.database import SessionLocal
from app.models import InvoiceJob, InvoiceType, PaymentCondition
from app.schemas.invoice_job import MockApprovalInput
from app.services.dingtalk_ingestion import DingTalkApprovalIngestionService


class FakeDingTalkClient:
    def __init__(self, user=DingTalkUser("allowed-user", "张三"), approvals=None):
        self.user, self.approvals, self.codes = user, approvals or [], []

    def exchange_auth_code(self, auth_code):
        self.codes.append(auth_code)
        return self.user

    def list_approval_instances(self, process_code, start_at, end_at):
        return self.approvals


def approval(**changes):
    value = DingTalkApprovalInstance(process_instance_id="real-test-1", process_code="invoice-process", result="AGREE", approved_at=datetime(2026, 9, 16, tzinfo=timezone.utc), approval_no="AP-1", form_values={"开票类型": "专票", "票款情况": "先开票再收款", "收款公司": "销方", "抬头类型": "企业", "抬头名称": "购方", "开票内容明细": json.dumps([{ "rowValue": [{"label": "开票内容", "value": "服务费"}, {"label": "数量", "value": "2"}, {"label": "金额（元）", "value": "15000.00"}]}])}, source_payload={"token": "never-store", "detail": "allowed"})
    return value.__class__(**{**value.__dict__, **changes})


def test_auth_exchange_and_allowlist_session():
    fake = FakeDingTalkClient()
    app.dependency_overrides[get_dingtalk_client] = lambda: fake
    client = TestClient(app)
    response = client.post("/api/auth/dingtalk", json={"auth_code": "code-1"})
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert fake.codes == ["code-1"]
    assert client.get("/api/auth/me").json()["user_id"] == "allowed-user"
    app.dependency_overrides.clear()


def test_non_allowlisted_user_is_rejected():
    app.dependency_overrides[get_dingtalk_client] = lambda: FakeDingTalkClient(DingTalkUser("other", "李四"))
    assert TestClient(app).post("/api/auth/dingtalk", json={"auth_code": "code"}).status_code == 403
    app.dependency_overrides.clear()


def test_invalid_auth_code_is_rejected_without_a_session():
    class InvalidCodeClient(FakeDingTalkClient):
        def exchange_auth_code(self, auth_code):
            raise DingTalkAuthenticationError("invalid")

    app.dependency_overrides[get_dingtalk_client] = InvalidCodeClient
    client = TestClient(app)
    assert client.post("/api/auth/dingtalk", json={"auth_code": "invalid-code"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401
    app.dependency_overrides.clear()


def test_logout_clears_the_authenticated_session():
    app.dependency_overrides[get_dingtalk_client] = FakeDingTalkClient
    client = TestClient(app)
    assert client.post("/api/auth/dingtalk", json={"auth_code": "code"}).status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    app.dependency_overrides.clear()


def test_sync_requires_authentication_in_production(monkeypatch):
    monkeypatch.setattr("app.api.auth.APP_ENV", "production")
    assert TestClient(app).post("/api/dingtalk/sync").status_code == 401


def test_production_rejects_dev_claim_header(monkeypatch):
    monkeypatch.setattr("app.api.auth.APP_ENV", "production")
    with SessionLocal() as session:
        job, _ = DingTalkApprovalIngestionService().ingest(session, MockApprovalInput(process_instance_id="production-claim", invoice_type=InvoiceType.NORMAL, payment_condition=PaymentCondition.OTHER, seller_name="s", buyer_name="b", buyer_tax_no="tax", amount="1.00", invoice_content="content", approved_at=datetime.now(timezone.utc)))
    assert TestClient(app).post(f"/api/invoice-jobs/{job.id}/claim", headers={"X-Dev-Operator-Id": "forbidden"}).status_code == 401


def test_production_blocks_unauthenticated_workbench_reads(monkeypatch):
    monkeypatch.setattr("app.api.auth.APP_ENV", "production")
    client = TestClient(app)
    assert client.get("/api/invoice-jobs").status_code == 401
    assert client.get("/api/invoice-jobs/summary").status_code == 401


def test_development_cors_allows_only_the_configured_origin():
    client = TestClient(app)
    allowed = client.options("/api/auth/me", headers={"Origin": "http://localhost:5174", "Access-Control-Request-Method": "GET"})
    rejected = client.options("/api/auth/me", headers={"Origin": "http://untrusted.example", "Access-Control-Request-Method": "GET"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5174"
    assert "access-control-allow-origin" not in rejected.headers


def test_sync_filters_and_redacts_payload():
    fake = FakeDingTalkClient(approvals=[approval(), approval(process_instance_id="pending", result="RUNNING"), approval(process_instance_id="rejected", result="REFUSED"), approval(process_instance_id="wrong", process_code="other")])
    app.dependency_overrides[get_dingtalk_client] = lambda: fake
    response = TestClient(app).post("/api/dingtalk/sync", headers={"X-Dev-Operator-Id": "allowed-user"})
    summary = response.json()
    assert {key: summary[key] for key in ("scanned", "approved", "created", "updated_pending", "already_exists", "skipped", "detail_failed", "parse_failed")} == {"scanned": 4, "approved": 1, "created": 1, "updated_pending": 0, "already_exists": 0, "skipped": 3, "detail_failed": 0, "parse_failed": 0}
    assert summary["last_successful_sync_at"]
    job = TestClient(app).get("/api/invoice-jobs").json()[0]
    assert job["amount"] == "15000.00"
    assert job["buyer_tax_no"] is None
    with SessionLocal() as session:
        assert session.get(InvoiceJob, job["id"]).source_payload["token"] == "[REDACTED]"
    app.dependency_overrides.clear()


def test_sync_parse_errors_are_not_ingested():
    fake = FakeDingTalkClient(approvals=[approval(process_instance_id="bad-lines", form_values={**approval().form_values, "开票内容明细": "not-json"}), approval(process_instance_id="missing", form_values={"开票内容明细": "[]"})])
    app.dependency_overrides[get_dingtalk_client] = lambda: fake
    response = TestClient(app).post("/api/dingtalk/sync")
    assert response.json()["parse_failed"] == 2
    assert TestClient(app).get("/api/invoice-jobs").json() == []
    app.dependency_overrides.clear()


def test_missing_buyer_name_skips_only_that_approval_and_second_sync_is_idempotent():
    valid = approval(process_instance_id="valid-without-tax")
    missing_buyer = approval(process_instance_id="missing-buyer", form_values={key: value for key, value in approval().form_values.items() if key != "抬头名称"})
    fake = FakeDingTalkClient(approvals=[missing_buyer, valid])
    app.dependency_overrides[get_dingtalk_client] = lambda: fake
    first = TestClient(app).post("/api/dingtalk/sync").json()
    second = TestClient(app).post("/api/dingtalk/sync").json()
    assert first["created"] == 1
    assert first["parse_failure_reasons"] == {"MISSING_BUYER_NAME": 1}
    assert second["already_exists"] == 1
    assert second["parse_failure_reasons"] == {"MISSING_BUYER_NAME": 1}
    with SessionLocal() as session:
        job = session.query(InvoiceJob).one()
        assert job.buyer_tax_no is None
        assert job.requested_total_amount == job.amount
        assert len(job.line_items) == 1
    app.dependency_overrides.clear()
