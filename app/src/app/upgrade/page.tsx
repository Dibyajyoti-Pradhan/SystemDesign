"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const FEATURES = [
  "Unlimited AI interview sessions",
  "AI interviewer with real-time follow-ups",
  "AI vs AI — watch two agents debate any question",
  "System design & coding tracks",
  "Spaced-repetition flashcard engine",
  "Concept map + notes",
];

export default function UpgradePage() {
  const router = useRouter();
  const [loading, setLoading] = useState<"checkout" | null>(null);

  async function handleCheckout() {
    setLoading("checkout");
    try {
      const res = await fetch("/api/stripe/checkout", { method: "POST" });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
    } finally {
      setLoading(null);
    }
  }

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        .up { height:100%; display:grid; place-items:center; padding: 40px; }
        .up__card { max-width: 480px; width:100%; background: var(--surf); border:1px solid var(--line); border-radius: var(--r-3); overflow:hidden; }
        .up__price { background: var(--accent); padding: 32px; text-align:center; }
        .up__amount { font-family: var(--font-read); font-size: 64px; font-weight: 400; color: #0B0C0E; letter-spacing: -0.03em; line-height: 1; }
        .up__per { font-family: var(--font-mono); font-size: 12px; color: rgba(0,0,0,0.55); text-transform: uppercase; letter-spacing: .12em; margin-top: 6px; }
        .up__trial { font-family: var(--font-mono); font-size: 11px; color: rgba(0,0,0,0.5); margin-top: 8px; text-transform: uppercase; letter-spacing: .1em; }
        .up__body { padding: 28px 32px 32px; display:flex; flex-direction:column; gap: 22px; }
        .up__features { display:flex; flex-direction:column; gap: 10px; }
        .up__feat { display:flex; align-items:center; gap: 12px; font-size: 13.5px; color: var(--ink-2); }
        .up__check { width: 18px; height: 18px; border-radius: 999px; background: rgba(212,165,116,0.12); border: 1px solid rgba(212,165,116,0.3); display:flex; align-items:center; justify-content:center; flex-shrink:0; }
        .up__actions { display:flex; flex-direction:column; gap: 8px; }
        .up__back { font-family: var(--font-mono); font-size: 11px; color: var(--mute); text-align:center; cursor:pointer; background:none; border:0; padding: 8px; }
        .up__back:hover { color: var(--ink); }
        .up__fine { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute-2); text-align:center; }
      ` }} />
      <div className="up">
        <div className="up__card">
          <div className="up__price">
            <div className="up__amount">£39</div>
            <div className="up__per">per month</div>
            <div className="up__trial">7-day free trial — cancel anytime</div>
          </div>
          <div className="up__body">
            <div className="up__features">
              {FEATURES.map((f) => (
                <div key={f} className="up__feat">
                  <span className="up__check">
                    <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="2 6 5 9 10 3" />
                    </svg>
                  </span>
                  {f}
                </div>
              ))}
            </div>
            <div className="up__actions">
              <button
                onClick={handleCheckout}
                disabled={loading !== null}
                className="btn btn--primary"
                style={{ width: "100%", justifyContent: "center", padding: "12px" }}
              >
                {loading === "checkout" ? "Redirecting…" : "Start Free Trial"}
              </button>
              <button onClick={() => router.back()} className="up__back">← Go back</button>
            </div>
            <div className="up__fine">Secure payment via Stripe. No card required during trial.</div>
          </div>
        </div>
      </div>
    </>
  );
}
