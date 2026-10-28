"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { workspaceRequest, type SystemStatus } from "@/lib/workspace";
export default function ServiceGate() {
  const [error, setError] = useState("");
  const pathname = usePathname();
  useEffect(() => { if (pathname === "/login") { setError(""); return; } let stopped = false; async function check() { try { const status = await workspaceRequest<SystemStatus>("/system"); if (status.workspace_release !== "20261027-workbench-r2" || !["paper_management", "version_choice", "reading_pages", "author_mapping", "layout_regions", "tracking_read_only", "csv_provenance", "translation_snapshots"].every(key => status.capabilities[key])) throw new Error("网页与后端版本或能力不匹配，请更新后端服务后再操作。"); if (!stopped) setError(""); } catch (cause) { if (!stopped) setError(cause instanceof Error ? cause.message : "后端暂时无法连接。"); } } void check(); const timer = setInterval(check, 30000); return () => { stopped = true; clearInterval(timer); }; }, [pathname]);
  return error ? <div className="sg-service-error" role="alert">{error} <a href="/settings">检查服务状态</a></div> : null;
}
