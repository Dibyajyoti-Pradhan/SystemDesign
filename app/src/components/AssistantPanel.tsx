"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { marked } from "marked";
import { Bot, Send, X, Trash2, Sparkles, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Mermaid } from "@/components/Mermaid";
import { cn } from "@/lib/utils";

type ChatMessage = { role: "user" | "assistant"; content: string };

const STORAGE_KEY = "study-assistant-v1";
const OPEN_KEY = "study-assistant-open-v1";

function MarkdownWithMermaid({ text }: { text: string }) {
  const segments = useMemo(() => {
    const parts: Array<{ kind: "md"; text: string } | { kind: "mermaid"; code: string }> = [];
    const re = /```mermaid\n([\s\S]*?)```/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) parts.push({ kind: "md", text: text.slice(last, m.index) });
      parts.push({ kind: "mermaid", code: m[1] });
      last = re.lastIndex;
    }
    if (last < text.length) parts.push({ kind: "md", text: text.slice(last) });
    return parts;
  }, [text]);

  return (
    <>
      {segments.map((seg, i) =>
        seg.kind === "mermaid" ? (
          <Mermaid key={i} chart={seg.code} />
        ) : (
          <div
            key={i}
            className="prose-system text-sm"
            dangerouslySetInnerHTML={{ __html: marked.parse(seg.text, { async: false }) as string }}
          />
        ),
      )}
    </>
  );
}

function pageLabel(pathname: string): string {
  if (pathname === "/") return "Home";
  // /[track]/... pages
  const trackMatch = pathname.match(/^\/(system-design|coding)(\/.*)?$/);
  if (trackMatch) {
    const trackLabel = trackMatch[1] === "coding" ? "Coding" : "System Design";
    const sub = trackMatch[2] ?? "";
    if (sub.startsWith("/topics/")) return `${trackLabel} · Topic`;
    if (sub === "/topics") return `${trackLabel} · Topics`;
    if (sub.startsWith("/questions/")) return `${trackLabel} · Question`;
    if (sub === "/questions") return `${trackLabel} · Questions`;
    if (sub.startsWith("/cheatsheets/")) return `${trackLabel} · Cheatsheet`;
    if (sub === "/cheatsheets") return `${trackLabel} · Cheatsheets`;
    if (sub.startsWith("/review")) return `${trackLabel} · Review`;
    return trackLabel;
  }
  if (pathname.startsWith("/interview/sessions/")) return "Session";
  if (pathname.startsWith("/admin/cards")) return "Card review queue";
  if (pathname.startsWith("/concept-map")) return "Concept map";
  if (pathname.startsWith("/notes")) return "Notes";
  if (pathname.startsWith("/search")) return "Search";
  return pathname;
}

