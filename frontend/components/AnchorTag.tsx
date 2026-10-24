/**
 * 统一的四字段锚点展示（paper_id / page_number / section / chunk_id）。
 * 锚点为空时明确标「无锚点」，不渲染成可点击的有效证据。
 */
import type { Anchor } from "@/lib/types";

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
    <span className="sg-anchor-inline">
      {index !== undefined ? (
        <span className="sg-mono">{`证据 ${String.fromCharCode(65 + index)}`}</span>
      ) : null}
      <span className="sg-mono">
        p.{anchor.page_number} · {anchor.chunk_id}
      </span>
      <span className="sg-mono">{anchor.section.join(" / ")}</span>
      <span className="sg-mono">{anchor.paper_id}</span>
    </span>
  );
}
