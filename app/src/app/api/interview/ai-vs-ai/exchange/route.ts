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

// Tightened from 14/16 → 11/13 on 2026-05-13 — at the prior budget,
// <<INTERVIEW_END>> consistently landed past the ~7-min QA budget (v6 & v7
// both ran out before the wrap-up turn). 11-soft / 13-hard pulls the natural
// sign-off into the 5-6 min envelope without skipping deep-dive.
const SOFT_BUDGET_TURNS = 11;
const HARD_CAP_TURNS = 13;
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

/**
 * Pop the most recent unconsumed steer (if any) and return a new transcript
 * with that entry flagged as consumed. The exchange route streams both turns
 * at once so we don't filter by target — the observer note is shown to the
 * combined-prompt model and applies to whichever role it addresses.
 */
function popPendingSteer(transcript: StoredMsg[]): { steer: string | null; target: "interviewer" | "candidate" | "both" | null; updated: StoredMsg[] } {
  for (let i = transcript.length - 1; i >= 0; i--) {
    const m = transcript[i];
    if (m.role === "steer" && !m.consumed) {
      const updated = transcript.map((x, idx) =>
        idx === i && x.role === "steer" ? { ...x, consumed: true } : x,
      );
      return { steer: m.content, target: m.target, updated };
    }
  }
  return { steer: null, target: null, updated: transcript };
}

function stripDrawBlocks(text: string): string {
  return text.replace(/<<DRAW>>[\s\S]*?<<END_DRAW>>/g, "").replace(/\n{3,}/g, "\n\n").trim();
}

/**
 * Fold every persisted DRAW block in the transcript into a compact summary of
 * the current whiteboard. Mirrors the client-side semantics from
 * VoiceAiVsAiSession.buildElements: move applies first, then remove, then
 * boxes (skip already-known ids), then arrows; panels are replace-always.
 *
 * Output looks like:
 *   [WHITEBOARD STATE]
 *   Boxes: client@1,0 | api@2,0 | service@3,0 (○) | db@5,0
 *   Arrows: client→api (read) | api→service (read) | service→db (write)
 *   Panels: requirements(8), scale(5)
 */
interface WBBox { id: string; label: string; c?: number; r?: number; shape: "rect" | "circle"; }
interface WBArrow { from: string; to: string; flow?: string; }

