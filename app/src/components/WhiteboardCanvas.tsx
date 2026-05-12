"use client";

import {
  useCallback,
  useEffect,
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

export type ElementType = "pen" | "rect" | "arrow" | "text";

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
}

export interface ArrowElement extends BaseElement {
  type: "arrow";
  endX: number;
  endY: number;
}

export interface TextElement extends BaseElement {
  type: "text";
  text: string;
  fontSize: number;
}

export type WhiteboardElement =
  | PenElement
  | RectElement
  | ArrowElement
  | TextElement;

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

export interface WhiteboardCanvasProps {
  onChange?: (elements: WhiteboardElement[]) => void;
  readOnly?: boolean;
}

interface TextEditState {
  worldX: number;
  worldY: number;
  value: string;
}

export function WhiteboardCanvas({ onChange, readOnly = false }: WhiteboardCanvasProps) {
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
    movedDuringDrag: boolean;
  }>({
    mode: "none",
    startScreenX: 0,
    startScreenY: 0,
    lastScreenX: 0,
    lastScreenY: 0,
    selectedId: null,
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

      if (el.type === "pen") {
        if (el.points.length === 0) return;
        ctx.beginPath();
        ctx.moveTo(el.x + el.points[0].x, el.y + el.points[0].y);
        for (let i = 1; i < el.points.length; i++) {
          ctx.lineTo(el.x + el.points[i].x, el.y + el.points[i].y);
        }
        ctx.stroke();
      } else if (el.type === "rect") {
        if (el.fill && el.fill !== "transparent") {
          ctx.fillStyle = el.fill;
          ctx.fillRect(el.x, el.y, el.width, el.height);
        }
        ctx.strokeRect(el.x, el.y, el.width, el.height);
      } else if (el.type === "arrow") {
        ctx.beginPath();
        ctx.moveTo(el.x, el.y);
        ctx.lineTo(el.endX, el.endY);
        ctx.stroke();
        drawArrowhead(ctx, el.x, el.y, el.endX, el.endY, el.color);
      } else if (el.type === "text") {
        ctx.fillStyle = el.color;
        ctx.font = `${el.fontSize}px ui-sans-serif, system-ui, -apple-system, sans-serif`;
        ctx.textBaseline = "alphabetic";
        ctx.fillText(el.text, el.x, el.y);
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
        const id = drag.selectedId;
        elementsRef.current = elementsRef.current.map((el) =>
          el.id === id ? translateElement(el, dxScreen, dyScreen) : el,
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
    <div className="flex flex-col h-full w-full" style={{ background: CANVAS_BG }}>
      {/* Toolbar */}
      <div className="shrink-0 h-10 flex items-center gap-1 px-2" style={{ background: "#1c1c1c", borderBottom: "1px solid #333" }}>
        {toolButtons.map(({ tool: t, label, key, Icon }) => {
          const active = tool === t;
          return (
            <button
              key={t}
              type="button"
              onClick={() => setTool(t)}
              title={`${label} (${key})`}
              disabled={readOnly}
              className={`inline-flex items-center justify-center w-8 h-8 rounded border text-sm transition-colors ${
                active
                  ? "border-blue-400 bg-blue-400/20 text-blue-400"
                  : "border-transparent text-zinc-300 hover:bg-zinc-700"
              }`}
            >
              <Icon className="h-4 w-4" />
            </button>
          );
        })}

        <div className="mx-1 h-5 w-px bg-zinc-600" />

        {/* Color swatches */}
        {COLORS.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setColor(c)}
            title={c}
            disabled={readOnly}
            className={`w-5 h-5 rounded-full border transition-transform ${
              color === c ? "ring-2 ring-offset-1 ring-primary scale-110" : "border-input"
            }`}
            style={{ backgroundColor: c }}
          />
        ))}

        <div className="mx-1 h-5 w-px bg-zinc-600" />

        {/* Stroke width */}
        <button
          type="button"
          onClick={() => setStrokeWidth(STROKE_THIN)}
          title="Thin stroke"
          disabled={readOnly}
          className={`inline-flex items-center justify-center w-8 h-8 rounded border ${
            strokeWidth === STROKE_THIN
              ? "border-blue-400 bg-blue-400/20 text-blue-400"
              : "border-transparent text-zinc-300 hover:bg-zinc-700"
          }`}
        >
          <span className="block w-4 h-[2px] bg-current" />
        </button>
        <button
          type="button"
          onClick={() => setStrokeWidth(STROKE_THICK)}
          title="Thick stroke"
          disabled={readOnly}
          className={`inline-flex items-center justify-center w-8 h-8 rounded border ${
            strokeWidth === STROKE_THICK
              ? "border-blue-400 bg-blue-400/20 text-blue-400"
              : "border-transparent text-zinc-300 hover:bg-zinc-700"
          }`}
        >
          <span className="block w-4 h-[5px] bg-current rounded-sm" />
        </button>

        <div className="mx-1 h-5 w-px bg-zinc-600" />

        <button
          type="button"
          onClick={undo}
          disabled={readOnly}
          title="Undo (Ctrl+Z)"
          className="inline-flex items-center justify-center w-8 h-8 rounded border border-transparent text-zinc-300 hover:bg-zinc-700"
        >
          <Undo2 className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={redo}
          disabled={readOnly}
          title="Redo (Ctrl+Shift+Z)"
          className="inline-flex items-center justify-center w-8 h-8 rounded border border-transparent text-zinc-300 hover:bg-zinc-700"
        >
          <Redo2 className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={clearAll}
          disabled={readOnly}
          title="Clear canvas"
          className="ml-auto inline-flex items-center gap-1 px-2 h-8 rounded text-xs text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200" style={{ border: "1px solid #444" }}
        >
          <Trash2 className="h-3.5 w-3.5" />
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
}
