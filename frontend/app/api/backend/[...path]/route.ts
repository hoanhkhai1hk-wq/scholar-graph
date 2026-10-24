import { API_ROOT } from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * 后端未开启 CORS，浏览器无法直连不同源地址。
 * 这里做同源透传：把 /api/backend/* 原样转发到后端 /api/v1/*，
 * 不改业务数据，只补两个诊断响应头（上游地址与上游状态码）。
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

  const body = await upstream.text();
  const headers = new Headers({
    "content-type": upstream.headers.get("content-type") ?? "application/json",
    "x-sg-upstream-url": target,
    "x-sg-upstream-status": String(upstream.status),
  });

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
