import Link from "next/link";
import UploadForm from "@/components/UploadWorkspace";
import Diagnostics from "@/components/Diagnostics";

export default function UploadPage() {
  return (
    <main className="sg-shell">
      <div className="sg-page-head">
        <Diagnostics summary="技术信息（接口路径与批量字段）">POST /api/v1/papers · /papers/batch</Diagnostics>
          <h1 className="sg-title">上传论文</h1>
        <p className="sg-lede">
          导入标准论文、扫描件或长书。逐篇查看处理结果，遇到重复版本时选择保留方式。
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
