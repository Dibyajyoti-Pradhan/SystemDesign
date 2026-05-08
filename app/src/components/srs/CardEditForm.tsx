"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Mermaid } from "@/components/Mermaid";
import { CheckCircle2, Eye, EyeOff, Save, X } from "lucide-react";

const CARD_TYPES = ["definition", "tradeoff", "scenario", "comparison"] as const;
type CardType = (typeof CARD_TYPES)[number];

export interface CardEditFormProps {
  cardId: number;
  initialType: CardType;
  initialFront: string;
  initialBack: string;
  initialDiagram: string | null;
  initialStatus: "pending_review" | "active" | "archived";
}

export function CardEditForm(props: CardEditFormProps) {
  const router = useRouter();
  const [type, setType] = useState<CardType>(props.initialType);
  const [front, setFront] = useState(props.initialFront);
  const [back, setBack] = useState(props.initialBack);
  const [diagram, setDiagram] = useState(props.initialDiagram ?? "");
  const [showPreview, setShowPreview] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  async function save(opts?: { approveAfter?: boolean }) {
    setError(null);
    const res = await fetch(`/api/cards/${props.cardId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type,
        front,
        back,
        diagramMermaid: diagram.trim() || null,
      }),
    });
    if (!res.ok) {
      const e = await res.json().catch(() => ({}));
      setError(e.error ?? "Failed to save");
      return false;
    }
    if (opts?.approveAfter) {
      const res2 = await fetch(`/api/cards/${props.cardId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "approve" }),
      });
      if (!res2.ok) {
        const e = await res2.json().catch(() => ({}));
        setError(e.error ?? "Saved but failed to approve");
        return false;
      }
    }
    return true;
  }

  function onSave() {
    startTransition(async () => {
      const ok = await save();
      if (ok) {
        router.refresh();
        router.push("/admin/cards");
      }
    });
  }

  function onSaveAndApprove() {
    startTransition(async () => {
      const ok = await save({ approveAfter: true });
      if (ok) {
        router.refresh();
        router.push("/admin/cards");
      }
    });
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Edit</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Type
            </label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as CardType)}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            >
              {CARD_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Front (question)
            </label>
            <textarea
              value={front}
              onChange={(e) => setFront(e.target.value)}
              rows={3}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Back (answer)
            </label>
            <textarea
              value={back}
              onChange={(e) => setBack(e.target.value)}
              rows={8}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Mermaid diagram (optional)
            </label>
            <textarea
              value={diagram}
              onChange={(e) => setDiagram(e.target.value)}
              rows={6}
              placeholder="flowchart TD&#10;  A --> B"
              className="w-full rounded-md border bg-background px-3 py-2 text-xs font-mono"
            />
          </div>

          {error && (
            <div className="text-sm text-destructive border border-destructive/30 bg-destructive/5 rounded p-2">
              {error}
            </div>
          )}

          <div className="flex flex-wrap gap-2 pt-2 border-t">
            <Button onClick={onSave} disabled={pending} size="sm" variant="outline">
              <Save className="h-4 w-4" /> Save
            </Button>
            <Button onClick={onSaveAndApprove} disabled={pending} size="sm">
              <CheckCircle2 className="h-4 w-4" /> Save & approve
            </Button>
            <Button asChild variant="ghost" size="sm">
              <Link href="/admin/cards">
                <X className="h-4 w-4" /> Cancel
              </Link>
            </Button>
            <Button
              onClick={() => setShowPreview((v) => !v)}
              variant="ghost"
              size="sm"
              className="ml-auto"
            >
              {showPreview ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              {showPreview ? "Hide preview" : "Show preview"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {showPreview && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Preview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
                Question
              </div>
              <div className="whitespace-pre-wrap text-sm leading-relaxed">{front}</div>
            </div>
            <div className="border-t pt-4">
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
                Answer
              </div>
              <div className="whitespace-pre-wrap text-sm leading-relaxed">{back}</div>
            </div>
            {diagram.trim() && <Mermaid chart={diagram} />}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
