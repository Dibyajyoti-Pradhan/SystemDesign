import { notFound } from "next/navigation";
import Link from "next/link";
import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import { db } from "@/db/client";
import { questions, interviewSessions } from "@/db/schema";
import { eq, desc, and } from "drizzle-orm";
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

  const diffColor =
    q.difficulty === "easy"
      ? "var(--good)"
      : q.difficulty === "hard"
      ? "var(--bad)"
      : "var(--warn)";

  return (
    <>
      <style>{`
        .qd { height:100%; overflow:auto; }
        .qd__inner { max-width: 920px; margin: 0 auto; padding: 36px 36px 64px; display:flex; flex-direction: column; gap: 28px; }
        .qd__head { display:flex; flex-direction: column; gap:12px; padding-bottom: 22px; border-bottom: 1px solid var(--line); }
        .qd__meta { display:flex; gap:8px; align-items: center; flex-wrap:wrap; }
        .qd__t { font-size: 32px; font-weight: 600; letter-spacing: -0.024em; line-height: 1.1; }
        .qd__sub { color: var(--mute); font-size: 14.5px; max-width: 60ch; line-height: 1.55; }
        .brief { font-family: var(--font-read); font-size: 16.5px; line-height: 1.65; color: var(--ink-2); display:flex; flex-direction: column; gap: 14px; }
        .brief h3 { font-family: var(--font-ui); font-size: 13px; font-weight: 600; color: var(--ink); margin: 12px 0 0; letter-spacing: -0.005em; }
        .brief ul { margin: 0; padding-left: 0; list-style: none; }
        .brief li { padding: 4px 0 4px 22px; position: relative; }
        .brief li::before { content:"—"; position: absolute; left: 0; color: var(--mute-2); font-family: var(--font-mono); }
        .ctas { display:grid; grid-template-columns: 1fr 1fr; gap: 14px; padding: 22px 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
        .cta { padding: 18px 20px; border:1px solid var(--line); border-radius: 10px; background: var(--bg-2); display:flex; flex-direction: column; gap: 6px; cursor:pointer; text-decoration:none; }
        .cta:hover { border-color: var(--line-2); background: var(--surf); }
        .cta.is-primary { border-color: var(--accent); background: rgba(212,165,116,0.04); }
        .cta__lbl { font-family: var(--font-mono); font-size: 10.5px; color: var(--accent); text-transform: uppercase; letter-spacing: .14em; }
        .cta__t { font-size: 17px; font-weight: 600; letter-spacing: -0.012em; }
        .cta__d { color: var(--mute); font-size: 13px; line-height: 1.5; max-width: 40ch; }
        .cta__go { display:flex; align-items:center; gap:6px; font-family: var(--font-mono); font-size: 11px; color: var(--accent); text-transform: uppercase; letter-spacing: .1em; margin-top: 6px; }
        .hist__h { display:flex; align-items: baseline; gap:14px; padding-bottom: 10px; border-bottom: 1px solid var(--line); margin-bottom: 12px; }
        .hist__lbl { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .14em; }
        .hist__ct { margin-left: auto; font-family: var(--font-mono); font-size: 11px; color: var(--mute-2); }
        .hist__r { display:grid; grid-template-columns: 60px 1fr 70px 70px 24px; gap: 14px; padding: 12px 0; border-bottom: 1px solid var(--line); align-items: center; cursor:pointer; text-decoration:none; color:inherit; }
        .hist__r:last-child { border-bottom: 0; }
        .hist__date { font-family: var(--font-mono); font-size: 11px; color: var(--mute); }
        .hist__mode { font-size: 13px; color: var(--ink); }
        .hist__mode em { display:block; font-family: var(--font-mono); font-size: 10px; color: var(--mute); margin-top: 3px; font-style: normal; text-transform: uppercase; letter-spacing: .08em; }
        .hist__turns { font-family: var(--font-mono); font-size: 11px; color: var(--mute); text-align: right; }
        .hist__sc { font-family: var(--font-mono); font-size: 13px; color: var(--ink); text-align: right; }
        .hist__sc em { color: var(--mute-2); font-style: normal; }
        .qd__back { display:inline-flex; align-items:center; gap:6px; font-family: var(--font-mono); font-size: 11px; color: var(--mute); text-decoration:none; text-transform:uppercase; letter-spacing:.08em; }
        .qd__back:hover { color: var(--ink); }
        .qd__brief-placeholder { font-family: var(--font-read); font-size: 15px; color: var(--mute); font-style: italic; }
      `}</style>
      <div className="qd">
        <div className="qd__inner">

          {/* Back link */}
          <Link href={`/${track}/questions`} className="qd__back">
            ← All questions
          </Link>

          {/* Header */}
          <div className="qd__head">
            <div className="qd__meta">
              <span className="badge" style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>
                #{String(q.number ?? 0).padStart(2, "0")}
              </span>
              <span className="badge" style={{ color: diffColor, borderColor: diffColor + "44" }}>
                {q.difficulty}
              </span>
              {q.language && (
                <span className="badge">{q.language}</span>
              )}
              <span className="badge">~{q.estMinutes} min</span>
              <div style={{ marginLeft: "auto" }}>
                <GenerateBriefButton slug={q.slug} />
              </div>
            </div>
            <h1 className="qd__t">{q.title}</h1>
            {q.pdfPath && (
              <p className="qd__sub">
                <a
                  href={`/api/pdf?path=${encodeURIComponent(q.pdfPath)}`}
                  target="_blank"
                  style={{ color: "var(--accent)", fontFamily: "var(--font-mono)", fontSize: 11, textTransform: "uppercase", letterSpacing: ".08em" }}
                >
                  Reference PDF ↗
                </a>
              </p>
            )}
          </div>

          {/* Brief content */}
          <div>
            {briefBody ? (
              <div className="brief">
                <MdxRenderer source={briefBody} />
              </div>
            ) : (
              <p className="qd__brief-placeholder">
                No brief generated yet — click Generate Brief to create one.
              </p>
            )}
          </div>

          {/* CTAs */}
          <div className="ctas">
            <Link href={`/interview/start/${q.slug}`} className="cta is-primary">
              <span className="cta__lbl">Self practice</span>
              <span className="cta__t">Try yourself</span>
              <span className="cta__d">Interview yourself with AI as the interviewer. You answer, AI pushes back.</span>
              <span className="cta__go">Start session →</span>
            </Link>
            <Link href={`/interview/ai-vs-ai/start/${q.slug}`} className="cta">
              <span className="cta__lbl">AI vs AI</span>
              <span className="cta__t">Watch AI vs AI</span>
              <span className="cta__d">Two AI agents — one interviewer, one candidate — debate this question live.</span>
              <span className="cta__go">Watch now →</span>
            </Link>
          </div>

          {/* Session history */}
          {sessions.length > 0 && (
            <div>
              <div className="hist__h">
                <span className="hist__lbl">Past sessions</span>
                <span className="hist__ct">{sessions.length}</span>
              </div>
              {sessions.map((s) => {
                const turns = turnCount(s.transcript);
                const modeLabel = s.mode === "ai_vs_ai" ? "AI vs AI" : "Self";
                const modeSubLabel = s.mode === "ai_vs_ai" ? "watched" : "practiced";
                return (
                  <div key={s.id} style={{ display: "grid", gridTemplateColumns: "60px 1fr 70px 70px 24px", gap: 14, padding: "12px 0", borderBottom: "1px solid var(--line)", alignItems: "center" }}>
                    <span className="hist__date">{relativeTime(s.startedAt)}</span>
                    <Link href={`/interview/sessions/${s.id}`} className="hist__r" style={{ display: "contents", textDecoration: "none", color: "inherit" }}>
                      <span className="hist__mode" style={{ gridColumn: "2" }}>
                        {modeLabel}
                        <em>{modeSubLabel}</em>
                      </span>
                    </Link>
                    <span className="hist__turns">{turns}t</span>
                    <span className="hist__sc">
                      {typeof s.score === "number" ? (
                        <>{s.score}<em>/100</em></>
                      ) : s.endedAt ? (
                        <em>done</em>
                      ) : (
                        <em>live</em>
                      )}
                    </span>
                    <DeleteSessionButton sessionId={s.id} iconOnly />
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
