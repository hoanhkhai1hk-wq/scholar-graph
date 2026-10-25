import type {
  AgentMeta,
  BatchResult,
  ChartOutput,
  Chunk,
  CitationLink,
  CompareResult,
  DedupDecision,
  DiffSummary,
  FetchResult,
  FrameworkOutline,
  GraphView,
  Paged,
  PaperMeta,
  ParseStatus,
  QAAnswer,
  QaMeta,
  RecommendationItem,
  ReferenceEntry,
  ReviewDraft,
  SearchHit,
  SearchMeta,
} from "./types";

/**
 * 取数基地址。
 * 默认 http://127.0.0.1:8000 来自后端启动说明（backend/README.md 与
 * tests/reports/module-one-api-report.md 的 uvicorn 启动命令），不是猜测。
 * 本地联调时以后端实际启动的地址为准，用 NEXT_PUBLIC_API_BASE_URL 覆盖。
 */
export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

function normalizeBase(value: string): string {
  return value.replace(/\/+$/, "");
}

const RAW_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL;

export const API_BASE_URL = normalizeBase(RAW_BASE);
export const API_ROOT = `${API_BASE_URL}/api/v1`;

/** 浏览器侧经同源代理转发，避免后端未开 CORS 导致直连被拦 */
export const PROXY_ROOT = "/api/backend";

export const DEFAULT_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 100;

export class ApiFetchError extends Error {
  readonly url: string;
  readonly status: number;
  readonly errorCode: string;
  readonly detail: string;

  constructor(args: {
    url: string;
    status: number;
    errorCode: string;
    detail: string;
  }) {
    super(`${args.errorCode}（HTTP ${args.status}）${args.detail}`);
    this.name = "ApiFetchError";
    this.url = args.url;
    this.status = args.status;
    this.errorCode = args.errorCode;
    this.detail = args.detail;
  }
}

async function requestJson<T>(
  url: string,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, { cache: "no-store", ...init });
  } catch (cause) {
    const reason = cause instanceof Error ? cause.message : String(cause);
    throw new ApiFetchError({
      url,
      status: 0,
      errorCode: "NETWORK_ERROR",
      detail: `无法连接后端：${reason}`,
    });
  }

  const text = await response.text();
  // 经代理转发时，上游真实地址由响应头带回，报错要显示真实接口地址
  const reportedUrl = response.headers.get("x-sg-upstream-url") ?? url;

  if (!response.ok) {
    let errorCode = "HTTP_ERROR";
    let detail = text;
    try {
      const parsed = JSON.parse(text) as {
        error_code?: string;
        message?: string;
      };
      if (parsed.error_code) errorCode = parsed.error_code;
      if (parsed.message) detail = parsed.message;
    } catch {
      // 非 JSON 错误体，保留原文
    }
    throw new ApiFetchError({
      url: reportedUrl,
      status: response.status,
      errorCode,
      detail,
    });
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiFetchError({
      url: reportedUrl,
      status: response.status,
      errorCode: "INVALID_JSON",
      detail: "后端返回的不是合法 JSON。",
    });
  }
}

/**
 * 需要读取响应头的调用（检索模式、向量状态、推荐原因）。
 * 头由同源代理原样带回，前端按后端原值展示，不改写语义。
 */
export async function requestJsonWithHeaders<T>(
  url: string,
  init?: RequestInit,
): Promise<{ data: T; headers: Headers }> {
  let response: Response;
  try {
    response = await fetch(url, { cache: "no-store", ...init });
  } catch (cause) {
    const reason = cause instanceof Error ? cause.message : String(cause);
    throw new ApiFetchError({
      url,
      status: 0,
      errorCode: "NETWORK_ERROR",
      detail: `无法连接后端：${reason}`,
    });
  }

  const text = await response.text();
  const reportedUrl =
    response.headers.get("x-sg-upstream-url") ?? url;

  if (!response.ok) {
    let errorCode = "HTTP_ERROR";
    let detail = text;
    try {
      const parsed = JSON.parse(text) as {
        error_code?: string;
        message?: string;
      };
      if (parsed.error_code) errorCode = parsed.error_code;
      if (parsed.message) detail = parsed.message;
    } catch {
      // 非 JSON 错误体，保留原文
    }
    throw new ApiFetchError({
      url: reportedUrl,
      status: response.status,
      errorCode,
      detail,
    });
  }

  try {
    return { data: JSON.parse(text) as T, headers: response.headers };
  } catch {
    throw new ApiFetchError({
      url: reportedUrl,
      status: response.status,
      errorCode: "INVALID_JSON",
      detail: "后端返回的不是合法 JSON。",
    });
  }
}

