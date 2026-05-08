import { notFound } from "next/navigation";
import Link from "next/link";
import { db } from "@/db/client";
import { questions, interviewSessions } from "@/db/schema";
import { asc, eq, inArray } from "drizzle-orm";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Clock, MessageSquare } from "lucide-react";
import { parseTrack, TRACK_LABELS } from "@/lib/paths";

export default async function QuestionsPage({
  params,
}: {
  params: Promise<{ track: string }>;
}) {
  const { track: trackParam } = await params;
  const track = parseTrack(trackParam);
  if (!track) notFound();

  const all = await db
    .select()
    .from(questions)
    .where(eq(questions.track, track))
    .orderBy(asc(questions.number));

  const questionIds = all.map((q) => q.id);
  const sessions = questionIds.length
    ? await db
        .select({ questionId: interviewSessions.questionId })
        .from(interviewSessions)
        .where(inArray(interviewSessions.questionId, questionIds))
    : [];

  const sessionsByQuestion = new Map<number, number>();
  for (const s of sessions) {
    sessionsByQuestion.set(s.questionId, (sessionsByQuestion.get(s.questionId) ?? 0) + 1);
  }

  const empty = all.length === 0;

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">
          {track === "coding" ? "Theoretical Q&A" : "Practice"}
        </h1>
        <p className="text-muted-foreground mt-1">
          {track === "coding"
            ? `${TRACK_LABELS[track]} · explain-it-like-a-staff-engineer style questions.`
            : "Pick a question to read the brief and start a session."}
        </p>
      </header>

      {empty ? (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            <p className="text-sm">No questions seeded for {TRACK_LABELS[track]} yet.</p>
            <p className="text-xs mt-1">
              Drop PDFs / .docx / .md into <code className="bg-muted px-1.5 py-0.5 rounded">{track}/interview-questions/</code> and run <code className="bg-muted px-1.5 py-0.5 rounded">npm run seed</code>.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {all.map((q) => {
            const past = sessionsByQuestion.get(q.id) ?? 0;
            return (
              <Link
                key={q.id}
                href={`/${track}/questions/${q.slug}`}
                className="block group"
              >
                <Card className="h-full transition-all hover:border-primary/40 hover:shadow-md">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle className="text-base group-hover:text-primary transition-colors">
                        <span className="text-muted-foreground font-mono text-xs mr-1.5">
                          #{String(q.number ?? 0).padStart(2, "0")}
                        </span>
                        {q.title}
                      </CardTitle>
                      <Badge variant="outline" className="text-[10px] capitalize shrink-0">
                        {q.difficulty}
                      </Badge>
                    </div>
                    <CardDescription className="flex items-center gap-2 text-xs">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3 w-3" /> ~{q.estMinutes} min
                      </span>
                      {past > 0 && (
                        <>
                          <span>·</span>
                          <span className="inline-flex items-center gap-1">
                            <MessageSquare className="h-3 w-3" />
                            {past} past
                          </span>
                        </>
                      )}
                    </CardDescription>
                  </CardHeader>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
