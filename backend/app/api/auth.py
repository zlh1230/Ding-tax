from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.config import APP_ENV, DINGTALK_ALLOWED_USER_IDS
from app.integrations.dingtalk.client import DingTalkAuthenticationError, DingTalkConfigurationError, DingTalkClient, get_dingtalk_client
from app.schemas.auth import CurrentOperator, DingTalkAuthCode

router = APIRouter(prefix="/api/auth", tags=["auth"])


def require_operator(request: Request, x_dev_operator_id: str | None = Header(default=None)) -> CurrentOperator:
    operator = request.session.get("operator")
    if operator:
        return CurrentOperator(**operator)
    if APP_ENV == "development":
        return CurrentOperator(user_id=x_dev_operator_id or "development-browser", name="开发环境开票员")
    raise HTTPException(status_code=401, detail="Not authenticated")


@router.post("/dingtalk", response_model=CurrentOperator)
def dingtalk_login(payload: DingTalkAuthCode, request: Request, client: DingTalkClient = Depends(get_dingtalk_client)):
    try:
        user = client.exchange_auth_code(payload.auth_code)
    except DingTalkAuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="DingTalk login failed") from error
    except DingTalkConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if user.user_id not in DINGTALK_ALLOWED_USER_IDS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号没有开票工作台权限")
    request.session["operator"] = {"user_id": user.user_id, "name": user.name}
    return CurrentOperator(**request.session["operator"])


@router.get("/me", response_model=CurrentOperator)
def me(request: Request):
    operator = request.session.get("operator")
    if not operator:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return CurrentOperator(**operator)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"status": "ok"}
