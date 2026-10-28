import { NextResponse, type NextRequest } from "next/server";
import { REVIEW_COOKIE, validSession } from "./lib/review-auth";

export async function middleware(request: NextRequest) {
  if (!process.env.SG_REVIEW_CODE) return NextResponse.next();
  const path = request.nextUrl.pathname;
  if (path === "/login" || path === "/api/review/login" || path.startsWith("/_next/") || path === "/favicon.ico") return NextResponse.next();
  const secret = process.env.SG_REVIEW_SIGNING_KEY;
  if (!secret || secret.length < 32) return new NextResponse("评审入口尚未正确配置。", { status: 503 });
  if (await validSession(request.cookies.get(REVIEW_COOKIE)?.value ?? "", secret)) return NextResponse.next();
  if (path.startsWith("/api/")) return NextResponse.json({ error_code: "AUTH_REQUIRED", message: "评审会话已到期，请重新输入访问码。", details: null }, { status: 401 });
  const login = new URL("/login", process.env.SG_PUBLIC_ORIGIN || request.url); login.searchParams.set("next", path + request.nextUrl.search);
  return NextResponse.redirect(login);
}
export const config = { matcher: ["/((?!_next/static|_next/image).*)"] };
