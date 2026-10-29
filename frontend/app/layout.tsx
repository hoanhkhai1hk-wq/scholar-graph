import type { Metadata } from "next";
import "./globals.css";
import "./workbench.css";
import "./celadon.css";
import SiteNav from "@/components/SiteNav";
import ServiceGate from "@/components/ServiceGate";

export const metadata: Metadata = {
  title: "ScholarGraph · 研枢",
  description: "论文管理、原文阅读、研究问答、双语对照与有来源依据的科研写作工作台。",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh">
      <body>
        <SiteNav />
        <div id="workspace-content" className="sg-app-content"><ServiceGate />{children}</div>
      </body>
    </html>
  );
}
