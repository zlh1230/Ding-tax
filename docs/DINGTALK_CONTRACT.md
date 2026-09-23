# DingTalk contract

Query date: 2026-09-16.

| Official document | API / JSAPI | Confirmed use in this project |
| --- | --- | --- |
| [获取微应用免登授权码](https://open.dingtalk.com/tools/explorer/jsapi?id=11723) | `dd.requestAuthCode` | Current Micro App JSAPI, supported for Windows. Input: `clientId`, `corpId`; output: `code`. The official Explorer says the code is returned to the app. |
| [获取用户token](https://open.dingtalk.com/document/orgapp/obtain-user-token) | server user-token exchange | Backend-only exchange of the frontend code; Client Secret never reaches the browser. Exact request/response fields must be verified in the enterprise API Explorer before enabling the HTTP adapter. |
| [获取企业内部应用的accessToken](https://open.dingtalk.com/document/orgapp/obtain-the-access_token-of-an-internal-app) | internal-app access token | Backend-only application credential. Exact request/response fields must be verified in the enterprise API Explorer before enabling the HTTP adapter. |
| [获取单个审批实例详情](https://open.dingtalk.com/document/orgapp/obtains-the-details-of-a-single-approval-instance) | approval-instance detail | Required to obtain the approved result, completion time, process code, instance ID and forms. Raw field paths are intentionally not guessed. |
| [JSAPI Explorer: requestAuthInfo](https://open.dingtalk.com/tools/explorer/jsapi?id=10296) | `dd.requestAuthInfo` | Official Explorer documents approval-data authorization using `modelKey: dd.oa|bpms`, `bizScene: processCode`, and one process code. Permission applicability is TO_VERIFY in the tenant console. |

## Contract boundary

## Verified approval instance APIs (2026-09-17)

| API | Method and endpoint | Authentication | Request / response |
| --- | --- | --- | --- |
| 获取审批实例 ID 列表 | `POST https://api.dingtalk.com/v1.0/workflow/processes/instanceIds/query` | `x-acs-dingtalk-access-token` | Body: `processCode`, epoch-millisecond `startTime`/`endTime`, `nextToken` (start at `0`), `maxResults` (at most `20`), `statuses: ["COMPLETED"]`; response wraps `list` in `result`. Continue only if a returned `nextToken` is present. Scope: `Workflow.Instance.Read`. |
| 获取单个审批实例详情 | `GET https://api.dingtalk.com/v1.0/workflow/processInstances?processInstanceId=...` | `x-acs-dingtalk-access-token` | Response wraps data in `result`, including `status`, `result`, `finishTime`, and `formComponentValues`. Tenant-approved condition is `status == COMPLETED` and `result == agree` (case-normalized). Scope: `Workflow.Instance.Read`. |

The verified seven-day completed query returned six instance IDs. The previously tried `/v1.0/workflow/processes/{processCode}/form` endpoint is obsolete for this project and must not be used.

The observed `开票内容明细` component is `TableField`; its `value` is a JSON string encoding a list of rows. Each row has `rowNumber` and `rowValue`; `rowValue` is a list of objects with `label`, `key`, and `value`. Across six read-only samples, the observed columns are `开票内容`, `单价`, `数量`, and `金额（元）`; all samples had one row and the amount shape parsed as Decimal. This shape is only a structural contract: never log row values.

Current tenant form labels include `收款公司`, `票款情况`, `抬头类型`, `抬头名称`, `公司税号`, `开票类型`, `公司开户行`, `开户行账号`, `公司地址`, `公司电话`, `开票内容明细`, and `备注`. Conditional fields may legitimately be absent.

`DingTalkClient` returns an adapter-normalized `DingTalkApprovalInstance`; only `DingTalkApprovalParser` maps its configured form titles into canonical invoice data. `DINGTALK_FIELD_MAP` is centralized in `backend/app/integrations/dingtalk/parser.py`.

The live HTTP adapter is deliberately disabled until the enterprise API Explorer supplies the exact current approval list/detail payload, endpoint, pagination cursor, rate limit and granted scopes. This avoids inventing a real DingTalk contract. The parser then must be updated from an approved captured test payload before live sync is enabled.

Only result `AGREE` / `APPROVED` and the configured process code may enter ingestion. Amount strings accept `15000`, `15000.00`, and `15,000.00` as `Decimal`; missing required fields and malformed amount values fail closed. Stored source payloads recursively redact keys containing `token`, `secret`, or `password`.
