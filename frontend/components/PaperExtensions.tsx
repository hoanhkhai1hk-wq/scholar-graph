import Link from "next/link";

/**
 * 详情页的延伸能力入口。后端 19 条端点已全部落地，
 * 这里只做导航，不再出现「接口未落地」的占位文案。
 */
const LINKS: { href: (id: string) => string; name: string; note: string }[] = [
  {
    href: (id) => `/read/${id}`,
    name: "阅读器",
    note: "章节导航与引用双向跳转（Chunk / ReferenceEntry / CitationLink）",
  },
  {
    href: () => "/qa",
    name: "问答与跨篇对比",
    note: "POST /papers/{id}/qa 与 /compare",
  },
  {
    href: () => "/graph",
    name: "局域引用图谱",
    note: "GET /graph，按本页论文构造图谱",
  },
  {
    href: () => "/retrieval",
    name: "检索与推荐",
    note: "/retrieval/search、/retrieval/fetch、/recommendations",
  },
  {
    href: () => "/writing",
    name: "综述与图表",
    note: "/frameworks、/reviews、/charts/csv",
  },
];

export default function PaperExtensions({ paperId }: { paperId: string }) {
  return (
    <section className="sg-section">
      <div className="sg-section__head">
        <h2 className="sg-section__title">延伸能力</h2>
        <span className="sg-section__hint">后端 19 条端点已全部落地</span>
      </div>
      <table className="sg-table">
        <thead>
          <tr>
            <th>能力</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          {LINKS.map((item) => (
            <tr key={item.name}>
              <td>
                <Link href={item.href(paperId)}>{item.name}</Link>
              </td>
              <td>{item.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
