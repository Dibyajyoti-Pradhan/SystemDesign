"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export function NoteEditor({ topicId, questionId }: { topicId: number | null; questionId: number | null }) {
  const [body, setBody] = useState("");
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    startTransition(async () => {
      const res = await fetch("/api/notes", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ body, topicId, questionId }),
      });
      if (res.ok) {
        setBody("");
        router.refresh();
      }
    });
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="What did you learn? Capacity numbers, gotchas, your own diagram in Mermaid..."
        rows={5}
        className="w-full p-3 text-sm border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring font-mono"
      />
      <div className="flex justify-between items-center">
        <p className="text-xs text-muted-foreground">Markdown supported.</p>
        <Button type="submit" disabled={pending || !body.trim()}>
          {pending ? "Saving..." : "Save note"}
        </Button>
      </div>
    </form>
  );
}
