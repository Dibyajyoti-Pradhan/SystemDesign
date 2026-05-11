"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

export function GenerateBriefButton({ slug }: { slug: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [eta, setEta] = useState(0);

  const trigger = () => {
    setError(null);
    setEta(0);
    const t0 = Date.now();
    const tick = setInterval(() => setEta(Math.round((Date.now() - t0) / 1000)), 500);
    start(async () => {
      try {
        const res = await fetch(`/api/questions/${slug}/generate-brief`, { method: "POST" });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.error || `HTTP ${res.status}`);
        }
        router.refresh();
      } catch (e: any) {
        setError(e?.message ?? String(e));
      } finally {
        clearInterval(tick);
      }
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <button onClick={trigger} disabled={pending} className="btn btn--ghost" style={{ fontSize: 12, padding: "4px 10px", display: "inline-flex", alignItems: "center", gap: 6 }}>
        {pending ? (
          <>
            <svg style={{ width: 12, height: 12, animation: "spin 1s linear infinite" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
            </svg>
            Generating… ({eta}s)
          </>
        ) : (
          <>
            <svg style={{ width: 12, height: 12 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
            </svg>
            Generate brief
          </>
        )}
      </button>
      {error && (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--bad)" }}>{error}</span>
      )}
      <style dangerouslySetInnerHTML={{ __html: `@keyframes spin { to { transform: rotate(360deg); } }` }} />
    </div>
  );
}
