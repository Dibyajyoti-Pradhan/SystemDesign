"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function StartInterviewButton({
  slug,
  mode,
}: {
  slug: string;
  mode: "self" | "ai_vs_ai";
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/sessions/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug, mode }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      const { id } = await res.json();
      router.push(`/interview/sessions/${id}`);
    } catch (e: any) {
      setError(e?.message ?? "Failed to start session");
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <button onClick={start} disabled={loading} className="btn btn--primary" style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
        {loading ? (
          <>
            <svg style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
            </svg>
            Starting…
          </>
        ) : (
          "Start session"
        )}
      </button>
      {error && <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--bad)" }}>{error}</span>}
      <style dangerouslySetInnerHTML={{ __html: `@keyframes spin { to { transform: rotate(360deg); } }` }} />
    </div>
  );
}
