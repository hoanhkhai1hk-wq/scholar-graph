/**
 * MOCK DATA — 演示假数据，未接后端。
 * 字段与 contracts/citation-link.v1.example.json 一致。
 *
 * 第 1 条为契约 example 原样复制；其余条目按同一字段集构造，用于展示一页多引用与跨页重复引用。
 */
export const citationLinkMock = [
  {
    schema_version: "1.0.0",
    paper_id: "paper-demo-001",
    citation_number: 1,
    page_number: 1,
    chunk_id: "chunk-demo-001-p1-001",
    ref_id: "ref-demo-001-1",
  },
  {
    schema_version: "1.0.0",
    paper_id: "paper-demo-001",
    citation_number: 2,
    page_number: 1,
    chunk_id: "chunk-demo-001-p1-002",
    ref_id: "ref-demo-001-2",
  },
  {
    schema_version: "1.0.0",
    paper_id: "paper-demo-001",
    citation_number: 1,
    page_number: 2,
    chunk_id: "chunk-demo-001-p2-001",
    ref_id: "ref-demo-001-1",
  },
  {
    schema_version: "1.0.0",
    paper_id: "paper-demo-002",
    citation_number: 1,
    page_number: 1,
    chunk_id: "chunk-demo-002-p1-001",
    ref_id: "ref-demo-002-1",
  },
] as const;

export default citationLinkMock;
