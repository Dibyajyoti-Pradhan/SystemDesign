"use client";

import { forwardRef } from "react";
import {
  WhiteboardCanvas,
  getCanvasJSON,
  type WhiteboardElement,
  type WhiteboardHandle,
} from "@/components/WhiteboardCanvas";

export type { WhiteboardHandle };

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
  /** Kept for backwards compatibility — the in-house canvas is always dark. */
  theme?: "light" | "dark";
}

export const Whiteboard = forwardRef<WhiteboardHandle, WhiteboardProps>(
  function Whiteboard({ onChange, readOnly = false }: WhiteboardProps, ref) {
    const handleChange = onChange
      ? (elements: WhiteboardElement[]) => {
          onChange(elements as WhiteboardElements, null);
        }
      : undefined;

    return (
      <div className="w-full h-full" style={{ width: "100%", height: "100%", minHeight: 400 }}>
        <WhiteboardCanvas ref={ref} onChange={handleChange} readOnly={readOnly} />
      </div>
    );
  },
);
Whiteboard.displayName = "Whiteboard";
