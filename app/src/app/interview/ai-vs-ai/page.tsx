"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { TranscriptSidebar, type TranscriptMessage } from "@/components/TranscriptSidebar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Play, Pause, StepForward, Square, Bot, User } from "lucide-react";

// Load whiteboard client-side only
const Whiteboard = dynamic(
  () => import("@/components/Whiteboard").then((m) => ({ default: m.Whiteboard })),
  { ssr: false },
);

type AgentRole = "interviewer" | "candidate";
type SteerTarget = "interviewer" | "candidate" | "both";

interface AiMsg {
  role: AgentRole | "steer";
  content: string;
  target?: SteerTarget;
  consumed?: boolean;
  ts: number;
}

const TOPICS = [
  { value: "design-url-shortener", label: "URL Shortener" },
  { value: "design-twitter-feed", label: "Twitter/X Feed" },
  { value: "design-rate-limiter", label: "Rate Limiter" },
  { value: "design-distributed-cache", label: "Distributed Cache" },
  { value: "design-notification-service", label: "Notification Service" },
];

const DIFFICULTIES = ["easy", "medium", "hard"] as const;
type Difficulty = (typeof DIFFICULTIES)[number];

function msgToTranscript(msg: AiMsg): TranscriptMessage | null {
  if (msg.role === "steer") return null;
  return {
    role: msg.role === "interviewer" ? "interviewer" : "candidate",
    content: msg.content,
    timestamp: new Date(msg.ts),
  };
}

function nextAgent(msgs: AiMsg[]): AgentRole {
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === "interviewer") return "candidate";
    if (msgs[i].role === "candidate") return "interviewer";
  }
  return "interviewer";
}

