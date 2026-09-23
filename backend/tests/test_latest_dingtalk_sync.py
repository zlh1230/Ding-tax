from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest
from fastapi.testclient import TestClient

from app.integrations.dingtalk.client import DingTalkConfigurationError, OfficialDingTalkClient, get_dingtalk_client
from app.integrations.dingtalk.parser import DingTalkApprovalParser
from app.integrations.dingtalk.schemas import DingTalkApprovalInstance
from app.main import app
from app.core.database import SessionLocal
from app.models import DingTalkSyncState, InvoiceJob, InvoiceJobStatus, InvoiceType
from app.services.dingtalk_sync import sync_dingtalk_approvals


def approval(instance_id: str, finished_at: datetime, *, status: str = "COMPLETED", result: str = "agree", invoice_type: str = "专票", amount: str = "10.00", lines: int = 1) -> DingTalkApprovalInstance:
    rows = [{"rowValue": [{"label": "开票内容", "value": f"service-{number}"}, {"label": "数量", "value": "1"}, {"label": "金额（元）", "value": amount}]} for number in range(1, lines + 1)]
    return DingTalkApprovalInstance(
        process_instance_id=instance_id,
        process_code="invoice-process",
        status=status,
        result=result,
        started_at=finished_at - timedelta(minutes=5),
        finished_at=finished_at,
        approved_at=finished_at,
        approval_no=f"approval-{instance_id}",
        form_values={"开票类型": invoice_type, "票款情况": "先开票再收款", "收款公司": "seller", "抬头类型": "企业", "抬头名称": "buyer", "开票内容明细": json.dumps(rows)},
        source_payload={"token": "redact-me"},
    )


class FakeSyncClient:
    def __init__(self, instances, *, ids=None, detail_failed=0):
        self.instances = instances
        self.calls = []
        self.last_sync_diagnostics = {"instance_id_count": ids if ids is not None else len(instances), "detail_failed_count": detail_failed}

    def list_approval_instances(self, process_code, start_at, end_at):
        self.calls.append((process_code, start_at, end_at))
        return self.instances


def test_latest_approval_is_imported_and_first_in_api():
    base = datetime(2026, 9, 23, 10, tzinfo=timezone.utc)
    client = FakeSyncClient([approval("A", base), approval("B", base + timedelta(minutes=10))])
    with SessionLocal() as session:
        first = sync_dingtalk_approvals(session, client)
        assert first["created"] == 2
        cursor = session.get(DingTalkSyncState, "invoice-process").last_successful_dingtalk_sync_at
        client.instances.append(approval("C", base + timedelta(minutes=20)))
        second = sync_dingtalk_approvals(session, client)
        assert second["created"] == 1
        expected_start = (cursor.replace(tzinfo=timezone.utc) if cursor.tzinfo is None else cursor) - timedelta(hours=24)
        assert client.calls[1][1] == expected_start
    app.dependency_overrides[get_dingtalk_client] = lambda: client
    jobs = TestClient(app).get("/api/invoice-jobs").json()
    app.dependency_overrides.clear()
    assert jobs[0]["process_instance_id"] == "C"
    assert jobs[0]["ding_finished_at"].startswith("2026-09-23T10:20:00")


def test_overlap_is_idempotent_and_pending_detail_refreshes_line_items():
    timestamp = datetime(2026, 9, 23, 10, tzinfo=timezone.utc)
    client = FakeSyncClient([approval("refreshable", timestamp, amount="10.00")])
    with SessionLocal() as session:
        assert sync_dingtalk_approvals(session, client)["created"] == 1
        assert sync_dingtalk_approvals(session, client)["already_exists"] == 1
        client.instances = [approval("refreshable", timestamp + timedelta(minutes=1), amount="20.00", lines=2)]
        assert sync_dingtalk_approvals(session, client)["updated_pending"] == 1
        job = session.query(InvoiceJob).filter_by(process_instance_id="refreshable").one()
        assert job.amount == Decimal("40.00")
        assert len(job.line_items) == 2


def test_non_pending_job_is_never_overwritten():
    timestamp = datetime(2026, 9, 23, 10, tzinfo=timezone.utc)
    client = FakeSyncClient([approval("claimed", timestamp, amount="10.00")])
    with SessionLocal() as session:
        sync_dingtalk_approvals(session, client)
        job = session.query(InvoiceJob).filter_by(process_instance_id="claimed").one()
        job.status = InvoiceJobStatus.CLAIMED
        session.commit()
        client.instances = [approval("claimed", timestamp + timedelta(minutes=1), amount="20.00")]
        result = sync_dingtalk_approvals(session, client)
        session.refresh(job)
        assert result["already_exists"] == 1
        assert job.amount == Decimal("10.00")


