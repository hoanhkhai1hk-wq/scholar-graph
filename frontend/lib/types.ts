/**
 * 与 contracts/ 下 v1 与 v1.1 契约记录对应的前端类型。
 * 字段名与契约一致，不新增、不改名。
 */

export interface PaperMeta {
  schema_version: string;
  id: string;
  title: string | null;
  authors: string[];
  institutions: string[];
  abstract: string | null;
  year: number | null;
  source: string | null;
  arxiv_id: string | null;
  doi: string | null;
  version: string | null;
  file_hash: string | null;
  page_count: number | null;
  has_text_layer: boolean | null;
}

export type ChunkType = "text" | "table" | "figure" | "formula";

export interface Chunk {
  schema_version: string;
  chunk_id: string;
  paper_id: string;
  page_number: number;
  section_path: string[];
  heading_1: string | null;
  heading_2: string | null;
  heading_3: string | null;
  text: string;
  bbox: number[] | null;
  type: ChunkType;
}

export interface ReferenceEntry {
  schema_version: string;
  ref_id: string;
  paper_id: string;
  number: number;
  authors: string[];
  year: number | null;
  title: string | null;
  venue: string | null;
  doi: string | null;
  arxiv_id: string | null;
}

export interface CitationLink {
  schema_version: string;
  paper_id: string;
  citation_number: number;
  page_number: number;
  chunk_id: string;
  ref_id: string;
}

export type ParseStatusValue =
  | "queued"
  | "parsing"
  | "ocr"
  | "indexing"
  | "completed"
  | "failed";

export interface ParseStatus {
  schema_version: string;
  paper_id: string;
  status: ParseStatusValue;
  progress: number;
  current_stage: string;
  error_code: string | null;
  error_message: string | null;
}

export interface Anchor {
  paper_id: string;
  page_number: number;
  section: string[];
  chunk_id: string;
}

export interface DedupEvidence {
  anchor: Anchor;
  reason: string;
}

export interface DedupDecision {
  schema_version: string;
  old_paper_id: string;
  new_paper_id: string;
  similarity: number;
  evidence: DedupEvidence[];
  recommendation: "keep_new" | "keep_old" | "keep_both" | "manual_review";
  human_override: boolean;
}

export interface KeySentence {
  text: string;
  anchor: Anchor | null;
  status: "verified" | "unverified";
}

export interface DiffSummary {
  schema_version: string;
  old_paper_id: string;
  new_paper_id: string;
  changed_sections: string[];
  summary_text: string;
  key_sentences: KeySentence[];
}

// ---------------------------------------------------------- 模块二：问答与对比

export interface NumericCheck {
  claim: string;
  status: "passed" | "failed" | "unverifiable";
  evidence: Anchor[];
  reason: string;
}

export interface NumericFactCheck {
  status: "passed" | "failed" | "unverifiable" | "not_applicable";
  checks: NumericCheck[];
}

export interface QAAnswer {
  schema_version: string;
  answer: string;
  anchors: Anchor[];
  numeric_fact_check: NumericFactCheck;
  refused: boolean;
}

export interface EvidenceRow {
  evidence_id: string;
  per_paper_index: number;
  anchor: Anchor;
  quotes: string[];
}

export interface CompareResult {
  evidence_table: EvidenceRow[];
  per_paper: QAAnswer[];
  synthesis: string;
}

// ------------------------------------------------------------ 模块五：引用图谱

export interface GraphNode {
  schema_version: string;
  paper_id: string;
  title: string | null;
  year: number | null;
  pagerank: number;
  level: "cornerstone" | "derived" | "isolated";
}

export interface GraphEdge {
  schema_version: string;
  from_paper_id: string;
  to_paper_id: string;
  anchor: Anchor | null;
  status: "verified" | "unverified";
}

export interface FutureWorkDirection {
  direction_id: string;
  topic: string;
  source: QAAnswer;
  resolutions: QAAnswer[];
}

export interface FutureWorkCheck {
  direction_id: string;
  candidate_paper_id: string;
  decision: string;
  reason: string;
}

export interface GraphDiagnostics {
  unresolved_references: { paper_id: string; ref_id: string; reason: string }[];
  pagerank: {
    damping: number;
    tolerance: number;
    max_iterations: number;
    iterations: number;
    residual: number;
    verified_pair_count: number;
    uniform_baseline: number;
  };
}

export interface GraphView {
  nodes: GraphNode[];
  edges: GraphEdge[];
  layers: {
    cornerstone: string[];
    derived: string[];
    isolated: string[];
  };
  future_work: {
    worth_exploring: FutureWorkDirection[];
    excluded: FutureWorkDirection[];
    unverifiable: FutureWorkDirection[];
    checks: FutureWorkCheck[];
  };
  diagnostics: GraphDiagnostics;
}

