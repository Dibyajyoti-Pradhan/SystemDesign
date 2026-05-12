import { NextRequest, NextResponse } from "next/server";
import path from "node:path";
import { db } from "@/db/client";
import { interviewSessions, questions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { claudeStream } from "@/lib/anthropic";
import { apiAuthGuard } from "@/lib/auth-guards";
import {
  buildExchangeSystemPrompt,
  type PacingContext,
} from "@/lib/interviewer";

const SOFT_BUDGET_TURNS = 20;
const HARD_CAP_TURNS = 24;
import { extractPdfText } from "@/lib/extractPdf";
import { REPO_ROOT } from "@/lib/paths";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type StoredMsg =
  | { role: "interviewer" | "candidate"; content: string; ts: number }
  | { role: "steer"; content: string; target: "interviewer" | "candidate" | "both"; consumed: boolean; ts: number };

function parseTranscript(raw: string | null | undefined): StoredMsg[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (m): m is StoredMsg =>
        m && typeof m === "object" && typeof m.role === "string" && typeof m.content === "string",
    );
  } catch {
    return [];
  }
}

function clipReference(text: string, max = 24_000): string {
  if (text.length <= max) return text;
  return text.slice(0, max) + "\n\n[reference truncated]";
}

function nextAgent(transcript: StoredMsg[]): "interviewer" | "candidate" {
  for (let i = transcript.length - 1; i >= 0; i--) {
    const m = transcript[i];
    if (m.role === "interviewer") return "candidate";
    if (m.role === "candidate") return "interviewer";
  }
  return "interviewer";
}

function buildNeutralHistory(transcript: StoredMsg[]): string {
  const lines: string[] = [];
  for (const m of transcript) {
    if (m.role === "steer") continue;
    const label = m.role === "interviewer" ? "Interviewer" : "Candidate";
    lines.push(`[${label}]: ${m.content}`);
  }
  return lines.join("\n\n");
}

function stripDrawBlocks(text: string): string {
  return text.replace(/<<DRAW>>[\s\S]*?<<END_DRAW>>/g, "").replace(/\n{3,}/g, "\n\n").trim();
}

