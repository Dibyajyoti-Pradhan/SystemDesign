import { NextRequest } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { apiAuthGuard } from "@/lib/auth-guards";
import { NextResponse } from "next/server";
import { claudeStream } from "@/lib/anthropic";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Role = "interviewer" | "candidate";

interface MessageBody {
  message: string;
  whiteboardState?: string;
  transcriptHistory: { role: Role; content: string }[];
  companyStyle?: "google" | "meta" | "amazon" | "generic";
  hintLevel?: 0 | 1 | 2 | 3;
}

function loadSystemPrompt(): string {
  try {
    return fs.readFileSync(
      path.join(process.cwd(), "../prompts/interview-system.txt"),
      "utf8",
    );
  } catch {
    return "You are a senior staff engineer running a system-design mock interview. Be professional, push back on vague answers, and guide the candidate through clarification, estimation, design, and deep-dives.";
  }
}

const COMPANY_STYLES: Record<string, string> = {
  google: "You are interviewing in Google style: focus on scale, distributed systems correctness, and elegant abstractions. Probe deeply on consistency, replication, and data modeling.",
  meta: "You are interviewing in Meta style: emphasize product thinking alongside technical depth. Ask about trade-offs for billions of users, newsfeed-style fanout, and social graph traversal.",
  amazon: "You are interviewing in Amazon style (leadership principles matter). Ask how they'd own this system end-to-end. Probe operational excellence: monitoring, runbooks, and graceful degradation.",
  generic: "",
};

const HINT_INSTRUCTIONS: Record<number, string> = {
  1: "The candidate has requested a hint. Give a subtle nudge — just point at the area to think about, nothing more.",
  2: "The candidate has requested a hint. Give a clearer hint — explain the concept they're missing without giving the full answer.",
  3: "The candidate has requested a hint. Give a near-complete hint — walk them very close to the answer but let them complete the final step.",
};

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  const guard = await apiAuthGuard();
  if (guard instanceof NextResponse) return guard;

  const { id } = await ctx.params;

  let body: MessageBody;
  try {
    body = await req.json();
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }

  const { message, whiteboardState, transcriptHistory = [], companyStyle, hintLevel = 0 } = body;

  if (!message?.trim()) {
    return new Response("Empty message", { status: 400 });
  }

  // Build system prompt
  let systemText = loadSystemPrompt();
  systemText += `\n\nSession ID: ${id}`;

  if (companyStyle && companyStyle !== "generic" && COMPANY_STYLES[companyStyle]) {
    systemText += `\n\n# Company Interview Style\n${COMPANY_STYLES[companyStyle]}`;
  }

  if (hintLevel && hintLevel > 0 && HINT_INSTRUCTIONS[hintLevel]) {
    systemText += `\n\n# Hint Mode\n${HINT_INSTRUCTIONS[hintLevel]}`;
  }

  // Build messages array for the conversation
  // We use a single user prompt with the full conversation history encoded
  const historyLines: string[] = [];
  for (const msg of transcriptHistory) {
    const tag = msg.role === "interviewer" ? "interviewer" : "candidate";
    historyLines.push(`<${tag}>\n${msg.content}\n</${tag}>`);
  }

  let userPrompt = "";
  if (historyLines.length > 0) {
    userPrompt += `Conversation history so far:\n\n${historyLines.join("\n\n")}\n\n`;
  }

  userPrompt += `Candidate's latest message:\n${message}`;

  if (whiteboardState && whiteboardState !== "[]" && whiteboardState !== "") {
    userPrompt += `\n\nCandidate's current whiteboard state (compact JSON of elements):\n${whiteboardState}`;
  }

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder();
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
    },
  });
}
