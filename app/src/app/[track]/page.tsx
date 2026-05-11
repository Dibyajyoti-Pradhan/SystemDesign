import { notFound } from "next/navigation";
import Link from "next/link";
import { db } from "@/db/client";
import { topics, questions, cards, interviewSessions } from "@/db/schema";
import { count, eq, lte, and, desc, isNotNull } from "drizzle-orm";
import { relativeTime } from "@/lib/utils";
import { parseTrack, TRACK_LABELS } from "@/lib/paths";

const CSS = `
.hm { height:100%; overflow:auto; }
.hm__inner { max-width: 1080px; margin: 0 auto; padding: 36px 36px 64px; }
.hm__hero { display:grid; grid-template-columns: 1fr auto; gap: 32px; align-items: end; padding-bottom: 28px; border-bottom: 1px solid var(--line); }
.hm__eyebrow { font-family: var(--font-mono); font-size: 11px; color: var(--accent); text-transform: uppercase; letter-spacing: .14em; margin-bottom: 10px; }
.hm__h { font-family: var(--font-ui); font-size: 38px; font-weight: 600; letter-spacing: -0.028em; line-height: 1.05; }
.hm__h em { font-family: var(--font-read); font-style: italic; font-weight: 400; color: var(--accent-2); }
.hm__sub { color: var(--mute); font-size: 15px; margin-top: 12px; max-width: 56ch; line-height: 1.55; }
.hm__stats { display:grid; grid-template-columns: repeat(3, auto); gap: 32px; padding: 4px 0 6px; }
.stat { display:flex; flex-direction: column; gap: 2px; }
.stat__n { font-family: var(--font-read); font-style: italic; font-weight: 400; font-size: 36px; line-height: 1; letter-spacing: -0.02em; }
.stat__l { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .1em; margin-top: 4px; }
.stat--accent .stat__n { color: var(--accent); }
.hm__row { display:grid; grid-template-columns: 1fr 360px; gap: 36px; padding-top: 32px; }
.blk { display:flex; flex-direction: column; gap: 14px; }
.blk__h { display:flex; align-items: baseline; gap: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--line); }
.blk__h .lbl { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .14em; }
.blk__h .ct { font-family: var(--font-mono); font-size: 11px; color: var(--mute-2); margin-left: auto; }
.rec { display:flex; flex-direction: column; gap: 10px; }
.rec__r { display:grid; grid-template-columns: 60px 1fr auto; gap: 12px; padding: 12px 14px; border:1px solid var(--line); border-radius: 8px; background: var(--bg-2); align-items: center; }
.rec__k { font-family: var(--font-mono); font-size: 9.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .14em; }
.rec__t { font-size: 13.5px; color: var(--ink); letter-spacing: -0.005em; }
.rec__t em { display:block; font-family: var(--font-mono); font-size: 10px; color: var(--mute-2); margin-top: 3px; font-style: normal; text-transform: uppercase; letter-spacing: .08em; }
.rec__ago { font-family: var(--font-mono); font-size: 11px; color: var(--mute); }
.plan { display:flex; flex-direction: column; gap: 10px; }
.plan__item { display:flex; align-items: center; gap: 14px; padding: 14px 16px; border:1px solid var(--line); border-radius: 8px; background: var(--bg-2); text-decoration: none; color: inherit; }
.plan__item:hover { border-color: var(--line-2); background: var(--surf); }
.plan__num { font-family: var(--font-mono); font-size: 11px; color: var(--mute-2); width: 18px; }
.plan__text { font-size: 13.5px; color: var(--ink); letter-spacing: -0.005em; flex:1; }
.plan__arrow { color: var(--mute-2); font-size: 16px; }
.plan__item:hover .plan__arrow { color: var(--accent); }
`;

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export default async function TrackHome({
  params,
}: {
  params: Promise<{ track: string }>;
}) {
  const { track: trackParam } = await params;
  const track = parseTrack(trackParam);
  if (!track) notFound();

  const now = new Date();

  const [topicCount] = await db.select({ n: count() }).from(topics).where(eq(topics.track, track));
  const [questionCount] = await db.select({ n: count() }).from(questions).where(eq(questions.track, track));

  // Cards inherit track via topic.
  const [activeCardCount] = await db
    .select({ n: count() })
    .from(cards)
    .leftJoin(topics, eq(cards.topicId, topics.id))
    .where(and(eq(cards.status, "active"), eq(topics.track, track)));

  const [dueCount] = await db
    .select({ n: count() })
    .from(cards)
    .leftJoin(topics, eq(cards.topicId, topics.id))
    .where(and(eq(cards.status, "active"), eq(topics.track, track), lte(cards.dueAt, now)));

  const [pendingCount] = await db
    .select({ n: count() })
    .from(cards)
    .leftJoin(topics, eq(cards.topicId, topics.id))
    .where(and(eq(cards.status, "pending_review"), eq(topics.track, track)));

  const recentTopics = await db
    .select()
    .from(topics)
    .where(and(eq(topics.track, track), isNotNull(topics.lastVisitedAt)))
    .orderBy(desc(topics.lastVisitedAt))
    .limit(5);

  const recentSessions = await db
    .select({
      id: interviewSessions.id,
      questionId: interviewSessions.questionId,
      score: interviewSessions.score,
      startedAt: interviewSessions.startedAt,
      title: questions.title,
    })
    .from(interviewSessions)
    .leftJoin(questions, eq(interviewSessions.questionId, questions.id))
    .where(eq(questions.track, track))
    .orderBy(desc(interviewSessions.startedAt))
    .limit(3);

  // Build a combined "recently" list
  type RecentItem =
    | { kind: "topic"; id: number; title: string; slug: string; ts: Date }
    | { kind: "session"; id: number; title: string | null; score: number | null; ts: Date };

  const recentItems: RecentItem[] = [
    ...recentTopics.map((t) => ({
      kind: "topic" as const,
      id: t.id,
      title: t.title,
      slug: t.slug,
      ts: t.lastVisitedAt!,
    })),
    ...recentSessions.map((s) => ({
      kind: "session" as const,
      id: s.id,
      title: s.title,
      score: s.score,
      ts: s.startedAt,
    })),
  ]
    .sort((a, b) => b.ts.getTime() - a.ts.getTime())
    .slice(0, 6);

  const trackLabel = TRACK_LABELS[track];
  const greeting = getGreeting();

  return (
    <div className="hm">
      <style dangerouslySetInnerHTML={{ __html: CSS }} />
      <div className="hm__inner">
        {/* Hero */}
        <div className="hm__hero">
          <div>
            <div className="hm__eyebrow">{trackLabel}</div>
            <h1 className="hm__h">
              {greeting}. Pick up where you <em>left off.</em>
            </h1>
            <p className="hm__sub">
              {activeCardCount.n} cards in your deck
              {dueCount.n > 0 ? `, ${dueCount.n} due today` : ", all caught up"}.{" "}
              {topicCount.n} topics · {questionCount.n} questions.
            </p>
          </div>
          <div className="hm__stats">
            <div className={`stat${dueCount.n > 0 ? " stat--accent" : ""}`}>
              <span className="stat__n">{dueCount.n}</span>
              <span className="stat__l">Cards due</span>
            </div>
            <div className="stat">
              <span className="stat__n">{topicCount.n}</span>
              <span className="stat__l">Topics</span>
            </div>
            <div className="stat">
              <span className="stat__n">{questionCount.n}</span>
              <span className="stat__l">Questions</span>
            </div>
          </div>
        </div>

        {/* Two-column row */}
        <div className="hm__row">
          {/* Left: Tonight's plan */}
          <div className="blk">
            <div className="blk__h">
              <span className="lbl">Tonight&apos;s plan</span>
            </div>
            <div className="plan">
              <Link href={`/${track}/review`} className="plan__item">
                <span className="plan__num">01</span>
                <span className="plan__text">
                  Review {dueCount.n} due card{dueCount.n !== 1 ? "s" : ""}
                </span>
                <span className="plan__arrow">›</span>
              </Link>
              <Link href={`/${track}/topics`} className="plan__item">
                <span className="plan__num">02</span>
                <span className="plan__text">
                  Browse topics ({topicCount.n} available)
                </span>
                <span className="plan__arrow">›</span>
              </Link>
              <Link href={`/${track}/questions`} className="plan__item">
                <span className="plan__num">03</span>
                <span className="plan__text">Mock interview</span>
                <span className="plan__arrow">›</span>
              </Link>
            </div>
          </div>

          {/* Right: Recently */}
          <div className="blk">
            <div className="blk__h">
              <span className="lbl">Recently</span>
              <span className="ct">{recentItems.length} items</span>
            </div>
            <div className="rec">
              {recentItems.length === 0 ? (
                <p style={{ color: "var(--mute)", fontSize: "13px" }}>
                  Nothing yet — start exploring topics.
                </p>
              ) : (
                recentItems.map((item) =>
                  item.kind === "topic" ? (
                    <Link
                      key={`topic-${item.id}`}
                      href={`/${track}/topics/${item.slug}`}
                      style={{ textDecoration: "none" }}
                    >
                      <div className="rec__r">
                        <span className="rec__k">Topic</span>
                        <span className="rec__t">{item.title}</span>
                        <span className="rec__ago">{relativeTime(item.ts)}</span>
                      </div>
                    </Link>
                  ) : (
                    <Link
                      key={`session-${item.id}`}
                      href={`/interview/sessions/${item.id}`}
                      style={{ textDecoration: "none" }}
                    >
                      <div className="rec__r">
                        <span className="rec__k">Session</span>
                        <span className="rec__t">
                          {item.title ?? `Session #${item.id}`}
                          {item.score != null && (
                            <em>{item.score}/100</em>
                          )}
                        </span>
                        <span className="rec__ago">{relativeTime(item.ts)}</span>
                      </div>
                    </Link>
                  )
                )
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
