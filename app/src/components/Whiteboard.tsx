"use client";

import dynamic from "next/dynamic";

// Excalidraw uses browser APIs — must be loaded client-side only.
const ExcalidrawDynamic = dynamic(
  () => import("@excalidraw/excalidraw").then((m) => ({ default: m.Excalidraw })),
  { ssr: false },
);

// Minimal structural type matching the fields we actually read off an Excalidraw element.
// Full Excalidraw element types are huge and live behind deep subpath imports — using a
// narrow structural type keeps us free of `any` while not coupling to Excalidraw internals.
export interface WhiteboardElementLike {
  type: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  isDeleted?: boolean;
  text?: string;
  label?: { text?: string };
}

export type WhiteboardElements = readonly WhiteboardElementLike[];
export type WhiteboardAppState = unknown;

export interface WhiteboardProps {
  onChange?: (elements: WhiteboardElements, state: WhiteboardAppState) => void;
  initialData?: unknown;
  readOnly?: boolean;
  theme?: "light" | "dark";
}

/**
 * Compact JSON representation of the whiteboard state for passing to Claude.
 * Only includes element type, text, and rough positions.
 */
export function getWhiteboardJSON(
  elements: WhiteboardElements,
  _state: WhiteboardAppState,
): string {
  const compact = elements
    .filter((el) => !el.isDeleted)
    .map((el) => {
      const base: Record<string, unknown> = {
        type: el.type,
        x: Math.round(el.x),
        y: Math.round(el.y),
      };
      if (el.text) base.text = el.text;
      if (typeof el.width === "number") base.w = Math.round(el.width);
      if (typeof el.height === "number") base.h = Math.round(el.height);
      if (el.label?.text) base.label = el.label.text;
      return base;
    });
  return JSON.stringify(compact);
}

export function Whiteboard({
  onChange,
  initialData,
  readOnly = false,
  theme = "light",
}: WhiteboardProps) {
  // Excalidraw's onChange signature uses internal types that aren't easily importable.
  // Cast at the boundary; consumers receive our structural type.
  const handleChange = onChange
    ? (elements: readonly unknown[], state: unknown) => {
        onChange(elements as WhiteboardElements, state);
      }
    : undefined;

  // Excalidraw's prop types ship from a deep subpath that next/dynamic strips, so we
  // cast through `unknown` only for the props whose generic shape TS cannot infer here.
  const initialDataProp = (initialData ?? null) as unknown as never;
  const onChangeProp = handleChange as unknown as never;

  return (
    <div className="w-full h-full" style={{ width: "100%", height: "100%", minHeight: 400 }}>
      <style>{`
        .excalidraw .welcome-screen-center,
        .excalidraw [class*="welcome-screen-decor"] {
          display: none !important;
        }
      `}</style>
      <ExcalidrawDynamic
        initialData={initialDataProp}
        viewModeEnabled={readOnly}
        onChange={onChangeProp}
        theme={theme}
        UIOptions={{
          canvasActions: {
            saveToActiveFile: false,
            loadScene: false,
            export: false,
            toggleTheme: false,
          },
        }}
      />
    </div>
  );
}
