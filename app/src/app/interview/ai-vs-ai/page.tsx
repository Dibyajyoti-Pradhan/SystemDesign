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

  const VSAI_CSS = `
.vsai { height:100%; display:grid; grid-template-rows: auto 1fr auto; background: var(--bg); }
.vs__meta { display:flex; align-items: center; gap: 14px; padding: 14px 36px 12px; border-bottom: 1px solid var(--line); }
.vs__title { font-size: 16px; font-weight: 600; letter-spacing: -0.012em; }
.vs__title small { color: var(--mute); font-weight: 400; margin-left: 8px; }
.vs__feed { overflow:auto; padding: 24px 36px 28px; }
.vs__lane { max-width: 920px; margin: 0 auto; display:flex; flex-direction: column; gap: 22px; }
.vs-turn { display:grid; grid-template-columns: 92px 1fr; gap: 18px; }
.vs-turn .gut { display:flex; flex-direction: column; align-items: flex-end; padding-top: 4px; gap: 4px; }
.vs-turn .who { font-family: var(--font-mono); font-size: 10.5px; text-transform: uppercase; letter-spacing: .1em; }
.vs-turn .num { font-family: var(--font-mono); font-size: 10px; color: var(--mute-2); }
.vs-turn.t-i .who { color: var(--accent); }
.vs-turn.t-c .who { color: var(--info); }
.vs-turn .body { font-size: 14.5px; line-height: 1.6; color: var(--ink-2); padding: 10px 14px; border-radius: 8px; background: var(--surf); border:1px solid var(--line); max-width: 70ch; position: relative; }
.vs-turn.t-i .body { background: var(--bg-2); border-color: var(--line); }
.vs-turn.t-i .body::before { content:""; position:absolute; left:-1px; top:14px; bottom:14px; width:2px; background: var(--accent); border-radius: 2px; }
.vs-turn.t-c .body::before { content:""; position:absolute; left:-1px; top:14px; bottom:14px; width:2px; background: var(--info); border-radius: 2px; }
.vs-bar { border-top: 1px solid var(--line); background: var(--bg-2); padding: 12px 36px; display:grid; grid-template-columns: auto 1fr auto; gap: 18px; align-items: center; }
.vs-bar .comp { background: var(--surf); border: 1px solid var(--line-2); border-radius: 8px; padding: 8px 10px 8px 12px; display:flex; align-items:center; gap: 12px; font-size: 13.5px; color: var(--ink-2); }
.vs-bar .comp__seg { display:flex; gap:1px; padding: 2px; border:1px solid var(--line); border-radius: 6px; background: var(--bg); }
.vs-bar .comp__seg span { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); padding: 4px 9px; border-radius: 4px; cursor:pointer; text-transform: uppercase; letter-spacing: .05em; }
.vs-bar .comp__seg span.is-on { background: var(--surf-2); color: var(--ink); }
.stave { display:flex; align-items: center; gap: 10px; margin-left: auto; }
.stave__lbl { font-family: var(--font-mono); font-size: 10px; color: var(--mute); text-transform: uppercase; letter-spacing: .1em; }
.stave__tick { width: 6px; height: 14px; background: var(--surf-3); border-radius: 1px; }
.stave__tick.is-done { background: var(--ink-2); }
.stave__tick.is-now { background: var(--accent); }
.vs-select { background: var(--surf); border: 1px solid var(--line); border-radius: 6px; padding: 5px 8px; font-size: 12px; color: var(--ink); font-family: var(--font-mono); cursor: pointer; }
.vs-select:focus { outline: none; border-color: var(--line-2); }
`;

  // Build turn list including streaming
  const allTurns = [
    ...messages.filter((m) => m.role !== "steer"),
    ...(streamingRole ? [{ role: streamingRole, content: streamingText, ts: Date.now() }] : []),
  ] as AiMsg[];

  return (
    <div className="vsai">
      <style>{VSAI_CSS}</style>

      {/* Header / meta */}
      <div className="vs__meta">
        <span className="vs__title">
          AI vs AI
          <small>Interview Simulator</small>
        </span>

        {!sessionStarted && (
          <>
            <select
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="vs-select"
            >
              {TOPICS.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>

            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as Difficulty)}
              className="vs-select"
            >
              {DIFFICULTIES.map((d) => (
                <option key={d} value={d} style={{ textTransform: "capitalize" }}>{d}</option>
              ))}
            </select>

            <button className="btn btn--primary" onClick={startSession} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Play size={13} /> Start Session
            </button>
          </>
        )}

        {sessionStarted && (
          <>
            {ended ? (
              <span className="badge">ended</span>
            ) : paused ? (
              <span className="badge">paused</span>
            ) : running ? (
              <span className="badge badge--accent" style={{ display: "flex", alignItems: "center", gap: 5 }}>
                {streamingRole === "interviewer" ? <Bot size={11} /> : <User size={11} />}
                {streamingRole ?? "…"} thinking
              </span>
            ) : (
              <span className="badge" style={{ display: "flex", alignItems: "center", gap: 5 }}>
                {agentUp === "interviewer" ? <Bot size={11} /> : <User size={11} />}
                {agentUp} up
              </span>
            )}

            {/* Auto speed segmented control */}
            <div className="comp__seg" style={{ display: "flex", gap: 1, padding: 2, border: "1px solid var(--line)", borderRadius: 6, background: "var(--bg)" }}>
              {[1000, 3000, 5000].map((ms) => (
                <span
                  key={ms}
                  className={autoInterval === ms ? "is-on" : ""}
                  onClick={() => setAutoInterval(ms)}
                  style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, color: autoInterval === ms ? "var(--ink)" : "var(--mute)", padding: "4px 9px", borderRadius: 4, cursor: "pointer", background: autoInterval === ms ? "var(--surf-2)" : "transparent", textTransform: "uppercase", letterSpacing: ".05em" }}
                >
                  {ms / 1000}s
                </span>
              ))}
            </div>

            {/* Turn stave */}
            <div className="stave">
              <span className="stave__lbl">turns</span>
              {Array.from({ length: 10 }).map((_, i) => (
                <div
                  key={i}
                  className={`stave__tick${i < allTurns.length - (running ? 1 : 0) ? " is-done" : running && i === allTurns.length - 1 ? " is-now" : ""}`}
                />
              ))}
            </div>

            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
              {paused && !ended ? (
                <button className="btn btn--primary" onClick={() => setPaused(false)} disabled={running || !sessionId} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Play size={13} /> Resume
                </button>
              ) : !ended ? (
                <button className="btn btn--ghost" onClick={() => setPaused(true)} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Pause size={13} /> Pause
                </button>
              ) : null}

              <button
                className="btn btn--ghost"
                onClick={() => { if (!running && !ended && sessionId) void step(); }}
                disabled={running || ended || !sessionId}
                style={{ display: "flex", alignItems: "center", gap: 6 }}
              >
                <StepForward size={13} /> Step
              </button>

              {running && (
                <button className="btn btn--ghost" onClick={stop} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Square size={13} /> Stop
                </button>
              )}
            </div>
          </>
        )}
      </div>

      {/* Transcript feed */}
      <div className="vs__feed">
        <div className="vs__lane">
          {!sessionStarted && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, color: "var(--mute)", fontSize: 14 }}>
              Configure topic and start a session to begin.
            </div>
          )}
          {allTurns.map((msg, i) => (
            <div key={i} className={`vs-turn ${msg.role === "interviewer" ? "t-i" : "t-c"}`}>
              <div className="gut">
                <span className="who">{msg.role === "interviewer" ? "Interviewer" : "Candidate"}</span>
                <span className="num">#{i + 1}</span>
              </div>
              <div className="body">{msg.content}</div>
            </div>
          ))}
          {error && (
            <div style={{ padding: "10px 14px", borderRadius: 8, background: "rgba(var(--bad-rgb, 239,68,68), 0.08)", border: "1px solid var(--bad)", color: "var(--bad)", fontSize: 13 }}>
              {error}
              <button type="button" onClick={() => setError(null)} style={{ marginLeft: 10, textDecoration: "underline", background: "none", border: 0, color: "inherit", cursor: "pointer" }}>Dismiss</button>
            </div>
          )}
        </div>
      </div>

      {/* Bottom bar */}
      <div className="vs-bar">
        <div className="comp">
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute)", textTransform: "uppercase", letterSpacing: ".08em" }}>
            {sessionId ? `Session #${sessionId}` : "No session"}
          </span>
        </div>
        <div />
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {sessionStarted && !ended && (
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute)", textTransform: "uppercase" }}>
              {allTurns.length} turns
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
