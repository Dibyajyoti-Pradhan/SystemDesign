'use client'

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Ship to unified dev log so we can grep both sides in one file.
    if (process.env.NODE_ENV !== "production") {
      fetch("/api/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          level: "error",
          url: typeof location !== "undefined" ? location.pathname + location.search : undefined,
          message: "ErrorBoundary: " + (error?.message ?? "unknown"),
          stack: error?.stack,
          meta: { digest: error?.digest },
        }),
        keepalive: true,
      }).catch(() => {});
    }
  }, [error]);

  return (
    <div style={{ minHeight: "60vh", display: "grid", placeItems: "center", padding: "32px 16px" }}>
      <div style={{ textAlign: "center", maxWidth: 520, display: "flex", flexDirection: "column", gap: 16 }}>
        <h2 style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.022em", color: "var(--ink)" }}>Something went wrong</h2>
        <p style={{ color: "var(--mute)", fontSize: 14, lineHeight: 1.5 }}>
          {error.message || 'An unexpected error occurred. Please try again.'}
        </p>
        {error?.digest && (
          <p style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute-2)" }}>digest: {error.digest}</p>
        )}
        <div>
          <button onClick={reset} className="btn btn--primary">Try again</button>
        </div>
      </div>
    </div>
  )
}
