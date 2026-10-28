"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const LINKS = [
  { href: "/", label: "论文库" },
  { href: "/qa", label: "研究问答" },
  { href: "/retrieval", label: "发现与追踪" },
  { href: "/graph", label: "引用图谱" },
  { href: "/writing", label: "写作工作台" },
];

/** Floating desktop navigation and keyboard-contained mobile drawer. */
export default function SiteNav() {
  const pathname = usePathname();
  const [preference, setPreference] = useState<boolean | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [tablet, setTablet] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLElement>(null);
  const collapsed = preference ?? (pathname.startsWith("/read/") || tablet);
  useEffect(() => {
    const stored = localStorage.getItem("sg.navigation.collapsed");
    if (stored !== null) setPreference(stored === "true");
    const media = matchMedia("(max-width: 1279px)");
    const update = () => setTablet(media.matches); update(); media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => { document.documentElement.dataset.nav = collapsed ? "compact" : "expanded"; document.documentElement.dataset.navManual = String(preference !== null); }, [collapsed, preference]);
  useEffect(() => { setMobileOpen(false); }, [pathname]);
  useEffect(() => {
    if (!mobileOpen) return;
    const content = document.getElementById("workspace-content");
    if (content) content.inert = true;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    drawer.current?.querySelector<HTMLElement>("a,button")?.focus();
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setMobileOpen(false); trigger.current?.focus(); }
      if (event.key === "Tab") {
        const items = [...(drawer.current?.querySelectorAll<HTMLElement>("a,button") ?? [])].filter(item => item.getClientRects().length);
        const first = items[0], last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("keydown", close); if (content) content.inert = false; document.body.style.overflow = previousOverflow; };
  }, [mobileOpen]);
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" || pathname.startsWith("/read/") || pathname.startsWith("/papers/") : pathname.startsWith(href);

  return (
    <>
      <a className="sg-skip-link" href="#workspace-content">跳到内容</a>
      <button ref={trigger} className="sg-mobile-menu" aria-expanded={mobileOpen} aria-controls="main-navigation" onClick={() => setMobileOpen(!mobileOpen)}>☰ 导航</button>
      {mobileOpen ? <button className="sg-nav-backdrop" aria-label="关闭导航" onClick={() => { setMobileOpen(false); trigger.current?.focus(); }} /> : null}
      <aside ref={drawer} id="main-navigation" data-user-expanded={preference === false || undefined} className={`sg-floating-nav${collapsed ? " is-compact" : ""}${mobileOpen ? " is-open" : ""}`} aria-label="主导航">
        {mobileOpen ? <button className="sg-btn sg-btn--ghost" onClick={() => { setMobileOpen(false); trigger.current?.focus(); }}>关闭导航</button> : null}
        <Link href="/" className="sg-floating-nav__brand" title="研枢 ScholarGraph"><span className="sg-brand-mark">研</span><span className="sg-nav-label">研枢<small>ScholarGraph</small></span></Link>
        <Link href="/upload" className="sg-nav-upload" title="上传论文"><span aria-hidden="true">＋</span><span className="sg-nav-label">上传论文</span></Link>
        <nav className="sg-floating-nav__links">
          {LINKS.map((link, index) => (
            <Link
              key={link.href}
              href={link.href}
              className={
                isActive(link.href) ? "sg-floating-link is-active" : "sg-floating-link"
              }
              title={link.label}
              aria-current={isActive(link.href) ? "page" : undefined}
            >
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d={[
                "M4 4h6v16H4z M14 4h6v16h-6z",
                "M4 4h16v12H9l-5 4z",
                "M6 6l12 0-6 12z M3 3h6v6H3z M15 3h6v6h-6z M9 15h6v6H9z",
                "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14 M15 15l6 6",
                "M4 20h16 M5 15L16 4l4 4L9 19H5z",
              ][index]} /></svg>
              <span className="sg-nav-label">{link.label}</span>
            </Link>
          ))}
        </nav>
        <div className="sg-floating-nav__footer">
          <Link href="/settings" title="设置与服务状态" className="sg-floating-link"><span aria-hidden="true">⚙</span><span className="sg-nav-label">设置与状态</span></Link>
          <button className="sg-floating-link sg-nav-toggle" aria-label={collapsed ? "展开导航" : "折叠导航"} title={collapsed ? "展开导航" : "折叠导航"} onClick={() => { const next = !collapsed; setPreference(next); localStorage.setItem("sg.navigation.collapsed", String(next)); }}><span aria-hidden="true">{collapsed ? "›" : "‹"}</span><span className="sg-nav-label">折叠导航</span></button>
        </div>
      </aside>
    </>
  );
}
