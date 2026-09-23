from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.dingtalk import router as dingtalk_router
from app.api.invoice_jobs import router as invoice_jobs_router
from app.core.config import APP_ENV, FRONTEND_ORIGIN, SESSION_SECRET

app = FastAPI(title="DingInvoiceMVP Backend")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, https_only=APP_ENV == "production", same_site="lax")
if APP_ENV == "development":
    app.add_middleware(CORSMiddleware, allow_origins=[FRONTEND_ORIGIN], allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Dev-Operator-Id"], allow_credentials=True)
app.include_router(invoice_jobs_router)
app.include_router(auth_router)
app.include_router(dingtalk_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ding-invoice-backend"}
