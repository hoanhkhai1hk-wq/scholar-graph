/**
 * 骨架屏：加载时用灰色占位块顶住版面，不白屏干等。
 * 只有一层极缓的透明度呼吸，且尊重 prefers-reduced-motion。
 */
export default function Skeleton({
  rows = 3,
  title = true,
  height = 14,
}: {
  rows?: number;
  title?: boolean;
  height?: number;
}) {
  return (
    <div className="sg-skeleton" aria-hidden="true">
      {title ? <span className="sg-skeleton__title" /> : null}
      {Array.from({ length: rows }, (_, index) => (
        <span
          key={index}
          className="sg-skeleton__line"
          style={{ height: `${height}px`, width: `${92 - index * 7}%` }}
        />
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="sg-skeleton" aria-hidden="true">
      <span className="sg-skeleton__title" />
      {Array.from({ length: rows }, (_, index) => (
        <span key={index} className="sg-skeleton__row" />
      ))}
    </div>
  );
}
