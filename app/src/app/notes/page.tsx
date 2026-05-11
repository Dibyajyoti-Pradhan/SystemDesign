import Link from "next/link";
import { db } from "@/db/client";
import { notes, topics, questions } from "@/db/schema";
import { desc, eq } from "drizzle-orm";
import { NoteEditor } from "@/components/NoteEditor";
import { relativeTime } from "@/lib/utils";

function groupByDate(items: Array<{ n: { updatedAt: Date | null }; [key: string]: unknown }>) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  const groups: Record<string, typeof items> = {
    Today: [],
    Yesterday: [],
    "This week": [],
    Older: [],
  };

  for (const item of items) {
    const d = item.n.updatedAt ? new Date(item.n.updatedAt) : null;
    if (!d) { groups.Older.push(item); continue; }
    const day = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    if (day >= today) groups.Today.push(item);
    else if (day >= yesterday) groups.Yesterday.push(item);
    else if (day >= weekAgo) groups["This week"].push(item);
    else groups.Older.push(item);
  }

  return Object.entries(groups).filter(([, arr]) => arr.length > 0);
}

export default async function NotesPage({
  searchParams,
}: {
  searchParams: Promise<{ topic?: string; question?: string }>;
}) {
  const sp = await searchParams;

  let attachedTopic = null;
  let attachedQuestion = null;
  if (sp.topic) {
    [attachedTopic] = await db.select().from(topics).where(eq(topics.slug, sp.topic)).limit(1);
  }
  if (sp.question) {
    [attachedQuestion] = await db.select().from(questions).where(eq(questions.slug, sp.question)).limit(1);
  }

  const allNotes = await db
    .select({
      n: notes,
      topicTitle: topics.title,
      topicSlug: topics.slug,
      questionTitle: questions.title,
      questionSlug: questions.slug,
    })
    .from(notes)
    .leftJoin(topics, eq(notes.topicId, topics.id))
    .leftJoin(questions, eq(notes.questionId, questions.id))
    .orderBy(desc(notes.updatedAt))
    .limit(50);

  const grouped = groupByDate(allNotes as Array<{ n: { updatedAt: Date | null }; topicTitle: string | null; topicSlug: string | null; questionTitle: string | null; questionSlug: string | null }>);

  return (
    <>
      <style>{`
        .nt { height:100%; overflow:auto; }
        .nt__inner { max-width: 880px; margin: 0 auto; padding: 36px 28px 64px; }
        .nt__head { display:flex; align-items: end; gap: 24px; padding-bottom: 22px; border-bottom: 1px solid var(--line); }
        .nt__h { font-size: 28px; font-weight: 600; letter-spacing: -0.022em; }
        .nt__h em { font-family: var(--font-read); font-style: italic; font-weight: 400; color: var(--mute); }
        .nt__sub { color: var(--mute); font-size: 14px; margin-top: 8px; max-width: 60ch; }
        .nt__r { margin-left:auto; display:flex; gap:8px; align-items:center; }
        .nt__day { display:flex; align-items:center; gap:14px; margin: 26px 0 8px; }
        .nt__day b { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .14em; font-weight: 500; }
        .nt__day::after { content:""; flex:1; height:1px; background: var(--line); }
        .nrow { display:grid; grid-template-columns: 88px 1fr 70px; gap: 22px; padding: 16px 0; border-bottom: 1px solid var(--line); align-items: start; }
        .nrow__when { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute-2); padding-top: 4px; text-transform: uppercase; letter-spacing: .08em; }
        .nrow__parent { font-family: var(--font-mono); font-size: 10.5px; color: var(--accent); margin-bottom: 6px; cursor: pointer; text-decoration:none; display:block; }
        .nrow__parent:hover { text-decoration: underline; }
        .nrow__body { font-family: var(--font-read); font-size: 16px; line-height: 1.6; color: var(--ink-2); white-space: pre-wrap; }
        .nrow__w { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute-2); text-align: right; padding-top: 4px; }
        .nt__compose-wrap { margin-top: 26px; padding-bottom: 4px; }
        .nt__empty { padding: 48px 0; text-align: center; font-family: var(--font-mono); font-size: 12px; color: var(--mute); text-transform: uppercase; letter-spacing: .12em; }
      `}</style>
      <div className="nt">
        <div className="nt__inner">
          <div className="nt__head">
            <div>
              <div className="nt__h">Notes <em>&amp; scratch</em></div>
              <div className="nt__sub">Your scratchpad. Markdown supported. Optionally attach to a topic or question.</div>
            </div>
            <div className="nt__r">
              <span className="badge">{allNotes.length} notes</span>
            </div>
          </div>

          <div className="nt__compose-wrap">
            <NoteEditor topicId={attachedTopic?.id ?? null} questionId={attachedQuestion?.id ?? null} />
          </div>

          {allNotes.length === 0 && (
            <div className="nt__empty">No notes yet — write your first one above.</div>
          )}

          {grouped.map(([label, items]) => (
            <div key={label}>
              <div className="nt__day"><b>{label}</b></div>
              {(items as Array<{ n: typeof allNotes[0]["n"]; topicTitle: string | null; topicSlug: string | null; questionTitle: string | null; questionSlug: string | null }>).map(({ n, topicTitle, topicSlug, questionTitle, questionSlug }) => {
                const wordCount = n.body ? n.body.split(/\s+/).filter(Boolean).length : 0;
                return (
                  <div key={n.id} className="nrow">
                    <div className="nrow__when">{relativeTime(n.updatedAt)}</div>
                    <div>
                      {topicTitle && topicSlug && (
                        <Link href={`/topics/${topicSlug}`} className="nrow__parent">
                          ↳ Topic · {topicTitle}
                        </Link>
                      )}
                      {questionTitle && questionSlug && (
                        <Link href={`/questions/${questionSlug}`} className="nrow__parent">
                          ↳ Question · {questionTitle}
                        </Link>
                      )}
                      <div className="nrow__body">{n.body}</div>
                    </div>
                    <div className="nrow__w">{wordCount}w</div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
