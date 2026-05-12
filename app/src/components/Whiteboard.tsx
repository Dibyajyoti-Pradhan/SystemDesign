"use client";

import {
  WhiteboardCanvas,
  getCanvasJSON,
  type WhiteboardElement,
} from "@/components/WhiteboardCanvas";

// Public element type — kept as a readonly array for consumers, matching the
// previous Excalidraw-backed contract.
export type WhiteboardElements = readonly WhiteboardElement[];

// Old API exposed an Excalidraw AppState; the in-house canvas has no analogue,
// so we expose `null` for compatibility.
export type WhiteboardAppState = null;

/**
 * Compact JSON representation of the whiteboard state for passing to Claude.
 * Returns "[]" for an empty canvas (never null).
 */
export function getWhiteboardJSON(
  elements: WhiteboardElements,
  _state: WhiteboardAppState,
): string {
  return getCanvasJSON(elements);
}

export interface WhiteboardProps {
  onChange?: (elements: WhiteboardElements, state: WhiteboardAppState) => void;
  readOnly?: boolean;
  /** Kept for backwards compatibility — the in-house canvas is always light. */
  theme?: "light" | "dark";
}

export function Whiteboard({ onChange, readOnly = false }: WhiteboardProps) {
  const handleChange = onChange
    ? (elements: WhiteboardElement[]) => {
        onChange(elements as WhiteboardElements, null);
      }
    : undefined;

  return (
    <div className="w-full h-full" style={{ width: "100%", height: "100%", minHeight: 400 }}>
      <WhiteboardCanvas onChange={handleChange} readOnly={readOnly} />
    </div>
  );
}
