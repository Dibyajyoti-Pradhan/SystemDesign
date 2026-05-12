"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
// Direct import (no dynamic) so forwardRef on Whiteboard works — dynamic() wrappers
// don't forward refs to the inner component, which broke whiteboardRef.current.
import { Whiteboard, type WhiteboardHandle, type WhiteboardElements, type WhiteboardAppState } from "@/components/Whiteboard";
import { type WhiteboardElement } from "@/components/WhiteboardCanvas";
import { Play, Pause, StepForward, X, Loader2, Bot } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Msg { role: "interviewer" | "candidate"; content: string; ts: number; }
interface CursorPos { x: number; y: number; visible: boolean; }
interface Props {
  sessionId: number;
  questionTitle: string;
  initialTranscript: Msg[];
  initialEnded: boolean;
}

// ---------------------------------------------------------------------------
// Draw command parsing
// ---------------------------------------------------------------------------

interface DrawBox { id: string; label: string; c: number; r: number; style?: "note"; }
interface DrawArrow { from: string; to: string; }
interface DrawCmd { boxes?: DrawBox[]; arrows?: DrawArrow[]; }

const DRAW_RE = /<<DRAW>>([\s\S]*?)<<END_DRAW>>/;

function parseDrawCmd(raw: string): DrawCmd | null {
  const m = raw.match(DRAW_RE);
  if (!m) return null;
  // Claude sometimes wraps JSON in code fences inside the block — strip them
  const inner = m[1].replace(/^```[a-z]*\n?/i, "").replace(/\n?```$/i, "").trim();
  try { return JSON.parse(inner) as DrawCmd; } catch { return null; }
}

