"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  sessionId: number;
  /** Where to navigate after a successful delete. If unset, just refreshes. */
  redirectTo?: string;
  /** Override the visible label. Defaults to "Delete". */
  label?: string;
  /** Hide the label and only show the icon. Useful in dense rows. */
  iconOnly?: boolean;
  variant?: "ghost" | "outline" | "destructive";
  size?: "sm" | "default" | "icon";
  className?: string;
}

export function DeleteSessionButton({
  sessionId,
  redirectTo,
  label = "Delete",
  iconOnly = false,
  variant = "ghost",
  size = "sm",
  className,
}: Props) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const handle = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm("Delete this session permanently? This cannot be undone.")) return;
    setError(null);
    start(async () => {
      try {
        const res = await fetch(`/api/interview/sessions/${sessionId}`, { method: "DELETE" });
        if (!res.ok) {
          const t = await res.text();
          throw new Error(t || `HTTP ${res.status}`);
        }
        if (redirectTo) router.push(redirectTo);
        else router.refresh();
      } catch (e: any) {
        setError(e?.message ?? String(e));
      }
    });
  };

  return (
    <span className="inline-flex items-center gap-1">
      <Button
        type="button"
        variant={variant}
        size={size}
        onClick={handle}
        disabled={pending}
        className={cn("text-destructive hover:bg-destructive/10 hover:text-destructive", className)}
        title={iconOnly ? label : undefined}
      >
        <Trash2 className={iconOnly ? "h-4 w-4" : "h-3 w-3"} />
        {!iconOnly && (pending ? "Deleting…" : label)}
      </Button>
      {error && <span className="text-xs text-destructive">{error}</span>}
    </span>
  );
}
