import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const api = readFileSync(new URL("../src/api/invoiceJobs.ts", import.meta.url), "utf8");
const app = readFileSync(new URL("../src/main.tsx", import.meta.url), "utf8");

test("workbench initial load syncs DingTalk and then refreshes local jobs", () => {
  assert.match(api, /\/api\/dingtalk\/invoice-jobs\/sync/);
  assert.match(app, /return sync\(\);/);
  assert.match(app, /finally \{\s*await load\(\);/);
});

test("manual refresh uses the same sync flow and failure preserves local loading", () => {
  assert.match(app, /onClick=\{\(\) => void sync\(true\)\}/);
  assert.match(app, /同步失败，已展示本地已有任务/);
  assert.match(app, /setSyncing\(false\)/);
});

test("workbench retains newest DingTalk completion first", () => {
  assert.match(api, /ding_finished_at \?\? job\.approved_at/);
  assert.match(app, /setJobs\(newestApprovalFirst\(all\)\)/);
});