export async function POST(req: NextRequest) {
  const guard = await apiAuthGuard();
  if (guard instanceof NextResponse) return guard;

  let body: { sessionId?: number; voiceMode?: boolean } = {};
  try {
    body = await req.json();
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }
  const sessionId = Number(body.sessionId);
  const voiceMode = body.voiceMode === true;
  if (!Number.isFinite(sessionId)) {
    return new Response("Missing sessionId", { status: 400 });
  }

  const [session] = await db
    .select()
    .from(interviewSessions)
    .where(eq(interviewSessions.id, sessionId))
    .limit(1);
  if (!session) return new Response("Session not found", { status: 404 });
  if (session.endedAt) return new Response("Session already ended", { status: 409 });
  if (session.mode !== "ai_vs_ai") {
    return new Response("Wrong mode for this route", { status: 400 });
  }

  const [question] = await db
    .select()
    .from(questions)
    .where(eq(questions.id, session.questionId))
    .limit(1);
  if (!question) return new Response("Question not found", { status: 404 });

  const transcript = parseTranscript(session.transcript);
  const agent = nextAgent(transcript);

  // Exchange always starts from the interviewer. If it's the candidate's turn,
  // caller should use /step instead.
  if (agent !== "interviewer") {
    return new Response(
      "Candidate turn next — use /step for single-turn stepping",
      { status: 409 },
    );
  }

  // Substantive turns so far (skip steers).
  const turnsSoFar = transcript.filter((m) => m.role !== "steer").length;
  const ivTurn = turnsSoFar + 1;
  const cxTurn = ivTurn + 1;
  const overSoftBudget = ivTurn > SOFT_BUDGET_TURNS;
  const atOrPastHardCap = ivTurn >= HARD_CAP_TURNS;
  const forceWrap = atOrPastHardCap;

  const pacing: PacingContext = {
    turn: ivTurn,
    budget: SOFT_BUDGET_TURNS,
    hardCap: HARD_CAP_TURNS,
  };

  let referenceText = "";
  if (question.pdfPath) {
    try {
      const abs = path.join(REPO_ROOT, question.pdfPath);
      referenceText = clipReference(await extractPdfText(abs));
    } catch (err) {
      console.error("[ai-vs-ai/exchange] failed to load reference pdf", err);
    }
  }

  let systemText = buildExchangeSystemPrompt(question, referenceText, pacing, undefined, undefined);

  if (forceWrap) {
    systemText += `\n\n# WRAP-UP REQUIRED THIS TURN
You have hit the hard turn cap. This is the interviewer's final turn. The interviewer MUST give a brief neutral sign-off and end with the literal token <<INTERVIEW_END>> on its own line. Do not ask any new questions. You may omit the <<CX>> section if the interview ends.`;
  } else if (overSoftBudget) {
    systemText += `\n\n# OVER SOFT BUDGET
You are past the soft turn budget. The interviewer should move to wrap-up THIS turn or next: ask for a single tradeoffs/wrap question if useful, otherwise sign off and emit <<INTERVIEW_END>>.`;
  }

  void voiceMode; // voiceMode already embedded in exchange system prompt

  const neutralHistory = buildNeutralHistory(transcript);

  let userPrompt: string;
  if (transcript.filter((m) => m.role !== "steer").length === 0) {
    userPrompt = `Start the interview. Interviewer: greet briefly, state the problem, ask your first question. Then candidate: give opening clarifying questions.`;
  } else {
    userPrompt = `Conversation so far:\n\n${neutralHistory}\n\nNow generate the next exchange. The interviewer responds first, then the candidate. Stay in character for both roles.`;
  }

  const headers = new Headers({
    "content-type": "text/plain; charset=utf-8",
    "cache-control": "no-store",
    "x-accel-buffering": "no",
    "x-iv-turn": String(ivTurn),
    "x-cx-turn": String(cxTurn),
    "x-soft-budget": String(SOFT_BUDGET_TURNS),
    "x-hard-cap": String(HARD_CAP_TURNS),
  });
  if (forceWrap) headers.set("x-force-wrap", "1");

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder();
      let fullText = "";
      let closed = false;
      const safeEnqueue = (chunk: Uint8Array) => {
        if (!closed) controller.enqueue(chunk);
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
          fullText += delta;
          safeEnqueue(encoder.encode(delta));
        }
      } catch (err) {
        console.error("[ai-vs-ai/exchange] stream error", err);
        const msg = err instanceof Error ? err.message : String(err);
        safeEnqueue(encoder.encode(`\n\n[error: ${msg}]`));
      } finally {
        // Parse IV and CX sections from the completed response
        if (fullText.trim().length > 0) {
          try {
            // Split on <<IV>> and <<CX>> markers
            const ivIdx = fullText.indexOf("<<IV>>");
            const cxIdx = fullText.indexOf("<<CX>>");

            let ivRaw = "";
            let cxRaw = "";

            if (ivIdx !== -1 && cxIdx !== -1 && cxIdx > ivIdx) {
              ivRaw = fullText.slice(ivIdx + 6, cxIdx).trim();
              cxRaw = fullText.slice(cxIdx + 6).trim();
            } else if (ivIdx !== -1 && cxIdx === -1) {
              // Only IV section (e.g., interview ended with <<INTERVIEW_END>>)
              ivRaw = fullText.slice(ivIdx + 6).trim();
            } else {
              // Fallback: treat entire text as IV
              ivRaw = fullText.trim();
            }

            const ivContent = stripDrawBlocks(ivRaw.replace(/<<INTERVIEW_END>>/g, "")).trim();
            const isEnd = ivRaw.includes("<<INTERVIEW_END>>");

            const newMessages: StoredMsg[] = [...transcript];

            if (ivContent) {
              newMessages.push({ role: "interviewer", content: ivRaw, ts: Date.now() });
            }

            if (!isEnd && cxRaw.trim()) {
              const cxContent = stripDrawBlocks(cxRaw).trim();
              if (cxContent) {
                newMessages.push({ role: "candidate", content: cxRaw, ts: Date.now() + 1 });
              }
            }

            if (newMessages.length > transcript.length) {
              await db
                .update(interviewSessions)
                .set({
                  transcript: JSON.stringify(newMessages),
                  ...(isEnd ? { endedAt: new Date() } : {}),
                })
                .where(eq(interviewSessions.id, sessionId));
            }
          } catch (e) {
            console.error("[ai-vs-ai/exchange] failed to persist transcript", e);
          }
        }
        safeClose();
      }
    },
  });

  return new Response(stream, { headers });
}
