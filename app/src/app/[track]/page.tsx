import { notFound } from "next/navigation";
import Link from "next/link";
import { db } from "@/db/client";
import { topics, questions, cards, interviewSessions } from "@/db/schema";
import { count, eq, lte, and, desc, isNotNull } from "drizzle-orm";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Sparkles, BookOpen, Library, MessageSquare, ArrowRight } from "lucide-react";
import { relativeTime } from "@/lib/utils";
import { parseTrack, TRACK_LABELS } from "@/lib/paths";

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

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">{TRACK_LABELS[track]}</h1>
        <p className="text-muted-foreground mt-1">Your daily 15 minutes to ace the interview.</p>
      </header>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-primary/20">
          <CardHeader className="pb-3">
            <CardDescription>Today&apos;s queue</CardDescription>
            <CardTitle className="text-3xl">{dueCount.n}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              {dueCount.n === 0 ? "Caught up. Nice." : `cards due for review`}
            </p>
            <Button asChild size="sm" disabled={dueCount.n === 0}>
              <Link href={`/${track}/review`}>
                <Sparkles className="h-4 w-4" />
                Start review
              </Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Library</CardDescription>
            <CardTitle className="text-3xl">{topicCount.n}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-sm text-muted-foreground">topics · {questionCount.n} questions</p>
            <Button asChild variant="ghost" size="sm" className="px-0 h-auto">
              <Link href={`/${track}/topics`}>
                Browse topics <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Cards</CardDescription>
            <CardTitle className="text-3xl">{activeCardCount.n}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-sm text-muted-foreground">
              active{" "}
              {pendingCount.n > 0 && (
                <Badge variant="muted" className="ml-1">
                  {pendingCount.n} pending review
                </Badge>
              )}
            </p>
            {pendingCount.n > 0 && (
              <Button asChild variant="ghost" size="sm" className="px-0 h-auto">
                <Link href="/admin/cards">
                  Review queue <ArrowRight className="h-3 w-3" />
                </Link>
              </Button>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Library className="h-4 w-4" /> Recent topics
            </CardTitle>
          </CardHeader>
          <CardContent>
            {recentTopics.length === 0 ? (
              <p className="text-sm text-muted-foreground">Visit a topic to start tracking.</p>
            ) : (
              <ul className="space-y-2">
                {recentTopics.map((t) => (
                  <li key={t.id} className="flex justify-between items-center text-sm">
                    <Link href={`/${track}/topics/${t.slug}`} className="hover:underline">
                      {t.title}
                    </Link>
                    <span className="text-xs text-muted-foreground">{relativeTime(t.lastVisitedAt)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <MessageSquare className="h-4 w-4" /> Recent sessions
            </CardTitle>
          </CardHeader>
          <CardContent>
            {recentSessions.length === 0 ? (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">No sessions yet.</p>
                <Button asChild size="sm" variant="outline">
                  <Link href={`/${track}/questions`}>
                    <BookOpen className="h-4 w-4" /> Start one
                  </Link>
                </Button>
              </div>
            ) : (
              <ul className="space-y-2">
                {recentSessions.map((s) => (
                  <li key={s.id} className="flex justify-between items-center text-sm">
                    <Link href={`/interview/sessions/${s.id}`} className="hover:underline truncate">
                      {s.title ?? `Session #${s.id}`}
                    </Link>
                    <span className="text-xs text-muted-foreground">
                      {s.score != null ? `${s.score}/100` : "in progress"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
