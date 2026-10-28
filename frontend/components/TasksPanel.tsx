"use client";
import { useEffect, useState } from "react";
import { workspaceRequest } from "@/lib/workspace";
import TaskMonitor, { type WorkspaceTask } from "./TaskMonitor";
const names: Record<string, string> = { upload: "论文上传与解析", translation: "论文翻译", writing: "研究写作与分析", acquisition: "论文自动获取", layout: "公式与图表识别", tracking: "发现相关新论文" };
const statuses: Record<string, string> = { queued: "排队中", running: "处理中", cancelling: "正在停止", completed: "已完成", partial: "部分成功", failed: "未完成", cancelled: "已停止", interrupted: "等待恢复" };
export default function TasksPanel() {
  const [tasks, setTasks] = useState<WorkspaceTask[]>([]), [selected, setSelected] = useState(""), [error, setError] = useState("");
  async function load() { try { setTasks(await workspaceRequest<WorkspaceTask[]>("/tasks")); setError(""); } catch (cause) { setError(cause instanceof Error ? cause.message : "任务记录未能读取。"); } }
  useEffect(() => { void load(); }, []);
  return <section className="sg-section"><div className="sg-section__head"><h2 className="sg-section__title">任务记录与恢复</h2><button className="sg-btn sg-btn--ghost" onClick={() => void load()}>刷新任务</button></div><p>页面切换或刷新后，可在此查看最近五十项任务，打开进度、停止或重试。</p>{error ? <p className="sg-error" role="alert">{error}</p> : null}{!tasks.length && !error ? <p>还没有任务记录。</p> : null}<div className="sg-task-history">{tasks.map(task => <button key={task.id} className="sg-task-row" aria-pressed={selected === task.id} onClick={() => setSelected(task.id)}><strong>{names[task.kind] ?? "后台任务"}</strong><span>{statuses[task.status] ?? task.status}</span><span>{new Date(task.created_at).toLocaleString("zh-CN")}</span><small>{task.progress.label}</small></button>)}</div>{selected ? <TaskMonitor key={selected} taskId={selected} onTaskChange={id => { setSelected(id); void load(); }} /> : null}</section>;
}
