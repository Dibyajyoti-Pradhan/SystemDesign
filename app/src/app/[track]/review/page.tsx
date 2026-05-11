import { notFound } from "next/navigation";
import Link from "next/link";
import { db } from "@/db/client";
import { cards, topics } from "@/db/schema";
import { and, eq, lte, asc, desc, isNull, or } from "drizzle-orm";
import { ReviewSession, type ReviewCard } from "@/components/srs/ReviewSession";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft } from "lucide-react";
import { parseTrack, TRACK_LABELS } from "@/lib/paths";

export const dynamic = "force-dynamic";

export default async function ReviewPage({
  params,
  searchParams,
}: {
  params: Promise<{ track: string }>;
  searchParams: Promise<{ topic?: string }>;
}) {
  const { track: trackParam } = await params;
  const track = parseTrack(trackParam);
  if (!track) notFound();
  const { topic: topicSlug } = await searchParams;
  const now = new Date();

  let topicFilterId: number | null = null;
  let topicTitle: string | null = null;
  if (topicSlug) {
    const [t] = await db
      .select()
      .from(topics)
      .where(and(eq(topics.slug, topicSlug), eq(topics.track, track)))
      .limit(1);
    if (t) {
      topicFilterId = t.id;
      topicTitle = t.title;
    }
  }

  const dueClause = or(isNull(cards.dueAt), lte(cards.dueAt, now));
  // Track-scoped: cards inherit track from their topic via the join.
  const whereClause = topicFilterId
    ? and(eq(cards.status, "active"), eq(cards.topicId, topicFilterId), dueClause)
    : and(eq(cards.status, "active"), eq(topics.track, track), dueClause);

  const rows = await db
    .select({
      id: cards.id,
      type: cards.type,
      front: cards.front,
      back: cards.back,
      diagramMermaid: cards.diagramMermaid,
      topicTitle: topics.title,
      topicSlug: topics.slug,
    })
    .from(cards)
    .leftJoin(topics, eq(cards.topicId, topics.id))
    .where(whereClause)
    .orderBy(desc(cards.difficulty), asc(cards.dueAt));

  const queue: ReviewCard[] = rows.map((r) => ({
    id: r.id,
    type: r.type,
    front: r.front,
    back: r.back,
    diagramMermaid: r.diagramMermaid,
    topicTitle: r.topicTitle,
    topicSlug: r.topicSlug,
  }));

  return (
    <div className="max-w-3xl mx-auto p-8 space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href={topicSlug ? `/${track}/topics/${topicSlug}` : `/${track}/topics`}
          className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <ArrowLeft className="h-4 w-4" /> {topicSlug ? "Back to topic" : "All topics"}
        </Link>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline">{TRACK_LABELS[track]}</Badge>
          {topicTitle && <Badge variant="outline">{topicTitle}</Badge>}
          <Badge variant="muted">{queue.length} due</Badge>
        </div>
      </div>

      <header>
        <h1 className="text-3xl font-bold tracking-tight">Review</h1>
        <p className="text-muted-foreground mt-1">
          {queue.length === 0
            ? "Inbox zero. Nothing left to drill."
            : `${queue.length} ${queue.length === 1 ? "card" : "cards"} due now${
                topicTitle ? ` in ${topicTitle}` : ""
              }.`}
        </p>
      </header>

      <ReviewSession cards={queue} topicSlug={topicSlug} track={track} />
    </div>
  );
}
