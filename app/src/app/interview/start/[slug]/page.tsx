import { notFound, redirect } from "next/navigation";
import { auth } from "@/auth";
import { db } from "@/db/client";
import { questions, interviewSessions } from "@/db/schema";
import { eq } from "drizzle-orm";

// Server component: create a fresh session row, redirect.
export default async function StartInterviewPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const session = await auth();
  if (!session?.user?.id) redirect("/sign-in");

  const { slug } = await params;
  const [q] = await db.select().from(questions).where(eq(questions.slug, slug)).limit(1);
  if (!q) notFound();

  const inserted = await db
    .insert(interviewSessions)
    .values({
      userId: session.user.id,
      questionId: q.id,
      transcript: "[]",
    })
    .returning({ id: interviewSessions.id });

  const id = inserted[0]?.id;
  if (!id) {
    throw new Error("Failed to create interview session");
  }
  redirect(`/interview/sessions/${id}`);
}
