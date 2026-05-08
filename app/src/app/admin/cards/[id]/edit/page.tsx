import Link from "next/link";
import { notFound } from "next/navigation";
import { db } from "@/db/client";
import { cards, topics } from "@/db/schema";
import { eq } from "drizzle-orm";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft } from "lucide-react";
import { CardEditForm } from "@/components/srs/CardEditForm";

export const dynamic = "force-dynamic";

export default async function EditCardPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: idStr } = await params;
  const id = Number(idStr);
  if (!Number.isFinite(id)) notFound();

  const [row] = await db
    .select({
      id: cards.id,
      type: cards.type,
      front: cards.front,
      back: cards.back,
      diagramMermaid: cards.diagramMermaid,
      status: cards.status,
      topicTitle: topics.title,
      topicSlug: topics.slug,
    })
    .from(cards)
    .leftJoin(topics, eq(cards.topicId, topics.id))
    .where(eq(cards.id, id))
    .limit(1);

  if (!row) notFound();

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href="/admin/cards"
          className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <ArrowLeft className="h-4 w-4" /> Pending cards
        </Link>
        <div className="flex items-center gap-2 text-xs">
          <Badge variant="outline">{row.status}</Badge>
          {row.topicTitle && row.topicSlug && (
            <Link
              href={`/topics/${row.topicSlug}`}
              className="text-muted-foreground hover:text-foreground"
            >
              {row.topicTitle}
            </Link>
          )}
        </div>
      </div>

      <header>
        <h1 className="text-3xl font-bold tracking-tight">Edit card #{row.id}</h1>
        <p className="text-muted-foreground mt-1">
          Tweak the question, answer, or diagram before approving.
        </p>
      </header>

      <CardEditForm
        cardId={row.id}
        initialType={row.type}
        initialFront={row.front}
        initialBack={row.back}
        initialDiagram={row.diagramMermaid}
        initialStatus={row.status}
      />
    </div>
  );
}
