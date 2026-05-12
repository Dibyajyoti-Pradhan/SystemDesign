"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { Play, Pause, StepForward, X, Loader2, Bot } from "lucide-react";
import {
  type WhiteboardHandle,
  type WhiteboardElements,
  type WhiteboardAppState,
} from "@/components/Whiteboard";
import { type WhiteboardElement } from "@/components/WhiteboardCanvas";

const Whiteboard = dynamic(
  () => import("@/components/Whiteboard").then((m) => ({ default: m.Whiteboard })),
  { ssr: false },
);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Msg {
  role: "interviewer" | "candidate";
  content: string;
  ts: number;
}

interface CursorPos {
  x: number;
  y: number;
  visible: boolean;
}

interface Props {
  sessionId: number;
  questionTitle: string;
  initialTranscript: Msg[];
  initialEnded: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Strip ```mermaid ... ``` blocks — diagrams go on the whiteboard, not transcript
function stripMermaid(text: string): string {
  return text.replace(/```mermaid[\s\S]*?```/gi, "").replace(/\n{3,}/g, "\n\n").trim();
}

function speakTurn(
  text: string,
  role: "interviewer" | "candidate",
  onEnd: () => void,
) {
  if (typeof window === "undefined" || !window.speechSynthesis) { onEnd(); return; }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = role === "interviewer" ? 0.93 : 0.97;
  u.pitch = role === "interviewer" ? 1.0 : 0.93;
  const voices = window.speechSynthesis.getVoices();
  if (role === "interviewer") {
    const v =
      voices.find((v) => v.lang === "en-GB" && v.name.includes("Neural")) ??
      voices.find((v) => v.lang === "en-GB") ??
      voices.find((v) => v.lang.startsWith("en"));
    if (v) u.voice = v;
  } else {
    const v =
      voices.find((v) => v.lang === "en-US" && v.name.includes("Neural")) ??
      voices.find((v) => v.lang === "en-US") ??
      voices.find((v) => v.lang.startsWith("en"));
    if (v) u.voice = v;
  }
  u.onend = onEnd;
  u.onerror = onEnd;
  window.speechSynthesis.speak(u);
}

// Arch terms we recognise and label on the whiteboard
const ARCH_TERMS: [string, string][] = [
  ["load balancer", "Load Balancer"], ["api gateway", "API Gateway"],
  ["cdn", "CDN"], ["cache", "Cache"], ["redis", "Redis"],
  ["database", "Database"], ["postgres", "Postgres"], ["mysql", "MySQL"],
  ["cassandra", "Cassandra"], ["dynamodb", "DynamoDB"],
  ["message queue", "Message Queue"], ["kafka", "Kafka"], ["sqs", "SQS"],
  ["pubsub", "Pub/Sub"], ["worker", "Workers"], ["app tier", "App Tier"],
  ["app server", "App Server"], ["service", "Service"],
  ["storage", "Object Storage"], ["s3", "S3"], ["blob", "Blob Store"],
  ["search", "Search"], ["elasticsearch", "Elasticsearch"],
  ["rate limit", "Rate Limiter"], ["auth", "Auth Service"],
  ["replica", "Replica"], ["shard", "Sharding"], ["index", "Index"],
];

// Layout: place boxes in a loose grid. Returns (x,y) for slot n.
function slotPosition(n: number, cols = 4): { x: number; y: number } {
  const col = n % cols;
  const row = Math.floor(n / cols);
  return { x: 60 + col * 210, y: 60 + row * 90 };
}

function extractDrawingElements(
  text: string,
  role: "interviewer" | "candidate",
  usedLabels: Set<string>,
  nextSlot: number,
): { elements: WhiteboardElement[]; newSlot: number; targetPos: { x: number; y: number } | null } {
  const lower = text.toLowerCase();
  const toAdd: string[] = [];
  for (const [keyword, label] of ARCH_TERMS) {
    if (lower.includes(keyword) && !usedLabels.has(label)) {
      toAdd.push(label);
      if (toAdd.length >= 3) break;
    }
  }

  if (toAdd.length === 0) return { elements: [], newSlot: nextSlot, targetPos: null };

  const color = role === "interviewer" ? "#D4A574" : "#7DA7C9";
  const elements: WhiteboardElement[] = [];
  let firstPos: { x: number; y: number } | null = null;

  toAdd.forEach((label, i) => {
    usedLabels.add(label);
    const { x, y } = slotPosition(nextSlot + i);
    if (i === 0) firstPos = { x, y };

    elements.push({
      id: `ai-r-${Date.now()}-${i}`,
      type: "rect",
      x, y,
      width: 160, height: 52,
      color,
      fill: "transparent",
      strokeWidth: 1.5,
    } as WhiteboardElement);

    elements.push({
      id: `ai-t-${Date.now()}-${i}`,
      type: "text",
      x: x + 12, y: y + 18,
      color,
      strokeWidth: 1,
      text: label,
      fontSize: 13,
    } as WhiteboardElement);
  });

  return { elements, newSlot: nextSlot + toAdd.length, targetPos: firstPos };
}

// ---------------------------------------------------------------------------
// Cursor animation — smooth random walk, optionally target a specific point
// ---------------------------------------------------------------------------

function animateCursor(
  setPos: (p: CursorPos) => void,
  stopRef: { current: boolean },
  bounds: { w: number; h: number },
  target?: { x: number; y: number },
) {
  let cx = bounds.w * (0.3 + Math.random() * 0.3);
  let cy = bounds.h * (0.2 + Math.random() * 0.3);
  let tx = target?.x ?? cx;
  let ty = target?.y ?? cy;
  let lastPick = 0;
  let phase: "goto" | "wander" = target ? "goto" : "wander";
  let rafId = 0;

  function tick(now: number) {
    if (stopRef.current) {
      setPos({ x: cx, y: cy, visible: false });
      return;
    }

    if (phase === "goto") {
      // Ease toward the target element, then switch to wandering nearby
      cx += (tx - cx) * 0.1;
      cy += (ty - cy) * 0.1;
      if (Math.hypot(tx - cx, ty - cy) < 5) phase = "wander";
    } else {
      // Pick new random target within canvas periodically
      if (now - lastPick > 800 + Math.random() * 1000) {
        tx = Math.max(40, Math.min(bounds.w - 40, tx + (Math.random() - 0.5) * 300));
        ty = Math.max(40, Math.min(bounds.h - 40, ty + (Math.random() - 0.5) * 200));
        lastPick = now;
      }
      cx += (tx - cx) * 0.07;
      cy += (ty - cy) * 0.07;
    }

    setPos({ x: cx, y: cy, visible: true });
    rafId = requestAnimationFrame(tick);
  }
  rafId = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(rafId);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const CURSOR_IV = "#D4A574";
const CURSOR_CX = "#7DA7C9";
const CURSOR_HU = "#7FB48A";

export function VoiceAiVsAiSession({
  sessionId,
  questionTitle,
  initialTranscript,
  initialEnded,
}: Props) {
  const router = useRouter();
  const whiteboardRef = useRef<WhiteboardHandle>(null);
  const whiteboardContainerRef = useRef<HTMLDivElement>(null);

  const [transcript, setTranscript] = useState<Msg[]>(initialTranscript);
  const [started, setStarted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentSpeaker, setCurrentSpeaker] = useState<"interviewer" | "candidate" | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [ended, setEnded] = useState(initialEnded);
  const [error, setError] = useState<string | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const [ivCursor, setIvCursor] = useState<CursorPos>({ x: 180, y: 130, visible: false });
  const [cxCursor, setCxCursor] = useState<CursorPos>({ x: 460, y: 280, visible: false });
  const [humanCursor, setHumanCursor] = useState<{ x: number; y: number } | null>(null);

  // Stable refs
  const isPlayingRef = useRef(false);
  const endedRef = useRef(initialEnded);
  const isSteppingRef = useRef(false);
  const usedLabelsRef = useRef<Set<string>>(new Set());
  const nextSlotRef = useRef(0);
  const animStopRef = useRef<{ current: boolean }>({ current: false });
  const lastDrawTargetRef = useRef<{ x: number; y: number } | undefined>(undefined);

  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);
  useEffect(() => { endedRef.current = ended; }, [ended]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript.length]);

