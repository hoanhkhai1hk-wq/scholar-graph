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
  variant = "library",
}: {
  title: string;
  hint: string;
  action?: ReactNode;
  aside?: ReactNode;
  variant?: "library" | "search" | "tracking" | "graph";
}) {
  return (
    <div className="sg-empty">
      <svg
        className="sg-empty__mark"
        viewBox="0 0 72 72"
        role="img"
        aria-label="空状态图示"
      >
        <g fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          {variant === "library" ? <><path d="M17 15h34v44H17z M24 9h34v44M10 22v43h34" /><path d="M25 26h18M25 33h18M25 40h11" /></> : null}
          {variant === "search" ? <><circle cx="31" cy="30" r="19" /><path d="m45 44 16 17M22 26h18M22 33h12" /></> : null}
          {variant === "tracking" ? <><path d="M10 37h52M22 24v6M48 43v6" /><circle cx="17" cy="37" r="4" /><circle cx="36" cy="37" r="4" /><circle cx="56" cy="37" r="4" /><path d="M45 13h13v13M58 13 44 27" /></> : null}
          {variant === "graph" ? <><path d="m21 22 30 3-13 28z" /><circle cx="21" cy="22" r="7" /><circle cx="51" cy="25" r="6" /><circle cx="38" cy="53" r="8" /></> : null}
        </g>
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
