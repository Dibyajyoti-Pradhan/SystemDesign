import { db } from "@/db/client";
import { topics } from "@/db/schema";
import { asc } from "drizzle-orm";
import { getContentQueue } from "@/lib/queue";

export const dynamic = "force-dynamic";

async function getQueueCounts(): Promise<{ waiting: number; active: number } | null> {
  try {
    const queue = await getContentQueue();
    if (!queue) return null;
    const counts = await queue.getJobCounts("waiting", "active");
    return { waiting: counts.waiting ?? 0, active: counts.active ?? 0 };
  } catch {
    return null;
  }
}

export default async function AdminDashboardPage() {
  const [rows, queueCounts] = await Promise.all([
    db
      .select({
        id: topics.id,
        slug: topics.slug,
        title: topics.title,
        generatedAt: topics.generatedAt,
        version: topics.version,
        generationStatus: topics.generationStatus,
      })
      .from(topics)
      .orderBy(asc(topics.categoryOrder), asc(topics.topicOrder), asc(topics.id)),
    getQueueCounts(),
  ]);

  const ADMIN_CSS = `
.adm { height:100%; overflow:auto; }
.adm__inner { max-width: 1080px; margin: 0 auto; padding: 30px 32px 60px; }
.adm__head { display:flex; align-items: end; gap: 24px; padding-bottom: 22px; border-bottom: 1px solid var(--line); }
.adm__h { font-size: 26px; font-weight: 600; letter-spacing: -0.022em; }
.adm__sub { color: var(--mute); font-size: 14px; margin-top: 6px; }
.adm__r { margin-left: auto; display:flex; gap: 8px; align-items: center; }
.adm__card { background: var(--surf); border: 1px solid var(--line); border-radius: 10px; padding: 18px 20px; margin: 20px 0; }
.adm__card h2 { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .12em; margin-bottom: 10px; }
.adm__row { display:grid; grid-template-columns: 1fr 80px 100px 180px 120px; gap: 18px; padding: 12px 6px; border-bottom: 1px solid var(--line); align-items: center; }
.adm__row:hover { background: var(--bg-2); }
.adm__row-head { display:grid; grid-template-columns: 1fr 80px 100px 180px 120px; gap: 18px; padding: 10px 6px; border-bottom: 1px solid var(--line); margin-top: 14px; }
.adm__row-head span { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute-2); text-transform: uppercase; letter-spacing: .12em; }
`;

  return (
    <div className="adm">
      <style>{ADMIN_CSS}</style>
      <div className="adm__inner">
        <div className="adm__head">
          <div>
            <h1 className="adm__h">Admin</h1>
            <p className="adm__sub">{rows.length} topics in the database</p>
          </div>
          <div className="adm__r">
            <a
              href="/admin/cards"
              className="btn btn--primary"
              style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}
            >
              Cards queue
            </a>
          </div>
        </div>

        {/* Queue depth panel */}
        <div className="adm__card">
          <h2>Job Queue</h2>
          {queueCounts === null ? (
            <p style={{ fontSize: 13, color: "var(--mute)" }}>
              Queue unavailable — set UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN to enable.
            </p>
          ) : (
            <div style={{ display: "flex", gap: 24, fontSize: 13 }}>
              <span>
                <span style={{ fontWeight: 600, color: "var(--warn)" }}>{queueCounts.waiting}</span>{" "}
                <span style={{ color: "var(--mute)" }}>waiting</span>
              </span>
              <span>
                <span style={{ fontWeight: 600, color: "var(--info)" }}>{queueCounts.active}</span>{" "}
                <span style={{ color: "var(--mute)" }}>active</span>
              </span>
            </div>
          )}
        </div>

        <div className="adm__row-head">
          <span>Topic</span>
          <span>Version</span>
          <span>Status</span>
          <span>Generated</span>
          <span>Actions</span>
        </div>
        {rows.map((t) => (
          <div key={t.id} className="adm__row">
            <div>
              <div style={{ fontSize: 13.5, color: "var(--ink)", fontWeight: 500 }}>{t.title}</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--mute)", marginTop: 2 }}>{t.slug}</div>
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--mute)" }}>{t.version}</div>
            <div>
              <span
                className="badge"
                style={{
                  color: t.generationStatus === "done" ? "var(--good)" : t.generationStatus === "error" ? "var(--bad)" : "var(--warn)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 10.5,
                  textTransform: "uppercase",
                  letterSpacing: ".08em",
                }}
              >
                {t.generationStatus}
              </span>
            </div>
            <div style={{ fontSize: 12, color: "var(--mute)" }}>
              {t.generatedAt ? t.generatedAt.toLocaleString() : "—"}
            </div>
            <div>
              <RegenerateButton slug={t.slug} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RegenerateButton({ slug }: { slug: string }) {
  return (
    <form
      action={`/api/admin/topics/${slug}/regenerate`}
      method="POST"
    >
      <button
        type="submit"
        className="btn btn--ghost"
        style={{ fontFamily: "var(--font-mono)", fontSize: 11, textTransform: "uppercase", letterSpacing: ".06em" }}
      >
        Regenerate
      </button>
    </form>
  );
}
