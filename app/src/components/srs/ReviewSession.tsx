"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Mermaid } from "@/components/Mermaid";
import { ArrowLeft } from "lucide-react";

export interface ReviewCard {
  id: number;
  type: "definition" | "tradeoff" | "scenario" | "comparison";
  front: string;
  back: string;
  diagramMermaid: string | null;
  topicTitle: string | null;
  topicSlug: string | null;
}

interface SessionStats {
  again: number;
  hard: number;
  good: number;
  easy: number;
}

const CSS = `
.card-wrap { max-width: 680px; margin: 0 auto; display:flex; flex-direction:column; gap: 20px; }
.srs-card { background: var(--surf); border:1px solid var(--line); border-radius: var(--r-3); }
.srs-card__meta { display:flex; justify-content:space-between; align-items:center; padding: 12px 18px; border-bottom: 1px solid var(--line); }
.srs-card__type { font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; letter-spacing: .1em; color: var(--mute); padding: 3px 7px; border:1px solid var(--line); border-radius: 4px; background: var(--bg-2); }
.srs-card__topic { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-decoration: none; }
.srs-card__topic:hover { color: var(--ink); }
.srs-card__body { padding: 24px 20px; display:flex; flex-direction:column; gap: 18px; }
.srs-card__label { font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; letter-spacing: .1em; color: var(--mute-2); margin-bottom: 6px; }
.srs-card__q { font-size: 17px; line-height: 1.5; color: var(--ink); white-space: pre-wrap; }
.srs-card__divider { border:0; border-top: 1px solid var(--line); margin: 0; }
.srs-card__a { font-size: 14.5px; line-height: 1.6; color: var(--ink-2); white-space: pre-wrap; }
.srs-reveal { width: 100%; padding: 11px; background: var(--surf-2); border:1px solid var(--line-2); border-radius: 6px; color: var(--mute); font-size: 13px; cursor:pointer; display:flex; align-items:center; justify-content:center; gap: 8px; }
.srs-reveal:hover { background: var(--surf-3); color: var(--ink); }
.srs-reveal .hint { font-family: var(--font-mono); font-size: 10px; color: var(--mute-2); margin-left: auto; }
.srs-ratings { display:grid; grid-template-columns: repeat(4,1fr); gap: 10px; }
.srs-rating { padding: 10px 6px; border-radius: 6px; border:1px solid var(--line-2); background: var(--surf-2); cursor:pointer; display:flex; flex-direction:column; align-items:center; gap: 3px; }
.srs-rating:hover { background: var(--surf-3); }
.srs-rating:disabled { opacity: .45; cursor:default; }
.srs-rating .r-lbl { font-size: 13px; font-weight: 600; color: var(--ink); }
.srs-rating .r-hint { font-family: var(--font-mono); font-size: 10px; color: var(--mute); }
.srs-rating.r-again .r-lbl { color: var(--bad); }
.srs-rating.r-easy .r-lbl { color: var(--good); }
.srs-footer { display:flex; justify-content:space-between; align-items:center; font-family: var(--font-mono); font-size: 11px; color: var(--mute); }
.srs-footer a { color: var(--mute); text-decoration:none; display:inline-flex; align-items:center; gap:5px; }
.srs-footer a:hover { color: var(--ink); }
.srs-done { background: var(--surf); border:1px solid var(--line); border-radius: var(--r-3); padding: 40px 32px; text-align: center; display:flex; flex-direction:column; align-items:center; gap: 20px; }
.srs-done__t { font-family: var(--font-read); font-size: 40px; font-style: italic; font-weight: 400; letter-spacing: -0.024em; color: var(--ink); }
.srs-done__stats { display:grid; grid-template-columns:repeat(4,1fr); gap: 12px; width: 100%; }
.srs-done__stat { background: var(--bg-2); border:1px solid var(--line); border-radius: 6px; padding: 12px; }
.srs-done__stat .n { font-family: var(--font-read); font-size: 32px; font-weight: 400; color: var(--ink); }
.srs-done__stat .l { font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; letter-spacing: .1em; color: var(--mute-2); margin-top: 2px; }
`;

const RATINGS: Array<{ rating: 1 | 2 | 3 | 4; label: string; hint: string; cls: string; shortcut: string }> = [
  { rating: 1, label: "Again", hint: "<10m · 1", cls: "r-again", shortcut: "1" },
  { rating: 2, label: "Hard",  hint: "shorter · 2", cls: "", shortcut: "2" },
  { rating: 3, label: "Good",  hint: "on track · 3", cls: "", shortcut: "3" },
  { rating: 4, label: "Easy",  hint: "longer · 4", cls: "r-easy", shortcut: "4" },
];

