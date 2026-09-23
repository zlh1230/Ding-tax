# Architecture

```text
DingTalk H5
    ↓
FastAPI Backend
    ↓
Local Agent
    ↓
Electronic Tax Bureau
```

Design principles for later gates:

- `InvoiceJob` 是唯一的核心业务表：一条已审批通过、等待执行的开票任务。
- Canonical jobs use `requested_total_amount` as the authoritative Decimal total and ordered `InvoiceLineItem` records. Legacy `amount` mirrors that total during transition; legacy `invoice_content` remains display-only.
- Existing Gate 1 rows are legacy rows: migration backfills their canonical total from `amount` but intentionally leaves line items empty because their legacy content is not structured.
- Real DingTalk ingestion remains disabled until buyer validation rules for the tenant form are explicitly approved; buyer database constraints were not weakened.
- DingTalk authentication uses the official PC Micro App `dd.requestAuthCode` entry point; the backend exchanges its one-time code and stores only a short HttpOnly session cookie.
- DingTalk access is backend allowlisted by user ID. Live sync is manual/on-demand and only accepts the configured approval process code plus final agreed results.
- `process_instance_id` 是唯一且幂等的钉钉审批实例键。重复 Mock ingestion 返回原任务，不会覆盖已发生的状态。
- 所有时间以 UTC 存储。
- 状态只由 `InvoiceJobService` 转换：`PENDING → CLAIMED → ISSUING → WAITING_CONFIRMATION → ISSUED → UPLOADING → COMPLETED`；明确失败可到 `ISSUE_FAILED` / `UPLOAD_FAILED`，最终结果不明进入 `UNKNOWN_RESULT`。
- 领取采用单条条件 `UPDATE ... WHERE id = ? AND status = PENDING`。仅更新一行才成功，避免多开票员重复领取，且可迁移至 PostgreSQL。
- 未来 DingTalk adapter 只负责将已通过审批映射到 ingestion service；未来 Local Agent 只在任务领取后接收语义化动作，不直接改状态。
- If the tax bureau submission result is unknown, never retry issuance directly; use `UNKNOWN_RESULT`.
- Verification codes, CA, and mobile scans are completed manually. Automation never bypasses security checks.
- Initial final invoice confirmation remains manual.
- Secrets never enter Git. External APIs and tax-bureau DOM must be verified from official documentation or actual pages.
