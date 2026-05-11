"use client";

import dynamic from "next/dynamic";

// Excalidraw uses browser APIs — must be loaded client-side only.
const ExcalidrawDynamic = dynamic(
  () => import("@excalidraw/excalidraw").then((m) => ({ default: m.Excalidraw })),
  { ssr: false },
);

export interface WhiteboardProps {
  onChange?: (elements: readonly any[], state: any) => void;
  initialData?: any;
  readOnly?: boolean;
}

/**
 * Compact JSON representation of the whiteboard state for passing to Claude.
 * Only includes element type, text, and rough positions.
 */
export function getWhiteboardJSON(elements: readonly any[], _state: any): string {
  const compact = (elements as any[])
    .filter((el) => !el.isDeleted)
    .map((el) => {
      const base: Record<string, unknown> = {
        type: el.type,
        x: Math.round(el.x),
        y: Math.round(el.y),
      };
      if (el.text) base.text = el.text;
      if (el.width) base.w = Math.round(el.width);
      if (el.height) base.h = Math.round(el.height);
      if (el.label?.text) base.label = el.label.text;
      return base;
    });
  return JSON.stringify(compact);
}

export function Whiteboard({ onChange, initialData, readOnly = false }: WhiteboardProps) {
  return (
    <div className="w-full h-full" style={{ minHeight: 400 }}>
      <ExcalidrawDynamic
        initialData={initialData ?? null}
        viewModeEnabled={readOnly}
        onChange={onChange}
        theme="dark"
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
