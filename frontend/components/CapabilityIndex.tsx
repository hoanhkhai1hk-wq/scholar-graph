import Link from "next/link";

/**
 * 能力索引。后端 19 条端点已全部落地，这里不再是「未落地清单」，
 * 而是链接到各能力页面。
 */
const CAPABILITIES: {
  href: string;
  name: string;
  endpoints: string[];
  note: string;
}[] = [
  {
    href: "/qa",
    name: "问答与跨篇对比",
    endpoints: ["POST /papers/{id}/qa", "POST /compare"],
    note: "原文摘录取证，拒答与纠错原样展示",
  },
  {
    href: "/graph",
    name: "局域引用图谱",
    endpoints: ["GET /graph"],
    note: "节点、边、基石分层与未来方向",
  },
  {
    href: "/retrieval",
    name: "检索、公开抓取与推荐",
    endpoints: [
      "POST /retrieval/search",
      "POST /retrieval/fetch",
      "GET /recommendations",
    ],
    note: "检索模式按响应头原样展示",
  },
  {
    href: "/writing",
    name: "综述框架、摘录草稿与图表",
    endpoints: ["POST /frameworks", "POST /reviews", "POST /charts/csv"],
    note: "图为摘录草稿，成文由用户完成",
  },
  {
    href: "/upload",
    name: "上传与解析",
    endpoints: [
      "POST /papers",
      "POST /papers/batch",
      "GET /papers/{id}/parse-status",
    ],
    note: "单篇与批量，解析状态实时推进",
  },
];

export default function CapabilityIndex() {
  return (
    <section className="sg-section">
      <div className="sg-section__head">
        <h2 className="sg-section__title">能力索引</h2>
        <span className="sg-section__hint">
          后端 19 条端点已全部落地 · 点击进入对应能力页
        </span>
      </div>

      <table className="sg-table">
        <thead>
          <tr>
            <th>能力</th>
            <th>对应端点</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          {CAPABILITIES.map((item) => (
            <tr key={item.href}>
              <td>
                <Link href={item.href}>{item.name}</Link>
              </td>
              <td className="sg-mono">{item.endpoints.join("；")}</td>
              <td>{item.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
