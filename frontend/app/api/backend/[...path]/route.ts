import { API_ROOT } from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * 同源透传：把 /api/backend/* 原样转发到后端 /api/v1/*，不改业务数据。
 *
 * 后端已为 http://localhost:3000 与 http://127.0.0.1:3000 开放 CORS 并暴露
 * X-ScholarGraph-* 响应头，但前端仍统一走这层代理，好处是：
 * 取数路径与服务端一致、不受开发端口变化影响、报错能带回上游真实地址。
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

  // 原样带回上游的 X-ScholarGraph-* 头，前端按后端原值展示检索模式等信息
  upstream.headers.forEach((value, key) => {
    if (key.toLowerCase().startsWith("x-scholargraph-")) {
      headers.set(key, value);
    }
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
