import { notFound } from "next/navigation";
import { db } from "@/db/client";
import { interviewSessions, questions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { VoiceInterviewSession } from "@/components/interview/VoiceInterviewSession";

const OPENING_PREFIX = `Let's get started. `;

function getFirstInterviewerMessage(
  questionTitle: string,
  questionDifficulty: string,
  estMinutes: number,
): string {
  return `${OPENING_PREFIX}Today we'll be working through a ${questionDifficulty} system-design problem: "${questionTitle}". This is a ${estMinutes}-minute interview. Before we dive in, I'd like you to ask me your clarifying questions to nail down the scope. Go ahead whenever you're ready.`;
}

export default async function VoiceInterviewPage({
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
  if (session.mode !== "voice") notFound();

  const [question] = await db
    .select()
    .from(questions)
    .where(eq(questions.id, session.questionId))
    .limit(1);
  if (!question) notFound();

  const openingMessage = getFirstInterviewerMessage(
    question.title,
    question.difficulty,
    question.estMinutes,
  );

  return (
    <div style={{ height: "100%", overflow: "hidden" }}>
      <VoiceInterviewSession
        sessionId={session.id}
        questionTitle={question.title}
        firstInterviewerMessage={openingMessage}
      />
    </div>
  );
}