def test_filter_requires_completed_and_agree_and_detail_failure_does_not_block_latest():
    timestamp = datetime(2026, 9, 23, 10, tzinfo=timezone.utc)
    client = FakeSyncClient([
        approval("running", timestamp, status=" running ", result="agree"),
        approval("rejected", timestamp + timedelta(minutes=1), result="reject"),
        approval("latest", timestamp + timedelta(minutes=2), status="completed", result=" AGREE "),
    ], ids=4, detail_failed=1)
    with SessionLocal() as session:
        result = sync_dingtalk_approvals(session, client)
        assert {key: result[key] for key in ("approved", "created", "skipped", "detail_failed", "running_count", "completed_agree_count", "completed_reject_count")} == {"approved": 1, "created": 1, "skipped": 2, "detail_failed": 1, "running_count": 1, "completed_agree_count": 1, "completed_reject_count": 1}
        assert session.query(InvoiceJob).one().process_instance_id == "latest"


def test_new_sync_endpoint_returns_safe_latest_summary_without_payload():
    timestamp = datetime(2026, 9, 23, 10, tzinfo=timezone.utc)
    app.dependency_overrides[get_dingtalk_client] = lambda: FakeSyncClient([approval("endpoint", timestamp)])
    response = TestClient(app).post("/api/dingtalk/invoice-jobs/sync")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert {"scanned", "approved", "created", "updated_pending", "already_exists", "skipped", "detail_failed", "parse_failed", "last_successful_sync_at"} <= body.keys()
    assert "token" not in str(body).lower()


def test_parser_supports_only_special_and_normal_with_decimal_multiline_total():
    timestamp = datetime(2026, 9, 23, 10, tzinfo=timezone.utc)
    special = DingTalkApprovalParser().parse(approval("special", timestamp, invoice_type="专票", amount="1.25", lines=2))
    normal = DingTalkApprovalParser().parse(approval("normal", timestamp, invoice_type="普票", amount="2.50"))
    assert special.invoice_type == InvoiceType.SPECIAL
    assert normal.invoice_type == InvoiceType.NORMAL
    assert special.requested_total_amount == Decimal("2.50")


def test_parser_accepts_tablefield_value_already_decoded_by_dingtalk():
    timestamp = datetime(2026, 9, 23, 10, tzinfo=timezone.utc)
    instance = approval("decoded-table", timestamp)
    values = dict(instance.form_values)
    values["开票内容明细"] = json.loads(values["开票内容明细"])
    parsed = DingTalkApprovalParser().parse(instance.__class__(**{**instance.__dict__, "form_values": values}))
    assert parsed.line_items[0].amount == Decimal("10.00")


def test_sync_cursor_does_not_advance_after_batch_failure():
    class BrokenClient:
        def list_approval_instances(self, *_):
            raise DingTalkConfigurationError("offline")

    with SessionLocal() as session:
        with pytest.raises(DingTalkConfigurationError):
            sync_dingtalk_approvals(session, BrokenClient())
        assert session.get(DingTalkSyncState, "invoice-process") is None


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code, self.body = status_code, body

    @property
    def is_error(self):
        return self.status_code >= 400

    def json(self):
        return self.body


class FakeHttpClient:
    def __init__(self):
        self.list_calls = []
        self.detail_calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def post(self, url, **kwargs):
        if url.endswith("accessToken"):
            return FakeResponse(200, {"accessToken": "test-token"})
        self.list_calls.append(kwargs["json"])
        token = kwargs["json"]["nextToken"]
        return FakeResponse(200, {"result": {"list": ["A", "B"] if token == 0 else ["B", "C"], "nextToken": "more" if token == 0 else "0"}})

    def get(self, url, **kwargs):
        instance_id = kwargs["params"]["processInstanceId"]
        self.detail_calls.append(instance_id)
        if instance_id == "B":
            return FakeResponse(500, {})
        return FakeResponse(200, {"result": {"processCode": "invoice-process", "status": "COMPLETED", "result": "agree", "startTime": "1780000000000", "finishTime": "1780000300000", "formComponentValues": []}})


def test_official_client_paginates_deduplicates_and_stops_on_string_zero(monkeypatch):
    import app.integrations.dingtalk.client as client_module

    monkeypatch.setattr(client_module, "DINGTALK_CLIENT_ID", "test-id")
    monkeypatch.setattr(client_module, "DINGTALK_CLIENT_SECRET", "test-secret")
    http = FakeHttpClient()
    client = OfficialDingTalkClient(lambda: http)
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    instances = client.list_approval_instances("invoice-process", start, start + timedelta(days=1))
    assert [call["nextToken"] for call in http.list_calls] == [0, "more"]
    assert all(call["maxResults"] == 20 and call["startTime"] == int(start.timestamp() * 1000) for call in http.list_calls)
    assert http.detail_calls == ["A", "B", "B", "C"]
    assert [item.process_instance_id for item in instances] == ["A", "C"]
    assert client.last_sync_diagnostics == {"list_page_count": 2, "instance_id_count": 3, "detail_failed_count": 1}
