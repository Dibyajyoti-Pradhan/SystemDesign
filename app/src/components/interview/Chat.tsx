"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { marked } from "marked";
import { Mermaid } from "@/components/Mermaid";
import { Button } from "@/components/ui/button";
import { Send, Square, CheckCircle2, Loader2 } from "lucide-react";

type Msg = { role: "user" | "assistant"; content: string; ts: number };

type ChatProps = {
  sessionId: number;
  initialMessages: Msg[];
};

// Marked is sync when configured this way; we render to HTML and dangerouslySet.
// Fenced ```mermaid ... ``` blocks are extracted before the markdown pass so
// they render as actual diagrams instead of escaped code.
marked.setOptions({ gfm: true, breaks: false });

type Segment =
  | { kind: "md"; text: string }
  | { kind: "mermaid"; chart: string };

function segmentMessage(content: string): Segment[] {
  const segments: Segment[] = [];
  const re = /```mermaid\n([\s\S]*?)```/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(content)) !== null) {
    if (m.index > last) {
      segments.push({ kind: "md", text: content.slice(last, m.index) });
    }
    segments.push({ kind: "mermaid", chart: m[1].trim() });
    last = m.index + m[0].length;
  }
  if (last < content.length) {
    segments.push({ kind: "md", text: content.slice(last) });
  }
  return segments;
}

function MarkdownBlock({ text }: { text: string }) {
  const html = useMemo(() => marked.parse(text) as string, [text]);
  // `.prose-system` (defined in globals.css) gives us decent default styling
  // for paragraphs, lists, code, and blockquotes without needing the
  // Tailwind Typography plugin.
  return (
    <div
      className="prose-system text-sm"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function MessageBubble({ role, content }: { role: "user" | "assistant"; content: string }) {
  const segments = useMemo(() => segmentMessage(content), [content]);
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={
          isUser
            ? "max-w-[85%] bg-primary text-primary-foreground rounded-lg rounded-br-sm px-4 py-2.5"
            : "max-w-[85%] bg-muted text-foreground rounded-lg rounded-bl-sm px-4 py-2.5"
        }
      >
        {isUser ? (
          <div className="whitespace-pre-wrap text-sm leading-relaxed">{content}</div>
        ) : (
          <div className="text-sm">
            {segments.map((seg, i) =>
              seg.kind === "mermaid" ? (
                <Mermaid key={i} chart={seg.chart} />
              ) : (
                <MarkdownBlock key={i} text={seg.text} />
              ),
            )}
            {content === "" && (
              <span className="inline-flex items-center gap-1.5 text-muted-foreground text-xs">
                <Loader2 className="h-3 w-3 animate-spin" /> thinking...
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function Chat({ sessionId, initialMessages }: ChatProps) {
  const [messages, setMessages] = useState<Msg[]>(initialMessages);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [grading, setGrading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const router = useRouter();

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, streaming]);

  // If the session has no messages yet, kick off a greeting from the interviewer.
  useEffect(() => {
    if (messages.length === 0 && !streaming) {
      void send("__begin__", true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function send(content: string, isAutoBegin = false) {
    setError(null);
    const userMsg: Msg = { role: "user", content, ts: Date.now() };
    const optimistic = isAutoBegin ? messages : [...messages, userMsg];
    if (!isAutoBegin) setMessages(optimistic);
    setMessages((cur) => [...(isAutoBegin ? cur : optimistic), { role: "assistant", content: "", ts: Date.now() }]);
    setStreaming(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const res = await fetch("/api/interview/message", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, content, autoBegin: isAutoBegin }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
        throw new Error(`Server error: ${res.status}`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let assistantText = "";
      // The route streams plain text chunks (no SSE framing) so we just accumulate.
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        assistantText += decoder.decode(value, { stream: true });
        setMessages((cur) => {
          const copy = cur.slice();
          // last entry is the streaming assistant placeholder
          const idx = copy.length - 1;
          if (idx >= 0 && copy[idx].role === "assistant") {
            copy[idx] = { ...copy[idx], content: assistantText };
          }
          return copy;
        });
      }
      if (!assistantText) {
        throw new Error("Empty response from server");
      }
      if (assistantText.includes("[error:")) {
        const match = assistantText.match(/\[error: ([^\]]+)\]/);
        throw new Error(match ? match[1] : "Stream error from server");
      }
    } catch (e: unknown) {
      if ((e as { name?: string })?.name === "AbortError") {
        // user-initiated, fine
      } else {
        setError(e instanceof Error ? e.message : "Stream failed");
        setMessages((cur) => cur.slice(0, -1)); // drop empty assistant bubble
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || streaming) return;
    setInput("");
    void send(trimmed);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit(e as unknown as FormEvent);
    }
  }

  function stopStream() {
    abortRef.current?.abort();
  }

  async function endInterview() {
    if (grading) return;
    if (!confirm("End the interview and generate the rubric? This is irreversible for this session.")) return;
    setGrading(true);
    setError(null);
    try {
      const res = await fetch("/api/interview/grade", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Grading failed: ${res.status}`);
      }
      router.refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Grading failed");
    } finally {
      setGrading(false);
    }
  }

  return (
    <div className="flex flex-col border rounded-lg bg-card overflow-hidden" style={{ height: "calc(100vh - 240px)", minHeight: "500px" }}>
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-sm text-muted-foreground py-12">
            Starting the interview...
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} role={m.role} content={m.content} />
        ))}
      </div>

      {error && (
        <div className="px-4 py-2 flex items-center gap-3 text-xs text-destructive bg-destructive/5 border-t border-destructive/20">
          <span className="flex-1">{error}</span>
          <button
            type="button"
            className="underline shrink-0"
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      <form onSubmit={onSubmit} className="border-t p-3 space-y-2 bg-muted/20">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Type your answer. Shift+Enter for newline. Use ```mermaid for diagrams."
          rows={3}
          disabled={streaming || grading}
          className="w-full resize-none rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 font-mono"
        />
        <div className="flex items-center justify-between gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={endInterview}
            disabled={streaming || grading || messages.length < 2}
          >
            {grading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            {grading ? "Grading..." : "End & grade"}
          </Button>
          <div className="flex items-center gap-2">
            {streaming && (
              <Button type="button" variant="ghost" size="sm" onClick={stopStream}>
                <Square className="h-4 w-4" /> Stop
              </Button>
            )}
            <Button type="submit" size="sm" disabled={streaming || grading || !input.trim()}>
              <Send className="h-4 w-4" /> Send
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