export default function AiVsAiPage() {
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<AiMsg[]>([]);
  const [streamingRole, setStreamingRole] = useState<AgentRole | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [running, setRunning] = useState(false);
  const [paused, setPaused] = useState(true);
  const [ended, setEnded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoInterval, setAutoInterval] = useState(3000);
  const [topic, setTopic] = useState(TOPICS[0].value);
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [sessionStarted, setSessionStarted] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const autoTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Convert messages to TranscriptSidebar format
  const transcriptMessages: TranscriptMessage[] = messages
    .map(msgToTranscript)
    .filter((m): m is TranscriptMessage => m !== null);

  // Determine next agent
  const agentUp = nextAgent(messages.filter((m) => m.role !== "steer") as AiMsg[]);

  // Auto-step when not paused
  useEffect(() => {
    if (paused || running || ended || !sessionId) return;
    const id = setTimeout(() => {
      void step();
    }, autoInterval);
    autoTimerRef.current = id;
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paused, running, ended, sessionId, messages.length]);

  async function startSession() {
    setError(null);
    setSessionStarted(true);
    setMessages([]);
    setEnded(false);
    setPaused(false);

    // Create session via API — for standalone page we use a synthetic question
    // by calling the existing start route pattern or creating a custom one.
    // For simplicity, look up the question by slug and start a session.
    try {
      const res = await fetch("/api/interview/ai-vs-ai/start-standalone", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ topic, difficulty }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || `Failed to start session: ${res.status}`);
      }
      const data: { sessionId: number } = await res.json();
      setSessionId(data.sessionId);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setSessionStarted(false);
      setPaused(true);
    }
  }

  const step = useCallback(async () => {
    if (!sessionId || running || ended) return;
    setRunning(true);
    setError(null);

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    let accumulated = "";
    let role: AgentRole = agentUp;

    try {
      const res = await fetch("/api/interview/ai-vs-ai/step", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId }),
        signal: ctrl.signal,
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`step failed (${res.status}): ${text}`);
      }

      const headerRole = res.headers.get("x-agent-role");
      if (headerRole === "interviewer" || headerRole === "candidate") role = headerRole;
      const forcedWrap = res.headers.get("x-force-wrap") === "1";

      setStreamingRole(role);
      setStreamingText("");

      if (!res.body) throw new Error("Empty response");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        accumulated += chunk;
        setStreamingText((prev) => prev + chunk);
      }

      if (!accumulated) throw new Error("Empty response");
      if (accumulated.includes("[error:")) {
        const match = accumulated.match(/\[error: ([^\]]+)\]/);
        throw new Error(match ? match[1] : "upstream error");
      }

      setMessages((prev) => [
        ...prev,
        { role, content: accumulated, ts: Date.now() },
      ]);

      if (accumulated.includes("<<INTERVIEW_END>>") || forcedWrap) {
        setPaused(true);
        setEnded(true);
      }
    } catch (e: any) {
      if (e?.name !== "AbortError") {
        setError(e?.message ?? String(e));
        setPaused(true);
      }
    } finally {
      setStreamingRole(null);
      setStreamingText("");
      setRunning(false);
      abortRef.current = null;
    }
  }, [sessionId, running, ended, agentUp]);

  function stop() {
    abortRef.current?.abort();
    setPaused(true);
    setRunning(false);
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* Header */}
      <header className="shrink-0 border-b px-4 py-2 flex items-center gap-3 bg-background flex-wrap">
        <span className="text-sm font-semibold">AI vs AI Interview</span>

        {!sessionStarted && (
          <>
            <select
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="text-xs border rounded px-2 py-1 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {TOPICS.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>

            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as Difficulty)}
              className="text-xs border rounded px-2 py-1 bg-background focus:outline-none focus:ring-1 focus:ring-ring capitalize"
            >
              {DIFFICULTIES.map((d) => (
                <option key={d} value={d} className="capitalize">{d}</option>
              ))}
            </select>

            <Button size="sm" onClick={startSession}>
              <Play className="h-3.5 w-3.5" /> Start Session
            </Button>
          </>
        )}

        {sessionStarted && (
          <>
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              {ended ? (
                <Badge variant="outline">ended</Badge>
              ) : paused ? (
                <Badge variant="outline">paused</Badge>
              ) : running ? (
                <Badge className="gap-1">
                  {streamingRole === "interviewer" ? <Bot className="h-3 w-3" /> : <User className="h-3 w-3" />}
                  {streamingRole ?? "…"} thinking
                </Badge>
              ) : (
                <Badge variant="outline" className="gap-1">
                  {agentUp === "interviewer" ? <Bot className="h-3 w-3" /> : <User className="h-3 w-3" />}
                  {agentUp} up
                </Badge>
              )}
            </div>

            {/* Auto speed */}
            <div className="flex items-center gap-1 text-xs">
              <span className="text-muted-foreground">Auto:</span>
              {[1000, 3000, 5000].map((ms) => (
                <button
                  key={ms}
                  type="button"
                  onClick={() => setAutoInterval(ms)}
                  className={`px-2 py-0.5 rounded border text-xs ${
                    autoInterval === ms ? "bg-primary text-primary-foreground border-primary" : "border-border"
                  }`}
                >
                  {ms / 1000}s
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2 ml-auto">
              {paused && !ended ? (
                <Button size="sm" onClick={() => setPaused(false)} disabled={running || !sessionId}>
                  <Play className="h-3.5 w-3.5" /> Resume
                </Button>
              ) : !ended ? (
                <Button size="sm" variant="outline" onClick={() => setPaused(true)}>
                  <Pause className="h-3.5 w-3.5" /> Pause
                </Button>
              ) : null}

              <Button
                size="sm"
                variant="outline"
                onClick={() => { if (!running && !ended && sessionId) void step(); }}
                disabled={running || ended || !sessionId}
              >
                <StepForward className="h-3.5 w-3.5" /> Step
              </Button>

              {running && (
                <Button size="sm" variant="ghost" onClick={stop}>
                  <Square className="h-3.5 w-3.5" /> Stop
                </Button>
              )}
            </div>
          </>
        )}
      </header>

      {/* Main area */}
      <div className="flex flex-1 min-h-0">
        {/* Whiteboard (read-only for AI candidate's drawings) — 60% */}
        <div className="w-3/5 min-h-0 border-r">
          {sessionStarted ? (
            <Whiteboard readOnly={true} />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Configure topic and start a session to begin.
            </div>
          )}
        </div>

        {/* Transcript sidebar — 40% */}
        <div className="w-2/5 min-h-0 flex flex-col">
          <TranscriptSidebar
            messages={[
              ...transcriptMessages,
              ...(streamingRole
                ? [
                    {
                      role: streamingRole,
                      content: streamingText,
                      timestamp: new Date(),
                    } as TranscriptMessage,
                  ]
                : []),
            ]}
            isStreaming={running}
          />
          {error && (
            <div className="shrink-0 px-4 py-2 text-xs text-destructive bg-destructive/5 border-t border-destructive/20">
              {error}
              <button type="button" onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
