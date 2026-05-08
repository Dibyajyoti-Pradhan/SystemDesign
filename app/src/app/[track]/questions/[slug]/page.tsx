import { notFound } from "next/navigation";
import Link from "next/link";
import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import { db } from "@/db/client";
import { questions, interviewSessions } from "@/db/schema";
import { eq, desc, and } from "drizzle-orm";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  Clock,
  ExternalLink,
  User,
  Bot,
  FileText,
} from "lucide-react";
import { CONTENT_ROOT, parseTrack } from "@/lib/paths";
import { MdxRenderer } from "@/components/MdxRenderer";
import { relativeTime } from "@/lib/utils";
import { GenerateBriefButton } from "@/components/question/GenerateBriefButton";
import { DeleteSessionButton } from "@/components/interview/DeleteSessionButton";

function turnCount(transcript: string | null | undefined): number {
  if (!transcript) return 0;
  try {
    const parsed = JSON.parse(transcript);
    if (!Array.isArray(parsed)) return 0;
    return parsed.filter(
      (m: any) =>
        m && (m.role === "user" || m.role === "assistant" || m.role === "interviewer" || m.role === "candidate"),
    ).length;
  } catch {
    return 0;
  }
}

async function readBrief(mdxPath: string | null): Promise<string | null> {
  if (!mdxPath) return null;
  try {
    const abs = path.isAbsolute(mdxPath) ? mdxPath : path.join(CONTENT_ROOT, mdxPath);
    const raw = await fs.readFile(abs, "utf8");
    const { content } = matter(raw);
    return content;
  } catch {
    return null;
  }
}

export default async function QuestionDetailPage({
  params,
}: {
  params: Promise<{ track: string; slug: string }>;
}) {
  const { track: trackParam, slug } = await params;
  const track = parseTrack(trackParam);
  if (!track) notFound();
  const [q] = await db
    .select()
    .from(questions)
    .where(and(eq(questions.slug, slug), eq(questions.track, track)))
    .limit(1);
  if (!q) notFound();

  const briefBody = await readBrief(q.mdxPath);

  const sessions = await db
    .select()
    .from(interviewSessions)
    .where(eq(interviewSessions.questionId, q.id))
    .orderBy(desc(interviewSessions.startedAt));

  return (
    <div className="max-w-3xl mx-auto p-8 space-y-6">
      <Link
        href={`/${track}/questions`}
        className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
      >
        <ArrowLeft className="h-4 w-4" /> All questions
      </Link>

      <header className="space-y-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="font-mono">#{String(q.number ?? 0).padStart(2, "0")}</span>
          <Badge variant="outline" className="capitalize">{q.difficulty}</Badge>
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3 w-3" /> ~{q.estMinutes} min
          </span>
        </div>
        <h1 className="text-4xl font-bold tracking-tight">{q.title}</h1>
      </header>

      <div className="flex flex-wrap gap-2">
        <Button asChild size="lg">
          <Link href={`/interview/start/${q.slug}`}>
            <User className="h-4 w-4" /> Try yourself
          </Link>
        </Button>
        <Button asChild variant="secondary" size="lg">
          <Link href={`/interview/ai-vs-ai/start/${q.slug}`}>
            <Bot className="h-4 w-4" /> Watch AI vs AI
          </Link>
        </Button>
        {q.pdfPath && (
          <Button asChild variant="outline" size="lg">
            <a href={`/api/pdf?path=${encodeURIComponent(q.pdfPath)}`} target="_blank">
              <ExternalLink className="h-4 w-4" /> Reference PDF
            </a>
          </Button>
        )}
      </div>

      <section className="space-y-3">
        {briefBody ? (
          <Card>
            <CardContent className="py-6">
              <div className="prose-system">
                <MdxRenderer source={briefBody} />
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card className="border-primary/20 bg-primary/5">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <FileText className="h-4 w-4" /> No brief yet
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Generate a tight problem brief from the source PDF — only the question, never
                the solution. Uses your Claude Code subscription. ~20–40 seconds.
              </p>
              <GenerateBriefButton slug={q.slug} />
            </CardContent>
          </Card>
        )}
      </section>

      {sessions.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold">
            Past sessions <span className="text-muted-foreground font-normal">({sessions.length})</span>
          </h2>
          <Card>
            <CardContent className="p-0 divide-y">
              {sessions.map((s) => {
                const turns = turnCount(s.transcript);
                const ended = !!s.endedAt;
                return (
                  <div key={s.id} className="flex items-center gap-3 p-3 group">
                    {s.mode === "ai_vs_ai" ? (
                      <Bot className="h-4 w-4 text-muted-foreground shrink-0" />
                    ) : (
                      <User className="h-4 w-4 text-muted-foreground shrink-0" />
                    )}
                    <Link
                      href={`/interview/sessions/${s.id}`}
                      className="flex-1 min-w-0 text-sm hover:text-primary transition-colors"
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <span>{relativeTime(s.startedAt)}</span>
                        <span className="text-muted-foreground">·</span>
                        <span className="text-muted-foreground">{turns} turn{turns === 1 ? "" : "s"}</span>
                        <span className="text-muted-foreground">·</span>
                        <span className="text-muted-foreground">{s.mode === "ai_vs_ai" ? "AI vs AI" : "Yourself"}</span>
                        {ended ? (
                          typeof s.score === "number" ? (
                            <Badge variant="default" className="text-[10px] ml-1">{s.score}/100</Badge>
                          ) : (
                            <Badge variant="muted" className="text-[10px] ml-1">ended</Badge>
                          )
                        ) : (
                          <Badge variant="outline" className="text-[10px] ml-1">in progress</Badge>
                        )}
                      </div>
                    </Link>
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                      <DeleteSessionButton sessionId={s.id} iconOnly />
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}
