import { notFound } from "next/navigation";
import Link from "next/link";
import { db } from "@/db/client";
import { questions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { StartInterviewButton } from "@/components/interview/StartInterviewButton";

export default async function StartAiVsAi({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [q] = await db.select().from(questions).where(eq(questions.slug, slug)).limit(1);
  if (!q) notFound();

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        .si { height:100%; display:grid; place-items:center; padding: 40px; }
        .si__card { max-width: 540px; width:100%; background: var(--surf); border:1px solid var(--line); border-radius: var(--r-3); padding: 36px; display:flex; flex-direction:column; gap: 22px; }
        .si__mode { font-family: var(--font-mono); font-size: 10.5px; color: var(--accent); text-transform: uppercase; letter-spacing: .14em; }
        .si__t { font-size: 26px; font-weight: 600; letter-spacing: -0.022em; line-height: 1.15; }
        .si__meta { display:flex; gap: 8px; }
        .si__desc { font-size: 14px; color: var(--mute); line-height: 1.6; }
        .si__actions { display:flex; gap: 10px; padding-top: 6px; }
      ` }} />
      <div className="si">
        <div className="si__card">
          <div className="si__mode">AI vs AI</div>
          <div className="si__t">{q.title}</div>
          <div className="si__meta">
            <span className="badge">#{String(q.number ?? 0).padStart(2, "0")}</span>
            <span className="badge">{q.difficulty}</span>
            <span className="badge">~{q.estMinutes} min</span>
          </div>
          <div className="si__desc">
            Watch two AI agents debate this question live — one plays the interviewer, one the candidate. You can steer the conversation or just observe. A score is generated at the end.
          </div>
          <div className="si__actions">
            <StartInterviewButton slug={slug} mode="ai_vs_ai" />
            <Link href={`/system-design/questions/${slug}`} className="btn btn--ghost">Cancel</Link>
          </div>
        </div>
      </div>
    </>
  );
}
