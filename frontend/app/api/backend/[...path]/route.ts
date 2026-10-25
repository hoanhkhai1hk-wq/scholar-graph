import { API_ROOT } from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * 同源透传：把 /api/backend/* 原样转发到后端 /api/v1/*，不改业务数据。
 *
 * 后端已为 http://localhost:3000 与 http://127.0.0.1:3000 开放 CORS 并暴露
 * X-ScholarGraph-* 响应头，但前端仍统一走这层代理，好处是：
 * 取数路径与服务端一致、不受开发端口变化影响、报错能带回上游真实地址。
 *
 * 关键：SSE（text/event-stream）必须**流式透传**。
 * 早期版本用 upstream.text() 一次性缓冲，SSE 会被憋到结束才吐出，页面拿不到增量。
 * 现在对流式响应直接回传 upstream.body：不缓冲、不解析、不拼装事件。
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
  const target = `${API_ROOT}/${pathSegments.join("/")}${incoming.search}`;

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method,
      ...(method === "POST"
        ? {
            headers: {
              "content-type":
                request.headers.get("content-type") ??
                "application/octet-stream",
              accept: request.headers.get("accept") ?? "application/json",
            },
            body: await request.arrayBuffer(),
          }
        : {}),
      cache: "no-store",
    });
  } catch (cause) {
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

  if (contentType.includes("text/event-stream")) {
    // SSE：保留后端设置的流式头，直接透传 body。
    // 代理层不做事件解析，也不拼答案。
    const cacheControl = upstream.headers.get("cache-control");
    const accelBuffering = upstream.headers.get("x-accel-buffering");
    if (cacheControl) headers.set("cache-control", cacheControl);
    if (accelBuffering) headers.set("x-accel-buffering", accelBuffering);
    // 避免中间层压缩把增量攒到结束
    headers.set("content-encoding", "none");

    return new Response(upstream.body, { status: upstream.status, headers });
  }

  // 非流式：原样回传正文（错误体也保持后端三字段形状）
  const body = await upstream.text();
  return new Response(body, { status: upstream.status, headers });
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
