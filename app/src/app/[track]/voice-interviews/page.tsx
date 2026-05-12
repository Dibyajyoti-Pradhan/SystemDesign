import { notFound } from "next/navigation";
import { db } from "@/db/client";
import { questions, interviewSessions, type Question } from "@/db/schema";
import { asc, eq, inArray, and } from "drizzle-orm";
import { parseTrack, TRACK_LABELS } from "@/lib/paths";
import { StartVoiceInterviewButton } from "@/components/interview/StartVoiceInterviewButton";
import { StartAiVsAiVoiceButton } from "@/components/interview/StartAiVsAiVoiceButton";

export async function generateMetadata({ params }: { params: Promise<{ track: string }> }) {
  const { track } = await params;
  const label = track === "coding" ? "Coding" : "System Design";
  return { title: label + " Voice Interviews" };
}

export default async function VoiceInterviewsPage({
  params,
}: {
  params: Promise<{ track: string }>;
}) {
  const { track: trackParam } = await params;
  const track = parseTrack(trackParam);
  if (!track) notFound();

  const all: Question[] = await db
    .select()
    .from(questions)
    .where(eq(questions.track, track))
    .orderBy(asc(questions.number));

  const questionIds = all.map((q: Question) => q.id);
  const sessions = questionIds.length
    ? await db
        .select({ questionId: interviewSessions.questionId })
        .from(interviewSessions)
        .where(
          and(
            inArray(interviewSessions.questionId, questionIds),
            eq(interviewSessions.mode, "voice"),
          ),
        )
    : [];

  const sessionsByQuestion = new Map<number, number>();
  for (const s of sessions) {
    sessionsByQuestion.set(s.questionId, (sessionsByQuestion.get(s.questionId) ?? 0) + 1);
  }

  const empty = all.length === 0;

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        .vl { height:100%; overflow:auto; }
        .vl__inner { max-width: 1080px; margin: 0 auto; padding: 36px 36px 64px; }
        .vl__head { display:flex; align-items: end; gap: 24px; padding-bottom: 24px; border-bottom: 1px solid var(--line); }
        .vl__h { font-size: 30px; font-weight: 600; letter-spacing: -0.024em; }
        .vl__h em { font-family: var(--font-read); font-style: italic; font-weight: 400; color: var(--mute); }
        .vl__sub { color: var(--mute); font-size: 14px; margin-top: 8px; max-width: 56ch; }
        .vl__beta { font-family: var(--font-mono); font-size: 9.5px; background: color-mix(in srgb, var(--accent) 15%, transparent); color: var(--accent); border: 1px solid color-mix(in srgb, var(--accent) 40%, transparent); border-radius: 3px; padding: 2px 7px; text-transform: uppercase; letter-spacing: .1em; vertical-align: middle; margin-left: 8px; }
        .vl__r { margin-left: auto; display:flex; gap:8px; }
        .vl__counts { display:flex; gap:18px; padding: 14px 0 4px; }
        .vl__counts span { font-family: var(--font-mono); font-size:11px; color:var(--mute); text-transform:uppercase; letter-spacing:.1em; }
        .vl__counts b { color: var(--ink); font-weight:500; }
        .vr { display:grid; grid-template-columns: 32px 1fr 80px 80px auto; gap:18px; padding: 16px 6px; border-bottom: 1px solid var(--line); align-items:center; }
        .vr__n { font-family: var(--font-mono); font-size: 11px; color: var(--mute-2); padding-left: 6px; }
        .vr__t { font-size: 14.5px; color: var(--ink); letter-spacing: -0.005em; font-weight: 500; }
        .vr__d { font-family: var(--font-mono); font-size: 10.5px; text-transform: uppercase; letter-spacing: .12em; }
        .vr__min { font-family: var(--font-mono); font-size: 11px; color: var(--mute); text-align: right; }
        .vr__btn { display:flex; gap: 8px; align-items: center; justify-content: flex-end; }
      ` }} />
      <div className="vl">
        <div className="vl__inner">
          <div className="vl__head">
            <div>
              <h1 className="vl__h">
                {TRACK_LABELS[track]} <em>voice interviews</em>
                <span className="vl__beta">beta</span>
              </h1>
              <p className="vl__sub">
                Speak your answers. Draw on the whiteboard. The AI interviewer responds via voice.
              </p>
            </div>
            <div className="vl__r">
              <div className="vl__counts">
                <span><b>{all.length}</b> questions</span>
                <span><b>{sessions.length}</b> voice sessions</span>
              </div>
            </div>
          </div>

          {empty ? (
            <div style={{ padding: "56px 0", display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
              <div style={{ fontFamily: "var(--font-read)", fontSize: 32, fontStyle: "italic", color: "var(--mute)", letterSpacing: "-0.02em" }}>
                Coming soon.
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--mute-2)", textAlign: "center", maxWidth: "42ch" }}>
                No questions yet for this track. Switch to System Design to get started.
              </div>
            </div>
          ) : (
            <div>
              {all.map((q: Question, idx: number) => {
                const past = sessionsByQuestion.get(q.id) ?? 0;
                const diffColor =
                  q.difficulty === "easy"
                    ? "var(--good)"
                    : q.difficulty === "hard"
                    ? "var(--bad)"
                    : "var(--warn)";
                return (
                  <div key={q.id} className="vr">
                    <span className="vr__n">{String(q.number ?? idx + 1).padStart(2, "0")}</span>
                    <span className="vr__t">{q.title}</span>
                    <span className="vr__d" style={{ color: diffColor }}>{q.difficulty}</span>
                    <span className="vr__min">~{q.estMinutes}m</span>
                    <div className="vr__btn">
                      <StartAiVsAiVoiceButton slug={q.slug} />
                      <StartVoiceInterviewButton slug={q.slug} past={past} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
