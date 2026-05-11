import { NextRequest } from "next/server";
import { claudeStream } from "@/lib/anthropic";
import { ASSISTANT_SYSTEM_PROMPT, resolvePageContext } from "@/lib/assistantContext";
import { apiAuthGuard } from "@/lib/auth-guards";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface Body {
  messages: ChatMessage[];
  pathname?: string;
}

function formatHistoryAsPrompt(messages: ChatMessage[], pageContext: string | null): string {
  const lines: string[] = [];
  if (pageContext) {
    lines.push(`<page_context>\n${pageContext}\n</page_context>`);
    lines.push("");
  }
  // Show prior turns explicitly so Claude has the threading.
  for (let i = 0; i < messages.length - 1; i++) {
    const m = messages[i];
    lines.push(`<${m.role}>\n${m.content}\n</${m.role}>`);
    lines.push("");
  }
  // Final user turn is what Claude is replying to.
  const last = messages[messages.length - 1];
  if (last && last.role === "user") {
    lines.push(last.content);
  }
  return lines.join("\n").trim();
}

export async function POST(req: NextRequest) {
  const guard = await apiAuthGuard();
  if (guard instanceof Response) return guard;

  let body: Body;
  try {
    body = await req.json();
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }

  if (!Array.isArray(body.messages) || body.messages.length === 0) {
    return new Response("Missing messages", { status: 400 });
  }
  const last = body.messages[body.messages.length - 1];
  if (!last || last.role !== "user" || !last.content?.trim()) {
    return new Response("Last message must be a non-empty user message", { status: 400 });
  }

  const pageContext = body.pathname ? await resolvePageContext(body.pathname) : null;
  const userPrompt = formatHistoryAsPrompt(body.messages, pageContext);

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder();
      try {
        for await (const delta of claudeStream({
          systemPrompt: ASSISTANT_SYSTEM_PROMPT,
          prompt: userPrompt,
          model: "sonnet",
          tools: "WebSearch,WebFetch",
        })) {
          controller.enqueue(encoder.encode(delta));
        }
      } catch (err) {
        console.error("[assistant] stream error", err);
        const msg = err instanceof Error ? err.message : String(err);
        controller.enqueue(encoder.encode(`\n\n[error: ${msg}]`));
      } finally {
        controller.close();
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
