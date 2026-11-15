"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const LINKS = [{ href: "/", label: "论文库" }, { href: "/qa", label: "研究问答" }, { href: "/graph", label: "引用图谱" }, { href: "/retrieval", label: "检索与追踪" }, { href: "/writing", label: "写作工作台" }];
function Icon({ name }: { name: "menu" | "settings" | "display" | "search" }) {
  const paths = { menu: "M4 6h16M4 12h16M4 18h16", settings: "M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0", display: "M3 4h18v13H3z M8 21h8M12 17v4", search: "M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0M15 15l6 6" };
  return <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
/** Shared shell persists while route content and its skeleton change. */
export default function SiteNav() {
  const pathname = usePathname(), router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false), [search, setSearch] = useState("");
  const [motion, setMotion] = useState(true), [solid, setSolid] = useState(false);
  const [systemMotionOff, setSystemMotionOff] = useState(false), [systemSolid, setSystemSolid] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null), drawer = useRef<HTMLDivElement>(null), displayMenu = useRef<HTMLDetailsElement>(null);
  const motionEnabled = motion && !systemMotionOff, glassEnabled = !solid && !systemSolid;
  useEffect(() => {
    setMotion(localStorage.getItem("sg.ui.motion") !== "off"); setSolid(localStorage.getItem("sg.ui.transparency") === "reduced");
    const motionQuery = matchMedia("(prefers-reduced-motion: reduce)"), transparencyQuery = matchMedia("(prefers-reduced-transparency: reduce)");
    const systemPreferences = () => { setSystemMotionOff(motionQuery.matches); setSystemSolid(transparencyQuery.matches); };
    systemPreferences(); motionQuery.addEventListener("change", systemPreferences); transparencyQuery.addEventListener("change", systemPreferences);
    delete document.documentElement.dataset.nav; delete document.documentElement.dataset.navManual;
    const visibility = () => { document.documentElement.dataset.uiHidden = String(document.hidden); };
    visibility(); document.addEventListener("visibilitychange", visibility);
    return () => { document.removeEventListener("visibilitychange", visibility); motionQuery.removeEventListener("change", systemPreferences); transparencyQuery.removeEventListener("change", systemPreferences); };
  }, []);
  useEffect(() => { document.documentElement.dataset.uiMotion = motionEnabled ? "on" : "off"; }, [motionEnabled]);
  useEffect(() => { document.documentElement.dataset.uiTransparency = glassEnabled ? "glass" : "reduced"; }, [glassEnabled]);
  useEffect(() => { setMobileOpen(false); }, [pathname]);
  useEffect(() => {
    const dismiss = (event: PointerEvent) => { if (event.target instanceof Node && !displayMenu.current?.contains(event.target) && displayMenu.current) displayMenu.current.open = false; };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape" && displayMenu.current?.open) { displayMenu.current.open = false; displayMenu.current.querySelector("summary")?.focus(); } };
    document.addEventListener("pointerdown", dismiss); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", dismiss); document.removeEventListener("keydown", escape); };
  }, []);
  function close() { setMobileOpen(false); trigger.current?.focus(); }
  useEffect(() => {
    if (!mobileOpen) return;
    const content = document.getElementById("workspace-content"), overflow = document.body.style.overflow;
    if (content) content.inert = true; document.body.style.overflow = "hidden"; drawer.current?.querySelector<HTMLElement>("button,a,input")?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); close(); }
      if (event.key !== "Tab") return;
      const items = [...(drawer.current?.querySelectorAll<HTMLElement>("button,a,input") ?? [])].filter(e => e.getClientRects().length && !e.hasAttribute("disabled"));
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    const resize = () => { if (innerWidth > 1000) close(); };
    document.addEventListener("keydown", keydown); window.addEventListener("resize", resize);
    return () => { if (content) content.inert = false; document.body.style.overflow = overflow; document.removeEventListener("keydown", keydown); window.removeEventListener("resize", resize); };
  }, [mobileOpen]);
  const active = (href: string) => href === "/" ? pathname === "/" || pathname.startsWith("/read/") || pathname.startsWith("/papers/") : pathname.startsWith(href);
  function toggleMotion() { const next = !motion; setMotion(next); localStorage.setItem("sg.ui.motion", next ? "on" : "off"); }
  function toggleTransparency() { const next = !solid; setSolid(next); localStorage.setItem("sg.ui.transparency", next ? "reduced" : "glass"); }
  function preferences(prefix: string) {
    return <>
      <div className="sg-display-heading"><strong>显示偏好</strong><span>调整顶部导航的动画与背景</span></div>
      <button className="sg-display-switch" type="button" role="switch" aria-label="导航流光" aria-checked={motionEnabled} aria-describedby={`${prefix}-motion-help`} disabled={systemMotionOff} onClick={toggleMotion}>
        <span className="sg-display-copy"><span className="sg-display-label">导航流光</span><span id={`${prefix}-motion-help`} className="sg-display-description">{systemMotionOff ? "系统已关闭动态效果" : motionEnabled ? "柔光在顶部导航缓慢移动" : "顶部导航保持静止"}</span></span>
        <span className="sg-display-state" aria-hidden="true">{motionEnabled ? "开启" : "关闭"}<span className="sg-display-track"><span /></span></span>
      </button>
      <button className="sg-display-switch" type="button" role="switch" aria-label="玻璃透明" aria-checked={glassEnabled} aria-describedby={`${prefix}-glass-help`} disabled={systemSolid} onClick={toggleTransparency}>
        <span className="sg-display-copy"><span className="sg-display-label">玻璃透明</span><span id={`${prefix}-glass-help`} className="sg-display-description">{systemSolid ? "系统已减少透明度" : glassEnabled ? "透出并模糊导航后的页面" : "使用不透明的浅色背景"}</span></span>
        <span className="sg-display-state" aria-hidden="true">{glassEnabled ? "开启" : "关闭"}<span className="sg-display-track"><span /></span></span>
      </button>
    </>;
  }
  function searchForm(mobile = false) { return <form className="sg-global-search" role="search" aria-label="全局论文搜索" onSubmit={event => { event.preventDefault(); setMobileOpen(false); router.push(`/?q=${encodeURIComponent(search.trim())}`); }}><label className="sg-visually-hidden" htmlFor={mobile ? "mobile-paper-search" : "desktop-paper-search"}>搜索论文</label><input id={mobile ? "mobile-paper-search" : "desktop-paper-search"} aria-label="全局搜索论文" type="search" placeholder="搜索论文" value={search} onChange={e => setSearch(e.target.value)} /><button type="submit" aria-label="提交论文搜索"><Icon name="search" /></button></form>; }
  return <>
    <a className="sg-skip-link" href="#workspace-content">跳到内容</a>
    <header className="sg-celadon-nav" aria-label="工作台导航">
      <div className="sg-nav-glass" aria-hidden="true" />
      <Link href="/" className="sg-celadon-brand" aria-label="研枢 ScholarGraph 论文库"><svg viewBox="0 0 36 36" width="32" height="32" aria-hidden="true"><path d="M6 9h11v21H6z M20 5h10v21H20z" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M10 14h3m-3 5h3m11-9h2m-2 5h2" stroke="currentColor" strokeWidth="1.5" /></svg><span>研枢<small>ScholarGraph</small></span></Link>
      <nav className="sg-celadon-links" aria-label="主导航">{LINKS.map(link => <Link key={link.href} href={link.href} aria-current={active(link.href) ? "page" : undefined}>{link.label}</Link>)}</nav>
      <div className="sg-nav-tools"><div className="sg-desktop-utilities">{searchForm()}<details ref={displayMenu} className="sg-display-menu"><summary aria-label="显示偏好" title="显示偏好"><Icon name="display" /></summary><div className="sg-display-options">{preferences("desktop-display")}</div></details><Link className="sg-icon-link" href="/settings" aria-label="设置与服务状态" title="设置与服务状态"><Icon name="settings" /></Link></div><Link className="sg-btn sg-nav-upload" href="/upload">上传论文</Link><button ref={trigger} className="sg-celadon-menu" aria-expanded={mobileOpen} aria-controls="mobile-navigation" onClick={() => setMobileOpen(!mobileOpen)}><Icon name="menu" /><span>菜单</span></button></div>
    </header>
    {mobileOpen ? <><button className="sg-celadon-backdrop" aria-label="关闭导航背景" onClick={close} /><div ref={drawer} id="mobile-navigation" className="sg-celadon-drawer" role="dialog" aria-modal="true" aria-label="导航菜单"><div className="sg-drawer-head"><strong>科研工作台</strong><button className="sg-btn sg-btn--ghost" onClick={close}>关闭导航</button></div>{searchForm(true)}<nav aria-label="移动主导航">{LINKS.map(link => <Link key={link.href} href={link.href} aria-current={active(link.href) ? "page" : undefined}>{link.label}</Link>)}</nav><Link href="/settings" onClick={close}>设置与服务状态</Link><div className="sg-display-options">{preferences("mobile-display")}</div></div></> : null}
  </>;
}
