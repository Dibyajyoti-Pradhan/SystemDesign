import { notFound } from "next/navigation";
import Link from "next/link";
import { db } from "@/db/client";
import { interviewSessions, questions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Clock, ExternalLink, Bot, RotateCcw } from "lucide-react";
import { Chat } from "@/components/interview/Chat";
import { AiVsAiSession } from "@/components/interview/AiVsAiSession";
import { Rubric, type RubricData } from "@/components/interview/Rubric";
import { DeleteSessionButton } from "@/components/interview/DeleteSessionButton";
import { formatDate } from "@/lib/utils";

type SelfMsg = { role: "user" | "assistant"; content: string; ts: number };
type AiMsg =
  | { role: "interviewer" | "candidate"; content: string; ts: number }
  | {
      role: "steer";
      content: string;
      target: "interviewer" | "candidate" | "both";
      consumed: boolean;
      ts: number;
    };

function parseSelfTranscript(raw: string | null | undefined): SelfMsg[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (m): m is SelfMsg =>
        m &&
        typeof m === "object" &&
        (m.role === "user" || m.role === "assistant") &&
        typeof m.content === "string",
    );
  } catch {
    return [];
  }
}

function parseAiTranscript(raw: string | null | undefined): AiMsg[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (m): m is AiMsg =>
        m && typeof m === "object" && typeof m.role === "string" && typeof m.content === "string",
    );
  } catch {
    return [];
  }
}

function parseRubric(raw: string | null | undefined): RubricData | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (
      typeof parsed?.score === "number" &&
      parsed?.sections &&
      Array.isArray(parsed?.strengths) &&
      Array.isArray(parsed?.gaps)
    ) {
      return parsed as RubricData;
    }
    return null;
  } catch {
    return null;
  }
}

export default async function InterviewSessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: idStr } = await params;
  const id = Number.parseInt(idStr, 10);
  if (!Number.isFinite(id)) notFound();

  const [session] = await db.select().from(interviewSessions).where(eq(interviewSessions.id, id)).limit(1);
  if (!session) notFound();

  const [question] = await db.select().from(questions).where(eq(questions.id, session.questionId)).limit(1);
  if (!question) notFound();

  const isAiVsAi = session.mode === "ai_vs_ai";
  const rubric = parseRubric(session.rubric);
  const ended = !!session.endedAt;

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <Link
          href={`/${question.track}/questions/${question.slug}`}
          className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <ArrowLeft className="h-4 w-4" /> Practice
        </Link>
        <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
          {isAiVsAi && (
            <Badge variant="outline" className="gap-1">
              <Bot className="h-3 w-3" /> AI vs AI
            </Badge>
          )}
          <Badge variant="outline" className="capitalize">
            {question.difficulty}
          </Badge>
          <Badge variant="muted" className="inline-flex items-center gap-1">
            <Clock className="h-3 w-3" /> ~{question.estMinutes} min
          </Badge>
          {ended ? (
            <Badge variant="default">
              {typeof session.score === "number" ? `Graded ${session.score}/100` : "Completed"}
            </Badge>
          ) : (
            <Badge variant="secondary">In progress</Badge>
          )}
          {isAiVsAi && (
            <>
              <Button asChild variant="outline" size="sm" title="Start a fresh session for this question">
                <Link href={`/interview/ai-vs-ai/start/${question.slug}`}>
                  <RotateCcw className="h-3 w-3" /> Restart
                </Link>
              </Button>
              <DeleteSessionButton
                sessionId={session.id}
                redirectTo={`/${question.track}/questions`}
                size="sm"
              />
            </>
          )}
        </div>
      </div>

      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">{question.title}</h1>
        <p className="text-sm text-muted-foreground">
          Session #{session.id} &middot; started {formatDate(session.startedAt)}
          {question.pdfPath && (
            <>
              {" "}
              &middot;{" "}
              <a
                href={`/api/pdf?path=${encodeURIComponent(question.pdfPath)}`}
                target="_blank"
                className="inline-flex items-center gap-1 hover:text-foreground"
              >
                <ExternalLink className="h-3 w-3" /> reference PDF
              </a>
            </>
          )}
        </p>
      </header>

      {rubric ? (
        <>
          <Rubric data={rubric} />

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Transcript</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 max-h-[600px] overflow-y-auto">
              {isAiVsAi ? (
                (() => {
                  const t = parseAiTranscript(session.transcript);
                  if (t.length === 0)
                    return <p className="text-sm text-muted-foreground">No messages.</p>;
                  return t.map((m, i) => (
                    <div key={i} className="space-y-1">
                      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                        {m.role === "steer"
                          ? `Steer → ${(m as any).target}`
                          : m.role === "interviewer"
                            ? "Interviewer"
                            : "Candidate"}
                      </div>
                      <div className="text-sm whitespace-pre-wrap leading-relaxed">{m.content}</div>
                    </div>
                  ));
                })()
              ) : (
                (() => {
                  const t = parseSelfTranscript(session.transcript);
                  if (t.length === 0)
                    return <p className="text-sm text-muted-foreground">No messages.</p>;
                  return t.map((m, i) => (
                    <div key={i} className="space-y-1">
                      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                        {m.role === "user" ? "You" : "Interviewer"}
                      </div>
                      <div className="text-sm whitespace-pre-wrap leading-relaxed">{m.content}</div>
                    </div>
                  ));
                })()
              )}
            </CardContent>
          </Card>

          <div className="pt-2">
            <Button asChild variant="outline" size="sm">
              <Link href={`/${question.track}/questions`}>Try another question</Link>
            </Button>
          </div>
        </>
      ) : isAiVsAi ? (
        <AiVsAiSession
          sessionId={session.id}
          questionTitle={question.title}
          initialTranscript={parseAiTranscript(session.transcript)}
          initialEnded={ended}
        />
      ) : (
        <Chat sessionId={session.id} initialMessages={parseSelfTranscript(session.transcript)} />
      )}
    </div>
  );
}
