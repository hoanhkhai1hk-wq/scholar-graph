"use client";

import { useEffect, useState } from "react";
import { workspaceRequest, type SystemStatus } from "@/lib/workspace";
import TasksPanel from "@/components/TasksPanel";

export default function SettingsPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState("");
  async function load() { try { setStatus(await workspaceRequest<SystemStatus>("/system")); setError(""); } catch (cause) { setError(cause instanceof Error ? cause.message : "服务检查失败。"); } }
  useEffect(() => { void load(); }, []);
  return <main className="sg-shell"><div className="sg-page-head"><h1 className="sg-title">设置与服务状态</h1><p className="sg-lede">检查当前工作台连接的服务，以及模型和追踪是否可用。</p></div><div className="sg-form"><button className="sg-btn" onClick={load}>重新检查</button></div>{error ? <div className="sg-error" role="alert"><strong>工作台服务未就绪</strong><p>{error}</p><p>旧版后端不包含工作台接口，需要使用配套的新版本服务。</p></div> : null}{status ? <><div className="sg-settings-grid"><section className="sg-section"><h2 className="sg-section__title">工作台</h2><p>接口版本：{status.api_version}</p><p>运行版本：{status.revision}</p></section><section className="sg-section"><h2 className="sg-section__title">模型服务</h2><p>{status.model_configured ? "已配置模型凭据" : "尚未配置模型，翻译与生成写作不可用"}</p><p>当前问答：{status.qa_mode === "deepseek" ? "模型取证回答" : "原文摘录"}</p><p className="sg-mono">配置存在不代表上游连通；实际调用会返回真实结果。</p></section><section className="sg-section"><h2 className="sg-section__title">论文追踪</h2><p>{status.tracking_enabled ? "后台定期追踪已启用" : "后台定期追踪未启用"}</p><a href="/retrieval">查看追踪记录</a></section></div><section className="sg-section"><h2 className="sg-section__title">数据与使用范围</h2><p>原始论文和解析记录独立保留，信息修正与版本选择有历史记录。删除操作先进入回收站。</p><p>单篇最大 {Math.round(status.limits.upload_bytes / 1024 / 1024)} MB，最多 {status.limits.pages} 页。单次跨篇问答最多 {status.limits.comparison_papers} 篇。</p></section></> : !error ? <p role="status">正在检查服务…</p> : null}<TasksPanel /></main>;
}
