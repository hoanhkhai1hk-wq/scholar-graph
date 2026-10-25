import { ApiFetchError, clientUrl } from "./api";
import type { QAAnswer } from "./types";

/**
 * 问答 SSE 客户端。
 *
 * 协议依据 backend/README.md「问答SSE流式端点」与 backend/scholar_graph/qa_sse.py：
 * 每个事件形如 `id: N\nevent: 类型\ndata: JSON单行\n\n`，10 秒无业务事件发 `: keep-alive`。
 * 浏览器原生 EventSource 只发 GET，本端点是 POST，因此用 fetch + ReadableStream 逐事件读。
 */

export interface ModeEvent {
  mode: string;
  token_streaming: boolean;
  fallback_reason: string | null;
  message: string;
}

export interface NodeStartEvent {
  node: string;
  attempt: number;
  evidence_count: number;
  elapsed_seconds: number;
}

export interface NodeEndEvent {
  node: string;
  attempt: number;
  evidence_count: number;
  elapsed_seconds: number;
  validation: boolean | null;
  validation_error: string | null;
  fallback_reason: string | null;
  status: string;
  reason?: string;
}

export interface ToolStartEvent {
  tool_name: string;
  origin: string;
  tool_call_id: string | null;
  attempt: number;
  evidence_count: number;
}

export interface ToolEndEvent {
  tool_name: string;
  origin: string;
  tool_call_id: string | null;
  attempt: number;
  elapsed_seconds: number | null;
  status: string;
  evidence_count: number;
  arguments_summary: Record<string, unknown>;
  return_summary: Record<string, unknown>;
}

export interface TokenEvent {
  node: string;
  attempt: number;
  delta: string;
  verified: boolean;
  channel: string;
}

export interface DoneEvent {
  status: string;
  token_streaming: boolean;
  fallback_reason: string | null;
  metadata?: {
    engine?: string;
    attempts?: number;
    max_attempts?: number;
    validated?: boolean;
    trace?: unknown[];
    tool_calls?: unknown[];
    model_calls?: unknown[];
  };
  model_calls?: unknown[];
}

export interface SseEnvelope {
  id: string | null;
  event: string;
  data: unknown;
}

/** 把一段文本切成完整事件；残留在 rest 里等下一个分块 */
export function parseSseChunk(buffer: string): {
  events: SseEnvelope[];
  rest: string;
} {
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: SseEnvelope[] = [];

  for (const block of blocks) {
    if (!block.trim()) continue;
    let id: string | null = null;
    let event = "message";
    const dataLines: string[] = [];

    for (const rawLine of block.split("\n")) {
      const line = rawLine.replace(/\r$/, "");
      if (line.startsWith(":")) continue; // 注释与 keep-alive
      if (line.startsWith("id:")) id = line.slice(3).trim();
      else if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }

    if (dataLines.length === 0) continue;
    const raw = dataLines.join("\n");
    try {
      events.push({ id, event, data: JSON.parse(raw) });
    } catch {
      // 单个事件解析失败不应中断整条流，记录为 malformed 交给调用方决定
      events.push({ id, event, data: { __malformed: raw } });
    }
  }

  return { events, rest };
}

export interface StreamHandlers {
  onEvent: (envelope: SseEnvelope) => void;
  onDone?: () => void;
  signal?: AbortSignal;
}

/**
 * 发起流式问答。逐事件回调，不缓冲完整响应。
 * 非 2xx（SSE 开始前的 422/404）按统一错误体抛出 ApiFetchError。
 */
export async function streamQa(
  paperId: string,
  question: string,
  handlers: StreamHandlers,
): Promise<void> {
  const url = clientUrl(`/papers/${paperId}/qa/stream`);

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        accept: "text/event-stream",
      },
      body: JSON.stringify({ question }),
      signal: handlers.signal,
      cache: "no-store",
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") {
      throw cause;
    }
    const reason = cause instanceof Error ? cause.message : String(cause);
    throw new ApiFetchError({
      url,
      status: 0,
      errorCode: "NETWORK_ERROR",
      detail: `无法连接后端：${reason}`,
    });
  }

  if (!response.ok) {
    const text = await response.text();
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
      // 保留原文
    }
    throw new ApiFetchError({
      url: response.headers.get("x-sg-upstream-url") ?? url,
      status: response.status,
      errorCode,
      detail,
    });
  }

  if (!response.body) {
    throw new ApiFetchError({
      url: response.headers.get("x-sg-upstream-url") ?? url,
      status: response.status,
      errorCode: "NO_STREAM_BODY",
      detail: "响应没有可读流，无法逐事件读取。",
    });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseChunk(buffer);
      buffer = parsed.rest;
      for (const envelope of parsed.events) {
        handlers.onEvent(envelope);
      }
    }
  } finally {
    handlers.onDone?.();
  }
}

export function isFinalAnswer(data: unknown): data is QAAnswer {
  return (
    typeof data === "object" &&
    data !== null &&
    "answer" in data &&
    "anchors" in data &&
    "numeric_fact_check" in data
  );
}