export function ReviewSession({
  cards,
  topicSlug,
  track,
}: {
  cards: ReviewCard[];
  topicSlug?: string;
  track: "system-design" | "coding";
}) {
  const router = useRouter();
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [stats, setStats] = useState<SessionStats>({ again: 0, hard: 0, good: 0, easy: 0 });
  const [done, setDone] = useState(false);

  const total = cards.length;
  const current = cards[index];
  const progress = done ? 100 : total === 0 ? 100 : Math.round((index / total) * 100);
  const finished = useMemo(() => stats.again + stats.hard + stats.good + stats.easy, [stats]);

  // Push progress into the server-rendered bar in the parent page
  useEffect(() => {
    const bar = document.querySelector<HTMLElement>(".srs-bar > i");
    if (bar) bar.style.width = `${progress}%`;
  }, [progress]);

  async function rate(rating: 1 | 2 | 3 | 4) {
    if (!current || submitting) return;
    setSubmitting(true);
    try {
      const res = await fetch(`/api/cards/${current.id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        console.error("Review failed:", err);
        return;
      }
      const key = rating === 1 ? "again" : rating === 2 ? "hard" : rating === 3 ? "good" : "easy";
      setStats((s) => ({ ...s, [key]: s[key] + 1 }));
      if (index + 1 >= total) {
        setDone(true);
        router.refresh();
      } else {
        setIndex((i) => i + 1);
        setRevealed(false);
      }
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (done) return;
      if (e.key === " " || e.key === "Enter") {
        if (!revealed) { e.preventDefault(); setRevealed(true); }
        return;
      }
      if (revealed && !submitting) {
        if (e.key === "1") rate(1);
        else if (e.key === "2") rate(2);
        else if (e.key === "3") rate(3);
        else if (e.key === "4") rate(4);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revealed, submitting, done, index]);

  if (done) {
    return (
      <>
        <style dangerouslySetInnerHTML={{ __html: CSS }} />
        <div className="card-wrap">
          <div className="srs-done">
            <div className="srs-done__t">Session complete.</div>
            <div className="srs-done__stats">
              {[
                { l: "Again", n: stats.again },
                { l: "Hard",  n: stats.hard },
                { l: "Good",  n: stats.good },
                { l: "Easy",  n: stats.easy },
              ].map((s) => (
                <div key={s.l} className="srs-done__stat">
                  <div className="n">{s.n}</div>
                  <div className="l">{s.l}</div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <button className="btn" onClick={() => router.refresh()}>Refresh queue</button>
              <Link href={`/${track}/topics`} className="btn btn--ghost">Back to topics</Link>
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: CSS }} />
      <div className="card-wrap">
        <div className="srs-card">
          <div className="srs-card__meta">
            <span className="srs-card__type">{current.type}</span>
            {current.topicSlug && current.topicTitle && (
              <Link href={`/${track}/topics/${current.topicSlug}`} className="srs-card__topic">
                {current.topicTitle}
              </Link>
            )}
          </div>
          <div className="srs-card__body">
            <div>
              <div className="srs-card__label">Question</div>
              <div className="srs-card__q">{current.front}</div>
            </div>
            {!revealed && current.diagramMermaid && (
              <div style={{ opacity: 0.6 }}><Mermaid chart={current.diagramMermaid} /></div>
            )}
            {revealed ? (
              <>
                <hr className="srs-card__divider" />
                <div>
                  <div className="srs-card__label">Answer</div>
                  <div className="srs-card__a">{current.back}</div>
                </div>
                {current.diagramMermaid && <Mermaid chart={current.diagramMermaid} />}
                <div className="srs-ratings">
                  {RATINGS.map((b) => (
                    <button
                      key={b.rating}
                      className={`srs-rating ${b.cls}`}
                      disabled={submitting}
                      onClick={() => rate(b.rating)}
                    >
                      <span className="r-lbl">{b.label}</span>
                      <span className="r-hint">{b.hint}</span>
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <button className="srs-reveal" onClick={() => setRevealed(true)}>
                <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                </svg>
                Show answer
                <span className="hint">space</span>
              </button>
            )}
          </div>
        </div>

        <div className="srs-footer">
          <Link href={`/${track}/topics`}>
            <ArrowLeft style={{ width: 12, height: 12 }} /> Exit session
          </Link>
          <span>A {stats.again} · H {stats.hard} · G {stats.good} · E {stats.easy}</span>
        </div>
      </div>
    </>
  );
}
