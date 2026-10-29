import { API_BASE_URL } from "@/lib/api";
import { serviceHeaders, boundedBody, reviewMutationAllowed } from "@/lib/server-transport";

export const dynamic = "force-dynamic";
async function forward(request: Request, context: { params: Promise<{ path: string[] }> }) {
  if (!reviewMutationAllowed(request)) return Response.json({ message: "请求来源不合法。" }, { status: 403 });
  const { path } = await context.params;
  if (path.some(part => part === "." || part === ".." || part.includes("/"))) return Response.json({ message: "请求路径不合法。" }, { status: 400 });
  const target = `${API_BASE_URL}/api/v2/${path.map(encodeURIComponent).join("/")}${new URL(request.url).search}`;
  const headers = serviceHeaders();
  for (const name of ["content-type", "accept", "range", "if-range"]) { const value = request.headers.get(name); if (value) headers.set(name, value); }
  try {
    const response = await fetch(target, { method: request.method, headers, cache: "no-store", signal: request.signal, ...(request.method === "GET" ? {} : { body: await boundedBody(request) }) });
    const outgoing = new Headers();
    for (const name of ["content-type", "content-range", "accept-ranges", "cache-control", "x-accel-buffering", "etag"]) { const value = response.headers.get(name); if (value) outgoing.set(name, value); }
    if (outgoing.get("content-type")?.includes("text/event-stream")) outgoing.set("content-encoding", "none");
    return new Response(response.body, { status: response.status, headers: outgoing });
  } catch (error) {
    const large = error instanceof Error && error.message === "REQUEST_TOO_LARGE";
    const truncated = error instanceof Error && error.message === "REQUEST_BODY_TRUNCATED";
    return Response.json({ error_code: large ? "FILE_TOO_LARGE" : truncated ? "INCOMPLETE_UPLOAD" : "NETWORK_ERROR",
      message: large ? "单次请求超过 100 MiB，请分批上传。" : truncated ? "上传数据不完整，未提交解析任务，请重新上传。" : "工作台服务无法连接，请检查后端是否已启动。", details: null }, { status: large ? 413 : truncated ? 400 : 502 });
  }
}
export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
