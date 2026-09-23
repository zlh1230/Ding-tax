import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { useEffect, useRef, useState } from "react";
import { InvoiceJob, invoiceJobsApi, newestApprovalFirst, Summary } from "./api/invoiceJobs";
import "./styles.css";

function App() {
  const [jobs, setJobs] = useState<InvoiceJob[]>([]);
  const [summary, setSummary] = useState<Summary>({ pending: 0, processing: 0, completed: 0, exceptions: 0 });
  const [tab, setTab] = useState<"pending" | "processing" | "completed" | "exceptions">("pending");
  const [selected, setSelected] = useState<InvoiceJob | null>(null);
  const [message, setMessage] = useState("");
  const [operator, setOperator] = useState<string>("");
  const [syncing, setSyncing] = useState(false);
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null);
  const [syncFailed, setSyncFailed] = useState(false);
  const initialSyncStarted = useRef(false);
  const load = async () => { try { const [all, counts] = await Promise.all([invoiceJobsApi.list(), invoiceJobsApi.summary()]); setJobs(newestApprovalFirst(all)); setSummary(counts); } catch (error) { setMessage(error instanceof Error ? error.message : "请求失败"); } };
  const sync = async (manual = false) => {
    setSyncing(true);
    setSyncFailed(false);
    try {
      const result = await invoiceJobsApi.sync();
      setLastSyncAt(result.last_successful_sync_at);
      if (manual) setMessage(`已同步：新增 ${result.created} 条，更新 ${result.updated_pending} 条，已存在 ${result.already_exists} 条。`);
    } catch {
      setSyncFailed(true);
      setMessage("同步失败，已展示本地已有任务。");
    } finally {
      await load();
      setSyncing(false);
    }
  };
  useEffect(() => {
    if (initialSyncStarted.current) return;
    initialSyncStarted.current = true;
    const dd = (window as Window & { dd?: { requestAuthCode: (args: { clientId: string; corpId: string; success: (result: { code: string }) => void; fail: () => void }) => void } }).dd;
    const clientId = import.meta.env.VITE_DINGTALK_CLIENT_ID;
    const corpId = import.meta.env.VITE_DINGTALK_CORP_ID;
    void invoiceJobsApi.me().then((user) => { setOperator(user.name); return sync(); }).catch(() => {
      if (dd && clientId && corpId) dd.requestAuthCode({ clientId, corpId, success: (result) => { void invoiceJobsApi.auth(result.code).then((user) => { setOperator(user.name); return sync(); }).catch(() => setMessage("钉钉免登失败")); }, fail: () => setMessage("钉钉免登失败") });
      else if (!dd) void sync();
      else setMessage("钉钉应用配置不完整");
    });
  }, []);
  const claim = async (job: InvoiceJob) => { try { await invoiceJobsApi.claim(job.id); setMessage("任务已领取，等待开票助手执行"); await load(); } catch (error) { setMessage(error instanceof Error ? error.message : "请求失败"); } };
  const importMock = async () => { try { await invoiceJobsApi.importMock(); setMessage("演示数据已加载"); await load(); } catch (error) { setMessage(error instanceof Error ? error.message : "请求失败"); } };
  const groups = { pending: ["PENDING"], processing: ["CLAIMED", "ISSUING", "WAITING_CONFIRMATION", "ISSUED", "UPLOADING"], completed: ["COMPLETED"], exceptions: ["ISSUE_FAILED", "UPLOAD_FAILED", "UNKNOWN_RESULT"] };
  const visibleJobs = jobs.filter((job) => groups[tab].includes(job.status));
  const labels = { pending: "待开票", processing: "处理中", completed: "已完成", exceptions: "异常" };
  return <main>
    <header><h1>开票工作台</h1><div>{operator && <span>当前开票员：{operator}　</span>}<button disabled={syncing} onClick={() => void sync(true)}>{syncing ? "正在同步…" : "刷新钉钉审批"}</button>{import.meta.env.DEV && <button onClick={() => void importMock()}>加载演示数据</button>}</div></header>
    <section className="summary">{([['pending', '待开票', summary.pending], ['processing', '处理中', summary.processing], ['completed', '已完成', summary.completed], ['exceptions', '异常', summary.exceptions]] as const).map(([key, label, value]) => <button className={tab === key ? "active" : ""} key={key} onClick={() => setTab(key)}><span>{label}</span><strong>{value}</strong></button>)}</section>
    <p className="sync-status" aria-live="polite">{syncing ? "正在同步钉钉审批…" : syncFailed ? "同步失败，当前展示本地已有任务。" : lastSyncAt ? `上次同步时间：${new Date(lastSyncAt).toLocaleString()}` : ""}</p>
    {message && <p className="message">{message}</p>}
    <nav>{(Object.keys(labels) as Array<keyof typeof labels>).map((key) => <button className={tab === key ? "active" : ""} key={key} onClick={() => setTab(key)}>{labels[key]}</button>)}</nav>
    <section className="jobs">{visibleJobs.map((job) => <article key={job.id}><div><h2>{job.buyer_name}</h2><p>{job.invoice_type === "SPECIAL" ? "专票" : "普票"} · ¥{job.amount} · {job.invoice_content}</p><p>备注：{job.remark ?? "-"}　部门：{job.department ?? "-"}</p><p>审批编号：{job.approval_no ?? "-"}　通过时间：{new Date(job.approved_at).toLocaleString()}</p></div><div className="actions"><button onClick={() => setSelected(job)}>查看</button>{job.status === "PENDING" && <button onClick={() => void claim(job)}>开始开票</button>}</div></article>)}{visibleJobs.length === 0 && <p>暂无任务。开发环境可先加载演示数据。</p>}</section>
    {selected && <div className="modal" role="dialog"><section><button className="close" onClick={() => setSelected(null)}>×</button><h2>{selected.buyer_name}</h2><p>销方：{selected.seller_name}</p><p>税号：{selected.buyer_tax_no}</p><p>审批实例：{selected.process_instance_id}</p><p>付款条件：{selected.payment_condition}</p><p>状态：{selected.status}</p></section></div>}
  </main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