/** 服务端组件直连后端；客户端组件走同源代理 */
export function serverUrl(endpointPath: string): string {
  return `${API_ROOT}${endpointPath}`;
}

export function clientUrl(endpointPath: string): string {
  return `${PROXY_ROOT}${endpointPath}`;
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

function clampPageSize(pageSize: number): number {
  if (!Number.isFinite(pageSize) || pageSize < 1) return DEFAULT_PAGE_SIZE;
  return Math.min(Math.floor(pageSize), MAX_PAGE_SIZE);
}

// ---------------------------------------------------------------- 读取端点

export interface PagedQuery {
  page?: number;
  pageSize?: number;
}

/**
 * 翻完一个分页端点的所有页。用于阅读器这类需要完整材料的页面。
 * 达到 maxPages 时停止并标记 truncated，页面须如实说明材料不完整。
 */
export async function fetchAllPages<T>(
  fetchPage: (page: number) => Promise<Paged<T>>,
  options: { maxPages?: number } = {},
): Promise<{ items: T[]; total: number; truncated: boolean }> {
  const maxPages = options.maxPages ?? 20;
  let current = await fetchPage(1);
  const items = [...current.items];
  const total = current.total;
  let page = 1;
  let truncated = false;

  while (current.has_next) {
    if (page >= maxPages) {
      truncated = true;
      break;
    }
    page += 1;
    current = await fetchPage(page);
    items.push(...current.items);
  }

  return { items, total, truncated };
}

export async function fetchPapers(
  query: PagedQuery & { title?: string; year?: string; source?: string } = {},
): Promise<Paged<PaperMeta>> {
  const qs = buildQuery({
    page: query.page ?? 1,
    page_size: clampPageSize(query.pageSize ?? DEFAULT_PAGE_SIZE),
    title: query.title,
    year: query.year,
    source: query.source,
  });
  return requestJson<Paged<PaperMeta>>(serverUrl(`/papers${qs}`));
}

export async function fetchPaper(paperId: string): Promise<PaperMeta> {
  return requestJson<PaperMeta>(serverUrl(`/papers/${paperId}`));
}

export async function fetchChunks(
  paperId: string,
  query: PagedQuery = {},
): Promise<Paged<Chunk>> {
  const qs = buildQuery({
    page: query.page ?? 1,
    page_size: clampPageSize(query.pageSize ?? MAX_PAGE_SIZE),
  });
  return requestJson<Paged<Chunk>>(
    serverUrl(`/papers/${paperId}/chunks${qs}`),
  );
}

export async function fetchReferences(
  paperId: string,
  query: PagedQuery = {},
): Promise<Paged<ReferenceEntry>> {
  const qs = buildQuery({
    page: query.page ?? 1,
    page_size: clampPageSize(query.pageSize ?? MAX_PAGE_SIZE),
  });
  return requestJson<Paged<ReferenceEntry>>(
    serverUrl(`/papers/${paperId}/references${qs}`),
  );
}

export async function fetchCitationLinks(
  paperId: string,
  query: PagedQuery = {},
): Promise<Paged<CitationLink>> {
  const qs = buildQuery({
    page: query.page ?? 1,
    page_size: clampPageSize(query.pageSize ?? MAX_PAGE_SIZE),
  });
  return requestJson<Paged<CitationLink>>(
    serverUrl(`/papers/${paperId}/citation-links${qs}`),
  );
}

export async function fetchParseStatus(
  paperId: string,
): Promise<ParseStatus> {
  return requestJson<ParseStatus>(
    serverUrl(`/papers/${paperId}/parse-status`),
  );
}

/**
 * 无去重记录时后端返回 404 / PAPER_NOT_FOUND，此处返回 null，
 * 由页面显示「暂无去重记录」，不编造假记录顶替。
 */
export async function fetchDedupDecision(
  paperId: string,
): Promise<DedupDecision | null> {
  try {
    return await requestJson<DedupDecision>(
      serverUrl(`/papers/${paperId}/dedup-decision`),
    );
  } catch (error) {
    if (error instanceof ApiFetchError && error.status === 404) return null;
    throw error;
  }
}

export async function fetchDiffSummary(
  paperId: string,
): Promise<DiffSummary | null> {
  try {
    return await requestJson<DiffSummary>(
      serverUrl(`/papers/${paperId}/diff-summary`),
    );
  } catch (error) {
    if (error instanceof ApiFetchError && error.status === 404) return null;
    throw error;
  }
}

// ------------------------------------------------------- 客户端调用（经代理）

export async function clientFetchParseStatus(
  paperId: string,
): Promise<ParseStatus> {
  return requestJson<ParseStatus>(
    clientUrl(`/papers/${paperId}/parse-status`),
  );
}

/**
 * 后端响应头为 UTF-8 百分号编码（见 backend/README.md：
 * X-ScholarGraph-Dedup-Warning 与 X-ScholarGraph-QA-Meta / Agent-Meta）。
 * 必须先解码再展示，不能直接把 %E4%BD%A0 之类的串给用户看。
 */
export function decodePercentUtf8(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    // 非法百分号序列：解码失败时返回原值，页面会照实显示原始串
    return value;
  }
}

