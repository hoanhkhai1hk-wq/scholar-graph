import { NextResponse } from "next/server";
import { REVIEW_COOKIE, equal, signature } from "@/lib/review-auth";
import { boundedBody } from "@/lib/server-transport";
const attempts = new Map<string, { count: number; since: number }>();
let globalAttempts = { count: 0, since: Date.now() };
export async function POST(request: Request) {
  const code = process.env.SG_REVIEW_CODE, secret = process.env.SG_REVIEW_SIGNING_KEY;
  if (!code || !secret || secret.length < 32) return NextResponse.json({ message: "评审入口尚未配置。" }, { status: 503 });
  if (request.headers.get("origin") !== (process.env.SG_PUBLIC_ORIGIN || new URL(request.url).origin)) return NextResponse.json({ message: "请求来源不合法。" }, { status: 403 });
  const peer = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "local";
  const now = Date.now(), prior = attempts.get(peer);
  if (now - globalAttempts.since >= 15 * 60 * 1000) globalAttempts = { count: 0, since: now };
  if (globalAttempts.count >= 240) return NextResponse.json({ message: "体验入口尝试次数较多，请稍后重试。" }, { status: 429 });
  globalAttempts.count++;
  const state = prior && now - prior.since < 15 * 60 * 1000 ? prior : { count: 0, since: now };
  if (state.count >= 8) return NextResponse.json({ message: "尝试次数较多，请十五分钟后重试。" }, { status: 429 });
  state.count++; attempts.set(peer, state);
  if (attempts.size > 2000) for (const [key, value] of attempts) if (now - value.since > 15 * 60 * 1000) attempts.delete(key);
  while (attempts.size > 2000) attempts.delete(attempts.keys().next().value!);
  let submitted: unknown;
  try { submitted = JSON.parse(new TextDecoder().decode(await boundedBody(request, 2048))).code; } catch { return NextResponse.json({ message: "请输入有效的评审访问码。" }, { status: 400 }); }
  if (typeof submitted !== "string" || !equal(submitted, code)) return NextResponse.json({ message: "访问码不正确。" }, { status: 401 });
  attempts.delete(peer);
  const value = `${Date.now() + 24 * 3600 * 1000}.${crypto.randomUUID().replaceAll("-", "")}`;
  const response = NextResponse.json({ ok: true });
  response.cookies.set(REVIEW_COOKIE, `${value}.${await signature(value, secret)}`, { httpOnly: true, sameSite: "strict", secure: new URL(request.url).protocol === "https:" || process.env.SG_SECURE_COOKIE === "true", path: "/", maxAge: 24 * 3600 });
  response.headers.set("cache-control", "no-store");
  return response;
}
