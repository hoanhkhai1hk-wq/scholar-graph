import { API_ROOT } from "@/lib/api";
import { serviceHeaders, boundedBody, reviewMutationAllowed } from "@/lib/server-transport";

export const dynamic = "force-dynamic";

/**
 * 同源透传：把 /api/backend/* 原样转发到后端 /api/v1/*，不改业务数据。
 *
 * 后端已为 http://localhost:3000 与 http://127.0.0.1:3000 开放 CORS 并暴露
 * X-ScholarGraph-* 响应头，但前端仍统一走这层代理，好处是：
 * 取数路径与服务端一致、不受开发端口变化影响、报错能带回上游真实地址。
 *
 * 关键：所有响应都**直接回传 upstream.body**，不做 text() 缓冲。
 * 早期版本用 upstream.text() 一次性缓冲，有两个后果：
 * SSE 被憋到结束才吐出（页面拿不到增量）；二进制响应（如原文 PDF 的
 * GET /papers/{id}/file）被按 UTF-8 解码而损坏。
 * 现在统一回传 body：流式、二进制安全，且代理层不改任何字节。
 *
 * 补充的响应头：x-sg-upstream-url（上游地址）、x-sg-upstream-status（上游状态码），
 * 以及原样带回上游所有 X-ScholarGraph-* 头（检索模式、向量状态、推荐原因）。
 */
async function forward(
  request: Request,
  pathSegments: string[],
  method: "GET" | "POST",
) {
  const incoming = new URL(request.url);
  if (!reviewMutationAllowed(request)) return Response.json({ message: "请求来源不合法。" }, { status: 403 });
  if (pathSegments.some(segment => segment === "." || segment === ".." || segment.includes("/"))) return Response.json({ message: "请求路径不合法。" }, { status: 400 });
  const target = `${API_ROOT}/${pathSegments.map(encodeURIComponent).join("/")}${incoming.search}`;

  let upstream: Response;
  try {
    const requestHeaders = serviceHeaders();
    for (const name of ["range", "if-range", "if-none-match", "accept"]) {
      const value = request.headers.get(name);
      if (value) requestHeaders.set(name, value);
    }
    if (method === "POST") requestHeaders.set("content-type", request.headers.get("content-type") ?? "application/octet-stream");
    upstream = await fetch(target, {
      method,
      headers: requestHeaders,
      ...(method === "POST"
        ? {
            body: await boundedBody(request),
          }
        : {}),
      cache: "no-store",
      signal: request.signal,
    });
  } catch (cause) {
    if (cause instanceof Error && cause.message === "REQUEST_TOO_LARGE") return Response.json({ error_code: "FILE_TOO_LARGE", message: "单次请求超过 100 MiB，请分批上传。", details: null }, { status: 413 });
    const reason = cause instanceof Error ? cause.message : String(cause);
    return Response.json(
      {
        error_code: "NETWORK_ERROR",
        message: `无法连接后端 ${API_ROOT}：${reason}`,
        details: null,
      },
      {
        status: 502,
        headers: { "x-sg-upstream-url": target, "x-sg-upstream-status": "0" },
      },
    );
  }

  const headers = new Headers({
    "content-type": upstream.headers.get("content-type") ?? "application/json",
    "x-sg-upstream-url": target,
    "x-sg-upstream-status": String(upstream.status),
  });

  // 原样带回上游的 X-ScholarGraph-* 头，前端按后端原值展示检索模式等信息
  upstream.headers.forEach((value, key) => {
    if (key.toLowerCase().startsWith("x-scholargraph-")) {
      headers.set(key, value);
    }
  });

  const contentType = upstream.headers.get("content-type") ?? "";

  // 原文件端点按 Range 请求返回 206/416，相关头原样带回，pdf.js 才能用分片读取
  for (const name of ["content-disposition", "accept-ranges", "etag", "content-range", ...(contentType.includes("application/pdf") ? ["content-length"] : [])]) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }

  if (contentType.includes("text/event-stream")) {
    // SSE：保留后端流式头，避免中间层压缩把增量攒到结束
    const cacheControl = upstream.headers.get("cache-control");
    const accelBuffering = upstream.headers.get("x-accel-buffering");
    if (cacheControl) headers.set("cache-control", cacheControl);
    if (accelBuffering) headers.set("x-accel-buffering", accelBuffering);
    headers.set("content-encoding", "none");
  }

  // 统一回传 body：SSE 流式、PDF 二进制安全、错误体也保持后端三字段形状
  return new Response(upstream.body, { status: upstream.status, headers });
}

export async function GET(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  return forward(request, path, "GET");
}

export async function POST(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  return forward(request, path, "POST");
}
