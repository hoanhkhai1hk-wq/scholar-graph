/**
 * 统一的四字段锚点展示（paper_id / page_number / section / chunk_id）。
 * 锚点为空时明确标「无锚点」，不渲染成可点击的有效证据。
 */
import type { Anchor } from "@/lib/types";
import Link from "next/link";

export default function AnchorTag({
  anchor,
  index,
}: {
  anchor: Anchor | null;
  index?: number;
}) {
  if (!anchor) {
    return <span className="sg-tag sg-tag--warning">无锚点 · 不可验证</span>;
  }

  return (
    <Link className="sg-anchor-inline" href={`/read/${encodeURIComponent(anchor.paper_id)}?page=${anchor.page_number}&chunk=${encodeURIComponent(anchor.chunk_id)}`} title="打开原文并定位证据">
      {index !== undefined ? (
        <span className="sg-mono">{`证据 ${String.fromCharCode(65 + index)}`}</span>
      ) : null}
      <span className="sg-mono">
        第 {anchor.page_number} 页 · 查看原文
      </span>
      <span className="sg-mono">{anchor.section.join(" / ")}</span>
    </Link>
  );
}
