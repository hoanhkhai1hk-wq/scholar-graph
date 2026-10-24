/**
 * MOCK DATA — 演示假数据，未接后端。
 * 字段与 contracts/diff-summary.v1.1.example.json 一致（原样复制）。
 *
 * changed_sections 为变化章节；key_sentences 含 1 条 verified（有锚点）
 * 与 1 条 unverified（anchor 为 null），用于演示「无锚点即不可验证」的展示口径。
 */
export const diffSummaryMock = [
  {
    schema_version: "1.1.0",
    old_paper_id: "paper-demo-001",
    new_paper_id: "paper-demo-002",
    changed_sections: ["1 Introduction / 1.1 Setup"],
    summary_text:
      "Synthetic comparison only: the stated sample count changes from 12 to 18, and the new version describes a corrected protocol.",
    key_sentences: [
      {
        text: "The synthetic study contains 18 samples and uses a corrected protocol.",
        anchor: {
          paper_id: "paper-demo-002",
          page_number: 1,
          section: ["1 Introduction", "1.1 Setup"],
          chunk_id: "chunk-demo-002-p1-001",
        },
        status: "verified",
      },
      {
        text: "A synthetic additional revision claim has no located source chunk.",
        anchor: null,
        status: "unverified",
      },
    ],
  },
] as const;

export default diffSummaryMock;
