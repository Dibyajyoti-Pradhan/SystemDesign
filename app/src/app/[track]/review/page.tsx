import { notFound } from "next/navigation";
import Link from "next/link";
import { db } from "@/db/client";
import { cards, topics } from "@/db/schema";
import { and, eq, lte, asc, desc, isNull, or } from "drizzle-orm";
import { ReviewSession, type ReviewCard } from "@/components/srs/ReviewSession";
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

  if (queue.length === 0) {
    return (
      <>
        <style dangerouslySetInnerHTML={{ __html: `
          .srd { height: 100%; display: grid; place-items: center; padding: 40px; }
          .srd__inner { max-width: 580px; text-align: center; display:flex; flex-direction: column; align-items: center; gap: 18px; }
          .srd__t { font-family: var(--font-read); font-style: italic; font-weight: 400; font-size: 56px; letter-spacing: -0.024em; line-height: 1.05; color: var(--ink); }
          .srd__sub { font-family: var(--font-read); font-size: 18px; color: var(--mute); line-height: 1.55; max-width: 44ch; }
        ` }} />
        <div className="srd">
          <div className="srd__inner">
            <div className="srd__t">All caught up.</div>
            <div className="srd__sub">
              No cards due right now
              {topicTitle ? ` in ${topicTitle}` : ""}.
              Come back tomorrow or add more topics to grow your deck.
            </div>
            <Link
              href={topicSlug ? `/${track}/topics/${topicSlug}` : `/${track}/topics`}
              className="btn btn--ghost"
            >
              {topicSlug ? "Back to topic" : `Browse ${TRACK_LABELS[track]} topics`}
            </Link>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        .srs-wrap { height:100%; display:grid; grid-template-rows: auto 1fr; background: var(--bg); }
        .srs-top { padding: 16px 32px 0; display:flex; align-items: center; gap: 14px; }
        .srs-count { font-family: var(--font-mono); font-size: 11px; color: var(--mute); text-transform: uppercase; letter-spacing: .12em; }
        .srs-count b { color: var(--ink); font-weight: 600; }
        .srs-bar { flex:1; height: 2px; background: var(--surf-3); border-radius: 999px; overflow: hidden; max-width: 520px; }
        .srs-bar > i { display:block; height:100%; background: var(--accent); }
        .srs-main { padding: 24px 32px; overflow:auto; }
      ` }} />
      <div className="srs-wrap">
        <div className="srs-top">
          <div className="srs-count">
            <b>{queue.length}</b> due today
            {topicTitle && <> · {topicTitle}</>}
            {!topicTitle && <> · {TRACK_LABELS[track]}</>}
          </div>
          <div className="srs-bar">
            <i style={{ width: "0%" }} />
          </div>
        </div>
        <div className="srs-main">
          <ReviewSession cards={queue} topicSlug={topicSlug} track={track} />
        </div>
      </div>
    </>
  );
}
