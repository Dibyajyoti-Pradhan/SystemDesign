"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Mermaid } from "@/components/Mermaid";
import { ArrowLeft, Sparkles, RotateCcw, Eye } from "lucide-react";

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

const RATING_BUTTONS: Array<{
  rating: 1 | 2 | 3 | 4;
  label: string;
  hint: string;
  variant: "destructive" | "outline" | "secondary" | "default";
  shortcut: string;
}> = [
  { rating: 1, label: "Again", hint: "<10m", variant: "destructive", shortcut: "1" },
  { rating: 2, label: "Hard", hint: "shorter", variant: "outline", shortcut: "2" },
  { rating: 3, label: "Good", hint: "on track", variant: "secondary", shortcut: "3" },
  { rating: 4, label: "Easy", hint: "longer", variant: "default", shortcut: "4" },
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
  const progress = total === 0 ? 100 : Math.round((index / total) * 100);

  const finished = useMemo(
    () => stats.again + stats.hard + stats.good + stats.easy,
    [stats],
  );

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
      const key =
        rating === 1 ? "again" : rating === 2 ? "hard" : rating === 3 ? "good" : "easy";
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
        if (!revealed) {
          e.preventDefault();
          setRevealed(true);
        }
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

  if (total === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center space-y-3">
          <Sparkles className="h-8 w-8 text-muted-foreground mx-auto" />
          <p className="text-muted-foreground">
            Nothing due {topicSlug ? `for ${topicSlug}` : "right now"}. Come back later or generate
            more cards.
          </p>
          <div className="flex gap-2 justify-center pt-2">
            <Button asChild variant="outline" size="sm">
              <Link href={`/${track}/topics`}>Browse topics</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/admin/cards">Pending cards</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (done) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5" /> Session complete
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Reviewed {finished} {finished === 1 ? "card" : "cards"}.
          </p>
          <div className="grid grid-cols-4 gap-2 text-center">
            <Stat label="Again" value={stats.again} className="text-destructive" />
            <Stat label="Hard" value={stats.hard} />
            <Stat label="Good" value={stats.good} />
            <Stat label="Easy" value={stats.easy} />
          </div>
          <div className="flex gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => router.refresh()}>
              <RotateCcw className="h-4 w-4" /> Refresh queue
            </Button>
            <Button asChild variant="ghost" size="sm">
              <Link href={`/${track}/topics`}>Back to topics</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Progress value={progress} className="flex-1" />
        <span className="text-xs text-muted-foreground tabular-nums w-16 text-right">
          {index + 1} / {total}
        </span>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex justify-between items-start gap-2">
            <Badge variant="outline" className="text-[10px] uppercase">
              {current.type}
            </Badge>
            {current.topicSlug && current.topicTitle && (
              <Link
                href={`/${track}/topics/${current.topicSlug}`}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                {current.topicTitle}
              </Link>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <div>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-2">
              Question
            </div>
            <div className="whitespace-pre-wrap text-base leading-relaxed">{current.front}</div>
          </div>

          {!revealed && current.diagramMermaid && (
            <div className="opacity-60">
              <Mermaid chart={current.diagramMermaid} />
            </div>
          )}

          {revealed && (
            <>
              <div className="border-t pt-4">
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-2">
                  Answer
                </div>
                <div className="whitespace-pre-wrap text-sm leading-relaxed">{current.back}</div>
              </div>
              {current.diagramMermaid && <Mermaid chart={current.diagramMermaid} />}
            </>
          )}

          {!revealed ? (
            <Button onClick={() => setRevealed(true)} className="w-full">
              <Eye className="h-4 w-4" /> Show answer
              <span className="ml-auto text-[10px] opacity-60">space</span>
            </Button>
          ) : (
            <div className="grid grid-cols-4 gap-2">
              {RATING_BUTTONS.map((b) => (
                <Button
                  key={b.rating}
                  variant={b.variant}
                  disabled={submitting}
                  onClick={() => rate(b.rating)}
                  className="flex flex-col items-center h-auto py-2"
                >
                  <span className="font-semibold">{b.label}</span>
                  <span className="text-[10px] opacity-70">{b.hint} · {b.shortcut}</span>
                </Button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between items-center text-xs text-muted-foreground">
        <Link href={`/${track}/topics`} className="hover:text-foreground inline-flex items-center gap-1">
          <ArrowLeft className="h-3 w-3" /> Exit session
        </Link>
        <div className="flex gap-3">
          <span>A {stats.again}</span>
          <span>H {stats.hard}</span>
          <span>G {stats.good}</span>
          <span>E {stats.easy}</span>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, className }: { label: string; value: number; className?: string }) {
  return (
    <div className="rounded-md border p-3">
      <div className={`text-2xl font-bold tabular-nums ${className ?? ""}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
    </div>
  );
}