function buildWhiteboardState(transcript: StoredMsg[]): string {
  const boxes = new Map<string, WBBox>();
  const arrows: WBArrow[] = [];
  const panels = new Map<string, number>();

  for (const m of transcript) {
    if (m.role !== "interviewer" && m.role !== "candidate") continue;
    const re = /<<DRAW>>([\s\S]*?)<<END_DRAW>>/g;
    let match: RegExpExecArray | null;
    while ((match = re.exec(m.content)) !== null) {
      const inner = match[1].replace(/^```[a-z]*\n?/i, "").replace(/\n?```$/i, "").trim();
      let cmd: {
        boxes?: Array<{ id?: unknown; label?: unknown; c?: unknown; r?: unknown; shape?: unknown }>;
        arrows?: Array<{ from?: unknown; to?: unknown; flow?: unknown }>;
        panels?: Array<{ id?: unknown; lines?: unknown }>;
        move?: Array<{ id?: unknown; c?: unknown; r?: unknown }>;
        remove?: unknown[];
      };
      try { cmd = JSON.parse(inner); } catch { continue; }

      for (const mv of (cmd.move ?? [])) {
        if (typeof mv?.id !== "string") continue;
        const existing = boxes.get(mv.id);
        if (existing && typeof mv.c === "number" && typeof mv.r === "number") {
          boxes.set(mv.id, { ...existing, c: mv.c, r: mv.r });
        }
      }
      for (const id of (cmd.remove ?? [])) {
        if (typeof id !== "string") continue;
        boxes.delete(id);
        for (let i = arrows.length - 1; i >= 0; i--) {
          if (arrows[i].from === id || arrows[i].to === id) arrows.splice(i, 1);
        }
      }
      for (const box of (cmd.boxes ?? [])) {
        if (typeof box?.id !== "string") continue;
        if (boxes.has(box.id)) continue;
        boxes.set(box.id, {
          id: box.id,
          label: typeof box.label === "string" ? box.label : box.id,
          c: typeof box.c === "number" ? box.c : undefined,
          r: typeof box.r === "number" ? box.r : undefined,
          shape: box.shape === "circle" ? "circle" : "rect",
        });
      }
      for (const arr of (cmd.arrows ?? [])) {
        if (typeof arr?.from !== "string" || typeof arr?.to !== "string") continue;
        arrows.push({ from: arr.from, to: arr.to, flow: typeof arr.flow === "string" ? arr.flow : undefined });
      }
      for (const panel of (cmd.panels ?? [])) {
        if (typeof panel?.id !== "string" || !Array.isArray(panel.lines)) continue;
        panels.set(panel.id, panel.lines.length);
      }
    }
  }

  if (boxes.size === 0 && arrows.length === 0 && panels.size === 0) return "";

  const boxStr = [...boxes.values()].map((b) => {
    const pos = (b.c !== undefined && b.r !== undefined) ? `@${b.c},${b.r}` : "@auto";
    const shape = b.shape === "circle" ? " (○)" : "";
    return `${b.id}${pos}${shape}`;
  }).join(" | ");
  const arrowStr = arrows.map((a) => `${a.from}→${a.to}${a.flow ? ` (${a.flow})` : ""}`).join(" | ");
  const panelStr = [...panels.entries()].filter(([, n]) => n > 0).map(([id, n]) => `${id}(${n})`).join(", ");

  const parts = ["[WHITEBOARD STATE]"];
  if (boxStr) parts.push(`Boxes: ${boxStr}`);
  if (arrowStr) parts.push(`Arrows: ${arrowStr}`);
  if (panelStr) parts.push(`Panels: ${panelStr}`);
  return parts.join("\n");
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

  // Pull any pending observer steer and flag it consumed before streaming.
  const { steer, target, updated: postSteerTranscript } = popPendingSteer(transcript);
  const workingTranscript = steer ? postSteerTranscript : transcript;
  if (steer) {
    await db
      .update(interviewSessions)
      .set({ transcript: JSON.stringify(postSteerTranscript) })
      .where(eq(interviewSessions.id, sessionId));
  }

  const neutralHistory = buildNeutralHistory(workingTranscript);

  let userPrompt: string;
  if (workingTranscript.filter((m) => m.role !== "steer").length === 0) {
    userPrompt = `Start the interview. Interviewer: greet briefly, state the problem, ask your first question. Then candidate: give opening clarifying questions.`;
  } else {
    userPrompt = `Conversation so far:\n\n${neutralHistory}\n\nNow generate the next exchange. The interviewer responds first, then the candidate. Stay in character for both roles.`;
  }

  // Echo the current whiteboard state so the model can reference existing
  // boxes and decide whether to add / move / remove instead of redrawing.
  const wbState = buildWhiteboardState(workingTranscript);
  if (wbState) {
    userPrompt = `${wbState}\n\n${userPrompt}`;
  }

  if (steer) {
    const audience =
      target === "interviewer" ? "the INTERVIEWER" :
      target === "candidate"   ? "the CANDIDATE"   :
      "both roles";
    userPrompt = `[Observer note — incorporate this into the next exchange (${audience}): ${steer}]\n\n${userPrompt}`;
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
  if (steer) headers.set("x-steer-consumed", "1");

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder();
      let fullText = "";
      let closed = false;
      const safeEnqueue = (chunk: Uint8Array) => {
        if (closed) return;
        try {
          controller.enqueue(chunk);
        } catch {
          // Controller was closed by external cancel (client navigated away,
          // page reload, etc.). Mark closed so subsequent calls bail.
          closed = true;
        }
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

            const newMessages: StoredMsg[] = [...workingTranscript];

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
              // Retry on transient SQLITE_BUSY / SQLITE_IOERR — under disk pressure
              // the write fails intermittently and a fresh attempt usually succeeds.
              const payload = {
                transcript: JSON.stringify(newMessages),
                ...(isEnd ? { endedAt: new Date() } : {}),
              };
              let persistErr: unknown = null;
              for (let attempt = 1; attempt <= 4; attempt++) {
                try {
                  await db
                    .update(interviewSessions)
                    .set(payload)
                    .where(eq(interviewSessions.id, sessionId));
                  persistErr = null;
                  break;
                } catch (e) {
                  persistErr = e;
                  const code = (e as { code?: string })?.code ?? "";
                  const transient = code === "SQLITE_BUSY" || code === "SQLITE_LOCKED" || code.startsWith("SQLITE_IOERR");
                  if (!transient || attempt === 4) break;
                  await new Promise((r) => setTimeout(r, 250 * attempt));
                }
              }
              if (persistErr) throw persistErr;
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
