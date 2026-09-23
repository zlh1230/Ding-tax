export type Status = "PENDING" | "CLAIMED" | "ISSUING" | "WAITING_CONFIRMATION" | "ISSUED" | "UPLOADING" | "COMPLETED" | "ISSUE_FAILED" | "UPLOAD_FAILED" | "UNKNOWN_RESULT";

export type InvoiceJob = {
  id: number; buyer_name: string; invoice_type: "NORMAL" | "SPECIAL"; amount: string;
  invoice_content: string; remark: string | null; department: string | null; approval_no: string | null;
  approved_at: string; status: Status; operator_id: string | null; seller_name: string;
  buyer_tax_no: string | null; payment_condition: string; process_instance_id: string;
  ding_started_at?: string | null; ding_finished_at?: string | null; created_at?: string;
};

export type Summary = { pending: number; processing: number; completed: number; exceptions: number };
export type DingTalkSyncSummary = {
  scanned: number; approved: number; created: number; updated_pending: number;
  already_exists: number; skipped: number; detail_failed: number; parse_failed: number;
  last_successful_sync_at: string;
};
const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

export function newestApprovalFirst(jobs: InvoiceJob[]): InvoiceJob[] {
  const timestamp = (job: InvoiceJob) => {
    const parsed = Date.parse(job.ding_finished_at ?? job.approved_at ?? job.created_at ?? "");
    return Number.isNaN(parsed) ? Number.NEGATIVE_INFINITY : parsed;
  };
  return jobs.map((job, index) => ({ job, index })).sort((left, right) => timestamp(right.job) - timestamp(left.job) || left.index - right.index).map(({ job }) => job);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { credentials: "include", ...options });
  if (!response.ok) throw new Error(response.status === 409 ? "该开票任务已被其他开票员领取或状态已变化，请刷新列表。" : "请求失败，请刷新后重试。");
  return response.json() as Promise<T>;
}

export const invoiceJobsApi = {
  list: () => request<InvoiceJob[]>("/api/invoice-jobs"),
  summary: () => request<Summary>("/api/invoice-jobs/summary"),
  importMock: () => request<{ created: number }>("/api/dev/mock-approvals/import", { method: "POST" }),
  claim: (id: number) => request<InvoiceJob>(`/api/invoice-jobs/${id}/claim`, { method: "POST", headers: { "X-Dev-Operator-Id": "dev-invoice-operator" } }),
  me: () => request<{ user_id: string; name: string }>("/api/auth/me"),
  auth: (auth_code: string) => request<{ user_id: string; name: string }>("/api/auth/dingtalk", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ auth_code }) }),
  sync: () => request<DingTalkSyncSummary>("/api/dingtalk/invoice-jobs/sync", { method: "POST" }),
};
