import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db/client";
import { questions, interviewSessions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { requireUser } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  let userId: string;
  try {
    userId = await requireUser();
  } catch {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { slug, mode } = await req.json();
  if (!slug) return NextResponse.json({ error: "slug required" }, { status: 400 });

  const [q] = await db.select().from(questions).where(eq(questions.slug, slug)).limit(1);
  if (!q) return NextResponse.json({ error: "Question not found" }, { status: 404 });

  const [created] = await db
    .insert(interviewSessions)
    .values({
      userId,
      questionId: q.id,
      mode: mode === "ai_vs_ai" ? "ai_vs_ai" : "self",
      transcript: "[]",
    })
    .returning({ id: interviewSessions.id });

  return NextResponse.json({ id: created.id });
}
