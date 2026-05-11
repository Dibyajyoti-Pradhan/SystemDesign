import { notFound } from "next/navigation";
import Link from "next/link";
import { db } from "@/db/client";
import { interviewSessions, questions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { ArrowLeft, RotateCcw } from "lucide-react";
import { Chat } from "@/components/interview/Chat";
import { AiVsAiSession } from "@/components/interview/AiVsAiSession";
import { type RubricData } from "@/components/interview/Rubric";
import { DeleteSessionButton } from "@/components/interview/DeleteSessionButton";
import { formatDate } from "@/lib/utils";

type SelfMsg = { role: "user" | "assistant"; content: string; ts: number };
type AiMsg =
  | { role: "interviewer" | "candidate"; content: string; ts: number }
  | {
      role: "steer";
      content: string;
      target: "interviewer" | "candidate" | "both";
      consumed: boolean;
      ts: number;
    };

function parseSelfTranscript(raw: string | null | undefined): SelfMsg[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (m): m is SelfMsg =>
        m &&
        typeof m === "object" &&
        (m.role === "user" || m.role === "assistant") &&
        typeof m.content === "string",
    );
  } catch {
    return [];
  }
}

function parseAiTranscript(raw: string | null | undefined): AiMsg[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (m): m is AiMsg =>
        m && typeof m === "object" && typeof m.role === "string" && typeof m.content === "string",
    );
  } catch {
    return [];
  }
}

function parseRubric(raw: string | null | undefined): RubricData | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (
      typeof parsed?.score === "number" &&
      parsed?.sections &&
      Array.isArray(parsed?.strengths) &&
      Array.isArray(parsed?.gaps)
    ) {
      return parsed as RubricData;
    }
    return null;
  } catch {
    return null;
  }
}

const SECTION_LABELS: Record<string, string> = {
  clarification: "Clarification",
  estimation: "Estimation (BoE)",
  high_level: "High-level design",
  deep_dive: "Deep dives",
  tradeoffs: "Tradeoffs",
};