  // Animate the active speaker's cursor; aim toward recently drawn element
  useEffect(() => {
    if (!currentSpeaker) return;
    const container = whiteboardContainerRef.current;
    const w = container?.clientWidth ?? 800;
    const h = container?.clientHeight ?? 600;
    const stopRef = { current: false };
    animStopRef.current = stopRef;
    const setter = currentSpeaker === "interviewer" ? setIvCursor : setCxCursor;
    const cancel = animateCursor(setter, stopRef, { w, h }, lastDrawTargetRef.current);
    return () => { stopRef.current = true; cancel(); };
  }, [currentSpeaker]);

  // Draw the question title on the whiteboard on first step
  const drawnTitleRef = useRef(false);
  function maybeDrawTitle() {
    if (drawnTitleRef.current || !whiteboardRef.current) return;
    drawnTitleRef.current = true;
    const title: WhiteboardElement = {
      id: "title-text",
      type: "text",
      x: 60, y: 20,
      color: "#5E636C",
      strokeWidth: 1,
      text: questionTitle.toUpperCase(),
      fontSize: 11,
    } as WhiteboardElement;
    whiteboardRef.current.addElements([title]);
  }

  const stepAndSpeak = useCallback(async () => {
    if (isSteppingRef.current || endedRef.current) return;
    isSteppingRef.current = true;
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/interview/ai-vs-ai/step", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, voiceMode: true }),
      });
      if (!res.ok || !res.body) throw new Error(`Server error ${res.status}`);

