import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db/client";
import { notes } from "@/db/schema";
import { eq } from "drizzle-orm";
import { apiAuthGuard } from "@/lib/auth-guards";

export async function POST(req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const guard = await apiAuthGuard();
  if (guard instanceof NextResponse) return guard;

  const { id } = await ctx.params;
  const formData = await req.formData().catch(() => null);
  const method = formData?.get("_method");
  if (method === "DELETE") {
    await db.delete(notes).where(eq(notes.id, Number(id)));
    return NextResponse.redirect(new URL("/notes", req.url), { status: 303 });
  }
  return NextResponse.json({ error: "Unknown method override" }, { status: 400 });
}

export async function DELETE(req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const guard = await apiAuthGuard();
  if (guard instanceof NextResponse) return guard;

  const { id } = await ctx.params;
  await db.delete(notes).where(eq(notes.id, Number(id)));
  return NextResponse.json({ ok: true });
}
