import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db/client";
import { interviewSessions, questions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { claudeRun } from "@/lib/claude-cli";
import { buildGradingPrompt } from "@/lib/interviewer";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type StoredMsg = { role: string; content: string; ts: number };

const GRADABLE_ROLES = new Set(["user", "assistant", "interviewer", "candidate"]);

function parseTranscript(raw: string | null | undefined): StoredMsg[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Keep both self-mode (user/assistant) and ai-vs-ai (interviewer/candidate);
    // drop steers and any other meta rows.
    return parsed.filter(
      (m): m is StoredMsg =>
        m &&
        typeof m === "object" &&
        typeof m.role === "string" &&
        typeof m.content === "string" &&
        GRADABLE_ROLES.has(m.role),
    );
  } catch {
    return [];
  }
}

type Rubric = {
  score: number;
  sections: {
    clarification: number;
    estimation: number;
    high_level: number;
    deep_dive: number;
    tradeoffs: number;
  };
  strengths: string[];
  gaps: string[];
};

const SECTION_KEYS = ["clarification", "estimation", "high_level", "deep_dive", "tradeoffs"] as const;

const RUBRIC_SCHEMA = {
  type: "object",
  properties: {
    score: { type: "integer", minimum: 0, maximum: 100 },
    sections: {
      type: "object",
      properties: {
        clarification: { type: "integer", minimum: 0, maximum: 100 },
        estimation: { type: "integer", minimum: 0, maximum: 100 },
        high_level: { type: "integer", minimum: 0, maximum: 100 },
        deep_dive: { type: "integer", minimum: 0, maximum: 100 },
        tradeoffs: { type: "integer", minimum: 0, maximum: 100 },
      },
      required: ["clarification", "estimation", "high_level", "deep_dive", "tradeoffs"],
      additionalProperties: false,
    },
    strengths: { type: "array", items: { type: "string" } },
    gaps: { type: "array", items: { type: "string" } },
  },
  required: ["score", "sections", "strengths", "gaps"],
  additionalProperties: false,
} as const;

function clamp(n: unknown): number {
  const v = typeof n === "number" ? n : Number(n);
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(100, Math.round(v)));
}

function normalizeRubric(parsed: unknown): Rubric | null {
  if (!parsed || typeof parsed !== "object") return null;
  const p = parsed as Record<string, unknown>;
  const sectionsIn = (p.sections ?? {}) as Record<string, unknown>;
  const sections = Object.fromEntries(
    SECTION_KEYS.map((k) => [k, clamp(sectionsIn[k])]),
  ) as Rubric["sections"];

  const strengths = Array.isArray(p.strengths)
    ? (p.strengths as unknown[]).filter((s): s is string => typeof s === "string")
    : [];
  const gaps = Array.isArray(p.gaps)
    ? (p.gaps as unknown[]).filter((s): s is string => typeof s === "string")
    : [];

  return { score: clamp(p.score), sections, strengths, gaps };
}

export async function POST(req: NextRequest) {
  let body: { sessionId?: number } = {};
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const sessionId = Number(body.sessionId);
  if (!Number.isFinite(sessionId)) {
    return NextResponse.json({ error: "Missing sessionId" }, { status: 400 });
  }

  const [session] = await db
    .select()
    .from(interviewSessions)
    .where(eq(interviewSessions.id, sessionId))
    .limit(1);
  if (!session) return NextResponse.json({ error: "Session not found" }, { status: 404 });

  const [question] = await db.select().from(questions).where(eq(questions.id, session.questionId)).limit(1);
  if (!question) return NextResponse.json({ error: "Question not found" }, { status: 404 });

  const transcript = parseTranscript(session.transcript);
  if (transcript.length < 2) {
    return NextResponse.json(
      { error: "Transcript too short to grade. Have at least one exchange first." },
      { status: 400 },
    );
  }

  const prompt = buildGradingPrompt(question, transcript);

  let rawText = "";
  try {
    rawText = await claudeRun({
      systemPrompt:
        "You are a strict, fair grader of system-design mock interviews. Output ONLY a JSON object exactly matching the provided schema. No markdown fences. No commentary.",
      prompt,
      jsonSchema: RUBRIC_SCHEMA,
      model: "sonnet",
    });
  } catch (err) {
    console.error("[grade] claude error", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Grading call failed" },
      { status: 502 },
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(rawText);
  } catch (err) {
    console.error("[grade] failed to parse rubric JSON", { rawText, err });
    return NextResponse.json(
      { error: "Grader returned non-JSON output. Try again." },
      { status: 502 },
    );
  }

  const rubric = normalizeRubric(parsed);
  if (!rubric) {
    return NextResponse.json({ error: "Rubric did not match expected schema." }, { status: 502 });
  }

  await db
    .update(interviewSessions)
    .set({
      rubric: JSON.stringify(rubric),
      score: rubric.score,
      endedAt: new Date(),
    })
    .where(eq(interviewSessions.id, sessionId));

  return NextResponse.json(rubric);
}
