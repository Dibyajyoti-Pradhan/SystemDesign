"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
// Direct import (no dynamic) so forwardRef on Whiteboard works — dynamic() wrappers
// don't forward refs to the inner component, which broke whiteboardRef.current.
import { Whiteboard, type WhiteboardHandle, type WhiteboardElements, type WhiteboardAppState } from "@/components/Whiteboard";
import { type WhiteboardElement } from "@/components/WhiteboardCanvas";
import { Play, Pause, StepForward, X, Loader2, Bot, MessageSquarePlus, Send, Clock, PanelsTopLeft, PanelLeft } from "lucide-react";

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

interface DrawBox {
  id: string;
  label: string;
  c?: number;
  r?: number;
  shape?: "rect" | "circle";
  replicas?: number;
  style?: "note";
}
type DrawArrowFlow = "read" | "write" | "async" | "error" | "control";
interface DrawArrow { from: string; to: string; label?: string; flow?: DrawArrowFlow; }
interface DrawPanel {
  id: "requirements" | "scale" | "apis" | "datamodel" | "functional" | "nonfunctional";
  lines: string[];
  append: boolean;
}
interface DrawMove { id: string; c: number; r: number; }
interface DrawCmd {
  boxes?: DrawBox[];
  arrows?: DrawArrow[];
  panels?: DrawPanel[];
  move?: DrawMove[];
  remove?: string[];
  focus?: string[] | "all";
}

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

// ---------------------------------------------------------------------------
// Panel zones — drawn directly on the whiteboard (so they pan/zoom along with
// the architecture, the way real whiteboard notes would). The Requirements
// zone is chromeless (no bg/title decoration); the model emits the
// hierarchical "Requirements: / Functional: / Non-Functional:" header inline
// so it reads as a natural left-column note. Other panels keep the framed
// label style so they're visually distinct categories.
// ---------------------------------------------------------------------------

/** Width (world-px) the panel column occupies. Architecture starts past it
 *  (GRID_X = 310). Exposed so the canvas can reserve the same band when
 *  auto-fitting, keeping the architecture from overlapping the panels. */
const PANEL_COLUMN_RESERVED_PX = 320;

const PANEL_ZONES: Record<string, { x: number; y: number; w: number; h: number; title: string; color: string }> = {
  requirements:  { x: 20,  y: 20,  w: 280, h: 230, title: "Requirements",  color: "#E7E8EA" },
  scale:         { x: 20,  y: 264, w: 260, h: 150, title: "Scale / BOE",   color: "#7DA7C9" },
  apis:          { x: 20,  y: 428, w: 280, h: 240, title: "APIs",          color: "#D4A574" },
  datamodel:     { x: 20,  y: 682, w: 260, h: 130, title: "Data Model",    color: "#C9A07A" },
  // Legacy aliases — fold any FN/NFN-era panel ids back into requirements.
  functional:    { x: 20,  y: 20,  w: 280, h: 230, title: "Requirements",  color: "#E7E8EA" },
  nonfunctional: { x: 20,  y: 20,  w: 280, h: 230, title: "Requirements",  color: "#E7E8EA" },
};

const PANEL_TITLE_FONT = 11;
const PANEL_LINE_FONT  = 12;
const PANEL_LINE_H     = 18;
const PANEL_CONTENT_Y  = 38; // y offset inside framed panels (when title is shown)

function buildPanelElements(panel: DrawPanel, existingLineCount: number): WhiteboardElement[] {
  const zone = PANEL_ZONES[panel.id];
  if (!zone) return [];
  const els: WhiteboardElement[] = [];

  const chromeless = zone.title === "";
  const lineTopOffset = chromeless ? 16 : PANEL_CONTENT_Y;

  // Text lines first (so they appear before the frame, like a real person
  // writes notes then optionally boxes them). The bg/title chrome comes after.
  panel.lines.forEach((line, i) => {
    const lineIdx = existingLineCount + i;
    const yPos = zone.y + lineTopOffset + lineIdx * PANEL_LINE_H;
    if (yPos + PANEL_LINE_FONT > zone.y + zone.h) return;
    els.push({
      id: `panel:${panel.id}:line:${lineIdx}`,
      type: "text",
      x: zone.x + 8, y: yPos,
      color: "#E7E8EA",
      strokeWidth: 1,
      text: line,
      fontSize: PANEL_LINE_FONT,
      wrapWidth: zone.w - 16,
    } as WhiteboardElement);
  });

  if (!chromeless && (!panel.append || existingLineCount === 0)) {
    els.push({
      id: `panel:${panel.id}:bg`,
      type: "rect",
      x: zone.x, y: zone.y,
      width: zone.w, height: zone.h,
      color: zone.color,
      fill: `${zone.color}18`,
      strokeWidth: 1.2,
    } as WhiteboardElement);
    els.push({
      id: `panel:${panel.id}:title`,
      type: "text",
      x: zone.x + 8, y: zone.y + 16,
      color: zone.color,
      strokeWidth: 1,
      text: zone.title.toUpperCase(),
      fontSize: PANEL_TITLE_FONT,
    } as WhiteboardElement);
  }

  return els;
}

// ---------------------------------------------------------------------------
// Grid → pixel layout (shifted right to avoid panel column)
// ---------------------------------------------------------------------------

const CELL_W = 190;
const CELL_H = 90;
const GRID_X = 310;  // shifted right to avoid left panel column
const GRID_Y = 56;
const BOX_W = 154;
const BOX_H = 52;

interface NodeRect { x: number; y: number; cx: number; cy: number; w: number; h: number; }

