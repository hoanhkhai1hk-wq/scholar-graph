/**
 * MOCK DATA — 演示假数据，未接后端。
 * 字段与 contracts/qa-answer.v1.example.json 一致。
 *
 * 第 1 条为契约 example 原样复制（passed，带锚点）。
 * 第 2 条为拒答示例，按同一字段集构造：refused=true、anchors 为空、
 * numeric_fact_check.status=not_applicable 且 checks 为空（契约规定的组合）。
 */
export const qaAnswerMock = [
  {
    schema_version: "1.0.0",
    answer: "The synthetic study contains 12 samples.",
    anchors: [
      {
        paper_id: "paper-demo-001",
        page_number: 1,
        section: ["1 Introduction", "1.1 Setup"],
        chunk_id: "chunk-demo-001-p1-001",
      },
    ],
    numeric_fact_check: {
      status: "passed",
      checks: [
        {
          claim: "The study contains 12 samples.",
          status: "passed",
          evidence: [
            {
              paper_id: "paper-demo-001",
              page_number: 1,
              section: ["1 Introduction", "1.1 Setup"],
              chunk_id: "chunk-demo-001-p1-001",
            },
          ],
          reason:
            "The synthetic chunk explicitly states 12 samples; this is not a real experiment.",
        },
      ],
    },
    refused: false,
  },
  {
    schema_version: "1.0.0",
    answer:
      "拒答：当前论文的分块与参考文献中未出现该结论所需的证据，缺少可定位的分块锚点，因此不给出推测性回答。",
    anchors: [],
    numeric_fact_check: {
      status: "not_applicable",
      checks: [],
    },
    refused: true,
  },
] as const;

export default qaAnswerMock;
