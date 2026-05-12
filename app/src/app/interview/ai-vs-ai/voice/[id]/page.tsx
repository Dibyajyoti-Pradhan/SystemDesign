import { notFound } from "next/navigation";
import { db } from "@/db/client";
import { interviewSessions, questions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { VoiceAiVsAiSession } from "@/components/interview/VoiceAiVsAiSession";

type StoredMsg =
  | { role: "interviewer" | "candidate"; content: string; ts: number }
  | { role: "steer"; content: string; target: string; consumed: boolean; ts: number };

function parseTranscript(raw: string | null | undefined) {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return (parsed as StoredMsg[]).filter(
      (m): m is { role: "interviewer" | "candidate"; content: string; ts: number } =>
        (m.role === "interviewer" || m.role === "candidate") && typeof m.content === "string",
    );
  } catch {
    return [];
  }
}

export default async function VoiceAiVsAiPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: idStr } = await params;
  const id = Number.parseInt(idStr, 10);
  if (!Number.isFinite(id)) notFound();

  const [session] = await db
    .select()
    .from(interviewSessions)
    .where(eq(interviewSessions.id, id))
    .limit(1);
  if (!session) notFound();
  if (session.mode !== "ai_vs_ai") notFound();

  const [question] = await db
    .select()
    .from(questions)
    .where(eq(questions.id, session.questionId))
    .limit(1);
  if (!question) notFound();

  const transcript = parseTranscript(session.transcript);
  const initialEnded = !!session.endedAt;

  return (
    <VoiceAiVsAiSession
      sessionId={session.id}
      questionTitle={question.title}
      initialTranscript={transcript}
      initialEnded={initialEnded}
    />
  );
}
