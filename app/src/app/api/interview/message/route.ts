import { NextRequest } from "next/server";
import path from "node:path";
import { db } from "@/db/client";
import { interviewSessions, questions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { claudeStream, formatTranscriptAsPrompt } from "@/lib/anthropic";
import { buildInterviewerSystemPrompt } from "@/lib/interviewer";
import { extractPdfText } from "@/lib/extractPdf";
import { REPO_ROOT } from "@/lib/paths";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type StoredMsg = { role: "user" | "assistant"; content: string; ts: number };

function parseTranscript(raw: string | null | undefined): StoredMsg[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (m): m is StoredMsg =>
        m && typeof m === "object" && (m.role === "user" || m.role === "assistant") && typeof m.content === "string",
    );
  } catch {
    return [];
  }
}

function clipReference(text: string, max = 24_000): string {
  if (text.length <= max) return text;
  return text.slice(0, max) + "\n\n[reference truncated]";
}

export async function POST(req: NextRequest) {
  let body: { sessionId?: number; content?: string; autoBegin?: boolean } = {};
  try {
    body = await req.json();
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }
  const sessionId = Number(body.sessionId);
  const userContent = typeof body.content === "string" ? body.content : "";
  const autoBegin = !!body.autoBegin;

  if (!Number.isFinite(sessionId)) {
    return new Response("Missing sessionId", { status: 400 });
  }
  if (!autoBegin && !userContent.trim()) {
    return new Response("Empty content", { status: 400 });
  }

  const [session] = await db
    .select()
    .from(interviewSessions)
    .where(eq(interviewSessions.id, sessionId))
    .limit(1);
  if (!session) return new Response("Session not found", { status: 404 });
  if (session.endedAt) return new Response("Session already ended", { status: 409 });

  const [question] = await db.select().from(questions).where(eq(questions.id, session.questionId)).limit(1);
  if (!question) return new Response("Question not found", { status: 404 });

  let referenceText = "";
  if (question.pdfPath) {
    try {
      const abs = path.join(REPO_ROOT, question.pdfPath);
      referenceText = clipReference(await extractPdfText(abs));
    } catch (err) {
      console.error("[interview] failed to load reference pdf", err);
    }
  }

  const systemText = buildInterviewerSystemPrompt(question, referenceText);

  const transcript = parseTranscript(session.transcript);
  const apiMessages: { role: "user" | "assistant"; content: string }[] = transcript.map((m) => ({
    role: m.role,
    content: m.content,
  }));

  if (autoBegin) {
    if (apiMessages.length === 0) {
      apiMessages.push({
        role: "user",
        content:
          "Hi — I'm ready to start the interview. Please greet me, briefly state the problem you want me to design, and ask your first question.",
      });
    }
  } else {
    apiMessages.push({ role: "user", content: userContent });
  }

  const persistedTranscript: StoredMsg[] = [...transcript];
  if (!autoBegin) {
    persistedTranscript.push({ role: "user", content: userContent, ts: Date.now() });
  }

  // Render the full conversation as a single prompt. Claude Code is stateless
  // for our purposes — our DB is the source of truth for the transcript.
  const conversationPrompt = formatTranscriptAsPrompt(apiMessages);

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
          prompt: conversationPrompt,
          model: "sonnet",
        })) {
          assistantText += delta;
          safeEnqueue(encoder.encode(delta));
        }
      } catch (err) {
        console.error("[interview] stream error", err);
        const msg = err instanceof Error ? err.message : String(err);
        safeEnqueue(encoder.encode(`\n\n[error: ${msg}]`));
      } finally {
        if (assistantText.trim().length > 0) {
          persistedTranscript.push({
            role: "assistant",
            content: assistantText,
            ts: Date.now(),
          });
        }
        try {
          await db
            .update(interviewSessions)
            .set({ transcript: JSON.stringify(persistedTranscript) })
            .where(eq(interviewSessions.id, sessionId));
        } catch (e) {
          console.error("[interview] failed to persist transcript", e);
        }
        safeClose();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
      "x-accel-buffering": "no",
    },
  });
}
