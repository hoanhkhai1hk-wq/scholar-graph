"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "论文库" },
  { href: "/qa", label: "问答" },
  { href: "/graph", label: "引用图谱" },
  { href: "/retrieval", label: "检索与追踪" },
  { href: "/writing", label: "写作辅助" },
  { href: "/upload", label: "上传论文" },
];

/**
 * 常驻顶部导航：六个入口在任一页面都可达，不再只靠首页能力索引表。
 * 当前项只用文字色与一条细线区分，不用彩色药丸（nav 应当后退）。
 */
export default function SiteNav() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="sg-nav">
      <div className="sg-nav__inner">
        <Link href="/" className="sg-nav__brand">
          研枢 ScholarGraph
        </Link>
        <nav className="sg-nav__links" aria-label="主导航">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={
                isActive(link.href)
                  ? "sg-nav__link sg-nav__link--active"
                  : "sg-nav__link"
              }
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
