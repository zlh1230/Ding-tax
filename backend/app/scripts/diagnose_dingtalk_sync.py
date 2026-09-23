from datetime import datetime, timedelta, timezone
import json

from app.core.config import DINGTALK_PROCESS_CODE, DINGTALK_SYNC_LOOKBACK_DAYS, DINGTALK_SYNC_SAFETY_OVERLAP_HOURS
from app.core.database import SessionLocal
from app.integrations.dingtalk.client import DingTalkConfigurationError, get_dingtalk_client
from app.integrations.dingtalk.parser import ApprovalParseError, DingTalkApprovalParser
from app.models import DingTalkSyncState, InvoiceJob
from app.services.dingtalk_sync import _as_utc


def _time(value: datetime | None) -> str:
    return value.isoformat() if value else "UNKNOWN"


def _line_item_structure(instance) -> None:
    component = next((item for item in instance.form_components if item.get("name") == "开票内容明细"), None)
    print(f"LINE_ITEM_COMPONENT_PRESENT = {'YES' if component else 'NO'}")
    if not component:
        print("LINE_ITEM_VALUE_TYPE = NONE")
        return
    value = component.get("value")
    print(f"LINE_ITEM_VALUE_TYPE = {type(value).__name__}")
    try:
        rows = json.loads(value) if isinstance(value, str) else value
        first = rows[0] if isinstance(rows, list) and rows else {}
        cells = first.get("rowValue", []) if isinstance(first, dict) else []
        labels = [cell.get("label") for cell in cells if isinstance(cell, dict) and isinstance(cell.get("label"), str)]
        print(f"LINE_ITEM_ROW_COUNT = {len(rows) if isinstance(rows, list) else 'UNKNOWN'}")
        print(f"LINE_ITEM_CELL_LABELS = {','.join(labels) if labels else 'NONE'}")
        print(f"LINE_ITEM_CELL_LABEL_CODEPOINTS = {','.join('-'.join(f'{ord(char):04X}' for char in label) for label in labels) if labels else 'NONE'}")
    except (TypeError, ValueError, json.JSONDecodeError):
        print("LINE_ITEM_STRUCTURE = UNREADABLE")


def main() -> int:
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        state = session.get(DingTalkSyncState, DINGTALK_PROCESS_CODE) if DINGTALK_PROCESS_CODE else None
        start = _as_utc(state.last_successful_dingtalk_sync_at) - timedelta(hours=DINGTALK_SYNC_SAFETY_OVERLAP_HOURS) if state else now - timedelta(days=DINGTALK_SYNC_LOOKBACK_DAYS)
        print(f"NOW_UTC = {_time(now)}")
        print(f"SYNC_WINDOW_START = {_time(start)}")
        print(f"SYNC_WINDOW_END = {_time(now)}")
        print(f"PROCESS_CODE_PRESENT = {'YES' if DINGTALK_PROCESS_CODE else 'NO'}")
        if not DINGTALK_PROCESS_CODE:
            return 2
        try:
            client = get_dingtalk_client()
            instances = client.list_approval_instances(DINGTALK_PROCESS_CODE, start, now)
        except DingTalkConfigurationError:
            print("LIST_PAGE_COUNT = 0")
            print("INSTANCE_ID_COUNT = 0")
            print("DETAIL_FETCH_OK = NO")
            return 1
        diagnostics = getattr(client, "last_sync_diagnostics", {})
        print(f"LIST_PAGE_COUNT = {diagnostics.get('list_page_count', 'UNKNOWN')}")
        print(f"INSTANCE_ID_COUNT = {diagnostics.get('instance_id_count', len(instances))}")
        latest = max(instances, key=lambda item: item.finished_at or item.approved_at or item.started_at or datetime.min.replace(tzinfo=timezone.utc), default=None)
        print(f"LATEST_INSTANCE_START_TIME = {_time(latest.started_at) if latest else 'NONE'}")
        print(f"LATEST_INSTANCE_FINISH_TIME = {_time((latest.finished_at or latest.approved_at) if latest else None)}")
        print(f"LATEST_INSTANCE_STATUS = {latest.status.strip().upper() if latest else 'NONE'}")
        print(f"LATEST_INSTANCE_RESULT = {latest.result.strip().lower() if latest else 'NONE'}")
        print(f"DETAIL_FETCH_OK = {'YES' if not diagnostics.get('detail_failed_count') else 'NO'}")
        if latest is None:
            print("PARSER_OK = NO")
            print("SKIP_REASON = NO_INSTANCES")
            print("DB_EXISTS = NO")
            print("WORKBENCH_VISIBLE = NO")
            return 0
        names = [item.get("name") for item in latest.form_components if isinstance(item, dict) and isinstance(item.get("name"), str)]
        print(f"FORM_FIELD_NAME_CODEPOINTS = {','.join('-'.join(f'{ord(char):04X}' for char in name) for name in names)}")
        _line_item_structure(latest)
        try:
            DingTalkApprovalParser().parse(latest)
            parser_ok, skip_reason = "YES", "NONE"
        except ApprovalParseError as error:
            parser_ok, skip_reason = "NO", error.code
        job = session.query(InvoiceJob).filter_by(process_instance_id=latest.process_instance_id).one_or_none()
        print(f"PARSER_OK = {parser_ok}")
        print(f"SKIP_REASON = {skip_reason}")
        print(f"DB_EXISTS = {'YES' if job else 'NO'}")
        print(f"WORKBENCH_VISIBLE = {'YES' if job else 'NO'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
