import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { db } from "@/db/client";
import { questions, interviewSessions } from "@/db/schema";
import { eq } from "drizzle-orm";

export default async function StartAiVsAi({ params }: { params: Promise<{ slug: string }> }) {
  const session = await auth();
  if (!session?.user?.id) redirect("/sign-in");

  const { slug } = await params;
  const [q] = await db.select().from(questions).where(eq(questions.slug, slug)).limit(1);
  if (!q) redirect("/questions");

  const [created] = await db
    .insert(interviewSessions)
    .values({
      userId: session.user.id,
      questionId: q.id,
      mode: "ai_vs_ai",
      transcript: "[]",
    })
    .returning({ id: interviewSessions.id });

  redirect(`/interview/sessions/${created.id}`);
}
