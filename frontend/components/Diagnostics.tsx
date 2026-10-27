import type { ReactNode } from "react";

/**
 * 诊断区：把接口路径、分页字段、契约名这类技术信息折叠起来，
 * 页面正文只留用户要办的事。技术术语与端点原文照旧，不翻译。
 */
export default function Diagnostics({
  summary = "技术信息（接口路径、分页字段、契约名）",
  children,
}: {
  summary?: string;
  children: ReactNode;
}) {
  return (
    <details className="sg-diag">
      <summary className="sg-diag__summary">{summary}</summary>
      <div className="sg-diag__body">{children}</div>
    </details>
  );
}