/** 读取编排元数据两个响应头，缺失时返回 null，不编造内容 */
export function readMetaHeaders(headers: Headers): {
  agentMeta: AgentMeta | null;
  qaMeta: QaMeta | null;
} {
  const agentRaw = headers.get("x-scholargraph-agent-meta");
  const qaRaw = headers.get("x-scholargraph-qa-meta");

  let agentMeta: AgentMeta | null = null;
  let qaMeta: QaMeta | null = null;

  if (agentRaw) {
    try {
      agentMeta = JSON.parse(decodePercentUtf8(agentRaw)) as AgentMeta;
    } catch {
      agentMeta = null;
    }
  }
  if (qaRaw) {
    try {
      qaMeta = JSON.parse(decodePercentUtf8(qaRaw)) as QaMeta;
    } catch {
      qaMeta = null;
    }
  }

  return { agentMeta, qaMeta };
}

export interface QaResponse<T> {
  data: T;
  agentMeta: AgentMeta | null;
  qaMeta: QaMeta | null;
}

export interface UploadResult {
  data: PaperMeta;
  warning: string | null;
}

export async function uploadSingle(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const { data, headers } = await requestJsonWithHeaders<PaperMeta>(
    clientUrl("/papers"),
    { method: "POST", body: form },
  );
  const raw = headers.get("x-scholargraph-dedup-warning");
  return {
    data,
    warning: raw ? decodePercentUtf8(raw) : null,
  };
}

export interface BatchUploadResult {
  data: BatchResult;
  /** 批量时后端在命中成功项上附加可选的 warning 字段 */
  warnings: Record<string, string>;
}

export async function uploadBatch(files: File[]): Promise<BatchUploadResult> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  const data = await requestJson<BatchResult>(clientUrl("/papers/batch"), {
    method: "POST",
    body: form,
  });
  const warnings: Record<string, string> = {};
  for (const item of data.succeeded) {
    const warning = (item as { warning?: string }).warning;
    if (warning) {
      warnings[item.paper_id] = warning;
    }
  }
  return { data, warnings };
}

// ------------------------------------------------------- 模块二：问答与对比

function postJsonClient<T>(endpointPath: string, payload: unknown): Promise<T> {
  return requestJson<T>(clientUrl(endpointPath), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function askQuestion(
  paperId: string,
  question: string,
  options: { agent?: boolean } = {},
): Promise<QaResponse<QAAnswer>> {
  const suffix = options.agent ? "?agent=true" : "";
  const { data, headers } = await requestJsonWithHeaders<QAAnswer>(
    clientUrl(`/papers/${paperId}/qa${suffix}`),
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question }),
    },
  );
  return { data, ...readMetaHeaders(headers) };
}

