from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import CurrentOperator, require_operator
from app.core.database import get_db
from app.integrations.dingtalk.client import DingTalkClient, DingTalkConfigurationError, get_dingtalk_client
from app.services.dingtalk_sync import sync_dingtalk_approvals

router = APIRouter(prefix="/api/dingtalk", tags=["dingtalk"])


def _sync(db: Session, client: DingTalkClient):
    try:
        return sync_dingtalk_approvals(db, client)
    except (DingTalkConfigurationError, ValueError) as error:
        raise HTTPException(status_code=503, detail="DingTalk sync is unavailable") from error


@router.post("/invoice-jobs/sync")
def sync_invoice_jobs(current_operator: CurrentOperator = Depends(require_operator), db: Session = Depends(get_db), client: DingTalkClient = Depends(get_dingtalk_client)):
    return _sync(db, client)


@router.post("/sync", include_in_schema=False)
def sync_legacy(current_operator: CurrentOperator = Depends(require_operator), db: Session = Depends(get_db), client: DingTalkClient = Depends(get_dingtalk_client)):
    return _sync(db, client)