function gridBox(c: number, r: number): NodeRect {
  const x = GRID_X + c * CELL_W;
  const y = GRID_Y + r * CELL_H;
  return { x, y, cx: x + BOX_W / 2, cy: y + BOX_H / 2, w: BOX_W, h: BOX_H };
}

/** World-space center for cursor pre-positioning. Approximate — the cursor
 *  overlay lives in container-pixel space, but our existing cursor logic
 *  already treats lastDrawTargetRef as raw coords. Good enough for the
 *  "reach before draw" effect at typical zoom levels. */
function elementCenter(el: WhiteboardElement): { x: number; y: number } | null {
  if (el.type === "rect") return { x: el.x + el.width / 2, y: el.y + el.height / 2 };
  if (el.type === "circle") return { x: el.x, y: el.y };
  if (el.type === "arrow") return { x: (el.x + el.endX) / 2, y: (el.y + el.endY) / 2 };
  if (el.type === "text") return { x: el.x + 20, y: el.y };
  return null;
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
  panelLineCountRef: React.MutableRefObject<Map<string, number>>,
  whiteboardRef: React.RefObject<WhiteboardHandle | null>,
): { elements: WhiteboardElement[]; firstNewPos: { x: number; y: number } | null } {
  const color = role === "interviewer" ? "#D4A574" : "#7DA7C9";
  const els: WhiteboardElement[] = [];
  let firstNewPos: { x: number; y: number } | null = null;

  // Process panels — ALWAYS REPLACE semantics. The AI is unreliable about
  // append vs. replace (often re-sends the same lines under append:true,
  // producing stacked overlapping text). So we ignore the append flag: any
  // panel emit blows away the old version and renders the new lines fresh.
  for (const panel of (cmd.panels ?? [])) {
    whiteboardRef.current?.removeElementsByPrefix(`panel:${panel.id}:`);
    panelLineCountRef.current.set(panel.id, 0);
    const panelEls = buildPanelElements({ ...panel, append: false }, 0);
    els.push(...panelEls);
    panelLineCountRef.current.set(panel.id, panel.lines.length);
  }

  // Auto-layout counter for boxes the model emitted without c/r — flow them
  // row-major starting at col 1 so they're always visible somewhere sensible.
  let autoSlot = nodeMap.size;
  const AUTO_COLS = 5;

  // Process MOVE commands first — repositions existing boxes. We update the
  // nodeMap then re-emit the rect+label elements (removing the old ones from
  // the canvas). Arrows reroute on next render against the new nodeMap.
  for (const m of (cmd.move ?? [])) {
    if (!nodeMap.has(m.id)) continue;
    const cValid = typeof m.c === "number" && Number.isFinite(m.c);
    const rValid = typeof m.r === "number" && Number.isFinite(m.r);
    if (!cValid || !rValid) continue;
    const c = Math.max(0, Math.min(5, m.c));
    const r = Math.max(0, Math.min(4, m.r));
    const rect = gridBox(c, r);
    nodeMap.set(m.id, rect);
    whiteboardRef.current?.removeElementsByPrefix(`box-${m.id}`);
    whiteboardRef.current?.removeElementsByPrefix(`lbl-${m.id}`);
    // We don't have shape/label info here — assume rect with original label.
    // If the model needs to change the label too, it should remove+re-add.
  }

  // REMOVE commands — drop boxes/arrows/panels by id-prefix.
  for (const id of (cmd.remove ?? [])) {
    nodeMap.delete(id);
    whiteboardRef.current?.removeElementsByPrefix(`box-${id}`);
    whiteboardRef.current?.removeElementsByPrefix(`lbl-${id}`);
    whiteboardRef.current?.removeElementsByPrefix(`arr-${id}-`);
    // Arrows TO this id — we re-emit all arrows each turn anyway; for the
    // current turn we just drop the source-side prefix matches.
  }

  // Process boxes
  for (const box of (cmd.boxes ?? [])) {
    if (nodeMap.has(box.id)) continue;
    let c: number;
    let r: number;
    const cValid = typeof box.c === "number" && Number.isFinite(box.c);
    const rValid = typeof box.r === "number" && Number.isFinite(box.r);
    if (cValid && rValid) {
      c = Math.max(0, Math.min(5, box.c as number));
      r = Math.max(0, Math.min(4, box.r as number));
    } else {
      c = 1 + (autoSlot % AUTO_COLS);
      r = Math.floor(autoSlot / AUTO_COLS);
      autoSlot++;
    }
    const rect = gridBox(c, r);
    nodeMap.set(box.id, rect);
    usedLabels.add(box.label);
    if (!firstNewPos) firstNewPos = { x: rect.cx, y: rect.cy };

    const isCircle = box.shape === "circle";
    const replicas = Math.max(1, Math.min(3, box.replicas ?? 1));

    if (isCircle) {
      // Circle is centered in the cell; use BOX_H/2 as radius for compactness.
      const radius = Math.min(BOX_W, BOX_H) / 2 - 2;
      els.push({
        id: `box-${box.id}`,
        type: "circle",
        x: rect.cx, y: rect.cy,
        radius,
        color,
        fill: box.style === "note" ? `${color}18` : "transparent",
        strokeWidth: box.style === "note" ? 1 : 1.8,
        replicas,
      } as WhiteboardElement);
      // Centered text inside circle
      els.push({
        id: `lbl-${box.id}`,
        type: "text",
        x: rect.cx - radius + 6, y: rect.cy + 4,
        color, strokeWidth: 1,
        text: box.label, fontSize: 12,
        wrapWidth: radius * 2 - 12,
      } as WhiteboardElement);
    } else {
      els.push({
        id: `box-${box.id}`,
        type: "rect",
        x: rect.x, y: rect.y,
        width: BOX_W, height: BOX_H,
        color,
        fill: box.style === "note" ? `${color}18` : "transparent",
        strokeWidth: box.style === "note" ? 1 : 1.8,
        replicas,
      } as WhiteboardElement);
      els.push({
        id: `lbl-${box.id}`,
        type: "text",
        x: rect.x + 8, y: rect.y + 18,
        color, strokeWidth: 1,
        text: box.label, fontSize: 12,
        wrapWidth: BOX_W - 16,
      } as WhiteboardElement);
    }
  }

  // Process arrows — endpoints recomputed each time so MOVE commands above
  // automatically reroute existing connections.
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
      label: arrow.label,
      flow: arrow.flow,
    } as WhiteboardElement);
  }

  return { elements: els, firstNewPos };
}

