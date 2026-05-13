"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from "react";
import {
  MousePointer2,
  Pencil,
  Square,
  ArrowRight,
  Type as TypeIcon,
  Eraser,
  Hand,
  Undo2,
  Redo2,
  Trash2,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Data model
// ---------------------------------------------------------------------------

export type ElementType = "pen" | "rect" | "arrow" | "text" | "circle";

/** Semantic categories for arrows. Picks a color so the observer can tell
 *  flows apart in a busy diagram. */
export type ArrowFlow = "read" | "write" | "async" | "error" | "control";

export interface BaseElement {
  id: string;
  type: ElementType;
  x: number;
  y: number;
  color: string;
  strokeWidth: number;
}

export interface PenElement extends BaseElement {
  type: "pen";
  points: { x: number; y: number }[];
}

export interface RectElement extends BaseElement {
  type: "rect";
  width: number;
  height: number;
  fill: string;
  /** When > 1, render N-1 offset ghost copies behind this rect to convey
   *  "replicated component" (e.g., Worker × 5). Capped at 3 visually. */
  replicas?: number;
}

export interface CircleElement extends BaseElement {
  type: "circle";
  /** Radius in world units. */
  radius: number;
  fill: string;
  replicas?: number;
}

export interface ArrowElement extends BaseElement {
  type: "arrow";
  endX: number;
  endY: number;
  /** Optional text rendered near the arrow midpoint (e.g., "POST /upload"). */
  label?: string;
  /** Semantic flow type — picks the arrow color and the label tint. */
  flow?: ArrowFlow;
}

export interface TextElement extends BaseElement {
  type: "text";
  text: string;
  fontSize: number;
  /** When set, the text auto-wraps to this width (in world px) using
   *  character-width approximation. Used for box labels. */
  wrapWidth?: number;
  /** When true and the text contains \n, render each line on its own row.
   *  Default true. */
  multiline?: boolean;
}

export type WhiteboardElement =
  | PenElement
  | RectElement
  | ArrowElement
  | TextElement
  | CircleElement;

export type Tool = "select" | "pen" | "rect" | "arrow" | "text" | "eraser" | "hand";

// ---------------------------------------------------------------------------
// JSON export — compact shape Claude consumes
// ---------------------------------------------------------------------------

interface CompactRecord {
  type: ElementType;
  x: number;
  y: number;
  w?: number;
  h?: number;
  text?: string;
  points?: { x: number; y: number }[];
  endX?: number;
  endY?: number;
}

export function getCanvasJSON(elements: readonly WhiteboardElement[]): string {
  if (!elements || elements.length === 0) return "[]";
  const compact: CompactRecord[] = elements.map((el) => {
    const base: CompactRecord = {
      type: el.type,
      x: Math.round(el.x),
      y: Math.round(el.y),
    };
    if (el.type === "rect") {
      base.w = Math.round(el.width);
      base.h = Math.round(el.height);
    } else if (el.type === "circle") {
      // Reuse w as diameter for the export shape.
      base.w = Math.round(el.radius * 2);
    } else if (el.type === "arrow") {
      base.endX = Math.round(el.endX);
      base.endY = Math.round(el.endY);
    } else if (el.type === "text") {
      base.text = el.text;
    } else if (el.type === "pen") {
      base.points = el.points.map((p) => ({
        x: Math.round(p.x),
        y: Math.round(p.y),
      }));
    }
    return base;
  });
  return JSON.stringify(compact);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CANVAS_BG = "#111111";
const COLORS = ["#f0f0f0", "#ff6b6b", "#69db7c", "#74c0fc", "#ffd43b", "#da77f2"];
const STROKE_THIN = 2;
const STROKE_THICK = 5;
const DEFAULT_COLOR = "#f0f0f0";
const DEFAULT_FONT_SIZE = 16;
const ERASER_RADIUS = 10;
const ARROWHEAD_LEN = 10;
const ARROWHEAD_ANGLE = (25 * Math.PI) / 180;
const UNDO_LIMIT = 50;

function newId(): string {
  return Math.random().toString(36).slice(2, 11);
}

interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

function elementBounds(el: WhiteboardElement): Bounds {
  if (el.type === "rect") {
    const x1 = Math.min(el.x, el.x + el.width);
    const x2 = Math.max(el.x, el.x + el.width);
    const y1 = Math.min(el.y, el.y + el.height);
    const y2 = Math.max(el.y, el.y + el.height);
    return { minX: x1, minY: y1, maxX: x2, maxY: y2 };
  }
  if (el.type === "arrow") {
    return {
      minX: Math.min(el.x, el.endX),
      minY: Math.min(el.y, el.endY),
      maxX: Math.max(el.x, el.endX),
      maxY: Math.max(el.y, el.endY),
    };
  }
  if (el.type === "circle") {
    return {
      minX: el.x - el.radius,
      minY: el.y - el.radius,
      maxX: el.x + el.radius,
      maxY: el.y + el.radius,
    };
  }
  if (el.type === "text") {
    const w = el.text.length * el.fontSize * 0.6;
    const h = el.fontSize * 1.2;
    return { minX: el.x, minY: el.y - h, maxX: el.x + w, maxY: el.y };
  }
  // pen
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of el.points) {
    const ax = el.x + p.x;
    const ay = el.y + p.y;
    if (ax < minX) minX = ax;
    if (ay < minY) minY = ay;
    if (ax > maxX) maxX = ax;
    if (ay > maxY) maxY = ay;
  }
  if (!isFinite(minX)) {
    minX = el.x;
    minY = el.y;
    maxX = el.x;
    maxY = el.y;
  }
  return { minX, minY, maxX, maxY };
}

function pointInBounds(px: number, py: number, b: Bounds, pad = 4): boolean {
  return (
    px >= b.minX - pad &&
    px <= b.maxX + pad &&
    py >= b.minY - pad &&
    py <= b.maxY + pad
  );
}

function circleIntersectsBounds(
  cx: number,
  cy: number,
  r: number,
  b: Bounds,
): boolean {
  const nx = Math.max(b.minX, Math.min(cx, b.maxX));
  const ny = Math.max(b.minY, Math.min(cy, b.maxY));
  const dx = cx - nx;
  const dy = cy - ny;
  return dx * dx + dy * dy <= r * r;
}

function translateElement(
  el: WhiteboardElement,
  dx: number,
  dy: number,
): WhiteboardElement {
  if (el.type === "arrow") {
    return { ...el, x: el.x + dx, y: el.y + dy, endX: el.endX + dx, endY: el.endY + dy };
  }
  return { ...el, x: el.x + dx, y: el.y + dy };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface WhiteboardHandle {
  addElements: (elements: WhiteboardElement[]) => void;
  removeElementsByPrefix: (prefix: string) => void;
  /** Smoothly pan & zoom so every non-panel element fits in the viewport. */
  fitToContent: () => void;
  /** Add elements WITHOUT the draw-in animation. Used on page reload to
   *  rebuild the whiteboard from the persisted transcript instantly. */
  restoreElements: (elements: WhiteboardElement[]) => void;
}

export interface WhiteboardCanvasProps {
  onChange?: (elements: WhiteboardElement[]) => void;
  readOnly?: boolean;
  /** Skip rendering of all "panel:*" elements (Requirements/Scale/APIs/etc.) —
   * lets the AI-vs-AI observer focus on the architecture diagram alone. */
  hidePanels?: boolean;
  /** Reserve this many screen-px on the left of the viewport for an external
   * overlay (e.g., the AI-vs-AI Requirements/Scale/APIs panel column). The
   * fit-to-content logic skips this band when auto-zooming so the architecture
   * never lands underneath the overlay. */
  reservedLeft?: number;
}

interface TextEditState {
  worldX: number;
  worldY: number;
  value: string;
  /** If set, the commit replaces the text of this existing element instead of
   *  creating a new one (used by double-click-to-edit on box labels). */
  editingId?: string;
}

export const WhiteboardCanvas = forwardRef<WhiteboardHandle, WhiteboardCanvasProps>(
function WhiteboardCanvas({ onChange, readOnly = false, hidePanels = false, reservedLeft = 0 }: WhiteboardCanvasProps, ref) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Elements + undo/redo stored in refs to avoid re-render storms.
  const elementsRef = useRef<WhiteboardElement[]>([]);
  const undoStackRef = useRef<WhiteboardElement[][]>([]);
  const redoStackRef = useRef<WhiteboardElement[][]>([]);

  // Pan offset (in screen pixels) and zoom scale.
  const panRef = useRef({ x: 0, y: 0 });
  const zoomRef = useRef(1);

  // Pointer / drag state.
  const draftRef = useRef<WhiteboardElement | null>(null);
  const dragRef = useRef<{
    mode: "none" | "draw" | "move" | "pan" | "erase";
    startScreenX: number;
    startScreenY: number;
    lastScreenX: number;
    lastScreenY: number;
    selectedId: string | null;
    /** When dragging a `box-<X>` rect/circle, these are the ids of paired
     *  `lbl-<X>...` text elements that should move with the box. */
    partnerIds: string[];
    movedDuringDrag: boolean;
  }>({
    mode: "none",
    startScreenX: 0,
    startScreenY: 0,
    lastScreenX: 0,
    lastScreenY: 0,
    selectedId: null,
    partnerIds: [],
    movedDuringDrag: false,
  });

  const [tool, setTool] = useState<Tool>("select");
  const toolRef = useRef<Tool>("select");
  useEffect(() => {
    toolRef.current = tool;
  }, [tool]);

  const [color, setColor] = useState<string>(DEFAULT_COLOR);
  const colorRef = useRef<string>(DEFAULT_COLOR);
  useEffect(() => {
    colorRef.current = color;
  }, [color]);

  const [strokeWidth, setStrokeWidth] = useState<number>(STROKE_THIN);
  const strokeWidthRef = useRef<number>(STROKE_THIN);
  useEffect(() => {
    strokeWidthRef.current = strokeWidth;
  }, [strokeWidth]);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedIdRef = useRef<string | null>(null);
  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  const [textEdit, setTextEdit] = useState<TextEditState | null>(null);
  const textInputRef = useRef<HTMLInputElement>(null);
  const [, setRenderTick] = useState(0);
  const requestRedraw = useCallback(() => {
    setRenderTick((t) => (t + 1) & 0x3fffffff);
  }, []);

  // Focus the text input whenever it mounts — more reliable than autoFocus.
  useEffect(() => {
    if (textEdit) {
      // rAF so the input is fully in the DOM before we focus.
      const id = requestAnimationFrame(() => textInputRef.current?.focus());
      return () => cancelAnimationFrame(id);
    }
  }, [textEdit]);

  // Canvas pixel size tracking (for HiDPI).
  const sizeRef = useRef({ width: 0, height: 0, dpr: 1 });

  // Mirror the hidePanels prop into a ref so the draw loop (called from rAF)
  // sees the latest value without needing to re-bind drawElement.
  const hidePanelsRef = useRef(hidePanels);
  useEffect(() => {
    hidePanelsRef.current = hidePanels;
    setRenderTick((t) => (t + 1) & 0x3fffffff);
  }, [hidePanels]);

  // Mirror reservedLeft into a ref so fitToContent (called from setTimeout,
  // rAF, the imperative handle, etc.) always reads the latest value. Trigger
  // a re-fit on change so toggling the side panel column smoothly expands or
  // contracts the architecture diagram.
  const reservedLeftRef = useRef(reservedLeft);
  useEffect(() => {
    reservedLeftRef.current = reservedLeft;
  }, [reservedLeft]);

  // ---------------------------------------------------------------------
  // Notify parent on changes
  // ---------------------------------------------------------------------
  const notifyChange = useCallback(() => {
    if (onChange) onChange(elementsRef.current.slice());
  }, [onChange]);

  // ---------------------------------------------------------------------
  // Undo / Redo
  // ---------------------------------------------------------------------
  const snapshot = useCallback((): WhiteboardElement[] => {
    return elementsRef.current.map((el) => {
      if (el.type === "pen") return { ...el, points: el.points.map((p) => ({ ...p })) };
      return { ...el };
    });
  }, []);

  const pushUndo = useCallback(() => {
    const snap = snapshot();
    undoStackRef.current.push(snap);
    if (undoStackRef.current.length > UNDO_LIMIT) undoStackRef.current.shift();
    redoStackRef.current = [];
  }, [snapshot]);

  const undo = useCallback(() => {
    const prev = undoStackRef.current.pop();
    if (!prev) return;
    redoStackRef.current.push(snapshot());
    elementsRef.current = prev;
    setSelectedId(null);
    requestRedraw();
    notifyChange();
  }, [notifyChange, requestRedraw, snapshot]);

  const redo = useCallback(() => {
    const next = redoStackRef.current.pop();
    if (!next) return;
    undoStackRef.current.push(snapshot());
    elementsRef.current = next;
    setSelectedId(null);
    requestRedraw();
    notifyChange();
  }, [notifyChange, requestRedraw, snapshot]);

  const clearAll = useCallback(() => {
    if (elementsRef.current.length === 0) return;
    pushUndo();
    elementsRef.current = [];
    setSelectedId(null);
    requestRedraw();
    notifyChange();
  }, [notifyChange, pushUndo, requestRedraw]);

  // ---------------------------------------------------------------------
  // Draw-in animations — boxes scale + fade in, arrows stroke-draw, text fades.
  // Each animation has a target START_TIME (may be in the future if staggered)
  // and a DURATION. Frames keep requesting redraws while the map is non-empty.
  // ---------------------------------------------------------------------
  const animStartRef = useRef<Map<string, number>>(new Map());
  const BOX_ANIM_MS = 280;
  const ARROW_ANIM_MS = 460;
  const TEXT_ANIM_MS = 220;

  const getAnimProgress = useCallback((elId: string, durationMs: number): number => {
    // Returns:
    //   -1 → never animated (no entry) → draw at full state
    //    0 → animation queued but not yet started (stagger) → don't render yet
    //  0..1 → in progress, apply easing
    //    1 → completed (entry removed) → draw at full state
    const start = animStartRef.current.get(elId);
    if (start === undefined) return -1;
    const now = performance.now();
    if (now < start) return 0;
    const elapsed = now - start;
    if (elapsed >= durationMs) {
      animStartRef.current.delete(elId);
      return 1;
    }
    return elapsed / durationMs;
  }, []);

  const pumpAnimationsRef = useRef<number | null>(null);
  const pumpAnimations = useCallback(() => {
    if (animStartRef.current.size === 0) {
      pumpAnimationsRef.current = null;
      return;
    }
    requestRedraw();
    pumpAnimationsRef.current = requestAnimationFrame(pumpAnimations);
  }, [requestRedraw]);

  const startPumpIfIdle = useCallback(() => {
    if (pumpAnimationsRef.current === null) {
      pumpAnimationsRef.current = requestAnimationFrame(pumpAnimations);
    }
  }, [pumpAnimations]);

  useEffect(() => {
    return () => {
      if (pumpAnimationsRef.current !== null) {
        cancelAnimationFrame(pumpAnimationsRef.current);
        pumpAnimationsRef.current = null;
      }
    };
  }, []);

  // ---------------------------------------------------------------------
  // Auto-fit — re-centers and zooms so all non-panel content stays visible.
  // The AI places architecture boxes on a grid that can extend beyond the
  // viewport at c=4 or c=5. When that happens we animate the pan/zoom so a
  // real-time observer always sees the whole diagram, the way a candidate
  // would step back from the whiteboard.
  // ---------------------------------------------------------------------
  const computeContentBbox = useCallback(() => {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    let any = false;
    for (const el of elementsRef.current) {
      // Skip the left-column panels — they're always anchored to the viewport
      // and shouldn't drive zoom.
      if (el.id.startsWith("panel:")) continue;
      any = true;
      if (el.type === "rect") {
        if (el.x < minX) minX = el.x;
        if (el.y < minY) minY = el.y;
        if (el.x + el.width > maxX) maxX = el.x + el.width;
        if (el.y + el.height > maxY) maxY = el.y + el.height;
      } else if (el.type === "arrow") {
        const x1 = Math.min(el.x, el.endX), x2 = Math.max(el.x, el.endX);
        const y1 = Math.min(el.y, el.endY), y2 = Math.max(el.y, el.endY);
        if (x1 < minX) minX = x1;
        if (y1 < minY) minY = y1;
        if (x2 > maxX) maxX = x2;
        if (y2 > maxY) maxY = y2;
      } else if (el.type === "text") {
        // Approximate text bbox — fontSize × ~0.6/char width.
        const w = el.text.length * el.fontSize * 0.6;
        if (el.x < minX) minX = el.x;
        if (el.y - el.fontSize < minY) minY = el.y - el.fontSize;
        if (el.x + w > maxX) maxX = el.x + w;
        if (el.y > maxY) maxY = el.y;
      } else if (el.type === "pen") {
        for (const p of el.points) {
          if (p.x < minX) minX = p.x;
          if (p.y < minY) minY = p.y;
          if (p.x > maxX) maxX = p.x;
          if (p.y > maxY) maxY = p.y;
        }
      }
    }
    if (!any) return null;
    return { minX, minY, maxX, maxY };
  }, []);

  // Animation token — every new pan/zoom animation increments this; in-flight
  // animations bail when they see a newer token. Prevents stale animations
  // from overwriting fresh ones (e.g., when many addElements fire in a row).
  const panZoomTokenRef = useRef(0);
  // Debounce token for the out-of-view re-fit triggered by addElements.
  const outOfViewTimerRef = useRef<number | null>(null);
  useEffect(() => () => {
    if (outOfViewTimerRef.current !== null) {
      clearTimeout(outOfViewTimerRef.current);
      outOfViewTimerRef.current = null;
    }
  }, []);
  const animatePanZoom = useCallback(
    (targetPanX: number, targetPanY: number, targetZoom: number, durationMs = 480) => {
      const startPanX = panRef.current.x;
      const startPanY = panRef.current.y;
      const startZoom = zoomRef.current;
      // Skip the animation if we're already close enough.
      if (
        Math.abs(targetPanX - startPanX) < 1 &&
        Math.abs(targetPanY - startPanY) < 1 &&
        Math.abs(targetZoom - startZoom) < 0.01
      ) {
        return;
      }
      const myToken = ++panZoomTokenRef.current;
      const startTime = performance.now();
      const tick = (now: number) => {
        if (panZoomTokenRef.current !== myToken) return; // superseded
        const t = Math.min(1, (now - startTime) / durationMs);
        // ease-out cubic — feels like a hand stepping back from the board
        const ease = 1 - Math.pow(1 - t, 3);
        panRef.current.x = startPanX + (targetPanX - startPanX) * ease;
        panRef.current.y = startPanY + (targetPanY - startPanY) * ease;
        zoomRef.current = startZoom + (targetZoom - startZoom) * ease;
        requestRedraw();
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    },
    [requestRedraw],
  );

  const FIT_PADDING = 40;
  const fitToContent = useCallback(() => {
    const bbox = computeContentBbox();
    if (!bbox) return;
    const { width, height } = sizeRef.current;
    if (width <= 0 || height <= 0) return;
    const contentW = bbox.maxX - bbox.minX;
    const contentH = bbox.maxY - bbox.minY;
    if (contentW <= 0 || contentH <= 0) return;
    const reserved = reservedLeftRef.current;
    const availW = Math.max(80, width - reserved - FIT_PADDING);
    const availH = Math.max(80, height - FIT_PADDING * 2);
    const zoomX = availW / contentW;
    const zoomY = availH / contentH;
    // Cap at 1 so we never up-zoom past native size; floor at 0.55 so panel
    // text (rendered as world content) stays legible.
    const targetZoom = Math.max(0.55, Math.min(1, zoomX, zoomY));
    const targetPanX = reserved + (availW - contentW * targetZoom) / 2 - bbox.minX * targetZoom;
    const targetPanY = (height - contentH * targetZoom) / 2 - bbox.minY * targetZoom;
    animatePanZoom(targetPanX, targetPanY, targetZoom);
  }, [animatePanZoom, computeContentBbox]);

  // Imperative API — lets parent inject AI-drawn elements programmatically.
  useImperativeHandle(ref, () => ({
    addElements(newEls: WhiteboardElement[]) {
      pushUndo();
      elementsRef.current = [...elementsRef.current, ...newEls];
      // Schedule draw-in animations. Stagger non-panel elements so a row of
      // boxes appears one at a time, the way a candidate would place them
      // while talking. Panel decoration (bg/title) skips the animation; panel
      // text lines get a short fade so the eye catches them.
      const now = performance.now();
      let stagger = 0;
      for (const el of newEls) {
        if (el.id.startsWith("panel:") && (el.id.endsWith(":bg") || el.id.endsWith(":title"))) {
          // skip — panel chrome appears instantly
          continue;
        }
        const isPanelLine = el.id.startsWith("panel:") && el.id.includes(":line:");
        const elStagger = isPanelLine ? 40 : 90;
        animStartRef.current.set(el.id, now + stagger);
        stagger += elStagger;
      }
      startPumpIfIdle();
      requestRedraw();
      notifyChange();
      // After paint, debounce a single out-of-view re-fit. Without the
      // debounce, multiple addElements calls within a few hundred ms each
      // schedule their own fit-check, and the resulting concurrent pan/zoom
      // animations step on each other — boxes added early can drift off
      // screen by the time the last fit settles.
      const justAddedAnyBox = newEls.some((e) => !e.id.startsWith("panel:"));
      if (justAddedAnyBox) {
        if (outOfViewTimerRef.current !== null) clearTimeout(outOfViewTimerRef.current);
        outOfViewTimerRef.current = window.setTimeout(() => {
          outOfViewTimerRef.current = null;
          const bbox = computeContentBbox();
          if (!bbox) return;
          const { width, height } = sizeRef.current;
          const z = zoomRef.current;
          const px = panRef.current.x;
          const py = panRef.current.y;
          const onScreenLeft = bbox.minX * z + px;
          const onScreenRight = bbox.maxX * z + px;
          const onScreenTop = bbox.minY * z + py;
          const onScreenBottom = bbox.maxY * z + py;
          const fudge = 8;
          const reserved = reservedLeftRef.current;
          const outOfView =
            onScreenRight > width - fudge ||
            onScreenBottom > height - fudge ||
            onScreenLeft < reserved + fudge ||
            onScreenTop < 0 + fudge;
          if (outOfView) fitToContent();
        }, 400);
      }
    },
    removeElementsByPrefix(prefix: string) {
      const before = elementsRef.current;
      const after = before.filter(el => !el.id.startsWith(prefix));
      if (after.length === before.length) return; // nothing to remove
      // Push pre-removal snapshot so undo restores the removed elements.
      undoStackRef.current.push(before.map(el => {
        if (el.type === "pen") return { ...el, points: el.points.map(p => ({ ...p })) };
        return { ...el };
      }));
      if (undoStackRef.current.length > UNDO_LIMIT) undoStackRef.current.shift();
      redoStackRef.current = [];
      elementsRef.current = after;
      requestRedraw();
      notifyChange();
    },
    fitToContent,
    restoreElements(newEls: WhiteboardElement[]) {
      elementsRef.current = [...elementsRef.current, ...newEls];
      requestRedraw();
      notifyChange();
      // After paint, fit the camera once so a reloaded interview shows the
      // full state, even if boxes ran off the original viewport.
      setTimeout(() => fitToContent(), 50);
    },
  }), [pushUndo, requestRedraw, notifyChange, computeContentBbox, fitToContent]);

  // ---------------------------------------------------------------------
  // Drawing
  // ---------------------------------------------------------------------
  const drawArrowhead = useCallback(
    (
      ctx: CanvasRenderingContext2D,
      fromX: number,
      fromY: number,
      toX: number,
      toY: number,
      color: string,
    ) => {
      const angle = Math.atan2(toY - fromY, toX - fromX);
      const x1 = toX - ARROWHEAD_LEN * Math.cos(angle - ARROWHEAD_ANGLE);
      const y1 = toY - ARROWHEAD_LEN * Math.sin(angle - ARROWHEAD_ANGLE);
      const x2 = toX - ARROWHEAD_LEN * Math.cos(angle + ARROWHEAD_ANGLE);
      const y2 = toY - ARROWHEAD_LEN * Math.sin(angle + ARROWHEAD_ANGLE);
      ctx.beginPath();
      ctx.moveTo(toX, toY);
      ctx.lineTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
    },
    [],
  );

  const drawElement = useCallback(
    (ctx: CanvasRenderingContext2D, el: WhiteboardElement, isSelected: boolean) => {
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = el.color;
      ctx.lineWidth = el.strokeWidth;

      // ---- Draw-in animation: figure out the per-element progress -------
      // Pick a duration per element type. Rect/arrow get longer; text fades.
      const animDuration =
        el.type === "arrow" ? ARROW_ANIM_MS :
        el.type === "rect"  ? BOX_ANIM_MS :
        el.type === "text"  ? TEXT_ANIM_MS :
        BOX_ANIM_MS;
      const rawT = getAnimProgress(el.id, animDuration);
      const isAnimating = rawT >= 0 && rawT < 1;
      // Skip rendering entirely if the animation hasn't fired yet (staggered start).
      if (rawT === 0) return;
      // Ease-out cubic
      const ease = (t: number) => 1 - Math.pow(1 - t, 3);
      const animT = isAnimating ? ease(rawT) : 1;

      if (el.type === "pen") {
        if (el.points.length === 0) return;
        ctx.beginPath();
        ctx.moveTo(el.x + el.points[0].x, el.y + el.points[0].y);
        for (let i = 1; i < el.points.length; i++) {
          ctx.lineTo(el.x + el.points[i].x, el.y + el.points[i].y);
        }
        ctx.stroke();
      } else if (el.type === "rect") {
        ctx.save();
        if (isAnimating) {
          const cx = el.x + el.width / 2;
          const cy = el.y + el.height / 2;
          const s = 0.86 + 0.14 * animT;
          ctx.globalAlpha = animT;
          ctx.translate(cx, cy);
          ctx.scale(s, s);
          ctx.translate(-cx, -cy);
        }
        // Replica ghost-stack: up to 2 offset duplicates behind the main rect.
        const stackCount = Math.max(0, Math.min(2, (el.replicas ?? 1) - 1));
        for (let i = stackCount; i >= 1; i--) {
          const ox = i * 6;
          const oy = -i * 6;
          ctx.save();
          ctx.globalAlpha = (ctx.globalAlpha ?? 1) * (0.45 - i * 0.12);
          if (el.fill && el.fill !== "transparent") {
            ctx.fillStyle = el.fill;
            ctx.fillRect(el.x + ox, el.y + oy, el.width, el.height);
          }
          ctx.strokeRect(el.x + ox, el.y + oy, el.width, el.height);
          ctx.restore();
        }
        if (el.fill && el.fill !== "transparent") {
          ctx.fillStyle = el.fill;
          ctx.fillRect(el.x, el.y, el.width, el.height);
        }
        ctx.strokeRect(el.x, el.y, el.width, el.height);
        ctx.restore();
      } else if (el.type === "circle") {
        ctx.save();
        if (isAnimating) {
          const s = 0.86 + 0.14 * animT;
          ctx.globalAlpha = animT;
          ctx.translate(el.x, el.y);
          ctx.scale(s, s);
          ctx.translate(-el.x, -el.y);
        }
        // Replica ghost-stack for circles
        const stackCount = Math.max(0, Math.min(2, (el.replicas ?? 1) - 1));
        for (let i = stackCount; i >= 1; i--) {
          const ox = i * 6;
          const oy = -i * 6;
          ctx.save();
          ctx.globalAlpha = (ctx.globalAlpha ?? 1) * (0.45 - i * 0.12);
          ctx.beginPath();
          ctx.arc(el.x + ox, el.y + oy, el.radius, 0, Math.PI * 2);
          if (el.fill && el.fill !== "transparent") {
            ctx.fillStyle = el.fill;
            ctx.fill();
          }
          ctx.stroke();
          ctx.restore();
        }
        ctx.beginPath();
        ctx.arc(el.x, el.y, el.radius, 0, Math.PI * 2);
        if (el.fill && el.fill !== "transparent") {
          ctx.fillStyle = el.fill;
          ctx.fill();
        }
        ctx.stroke();
        ctx.restore();
      } else if (el.type === "arrow") {
        // Flow-typed arrows use semantic colors so multiple flows are visually
        // distinct without changing the element shape.
        const flowColor =
          el.flow === "read"   ? "#7DA7C9" :   // info (blue)
          el.flow === "write"  ? "#D4A574" :   // accent (tan)
          el.flow === "async"  ? "#7FB48A" :   // good (green)
          el.flow === "error"  ? "#C9786A" :   // bad (red)
          el.flow === "control"? "#BDC1C6" :   // ink-2 (neutral)
          el.color;
        ctx.strokeStyle = flowColor;

        const lineT = Math.min(1, animT / 0.88);
        const drawX = el.x + (el.endX - el.x) * lineT;
        const drawY = el.y + (el.endY - el.y) * lineT;
        ctx.beginPath();
        ctx.moveTo(el.x, el.y);
        ctx.lineTo(drawX, drawY);
        ctx.stroke();
        if (animT > 0.88) {
          const headAlpha = Math.min(1, (animT - 0.88) / 0.12);
          ctx.save();
          ctx.globalAlpha = headAlpha;
          drawArrowhead(ctx, el.x, el.y, el.endX, el.endY, flowColor);
          ctx.restore();
        }
        // Arrow label — rendered at midpoint with a small dark backing so it
        // reads cleanly against the canvas. Appears in last third of animation.
        if (el.label && animT > 0.6) {
          ctx.save();
          ctx.globalAlpha = Math.min(1, (animT - 0.6) / 0.4);
          const mx = (el.x + el.endX) / 2;
          const my = (el.y + el.endY) / 2;
          ctx.font = `10px ui-sans-serif, system-ui, -apple-system, sans-serif`;
          ctx.textBaseline = "middle";
          ctx.textAlign = "center";
          const metrics = ctx.measureText(el.label);
          const padX = 4, padY = 2;
          const bw = metrics.width + padX * 2;
          const bh = 14 + padY;
          ctx.fillStyle = "#0B0C0E"; // bg
          ctx.fillRect(mx - bw / 2, my - bh / 2, bw, bh);
          ctx.fillStyle = flowColor;
          ctx.fillText(el.label, mx, my);
          ctx.restore();
        }
      } else if (el.type === "text") {
        ctx.save();
        if (isAnimating) ctx.globalAlpha = animT;
        ctx.fillStyle = el.color;
        ctx.font = `${el.fontSize}px ui-sans-serif, system-ui, -apple-system, sans-serif`;
        ctx.textBaseline = "alphabetic";
        // Multi-line support: split on \n, and if wrapWidth is set, wrap each
        // line greedily on word boundaries to fit the width.
        const lineHeight = el.fontSize * 1.3;
        const lines: string[] = [];
        const rawLines = (el.multiline === false) ? [el.text] : el.text.split(/\n/);
        for (const rawLine of rawLines) {
          if (!el.wrapWidth || el.wrapWidth <= 0) {
            lines.push(rawLine);
            continue;
          }
          const words = rawLine.split(/(\s+)/);
          let buf = "";
          for (const w of words) {
            const candidate = buf + w;
            if (ctx.measureText(candidate).width <= el.wrapWidth) {
              buf = candidate;
            } else {
              if (buf.trim()) lines.push(buf.trimEnd());
              buf = w.trimStart();
            }
          }
          if (buf.trim()) lines.push(buf.trimEnd());
        }
        for (let i = 0; i < lines.length; i++) {
          ctx.fillText(lines[i], el.x, el.y + i * lineHeight);
        }
        ctx.restore();
      }

      if (isSelected) {
        const b = elementBounds(el);
        ctx.save();
        ctx.strokeStyle = "#1971c2";
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 3]);
        ctx.strokeRect(
          b.minX - 4,
          b.minY - 4,
          b.maxX - b.minX + 8,
          b.maxY - b.minY + 8,
        );
        ctx.restore();
      }
    },
    [drawArrowhead],
  );

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const { width, height, dpr } = sizeRef.current;

    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = CANVAS_BG;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.restore();

    ctx.save();
    // DPR scaling + pan translation.
    const z = zoomRef.current;
    ctx.setTransform(dpr * z, 0, 0, dpr * z, panRef.current.x * dpr, panRef.current.y * dpr);

    void width;
    void height;

    const selId = selectedIdRef.current;
    for (const el of elementsRef.current) {
      // When hidePanels is on, skip the Requirements/Scale/APIs/Data-Model
      // left-column decorations so the architecture diagram has the full canvas.
      if (hidePanelsRef.current && el.id.startsWith("panel:")) continue;
      drawElement(ctx, el, el.id === selId);
    }
    if (draftRef.current) {
      drawElement(ctx, draftRef.current, false);
    }
    ctx.restore();
  }, [drawElement]);

  // Redraw whenever renderTick changes.
  useEffect(() => {
    draw();
  });

  // ---------------------------------------------------------------------
  // Resize handling
  // ---------------------------------------------------------------------
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const apply = () => {
      const rect = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const w = Math.max(1, Math.floor(rect.width));
      const h = Math.max(1, Math.floor(rect.height));
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      sizeRef.current = { width: w, height: h, dpr };
      draw();
    };

    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(container);
    return () => ro.disconnect();
  }, [draw]);

  // ---------------------------------------------------------------------
  // Coordinate helpers
  // ---------------------------------------------------------------------
  const screenToWorld = useCallback((clientX: number, clientY: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const sx = clientX - rect.left;
    const sy = clientY - rect.top;
    const z = zoomRef.current;
    return { x: (sx - panRef.current.x) / z, y: (sy - panRef.current.y) / z };
  }, []);

  // ---------------------------------------------------------------------
  // Hit testing
  // ---------------------------------------------------------------------
  const hitTest = useCallback((wx: number, wy: number): WhiteboardElement | null => {
    const els = elementsRef.current;
    for (let i = els.length - 1; i >= 0; i--) {
      const el = els[i];
      if (el.type === "circle") {
        // Precise hit-test for circles — bbox would treat corners as hits.
        const dx = wx - el.x;
        const dy = wy - el.y;
        const r = el.radius + 6; // small padding for easier grab
        if (dx * dx + dy * dy <= r * r) return el;
        continue;
      }
      if (pointInBounds(wx, wy, elementBounds(el), 6)) return el;
    }
    return null;
  }, []);

  // ---------------------------------------------------------------------
  // Pointer handlers
  // ---------------------------------------------------------------------
  const commitDraft = useCallback(() => {
    const draft = draftRef.current;
    if (!draft) return;
    // For rect/arrow, skip if zero size (just a click).
    if (draft.type === "rect") {
      if (Math.abs(draft.width) < 2 && Math.abs(draft.height) < 2) {
        draftRef.current = null;
        return;
      }
      // Normalize negative dims.
      if (draft.width < 0) {
        draft.x = draft.x + draft.width;
        draft.width = -draft.width;
      }
      if (draft.height < 0) {
        draft.y = draft.y + draft.height;
        draft.height = -draft.height;
      }
    }
    if (draft.type === "arrow") {
      if (Math.abs(draft.endX - draft.x) < 2 && Math.abs(draft.endY - draft.y) < 2) {
        draftRef.current = null;
        return;
      }
    }
    if (draft.type === "pen" && draft.points.length < 2) {
      draftRef.current = null;
      return;
    }
    pushUndo();
    elementsRef.current = [...elementsRef.current, draft];
    draftRef.current = null;
    notifyChange();
  }, [notifyChange, pushUndo]);

  const onPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLCanvasElement>) => {
      if (readOnly) return;
      if (e.button !== 0) return;
      // Commit any pending text edit on click outside.
      if (textEdit) return;

      const world = screenToWorld(e.clientX, e.clientY);
      const t = toolRef.current;

      // Don't capture pointer for text tool — the input needs focus on mount.
      const canvas = canvasRef.current;
      if (canvas && t !== "text") canvas.setPointerCapture(e.pointerId);
      const c = colorRef.current;
      const sw = strokeWidthRef.current;

      dragRef.current = {
        mode: "none",
        startScreenX: e.clientX,
        startScreenY: e.clientY,
        lastScreenX: e.clientX,
        lastScreenY: e.clientY,
        selectedId: null,
        partnerIds: [],
        movedDuringDrag: false,
      };

      if (t === "pen") {
        const el: PenElement = {
          id: newId(),
          type: "pen",
          x: world.x,
          y: world.y,
          color: c,
          strokeWidth: sw,
          points: [{ x: 0, y: 0 }],
        };
        draftRef.current = el;
        dragRef.current.mode = "draw";
        requestRedraw();
        return;
      }

      if (t === "rect") {
        const el: RectElement = {
          id: newId(),
          type: "rect",
          x: world.x,
          y: world.y,
          color: c,
          strokeWidth: sw,
          width: 0,
          height: 0,
          fill: "transparent",
        };
        draftRef.current = el;
        dragRef.current.mode = "draw";
        requestRedraw();
        return;
      }

      if (t === "arrow") {
        const el: ArrowElement = {
          id: newId(),
          type: "arrow",
          x: world.x,
          y: world.y,
          endX: world.x,
          endY: world.y,
          color: c,
          strokeWidth: sw,
        };
        draftRef.current = el;
        dragRef.current.mode = "draw";
        requestRedraw();
        return;
      }

      if (t === "text") {
        setTextEdit({ worldX: world.x, worldY: world.y, value: "" });
        dragRef.current.mode = "none";
        return;
      }

      if (t === "eraser") {
        dragRef.current.mode = "erase";
        const before = elementsRef.current.length;
        const remaining = elementsRef.current.filter((el) => {
          return !circleIntersectsBounds(world.x, world.y, ERASER_RADIUS, elementBounds(el));
        });
        if (remaining.length !== before) {
          pushUndo();
          elementsRef.current = remaining;
          if (selectedIdRef.current && !remaining.find((el) => el.id === selectedIdRef.current)) {
            setSelectedId(null);
          }
          dragRef.current.movedDuringDrag = true;
          requestRedraw();
        }
        return;
      }

      if (t === "hand") {
        dragRef.current.mode = "pan";
        return;
      }

      // Select
      const hit = hitTest(world.x, world.y);
      if (hit) {
        setSelectedId(hit.id);
        dragRef.current.selectedId = hit.id;
        dragRef.current.mode = "move";
        // When the hit is a `box-<X>` rect/circle, drag its paired `lbl-<X>...`
        // text element(s) along with it so the label stays anchored to the box.
        if ((hit.type === "rect" || hit.type === "circle") && hit.id.startsWith("box-")) {
          const boxKey = hit.id.slice(4);
          dragRef.current.partnerIds = elementsRef.current
            .filter((el) => el.id.startsWith(`lbl-${boxKey}`))
            .map((el) => el.id);
        } else {
          dragRef.current.partnerIds = [];
        }
        // Snapshot before move so undo restores positions.
        pushUndo();
      } else {
        setSelectedId(null);
        dragRef.current.mode = "pan";
      }
      requestRedraw();
    },
    [hitTest, pushUndo, readOnly, requestRedraw, screenToWorld, textEdit],
  );

  const onPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLCanvasElement>) => {
      if (readOnly) return;
      const drag = dragRef.current;
      if (drag.mode === "none") return;

      const dxScreen = e.clientX - drag.lastScreenX;
      const dyScreen = e.clientY - drag.lastScreenY;
      drag.lastScreenX = e.clientX;
      drag.lastScreenY = e.clientY;
      drag.movedDuringDrag = true;

      const world = screenToWorld(e.clientX, e.clientY);

      if (drag.mode === "draw" && draftRef.current) {
        const draft = draftRef.current;
        if (draft.type === "pen") {
          draft.points.push({ x: world.x - draft.x, y: world.y - draft.y });
        } else if (draft.type === "rect") {
          draft.width = world.x - draft.x;
          draft.height = world.y - draft.y;
        } else if (draft.type === "arrow") {
          draft.endX = world.x;
          draft.endY = world.y;
        }
        requestRedraw();
        return;
      }

      if (drag.mode === "move" && drag.selectedId) {
        const moveIds = new Set<string>([drag.selectedId, ...drag.partnerIds]);
        // Translate by world-space delta so dragging stays at cursor speed
        // regardless of zoom level.
        const z = zoomRef.current;
        const dxWorld = dxScreen / z;
        const dyWorld = dyScreen / z;
        elementsRef.current = elementsRef.current.map((el) =>
          moveIds.has(el.id) ? translateElement(el, dxWorld, dyWorld) : el,
        );
        requestRedraw();
        return;
      }

      if (drag.mode === "pan") {
        panRef.current.x += dxScreen;
        panRef.current.y += dyScreen;
        requestRedraw();
        return;
      }

      if (drag.mode === "erase") {
        const before = elementsRef.current.length;
        const remaining = elementsRef.current.filter((el) => {
          return !circleIntersectsBounds(world.x, world.y, ERASER_RADIUS, elementBounds(el));
        });
        if (remaining.length !== before) {
          elementsRef.current = remaining;
          if (selectedIdRef.current && !remaining.find((el) => el.id === selectedIdRef.current)) {
            setSelectedId(null);
          }
          requestRedraw();
        }
        return;
      }
    },
    [readOnly, requestRedraw, screenToWorld],
  );

  const onPointerUp = useCallback(
    (e: ReactPointerEvent<HTMLCanvasElement>) => {
      if (readOnly) return;
      const canvas = canvasRef.current;
      if (canvas && canvas.hasPointerCapture(e.pointerId)) {
        canvas.releasePointerCapture(e.pointerId);
      }
      const drag = dragRef.current;

      if (drag.mode === "draw") {
        commitDraft();
      } else if (drag.mode === "move") {
        // Already pushed pre-move snapshot. If nothing moved, roll back the snapshot.
        if (!drag.movedDuringDrag) {
          undoStackRef.current.pop();
        } else {
          notifyChange();
        }
      } else if (drag.mode === "erase") {
        if (drag.movedDuringDrag) notifyChange();
      }

      drag.mode = "none";
      requestRedraw();
    },
    [commitDraft, notifyChange, readOnly, requestRedraw],
  );

  // ---------------------------------------------------------------------
  // Text edit overlay
  // ---------------------------------------------------------------------
  const commitText = useCallback((dismissIfEmpty = false) => {
    if (!textEdit) return;
    const trimmed = textEdit.value.trim();
    if (trimmed.length === 0) {
      if (dismissIfEmpty) setTextEdit(null);
      return;
    }
    // Editing an existing label (double-click flow): replace its text in place.
    if (textEdit.editingId) {
      const targetId = textEdit.editingId;
      pushUndo();
      elementsRef.current = elementsRef.current.map((el) =>
        el.id === targetId && el.type === "text" ? { ...el, text: trimmed } : el,
      );
      setTextEdit(null);
      requestRedraw();
      notifyChange();
      return;
    }
    // Fresh-text path: new element at the click position.
    const el: TextElement = {
      id: newId(),
      type: "text",
      x: textEdit.worldX,
      y: textEdit.worldY + DEFAULT_FONT_SIZE,
      color: colorRef.current,
      strokeWidth: strokeWidthRef.current,
      text: trimmed,
      fontSize: DEFAULT_FONT_SIZE,
    };
    pushUndo();
    elementsRef.current = [...elementsRef.current, el];
    setTextEdit(null);
    requestRedraw();
    notifyChange();
  }, [notifyChange, pushUndo, requestRedraw, textEdit]);

  // ---------------------------------------------------------------------
  // Double-click on a box/circle: open the text-edit overlay anchored at
  // its label so the user can rename in place. No new element is created;
  // commitText branches on editingId to replace the existing label's text.
  // ---------------------------------------------------------------------
  const onDoubleClick = useCallback(
    (e: ReactPointerEvent<HTMLCanvasElement>) => {
      if (readOnly) return;
      const world = screenToWorld(e.clientX, e.clientY);
      const hit = hitTest(world.x, world.y);
      if (!hit) return;
      if (hit.type !== "rect" && hit.type !== "circle") return;
      if (!hit.id.startsWith("box-")) return;
      const boxKey = hit.id.slice(4);
      const label = elementsRef.current.find(
        (el) => el.id.startsWith(`lbl-${boxKey}`) && el.type === "text",
      ) as TextElement | undefined;
      if (!label) return;
      // Anchor the editor at the label's position (one font-size up so the
      // text input visually overlaps where the label sits).
      setTextEdit({
        worldX: label.x,
        worldY: label.y - label.fontSize,
        value: label.text,
        editingId: label.id,
      });
    },
    [hitTest, readOnly, screenToWorld],
  );

  // ---------------------------------------------------------------------
  // Keyboard shortcuts
  // ---------------------------------------------------------------------
  useEffect(() => {
    if (readOnly) return;
    const handler = (e: KeyboardEvent) => {
      // Ignore when typing in an input/textarea (e.g. text overlay).
      const target = e.target as HTMLElement | null;
      const isTyping =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);

      if ((e.ctrlKey || e.metaKey) && (e.key === "z" || e.key === "Z")) {
        e.preventDefault();
        if (e.shiftKey) redo();
        else undo();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === "y" || e.key === "Y")) {
        e.preventDefault();
        redo();
        return;
      }

      if (isTyping) return;

      switch (e.key.toLowerCase()) {
        case "v":
          setTool("select");
          break;
        case "p":
          setTool("pen");
          break;
        case "r":
          setTool("rect");
          break;
        case "a":
          setTool("arrow");
          break;
        case "t":
          setTool("text");
          break;
        case "e":
          setTool("eraser");
          break;
        case "h":
          setTool("hand");
          break;
        case "delete":
        case "backspace":
          if (selectedIdRef.current) {
            const id = selectedIdRef.current;
            pushUndo();
            elementsRef.current = elementsRef.current.filter((el) => el.id !== id);
            setSelectedId(null);
            requestRedraw();
            notifyChange();
          }
          break;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [notifyChange, pushUndo, readOnly, redo, requestRedraw, undo]);

  // ---------------------------------------------------------------------
  // Toolbar UI
  // ---------------------------------------------------------------------
  const toolButtons: { tool: Tool; label: string; key: string; Icon: typeof MousePointer2 }[] = [
    { tool: "select", label: "Select", key: "V", Icon: MousePointer2 },
    { tool: "pen", label: "Pen", key: "P", Icon: Pencil },
    { tool: "rect", label: "Rectangle", key: "R", Icon: Square },
    { tool: "arrow", label: "Arrow", key: "A", Icon: ArrowRight },
    { tool: "text", label: "Text", key: "T", Icon: TypeIcon },
    { tool: "eraser", label: "Eraser", key: "E", Icon: Eraser },
    { tool: "hand", label: "Pan", key: "H", Icon: Hand },
  ];

  // Position the text input overlay using screen coords derived from world coords + pan.
  const textInputStyle: CSSProperties | undefined = textEdit
    ? {
        position: "absolute",
        left: textEdit.worldX * zoomRef.current + panRef.current.x,
        top: textEdit.worldY * zoomRef.current + panRef.current.y,
        font: `${DEFAULT_FONT_SIZE * zoomRef.current}px ui-sans-serif, system-ui, -apple-system, sans-serif`,
        color: colorRef.current,
        background: "rgba(0,0,0,0.5)",
        border: "1px dashed #74c0fc",
        outline: "none",
        padding: "0 2px",
        minWidth: 40,
      }
    : undefined;

  const cursorClass: Record<Tool, string> = {
    select: "cursor-default",
    pen: "cursor-crosshair",
    rect: "cursor-crosshair",
    arrow: "cursor-crosshair",
    text: "cursor-text",
    eraser: "cursor-cell",
    hand: "cursor-grab",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", width: "100%", background: CANVAS_BG }}>
      {/* Toolbar */}
      <div className="shrink-0 h-10 flex items-center gap-1 px-2" style={{ background: "var(--surf)", borderBottom: "1px solid var(--line)" }}>
        {toolButtons.map(({ tool: t, label, key, Icon }) => {
          const active = tool === t;
          return (
            <button
              key={t}
              type="button"
              onClick={() => setTool(t)}
              title={`${label} (${key})`}
              disabled={readOnly}
              style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                width: 30, height: 30, borderRadius: 4, fontSize: 13, border: active ? "1px solid var(--accent)" : "1px solid transparent",
                background: active ? "color-mix(in srgb, var(--accent) 15%, transparent)" : "transparent",
                color: active ? "var(--accent)" : "var(--ink-2)", cursor: "pointer", transition: "background 0.1s",
              }}
            >
              <Icon className="h-4 w-4" />
            </button>
          );
        })}

        <div style={{ width: 1, height: 18, background: "var(--line-2)", margin: "0 2px", flexShrink: 0 }} />

        {/* Color swatches */}
        {COLORS.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setColor(c)}
            title={c}
            disabled={readOnly}
            style={{ width: 18, height: 18, borderRadius: "50%", border: color === c ? "2px solid var(--accent)" : "1px solid var(--line-2)", transform: color === c ? "scale(1.15)" : "scale(1)", transition: "transform 0.1s", cursor: "pointer", backgroundColor: c, outline: color === c ? "2px solid color-mix(in srgb, var(--accent) 30%, transparent)" : "none", outlineOffset: 1 }}
          />
        ))}

        <div style={{ width: 1, height: 18, background: "var(--line-2)", margin: "0 2px", flexShrink: 0 }} />

        {/* Stroke width */}
        {([STROKE_THIN, STROKE_THICK] as const).map((sw) => {
          const active = strokeWidth === sw;
          return (
            <button key={sw} type="button" onClick={() => setStrokeWidth(sw)} title={sw === STROKE_THIN ? "Thin" : "Thick"} disabled={readOnly}
              style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 30, height: 30, borderRadius: 4, border: active ? "1px solid var(--accent)" : "1px solid transparent", background: active ? "color-mix(in srgb, var(--accent) 15%, transparent)" : "transparent", color: active ? "var(--accent)" : "var(--ink-2)", cursor: "pointer" }}>
              <span style={{ display: "block", width: 14, height: sw === STROKE_THIN ? 2 : 5, background: "currentColor", borderRadius: 2 }} />
            </button>
          );
        })}

        <div style={{ width: 1, height: 18, background: "var(--line-2)", margin: "0 2px", flexShrink: 0 }} />

        {[{ fn: undo, icon: <Undo2 style={{ width: 14, height: 14 }} />, title: "Undo (Ctrl+Z)" }, { fn: redo, icon: <Redo2 style={{ width: 14, height: 14 }} />, title: "Redo (Ctrl+Shift+Z)" }].map(({ fn, icon, title }) => (
          <button key={title} type="button" onClick={fn} disabled={readOnly} title={title}
            style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 30, height: 30, borderRadius: 4, border: "1px solid transparent", background: "transparent", color: "var(--ink-2)", cursor: "pointer" }}>
            {icon}
          </button>
        ))}

        <button type="button" onClick={clearAll} disabled={readOnly} title="Clear canvas"
          style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 5, padding: "0 10px", height: 28, borderRadius: 4, border: "1px solid var(--line-2)", background: "transparent", color: "var(--mute)", fontSize: 11, fontFamily: "var(--font-mono)", cursor: "pointer", letterSpacing: "0.05em" }}>
          <Trash2 style={{ width: 12, height: 12 }} />
          Clear
        </button>
      </div>

      {/* Canvas surface */}
      <div ref={containerRef} className="relative flex-1 min-h-0 overflow-hidden">
        <canvas
          ref={canvasRef}
          className={`block touch-none ${cursorClass[tool]}`}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onDoubleClick={onDoubleClick}
          onWheel={(e) => {
            e.preventDefault();
            const canvas = canvasRef.current;
            if (!canvas) return;
            const rect = canvas.getBoundingClientRect();
            const cursorX = e.clientX - rect.left;
            const cursorY = e.clientY - rect.top;
            const oldZoom = zoomRef.current;
            const factor = e.deltaY < 0 ? 1.1 : 0.9;
            const newZoom = Math.min(10, Math.max(0.1, oldZoom * factor));
            // Zoom toward cursor: world point under cursor must stay fixed.
            panRef.current.x = cursorX - (cursorX - panRef.current.x) * (newZoom / oldZoom);
            panRef.current.y = cursorY - (cursorY - panRef.current.y) * (newZoom / oldZoom);
            zoomRef.current = newZoom;
            requestRedraw();
          }}
        />
        {textEdit && (
          <input
            ref={textInputRef}
            type="text"
            value={textEdit.value}
            onChange={(e) => setTextEdit({ ...textEdit, value: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                commitText(true);
              } else if (e.key === "Escape") {
                e.preventDefault();
                setTextEdit(null);
              }
            }}
            onBlur={() => commitText(true)}
            style={textInputStyle}
          />
        )}
      </div>
    </div>
  );
});
WhiteboardCanvas.displayName = "WhiteboardCanvas";
