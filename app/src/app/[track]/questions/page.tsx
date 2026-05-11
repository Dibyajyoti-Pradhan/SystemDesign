import { notFound } from "next/navigation";
import Link from "next/link";
import { db } from "@/db/client";
import { questions, interviewSessions } from "@/db/schema";
import { asc, eq, inArray, and, isNotNull } from "drizzle-orm";
import { parseTrack, TRACK_LABELS } from "@/lib/paths";
import { LanguageFilter } from "@/components/LanguageFilter";

export async function generateMetadata({ params }: { params: Promise<{ track: string }> }) {
  const { track } = await params;
  const label = track === "coding" ? "Coding" : "System Design";
  return { title: label + " Questions" };
}


export default async function QuestionsPage({
  params,
  searchParams,
}: {
  params: Promise<{ track: string }>;
  searchParams: Promise<{ lang?: string }>;
}) {
  const { track: trackParam } = await params;
  const track = parseTrack(trackParam);
  if (!track) notFound();
  const { lang } = await searchParams;

  const baseWhere = eq(questions.track, track);
  const whereClause =
    track === "coding" && lang ? and(baseWhere, eq(questions.language, lang)) : baseWhere;

  const all = await db.select().from(questions).where(whereClause).orderBy(asc(questions.number));

  // Distinct languages for filter chips (coding only)
  const languageRows =
    track === "coding"
      ? await db
          .selectDistinct({ language: questions.language })
          .from(questions)
          .where(and(eq(questions.track, "coding"), isNotNull(questions.language)))
      : [];
  const availableLanguages = languageRows
    .map((r) => r.language)
    .filter((x): x is string => !!x)
    .sort();

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
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        .ql { height:100%; overflow:auto; }
        .ql__inner { max-width: 1080px; margin: 0 auto; padding: 36px 36px 64px; }
        .ql__head { display:flex; align-items: end; gap: 24px; padding-bottom: 24px; border-bottom: 1px solid var(--line); }
        .ql__h { font-size: 30px; font-weight: 600; letter-spacing: -0.024em; }
        .ql__h em { font-family: var(--font-read); font-style: italic; font-weight: 400; color: var(--mute); }
        .ql__sub { color: var(--mute); font-size: 14px; margin-top: 8px; max-width: 56ch; }
        .ql__r { margin-left: auto; display:flex; gap:8px; }
        .ql__counts { display:flex; gap:18px; padding: 14px 0 4px; }
        .ql__counts span { font-family: var(--font-mono); font-size:11px; color:var(--mute); text-transform:uppercase; letter-spacing:.1em; }
        .ql__counts b { color: var(--ink); font-weight:500; }
        .qr { display:grid; grid-template-columns: 32px 1fr 80px 220px 80px 100px; gap:18px; padding: 16px 6px; border-bottom: 1px solid var(--line); align-items:center; cursor:pointer; text-decoration:none; color:inherit; }
        .qr:hover { background: var(--bg-2); }
        .qr__n { font-family: var(--font-mono); font-size: 11px; color: var(--mute-2); padding-left: 6px; }
        .qr__t { font-size: 14.5px; color: var(--ink); letter-spacing: -0.005em; font-weight: 500; }
        .qr__t em { display:block; font-family: var(--font-mono); font-size: 10px; color: var(--mute); margin-top:4px; font-style: normal; text-transform:uppercase; letter-spacing:.08em; }
        .qr__d { font-family: var(--font-mono); font-size: 10.5px; text-transform: uppercase; letter-spacing: .12em; }
        .qr__tags { display:flex; gap: 5px; flex-wrap: wrap; }
        .qr__tags span { font-family: var(--font-mono); font-size: 9.5px; color: var(--mute); border:1px solid var(--line); border-radius: 3px; padding: 1px 5px; text-transform: uppercase; letter-spacing: .08em; }
        .qr__min { font-family: var(--font-mono); font-size: 11px; color: var(--mute); text-align: right; }
        .qr__score { font-family: var(--font-mono); font-size: 12px; color: var(--ink); text-align: right; }
        .qr__score em { color: var(--mute-2); font-style: normal; }
        .qr__score.none { color: var(--accent); }
        .ql__lang-filter { padding: 16px 0 4px; }
      ` }} />
      <div className="ql">
        <div className="ql__inner">
          <div className="ql__head">
            <div>
              <h1 className="ql__h">
                {TRACK_LABELS[track]} <em>questions</em>
              </h1>
              <p className="ql__sub">
                {track === "coding"
                  ? "Explain-it-like-a-staff-engineer style questions. AI-vs-AI works on the title alone."
                  : "Pick a question to read the brief and start a session."}
              </p>
            </div>
            <div className="ql__r">
              <div className="ql__counts">
                <span><b>{all.length}</b> questions</span>
                <span><b>{sessions.length}</b> attempts</span>
              </div>
            </div>
          </div>

          {track === "coding" && availableLanguages.length > 0 && (
            <div className="ql__lang-filter">
              <LanguageFilter
                languages={availableLanguages}
                activeLanguage={lang ?? null}
                basePath={`/${track}/questions`}
              />
            </div>
          )}

          {empty ? (
            <div style={{ padding: "56px 0", display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
              <div style={{ fontFamily: "var(--font-read)", fontSize: 32, fontStyle: "italic", color: "var(--mute)", letterSpacing: "-0.02em" }}>
                {lang ? `No ${lang} questions yet.` : "Coming soon."}
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--mute-2)", textAlign: "center", maxWidth: "42ch" }}>
                {lang
                  ? `No questions are available for ${lang} yet. Try a different language or check back later.`
                  : `${TRACK_LABELS[track]} interview questions are being added. Switch to the System Design track to get started now.`}
              </div>
            </div>
          ) : (
            <div>
              {all.map((q, idx) => {
                const past = sessionsByQuestion.get(q.id) ?? 0;
                let tags: string[] = [];
                try { tags = JSON.parse(q.tags ?? "[]"); } catch { tags = []; }
                const diffColor =
                  q.difficulty === "easy"
                    ? "var(--good)"
                    : q.difficulty === "hard"
                    ? "var(--bad)"
                    : "var(--warn)";
                return (
                  <Link key={q.id} href={`/${track}/questions/${q.slug}`} className="qr">
                    <span className="qr__n">{String(q.number ?? idx + 1).padStart(2, "0")}</span>
                    <span className="qr__t">
                      {q.title}
                      {q.language && <em>{q.language}</em>}
                    </span>
                    <span className="qr__d" style={{ color: diffColor }}>{q.difficulty}</span>
                    <span className="qr__tags">
                      {tags.slice(0, 4).map((tag) => (
                        <span key={tag}>{tag}</span>
                      ))}
                    </span>
                    <span className="qr__min">~{q.estMinutes}m</span>
                    <span className={`qr__score${past === 0 ? " none" : ""}`}>
                      {past === 0 ? "start →" : <>{past}<em> sess</em></>}
                    </span>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
