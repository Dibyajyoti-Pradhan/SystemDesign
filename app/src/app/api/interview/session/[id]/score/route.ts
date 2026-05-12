import { NextRequest, NextResponse } from "next/server";
import { apiAuthGuard } from "@/lib/auth-guards";
import { claudeRun } from "@/lib/anthropic";
import { track } from "@/lib/analytics";
import { db } from "@/db/client";
import { interviewSessions } from "@/db/schema";
import { eq } from "drizzle-orm";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface ScoreBody {
  transcriptHistory: { role: "interviewer" | "candidate"; content: string }[];
  whiteboardSnapshot?: string;
}

export interface ScoreObject {
  communication: number;
  correctness: number;
  efficiency: number;
  summary: string;
}

function buildScoringPrompt(
  transcript: { role: string; content: string }[],
): string {
  const formatted = transcript
    .map((m) => {
      const label = m.role === "candidate" ? "Candidate" : "Interviewer";
      return `### ${label}\n${m.content}`;
    })
    .join("\n\n");

  return `You are scoring a system-design mock interview. Below is the full transcript.

<transcript>
${formatted}
</transcript>

Score the CANDIDATE only across three dimensions (each 1-5):
- communication: clarity, structure, and articulation of ideas
- correctness: technical accuracy of the solution and answers
- efficiency: ability to stay on-topic, estimate well, and use time wisely

Respond with ONLY a JSON object — no prose, no markdown fences:
{
  "communication": <integer 1-5>,
  "correctness": <integer 1-5>,
  "efficiency": <integer 1-5>,
  "summary": "<exactly 2 sentences: first sentence a strength, second sentence a key area to improve>"
}`;
}

function clampScore(n: unknown): number {
  const v = typeof n === "number" ? n : Number(n);
  if (!Number.isFinite(v)) return 1;
  return Math.max(1, Math.min(5, Math.round(v)));
}

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  const guard = await apiAuthGuard();
  if (guard instanceof NextResponse) return guard;

  const { id } = await ctx.params;

  let body: ScoreBody;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { transcriptHistory = [], whiteboardSnapshot } = body;

  if (transcriptHistory.length < 2) {
    return NextResponse.json(
      { error: "Transcript too short. Have at least one exchange first." },
      { status: 400 },
    );
  }

  const prompt = buildScoringPrompt(transcriptHistory);

  let rawText = "";
  try {
    rawText = await claudeRun({
      prompt,
      model: "sonnet",
      jsonSchema: {
        type: "object",
        properties: {
          communication: { type: "integer", minimum: 1, maximum: 5 },
          correctness: { type: "integer", minimum: 1, maximum: 5 },
          efficiency: { type: "integer", minimum: 1, maximum: 5 },
          summary: { type: "string" },
        },
        required: ["communication", "correctness", "efficiency", "summary"],
      },
    });
  } catch (err) {
    console.error("[interview/session/score] claude error", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Scoring call failed" },
      { status: 502 },
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(rawText);
  } catch {
    return NextResponse.json(
      { error: "Scorer returned non-JSON output. Try again." },
      { status: 502 },
    );
  }

  if (!parsed || typeof parsed !== "object") {
    return NextResponse.json({ error: "Invalid score object" }, { status: 502 });
  }

  const p = parsed as Record<string, unknown>;
  const score: ScoreObject = {
    communication: clampScore(p.communication),
    correctness: clampScore(p.correctness),
    efficiency: clampScore(p.efficiency),
    summary: typeof p.summary === "string" ? p.summary : "",
  };

  track('interview_complete', { communication: score.communication, correctness: score.correctness, efficiency: score.efficiency })

  const sessionId = Number.parseInt(id, 10);
  if (Number.isFinite(sessionId)) {
    const updateValues: Record<string, unknown> = { endedAt: new Date() };
    if (whiteboardSnapshot) updateValues.whiteboardSnapshot = whiteboardSnapshot;
    await db
      .update(interviewSessions)
      .set(updateValues)
      .where(eq(interviewSessions.id, sessionId));
  }

  return NextResponse.json(score);
}
