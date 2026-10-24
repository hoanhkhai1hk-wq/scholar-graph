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
