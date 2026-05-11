import { notFound } from "next/navigation";
import Link from "next/link";
import { db } from "@/db/client";
import { topics } from "@/db/schema";
import { and, asc, eq, isNotNull } from "drizzle-orm";
import { parseTrack, TRACK_LABELS } from "@/lib/paths";
import { LanguageFilter } from "@/components/LanguageFilter";

const CSS = `
.tl { height:100%; overflow:auto; }
.tl__inner { max-width: 1080px; margin: 0 auto; padding: 36px 36px 64px; }
.tl__head { display:flex; align-items: end; gap: 24px; padding-bottom: 24px; border-bottom: 1px solid var(--line); }
.tl__h { font-size: 30px; font-weight: 600; letter-spacing: -0.024em; line-height: 1.1; }
.tl__h em { font-family: var(--font-read); font-style: italic; font-weight: 400; color: var(--mute); }
.tl__sub { color: var(--mute); font-size: 14px; margin-top: 8px; max-width: 56ch; }
.tl__sort { margin-left: auto; display:flex; gap: 8px; align-items: center; }
.tl__counts { display:flex; gap: 18px; padding: 14px 0 4px; }
.tl__counts span { font-family: var(--font-mono); font-size: 11px; color: var(--mute); text-transform: uppercase; letter-spacing: .1em; }
.tl__counts b { color: var(--ink); font-weight: 500; }
.grp { padding-top: 28px; }
.grp__h { display:flex; align-items: baseline; gap: 14px; padding-bottom: 12px; border-bottom: 1px solid var(--line); }
.grp__k { font-family: var(--font-ui); font-size: 13.5px; font-weight: 600; letter-spacing: -0.005em; }
.grp__n { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute-2); text-transform: uppercase; letter-spacing: .1em; }
.grp__avg { margin-left: auto; font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .1em; }
.grp__avg b { color: var(--accent); font-weight: 500; }
.tl__row { display:grid; grid-template-columns: 32px 1fr 110px 80px 24px; gap: 18px; padding: 16px 6px 16px 0; border-bottom: 1px solid var(--line); align-items: center; cursor: pointer; text-decoration: none; color: inherit; }
.tl__row:hover { background: var(--bg-2); }
.row__n { font-family: var(--font-mono); font-size: 11px; color: var(--mute-2); padding-left: 6px; }
.row__main { display:flex; flex-direction: column; gap: 4px; min-width: 0; }
.row__t { display:flex; align-items: baseline; gap: 10px; }
.row__ttl { font-size: 14.5px; color: var(--ink); letter-spacing: -0.005em; font-weight: 500; }
.row__sum { color: var(--mute); font-size: 13px; line-height: 1.45; max-width: 78ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row__bar { display:flex; align-items: center; gap: 8px; }
.row__bar .b { flex:1; height: 3px; background: var(--surf-3); border-radius: 999px; overflow: hidden; }
.row__bar .b > i { display:block; height:100%; background: var(--ink-2); }
.row__bar .b > i.acc { background: var(--accent); }
.row__pct { font-family: var(--font-mono); font-size: 11px; color: var(--ink); width: 24px; text-align: right; }
.row__cards { font-family: var(--font-mono); font-size: 11px; color: var(--mute); text-align: right; }
.row__cards b { color: var(--ink-2); font-weight: 500; }
.row__chev { color: var(--mute-2); display:flex; justify-content: center; }
.tl__row:hover .row__chev { color: var(--ink); }
.row.is-pdf .row__ttl { color: var(--mute); }
.pdfb { font-family: var(--font-mono); font-size: 9.5px; color: var(--mute-2); padding: 1px 5px; border:1px solid var(--line); border-radius: 3px; text-transform: uppercase; letter-spacing: .12em; }
.lang-filter { display:flex; gap: 8px; padding: 16px 0 4px; flex-wrap: wrap; }
`;

export default async function TopicsPage({
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

  const baseWhere = eq(topics.track, track);
  const whereClause =
    track === "coding" && lang ? and(baseWhere, eq(topics.language, lang)) : baseWhere;

  const all = await db
    .select()
    .from(topics)
    .where(whereClause)
    .orderBy(asc(topics.categoryOrder), asc(topics.topicOrder));

  const languageRows =
    track === "coding"
      ? await db
          .selectDistinct({ language: topics.language })
          .from(topics)
          .where(and(eq(topics.track, "coding"), isNotNull(topics.language)))
      : [];
  const availableLanguages = languageRows
    .map((r) => r.language)
    .filter((x): x is string => !!x)
    .sort();

  const grouped = new Map<string, typeof all>();
  for (const t of all) {
    if (!grouped.has(t.category)) grouped.set(t.category, []);
    grouped.get(t.category)!.push(t);
  }

  let globalIdx = 0;

  return (
    <div className="tl">
      <style>{CSS}</style>
      <div className="tl__inner">
        {/* Header */}
        <div className="tl__head">
          <div>
            <h1 className="tl__h">
              Topics <em>· {TRACK_LABELS[track]}</em>
            </h1>
            <p className="tl__sub">
              {all.length} concepts across {grouped.size} categories.
            </p>
          </div>
        </div>

        {/* Counts strip */}
        <div className="tl__counts">
          <span><b>{all.length}</b> Topics</span>
          <span><b>{grouped.size}</b> Categories</span>
          <span><b>{all.filter((t) => t.mdxPath).length}</b> Ready</span>
        </div>

        {/* Language filter for coding track */}
        {track === "coding" && availableLanguages.length > 0 && (
          <div className="lang-filter">
            <LanguageFilter
              languages={availableLanguages}
              activeLanguage={lang ?? null}
              basePath={`/${track}/topics`}
            />
          </div>
        )}

        {grouped.size === 0 && (
          <div style={{ padding: "48px 0", textAlign: "center", color: "var(--mute)", fontSize: "14px" }}>
            No topics yet — upload a PDF to get started.
          </div>
        )}

        {/* Grouped topic list */}
        {[...grouped.entries()].map(([category, items]) => {
          const avgMastery = Math.round(items.reduce((a, t) => a + t.mastery, 0) / items.length);
          return (
            <div key={category} className="grp">
              <div className="grp__h">
                <span className="grp__k">{category}</span>
                <span className="grp__n">{items.length} topics</span>
                <span className="grp__avg">Avg mastery <b>{avgMastery}%</b></span>
              </div>
              {items.map((t) => {
                globalIdx += 1;
                const idx = globalIdx;
                const isPdf = !t.mdxPath;
                return (
                  <Link
                    key={t.id}
                    href={`/${track}/topics/${t.slug}`}
                    className={`tl__row${isPdf ? " row is-pdf" : ""}`}
                  >
                    <span className="row__n">{String(idx).padStart(2, "0")}</span>
                    <div className="row__main">
                      <div className="row__t">
                        <span className="row__ttl">{t.title}</span>
                        {isPdf && <span className="pdfb">PDF</span>}
                      </div>
                      {t.summary && (
                        <span className="row__sum">{t.summary}</span>
                      )}
                    </div>
                    <div className="row__bar">
                      <div className="b">
                        <i
                          className={t.mastery >= 80 ? "acc" : ""}
                          style={{ width: `${t.mastery}%` }}
                        />
                      </div>
                      <span className="row__pct">{t.mastery}%</span>
                    </div>
                    <span className="row__cards">—</span>
                    <span className="row__chev">›</span>
                  </Link>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
