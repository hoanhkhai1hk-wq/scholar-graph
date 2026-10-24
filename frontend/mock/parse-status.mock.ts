/**
 * MOCK DATA — 演示假数据，未接后端。
 * 字段与 contracts/parse-status.v1.1.example.json 一致。
 *
 * 第 1 条为契约 example 原样复制（failed / OCR_FAILED）。
 * 其余条目按同一字段集构造，用于静态展示状态推进过程：
 * 本页面不做轮询、不动画，只把几个时点的快照并排列出。
 */
export const parseStatusMock = [
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-001",
    status: "queued",
    progress: 0,
    current_stage: "Waiting in the upload queue; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-001",
    status: "parsing",
    progress: 30,
    current_stage: "Parsing page structure and extracting chunks; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-001",
    status: "indexing",
    progress: 80,
    current_stage: "Building reference entries and citation links; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-001",
    status: "completed",
    progress: 100,
    current_stage: "All stages finished; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
] as const;

export default parseStatusMock;
