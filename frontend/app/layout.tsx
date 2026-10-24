import type { Metadata } from "next";
import "./globals.css";
import DemoBanner from "@/components/DemoBanner";

export const metadata: Metadata = {
  title: "ScholarGraph · 研枢（演示壳）",
  description: "科研助手 Agent 系统前端演示壳，使用契约示例假数据，未接后端。",
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
        <DemoBanner />
        {children}
      </body>
    </html>
  );
}