function stripMeta(text: string): string {
  return text
    .replace(/<<DRAW>>[\s\S]*?<<END_DRAW>>/g, "")
    .replace(/```mermaid[\s\S]*?```/gi, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// Fallback: extract known arch terms when no <<DRAW>> block found
const FALLBACK_TERMS: [string, string][] = [
  ["load balancer", "Load Balancer"], ["api gateway", "API Gateway"],
  ["cdn", "CDN"], ["cache", "Cache"], ["redis", "Redis"],
  ["database", "Database"], ["postgres", "Postgres"], ["mysql", "MySQL"],
  ["cassandra", "Cassandra"], ["dynamodb", "DynamoDB"],
  ["message queue", "Message Queue"], ["kafka", "Kafka"], ["sqs", "SQS"],
  ["worker", "Workers"], ["app server", "App Server"], ["app tier", "App Tier"],
  ["object storage", "Object Storage"], ["s3", "S3"],
  ["rate limit", "Rate Limiter"], ["auth", "Auth Service"],
  ["search", "Search"], ["elasticsearch", "Elasticsearch"],
];

function fallbackCmd(text: string, usedLabels: Set<string>): DrawCmd {
  const lower = text.toLowerCase();
  const boxes: DrawBox[] = [];
  for (const [kw, label] of FALLBACK_TERMS) {
    if (lower.includes(kw) && !usedLabels.has(label) && boxes.length < 3) {
      boxes.push({ id: label.toLowerCase().replace(/\s+/g, "_"), label, c: 0, r: 0 });
    }
  }
  return { boxes, arrows: [] };
}

// ---------------------------------------------------------------------------
// Grid → pixel layout
// ---------------------------------------------------------------------------

const CELL_W = 190;
const CELL_H = 90;
const GRID_X = 48;
const GRID_Y = 56;
const BOX_W = 154;
const BOX_H = 52;

interface NodeRect { x: number; y: number; cx: number; cy: number; w: number; h: number; }

function gridBox(c: number, r: number): NodeRect {
  const x = GRID_X + c * CELL_W;
  const y = GRID_Y + r * CELL_H;
  return { x, y, cx: x + BOX_W / 2, cy: y + BOX_H / 2, w: BOX_W, h: BOX_H };
}

// Auto-assign grid position for fallback terms
function assignFallbackPositions(boxes: DrawBox[], nodeMap: Map<string, NodeRect>): DrawBox[] {
  const takenSlots = new Set<string>();
  for (const [, rect] of nodeMap) {
    // find closest grid slot to existing rect
    const c = Math.round((rect.x - GRID_X) / CELL_W);
    const r = Math.round((rect.y - GRID_Y) / CELL_H);
    takenSlots.add(`${c},${r}`);
  }
  let slot = 0;
  return boxes.map(box => {
    while (takenSlots.has(`${slot % 6},${Math.floor(slot / 6)}`)) slot++;
    const c = slot % 6;
    const r = Math.min(4, Math.floor(slot / 6));
    slot++;
    return { ...box, c, r };
  });
}

function arrowEndpoints(src: NodeRect, dst: NodeRect): [number, number, number, number] {
  const dx = dst.cx - src.cx, dy = dst.cy - src.cy;
  const horiz = Math.abs(dx) >= Math.abs(dy);
  const sx = horiz ? (dx > 0 ? src.x + src.w : src.x) : src.cx;
  const sy = horiz ? src.cy : (dy > 0 ? src.y + src.h : src.y);
  const ex = horiz ? (dx > 0 ? dst.x : dst.x + dst.w) : dst.cx;
  const ey = horiz ? dst.cy : (dy > 0 ? dst.y : dst.y + dst.h);
  return [sx, sy, ex, ey];
}

function buildElements(
  cmd: DrawCmd,
  role: "interviewer" | "candidate",
  nodeMap: Map<string, NodeRect>,
  usedLabels: Set<string>,
): { elements: WhiteboardElement[]; firstNewPos: { x: number; y: number } | null } {
  const color = role === "interviewer" ? "#D4A574" : "#7DA7C9";
  const els: WhiteboardElement[] = [];
  let firstNewPos: { x: number; y: number } | null = null;

  for (const box of (cmd.boxes ?? [])) {
    if (nodeMap.has(box.id)) continue;
    const rect = gridBox(Math.max(0, Math.min(5, box.c)), Math.max(0, Math.min(4, box.r)));
    nodeMap.set(box.id, rect);
    usedLabels.add(box.label);
    if (!firstNewPos) firstNewPos = { x: rect.cx, y: rect.cy };

    els.push({
      id: `box-${box.id}`,
      type: "rect",
      x: rect.x, y: rect.y,
      width: BOX_W, height: BOX_H,
      color,
      fill: box.style === "note" ? `${color}18` : "transparent",
      strokeWidth: box.style === "note" ? 1 : 1.8,
    } as WhiteboardElement);

    els.push({
      id: `lbl-${box.id}`,
      type: "text",
      x: rect.x + 10, y: rect.y + 18,
      color, strokeWidth: 1,
      text: box.label, fontSize: 13,
    } as WhiteboardElement);
  }

  for (const arrow of (cmd.arrows ?? [])) {
    const src = nodeMap.get(arrow.from);
    const dst = nodeMap.get(arrow.to);
    if (!src || !dst) continue;
    const [x, y, endX, endY] = arrowEndpoints(src, dst);
    els.push({
      id: `arr-${arrow.from}-${arrow.to}-${Date.now()}`,
      type: "arrow",
      x, y, endX, endY,
      color, strokeWidth: 1.5,
    } as WhiteboardElement);
  }

  return { elements: els, firstNewPos };
}

// ---------------------------------------------------------------------------
// TTS
// ---------------------------------------------------------------------------

function speakTurn(text: string, role: "interviewer" | "candidate", onEnd: () => void) {
  if (typeof window === "undefined" || !window.speechSynthesis) { onEnd(); return; }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = role === "interviewer" ? 0.93 : 0.97;
  u.pitch = role === "interviewer" ? 1.0 : 0.93;
  const voices = window.speechSynthesis.getVoices();
  if (role === "interviewer") {
    const v = voices.find(v => v.lang === "en-GB" && v.name.includes("Neural"))
      ?? voices.find(v => v.lang === "en-GB")
      ?? voices.find(v => v.lang.startsWith("en"));
    if (v) u.voice = v;
  } else {
    const v = voices.find(v => v.lang === "en-US" && v.name.includes("Neural"))
      ?? voices.find(v => v.lang === "en-US")
      ?? voices.find(v => v.lang.startsWith("en"));
    if (v) u.voice = v;
  }
  u.onend = onEnd;
  u.onerror = onEnd;
  window.speechSynthesis.speak(u);
}

// ---------------------------------------------------------------------------
// Cursor animation
// ---------------------------------------------------------------------------

function animateCursor(
  set: (p: CursorPos) => void,
  stopRef: { current: boolean },
  bounds: { w: number; h: number },
  target?: { x: number; y: number },
) {
  let cx = bounds.w * 0.4, cy = bounds.h * 0.3;
  let tx = target?.x ?? cx, ty = target?.y ?? cy;
  let phase: "goto" | "wander" = target ? "goto" : "wander";
  let lastPick = 0;
  const raf = { id: 0 };
  function tick(now: number) {
    if (stopRef.current) { set({ x: cx, y: cy, visible: false }); return; }
    if (phase === "goto") {
      cx += (tx - cx) * 0.09; cy += (ty - cy) * 0.09;
      if (Math.hypot(tx - cx, ty - cy) < 6) phase = "wander";
    } else {
      if (now - lastPick > 900 + Math.random() * 900) {
        tx = Math.max(40, Math.min(bounds.w - 40, tx + (Math.random() - 0.5) * 260));
        ty = Math.max(40, Math.min(bounds.h - 40, ty + (Math.random() - 0.5) * 160));
        lastPick = now;
      }
      cx += (tx - cx) * 0.07; cy += (ty - cy) * 0.07;
    }
    set({ x: cx, y: cy, visible: true });
    raf.id = requestAnimationFrame(tick);
  }
  raf.id = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(raf.id);
}

const IV = "#D4A574";
const CX = "#7DA7C9";
const HU = "#7FB48A";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function VoiceAiVsAiSession({ sessionId, questionTitle, initialTranscript, initialEnded }: Props) {
  const router = useRouter();
  const whiteboardRef = useRef<WhiteboardHandle>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const nodeMapRef = useRef<Map<string, NodeRect>>(new Map());
  const usedLabelsRef = useRef<Set<string>>(new Set());

  const [transcript, setTranscript] = useState<Msg[]>(initialTranscript);
  const [started, setStarted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speaker, setSpeaker] = useState<"interviewer" | "candidate" | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [ended, setEnded] = useState(initialEnded);
  const [error, setError] = useState<string | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const [ivCursor, setIvCursor] = useState<CursorPos>({ x: 160, y: 120, visible: false });
  const [cxCursor, setCxCursor] = useState<CursorPos>({ x: 440, y: 260, visible: false });
  const [humanCursor, setHumanCursor] = useState<{ x: number; y: number } | null>(null);

  const isPlayingRef = useRef(false);
  const endedRef = useRef(initialEnded);
  const isSteppingRef = useRef(false);
  const lastDrawTargetRef = useRef<{ x: number; y: number } | undefined>(undefined);
  const titleDrawnRef = useRef(false);
  const pendingCxRef = useRef<{ text: string; elements: WhiteboardElement[] } | null>(null);

  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);
  useEffect(() => { endedRef.current = ended; }, [ended]);
  useEffect(() => { transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [transcript.length]);

  useEffect(() => {
    if (!speaker) return;
    const w = containerRef.current?.clientWidth ?? 800;
    const h = containerRef.current?.clientHeight ?? 600;
    const stop = { current: false };
    const setter = speaker === "interviewer" ? setIvCursor : setCxCursor;
    const cancel = animateCursor(setter, stop, { w, h }, lastDrawTargetRef.current);
    return () => { stop.current = true; cancel(); };
  }, [speaker]);

  function drawTitleOnce() {
    if (titleDrawnRef.current || !whiteboardRef.current) return;
    titleDrawnRef.current = true;
    whiteboardRef.current.addElements([{
      id: "q-title", type: "text",
      x: GRID_X, y: 20, color: "#5E636C",
      strokeWidth: 1, text: questionTitle.toUpperCase(), fontSize: 11,
    } as WhiteboardElement]);
  }

  // Build the element list and update nodeMap/usedLabels immediately (so the
  // cursor animation can target the first new node), but don't push the
  // elements onto the whiteboard yet — that happens progressively during
  // speech via applyDrawingProgressive.
  function collectDrawElements(raw: string, role: "interviewer" | "candidate"): WhiteboardElement[] {
    if (whiteboardRef.current) drawTitleOnce();

    let cmd = parseDrawCmd(raw);
    if (!cmd || (!(cmd.boxes?.length) && !(cmd.arrows?.length))) {
      const spoken = stripMeta(raw);
      const fb = fallbackCmd(spoken, usedLabelsRef.current);
      if (fb.boxes && fb.boxes.length > 0) {
        const positioned = assignFallbackPositions(fb.boxes, nodeMapRef.current);
        cmd = { boxes: positioned, arrows: [] };
      }
    }
    if (!cmd) return [];

    const { elements, firstNewPos } = buildElements(cmd, role, nodeMapRef.current, usedLabelsRef.current);
    if (firstNewPos) lastDrawTargetRef.current = firstNewPos;
    return elements;
  }

  function applyDrawingProgressive(elements: WhiteboardElement[], spokenText: string) {
    if (!whiteboardRef.current || elements.length === 0) return;
    const wordCount = spokenText.split(/\s+/).filter(Boolean).length;
    const estimatedMs = Math.max(4000, (wordCount / 150) * 60 * 1000); // ~150 wpm
    const usableMs = estimatedMs * 0.8; // don't go past 80% of speech
    elements.forEach((el, i) => {
      const delay = i === 0
        ? 800
        : Math.min(1500 + (i / elements.length) * usableMs, usableMs);
      setTimeout(() => {
        whiteboardRef.current?.addElements([el]);
      }, delay);
    });
  }

  const exchangeAndSpeak = useCallback(async () => {
    if (isSteppingRef.current || endedRef.current) return;
    isSteppingRef.current = true;
    setIsLoading(true);
    setError(null);
    pendingCxRef.current = null;

    try {
      const res = await fetch("/api/interview/ai-vs-ai/exchange", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, voiceMode: true }),
      });
      if (!res.ok || !res.body) throw new Error(`Server error ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      let buffer = "";
      let ivText = "";
      let cxText = "";
      let phase: "waiting" | "iv" | "cx" = "waiting";
      let ivSpeakStarted = false;

      const startIvSpeech = () => {
        const isEnd = ivText.includes("<<INTERVIEW_END>>");
        const spoken = stripMeta(ivText.replace(/<<INTERVIEW_END>>/g, ""));
        const drawElements = collectDrawElements(ivText, "interviewer");
        setTranscript(prev => [...prev, { role: "interviewer", content: spoken, ts: Date.now() }]);

        if (isEnd) {
          setEnded(true); endedRef.current = true;
          setIsPlaying(false); setSpeaker(null);
          whiteboardRef.current?.addElements(drawElements);
          return;
        }

        isSteppingRef.current = false;
        setIsLoading(false);

        if (!isPlayingRef.current) {
          whiteboardRef.current?.addElements(drawElements);
          return;
        }

        setSpeaker("interviewer");
        applyDrawingProgressive(drawElements, spoken);
        speakTurn(spoken, "interviewer", () => {
          setSpeaker(null);
          const pending = pendingCxRef.current;
          pendingCxRef.current = null;
          if (pending && isPlayingRef.current && !endedRef.current) {
            setSpeaker("candidate");
            applyDrawingProgressive(pending.elements, pending.text);
            speakTurn(pending.text, "candidate", () => {
              setSpeaker(null);
              if (isPlayingRef.current && !endedRef.current) {
                setTimeout(() => { void exchangeAndSpeak(); }, 600);
              }
            });
          } else if (isPlayingRef.current && !endedRef.current) {
            setTimeout(() => { void exchangeAndSpeak(); }, 600);
          }
        });
      };

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;

        if (phase === "waiting") {
          const idx = buffer.indexOf("<<IV>>");
          if (idx !== -1) { buffer = buffer.slice(idx + 6); phase = "iv"; }
        }

        if (phase === "iv") {
          const idx = buffer.indexOf("<<CX>>");
          if (idx !== -1) {
            ivText += buffer.slice(0, idx);
            buffer = buffer.slice(idx + 6);
            phase = "cx";
            if (!ivSpeakStarted) { ivSpeakStarted = true; startIvSpeech(); }
          } else {
            ivText += buffer; buffer = "";
          }
        }

        if (phase === "cx") {
          cxText += buffer; buffer = "";
        }
      }

      // Stream done — handle remaining cases
      if (phase === "iv" && !ivSpeakStarted) {
        ivText += buffer;
        startIvSpeech();
      }

      // Process CX if we got it
      if (cxText.trim()) {
        const spokenCx = stripMeta(cxText);
        const elements = collectDrawElements(cxText, "candidate");
        setTranscript(prev => [...prev, { role: "candidate", content: spokenCx, ts: Date.now() }]);
        pendingCxRef.current = { text: spokenCx, elements };
      }

      if (!ivSpeakStarted) {
        isSteppingRef.current = false;
        setIsLoading(false);
      }

    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Exchange failed");
      setIsPlaying(false); setSpeaker(null);
      isSteppingRef.current = false; setIsLoading(false);
    }
  }, [sessionId]);

  function beginAndPlay() {
    setStarted(true); setIsPlaying(true); isPlayingRef.current = true;
    void exchangeAndSpeak();
  }
  function togglePlay() {
    if (ended) return;
    if (isPlaying) {
      setIsPlaying(false); isPlayingRef.current = false;
      window.speechSynthesis?.cancel(); setSpeaker(null);
    } else {
      setIsPlaying(true); isPlayingRef.current = true;
      if (!isSteppingRef.current && !speaker) void exchangeAndSpeak();
    }
  }
  function exchangeOnce() {
    if (ended || isSteppingRef.current || speaker) return;
    setIsPlaying(false); isPlayingRef.current = false;
    void exchangeAndSpeak();
  }
  async function endSession() {
    if (!confirm("End session and score it?")) return;
    window.speechSynthesis?.cancel();
    try {
      const res = await fetch(`/api/interview/session/${sessionId}/score`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ transcriptHistory: transcript.map(m => ({ role: m.role, content: m.content })) }),
      });
      if (!res.ok) throw new Error(`Score failed: ${res.status}`);
      router.push(`/interview/sessions/${sessionId}`);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed"); }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "var(--bg)", color: "var(--ink)", fontFamily: "var(--font-ui)" }}>
      <header style={{ flexShrink: 0, height: 44, display: "flex", alignItems: "center", padding: "0 18px", borderBottom: "1px solid var(--line)", gap: 12, background: "var(--bg)" }}>
        <Bot style={{ width: 14, height: 14, color: "var(--mute)" }} />
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.1em" }}>AI vs AI</span>
        <span style={{ color: "var(--subtle)" }}>›</span>
        <b style={{ color: "var(--ink-2)", fontWeight: 500, fontSize: 13, letterSpacing: "-0.005em", maxWidth: 340, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{questionTitle}</b>
        <div style={{ flex: 1 }} />
        {speaker && (
          <div style={{ display: "flex", alignItems: "center", gap: 5, fontFamily: "var(--font-mono)", fontSize: 10, color: speaker === "interviewer" ? IV : CX }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: "currentColor", animation: "speak-pulse 0.8s ease-in-out infinite" }} />
            {speaker === "interviewer" ? "Interviewer speaking" : "Candidate speaking"}
          </div>
        )}
        {isLoading && !speaker && <Loader2 style={{ width: 12, height: 12, color: "var(--mute)", animation: "spin 1s linear infinite" }} />}
        {started && !ended && (
          <>
            <button type="button" onClick={togglePlay} className="btn" style={{ fontSize: 12, padding: "4px 10px", gap: 5 }}>
              {isPlaying ? <Pause style={{ width: 12, height: 12 }} /> : <Play style={{ width: 12, height: 12 }} />}
              {isPlaying ? "Pause" : "Play"}
            </button>
            <button type="button" onClick={exchangeOnce} disabled={!!speaker || isPlaying} className="btn btn--ghost" style={{ fontSize: 12, padding: "4px 10px", gap: 5 }}>
              <StepForward style={{ width: 12, height: 12 }} />Step
            </button>
          </>
        )}
        <button type="button" onClick={endSession} className="btn" style={{ fontSize: 12, padding: "4px 10px", gap: 5 }}>
          <X style={{ width: 12, height: 12 }} />End
        </button>
      </header>

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <div
          ref={containerRef}
          onMouseMove={e => { const r = e.currentTarget.getBoundingClientRect(); setHumanCursor({ x: e.clientX - r.left, y: e.clientY - r.top }); }}
          onMouseLeave={() => setHumanCursor(null)}
          style={{ flex: 1, minHeight: 0, minWidth: 0, position: "relative" }}
        >
          <Whiteboard ref={whiteboardRef} onChange={(_els: WhiteboardElements, _s: WhiteboardAppState) => {}} />

          <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden" }}>
            {ivCursor.visible && <Cursor x={ivCursor.x} y={ivCursor.y} color={IV} label="INTERVIEWER" />}
            {cxCursor.visible && <Cursor x={cxCursor.x} y={cxCursor.y} color={CX} label="CANDIDATE" />}
            {humanCursor && (
              <div style={{ position: "absolute", left: humanCursor.x + 14, top: humanCursor.y - 2 }}>
                <div style={{ background: HU, color: "#0D1A10", fontFamily: "var(--font-mono)", fontSize: 8, fontWeight: 700, padding: "1px 4px", borderRadius: 2, letterSpacing: "0.06em" }}>YOU</div>
              </div>
            )}
          </div>

          {!started && (
            <div style={{ position: "absolute", inset: 0, background: "color-mix(in srgb, var(--bg) 85%, transparent)", backdropFilter: "blur(3px)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, zIndex: 10 }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.12em" }}>AI vs AI · Voice</div>
              <div style={{ fontSize: 20, fontWeight: 600, color: "var(--ink)", letterSpacing: "-0.02em", maxWidth: 420, textAlign: "center", lineHeight: 1.25 }}>{questionTitle}</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute-2)", textAlign: "center", maxWidth: "38ch", lineHeight: 1.65 }}>
                Two AIs interview each other. Architecture builds on the whiteboard as they discuss.
              </div>
              <div style={{ display: "flex", gap: 18, marginTop: 4 }}>
                {([["INTERVIEWER", IV], ["CANDIDATE", CX], ["YOU", HU]] as const).map(([l, c]) => (
                  <div key={l} style={{ display: "flex", alignItems: "center", gap: 5, fontFamily: "var(--font-mono)", fontSize: 10, color: c }}>
                    <div style={{ width: 7, height: 7, borderRadius: "50%", background: c }} />{l}
                  </div>
                ))}
              </div>
              <button type="button" onClick={beginAndPlay} style={{ marginTop: 8, display: "inline-flex", alignItems: "center", gap: 10, padding: "11px 26px", borderRadius: 8, background: "var(--accent)", color: "var(--accent-ink)", border: "none", fontSize: 14, fontWeight: 600, cursor: "pointer" }}>
                <Play style={{ width: 16, height: 16 }} />Start Interview
              </button>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute-2)" }}>Audio starts on click</div>
            </div>
          )}
        </div>

        {/* Compact transcript */}
        <aside style={{ width: 256, flexShrink: 0, display: "flex", flexDirection: "column", borderLeft: "1px solid var(--line)", background: "var(--bg-2)" }}>
          <div style={{ flexShrink: 0, padding: "7px 12px 6px", borderBottom: "1px solid var(--line)", display: "flex", gap: 14 }}>
            {(["interviewer", "candidate"] as const).map(r => (
              <div key={r} style={{ display: "flex", alignItems: "center", gap: 4, fontFamily: "var(--font-mono)", fontSize: 9, textTransform: "uppercase", letterSpacing: "0.08em", color: r === "interviewer" ? IV : CX }}>
                <div style={{ width: 4, height: 4, borderRadius: "50%", background: "currentColor" }} />{r}
              </div>
            ))}
          </div>
          <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "8px 10px 6px", display: "flex", flexDirection: "column", gap: 4 }}>
            {transcript.length === 0
              ? <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-read)", fontStyle: "italic", fontSize: 12, color: "var(--mute-2)", padding: "24px 0", textAlign: "center" }}>Conversation will appear here</div>
              : transcript.map((msg, i) => {
                  const isIv = msg.role === "interviewer";
                  return (
                    <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: isIv ? "flex-start" : "flex-end" }}>
                      <div style={{
                        maxWidth: "96%", padding: "5px 9px", fontSize: 12, lineHeight: 1.45, whiteSpace: "pre-wrap",
                        borderRadius: isIv ? "2px 7px 7px 7px" : "7px 2px 7px 7px",
                        background: isIv ? "var(--surf)" : "var(--bg)",
                        border: `1px solid ${isIv ? "var(--line)" : "var(--line-2)"}`,
                        borderLeft: isIv ? `2px solid ${IV}` : undefined,
                        borderRight: !isIv ? `2px solid ${CX}` : undefined,
                        color: "var(--ink-2)",
                      }}>
                        {msg.content}
                      </div>
                    </div>
                  );
                })
            }
            {isLoading && <div style={{ display: "flex", alignItems: "center", gap: 5, padding: "3px 2px" }}><Loader2 style={{ width: 10, height: 10, color: "var(--mute)", animation: "spin 1s linear infinite" }} /><span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--mute)" }}>Thinking…</span></div>}
            {error && <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--bad)", padding: "3px 2px" }}>{error}</div>}
            {ended && <div style={{ textAlign: "center", padding: "10px 0", fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Interview ended</div>}
            <div ref={transcriptEndRef} />
          </div>
        </aside>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes speak-pulse { 0%,100%{ opacity:1; } 50%{ opacity:0.2; } }
      `}</style>
    </div>
  );
}

function Cursor({ x, y, color, label }: { x: number; y: number; color: string; label: string }) {
  return (
    <div style={{ position: "absolute", left: x, top: y, transform: "translate(-1px,-1px)", transition: "left 0.1s ease-out, top 0.1s ease-out" }}>
      <svg width="13" height="17" viewBox="0 0 13 17" fill="none">
        <path d="M1.5 1.5L11 6.5L6.5 8.5L5 13.5L1.5 1.5Z" fill={color} stroke="#0B0C0E" strokeWidth="1" strokeLinejoin="round" />
      </svg>
      <div style={{ position: "absolute", left: 13, top: 0, background: color, color: color === IV ? "#1A1408" : "#0D1520", fontFamily: "var(--font-mono)", fontSize: 8, fontWeight: 700, padding: "1px 4px", borderRadius: 2, whiteSpace: "nowrap", letterSpacing: "0.06em" }}>
        {label}
      </div>
    </div>
  );
}
