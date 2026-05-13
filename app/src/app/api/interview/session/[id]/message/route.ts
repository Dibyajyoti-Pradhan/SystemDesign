import { NextRequest, NextResponse } from "next/server";
import path from "node:path";
import { eq } from "drizzle-orm";
import { db } from "@/db/client";
import { interviewSessions, questions } from "@/db/schema";
import { apiAuthGuard } from "@/lib/auth-guards";
import { claudeStream } from "@/lib/anthropic";
import {
  buildInterviewerSystemPrompt,
  type InterviewConfig,
  type PacingContext,
} from "@/lib/interviewer";
import { extractPdfText } from "@/lib/extractPdf";
import { REPO_ROOT } from "@/lib/paths";
import logger from "@/lib/logger";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const SOFT_BUDGET_TURNS = 20;
const HARD_CAP_TURNS = 24;

type Role = "interviewer" | "candidate";

interface MessageBody {
  message: string;
  whiteboardState?: string;
  transcriptHistory?: { role: Role; content: string }[];
  hintLevel?: 0 | 1 | 2 | 3;
  voiceMode?: boolean;
  config?: InterviewConfig;
}

function clipReference(text: string, max = 24_000): string {
  if (text.length <= max) return text;
  return text.slice(0, max) + "\n\n[reference truncated]";
}

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  const guard = await apiAuthGuard();
  if (guard instanceof NextResponse) return guard;

  const { id: idStr } = await ctx.params;
  const sessionId = Number.parseInt(idStr, 10);
  if (!Number.isFinite(sessionId)) {
    return new Response("Invalid session id", { status: 400 });
  }

  let body: MessageBody;
  try {
    body = await req.json();
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }

  const {
    message,
    whiteboardState,
    transcriptHistory = [],
    hintLevel = 0,
    voiceMode = true,
    config,
  } = body;

  if (!message?.trim()) {
    return new Response("Empty message", { status: 400 });
  }

  // Load session + question so we can ground on the real reference solution
  const [session] = await db
    .select()
    .from(interviewSessions)
    .where(eq(interviewSessions.id, sessionId))
    .limit(1);
  if (!session) return new Response("Session not found", { status: 404 });
  if (session.endedAt) return new Response("Session already ended", { status: 409 });

  const [question] = await db
    .select()
    .from(questions)
    .where(eq(questions.id, session.questionId))
    .limit(1);
  if (!question) return new Response("Question not found", { status: 404 });

  // Pacing — the upcoming turn is one past how many interviewer messages exist.
  const interviewerTurns = transcriptHistory.filter((m) => m.role === "interviewer").length;
  const upcomingTurn = interviewerTurns + 1;
  const pacing: PacingContext = {
    turn: upcomingTurn,
    budget: SOFT_BUDGET_TURNS,
    hardCap: HARD_CAP_TURNS,
  };

  // Optional reference text (PDF that ships with the question)
  let referenceText = "";
  if (question.pdfPath) {
    try {
      const abs = path.join(REPO_ROOT, question.pdfPath);
      referenceText = clipReference(await extractPdfText(abs));
    } catch (err) {
      logger.warn({ err, questionId: question.id }, "[voice] failed to load reference pdf");
    }
  }

  let systemText = buildInterviewerSystemPrompt(
    question,
    referenceText,
    pacing,
    voiceMode,
    config,
  );

  // Force-wrap if we're past the hard cap
  if (upcomingTurn >= HARD_CAP_TURNS) {
    systemText += `\n\n# WRAP-UP REQUIRED THIS TURN
You have hit the hard turn cap. This is your final turn. Give a brief neutral sign-off ("Thanks, that's everything I needed.") and end with the literal token <<INTERVIEW_END>> on its own line. Do not ask any new questions.`;
  } else if (upcomingTurn > SOFT_BUDGET_TURNS) {
    systemText += `\n\n# OVER SOFT BUDGET
You are past the soft turn budget. Move to wrap-up THIS turn or next: ask for a single tradeoffs/wrap question if useful, otherwise sign off and emit <<INTERVIEW_END>>.`;
  }

  if (hintLevel > 0) {
    systemText += `\n\n# HINT REQUESTED THIS TURN
The candidate explicitly asked for a hint. Deliver a Level ${hintLevel} hint per the Hint Policy. Do not skip levels. After the hint, return to your normal pushback rhythm.`;
  }

  // Build the user prompt — full history rendered XML-style for clean parsing.
  const lines: string[] = [];
  for (const m of transcriptHistory) {
    const tag = m.role === "interviewer" ? "you" : "them";
    lines.push(`<${tag}>\n${m.content}\n</${tag}>`);
  }
  const historyBlock = lines.length
    ? `Conversation so far (you = your past turns, them = the candidate):\n\n${lines.join("\n\n")}\n\n`
    : "";

  let userPrompt =
    historyBlock +
    `Candidate's latest message:\n${message}\n\nNow give your next turn — one substantive response. Stay in character.`;

  if (whiteboardState && whiteboardState !== "[]" && whiteboardState !== "") {
    userPrompt += `\n\nCandidate's current whiteboard state (compact JSON of elements):\n${whiteboardState}`;
  }

  logger.info(
    {
      route: "interview/session/message",
      userId: guard.userId,
      sessionId,
      messageLength: message.length,
      turn: upcomingTurn,
      hintLevel,
      voiceMode,
    },
    "interview message received",
  );

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder();
      let closed = false;
      const safeEnqueue = (chunk: Uint8Array) => {
        if (closed) return;
        try { controller.enqueue(chunk); } catch { closed = true; }
      };
      const safeClose = () => {
        if (!closed) {
          closed = true;
          try { controller.close(); } catch {}
        }
      };

      try {
        for await (const delta of claudeStream({
          systemPrompt: systemText,
          prompt: userPrompt,
          model: "sonnet",
        })) {
          safeEnqueue(encoder.encode(delta));
        }
      } catch (err) {
        console.error("[interview/session/message] stream error", err);
        const msg = err instanceof Error ? err.message : String(err);
        safeEnqueue(encoder.encode(`\n\n[error: ${msg}]`));
      } finally {
        safeClose();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
      "x-accel-buffering": "no",
      "x-turn-number": String(upcomingTurn),
    },
  });
}
