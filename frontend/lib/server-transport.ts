/** Only imported by server route handlers; never expose the internal service token. */
export function serviceHeaders(headers = new Headers()) {
  const token = process.env.SG_SERVICE_TOKEN;
  if (token) headers.set("x-scholargraph-service", token);
  return headers;
}
export function reviewMutationAllowed(request: Request) {
  if (!process.env.SG_REVIEW_CODE || request.method === "GET") return true;
  return request.headers.get("origin") === (process.env.SG_PUBLIC_ORIGIN || new URL(request.url).origin);
}
export async function boundedBody(request: Request, maximum = 100 * 1024 * 1024): Promise<ArrayBuffer> {
  if (Number(request.headers.get("content-length")) > maximum) throw new Error("REQUEST_TOO_LARGE");
  const reader = request.body?.getReader();
  if (!reader) return new ArrayBuffer(0);
  const chunks: Uint8Array[] = []; let size = 0;
  try { while (true) { const next = await reader.read(); if (next.done) break; size += next.value.byteLength; if (size > maximum) { await reader.cancel(); throw new Error("REQUEST_TOO_LARGE"); } chunks.push(next.value); } }
  finally { reader.releaseLock(); }
  const declared = request.headers.get("content-length");
  if (declared !== null && Number(declared) !== size) throw new Error("REQUEST_BODY_TRUNCATED");
  const body = new Uint8Array(size); let offset = 0; for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; } return body.buffer;
}
