"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { TranscriptSidebar, type TranscriptMessage, type ScoreObject } from "@/components/TranscriptSidebar";
import { getWhiteboardJSON } from "@/components/Whiteboard";
import { Button } from "@/components/ui/button";
import { Send, Loader2, Lightbulb, CheckCircle2, ArrowLeft } from "lucide-react";
import Link from "next/link";

// Load whiteboard client-side only (uses browser APIs)
const Whiteboard = dynamic(
  () => import("@/components/Whiteboard").then((m) => ({ default: m.Whiteboard })),
  { ssr: false },
);

type CompanyStyle = "google" | "meta" | "amazon" | "generic";
type HintLevel = 0 | 1 | 2 | 3;

const COMPANY_OPTIONS: { value: CompanyStyle; label: string }[] = [
  { value: "generic", label: "Generic" },
  { value: "google", label: "Google" },
  { value: "meta", label: "Meta" },
  { value: "amazon", label: "Amazon" },
];

const HINT_LABELS: Record<HintLevel, string> = {
  0: "Hint",
  1: "Hint (nudge)",
  2: "Hint (clearer)",
  3: "Hint (near-complete)",
};

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function InterviewSessionPage({ params }: PageProps) {
  const [sessionId, setSessionId] = useState<string>("");

  useEffect(() => {
    params.then(({ id }) => setSessionId(id));
  }, [params]);

  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [score, setScore] = useState<ScoreObject | undefined>(undefined);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isScoring, setIsScoring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [companyStyle, setCompanyStyle] = useState<CompanyStyle>("generic");
  const [hintLevel, setHintLevel] = useState<HintLevel>(0);
  const [sessionEnded, setSessionEnded] = useState(false);

  // Whiteboard state
  const whiteboardElementsRef = useRef<readonly any[]>([]);
  const whiteboardStateRef = useRef<any>(null);

  const abortRef = useRef<AbortController | null>(null);

  const handleWhiteboardChange = useCallback((elements: readonly any[], state: any) => {
    whiteboardElementsRef.current = elements;
    whiteboardStateRef.current = state;
  }, []);

  async function sendMessage(messageText: string, useHint: boolean = false) {
    if (!sessionId || isStreaming || sessionEnded) return;

    setError(null);

    const whiteboardState = getWhiteboardJSON(
      whiteboardElementsRef.current,
      whiteboardStateRef.current,
    );

    // Add candidate message to transcript
    const candidateMsg: TranscriptMessage = {
      role: "candidate",
      content: messageText,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, candidateMsg]);

    // Add empty interviewer placeholder
    const interviewerPlaceholder: TranscriptMessage = {
      role: "interviewer",
      content: "",
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, interviewerPlaceholder]);
    setIsStreaming(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const transcriptForApi = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));
      // Include the candidate message we just added
      transcriptForApi.push({ role: "candidate", content: messageText });

      const res = await fetch(`/api/interview/session/${sessionId}/message`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          message: messageText,
          whiteboardState: whiteboardState !== "[]" ? whiteboardState : undefined,
          transcriptHistory: transcriptForApi.slice(0, -1), // exclude the one we just added
          companyStyle,
          hintLevel: useHint ? hintLevel : 0,
        }),
        signal: ctrl.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`Server error: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        accumulated += chunk;
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy.length - 1;
          if (last >= 0 && copy[last].role === "interviewer") {
            copy[last] = { ...copy[last], content: accumulated };
          }
          return copy;
        });
      }

      if (!accumulated) throw new Error("Empty response from server");
      if (accumulated.includes("[error:")) {
        const match = accumulated.match(/\[error: ([^\]]+)\]/);
        throw new Error(match ? match[1] : "Stream error from server");
      }

      // Reset hint level after use
      if (useHint && hintLevel > 0) {
        setHintLevel(0);
      }

      // Check for end sentinel
      if (accumulated.includes("<<INTERVIEW_END>>")) {
        setSessionEnded(true);
        // Clean the sentinel from the displayed message
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy.length - 1;
          if (last >= 0 && copy[last].role === "interviewer") {
            copy[last] = {
              ...copy[last],
              content: copy[last].content.replace(/<<INTERVIEW_END>>/g, "").trimEnd(),
            };
          }
          return copy;
        });
      }
    } catch (e: unknown) {
      if ((e as { name?: string })?.name !== "AbortError") {
        setError(e instanceof Error ? e.message : "Stream failed");
        // Remove the empty placeholder
        setMessages((prev) => {
          const copy = [...prev];
          if (copy.length > 0 && copy[copy.length - 1].role === "interviewer" && copy[copy.length - 1].content === "") {
            return copy.slice(0, -1);
          }
          return copy;
        });
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isStreaming || sessionEnded) return;
    setInput("");
    void sendMessage(trimmed);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit(e as unknown as React.FormEvent);
    }
  }

  function cycleHint() {
    if (sessionEnded) return;
    setHintLevel((prev) => ((prev + 1) % 4) as HintLevel);
  }

  async function endAndScore() {
    if (isScoring || sessionEnded) return;
    if (!confirm("End this session and get a score? This cannot be undone.")) return;

    setIsScoring(true);
    setError(null);
    setSessionEnded(true);

    try {
      const transcriptForApi = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res = await fetch(`/api/interview/session/${sessionId}/score`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ transcriptHistory: transcriptForApi }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Scoring failed: ${res.status}`);
      }

      const scoreData: ScoreObject = await res.json();
      setScore(scoreData);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Scoring failed");
    } finally {
      setIsScoring(false);
    }
  }

  if (!sessionId) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* Top bar */}
      <header className="shrink-0 border-b px-4 py-2 flex items-center gap-3 bg-background">
        <Link href="/interview" className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
          <ArrowLeft className="h-4 w-4" /> Back
        </Link>
        <span className="text-sm font-semibold flex-1">Interview Session #{sessionId}</span>

        {/* Company style */}
        <select
          value={companyStyle}
          onChange={(e) => setCompanyStyle(e.target.value as CompanyStyle)}
          disabled={isStreaming || sessionEnded}
          className="text-xs border rounded px-2 py-1 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
        >
          {COMPANY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        {/* Hint toggle */}
        <Button
          type="button"
          variant={hintLevel > 0 ? "default" : "outline"}
          size="sm"
          onClick={cycleHint}
          disabled={isStreaming || sessionEnded}
          title="Cycle hint level (0→1→2→3)"
        >
          <Lightbulb className="h-3.5 w-3.5" />
          {HINT_LABELS[hintLevel]}
        </Button>

        {/* End & Score */}
        <Button
          type="button"
          variant="destructive"
          size="sm"
          onClick={endAndScore}
          disabled={isScoring || sessionEnded || messages.length < 2}
        >
          {isScoring ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
          {isScoring ? "Scoring..." : sessionEnded ? "Session Ended" : "End & Score"}
        </Button>
      </header>

      {/* Main two-column area */}
      <div className="flex flex-1 min-h-0">
        {/* Whiteboard — 60% */}
        <div className="w-3/5 flex flex-col min-h-0 border-r">
          <div className="flex-1 min-h-0">
            <Whiteboard onChange={handleWhiteboardChange} />
          </div>

          {/* Input at bottom of whiteboard column */}
          <div className="shrink-0 border-t p-3 bg-background">
            {error && (
              <div className="mb-2 px-3 py-1.5 text-xs text-destructive bg-destructive/5 border border-destructive/20 rounded-md flex items-center gap-2">
                <span className="flex-1">{error}</span>
                <button type="button" onClick={() => setError(null)} className="underline shrink-0">Dismiss</button>
              </div>
            )}
            <form onSubmit={onSubmit} className="flex flex-col gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={
                  sessionEnded
                    ? "Session has ended."
                    : "Type your answer. Shift+Enter for newline. Use ```mermaid for diagrams."
                }
                rows={3}
                disabled={isStreaming || sessionEnded}
                className="w-full resize-none rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 font-mono"
              />
              <div className="flex items-center gap-2 justify-end">
                {hintLevel > 0 && !sessionEnded && (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      void sendMessage("[Requesting a hint]", true);
                    }}
                    disabled={isStreaming || sessionEnded}
                  >
                    <Lightbulb className="h-3.5 w-3.5" /> Request hint
                  </Button>
                )}
                <Button
                  type="submit"
                  size="sm"
                  disabled={isStreaming || sessionEnded || !input.trim()}
                >
                  {isStreaming ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                  {isStreaming ? "Sending..." : "Send"}
                </Button>
              </div>
            </form>
          </div>
        </div>

        {/* Transcript sidebar — 40% */}
        <div className="w-2/5 min-h-0 flex flex-col">
          <TranscriptSidebar
            messages={messages}
            score={score}
            isStreaming={isStreaming}
          />
        </div>
      </div>
    </div>
  );
}