// ---------------------------------------------------------------------------
// TTS — chunked by sentence so long turns don't hit the browser's TTS watchdog
// (Chrome cuts speech after ~10-15s of audio; Safari has its own quirks).
// ---------------------------------------------------------------------------

const SENTENCE_RE = /[^.!?]+[.!?]+(\s+|$)|[^.!?]+$/g;

function splitForSpeech(text: string): string[] {
  const trimmed = text.trim();
  if (!trimmed) return [];
  const matches = trimmed.match(SENTENCE_RE);
  if (!matches) return [trimmed];
  const out: string[] = [];
  let buffer = "";
  for (const raw of matches) {
    const piece = raw.trim();
    if (!piece) continue;
    // Combine very short sentences with the next chunk so the cadence stays natural.
    if (buffer.length + piece.length < 180) {
      buffer = buffer ? `${buffer} ${piece}` : piece;
    } else {
      if (buffer) out.push(buffer);
      buffer = piece;
    }
    if (buffer.length >= 220) {
      out.push(buffer);
      buffer = "";
    }
  }
  if (buffer) out.push(buffer);
  return out;
}

let watchdogTimer: ReturnType<typeof setInterval> | null = null;

/** Some browsers (notably Chrome) pause speechSynthesis after ~15s. The fix is
 * to call resume() periodically while we're speaking, which silently reschedules
 * the watchdog. Harmless in Safari. */
function startWatchdog() {
  if (watchdogTimer) return;
  watchdogTimer = setInterval(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    if (window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
      window.speechSynthesis.pause();
      window.speechSynthesis.resume();
    }
  }, 10_000);
}

function stopWatchdog() {
  if (watchdogTimer) {
    clearInterval(watchdogTimer);
    watchdogTimer = null;
  }
}

function pickVoice(role: "interviewer" | "candidate"): SpeechSynthesisVoice | undefined {
  if (typeof window === "undefined" || !window.speechSynthesis) return undefined;
  const voices = window.speechSynthesis.getVoices();
  const isQuality = (v: SpeechSynthesisVoice) =>
    /premium|enhanced|neural/i.test(v.name);
  const englishVoices = voices.filter((v) => v.lang.startsWith("en"));
  const candidates = englishVoices
    .map((v) => ({
      v,
      score:
        (isQuality(v) ? 10 : 0) +
        (role === "interviewer"
          ? (/Samantha|Karen|Allison|Ava|Susan|Serena/.test(v.name) ? 6 : 0)
          : (/Daniel|Alex|Tom|Aaron|Fred|Oliver/.test(v.name) ? 6 : 0)) +
        (v.lang === "en-US" ? 4 : v.lang === "en-GB" ? 3 : 1) +
        (v.localService ? 2 : 0),
    }))
    .sort((a, b) => b.score - a.score);
  return candidates[0]?.v;
}

// ---------------------------------------------------------------------------
// Persistent audio element — Safari's autoplay policy only "unlocks" the
// specific HTMLMediaElement that gets played() inside a user gesture. So we
// keep ONE element across the whole interview and just swap its src.
// ---------------------------------------------------------------------------
let sharedAudio: HTMLAudioElement | null = null;
let audioUnlocked = false;

/** Call from a user-gesture handler (Start click) to unlock audio playback
 *  for the rest of the session. Plays a tiny silent buffer. */
export function primeAudio() {
  if (typeof window === "undefined") return;
  if (!sharedAudio) sharedAudio = new Audio();
  if (audioUnlocked) return;
  // 0.05s silent MP3 — just enough for play() to succeed within the gesture.
  sharedAudio.src =
    "data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU3LjgzLjEwMAAAAAAAAAAAAAAA//tQxAADB8AhSmxhIIEVCSiJrDCQBTcu3UrAIwUdkRgQbFAZC1CQEwTJ9mjRvBA4UOLD8nKVOWfh+UlK3z/177OXrfOdKl7pyn3Xf//FJAhVcoYf6XU0AAAAA";
  sharedAudio.volume = 0.001;
  sharedAudio.play().then(() => {
    audioUnlocked = true;
    sharedAudio!.volume = 1;
  }).catch(() => { /* silent */ });
}

// ---------------------------------------------------------------------------
// Cancel handle so the parent can barge in (End button, Ask modal) without
// holding refs to individual audio elements / synth utterances.
// ---------------------------------------------------------------------------
let currentSpeechCancel: (() => void) | null = null;

function cancelCurrentSpeech() {
  if (currentSpeechCancel) {
    try { currentSpeechCancel(); } catch {}
    currentSpeechCancel = null;
  }
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  stopWatchdog();
}

