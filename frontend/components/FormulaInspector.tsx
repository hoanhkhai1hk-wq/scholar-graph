"use client";
import { useCallback, useEffect, useState } from "react";
import { workspacePost, workspaceRequest, workspaceUrl } from "@/lib/workspace";
import TaskMonitor, { type WorkspaceTask } from "./TaskMonitor";

interface Formula { region_id: string; page_number: number; latex: string; recognized_latex?: string; status: string; notice: string; correction?: { note: string }; }
interface Result { items: Formula[]; expected_regions: number; model_ready: boolean; notice: string; }

export default function FormulaInspector({ paperId }: { paperId: string }) {
  const [data, setData] = useState<Result | null>(null), [revision, setRevision] = useState(0);
  const [task, setTask] = useState(""), [active, setActive] = useState(false), [error, setError] = useState(""), [copied, setCopied] = useState("");
  const refresh = useCallback(() => setRevision(value => value + 1), []);
  useEffect(() => { setTask(localStorage.getItem(`sg.formula.${paperId}`) ?? ""); }, [paperId]);
  useEffect(() => { let stopped = false; void workspaceRequest<Result>(`/papers/${paperId}/formulas`).then(value => { if (!stopped) setData(value); }).catch(cause => { if (!stopped) setError(cause.message); }); return () => { stopped = true; }; }, [paperId, revision]);
  function remember(id: string) { setTask(id); localStorage.setItem(`sg.formula.${paperId}`, id); }
  const disabledReason = !data?.model_ready ? "本地公式模型尚未准备完成" : !data.expected_regions ? "请先完成版面区域识别，检测出公式后即可识别" : "";
  return <section className="sg-section"><h3>公式 LaTeX 与原图核对</h3><p>将已检测的公式原图交给本地模型识别，论文材料不会发送到外部服务。结果为机器识别候选，请核对分式、上下标和符号。</p>
    <button className="sg-btn sg-btn--ghost" disabled={active || !!disabledReason} title={disabledReason || undefined} onClick={async () => { setError(""); setActive(true); try { const value = await workspacePost<WorkspaceTask>(`/papers/${paperId}/formula-tasks`, {}); remember(value.id); } catch (cause) { setError(cause instanceof Error ? cause.message : "公式识别未能开始。"); setActive(false); } }}>从公式原图识别 LaTeX</button>
    {disabledReason ? <p className="sg-help">{disabledReason}</p> : null}{error ? <p className="sg-error" role="alert">{error}</p> : null}
    {task ? <TaskMonitor taskId={task} onTaskChange={remember} onResult={refresh} onStatus={status => setActive(["queued", "running", "cancelling"].includes(status))} /> : null}
    {data ? <p>已保存 {data.items.length} / {data.expected_regions} 个公式区域的识别结果；数量齐全不代表数学表达已核对正确。</p> : null}
    {data?.items.map(formula => <details key={formula.region_id}><summary>公式 · 第 {formula.page_number} 页 · 查看原图与 LaTeX</summary>
      <img className="sg-source-region" loading="lazy" src={workspaceUrl(`/papers/${paperId}/layout-regions/${formula.region_id}`)} alt={`第${formula.page_number}页公式原图`} />
      <form key={formula.latex} onSubmit={async event => { event.preventDefault(); setError(""); const fields = new FormData(event.currentTarget); try { await workspacePost(`/papers/${paperId}/formulas/${formula.region_id}`, { latex: fields.get("latex"), note: fields.get("note") }, "PATCH"); refresh(); } catch (cause) { setError(cause instanceof Error ? cause.message : "修正未保存。"); } }}>
        <label className="sg-field">LaTeX（可对照原图修正）<textarea name="latex" className="sg-input" required maxLength={12000} defaultValue={formula.latex} rows={4} /></label>
        <label className="sg-field">核对与修正说明<input name="note" className="sg-input" required maxLength={1000} defaultValue={formula.correction?.note ?? ""} /></label>
        <button className="sg-btn sg-btn--ghost">保存原图核对后的修正</button>
      </form>
      {formula.recognized_latex ? <details><summary>原始机器候选</summary><pre className="sg-mono">{formula.recognized_latex}</pre></details> : null}
      <p>{formula.notice}</p><div className="sg-form"><button className="sg-btn sg-btn--ghost" onClick={async () => { try { await navigator.clipboard.writeText(formula.latex); setCopied(formula.region_id); } catch { setError("未能复制，请在文本框中选中并复制。"); } }}>{copied === formula.region_id ? "已复制" : "复制 LaTeX"}</button><a href={`/read/${paperId}?page=${formula.page_number}`}>打开原文核对</a></div>
    </details>)}
  </section>;
}