// ---------------------------------------------- 模块四：检索、抓取与推荐

export interface SearchHit {
  chunk: Chunk;
  anchor: Anchor;
  relevance: number;
  retrieval_method: string;
}

/** 检索响应头原样回显，不得把词法说成向量 */
export interface SearchMeta {
  mode: string | null;
  vectorStatus: string | null;
  reason: string | null;
}

export interface FetchResult {
  succeeded: boolean;
  metadata: PaperMeta | null;
  paper: PaperMeta | null;
  initial_parse_status: ParseStatus | null;
  parse_status: ParseStatus | null;
  error: { error_code: string; message: string; details: unknown } | null;
}

export interface RecommendationSignals {
  graph_neighbor: number | null;
  pagerank_normalized: number | null;
  recency: number | null;
  github_link: number | null;
}

export interface RecommendationReason {
  signal: string;
  text: string;
  evidence: string[];
}

export interface RecommendationItem {
  paper: PaperMeta;
  score: number;
  signals: RecommendationSignals;
  reasons: RecommendationReason[];
  missing_signals: string[];
  scoring_version: string;
  as_of_year: number;
}

// -------------------------------------------------- 模块六：框架、草稿与图表

export interface WritingPoint {
  text: string;
  anchor: Anchor | null;
}

export interface FrameworkChapter {
  chapter_id: string;
  kind: string;
  title: string;
  paper_ids: string[];
  anchors: Anchor[];
  writing_points: WritingPoint[];
}

export interface FrameworkOutline {
  schema_version: string;
  paper_ids: string[];
  chapters: FrameworkChapter[];
}

export interface ReviewPoint {
  text: string;
  status: "verified" | "unverifiable";
  anchors: Anchor[];
  numeric_fact_check: NumericFactCheck;
  requirement: string | null;
}

export interface ReviewChapter {
  chapter_id: string;
  title: string;
  points: ReviewPoint[];
}

export interface ReviewDraft {
  framework: FrameworkOutline;
  chapters: ReviewChapter[];
  mode: string;
  unverifiable_count: number;
}

export interface ChartSeries {
  name: string;
  values: number[];
}

export interface ChartNumericCheck {
  value: number;
  csv_anchor: {
    csv_ref: string;
    row_number: number;
    column_name: string;
  };
  verified: boolean;
}

export interface ChartOutput {
  schema_version: string;
  chart_id: string;
  chart_type: string;
  series: ChartSeries[];
  image_ref: string;
  caption: string;
  numeric_checks: ChartNumericCheck[];
}

// ------------------------------------------------- 编排 trace 与调用元数据

/** LangGraph 节点轨迹行：plan → retrieve → qa → validate */
export interface TraceRow {
  node: string;
  elapsed_seconds: number;
  attempt: number;
  evidence_count: number;
  validation: boolean | null;
  validation_error: string | null;
  fallback_reason: string | null;
}

/** 工具调用行：origin 为 model_function_call 时表示真实模型发起 */
export interface ToolCallRow {
  tool_name: string;
  tool_call_id: string | null;
  attempt: number;
  origin: string;
  arguments_summary: Record<string, unknown>;
  return_summary: Record<string, unknown>;
  elapsed_seconds: number | null;
  status: string;
}

/** X-ScholarGraph-Agent-Meta 解码后的结构 */
export interface AgentMeta {
  engine: string;
  attempts: number;
  max_attempts: number;
  fallback_reason: string | null;
  trace: TraceRow[];
  tool_calls: ToolCallRow[];
  model_calls: ModelCallRow[];
  checkpointing: boolean;
  external_tracing: boolean;
  validated: boolean;
}

/** X-ScholarGraph-QA-Meta 与 Agent-Meta 中的模型调用统计 */
export interface ModelCallRow {
  provider: string;
  model: string;
  phase: string;
  elapsed_seconds: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  http_status: number | null;
  status: string;
}

export interface QaMeta {
  model_calls: ModelCallRow[];
}

/** 列表端点统一分页壳（六字段，docs/api-draft-v1.md 已定义） */
export interface Paged<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
}

/** 全 API 统一错误体，引用 ParseStatus 的 #/$defs/api_error */
export interface ApiErrorBody {
  error_code: string;
  message: string;
  details: unknown;
}

export interface BatchSucceededItem {
  paper_id: string;
  parse_status: ParseStatus;
}

export interface BatchFailedItem {
  filename: string;
  error_code: string;
  error_message: string;
}

export interface BatchResult {
  succeeded: BatchSucceededItem[];
  failed: BatchFailedItem[];
  succeeded_count: number;
  failed_count: number;
}
