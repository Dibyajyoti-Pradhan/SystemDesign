"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Sparkles, Loader2 } from "lucide-react";

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
    <div className="space-y-2">
      <Button onClick={trigger} disabled={pending} variant="outline" size="sm">
        {pending ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" /> Generating brief… ({eta}s)
          </>
        ) : (
          <>
            <Sparkles className="h-4 w-4" /> Generate brief
          </>
        )}
      </Button>
      {pending && (
        <p className="text-xs text-muted-foreground">
          Claude is reading the PDF and extracting just the question — never the solution. ~20-40s.
        </p>
      )}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
