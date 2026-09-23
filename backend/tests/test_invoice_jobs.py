from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models import InvoiceJob, InvoiceJobStatus, InvoiceType, PaymentCondition
from app.schemas.invoice_job import MockApprovalInput
from app.services.dingtalk_ingestion import DingTalkApprovalIngestionService
from app.services.invoice_job_service import InvoiceJobConflictError, InvoiceJobService

client = TestClient(app)


def mock_input(instance_id: str = "approval-1") -> MockApprovalInput:
    return MockApprovalInput(process_instance_id=instance_id, approval_no="TEST-1", invoice_type=InvoiceType.SPECIAL, payment_condition=PaymentCondition.BEFORE_PAYMENT, seller_name="Seller", buyer_name="Buyer", buyer_tax_no="91330100TEST", amount=Decimal("15000.00"), invoice_content="认证费", remark="备注", department="测试部", approved_at=datetime(2026, 9, 16, tzinfo=timezone.utc))


def create_job(instance_id: str = "approval-1") -> InvoiceJob:
    with SessionLocal() as session:
        job, _ = DingTalkApprovalIngestionService().ingest(session, mock_input(instance_id))
        return job


def test_ingestion_is_idempotent_and_preserves_decimal():
    with SessionLocal() as session:
        service = DingTalkApprovalIngestionService()
        first, created = service.ingest(session, mock_input())
        second, duplicate_created = service.ingest(session, mock_input())
        assert created is True
        assert duplicate_created is False
        assert first.id == second.id
        assert first.amount == Decimal("15000.00")
    response = client.get("/api/invoice-jobs")
    assert len(response.json()) == 1
    assert response.json()[0]["amount"] == "15000.00"


def test_claim_is_atomic_and_second_claim_is_conflict():
    job = create_job()
    first = client.post(f"/api/invoice-jobs/{job.id}/claim", headers={"X-Dev-Operator-Id": "operator-a"})
    second = client.post(f"/api/invoice-jobs/{job.id}/claim", headers={"X-Dev-Operator-Id": "operator-b"})
    assert first.status_code == 200
    assert first.json()["operator_id"] == "operator-a"
    assert first.json()["status"] == "CLAIMED"
    assert second.status_code == 409


def test_completed_and_unknown_result_cannot_be_claimed():
    completed = create_job("completed")
    unknown = create_job("unknown")
    with SessionLocal() as session:
        service = InvoiceJobService()
        for job, final_status in ((session.get(InvoiceJob, completed.id), InvoiceJobStatus.COMPLETED), (session.get(InvoiceJob, unknown.id), InvoiceJobStatus.UNKNOWN_RESULT)):
            service.claim(session, job.id, "operator-a")
            service.transition(session, job, InvoiceJobStatus.ISSUING)
            service.transition(session, job, InvoiceJobStatus.WAITING_CONFIRMATION)
            if final_status == InvoiceJobStatus.COMPLETED:
                service.transition(session, job, InvoiceJobStatus.ISSUED)
                service.transition(session, job, InvoiceJobStatus.UPLOADING)
            service.transition(session, job, final_status)
    assert client.post(f"/api/invoice-jobs/{completed.id}/claim", headers={"X-Dev-Operator-Id": "operator-b"}).status_code == 409
    assert client.post(f"/api/invoice-jobs/{unknown.id}/claim", headers={"X-Dev-Operator-Id": "operator-b"}).status_code == 409


def test_illegal_transition_is_rejected():
    job = create_job()
    with SessionLocal() as session:
        with pytest.raises(InvoiceJobConflictError):
            InvoiceJobService().transition(session, session.get(InvoiceJob, job.id), InvoiceJobStatus.COMPLETED)


def test_required_state_transitions():
    pending_to_unknown = create_job("to-unknown")
    claim_to_failure = create_job("to-issue-failure")
    upload_to_failure = create_job("to-upload-failure")
    with SessionLocal() as session:
        service = InvoiceJobService()
        unknown = session.get(InvoiceJob, pending_to_unknown.id)
        service.claim(session, unknown.id, "operator")
        service.transition(session, unknown, InvoiceJobStatus.ISSUING)
        service.transition(session, unknown, InvoiceJobStatus.WAITING_CONFIRMATION)
        assert service.transition(session, unknown, InvoiceJobStatus.UNKNOWN_RESULT).status == InvoiceJobStatus.UNKNOWN_RESULT

        issue_failure = session.get(InvoiceJob, claim_to_failure.id)
        service.claim(session, issue_failure.id, "operator")
        assert service.transition(session, issue_failure, InvoiceJobStatus.ISSUE_FAILED).status == InvoiceJobStatus.ISSUE_FAILED

        upload_failure = session.get(InvoiceJob, upload_to_failure.id)
        service.claim(session, upload_failure.id, "operator")
        service.transition(session, upload_failure, InvoiceJobStatus.ISSUING)
        service.transition(session, upload_failure, InvoiceJobStatus.WAITING_CONFIRMATION)
        service.transition(session, upload_failure, InvoiceJobStatus.ISSUED)
        service.transition(session, upload_failure, InvoiceJobStatus.UPLOADING)
        assert service.transition(session, upload_failure, InvoiceJobStatus.UPLOAD_FAILED).status == InvoiceJobStatus.UPLOAD_FAILED


def test_summary_and_mock_import_are_idempotent():
    first = client.post("/api/dev/mock-approvals/import")
    second = client.post("/api/dev/mock-approvals/import")
    assert first.json() == {"created": 4, "already_exists": 0, "total": 4}
    assert second.json() == {"created": 0, "already_exists": 4, "total": 4}
    assert client.get("/api/invoice-jobs/summary").json() == {"pending": 2, "processing": 0, "completed": 1, "exceptions": 1}


def test_development_endpoints_are_hidden_outside_development(monkeypatch):
    monkeypatch.setattr("app.api.invoice_jobs.APP_ENV", "production")
    assert client.post("/api/dev/mock-approvals/import").status_code == 404
    assert client.post("/api/invoice-jobs/1/claim", headers={"X-Dev-Operator-Id": "operator"}).status_code == 404
