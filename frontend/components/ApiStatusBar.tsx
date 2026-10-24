import { API_ROOT } from "@/lib/api";

export const BACKEND_API_ROOT = API_ROOT;

/**
 * 替代原「演示假数据」横幅的顶部状态条。
 * 显示真实取数后端地址，不显示任何演示字样。
 */
export default function ApiStatusBar() {
  return (
    <div className="sg-statusbar">
      <span className="sg-statusbar__brand">ScholarGraph · 研枢</span>
      <nav className="sg-statusbar__nav">
        <a href="/">论文库</a>
        <a href="/upload">上传</a>
      </nav>
      <span className="sg-statusbar__api" title="取数基地址（NEXT_PUBLIC_API_BASE_URL）">
        数据后端 <code>{BACKEND_API_ROOT}</code>
      </span>
    </div>
  );
}
