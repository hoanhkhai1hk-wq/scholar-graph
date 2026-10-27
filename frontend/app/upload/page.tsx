import Link from "next/link";
import UploadForm from "@/components/UploadForm";
import Diagnostics from "@/components/Diagnostics";

export default function UploadPage() {
  return (
    <main className="sg-shell">
      <div className="sg-page-head">
        <Diagnostics summary="技术信息（接口路径与批量字段）">POST /api/v1/papers · /papers/batch</Diagnostics>
        <h1 className="sg-title">上传 PDF</h1>
        <p className="sg-lede">
          上传走模块一已落地的两个端点。批量响应按 succeeded / failed /
          succeeded_count / failed_count 展示，整批不丢项。
          单篇上传字段名为 file，批量为重复的 files 字段。
        </p>
        <p className="sg-back">
          <Link href="/">← 返回论文库</Link>
        </p>
      </div>

      <UploadForm />
    </main>
  );
}

export const dynamic = "force-dynamic";