      const role = (res.headers.get("x-agent-role") ?? "interviewer") as "interviewer" | "candidate";

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let text = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        text += decoder.decode(value, { stream: true });
      }

      const isEnd = text.includes("<<INTERVIEW_END>>");
      const cleaned = stripMermaid(text.replace(/<<INTERVIEW_END>>/g, "").trimEnd());

      setTranscript((prev) => [...prev, { role, content: cleaned, ts: Date.now() }]);

      // Draw title on first ever turn, then extract components
      maybeDrawTitle();
      const { elements, newSlot, targetPos } = extractDrawingElements(
        cleaned, role, usedLabelsRef.current, nextSlotRef.current,
      );
      if (elements.length > 0 && whiteboardRef.current) {
        whiteboardRef.current.addElements(elements);
        nextSlotRef.current = newSlot;
        if (targetPos) lastDrawTargetRef.current = targetPos;
      }

      if (isEnd) {
        setEnded(true);
        setIsPlaying(false);
        endedRef.current = true;
        setCurrentSpeaker(null);
      }

      isSteppingRef.current = false;
      setIsLoading(false);

      if (isPlayingRef.current && !isEnd) {
        setCurrentSpeaker(role);
        speakTurn(cleaned, role, () => {
          setCurrentSpeaker(null);
          if (isPlayingRef.current && !endedRef.current) void stepAndSpeak();
        });
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Step failed");
      setIsPlaying(false);
      setCurrentSpeaker(null);
      isSteppingRef.current = false;
      setIsLoading(false);
    }
  }, [sessionId]);

  function beginAndPlay() {
    setStarted(true);
    setIsPlaying(true);
    isPlayingRef.current = true;
    void stepAndSpeak();
  }

  function togglePlay() {
    if (ended) return;
    if (isPlaying) {
      setIsPlaying(false);
      isPlayingRef.current = false;
      window.speechSynthesis?.cancel();
      setCurrentSpeaker(null);
    } else {
      setIsPlaying(true);
      isPlayingRef.current = true;
      if (!isSteppingRef.current && !currentSpeaker) void stepAndSpeak();
    }
  }

  function stepOnce() {
    if (ended || isSteppingRef.current || currentSpeaker) return;
    setIsPlaying(false);
    isPlayingRef.current = false;
    void stepAndSpeak();
  }

  async function endSession() {
    if (!confirm("End session and score it?")) return;
    window.speechSynthesis?.cancel();
    try {
      const res = await fetch(`/api/interview/session/${sessionId}/score`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          transcriptHistory: transcript.map((m) => ({ role: m.role, content: m.content })),
        }),
      });
      if (!res.ok) throw new Error(`Score failed: ${res.status}`);
      router.push(`/interview/sessions/${sessionId}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to end session");
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "var(--bg)", color: "var(--ink)", fontFamily: "var(--font-ui)" }}>

      {/* Top bar */}
      <header style={{ flexShrink: 0, height: 44, display: "flex", alignItems: "center", padding: "0 18px", borderBottom: "1px solid var(--line)", gap: 12, background: "var(--bg)" }}>
        <Bot style={{ width: 14, height: 14, color: "var(--mute)" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.1em" }}>AI vs AI</span>
          <span style={{ color: "var(--subtle)" }}>›</span>
          <b style={{ color: "var(--ink-2)", fontWeight: 500, fontSize: 13, letterSpacing: "-0.005em", maxWidth: 340, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{questionTitle}</b>
        </div>
        <div style={{ flex: 1 }} />

        {currentSpeaker && (
          <div style={{ display: "flex", alignItems: "center", gap: 5, fontFamily: "var(--font-mono)", fontSize: 10, color: currentSpeaker === "interviewer" ? CURSOR_IV : CURSOR_CX }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: "currentColor", animation: "speak-pulse 0.8s ease-in-out infinite" }} />
            {currentSpeaker === "interviewer" ? "Interviewer" : "Candidate"}
          </div>
        )}
        {isLoading && !currentSpeaker && (
          <Loader2 style={{ width: 12, height: 12, color: "var(--mute)", animation: "spin 1s linear infinite" }} />
        )}

        {started && !ended && (
          <>
            <button type="button" onClick={togglePlay} className="btn" style={{ fontSize: 12, padding: "4px 10px", gap: 5 }}>
              {isPlaying ? <Pause style={{ width: 12, height: 12 }} /> : <Play style={{ width: 12, height: 12 }} />}
              {isPlaying ? "Pause" : "Play"}
            </button>
            <button
              type="button"
              onClick={stepOnce}
              disabled={!!currentSpeaker || isPlaying}
              className="btn btn--ghost"
              style={{ fontSize: 12, padding: "4px 10px", gap: 5 }}
            >
              <StepForward style={{ width: 12, height: 12 }} />
              Step
            </button>
          </>
        )}
        <button type="button" onClick={endSession} className="btn" style={{ fontSize: 12, padding: "4px 10px", gap: 5 }}>
          <X style={{ width: 12, height: 12 }} />
          End
        </button>
      </header>

      {/* Main: whiteboard + sidebar */}
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>

        {/* Whiteboard + cursor overlay */}
        <div
          ref={whiteboardContainerRef}
          onMouseMove={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            setHumanCursor({ x: e.clientX - r.left, y: e.clientY - r.top });
          }}
          onMouseLeave={() => setHumanCursor(null)}
          style={{ flex: 1, minHeight: 0, minWidth: 0, position: "relative" }}
        >
          <Whiteboard ref={whiteboardRef} onChange={(els: WhiteboardElements, s: WhiteboardAppState) => { void els; void s; }} />

          {/* Cursor overlay */}
          <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden" }}>
            {ivCursor.visible && (
              <CursorLabel x={ivCursor.x} y={ivCursor.y} color={CURSOR_IV} label="INTERVIEWER" />
            )}
            {cxCursor.visible && (
              <CursorLabel x={cxCursor.x} y={cxCursor.y} color={CURSOR_CX} label="CANDIDATE" />
            )}
            {humanCursor && (
              <div style={{ position: "absolute", left: humanCursor.x + 14, top: humanCursor.y - 2 }}>
                <div style={{ background: CURSOR_HU, color: "#0D1A10", fontFamily: "var(--font-mono)", fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 3, letterSpacing: "0.06em" }}>YOU</div>
              </div>
            )}
          </div>

          {/* Begin overlay */}
          {!started && (
            <div style={{
              position: "absolute", inset: 0,
              background: "color-mix(in srgb, var(--bg) 85%, transparent)",
              backdropFilter: "blur(3px)",
              display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
              gap: 16, zIndex: 10,
            }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.12em" }}>AI vs AI · Voice</div>
              <div style={{ fontSize: 20, fontWeight: 600, color: "var(--ink)", letterSpacing: "-0.02em", maxWidth: 400, textAlign: "center", lineHeight: 1.25 }}>{questionTitle}</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute-2)", textAlign: "center", maxWidth: "36ch", lineHeight: 1.6 }}>
                Two AIs interview each other with voice. Components appear on the whiteboard as they discuss. You can draw too.
              </div>
              <div style={{ display: "flex", gap: 18, marginTop: 2 }}>
                {([["INTERVIEWER", CURSOR_IV], ["CANDIDATE", CURSOR_CX], ["YOU", CURSOR_HU]] as const).map(([lbl, col]) => (
                  <div key={lbl} style={{ display: "flex", alignItems: "center", gap: 5, fontFamily: "var(--font-mono)", fontSize: 10, color: col }}>
                    <div style={{ width: 7, height: 7, borderRadius: "50%", background: col }} />
                    {lbl}
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={beginAndPlay}
                style={{ marginTop: 6, display: "inline-flex", alignItems: "center", gap: 10, padding: "11px 26px", borderRadius: 8, background: "var(--accent)", color: "var(--accent-ink)", border: "none", fontSize: 14, fontWeight: 600, cursor: "pointer", letterSpacing: "-0.01em" }}
              >
                <Play style={{ width: 16, height: 16 }} />
                Start Interview
              </button>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute-2)" }}>Audio starts on click</div>
            </div>
          )}
        </div>

        {/* Compact transcript sidebar */}
        <aside style={{ width: 260, flexShrink: 0, display: "flex", flexDirection: "column", borderLeft: "1px solid var(--line)", background: "var(--bg-2)" }}>
          <div style={{ flexShrink: 0, padding: "8px 12px 6px", borderBottom: "1px solid var(--line)", display: "flex", gap: 14 }}>
            {(["interviewer", "candidate"] as const).map((r) => (
              <div key={r} style={{ display: "flex", alignItems: "center", gap: 4, fontFamily: "var(--font-mono)", fontSize: 9, textTransform: "uppercase", letterSpacing: "0.08em", color: r === "interviewer" ? CURSOR_IV : CURSOR_CX }}>
                <div style={{ width: 4, height: 4, borderRadius: "50%", background: "currentColor" }} />
                {r}
              </div>
            ))}
          </div>

          <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "8px 10px 6px", display: "flex", flexDirection: "column", gap: 4 }}>
            {transcript.length === 0 ? (
              <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-read)", fontStyle: "italic", fontSize: 12, color: "var(--mute-2)", textAlign: "center", padding: "20px 0" }}>
                Conversation will appear here
              </div>
            ) : (
              transcript.map((msg, i) => {
                const isIv = msg.role === "interviewer";
                return (
                  <div key={i} style={{ display: "flex", flexDirection: "column", gap: 2, alignItems: isIv ? "flex-start" : "flex-end" }}>
                    <div style={{
                      maxWidth: "96%",
                      borderRadius: isIv ? "2px 7px 7px 7px" : "7px 2px 7px 7px",
                      padding: "5px 9px",
                      fontSize: 12,
                      lineHeight: 1.45,
                      whiteSpace: "pre-wrap",
                      background: isIv ? "var(--surf)" : "var(--bg)",
                      border: `1px solid ${isIv ? "var(--line)" : "var(--line-2)"}`,
                      color: isIv ? "var(--ink-2)" : "var(--ink)",
                      borderLeft: isIv ? `2px solid ${CURSOR_IV}` : undefined,
                      borderRight: !isIv ? `2px solid ${CURSOR_CX}` : undefined,
                    }}>
                      {msg.content}
                    </div>
                  </div>
                );
              })
            )}
            {isLoading && (
              <div style={{ padding: "4px 2px", display: "flex", alignItems: "center", gap: 5 }}>
                <Loader2 style={{ width: 10, height: 10, color: "var(--mute)", animation: "spin 1s linear infinite" }} />
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--mute)" }}>Thinking…</span>
              </div>
            )}
            {error && (
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--bad)", padding: "3px 2px" }}>{error}</div>
            )}
            {ended && (
              <div style={{ textAlign: "center", padding: "10px 0", fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                Interview ended
              </div>
            )}
            <div ref={transcriptEndRef} />
          </div>
        </aside>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes speak-pulse { 0%,100%{ opacity:1; } 50%{ opacity:0.25; } }
      `}</style>
    </div>
  );
}

function CursorLabel({ x, y, color, label }: { x: number; y: number; color: string; label: string }) {
  return (
    <div style={{
      position: "absolute", left: x, top: y,
      transform: "translate(-2px, -2px)",
      transition: "left 0.12s ease-out, top 0.12s ease-out",
    }}>
      <svg width="14" height="18" viewBox="0 0 14 18" fill="none">
        <path d="M2 2L12 7L7 9L5.5 14L2 2Z" fill={color} stroke="#111" strokeWidth="0.8" strokeLinejoin="round" />
      </svg>
      <div style={{
        position: "absolute", left: 14, top: 0,
        background: color, color: color === CURSOR_IV ? "#1A1408" : "#0D1520",
        fontFamily: "var(--font-mono)", fontSize: 8, fontWeight: 700,
        padding: "1px 4px", borderRadius: 2, whiteSpace: "nowrap", letterSpacing: "0.06em",
      }}>
        {label}
      </div>
    </div>
  );
}
