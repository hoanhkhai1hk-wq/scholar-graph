/**
 * MOCK DATA — 演示假数据，未接后端。
 * 字段与 contracts/ 下的契约 example 一一对应，不新增、不改名、不臆造字段。
 *
 * 来源：contracts/paper-meta.v1.example.json（原样复制，1 条）
 * 补充：paper-demo-002 为演示版本去重关系（新版本）而按同一字段集构造的第二条记录，
 *       用于对应 contracts/dedup-decision.v1.1.example.json 中的 new_paper_id。
 *       字段集与 v1 契约完全一致，未引入任何契约外字段。
 */
export const paperMetaMock = [
  {
    schema_version: "1.0.0",
    id: "paper-demo-001",
    title: "Synthetic Research Example",
    authors: ["Demo Author"],
    institutions: ["Demo Institute"],
    abstract: "Synthetic metadata for contract validation only.",
    year: 2026,
    source: "synthetic-fixture",
    arxiv_id: null,
    doi: null,
    version: "v1",
    file_hash:
      "0000000000000000000000000000000000000000000000000000000000000000",
    page_count: 2,
    has_text_layer: true,
  },
  {
    schema_version: "1.0.0",
    id: "paper-demo-002",
    title: "Synthetic Research Example",
    authors: ["Demo Author"],
    institutions: ["Demo Institute"],
    abstract: "Synthetic metadata for contract validation only.",
    year: 2026,
    source: "synthetic-fixture",
    arxiv_id: null,
    doi: null,
    version: "v7",
    file_hash:
      "1111111111111111111111111111111111111111111111111111111111111111",
    page_count: 2,
    has_text_layer: true,
  },
  {
    schema_version: "1.0.0",
    id: "paper-demo-003",
    title: "Synthetic Scanned Sample",
    authors: ["Scan Author"],
    institutions: ["Scan Institute"],
    abstract: "Synthetic scan sample without a text layer.",
    year: 2026,
    source: "synthetic-fixture",
    arxiv_id: null,
    doi: null,
    version: "v1",
    file_hash:
      "2222222222222222222222222222222222222222222222222222222222222222",
    page_count: 1,
    has_text_layer: false,
  },
] as const;

export default paperMetaMock;
