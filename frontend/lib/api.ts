import type {
  BatchResult,
  Chunk,
  CitationLink,
  DedupDecision,
  DiffSummary,
  Paged,
  PaperMeta,
  ParseStatus,
  ReferenceEntry,
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

export async function uploadSingle(file: File): Promise<PaperMeta> {
  const form = new FormData();
  form.append("file", file);
  return requestJson<PaperMeta>(clientUrl("/papers"), {
    method: "POST",
    body: form,
  });
}

export async function uploadBatch(files: File[]): Promise<BatchResult> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  return requestJson<BatchResult>(clientUrl("/papers/batch"), {
    method: "POST",
    body: form,
  });
}
