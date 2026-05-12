"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Bot } from "lucide-react";

export function StartAiVsAiVoiceButton({ slug }: { slug: string }) {
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
        body: JSON.stringify({ slug, mode: "ai_vs_ai" }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? `HTTP ${res.status}`);
      }
      const { id } = await res.json() as { id: number };
      router.push(`/interview/ai-vs-ai/voice/${id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start session");
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <button
        onClick={start}
        disabled={loading}
        style={{
          fontFamily: "var(--font-mono)", fontSize: 11,
          display: "inline-flex", alignItems: "center", gap: 5,
          padding: "5px 12px", borderRadius: "var(--r-1)",
          border: "1px solid var(--line-2)",
          color: "var(--mute)", background: "transparent",
          cursor: loading ? "not-allowed" : "pointer",
          opacity: loading ? 0.7 : 1, transition: "background 0.12s",
        }}
      >
        {loading ? (
          <>
            <svg style={{ width: 11, height: 11, animation: "spin 1s linear infinite" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
            Starting…
          </>
        ) : (
          <>
            <Bot style={{ width: 11, height: 11 }} />
            AI vs AI
          </>
        )}
      </button>
      {error && (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--bad)" }}>{error}</span>
      )}
      <style dangerouslySetInnerHTML={{ __html: `@keyframes spin { to { transform: rotate(360deg); } }` }} />
    </div>
  );
}
