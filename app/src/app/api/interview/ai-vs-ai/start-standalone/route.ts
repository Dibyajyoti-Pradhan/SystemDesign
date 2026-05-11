import { NextRequest, NextResponse } from "next/server";
import { apiAuthGuard } from "@/lib/auth-guards";
import { db } from "@/db/client";
import { interviewSessions, questions } from "@/db/schema";
import { eq } from "drizzle-orm";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Creates an AI vs AI session for the standalone /interview/ai-vs-ai page.
 * Looks up a question by slug (topic), or falls back to the first available question.
 */
export async function POST(req: NextRequest) {
  const guard = await apiAuthGuard();
  if (guard instanceof NextResponse) return guard;
  const { userId } = guard;

  let body: { topic?: string; difficulty?: string } = {};
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { topic, difficulty = "medium" } = body;

  let questionId: number;

  // Try to find a question matching the topic slug
  if (topic) {
    const [q] = await db
      .select({ id: questions.id })
      .from(questions)
      .where(eq(questions.slug, topic))
      .limit(1);
    if (q) {
      questionId = q.id;
    } else {
      // Fall back to any question with matching difficulty
      const [fallback] = await db
        .select({ id: questions.id })
        .from(questions)
        .where(eq(questions.difficulty, difficulty))
        .limit(1);
      if (fallback) {
        questionId = fallback.id;
      } else {
        // Last resort: first question
        const [first] = await db
          .select({ id: questions.id })
          .from(questions)
          .limit(1);
        if (!first) {
          return NextResponse.json(
            { error: "No questions found in database. Please seed the database first." },
            { status: 404 },
          );
        }
        questionId = first.id;
      }
    }
  } else {
    const [first] = await db.select({ id: questions.id }).from(questions).limit(1);
    if (!first) {
      return NextResponse.json(
        { error: "No questions found in database." },
        { status: 404 },
      );
    }
    questionId = first.id;
  }

  const [created] = await db
    .insert(interviewSessions)
    .values({
      userId,
      questionId,
      mode: "ai_vs_ai",
      transcript: "[]",
    })
    .returning({ id: interviewSessions.id });

  return NextResponse.json({ sessionId: created.id });
}