export default async function InterviewSessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: idStr } = await params;
  const id = Number.parseInt(idStr, 10);
  if (!Number.isFinite(id)) notFound();

  const [session] = await db.select().from(interviewSessions).where(eq(interviewSessions.id, id)).limit(1);
  if (!session) notFound();

  const [question] = await db.select().from(questions).where(eq(questions.id, session.questionId)).limit(1);
  if (!question) notFound();

  const isAiVsAi = session.mode === "ai_vs_ai";
  const rubric = parseRubric(session.rubric);
  const ended = !!session.endedAt;

  if (rubric) {
    const sectionKeys = Object.keys(SECTION_LABELS) as Array<keyof RubricData["sections"]>;
    return (
      <>
        <style dangerouslySetInnerHTML={{ __html: `
          .rub { height:100%; overflow:auto; background: var(--bg); }
          .rub__inner { max-width: 1080px; margin: 0 auto; padding: 36px 36px 64px; }
          .rub__head { display:grid; grid-template-columns: 1fr auto; gap: 32px; align-items: end; padding-bottom: 26px; border-bottom: 1px solid var(--line); }
          .rub__eyebrow { font-family: var(--font-mono); font-size: 10.5px; color: var(--accent); text-transform: uppercase; letter-spacing: .14em; margin-bottom: 8px; }
          .rub__q { font-size: 26px; font-weight: 600; letter-spacing: -0.022em; line-height: 1.2; }
          .rub__sub { color: var(--mute); font-family: var(--font-mono); font-size: 11.5px; margin-top: 6px; text-transform: uppercase; letter-spacing: .08em; }
          .rub__score { display:flex; flex-direction: column; align-items: flex-end; gap: 4px; }
          .score__big { font-family: var(--font-read); font-weight: 400; font-style: italic; font-size: 86px; letter-spacing: -0.04em; line-height: 0.9; color: var(--ink); }
          .score__big sup { font-size: 32px; color: var(--mute-2); font-style: normal; vertical-align: 38px; margin-left: 4px; }
          .score__lbl { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .14em; }
          .stave2 { padding: 36px 0 24px; }
          .stave2__head { display:flex; align-items: baseline; gap: 14px; margin-bottom: 18px; }
          .stave2__row { display:grid; grid-template-columns: 22px 132px 1fr 56px; gap: 14px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--line); }
          .stave2__row:last-child { border-bottom: 0; }
          .stave2__n { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute-2); }
          .stave2__k { font-size: 13.5px; color: var(--ink); letter-spacing: -0.005em; }
          .stave2__k em { display:block; font-family: var(--font-mono); font-size: 10px; color: var(--mute-2); margin-top: 2px; font-style: normal; text-transform: uppercase; letter-spacing: .1em; }
          .stave2__line { position: relative; height: 24px; display:flex; align-items: center; }
          .stave2__line::before { content:""; position:absolute; left:0; right:0; top: 50%; height: 1px; background: var(--line); }
          .stave2__line .fill { position:absolute; left:0; top: 50%; transform: translateY(-50%); height: 2px; background: var(--ink-2); }
          .stave2__line .marker { position:absolute; top: 50%; transform: translate(-50%, -50%); width: 12px; height: 12px; border-radius: 999px; background: var(--bg); border: 2px solid var(--accent); }
          .stave2__line .marker.low { border-color: var(--mute); }
          .stave2__num { font-family: var(--font-mono); font-size: 13px; color: var(--ink); text-align: right; }
          .twocol { display:grid; grid-template-columns: 1fr 1fr; gap: 32px; padding-top: 36px; }
          .col__h { display:flex; align-items: baseline; gap: 10px; padding-bottom: 12px; border-bottom: 1px solid var(--line); margin-bottom: 16px; }
          .col__h .lbl { font-family: var(--font-mono); font-size: 10.5px; text-transform: uppercase; letter-spacing: .14em; }
          .col__h.s .lbl { color: var(--good); }
          .col__h.g .lbl { color: var(--bad); }
          .item { padding: 12px 0; border-bottom: 1px solid var(--line); display:flex; gap: 14px; }
          .item:last-child { border-bottom: 0; }
          .item__num { font-family: var(--font-mono); font-size: 10px; color: var(--mute-2); padding-top: 3px; }
          .item__body { flex:1; font-family: var(--font-read); font-size: 15px; line-height: 1.55; color: var(--ink-2); }
          .rub__actions { display:flex; align-items:center; gap: 10px; margin-top: 32px; }
          .rub__transcript { margin-top: 40px; border-top: 1px solid var(--line); padding-top: 28px; }
          .rub__tx-head { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .14em; margin-bottom: 18px; }
          .tx-msg { padding: 12px 0; border-bottom: 1px solid var(--line); }
          .tx-msg:last-child { border-bottom: 0; }
          .tx-msg__who { font-family: var(--font-mono); font-size: 10px; color: var(--mute); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 5px; }
          .tx-msg__body { font-size: 13.5px; line-height: 1.6; color: var(--ink-2); white-space: pre-wrap; }
        ` }} />
        <div className="rub">
          <div className="rub__inner">
            {/* Header */}
            <div className="rub__head">
              <div>
                <div className="rub__eyebrow">
                  <Link href={`/${question.track}/questions/${question.slug}`} style={{ color: "var(--accent)", textDecoration: "none" }}>
                    ← {question.track}
                  </Link>
                  {" · "}Session #{session.id} · {formatDate(session.startedAt)}
                </div>
                <div className="rub__q">{question.title}</div>
                <div className="rub__sub">
                  {isAiVsAi ? "ai vs ai" : "self practice"} · {question.difficulty} · ~{question.estMinutes} min
                </div>
              </div>
              <div className="rub__score">
                <div className="score__big">
                  {rubric.score}<sup>/100</sup>
                </div>
                <div className="score__lbl">overall score</div>
              </div>
            </div>

            {/* Section breakdown */}
            <div className="stave2">
              <div className="stave2__head">
                <span className="badge">By section</span>
              </div>
              {sectionKeys.map((key, i) => {
                const v = rubric.sections?.[key] ?? 0;
                const pct = Math.min(100, Math.max(0, v));
                return (
                  <div key={key} className="stave2__row">
                    <span className="stave2__n">{String(i + 1).padStart(2, "0")}</span>
                    <span className="stave2__k">{SECTION_LABELS[key]}<em>{key.replace(/_/g, " ")}</em></span>
                    <div className="stave2__line">
                      <div className="fill" style={{ width: `${pct}%` }} />
                      <div className="marker" style={{ left: `${pct}%` }} />
                    </div>
                    <span className="stave2__num">{v}</span>
                  </div>
                );
              })}
            </div>

            {/* Strengths & gaps */}
            <div className="twocol">
              <div>
                <div className="col__h s">
                  <span className="lbl">Strengths</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute-2)" }}>{rubric.strengths.length}</span>
                </div>
                {rubric.strengths.length === 0 ? (
                  <p style={{ color: "var(--mute)", fontFamily: "var(--font-mono)", fontSize: 12 }}>None recorded.</p>
                ) : (
                  rubric.strengths.map((s, i) => (
                    <div key={i} className="item">
                      <span className="item__num">{String(i + 1).padStart(2, "0")}</span>
                      <span className="item__body">{s}</span>
                    </div>
                  ))
                )}
              </div>
              <div>
                <div className="col__h g">
                  <span className="lbl">Gaps</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute-2)" }}>{rubric.gaps.length}</span>
                </div>
                {rubric.gaps.length === 0 ? (
                  <p style={{ color: "var(--mute)", fontFamily: "var(--font-mono)", fontSize: 12 }}>None recorded.</p>
                ) : (
                  rubric.gaps.map((g, i) => (
                    <div key={i} className="item">
                      <span className="item__num">{String(i + 1).padStart(2, "0")}</span>
                      <span className="item__body">{g}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="rub__actions">
              <Link href={`/${question.track}/questions`} className="btn btn--ghost">
                <ArrowLeft style={{ width: 13, height: 13 }} /> All questions
              </Link>
              {isAiVsAi && (
                <Link href={`/interview/ai-vs-ai/start/${question.slug}`} className="btn">
                  <RotateCcw style={{ width: 13, height: 13 }} /> Run again
                </Link>
              )}
              <DeleteSessionButton
                sessionId={session.id}
                redirectTo={`/${question.track}/questions`}
              />
            </div>

            {/* Transcript */}
            <div className="rub__transcript">
              <div className="rub__tx-head">Transcript</div>
              {isAiVsAi
                ? (() => {
                    const t = parseAiTranscript(session.transcript);
                    if (t.length === 0)
                      return <p style={{ color: "var(--mute)", fontSize: 13 }}>No messages.</p>;
                    return t.map((m, i) => (
                      <div key={i} className="tx-msg">
                        <div className="tx-msg__who">
                          {m.role === "steer"
                            ? `Steer → ${(m as any).target}`
                            : m.role === "interviewer"
                            ? "Interviewer"
                            : "Candidate"}
                        </div>
                        <div className="tx-msg__body">{m.content}</div>
                      </div>
                    ));
                  })()
                : (() => {
                    const t = parseSelfTranscript(session.transcript);
                    if (t.length === 0)
                      return <p style={{ color: "var(--mute)", fontSize: 13 }}>No messages.</p>;
                    return t.map((m, i) => (
                      <div key={i} className="tx-msg">
                        <div className="tx-msg__who">
                          {m.role === "user" ? "You" : "Interviewer"}
                        </div>
                        <div className="tx-msg__body">{m.content}</div>
                      </div>
                    ));
                  })()}
            </div>
          </div>
        </div>
      </>
    );
  }

  // In-progress or no rubric yet — render live interview components in dark wrapper
  if (isAiVsAi) {
    return (
      <div style={{ height: "100%", overflow: "hidden", background: "var(--bg)" }}>
        <AiVsAiSession
          sessionId={session.id}
          questionTitle={question.title}
          initialTranscript={parseAiTranscript(session.transcript)}
          initialEnded={ended}
        />
      </div>
    );
  }

  return (
    <div style={{ height: "100%", overflow: "hidden", background: "var(--bg)" }}>
      <Chat sessionId={session.id} initialMessages={parseSelfTranscript(session.transcript)} />
    </div>
  );
}
