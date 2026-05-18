import { NextResponse, type NextRequest } from "next/server";

// 受保护路径前缀(无 token 直接跳 /login)。
const PROTECTED_PREFIXES = ["/test", "/change-password"];

// Middleware 跑在 edge,只能读 cookie,但我们 token 在 localStorage。
// 这里只做一道粗筛:存在 cookie 标记则放行,否则放行至客户端守卫(防止误拦)。
// 实际登录态以 /auth/me 为准(客户端二次校验)。
export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (!PROTECTED_PREFIXES.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }
  // 由客户端 hook 完成 token 校验与跳转,这里只放行。
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|favicon.ico).*)"],
};
