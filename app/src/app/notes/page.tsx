import Link from "next/link";
import { db } from "@/db/client";
import { notes, topics, questions } from "@/db/schema";
import { desc, eq } from "drizzle-orm";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { NoteEditor } from "@/components/NoteEditor";
import { relativeTime } from "@/lib/utils";

export default async function NotesPage({
  searchParams,
}: {
  searchParams: Promise<{ topic?: string; question?: string }>;
}) {
  const sp = await searchParams;

  let attachedTopic = null;
  let attachedQuestion = null;
  if (sp.topic) {
    [attachedTopic] = await db.select().from(topics).where(eq(topics.slug, sp.topic)).limit(1);
  }
  if (sp.question) {
    [attachedQuestion] = await db.select().from(questions).where(eq(questions.slug, sp.question)).limit(1);
  }

  const allNotes = await db
    .select({
      n: notes,
      topicTitle: topics.title,
      topicSlug: topics.slug,
      questionTitle: questions.title,
      questionSlug: questions.slug,
    })
    .from(notes)
    .leftJoin(topics, eq(notes.topicId, topics.id))
    .leftJoin(questions, eq(notes.questionId, questions.id))
    .orderBy(desc(notes.updatedAt))
    .limit(50);

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Notes</h1>
        <p className="text-muted-foreground mt-1">Your own scratchpad. Markdown supported. Optionally attach to a topic or question.</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">New note</CardTitle>
          {attachedTopic && <CardDescription>Attached to topic: <Badge variant="muted">{attachedTopic.title}</Badge></CardDescription>}
          {attachedQuestion && <CardDescription>Attached to question: <Badge variant="muted">{attachedQuestion.title}</Badge></CardDescription>}
        </CardHeader>
        <CardContent>
          <NoteEditor topicId={attachedTopic?.id ?? null} questionId={attachedQuestion?.id ?? null} />
        </CardContent>
      </Card>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">All notes</h2>
        {allNotes.length === 0 && (
          <p className="text-sm text-muted-foreground">No notes yet.</p>
        )}
        {allNotes.map(({ n, topicTitle, topicSlug, questionTitle, questionSlug }) => (
          <Card key={n.id}>
            <CardContent className="py-4 space-y-2">
              <div className="flex items-center justify-between gap-2 text-xs">
                <div className="flex gap-2 flex-wrap">
                  {topicTitle && (
                    <Link href={`/topics/${topicSlug}`}>
                      <Badge variant="muted" className="cursor-pointer hover:bg-muted/80">{topicTitle}</Badge>
                    </Link>
                  )}
                  {questionTitle && (
                    <Link href={`/questions/${questionSlug}`}>
                      <Badge variant="outline" className="cursor-pointer">{questionTitle}</Badge>
                    </Link>
                  )}
                </div>
                <span className="text-muted-foreground">{relativeTime(n.updatedAt)}</span>
              </div>
              <pre className="whitespace-pre-wrap text-sm font-sans">{n.body}</pre>
              <div className="flex gap-1">
                <form action={`/api/notes/${n.id}`} method="POST">
                  <input type="hidden" name="_method" value="DELETE" />
                  <Button type="submit" variant="ghost" size="sm" className="text-xs h-7">Delete</Button>
                </form>
              </div>
            </CardContent>
          </Card>
        ))}
      </section>
    </div>
  );
}
