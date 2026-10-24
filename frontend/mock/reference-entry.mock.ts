/**
 * MOCK DATA — 演示假数据，未接后端。
 * 字段与 contracts/reference-entry.v1.example.json 一致。
 *
 * 第 1 条为契约 example 原样复制；其余条目按同一字段集构造，用于展示编号条目与 DOI/arXiv 取值。
 */
export const referenceEntryMock = [
  {
    schema_version: "1.0.0",
    ref_id: "ref-demo-001-1",
    paper_id: "paper-demo-001",
    number: 1,
    authors: ["Example Author"],
    year: 2025,
    title: "Synthetic Prior Study",
    venue: "Synthetic Proceedings",
    doi: null,
    arxiv_id: null,
  },
  {
    schema_version: "1.0.0",
    ref_id: "ref-demo-001-2",
    paper_id: "paper-demo-001",
    number: 2,
    authors: ["Another Author", "Third Author"],
    year: 2023,
    title: "Synthetic Baseline Method",
    venue: "Synthetic Journal",
    doi: "10.0000/synthetic.2023.02",
    arxiv_id: null,
  },
  {
    schema_version: "1.0.0",
    ref_id: "ref-demo-002-1",
    paper_id: "paper-demo-002",
    number: 1,
    authors: ["Example Author"],
    year: 2025,
    title: "Synthetic Prior Study",
    venue: "Synthetic Proceedings",
    doi: null,
    arxiv_id: null,
  },
] as const;

export default referenceEntryMock;
