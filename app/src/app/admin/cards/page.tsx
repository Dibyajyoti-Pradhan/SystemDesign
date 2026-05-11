import Link from "next/link";
import { db } from "@/db/client";
import { cards, topics } from "@/db/schema";
import { eq, asc } from "drizzle-orm";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { CheckCircle2, Pencil, X, ArrowLeft } from "lucide-react";

export const dynamic = "force-dynamic";

async function approveCard(formData: FormData) {
  "use server";
  const id = Number(formData.get("id"));
  if (!Number.isFinite(id)) return;
  await db
    .update(cards)
    .set({ status: "active", dueAt: new Date() })
    .where(eq(cards.id, id));
  revalidatePath("/admin/cards");
  revalidatePath("/review");
}

async function rejectCard(formData: FormData) {
  "use server";
  const id = Number(formData.get("id"));
  if (!Number.isFinite(id)) return;
  await db.update(cards).set({ status: "archived" }).where(eq(cards.id, id));
  revalidatePath("/admin/cards");
}

async function editCard(formData: FormData) {
  "use server";
  const id = Number(formData.get("id"));
  if (!Number.isFinite(id)) return;
  redirect(`/admin/cards/${id}/edit`);
}

const TYPE_COLORS: Record<string, string> = {
  definition: "var(--info)",
  tradeoff: "var(--warn)",
  scenario: "var(--good)",
  comparison: "var(--accent)",
};

const AQ_CSS = `
.aq { height:100%; overflow:auto; }
.aq__inner { max-width: 1080px; margin: 0 auto; padding: 30px 32px 60px; }
.aq__head { display:flex; align-items: end; gap: 24px; padding-bottom: 22px; border-bottom: 1px solid var(--line); }
.aq__h { font-size: 26px; font-weight: 600; letter-spacing: -0.022em; }
.aq__h em { font-family: var(--font-read); font-style: italic; font-weight: 400; color: var(--mute); }
.aq__sub { color: var(--mute); font-size: 14px; margin-top: 6px; max-width: 60ch; }
.aq__r { margin-left: auto; display:flex; gap: 8px; align-items: center; }
.aq__bar { display:grid; grid-template-columns: 32px 80px 80px 1.4fr 1fr 200px; gap: 18px; padding: 12px 6px; border-bottom: 1px solid var(--line); margin-top: 14px; }
.aq__bar span { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute-2); text-transform: uppercase; letter-spacing: .12em; }
.ar { display:grid; grid-template-columns: 32px 80px 80px 1.4fr 1fr 200px; gap: 18px; padding: 16px 6px; border-bottom: 1px solid var(--line); align-items: start; }
.ar:hover { background: var(--bg-2); }
.ar__chk { width: 16px; height: 16px; border:1px solid var(--line-2); border-radius: 3px; margin-top: 2px; cursor: pointer; }
.ar__id { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); }
.ar__type { font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; letter-spacing: .12em; padding-top:1px; }
.ar__front { font-size: 13.5px; color: var(--ink); line-height: 1.5; padding-right: 16px; }
.ar__back { font-size: 12.5px; color: var(--mute); line-height: 1.5; max-width: 50ch; }
.ar__act { display:flex; gap: 5px; justify-content: flex-end; }
`;

export default async function AdminCardsPage() {
  const rows = await db
    .select({
      id: cards.id,
      type: cards.type,
      front: cards.front,
      back: cards.back,
      diagramMermaid: cards.diagramMermaid,
      generatedByModel: cards.generatedByModel,
      createdAt: cards.createdAt,
      topicTitle: topics.title,
      topicSlug: topics.slug,
      topicCategory: topics.category,
    })
    .from(cards)
    .leftJoin(topics, eq(cards.topicId, topics.id))
    .where(eq(cards.status, "pending_review"))
    .orderBy(asc(topics.categoryOrder), asc(topics.topicOrder), asc(cards.id));

  const grouped = new Map<string, typeof rows>();
  for (const r of rows) {
    const key = r.topicTitle ?? "Unassigned";
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(r);
  }

  return (
    <div className="aq">
      <style dangerouslySetInnerHTML={{ __html: AQ_CSS }} />
      <div className="aq__inner">
        <div className="aq__head">
          <div>
            <h1 className="aq__h">
              Pending cards <em>approval queue</em>
            </h1>
            <p className="aq__sub">
              Review Claude-generated flashcards before they enter your daily rotation.
            </p>
          </div>
          <div className="aq__r">
            <Link
              href="/admin"
              style={{ display: "flex", alignItems: "center", gap: 6, fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute)", textDecoration: "none", textTransform: "uppercase", letterSpacing: ".08em" }}
            >
              <ArrowLeft size={13} /> Admin
            </Link>
            <span className="badge badge--accent">{rows.length} pending</span>
          </div>
        </div>

        {rows.length === 0 && (
          <div style={{ padding: "48px 0", textAlign: "center", color: "var(--mute)" }}>
            <p style={{ marginBottom: 12 }}>No cards waiting for review.</p>
            <code style={{ fontFamily: "var(--font-mono)", fontSize: 12, background: "var(--surf)", border: "1px solid var(--line)", borderRadius: 6, padding: "6px 12px" }}>
              npm run generate-cards &lt;topic-slug&gt;
            </code>
          </div>
        )}

        {rows.length > 0 && (
          <>
            <div className="aq__bar">
              <span></span>
              <span>ID</span>
              <span>Type</span>
              <span>Front</span>
              <span>Back</span>
              <span style={{ textAlign: "right" }}>Actions</span>
            </div>

            {[...grouped.entries()].map(([topicTitle, items]) => (
              <div key={topicTitle}>
                <div style={{ padding: "14px 6px 6px", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute)", textTransform: "uppercase", letterSpacing: ".1em", borderBottom: "1px solid var(--line)" }}>
                  {topicTitle}
                  <span style={{ marginLeft: 10, color: "var(--mute-2)" }}>— {items.length}</span>
                </div>
                {items.map((c) => (
                  <div key={c.id} className="ar">
                    <div><div className="ar__chk" /></div>
                    <div className="ar__id">#{c.id}</div>
                    <div className="ar__type" style={{ color: TYPE_COLORS[c.type] ?? "var(--mute)" }}>
                      {c.type}
                    </div>
                    <div className="ar__front">{c.front}</div>
                    <div className="ar__back">{c.back}</div>
                    <div className="ar__act">
                      <form action={approveCard}>
                        <input type="hidden" name="id" value={c.id} />
                        <button type="submit" className="btn btn--primary" style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12 }}>
                          <CheckCircle2 size={12} /> Approve
                        </button>
                      </form>
                      <form action={editCard}>
                        <input type="hidden" name="id" value={c.id} />
                        <button type="submit" className="btn btn--ghost" style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12 }}>
                          <Pencil size={12} /> Edit
                        </button>
                      </form>
                      <form action={rejectCard}>
                        <input type="hidden" name="id" value={c.id} />
                        <button type="submit" className="btn btn--ghost" style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "var(--bad)" }}>
                          <X size={12} /> Reject
                        </button>
                      </form>
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
