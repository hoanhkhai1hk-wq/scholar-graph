import Link from "next/link";
import { getReading } from "@/lib/workspace";
import ReadingWorkbench from "@/components/ReadingWorkbench";

export const dynamic = "force-dynamic";

export default async function ReaderPage({ params, searchParams }: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ page?: string }>;
}) {
  const { id } = await params;
  const query = await searchParams;
  const requested = Number(query.page ?? 1);
  const page = Number.isInteger(requested) && requested > 0 ? requested : 1;
  try {
    const initial = await getReading(id, page);
    return <ReadingWorkbench key={id} initial={initial} />;
  } catch (cause) {
    return <main className="sg-shell"><h1 className="sg-title">阅读服务暂时不可用</h1><div className="sg-error" role="alert"><p>{cause instanceof Error ? cause.message : "论文材料加载失败。"}</p><p>请在设置中检查服务版本，或返回论文库重新打开。</p></div><div className="sg-form"><Link className="sg-btn" href="/settings">检查服务</Link><Link className="sg-btn sg-btn--ghost" href="/">返回论文库</Link></div></main>;
  }
}
