/**
 * MOCK DATA — 演示假数据，未接后端。
 * 字段与 contracts/dedup-decision.v1.1.example.json 一致（原样复制）。
 *
 * old_paper_id = paper-demo-001（v1，正文 12 samples）
 * new_paper_id = paper-demo-002（v7，正文 18 samples）
 * recommendation = keep_new，human_override = false
 */
export const dedupDecisionMock = [
  {
    schema_version: "1.1.0",
    old_paper_id: "paper-demo-001",
    new_paper_id: "paper-demo-002",
    similarity: 0.94,
    evidence: [
      {
        anchor: {
          paper_id: "paper-demo-002",
          page_number: 1,
          section: ["1 Introduction", "1.1 Setup"],
          chunk_id: "chunk-demo-002-p1-001",
        },
        reason:
          "Synthetic comparison only: the old chunk states 12 samples; the new chunk states 18 samples and describes a corrected protocol, providing the stated basis for preferring the new version.",
      },
    ],
    recommendation: "keep_new",
    human_override: false,
  },
] as const;

export default dedupDecisionMock;
