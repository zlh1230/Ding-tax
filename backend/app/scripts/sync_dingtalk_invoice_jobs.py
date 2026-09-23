from app.core.database import SessionLocal
from app.integrations.dingtalk.client import DingTalkConfigurationError, get_dingtalk_client
from app.services.dingtalk_sync import sync_dingtalk_approvals


def main() -> int:
    with SessionLocal() as session:
        try:
            result = sync_dingtalk_approvals(session, get_dingtalk_client())
        except (DingTalkConfigurationError, ValueError):
            print("SYNC_STATUS = FAILED")
            return 1
    for key in ("scanned", "approved", "created", "updated_pending", "already_exists", "skipped", "detail_failed", "parse_failed", "last_successful_sync_at"):
        print(f"{key.upper()} = {result[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
