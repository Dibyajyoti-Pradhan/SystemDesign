import { NextRequest, NextResponse } from "next/server";
import path from "node:path";
import { db } from "@/db/client";
import { interviewSessions, questions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { claudeStream } from "@/lib/anthropic";
import { apiAuthGuard } from "@/lib/auth-guards";
import {
  buildInterviewerSystemPrompt,
  buildCandidateSystemPrompt,
  type PacingContext,
} from "@/lib/interviewer";

const SOFT_BUDGET_TURNS = 20;
const HARD_CAP_TURNS = 24;
import { extractPdfText } from "@/lib/extractPdf";
import { REPO_ROOT } from "@/lib/paths";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Role = "interviewer" | "candidate" | "steer";
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
  // Interviewer always opens. After that, the agent who didn't speak last is up.
  for (let i = transcript.length - 1; i >= 0; i--) {
    const m = transcript[i];
    if (m.role === "interviewer") return "candidate";
    if (m.role === "candidate") return "interviewer";
  }
  return "interviewer";
}

function popPendingSteer(
  transcript: StoredMsg[],
  agent: "interviewer" | "candidate",
): { steer: string | null; updated: StoredMsg[] } {
  // Find latest unconsumed steer matching this agent or 'both'.
  for (let i = transcript.length - 1; i >= 0; i--) {
    const m = transcript[i];
    if (
      m.role === "steer" &&
      !m.consumed &&
      (m.target === agent || m.target === "both")
    ) {
      const updated = transcript.map((x, idx) =>
        idx === i && x.role === "steer" ? { ...x, consumed: true } : x,
      );
      return { steer: m.content, updated };
    }
  }
  return { steer: null, updated: transcript };
}

function buildHistoryForAgent(
  transcript: StoredMsg[],
  agent: "interviewer" | "candidate",
): string {
  // Format the convo history with the OTHER agent labelled as their utterances.
  // We render like an XML-ish transcript so the model parses cleanly.
  const lines: string[] = [];
  for (const m of transcript) {
    if (m.role === "steer") continue;
    const tag = m.role === agent ? "you" : "them";
    lines.push(`<${tag}>\n${m.content}\n</${tag}>`);
  }
  return lines.join("\n\n");
}

export async function POST(req: NextRequest) {
  const guard = await apiAuthGuard();
  if (guard instanceof NextResponse) return guard;

  let body: { sessionId?: number } = {};
  try {
    body = await req.json();
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }
  const sessionId = Number(body.sessionId);
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

  // Substantive turns so far (skip steers).
  const turnsSoFar = transcript.filter((m) => m.role !== "steer").length;
  const upcomingTurn = turnsSoFar + 1;
  const overSoftBudget = upcomingTurn > SOFT_BUDGET_TURNS;
  const atOrPastHardCap = upcomingTurn >= HARD_CAP_TURNS;

  // Force-wrap: if we're at the hard cap and the next agent is the interviewer,
  // they MUST sign off this turn. If we're at the hard cap and the candidate is
  // up, we still let them speak (their final answer), then the interviewer's
  // next turn will be forced. We just route an extra hint via the system prompt.
  const forceWrap = atOrPastHardCap && agent === "interviewer";

  const pacing: PacingContext = {
    turn: upcomingTurn,
    budget: SOFT_BUDGET_TURNS,
    hardCap: HARD_CAP_TURNS,
  };

  // Build the system prompt for the next agent.
  let systemText: string;
  if (agent === "interviewer") {
    let referenceText = "";
    if (question.pdfPath) {
      try {
        const abs = path.join(REPO_ROOT, question.pdfPath);
        referenceText = clipReference(await extractPdfText(abs));
      } catch (err) {
        console.error("[ai-vs-ai] failed to load reference pdf", err);
      }
    }
    systemText = buildInterviewerSystemPrompt(question, referenceText, pacing);
    if (forceWrap) {
      systemText += `\n\n# WRAP-UP REQUIRED THIS TURN
You have hit the hard turn cap. This is your final turn. Give a brief neutral sign-off ("Thanks, that's everything I needed.") and end with the literal token <<INTERVIEW_END>> on its own line. Do not ask any new questions.`;
    } else if (overSoftBudget) {
      systemText += `\n\n# OVER SOFT BUDGET
You are past the soft turn budget. Move to wrap-up THIS turn or next: ask for a single tradeoffs/wrap question if useful, otherwise sign off and emit <<INTERVIEW_END>>.`;
    }
  } else {
    systemText = buildCandidateSystemPrompt(question, pacing);
    if (overSoftBudget) {
      systemText += `\n\n# OVER SOFT BUDGET
The interview is wrapping up. Keep this turn tight — summarize tradeoffs you'd revisit and let the interviewer close out.`;
    }
  }

  // Pull any pending steer for this agent and consume it.
  const { steer, updated: postSteerTranscript } = popPendingSteer(transcript, agent);

  const history = buildHistoryForAgent(postSteerTranscript, agent);

  let userPrompt: string;
  if (postSteerTranscript.filter((m) => m.role !== "steer").length === 0) {
    // First turn ever: interviewer kicks off.
    userPrompt = `Start the interview. Greet the candidate briefly, state the problem you'd like them to design (1-2 sentences), then ask your first clarifying question. Keep it tight.`;
  } else {
    userPrompt = `Conversation so far (you = your past turns, them = the other party):\n\n${history}\n\nNow give your next turn — one substantive response. Stay in character.`;
  }

  if (steer) {
    userPrompt = `[Observer note — react to this in your next turn: ${steer}]\n\n${userPrompt}`;
  }

  // Persist the consumed-steer transcript update before streaming begins, so
  // even if the stream errors mid-flight, we won't double-apply the steer.
  if (steer) {
    await db
      .update(interviewSessions)
      .set({ transcript: JSON.stringify(postSteerTranscript) })
      .where(eq(interviewSessions.id, sessionId));
  }

  const headers = new Headers({
    "content-type": "text/plain; charset=utf-8",
    "cache-control": "no-store",
    "x-accel-buffering": "no",
    "x-agent-role": agent,
    "x-turn-number": String(upcomingTurn),
    "x-soft-budget": String(SOFT_BUDGET_TURNS),
    "x-hard-cap": String(HARD_CAP_TURNS),
  });
  if (steer) headers.set("x-steer-consumed", "1");
  if (forceWrap) headers.set("x-force-wrap", "1");

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder();
      let assistantText = "";
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
          assistantText += delta;
          safeEnqueue(encoder.encode(delta));
        }
      } catch (err) {
        console.error("[ai-vs-ai] stream error", err);
        const msg = err instanceof Error ? err.message : String(err);
        safeEnqueue(encoder.encode(`\n\n[error: ${msg}]`));
      } finally {
        if (assistantText.trim().length > 0) {
          const finalTranscript: StoredMsg[] = [
            ...postSteerTranscript,
            { role: agent, content: assistantText, ts: Date.now() },
          ];
          try {
            await db
              .update(interviewSessions)
              .set({ transcript: JSON.stringify(finalTranscript) })
              .where(eq(interviewSessions.id, sessionId));
          } catch (e) {
            console.error("[ai-vs-ai] failed to persist transcript", e);
          }
        }
        safeClose();
      }
    },
  });

  return new Response(stream, { headers });
}
