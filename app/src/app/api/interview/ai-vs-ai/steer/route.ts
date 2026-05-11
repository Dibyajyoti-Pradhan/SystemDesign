import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db/client";
import { interviewSessions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { z } from "zod";
import { apiAuthGuard } from "@/lib/auth-guards";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const bodySchema = z.object({
  sessionId: z.number().int(),
  content: z.string().min(1).max(2000),
  target: z.enum(["interviewer", "candidate", "both"]),
});

export async function POST(req: NextRequest) {
  const guard = await apiAuthGuard();
  if (guard instanceof NextResponse) return guard;

  let json: unknown;
  try {
    json = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const parsed = bodySchema.safeParse(json);
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.issues }, { status: 400 });
  }
  const { sessionId, content, target } = parsed.data;

  const [session] = await db
    .select()
    .from(interviewSessions)
    .where(eq(interviewSessions.id, sessionId))
    .limit(1);
  if (!session) return NextResponse.json({ error: "Session not found" }, { status: 404 });
  if (session.endedAt) return NextResponse.json({ error: "Session ended" }, { status: 409 });
  if (session.mode !== "ai_vs_ai") {
    return NextResponse.json({ error: "Wrong mode" }, { status: 400 });
  }

  let transcript: any[] = [];
  try {
    transcript = JSON.parse(session.transcript ?? "[]");
    if (!Array.isArray(transcript)) transcript = [];
  } catch {
    transcript = [];
  }

  transcript.push({
    role: "steer",
    content: content.trim(),
    target,
    consumed: false,
    ts: Date.now(),
  });

  await db
    .update(interviewSessions)
    .set({ transcript: JSON.stringify(transcript) })
    .where(eq(interviewSessions.id, sessionId));

  return NextResponse.json({ ok: true });
}
