# DingInvoiceMVP

钉钉开票工作台与电子税务局自动开票助手的独立 MVP 项目。

组件：

- `frontend/`：钉钉 H5 开票工作台（React、TypeScript、Vite）
- `backend/`：本地 API（FastAPI、SQLAlchemy、Alembic、SQLite）
- `agent/`：Windows 本地自动化 Agent（Python、Playwright）

## 本地启动

Backend：

```powershell
cd C:\DingInvoiceMVP\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:8000/health`。

Frontend：

```powershell
cd C:\DingInvoiceMVP\frontend
npm install
npm run dev
```

Agent：

```powershell
cd C:\DingInvoiceMVP\agent
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python src\main.py
```

开票专用 Chrome（人工登录后供 Agent 复用）：

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\DingInvoiceMVP\agent\chrome-etax-profile"
```

## 数据库 migration

```powershell
cd C:\DingInvoiceMVP\backend
.\.venv\Scripts\alembic upgrade head
```

## 演示工作台

先启动 backend，再启动 frontend。在开发环境中，点击工作台的“加载演示数据”，或执行：

```powershell
Invoke-WebRequest -Method POST http://127.0.0.1:8000/api/dev/mock-approvals/import
```

待开票任务可由开发用 header `X-Dev-Operator-Id` 领取；工作台的“开始开票”会调用该接口。此机制仅在 `APP_ENV=development` 可用。

## 当前阶段

当前为 `GATE_1_INVOICE_JOB_AND_MOCK_WORKBENCH`。没有真实钉钉 API，也不会访问电子税务局。

**THIS PROJECT DOES NOT YET SUBMIT REAL TAX INVOICES.**
