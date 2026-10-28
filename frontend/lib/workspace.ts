import { API_BASE_URL } from "./api";
import type { Chunk, CitationLink, PaperMeta, Paged, ReferenceEntry } from "./types";

export interface PaperView { paper: PaperMeta; original: PaperMeta; archived: boolean; hidden_version: boolean; year_source?: string; missing_fields: string[]; source: string; author_profiles: unknown[]; filename?: string; }
export interface ReadingContext { paper: PaperMeta; outline: { section_path: string[]; page_number: number; chunk_id: string; text: string }[]; chunks: Chunk[]; references: ReferenceEntry[]; citation_links: CitationLink[]; page_number: number; total_chunks: number; bibliography_locations?: Record<string, { page_number: number; chunk_id: string; text: string }>; }
export interface SystemStatus { api_version: string; workspace_release: string; data_class: string; revision: string; model_configured: boolean; qa_mode: string; tracking_enabled: boolean; capabilities: Record<string, boolean>; limits: Record<string, number>; }

export function workspaceUrl(path: string): string { return typeof window === "undefined" ? `${API_BASE_URL}/api/v2${path}` : `/api/workspace${path}`; }
export async function workspaceRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (typeof window === "undefined" && process.env.SG_SERVICE_TOKEN) headers.set("x-scholargraph-service", process.env.SG_SERVICE_TOKEN);
  const response = await fetch(workspaceUrl(path), { cache: "no-store", ...init, headers });
  const value = await response.json().catch(() => null);
  if (!response.ok) throw new Error(value?.message ?? `工作台服务暂时不可用（${response.status}）。请在设置中检查服务版本。`);
  if (value === null) throw new Error("服务返回的数据不完整。");
  return value as T;
}
export function workspacePost<T>(path: string, value: unknown, method = "POST") { return workspaceRequest<T>(path, { method, headers: { "content-type": "application/json" }, body: JSON.stringify(value) }); }
export const getPaperViews = (query = "") => workspaceRequest<Paged<PaperView>>(`/papers${query}`);
export const getReading = (id: string, page = 1, includeNavigation = true) => workspaceRequest<ReadingContext>(`/papers/${encodeURIComponent(id)}/reading?physical_page=${page}&include_navigation=${includeNavigation}`);
