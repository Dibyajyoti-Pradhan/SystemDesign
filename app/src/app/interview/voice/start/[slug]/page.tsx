import { notFound } from "next/navigation";
import Link from "next/link";
import { db } from "@/db/client";
import { questions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { StartVoiceInterviewButton } from "@/components/interview/StartVoiceInterviewButton";

export default async function StartVoiceInterviewPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const [q] = await db.select().from(questions).where(eq(questions.slug, slug)).limit(1);
  if (!q) notFound();

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        .svi { height:100%; display:grid; place-items:center; padding: 40px; }
        .svi__card { max-width: 560px; width:100%; background: var(--surf); border:1px solid var(--line); border-radius: var(--r-3); padding: 36px; display:flex; flex-direction:column; gap: 22px; }
        .svi__mode { font-family: var(--font-mono); font-size: 10.5px; color: var(--accent); text-transform: uppercase; letter-spacing: .14em; display:flex; align-items:center; gap:8px; }
        .svi__beta { font-family: var(--font-mono); font-size: 9px; background: color-mix(in srgb, var(--accent) 15%, transparent); color: var(--accent); border: 1px solid color-mix(in srgb, var(--accent) 40%, transparent); border-radius: 3px; padding: 1px 6px; text-transform: uppercase; letter-spacing: .1em; }
        .svi__t { font-size: 26px; font-weight: 600; letter-spacing: -0.022em; line-height: 1.15; }
        .svi__meta { display:flex; gap: 8px; }
        .svi__format { display:flex; flex-direction:column; gap: 10px; }
        .svi__format-row { display:flex; align-items: flex-start; gap: 10px; font-size: 13.5px; color: var(--ink-2); line-height: 1.5; }
        .svi__format-icon { font-size: 16px; flex-shrink:0; margin-top: 1px; }
        .svi__actions { display:flex; gap: 10px; padding-top: 6px; }
      ` }} />
      <div className="svi">
        <div className="svi__card">
          <div className="svi__mode">
            Voice Interview
            <span className="svi__beta">beta</span>
          </div>
          <div className="svi__t">{q.title}</div>
          <div className="svi__meta">
            <span className="badge">#{String(q.number ?? 0).padStart(2, "0")}</span>
            <span className="badge">{q.difficulty}</span>
            <span className="badge">~{q.estMinutes} min</span>
          </div>
          <div className="svi__format">
            <div className="svi__format-row">
              <span className="svi__format-icon">🎙</span>
              <span>Speak your answers out loud. The AI interviewer listens and responds via voice.</span>
            </div>
            <div className="svi__format-row">
              <span className="svi__format-icon">✏️</span>
              <span>Draw your architecture on the whiteboard. The interviewer can see your diagram.</span>
            </div>
            <div className="svi__format-row">
              <span className="svi__format-icon">💬</span>
              <span>The full transcript is shown in a side panel as a reference — no typing required.</span>
            </div>
          </div>
          <div className="svi__actions">
            <StartVoiceInterviewButton slug={slug} />
            <Link href={`/${q.track}/voice-interviews`} className="btn btn--ghost">Cancel</Link>
          </div>
        </div>
      </div>
    </>
  );
}