export function AssistantPanel() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const pathname = usePathname();
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Hydrate from localStorage
  useEffect(() => {
    try {
      const m = localStorage.getItem(STORAGE_KEY);
      if (m) setMessages(JSON.parse(m));
      const o = localStorage.getItem(OPEN_KEY);
      if (o === "1") setOpen(true);
    } catch {}
  }, []);

  // Persist
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch {}
  }, [messages]);
  useEffect(() => {
    try {
      localStorage.setItem(OPEN_KEY, open ? "1" : "0");
    } catch {}
  }, [open]);

  // Auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streaming]);

  // Focus on open
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const send = async () => {
    const trimmed = input.trim();
    if (!trimmed || streaming) return;

    const next: ChatMessage[] = [...messages, { role: "user", content: trimmed }, { role: "assistant", content: "" }];
    setMessages(next);
    setInput("");
    setStreaming(true);

    const ctl = new AbortController();
    abortRef.current = ctl;

    try {
      const res = await fetch("/api/assistant/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          messages: next.slice(0, -1), // drop the empty placeholder we just added
          pathname,
        }),
        signal: ctl.signal,
      });
      if (!res.ok || !res.body) throw new Error(`assistant failed: ${res.status} ${await res.text()}`);

      const reader = res.body.getReader();
      const dec = new TextDecoder();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = dec.decode(value, { stream: true });
        setMessages((cur) => {
          const out = [...cur];
          const last = out[out.length - 1];
          if (last?.role === "assistant") {
            out[out.length - 1] = { role: "assistant", content: last.content + chunk };
          }
          return out;
        });
      }
    } catch (e: any) {
      if (e?.name !== "AbortError") {
        setMessages((cur) => {
          const out = [...cur];
          const last = out[out.length - 1];
          if (last?.role === "assistant") {
            out[out.length - 1] = { role: "assistant", content: (last.content || "") + `\n\n[error: ${e?.message ?? String(e)}]` };
          }
          return out;
        });
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const stop = () => abortRef.current?.abort();
  const clear = () => {
    if (streaming) stop();
    setMessages([]);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed right-4 bottom-4 z-30 h-12 px-4 rounded-full shadow-lg bg-primary text-primary-foreground flex items-center gap-2 hover:opacity-90 transition-opacity"
          title="Open study assistant"
        >
          <Sparkles className="h-4 w-4" />
          <span className="text-sm font-medium">Ask</span>
        </button>
      )}

      {open && (
        <aside
          className={cn(
            "fixed right-0 top-0 h-screen w-[420px] max-w-[92vw] bg-background border-l shadow-2xl z-40 flex flex-col",
          )}
          aria-label="Study assistant"
        >
          <header className="flex items-center justify-between gap-2 p-3 border-b">
            <div className="flex items-center gap-2 min-w-0">
              <Bot className="h-4 w-4 shrink-0" />
              <div className="min-w-0">
                <div className="text-sm font-semibold truncate">Study Assistant</div>
                <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <Badge variant="outline" className="text-[10px]">{pageLabel(pathname)}</Badge>
                  <Badge variant="muted" className="text-[10px] gap-1"><Globe className="h-2.5 w-2.5" />web</Badge>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" onClick={clear} title="Clear chat">
                <Trash2 className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" onClick={() => setOpen(false)} title="Close">
                <X className="h-4 w-4" />
              </Button>
            </div>
          </header>

          <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3">
            {messages.length === 0 && (
              <div className="text-sm text-muted-foreground space-y-3">
                <p>Ask anything system-design. I know what page you&apos;re on, can search the web, and give concrete answers with diagrams when useful.</p>
                <div className="space-y-1.5">
                  <div className="text-xs font-medium text-foreground">Try:</div>
                  {[
                    "Why pick consistent hashing over modulo?",
                    "Show me a Mermaid for read-through caching",
                    "What's the latest on FoundationDB?",
                    "Compare Cassandra vs DynamoDB write paths",
                  ].map((q) => (
                    <button
                      key={q}
                      onClick={() => setInput(q)}
                      className="block text-left text-xs text-primary hover:underline"
                    >
                      → {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={cn("flex flex-col gap-1", m.role === "user" && "items-end")}>
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  {m.role === "user" ? "You" : "Assistant"}
                </div>
                <div
                  className={cn(
                    "rounded-lg px-3 py-2 max-w-full",
                    m.role === "user"
                      ? "bg-primary text-primary-foreground text-sm whitespace-pre-wrap"
                      : "bg-muted/50 border",
                  )}
                >
                  {m.role === "assistant" ? (
                    m.content ? (
                      <MarkdownWithMermaid text={m.content} />
                    ) : streaming ? (
                      <span className="text-muted-foreground text-xs animate-pulse">thinking…</span>
                    ) : null
                  ) : (
                    m.content
                  )}
                </div>
              </div>
            ))}
          </div>

          <footer className="border-t p-3 space-y-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Ask about this page, or any system-design topic…"
              rows={2}
              className="w-full p-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring resize-none"
              disabled={streaming}
            />
            <div className="flex items-center gap-2 justify-between">
              <span className="text-[10px] text-muted-foreground">Enter to send · Shift+Enter for newline</span>
              {streaming ? (
                <Button size="sm" variant="outline" onClick={stop}>
                  Stop
                </Button>
              ) : (
                <Button size="sm" onClick={send} disabled={!input.trim()}>
                  <Send className="h-3 w-3" /> Send
                </Button>
              )}
            </div>
          </footer>
        </aside>
      )}
    </>
  );
}
