"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

export function GenerateTopicButton({ slug }: { slug: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [eta, setEta] = useState<number>(0);

  const trigger = () => {
    setError(null);
    setEta(0);
    const t0 = Date.now();
    const tick = setInterval(() => setEta(Math.round((Date.now() - t0) / 1000)), 500);
    start(async () => {
      try {
        const res = await fetch(`/api/topics/${slug}/generate`, { method: "POST" });
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
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <button className="btn btn--primary" onClick={trigger} disabled={pending} style={{ alignSelf: "flex-start" }}>
        {pending ? (
          <>
            <svg style={{ width: 13, height: 13, animation: "spin 1s linear infinite" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
            Generating… ({eta}s)
          </>
        ) : (
          <>
            <svg style={{ width: 13, height: 13 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            Generate this page from PDF
          </>
        )}
      </button>
      {pending && (
        <span style={{ fontSize: 12, color: "var(--mute)", fontFamily: "var(--font-mono)" }}>
          Claude is reading the PDF and writing TL;DR / Standard / Deep sections with diagrams. ~30–60s.
        </span>
      )}
      {error && (
        <span style={{ fontSize: 12, color: "var(--bad)" }}>Generation failed: {error}</span>
      )}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
