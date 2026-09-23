from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import InvoiceJobStatus, InvoiceType, PaymentCondition
from app.schemas.invoice_job import MockApprovalInput
from app.services.dingtalk_ingestion import DingTalkApprovalIngestionService
from app.services.invoice_job_service import InvoiceJobService


MOCK_APPROVALS = [
    MockApprovalInput(process_instance_id="mock-approved-001", approval_no="DING-MOCK-001", invoice_type=InvoiceType.SPECIAL, payment_condition=PaymentCondition.BEFORE_PAYMENT, seller_name="浙江鸿程计算机系统有限公司", buyer_name="杭州示例科技有限公司", buyer_tax_no="91330100MOCK00001", amount=Decimal("15000.00"), invoice_content="认证费", remark="知识产权体系", department="杭州审核一部", approved_at=datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc)),
    MockApprovalInput(process_instance_id="mock-approved-002", approval_no="DING-MOCK-002", invoice_type=InvoiceType.NORMAL, payment_condition=PaymentCondition.AFTER_PAYMENT, seller_name="示例服务有限公司", buyer_name="上海演示贸易有限公司", buyer_tax_no="91310100MOCK00002", amount=Decimal("2680.50"), invoice_content="技术服务费", remark="开发环境测试", department="上海服务组", approved_at=datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)),
    MockApprovalInput(process_instance_id="mock-approved-003", approval_no="DING-MOCK-003", invoice_type=InvoiceType.NORMAL, payment_condition=PaymentCondition.OTHER, seller_name="示例服务有限公司", buyer_name="北京演示咨询有限公司", buyer_tax_no="91110100MOCK00003", amount=Decimal("980.00"), invoice_content="咨询服务费", department="北京服务组", approved_at=datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc)),
    MockApprovalInput(process_instance_id="mock-approved-004", approval_no="DING-MOCK-004", invoice_type=InvoiceType.SPECIAL, payment_condition=PaymentCondition.BEFORE_PAYMENT, seller_name="示例服务有限公司", buyer_name="广州演示制造有限公司", buyer_tax_no="91440100MOCK00004", amount=Decimal("5200.00"), invoice_content="软件服务费", remark="异常演示", department="广州服务组", approved_at=datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc)),
]


def import_mock_approvals(session: Session) -> dict:
    ingestion = DingTalkApprovalIngestionService()
    transitions = InvoiceJobService()
    jobs = []
    created_count = 0
    for approval in MOCK_APPROVALS:
        job, created = ingestion.ingest(session, approval)
        created_count += created
        jobs.append(job)
    for job, status in ((jobs[2], InvoiceJobStatus.COMPLETED), (jobs[3], InvoiceJobStatus.ISSUE_FAILED)):
        if job.status != InvoiceJobStatus.PENDING:
            continue
        transitions.claim(session, job.id, "demo-operator")
        job = session.get(type(job), job.id)
        if status == InvoiceJobStatus.COMPLETED:
            for target in (InvoiceJobStatus.ISSUING, InvoiceJobStatus.WAITING_CONFIRMATION, InvoiceJobStatus.ISSUED, InvoiceJobStatus.UPLOADING, InvoiceJobStatus.COMPLETED):
                transitions.transition(session, job, target)
        else:
            transitions.transition(session, job, InvoiceJobStatus.ISSUE_FAILED)
    return {"created": created_count, "already_exists": len(MOCK_APPROVALS) - created_count, "total": len(MOCK_APPROVALS)}
