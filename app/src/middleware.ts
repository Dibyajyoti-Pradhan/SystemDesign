import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Logs inbound requests to the dev terminal in development.
// The unified file log lives at app/dev.log — server routes write via
// lib/devlog.ts, client posts to /api/log.
export function middleware(req: NextRequest) {
  if (process.env.NODE_ENV !== "production") {
    const { pathname, search } = req.nextUrl;
    if (!pathname.startsWith("/api/log") && !pathname.startsWith("/_next")) {
      console.log(`[req] ${req.method} ${pathname}${search}`);
    }
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
  ],
};
