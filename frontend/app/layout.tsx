import type { Metadata } from "next";
import "./globals.css";
import ApiStatusBar from "@/components/ApiStatusBar";
import SiteNav from "@/components/SiteNav";

export const metadata: Metadata = {
  title: "ScholarGraph · 研枢",
  description: "科研助手 Agent 系统前端，数据取自模块一已落地的 HTTP API。",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <SiteNav />
        <ApiStatusBar />
        {children}
      </body>
    </html>
  );
}
