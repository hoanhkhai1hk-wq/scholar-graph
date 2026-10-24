import Link from "next/link";
import { paperMetaMock } from "@/mock";

export default function HomePage() {
  return (
    <main className="sg-shell">
      <div className="sg-page-head">
        <p className="sg-eyebrow">ScholarGraph · 研枢</p>
        <h1 className="sg-title">论文库</h1>
        <p className="sg-lede">
          下列条目取自 contracts/paper-meta.v1.example.json
          及其按同一字段集构造的补充记录，均为合成假数据。点击标题进入详情页。
        </p>
      </div>

      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">PaperMeta 列表</h2>
          <span className="sg-section__hint">
            共 {paperMetaMock.length} 条 · 字段与 v1 契约一致
          </span>
        </div>

        <table className="sg-table">
          <thead>
            <tr>
              <th>标题</th>
              <th>作者</th>
              <th className="sg-num">年份</th>
              <th className="sg-num">版本</th>
              <th className="sg-num">页数</th>
              <th>文本层</th>
              <th>来源</th>
              <th>标识</th>
            </tr>
          </thead>
          <tbody>
            {paperMetaMock.map((paper) => (
              <tr key={paper.id}>
                <td>
                  <Link href={`/papers/${paper.id}`}>{paper.title}</Link>
                  <div className="sg-mono">{paper.id}</div>
                </td>
                <td>
                  {paper.authors.join("; ")}
                  <div className="sg-mono">{paper.institutions.join("; ")}</div>
                </td>
                <td className="sg-num">{paper.year ?? "—"}</td>
                <td className="sg-num">{paper.version ?? "—"}</td>
                <td className="sg-num">{paper.page_count ?? "—"}</td>
                <td>
                  {paper.has_text_layer === null ? (
                    <span className="sg-tag sg-tag--muted">未检查</span>
                  ) : paper.has_text_layer ? (
                    <span className="sg-tag sg-tag--success">有</span>
                  ) : (
                    <span className="sg-tag sg-tag--warning">无</span>
                  )}
                </td>
                <td>{paper.source ?? "—"}</td>
                <td>
                  <div className="sg-mono">
                    {paper.arxiv_id ? `arXiv ${paper.arxiv_id}` : "arXiv —"}
                  </div>
                  <div className="sg-mono">
                    {paper.doi ? `DOI ${paper.doi}` : "DOI —"}
                  </div>
                  <div className="sg-mono" title={paper.file_hash}>
                    {paper.file_hash
                      ? `${paper.file_hash.slice(0, 12)}…`
                      : "hash —"}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