function speakWithWebSpeech(
  chunks: string[],
  role: "interviewer" | "candidate",
  onEnd: () => void,
): () => void {
  let cancelled = false;
  const voice = pickVoice(role);
  const rate = role === "interviewer" ? 0.96 : 0.98;
  const pitch = role === "interviewer" ? 1.0 : 0.93;
  startWatchdog();
  let i = 0;
  const speakNext = () => {
    if (cancelled || i >= chunks.length) { stopWatchdog(); if (!cancelled) onEnd(); return; }
    const u = new SpeechSynthesisUtterance(chunks[i++]);
    u.rate = rate; u.pitch = pitch;
    if (voice) u.voice = voice;
    u.onend = () => { if (!cancelled) speakNext(); };
    u.onerror = () => { cancelled = true; stopWatchdog(); onEnd(); };
    try { window.speechSynthesis.speak(u); }
    catch { cancelled = true; stopWatchdog(); onEnd(); }
  };
  speakNext();
  return () => { cancelled = true; window.speechSynthesis?.cancel(); stopWatchdog(); };
}

/**
 * Speak a turn using ElevenLabs TTS (Brian for interviewer, Liam for candidate).
 * Falls back to Web Speech if the route 503s (no key) or the network fails.
 */
function speakTurn(
  text: string,
  role: "interviewer" | "candidate",
  onPreSpeak: () => void,
  onEnd: () => void,
) {
  if (typeof window === "undefined") {
    onPreSpeak();
    onEnd();
    return;
  }
  const chunks = splitForSpeech(text);
  if (chunks.length === 0) {
    onPreSpeak();
    onEnd();
    return;
  }

  onPreSpeak();

  let cancelled = false;
  let currentAudio: HTMLAudioElement | null = null;
  const abort = new AbortController();

  const cancel = () => {
    cancelled = true;
    abort.abort();
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.src = "";
      currentAudio = null;
    }
  };
  currentSpeechCancel = cancel;

  const finish = () => {
    if (currentSpeechCancel === cancel) currentSpeechCancel = null;
    onEnd();
  };

  // Sequential ElevenLabs fetch + playback. We pipeline by pre-fetching ONE
  // chunk ahead while the current one plays — keeps audio gap-free without
  // rate-limiting the upstream (full parallel triggers HTTP 500 from
  // ElevenLabs Turbo above ~3 concurrent requests).
  const playSequentially = async () => {
    // Reuse a single audio element so Safari's autoplay-unlock from the
    // Start-click gesture carries across all chunks.
    if (!sharedAudio) sharedAudio = new Audio();
    sharedAudio.volume = 1;

    const fetchChunk = (chunk: string) =>
      fetch("/api/tts/stream", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text: chunk, persona: role }),
        signal: abort.signal,
      }).then(async (r) => {
        if (!r.ok) throw new Error(`tts ${r.status}`);
        return r.blob();
      });

    // Pipeline: kick off chunk 0, then loop play-N while pre-fetching N+1.
    let pendingNext: Promise<Blob> | null = chunks.length > 0 ? fetchChunk(chunks[0]) : null;

    for (let idx = 0; idx < chunks.length; idx++) {
      if (cancelled) return;
      let blob: Blob;
      try {
        blob = await pendingNext!;
      } catch (e) {
        if (cancelled) return;
        const remaining = chunks.slice(idx);
        abort.abort();
        const cancelWebSpeech = speakWithWebSpeech(remaining, role, finish);
        currentSpeechCancel = () => {
          cancelled = true;
          cancelWebSpeech();
          if (currentSpeechCancel) currentSpeechCancel = null;
        };
        return;
      }

      // Prefetch the next chunk while this one plays.
      pendingNext = idx + 1 < chunks.length ? fetchChunk(chunks[idx + 1]) : null;

      if (cancelled) return;
      const url = URL.createObjectURL(blob);
      const audio = sharedAudio!;
      audio.src = url;
      currentAudio = audio;
      await new Promise<void>((resolve) => {
        audio.onended = () => { URL.revokeObjectURL(url); currentAudio = null; resolve(); };
        audio.onerror = () => { URL.revokeObjectURL(url); currentAudio = null; resolve(); };
        audio.onpause = () => {
          // Only resolve on actual pause-by-cancel, not on natural end.
          if (cancelled) { URL.revokeObjectURL(url); currentAudio = null; resolve(); }
        };
        audio.play().catch(() => resolve());
      });
    }
    finish();
  };

  void playSequentially();
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
  const panelLineCountRef = useRef<Map<string, number>>(new Map());

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

  // Spectator "Ask" modal state — lets the human viewer inject a question that
  // gets persisted as a steer and consumed by the next exchange.
  const [askOpen, setAskOpen] = useState(false);
  const [askTarget, setAskTarget] = useState<"interviewer" | "candidate" | "both">("both");
  const [askText, setAskText] = useState("");
  const [askSubmitting, setAskSubmitting] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const wasPlayingRef = useRef(false);

  // End-session state — scoring takes ~10-20s so the user needs visible feedback
  // that something is happening, not just a frozen UI.
  const [isEnding, setIsEnding] = useState(false);
  const isEndingRef = useRef(false);

  // Elapsed-time clock. Starts when Start Interview is clicked. Just a vanity
  // counter for the observer — gives the meeting a real-time feel.
  const [elapsedSec, setElapsedSec] = useState(0);
  const startTimeRef = useRef<number | null>(null);
  useEffect(() => {
    if (!started || ended) return;
    if (startTimeRef.current === null) startTimeRef.current = Date.now();
    const id = setInterval(() => {
      if (startTimeRef.current !== null) {
        setElapsedSec(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }
    }, 1000);
    return () => clearInterval(id);
  }, [started, ended]);
  const elapsedStr = `${Math.floor(elapsedSec / 60).toString().padStart(2, "0")}:${(elapsedSec % 60).toString().padStart(2, "0")}`;

  // Hide-panels toggle — gives the architecture diagram the full canvas width
  // when the observer wants to focus on the boxes.
  const [hidePanels, setHidePanels] = useState(false);

  function openAsk() {
    wasPlayingRef.current = isPlayingRef.current;
    setIsPlaying(false);
    isPlayingRef.current = false;
    cancelCurrentSpeech();
    setSpeaker(null);
    setAskError(null);
    setAskOpen(true);
  }

  function closeAsk(resume: boolean) {
    setAskOpen(false);
    setAskText("");
    setAskError(null);
    if (resume && wasPlayingRef.current && !endedRef.current) {
      setIsPlaying(true);
      isPlayingRef.current = true;
      if (!isSteppingRef.current && !speaker) void exchangeAndSpeak();
    }
  }

  async function submitAsk() {
    const text = askText.trim();
    if (!text) return;
    setAskSubmitting(true);
    setAskError(null);
    try {
      const res = await fetch("/api/interview/ai-vs-ai/steer", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, content: text, target: askTarget }),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`Steer failed: ${res.status} ${body}`);
      }
      closeAsk(true);
    } catch (e) {
      setAskError(e instanceof Error ? e.message : "Failed to send");
    } finally {
      setAskSubmitting(false);
    }
  }

  const isPlayingRef = useRef(false);
  const endedRef = useRef(initialEnded);
  const isSteppingRef = useRef(false);
  const lastDrawTargetRef = useRef<{ x: number; y: number } | undefined>(undefined);
  const titleDrawnRef = useRef(false);
  const pendingCxRef = useRef<{
    text: string;
    elements: WhiteboardElement[];
    addTranscript: () => void;
  } | null>(null);
  // Prefetch of the NEXT /exchange — kicked off the moment the candidate's
  // audio starts so the silent gap between turns collapses from a full
  // ~30s Claude round-trip to roughly the first-byte time of one stream.
  const pendingNextExchangeRef = useRef<{ promise: Promise<Response>; abort: AbortController } | null>(null);

  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);
  useEffect(() => { endedRef.current = ended; }, [ended]);
  useEffect(() => { transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [transcript.length]);

  // Replay persisted DRAW blocks onto the whiteboard on mount. Lets an observer
  // who joins mid-interview (or reloads the page) see the diagram-so-far
  // instantly, without re-running the whole exchange loop.
  const replayedRef = useRef(false);
  useEffect(() => {
    if (replayedRef.current) return;
    if (!whiteboardRef.current) return;
    if (initialTranscript.length === 0) return;
    replayedRef.current = true;

    const allEls: WhiteboardElement[] = [];
    for (const msg of initialTranscript) {
      if (msg.role !== "interviewer" && msg.role !== "candidate") continue;
      const els = collectDrawElements(msg.content, msg.role);
      allEls.push(...els);
    }
    if (allEls.length === 0) return;
    drawTitleOnce();
    // Use restoreElements so they appear instantly (no fade-in for replay).
    whiteboardRef.current.restoreElements(allEls);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  // Build element list from a raw response string. Does NOT call setTranscript.
  function collectDrawElements(raw: string, role: "interviewer" | "candidate"): WhiteboardElement[] {
    if (whiteboardRef.current) drawTitleOnce();

    const cmd = parseDrawCmd(raw);
    if (!cmd) return [];
    const hasContent =
      (cmd.boxes?.length ?? 0) > 0 ||
      (cmd.arrows?.length ?? 0) > 0 ||
      (cmd.panels?.length ?? 0) > 0 ||
      (cmd.move?.length ?? 0) > 0 ||
      (cmd.remove?.length ?? 0) > 0 ||
      cmd.focus != null;
    if (!hasContent) return [];

    const { elements, firstNewPos } = buildElements(cmd, role, nodeMapRef.current, usedLabelsRef.current, panelLineCountRef, whiteboardRef);
    if (firstNewPos) lastDrawTargetRef.current = firstNewPos;

    // Focus command — pan/zoom the camera. For v1 we always fit the full
    // content (ignores partial target list); good enough for "step back from
    // the board to show the whole picture" semantics.
    if (cmd.focus) {
      setTimeout(() => whiteboardRef.current?.fitToContent(), 200);
    }

    return elements;
  }

  function applyDrawingProgressive(elements: WhiteboardElement[], spokenText: string) {
    if (!whiteboardRef.current || elements.length === 0) return;
    const wordCount = spokenText.split(/\s+/).filter(Boolean).length;
    const estimatedMs = Math.max(4000, (wordCount / 150) * 60 * 1000); // ~150 wpm
    const usableMs = estimatedMs * 0.8; // don't go past 80% of speech
    elements.forEach((el, i) => {
      const addDelay = i === 0
        ? 800
        : Math.min(1500 + (i / elements.length) * usableMs, usableMs);
      // Move the role cursor to the element's center ~250ms BEFORE the
      // element actually renders, so the cursor "arrives" first — matches how
      // a real engineer reaches the spot, then draws.
      const target = elementCenter(el);
      if (target) {
        const preMoveAt = Math.max(0, addDelay - 250);
        setTimeout(() => { lastDrawTargetRef.current = target; }, preMoveAt);
      }
      setTimeout(() => {
        whiteboardRef.current?.addElements([el]);
      }, addDelay);
    });
  }

  const fetchExchange = useCallback((): { promise: Promise<Response>; abort: AbortController } => {
    const abort = new AbortController();
    const promise = fetch("/api/interview/ai-vs-ai/exchange", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ sessionId, voiceMode: true }),
      signal: abort.signal,
    });
    return { promise, abort };
  }, [sessionId]);

  const kickOffNextExchange = useCallback(() => {
    if (endedRef.current) return;
    if (!isPlayingRef.current) return;
    if (pendingNextExchangeRef.current) return;
    // Server reads transcript at request start; the prior turn's persistence
    // happens server-side just after Claude's generation finishes (well before
    // its TTS plays out client-side), so prefetching here sees fresh state.
    pendingNextExchangeRef.current = fetchExchange();
  }, [fetchExchange]);

  const cancelPendingNextExchange = useCallback(() => {
    const p = pendingNextExchangeRef.current;
    if (!p) return;
    try { p.abort.abort(); } catch {}
    pendingNextExchangeRef.current = null;
  }, []);

  const exchangeAndSpeak = useCallback(async () => {
    if (isSteppingRef.current || endedRef.current) return;
    isSteppingRef.current = true;
    setIsLoading(true);
    setError(null);
    pendingCxRef.current = null;

    try {
      // Use the prefetched stream if available (kicked off when the prior
      // candidate's audio started). Otherwise fetch fresh.
      let active = pendingNextExchangeRef.current;
      pendingNextExchangeRef.current = null;
      if (!active) active = fetchExchange();
      const res = await active.promise;
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

        if (isEnd) {
          // Wrap-up turn: play the TTS so the observer hears the sign-off,
          // then auto-trigger the score flow. Don't gate on isPlaying — the
          // interview is ending, the wrap-up audio should always play.
          setTranscript(prev => [...prev, { role: "interviewer", content: spoken, ts: Date.now() }]);
          whiteboardRef.current?.addElements(drawElements);
          isSteppingRef.current = false;
          setIsLoading(false);
          setSpeaker("interviewer");
          speakTurn(
            spoken,
            "interviewer",
            () => { /* transcript already added */ },
            () => {
              setSpeaker(null);
              setEnded(true); endedRef.current = true;
              setIsPlaying(false); isPlayingRef.current = false;
              // Brief beat before the scoring overlay so the audio's last
              // syllable doesn't get clipped by the route transition.
              setTimeout(() => { void autoScoreAndExit(); }, 700);
            },
          );
          return;
        }

        isSteppingRef.current = false;
        setIsLoading(false);

        if (!isPlayingRef.current) {
          // Not playing — add to transcript immediately and apply drawing
          setTranscript(prev => [...prev, { role: "interviewer", content: spoken, ts: Date.now() }]);
          whiteboardRef.current?.addElements(drawElements);
          return;
        }

        setSpeaker("interviewer");
        applyDrawingProgressive(drawElements, spoken);
        speakTurn(spoken, "interviewer",
          () => { setTranscript(prev => [...prev, { role: "interviewer", content: spoken, ts: Date.now() }]); },
          () => {
            setSpeaker(null);
            const pending = pendingCxRef.current;
            pendingCxRef.current = null;
            if (pending && isPlayingRef.current && !endedRef.current) {
              setSpeaker("candidate");
              applyDrawingProgressive(pending.elements, pending.text);
              // Kick off the NEXT exchange in parallel with this candidate's
              // audio. The server-side persistence of the current turn has
              // already finished by now, so the prefetch sees up-to-date
              // transcript state.
              kickOffNextExchange();
              speakTurn(pending.text, "candidate",
                () => { pending.addTranscript(); },
                () => {
                  setSpeaker(null);
                  if (isPlayingRef.current && !endedRef.current) {
                    // 1200ms beat between candidate finishing and interviewer
                    // pushing back. Real interviewers take ~1-2s to process
                    // before responding — the prior 150ms made it sound like
                    // an oral exam, not a conversation.
                    setTimeout(() => { void exchangeAndSpeak(); }, 1200);
                  }
                },
              );
            } else if (isPlayingRef.current && !endedRef.current) {
              setTimeout(() => { void exchangeAndSpeak(); }, 1200);
            }
          },
        );
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
        const ts = Date.now();
        if (!isPlayingRef.current) {
          // Not playing — add transcript immediately and apply drawing
          setTranscript(prev => [...prev, { role: "candidate", content: spokenCx, ts }]);
          whiteboardRef.current?.addElements(elements);
        } else {
          // Playing — store text, elements, and a transcript callback.
          // The IV onEnd block will call addTranscript() right as CX speech begins.
          pendingCxRef.current = {
            text: spokenCx,
            elements,
            addTranscript: () => {
              setTranscript(prev => [...prev, { role: "candidate", content: spokenCx, ts }]);
            },
          };
        }
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
  }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  function beginAndPlay() {
    // Unlock the persistent audio element inside this user-gesture handler
    // — Safari blocks .play() outside gesture context, so we prime it now.
    primeAudio();
    setStarted(true); setIsPlaying(true); isPlayingRef.current = true;
    void exchangeAndSpeak();
  }
  function togglePlay() {
    if (ended) return;
    if (isPlaying) {
      setIsPlaying(false); isPlayingRef.current = false;
      cancelCurrentSpeech(); setSpeaker(null);
      // Drop the prefetched stream — it's stale once paused; we'll re-fetch
      // on resume so the response reflects any steers added during the pause.
      cancelPendingNextExchange();
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
  /**
   * Run the score endpoint and redirect, without a confirm dialog. Used when
   * the interviewer naturally signs off with <<INTERVIEW_END>> so the
   * observer sees the same "Scoring → score page" flow they'd get from End.
   */
  async function autoScoreAndExit() {
    if (isEndingRef.current) return;
    await runScoreAndExit();
  }

  async function runScoreAndExit() {
    isEndingRef.current = true;
    setIsEnding(true);
    setError(null);
    cancelCurrentSpeech();
    cancelPendingNextExchange();
    setSpeaker(null);

    const payload = {
      transcriptHistory: transcript.map((m) => ({ role: m.role, content: m.content })),
    };

    try {
      const res = await fetch(`/api/interview/session/${sessionId}/score`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        let detail = `${res.status}`;
        try {
          const j = await res.json();
          if (j?.error) detail = `${res.status} · ${j.error}`;
        } catch { /* ignore */ }
        throw new Error(`Score failed: ${detail}`);
      }
      router.push(`/interview/sessions/${sessionId}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
      isEndingRef.current = false;
      setIsEnding(false);
    }
  }

  async function endSession() {
    if (isEndingRef.current) return;
    if (!confirm("End session and score it?")) return;
    isEndingRef.current = true;
    setIsEnding(true);
    setError(null);
    setIsPlaying(false);
    isPlayingRef.current = false;
    cancelCurrentSpeech();
    cancelPendingNextExchange();
    setSpeaker(null);

    const payload = {
      transcriptHistory: transcript.map((m) => ({ role: m.role, content: m.content })),
    };

    try {
      const res = await fetch(`/api/interview/session/${sessionId}/score`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        // Try to surface server-supplied error message.
        let detail = `${res.status}`;
        try {
          const j = await res.json();
          if (j?.error) detail = `${res.status} · ${j.error}`;
        } catch { /* ignore */ }
        throw new Error(`Score failed: ${detail}`);
      }
      router.push(`/interview/sessions/${sessionId}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
      isEndingRef.current = false;
      setIsEnding(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "var(--bg)", color: "var(--ink)", fontFamily: "var(--font-ui)" }}>
      <header style={{ flexShrink: 0, height: 44, display: "flex", alignItems: "center", padding: "0 18px", borderBottom: "1px solid var(--line)", gap: 12, background: "var(--bg)" }}>
        <Bot style={{ width: 14, height: 14, color: "var(--mute)" }} />
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.1em" }}>AI vs AI</span>
        <span style={{ color: "var(--subtle)" }}>›</span>
        <b style={{ color: "var(--ink-2)", fontWeight: 500, fontSize: 13, letterSpacing: "-0.005em", maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{questionTitle}</b>
        {started && (
          <div
            title="Elapsed interview time"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: elapsedSec > 28 * 60 ? "var(--bad)" : elapsedSec > 24 * 60 ? "var(--accent)" : "var(--mute-2)",
              border: "1px solid var(--line)",
              borderRadius: 4,
              padding: "2px 7px",
              marginLeft: 4,
              letterSpacing: "0.02em",
            }}
          >
            <Clock style={{ width: 11, height: 11, opacity: 0.75 }} />
            {elapsedStr} <span style={{ opacity: 0.5 }}>/ 30:00</span>
          </div>
        )}
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
            <button
              type="button"
              onClick={() => setHidePanels((v) => !v)}
              className="btn btn--ghost"
              style={{ fontSize: 12, padding: "4px 8px", gap: 5 }}
              title={hidePanels ? "Show requirements / scale / api / data-model panels" : "Hide panels to maximize the diagram"}
            >
              {hidePanels ? <PanelLeft style={{ width: 12, height: 12 }} /> : <PanelsTopLeft style={{ width: 12, height: 12 }} />}
            </button>
            <button type="button" onClick={togglePlay} className="btn" style={{ fontSize: 12, padding: "4px 10px", gap: 5 }}>
              {isPlaying ? <Pause style={{ width: 12, height: 12 }} /> : <Play style={{ width: 12, height: 12 }} />}
              {isPlaying ? "Pause" : "Play"}
            </button>
            <button type="button" onClick={exchangeOnce} disabled={!!speaker || isPlaying} className="btn btn--ghost" style={{ fontSize: 12, padding: "4px 10px", gap: 5 }}>
              <StepForward style={{ width: 12, height: 12 }} />Step
            </button>
            <button
              type="button"
              onClick={openAsk}
              className="btn"
              style={{
                fontSize: 12,
                padding: "4px 10px",
                gap: 5,
                color: "var(--accent)",
                borderColor: "color-mix(in srgb, var(--accent) 35%, var(--line-2))",
              }}
              title="Pause and inject a question for the interviewer, the candidate, or both"
            >
              <MessageSquarePlus style={{ width: 12, height: 12 }} />Ask
            </button>
          </>
        )}
        <button
          type="button"
          onClick={endSession}
          disabled={isEnding}
          className="btn"
          style={{
            fontSize: 12,
            padding: "4px 10px",
            gap: 5,
            opacity: isEnding ? 0.55 : 1,
            cursor: isEnding ? "wait" : "pointer",
          }}
        >
          {isEnding ? (
            <Loader2 style={{ width: 12, height: 12, animation: "spin 1s linear infinite" }} />
          ) : (
            <X style={{ width: 12, height: 12 }} />
          )}
          {isEnding ? "Saving…" : "End"}
        </button>
      </header>

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <div
          ref={containerRef}
          onMouseMove={e => { const r = e.currentTarget.getBoundingClientRect(); setHumanCursor({ x: e.clientX - r.left, y: e.clientY - r.top }); }}
          onMouseLeave={() => setHumanCursor(null)}
          style={{ flex: 1, minHeight: 0, minWidth: 0, position: "relative" }}
        >
          <Whiteboard
            ref={whiteboardRef}
            hidePanels={hidePanels}
            reservedLeft={hidePanels ? 0 : PANEL_COLUMN_RESERVED_PX}
            onChange={(_els: WhiteboardElements, _s: WhiteboardAppState) => {}}
          />

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
                        {stripMeta(msg.content)}
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

      {isEnding && (
        <div
          role="status"
          aria-live="polite"
          aria-label="Scoring the interview"
          style={{
            position: "fixed",
            inset: 0,
            background: "color-mix(in srgb, var(--bg) 80%, transparent)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 110,
          }}
        >
          <div
            style={{
              padding: "20px 26px",
              background: "var(--surf)",
              border: "1px solid var(--line-2)",
              borderRadius: 12,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 12,
              minWidth: 260,
              boxShadow: "0 18px 40px rgba(0,0,0,0.45)",
            }}
          >
            <Loader2 style={{ width: 22, height: 22, color: "var(--accent)", animation: "spin 1s linear infinite" }} />
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>Scoring the interview…</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute)", textAlign: "center", maxWidth: "32ch", lineHeight: 1.6 }}>
              This runs a full pass over the transcript and usually takes 10–20s.
            </div>
          </div>
        </div>
      )}

      {askOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Inject a question"
          onClick={(e) => { if (e.target === e.currentTarget && !askSubmitting) closeAsk(true); }}
          style={{
            position: "fixed",
            inset: 0,
            background: "color-mix(in srgb, var(--bg) 75%, transparent)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: 16,
          }}
        >
          <div
            style={{
              width: "min(520px, 100%)",
              background: "var(--surf)",
              border: "1px solid var(--line-2)",
              borderRadius: 12,
              padding: "18px 18px 14px",
              display: "flex",
              flexDirection: "column",
              gap: 12,
              boxShadow: "0 18px 40px rgba(0,0,0,0.45)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <MessageSquarePlus style={{ width: 14, height: 14, color: "var(--accent)" }} />
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                Spectator · Ask
              </span>
              <div style={{ flex: 1 }} />
              <button
                type="button"
                onClick={() => !askSubmitting && closeAsk(true)}
                className="btn btn--ghost"
                style={{ padding: "2px 6px", fontSize: 11 }}
                disabled={askSubmitting}
              >
                <X style={{ width: 12, height: 12 }} />
              </button>
            </div>

            <div style={{ display: "flex", gap: 6 }}>
              {(["interviewer", "candidate", "both"] as const).map((t) => {
                const active = askTarget === t;
                const color = t === "interviewer" ? IV : t === "candidate" ? CX : "var(--ink-2)";
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setAskTarget(t)}
                    style={{
                      flex: 1,
                      padding: "6px 10px",
                      borderRadius: 6,
                      border: `1px solid ${active ? color : "var(--line-2)"}`,
                      background: active ? "color-mix(in srgb, currentColor 12%, var(--surf))" : "var(--surf-2)",
                      color: active ? color : "var(--mute)",
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      cursor: "pointer",
                    }}
                  >
                    {t}
                  </button>
                );
              })}
            </div>

            <textarea
              autoFocus
              value={askText}
              onChange={(e) => setAskText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  if (!askSubmitting) void submitAsk();
                } else if (e.key === "Escape" && !askSubmitting) {
                  closeAsk(true);
                }
              }}
              placeholder={
                askTarget === "interviewer"
                  ? "e.g. Push harder on the partitioning strategy."
                  : askTarget === "candidate"
                    ? "e.g. Don't move on yet — what about hot-key candidates like celebrities?"
                    : "e.g. Spend the next exchange on failure modes and idempotency."
              }
              style={{
                minHeight: 90,
                resize: "vertical",
                padding: "10px 12px",
                background: "var(--bg-2)",
                color: "var(--ink)",
                border: "1px solid var(--line-2)",
                borderRadius: 8,
                fontFamily: "var(--font-ui)",
                fontSize: 13,
                lineHeight: 1.5,
                outline: "none",
              }}
            />

            {askError && (
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--bad)" }}>{askError}</div>
            )}

            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ flex: 1, fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute-2)" }}>
                ⌘↵ to send · Esc to cancel
              </span>
              <button
                type="button"
                onClick={() => closeAsk(true)}
                className="btn btn--ghost"
                style={{ fontSize: 12, padding: "5px 10px" }}
                disabled={askSubmitting}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={submitAsk}
                disabled={askSubmitting || !askText.trim()}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  padding: "6px 12px",
                  borderRadius: 6,
                  background: "var(--accent)",
                  color: "var(--accent-ink)",
                  border: "1px solid var(--accent)",
                  cursor: askSubmitting || !askText.trim() ? "not-allowed" : "pointer",
                  opacity: askSubmitting || !askText.trim() ? 0.55 : 1,
                }}
              >
                {askSubmitting ? <Loader2 style={{ width: 12, height: 12, animation: "spin 1s linear infinite" }} /> : <Send style={{ width: 12, height: 12 }} />}
                Send & resume
              </button>
            </div>
          </div>
        </div>
      )}

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
