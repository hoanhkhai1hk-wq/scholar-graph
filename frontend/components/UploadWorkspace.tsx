"use client";

import { useEffect, useRef, useState } from "react";
import { workspaceRequest, type SystemStatus } from "@/lib/workspace";
import TaskMonitor, { type WorkspaceTask } from "./TaskMonitor";

export default function UploadWorkspace() {
  const [files, setFiles] = useState<File[]>([]);
  const [taskId, setTaskId] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [publicDemo, setPublicDemo] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  useEffect(() => { const saved = localStorage.getItem("sg.upload.task"); if (saved) setTaskId(saved); }, []);
  useEffect(() => { void workspaceRequest<SystemStatus>("/system").then(value => setPublicDemo(value.data_class === "public_demo")).catch(() => {}); }, []);
  function selected(incoming: File[]) { setError(""); if (incoming.length > 20) { setError("一次最多上传 20 个文件。"); return; } setFiles(incoming); }
  function remember(id: string) { setTaskId(id); localStorage.setItem("sg.upload.task", id); }
  async function upload() {
    if (!files.length || uploading) return;
    setUploading(true); setError("");
    try { const body = new FormData(); files.forEach(file => body.append("files", file)); const task = await workspaceRequest<WorkspaceTask>("/uploads", { method: "POST", body }); remember(task.id); setFiles([]); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "文件上传失败，请重试。"); }
    finally { setUploading(false); }
  }
  return <>{publicDemo ? <p className="sg-note">评审演示库：上传文件会出现在共享测试库，请使用公开论文。</p> : null}<section className="sg-section"><div className={`sg-upload-drop${dragging ? " is-dragging" : ""}`} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); if (!uploading) selected(Array.from(event.dataTransfer.files)); }}><h2 className="sg-section__title">把论文拖到这里</h2><p>标准 PDF、扫描论文和长书均可。一次最多 20 个文件，每个不超过 50 MB。</p><button className="sg-btn sg-btn--ghost" disabled={uploading} onClick={() => picker.current?.click()}>选择 PDF 文件</button><input ref={picker} type="file" accept="application/pdf,.pdf" multiple hidden onChange={event => selected(Array.from(event.target.files ?? []))} /></div>{files.length ? <><ul className="sg-upload-files">{files.map((file, index) => <li key={`${file.name}-${index}`}><span>{file.name}</span><span>{(file.size / 1024 / 1024).toFixed(1)} MB</span><button className="sg-linklike" disabled={uploading} onClick={() => setFiles(files.filter((_, n) => n !== index))} aria-label={`移除 ${file.name}`}>移除</button></li>)}</ul><button className="sg-btn" disabled={uploading} onClick={() => void upload()}>{uploading ? "正在传输文件…" : `上传并解析 ${files.length} 篇`}</button></> : null}{error ? <p role="alert" className="sg-error">{error}</p> : null}<p className="sg-mono">文件接收后在后台解析，可离开页面后返回查看。长文档在页面批次结束后响应停止；已完成页会保存，重试时可继续。</p></section>{taskId ? <TaskMonitor taskId={taskId} onTaskChange={remember} /> : null}</>;
}
