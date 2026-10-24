/**
 * MOCK DATA — 演示假数据，未接后端。
 * 字段与 contracts/parse-status.v1.1.example.json 一致。
 *
 * 本数据集按「每篇论文一条静态状态序列」组织，用于静态展示状态推进：
 * 页面不做轮询、不做动画，只把各时点的快照并排列出。
 *
 * 三条路径：
 *   paper-demo-001 → 失败路径，末端记录为 contracts/parse-status.v1.1.example.json 的原样复制
 *   paper-demo-002 → 文本正常路径，末端为 completed
 *   paper-demo-003 → 扫描 OCR 路径，parsing 后进入 ocr，末端为 completed
 *
 * 除 001 末端那条外，其余记录为按同一字段集构造的补充快照，未引入任何契约外字段。
 */
export const parseStatusMock = [
  // paper-demo-001：失败路径
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
    current_stage:
      "Parsing page structure and extracting chunks; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-001",
    status: "failed",
    progress: 35,
    current_stage: "Synthetic OCR failure example; no parsing service was run.",
    error_code: "OCR_FAILED",
    error_message: "Synthetic example: OCR could not extract usable text.",
  },

  // paper-demo-002：文本正常路径
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-002",
    status: "queued",
    progress: 0,
    current_stage: "Waiting in the upload queue; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-002",
    status: "parsing",
    progress: 30,
    current_stage:
      "Parsing page structure and extracting chunks; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-002",
    status: "indexing",
    progress: 80,
    current_stage:
      "Building reference entries and citation links; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-002",
    status: "completed",
    progress: 100,
    current_stage: "All stages finished; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },

  // paper-demo-003：扫描 OCR 路径
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-003",
    status: "queued",
    progress: 0,
    current_stage: "Waiting in the upload queue; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-003",
    status: "parsing",
    progress: 30,
    current_stage: "Parsing page structure; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-003",
    status: "ocr",
    progress: 40,
    current_stage:
      "No text layer detected, switching to the OCR branch; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-003",
    status: "ocr",
    progress: 70,
    current_stage:
      "OCR branch is recognizing page images; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-003",
    status: "indexing",
    progress: 95,
    current_stage:
      "Building reference entries and citation links; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
  {
    schema_version: "1.1.0",
    paper_id: "paper-demo-003",
    status: "completed",
    progress: 100,
    current_stage: "All stages finished; synthetic static snapshot.",
    error_code: null,
    error_message: null,
  },
] as const;

export default parseStatusMock;
