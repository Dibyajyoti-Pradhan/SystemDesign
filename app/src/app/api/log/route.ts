import { NextRequest, NextResponse } from "next/server";
import { devlog } from "@/lib/devlog";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  if (process.env.NODE_ENV === "production") {
    return NextResponse.json({ ok: false }, { status: 404 });
  }
  let body: any;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: "invalid JSON" }, { status: 400 });
  }
  // Accept either a single entry or an array (batched).
  const entries: any[] = Array.isArray(body) ? body : [body];
  for (const e of entries) {
    devlog({
      source: "client",
      level: e.level ?? "info",
      method: e.method,
      url: e.url,
      status: e.status,
      durationMs: e.durationMs,
      message: e.message,
      stack: e.stack,
      meta: e.meta,
    });
  }
  return NextResponse.json({ ok: true });
}