export async function comparePapers(
  paperIds: string[],
  question: string,
  options: { agent?: boolean } = {},
): Promise<QaResponse<CompareResult>> {
  const suffix = options.agent ? "?agent=true" : "";
  const { data, headers } = await requestJsonWithHeaders<CompareResult>(
    clientUrl(`/compare${suffix}`),
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ paper_ids: paperIds, question }),
    },
  );
  return { data, ...readMetaHeaders(headers) };
}

// --------------------------------------------------------- 模块五：引用图谱

export async function fetchGraph(paperIds: string[]): Promise<GraphView> {
  const params = new URLSearchParams();
  for (const id of paperIds) {
    params.append("paper_ids", id);
  }
  return requestJson<GraphView>(serverUrl(`/graph?${params.toString()}`));
}

/** 客户端版本：经同源代理，用于用户在页面上勾选论文后即时生成 */
export async function clientFetchGraph(
  paperIds: string[],
): Promise<GraphView> {
  const params = new URLSearchParams();
  for (const id of paperIds) {
    params.append("paper_ids", id);
  }
  return requestJson<GraphView>(clientUrl(`/graph?${params.toString()}`));
}

// ------------------------------------------------ 模块四：检索、抓取与推荐

export interface SearchResponse {
  data: Paged<SearchHit>;
  meta: SearchMeta;
}

export async function searchRetrieval(payload: {
  question: string;
  paper_ids?: string[];
  page?: number;
  page_size?: number;
  min_relevance?: number;
}): Promise<SearchResponse> {
  const { data, headers } = await requestJsonWithHeaders<Paged<SearchHit>>(
    clientUrl("/retrieval/search"),
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return {
    data,
    meta: {
      mode: headers.get("x-scholargraph-search-mode"),
      vectorStatus: headers.get("x-scholargraph-vector-status"),
      reason: headers.get("x-scholargraph-search-reason"),
    },
  };
}

export async function fetchArxiv(payload: {
  title?: string;
  reference?: ReferenceEntry;
}): Promise<FetchResult> {
  return postJsonClient<FetchResult>("/retrieval/fetch", payload);
}

export interface RecommendationResponse {
  data: Paged<RecommendationItem>;
  reason: string | null;
}

export async function fetchRecommendations(params: {
  paperId: string;
  asOfYear?: number;
  page?: number;
  pageSize?: number;
}): Promise<RecommendationResponse> {
  const qs = buildQuery({
    paper_id: params.paperId,
    as_of_year: params.asOfYear,
    page: params.page ?? 1,
    page_size: clampPageSize(params.pageSize ?? DEFAULT_PAGE_SIZE),
  });
  const { data, headers } =
    await requestJsonWithHeaders<Paged<RecommendationItem>>(
      clientUrl(`/recommendations${qs}`),
    );
  return {
    data,
    reason: headers.get("x-scholargraph-recommendation-reason"),
  };
}

// -------------------------------------------------- 模块六：框架、草稿与图表

export async function generateFramework(
  paperIds: string[],
): Promise<FrameworkOutline> {
  return postJsonClient<FrameworkOutline>("/frameworks", {
    paper_ids: paperIds,
  });
}

export async function generateReview(payload: {
  paper_ids: string[];
  framework: FrameworkOutline;
  requirements?: string[];
}): Promise<ReviewDraft> {
  return postJsonClient<ReviewDraft>("/reviews", payload);
}

export async function uploadCsvChart(payload: {
  file: File;
  value_columns: string[];
  chart_type?: string;
  x_column?: string;
  caption?: string;
}): Promise<ChartOutput> {
  const form = new FormData();
  form.append("file", payload.file);
  form.append("value_columns", JSON.stringify(payload.value_columns));
  if (payload.chart_type) form.append("chart_type", payload.chart_type);
  if (payload.x_column) form.append("x_column", payload.x_column);
  if (payload.caption) form.append("caption", payload.caption);
  return requestJson<ChartOutput>(clientUrl("/charts/csv"), {
    method: "POST",
    body: form,
  });
}
