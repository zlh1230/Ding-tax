from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import DINGTALK_PROCESS_CODE, DINGTALK_SYNC_LOOKBACK_DAYS, DINGTALK_SYNC_SAFETY_OVERLAP_HOURS
from app.integrations.dingtalk.client import DingTalkClient
from app.integrations.dingtalk.parser import ApprovalParseError, DingTalkApprovalParser
from app.models import DingTalkSyncState
from app.services.dingtalk_ingestion import DingTalkApprovalIngestionService


def sync_dingtalk_approvals(session: Session, client: DingTalkClient) -> dict:
    if not DINGTALK_PROCESS_CODE:
        raise ValueError("DINGTALK_PROCESS_CODE is not configured")
    end_at = datetime.now(timezone.utc)
    state = session.get(DingTalkSyncState, DINGTALK_PROCESS_CODE)
    last_successful_at = _as_utc(state.last_successful_dingtalk_sync_at) if state else None
    start_at = last_successful_at - timedelta(hours=DINGTALK_SYNC_SAFETY_OVERLAP_HOURS) if last_successful_at else end_at - timedelta(days=DINGTALK_SYNC_LOOKBACK_DAYS)
    instances = client.list_approval_instances(DINGTALK_PROCESS_CODE, start_at, end_at)
    diagnostics = getattr(client, "last_sync_diagnostics", {})
    summary = {
        "scanned": int(diagnostics.get("instance_id_count", len(instances))), "approved": 0,
        "created": 0, "updated_pending": 0, "already_exists": 0, "skipped": 0,
        "detail_failed": int(diagnostics.get("detail_failed_count", 0)), "parse_failed": 0,
        "parse_failure_reasons": {}, "running_count": 0, "completed_agree_count": 0,
        "completed_reject_count": 0, "terminated_count": 0,
    }
    parser, ingestion = DingTalkApprovalParser(), DingTalkApprovalIngestionService()
    for instance in instances:
        status, result = instance.status.strip().upper(), instance.result.strip().lower()
        if status == "RUNNING":
            summary["running_count"] += 1
        elif status == "TERMINATED":
            summary["terminated_count"] += 1
        elif status == "COMPLETED" and result == "agree":
            summary["completed_agree_count"] += 1
        elif status == "COMPLETED":
            summary["completed_reject_count"] += 1
        if instance.process_code != DINGTALK_PROCESS_CODE or status != "COMPLETED" or result != "agree":
            summary["skipped"] += 1
            continue
        summary["approved"] += 1
        try:
            _, outcome = ingestion.upsert(session, parser.parse(instance))
            summary[outcome] += 1
        except ApprovalParseError as error:
            summary["parse_failed"] += 1
            summary["parse_failure_reasons"][error.code] = summary["parse_failure_reasons"].get(error.code, 0) + 1
    if state is None:
        state = DingTalkSyncState(process_code=DINGTALK_PROCESS_CODE, last_successful_dingtalk_sync_at=end_at)
        session.add(state)
    else:
        state.last_successful_dingtalk_sync_at = end_at
    session.commit()
    summary["last_successful_sync_at"] = end_at.isoformat()
    return summary


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
