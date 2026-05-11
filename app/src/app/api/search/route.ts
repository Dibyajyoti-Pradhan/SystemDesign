import { NextRequest, NextResponse } from "next/server";
import { search } from "@/lib/search";
import { apiAuthGuard } from "@/lib/auth-guards";

export async function GET(req: NextRequest) {
  const guard = await apiAuthGuard();
  if (guard instanceof NextResponse) return guard;

  const q = req.nextUrl.searchParams.get("q") ?? "";
  const limit = Number(req.nextUrl.searchParams.get("limit") ?? 10);
  const hits = await search(q, limit);
  return NextResponse.json({ hits });
}
