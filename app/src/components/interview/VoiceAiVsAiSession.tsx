"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { Play, Pause, StepForward, X, Loader2, Bot } from "lucide-react";
import { type WhiteboardHandle, type WhiteboardElements, type WhiteboardAppState } from "@/components/Whiteboard";
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

// Speak text and fire onEnd — separate from useVoicePlayback so we can wire
// the auto-advance callback without restructuring the shared hook.
function speakTurn(
  text: string,
  role: "interviewer" | "candidate",
  onEnd: () => void,
) {
  if (typeof window === "undefined" || !window.speechSynthesis) { onEnd(); return; }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = role === "interviewer" ? 0.92 : 0.97;
  u.pitch = role === "interviewer" ? 1.0 : 0.95;
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

// Parse key architectural terms from an AI response and convert to whiteboard
// text/rect elements. We place them in a loose grid to avoid overlap.
function extractDrawingElements(
  text: string,
  role: "interviewer" | "candidate",
  existingCount: number,
): WhiteboardElement[] {
  const ARCH_TERMS = [
    "load balancer", "database", "cache", "api gateway", "cdn", "queue",
    "message queue", "service", "microservice", "storage", "proxy",
    "server", "client", "auth", "authentication", "rate limiter",
    "sharding", "replica", "kafka", "redis", "postgres", "mysql",
    "s3", "blob storage", "indexing", "search", "pubsub",
  ];
  const lower = text.toLowerCase();
  const found: string[] = [];
  for (const term of ARCH_TERMS) {
    if (lower.includes(term) && !found.includes(term)) found.push(term);
    if (found.length >= 3) break;
  }
  if (found.length === 0) return [];

  // Colors: interviewer draws in amber, candidate draws in blue
  const color = role === "interviewer" ? "#D4A574" : "#7DA7C9";
  const cols = 4;
  const cellW = 200;
  const cellH = 80;
  const startX = 60;
  const startY = 60;

  return found.map((term, i) => {
    const slot = existingCount + i;
    const col = slot % cols;
    const row = Math.floor(slot / cols);
    const id = `ai-${Date.now()}-${i}`;
    const x = startX + col * (cellW + 20);
    const y = startY + row * (cellH + 20);
    return {
      id,
      type: "rect" as const,
      x,
      y,
      width: cellW - 20,
      height: cellH - 20,
      color,
      fill: "transparent",
      strokeWidth: 1.5,
      label: term,
    } as WhiteboardElement & { label?: string };
  }).flatMap((rect, i) => {
    // Return the rect + a text label inside it
    const term = found[i];
    const textEl: WhiteboardElement = {
      id: `${rect.id}-t`,
      type: "text",
      x: rect.x + 10,
      y: rect.y + 18,
      color: (rect as { color: string }).color,
      strokeWidth: 1,
      text: term.toUpperCase(),
      fontSize: 12,
    };
    return [rect as WhiteboardElement, textEl];
  });
}

// ---------------------------------------------------------------------------
// Cursor animation — smooth random walk within canvas bounds
// ---------------------------------------------------------------------------

function animateCursor(
  setPos: (pos: CursorPos) => void,
  stopRef: { current: boolean },
  bounds: { w: number; h: number },
) {
  let cx = bounds.w * (0.3 + Math.random() * 0.4);
  let cy = bounds.h * (0.2 + Math.random() * 0.4);
  let tx = cx;
  let ty = cy;
  let lastTarget = 0;
  let rafId = 0;

  function tick(now: number) {
    if (stopRef.current) {
      setPos({ x: cx, y: cy, visible: false });
      return;
    }
    // Pick a new target every 900–1800ms
    if (now - lastTarget > 900 + Math.random() * 900) {
      tx = bounds.w * (0.1 + Math.random() * 0.75);
      ty = bounds.h * (0.1 + Math.random() * 0.75);
      lastTarget = now;
    }
    // Ease toward target
    cx += (tx - cx) * 0.06;
    cy += (ty - cy) * 0.06;
    setPos({ x: cx, y: cy, visible: true });
    rafId = requestAnimationFrame(tick);
  }
  rafId = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(rafId);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function VoiceAiVsAiSession({
  sessionId,
  questionTitle,
  initialTranscript,
  initialEnded,
}: Props) {
  const router = useRouter();
  const whiteboardRef = useRef<WhiteboardHandle>(null);
  const whiteboardElsRef = useRef<WhiteboardElements>([]);
  const whiteboardContainerRef = useRef<HTMLDivElement>(null);

  const [transcript, setTranscript] = useState<Msg[]>(initialTranscript);
  const [started, setStarted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentSpeaker, setCurrentSpeaker] = useState<"interviewer" | "candidate" | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [ended, setEnded] = useState(initialEnded);
  const [error, setError] = useState<string | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // Cursors
  const [ivCursor, setIvCursor] = useState<CursorPos>({ x: 200, y: 150, visible: false });
  const [cxCursor, setCxCursor] = useState<CursorPos>({ x: 500, y: 300, visible: false });
  const [humanCursor, setHumanCursor] = useState<{ x: number; y: number } | null>(null);

  // Stable refs for async callbacks
  const isPlayingRef = useRef(false);
  const endedRef = useRef(initialEnded);
  const isSteppingRef = useRef(false);
  const aiElementCountRef = useRef(0);
  const animStopRef = useRef({ current: false });

  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);
  useEffect(() => { endedRef.current = ended; }, [ended]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript.length]);

  // Animate the active speaker's cursor
  useEffect(() => {
    if (!currentSpeaker) return;
    const container = whiteboardContainerRef.current;
    const w = container?.clientWidth ?? 800;
    const h = container?.clientHeight ?? 600;
    const stopRef = { current: false };
    animStopRef.current = stopRef;
    const setter = currentSpeaker === "interviewer" ? setIvCursor : setCxCursor;
    const cancel = animateCursor(setter, stopRef, { w, h });
    return () => { stopRef.current = true; cancel(); };
  }, [currentSpeaker]);

  const stepAndSpeak = useCallback(async () => {
    if (isSteppingRef.current || endedRef.current) return;
    isSteppingRef.current = true;
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/interview/ai-vs-ai/step", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId }),
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
      const cleaned = text.replace(/<<INTERVIEW_END>>/g, "").trimEnd();

      setTranscript((prev) => [...prev, { role, content: cleaned, ts: Date.now() }]);

      // Draw architectural concepts the AI mentioned
      const drawEls = extractDrawingElements(cleaned, role, aiElementCountRef.current);
      if (drawEls.length > 0 && whiteboardRef.current) {
        whiteboardRef.current.addElements(drawEls);
        aiElementCountRef.current += drawEls.length / 2; // each concept = rect + text
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
          if (isPlayingRef.current && !endedRef.current) {
            void stepAndSpeak();
          }
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
      if (!isSteppingRef.current) void stepAndSpeak();
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

  function handleWhiteboardChange(els: WhiteboardElements, _state: WhiteboardAppState) {
    whiteboardElsRef.current = els;
  }

  function handleMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    setHumanCursor({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const CURSOR_IV = "#D4A574";   // amber — interviewer
  const CURSOR_CX = "#7DA7C9";   // blue  — candidate
  const CURSOR_HU = "#7FB48A";   // green — human

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

        {/* Speaker indicator */}
        {currentSpeaker && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontFamily: "var(--font-mono)", fontSize: 10, color: currentSpeaker === "interviewer" ? CURSOR_IV : CURSOR_CX }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor", animation: "speak-pulse 0.8s ease-in-out infinite" }} />
            {currentSpeaker === "interviewer" ? "Interviewer speaking" : "Candidate speaking"}
          </div>
        )}
        {isLoading && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute)" }}>
            <Loader2 style={{ width: 11, height: 11, animation: "spin 1s linear infinite" }} />
            Thinking…
          </div>
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
              disabled={isSteppingRef.current || !!currentSpeaker || isPlaying}
              className="btn btn--ghost"
              style={{ fontSize: 12, padding: "4px 10px", gap: 5 }}
              title="One turn"
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

      {/* Main area: whiteboard + transcript sidebar */}
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>

        {/* Whiteboard with cursor overlay */}
        <div
          ref={whiteboardContainerRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHumanCursor(null)}
          style={{ flex: 1, minHeight: 0, minWidth: 0, position: "relative" }}
        >
          <Whiteboard ref={whiteboardRef} onChange={handleWhiteboardChange} />

          {/* Cursor overlay — pointer-events:none so canvas stays interactive */}
          <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden" }}>

            {/* Interviewer cursor */}
            {ivCursor.visible && (
              <div style={{ position: "absolute", left: ivCursor.x, top: ivCursor.y, transform: "translate(-2px, -2px)", transition: "left 0.15s ease-out, top 0.15s ease-out" }}>
                <CursorIcon color={CURSOR_IV} />
                <div style={{ position: "absolute", left: 16, top: 0, background: CURSOR_IV, color: "#1A1408", fontFamily: "var(--font-mono)", fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 3, whiteSpace: "nowrap", letterSpacing: "0.06em" }}>
                  INTERVIEWER
                </div>
              </div>
            )}

            {/* Candidate cursor */}
            {cxCursor.visible && (
              <div style={{ position: "absolute", left: cxCursor.x, top: cxCursor.y, transform: "translate(-2px, -2px)", transition: "left 0.15s ease-out, top 0.15s ease-out" }}>
                <CursorIcon color={CURSOR_CX} />
                <div style={{ position: "absolute", left: 16, top: 0, background: CURSOR_CX, color: "#0D1520", fontFamily: "var(--font-mono)", fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 3, whiteSpace: "nowrap", letterSpacing: "0.06em" }}>
                  CANDIDATE
                </div>
              </div>
            )}

            {/* Human cursor */}
            {humanCursor && (
              <div style={{ position: "absolute", left: humanCursor.x + 14, top: humanCursor.y - 2, pointerEvents: "none" }}>
                <div style={{ background: CURSOR_HU, color: "#0D1A10", fontFamily: "var(--font-mono)", fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 3, whiteSpace: "nowrap", letterSpacing: "0.06em" }}>
                  YOU
                </div>
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
              gap: 18, zIndex: 10,
            }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.12em" }}>AI vs AI · Voice</div>
              <div style={{ fontSize: 20, fontWeight: 600, color: "var(--ink)", letterSpacing: "-0.02em", maxWidth: 400, textAlign: "center", lineHeight: 1.25 }}>{questionTitle}</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute-2)", textAlign: "center", maxWidth: "36ch", lineHeight: 1.6 }}>
                Two AIs interview each other with voice and draw on the whiteboard. You can draw too.
              </div>
              {/* Cursor legend */}
              <div style={{ display: "flex", gap: 20, marginTop: 4 }}>
                {([["INTERVIEWER", CURSOR_IV], ["CANDIDATE", CURSOR_CX], ["YOU", CURSOR_HU]] as const).map(([label, color]) => (
                  <div key={label} style={{ display: "flex", alignItems: "center", gap: 6, fontFamily: "var(--font-mono)", fontSize: 10, color }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: color }} />
                    {label}
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={beginAndPlay}
                style={{ marginTop: 8, display: "inline-flex", alignItems: "center", gap: 10, padding: "11px 26px", borderRadius: 8, background: "var(--accent)", color: "var(--accent-ink)", border: "none", fontSize: 14, fontWeight: 600, cursor: "pointer", letterSpacing: "-0.01em" }}
              >
                <Play style={{ width: 16, height: 16 }} />
                Start Interview
              </button>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute-2)" }}>Audio starts on click</div>
            </div>
          )}
        </div>

        {/* Transcript sidebar */}
        <aside style={{ width: 280, flexShrink: 0, display: "flex", flexDirection: "column", borderLeft: "1px solid var(--line)", background: "var(--bg-2)" }}>
          <div style={{ flexShrink: 0, padding: "10px 14px 8px", borderBottom: "1px solid var(--line)", display: "flex", gap: 12 }}>
            {(["interviewer", "candidate"] as const).map((r) => (
              <div key={r} style={{ display: "flex", alignItems: "center", gap: 5, fontFamily: "var(--font-mono)", fontSize: 9.5, textTransform: "uppercase", letterSpacing: "0.08em", color: r === "interviewer" ? CURSOR_IV : CURSOR_CX }}>
                <div style={{ width: 5, height: 5, borderRadius: "50%", background: "currentColor" }} />
                {r}
              </div>
            ))}
          </div>

          <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "12px 12px 6px", display: "flex", flexDirection: "column", gap: 8 }}>
            {transcript.length === 0 ? (
              <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-read)", fontStyle: "italic", fontSize: 13, color: "var(--mute-2)", textAlign: "center" }}>
                Conversation will appear here
              </div>
            ) : (
              transcript.map((msg, i) => {
                const isIv = msg.role === "interviewer";
                return (
                  <div key={i} style={{ display: "flex", flexDirection: "column", gap: 2, alignItems: isIv ? "flex-start" : "flex-end" }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: isIv ? CURSOR_IV : CURSOR_CX, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      {isIv ? "Interviewer" : "Candidate"}
                    </span>
                    <div style={{
                      maxWidth: "94%", borderRadius: isIv ? "3px 8px 8px 8px" : "8px 3px 8px 8px",
                      padding: "7px 10px", fontSize: 12.5, lineHeight: 1.5, whiteSpace: "pre-wrap",
                      background: isIv ? "var(--surf)" : "var(--bg)",
                      border: `1px solid ${isIv ? "var(--line)" : "var(--line-2)"}`,
                      color: "var(--ink-2)",
                    }}>
                      {msg.content}
                    </div>
                  </div>
                );
              })
            )}
            {isLoading && (
              <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 2px" }}>
                <Loader2 style={{ width: 12, height: 12, color: "var(--mute)", animation: "spin 1s linear infinite" }} />
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute)" }}>Thinking…</span>
              </div>
            )}
            {error && (
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--bad)", padding: "4px 2px" }}>{error}</div>
            )}
            {ended && (
              <div style={{ textAlign: "center", padding: "12px 0", fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                Interview ended
              </div>
            )}
            <div ref={transcriptEndRef} />
          </div>
        </aside>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes speak-pulse { 0%,100%{ opacity:1; } 50%{ opacity:0.3; } }
      `}</style>
    </div>
  );
}

// Minimal SVG cursor arrow
function CursorIcon({ color }: { color: string }) {
  return (
    <svg width="16" height="20" viewBox="0 0 16 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M2 2L14 8L8 10L6 16L2 2Z" fill={color} stroke="#111" strokeWidth="1" strokeLinejoin="round" />
    </svg>
  );
}
