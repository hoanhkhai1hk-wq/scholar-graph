import type { ReactNode } from "react";

/**
 * 空状态：给一句人话说明 + 下一步怎么做，不留白板。
 * 图示是画出来的线条（不是 emoji 图标），与纸感一致。
 */
export default function EmptyState({
  title,
  hint,
  action,
  aside,
}: {
  title: string;
  hint: string;
  action?: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <div className="sg-empty">
      <svg
        className="sg-empty__mark"
        viewBox="0 0 72 72"
        role="img"
        aria-label="空状态图示"
      >
        <circle
          cx="36"
          cy="36"
          r="27"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
        />
        <circle
          cx="36"
          cy="36"
          r="18"
          fill="none"
          stroke="currentColor"
          strokeWidth="0.5"
        />
        <line
          x1="18"
          y1="36"
          x2="54"
          y2="36"
          stroke="currentColor"
          strokeWidth="0.5"
        />
        <line
          x1="36"
          y1="18"
          x2="36"
          y2="54"
          stroke="currentColor"
          strokeWidth="0.5"
        />
      </svg>
      <div className="sg-empty__body">
        <p className="sg-empty__title">{title}</p>
        <p className="sg-empty__hint">{hint}</p>
        {action ? <div className="sg-empty__action">{action}</div> : null}
        {aside ? <p className="sg-mono">{aside}</p> : null}
      </div>
    </div>
  );
}
