import { db } from "@/db/client";
import { topics, topicLinks } from "@/db/schema";
import { asc } from "drizzle-orm";
import { ConceptMap } from "@/components/ConceptMap";

const CSS = `
.cm-wrap { height:100%; position: relative; background: var(--bg); overflow:hidden; }
.cm__hud { position:absolute; top: 14px; left: 18px; z-index: 5; display:flex; flex-direction: column; gap: 12px; }
.cm__title { padding: 10px 14px; background: rgba(11,12,14,0.85); backdrop-filter: blur(6px); border:1px solid var(--line); border-radius: 8px; display:flex; flex-direction: column; gap:2px; }
.cm__title b { font-size: 13.5px; font-weight: 600; letter-spacing: -0.005em; }
.cm__title span { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .1em; }
.cm__filters { position:absolute; top: 14px; right: 18px; z-index: 5; display:flex; gap: 6px; }
.cm-pill { padding: 6px 10px; border-radius: 6px; border:1px solid var(--line); background: rgba(11,12,14,0.85); backdrop-filter: blur(6px); font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .08em; cursor:pointer; }
.cm-pill.is-on { color: var(--ink); border-color: var(--line-2); background: var(--surf); }
.cm__ctrl { position:absolute; bottom: 16px; right: 18px; z-index: 5; display:flex; flex-direction: column; gap: 8px; align-items: flex-end; }
.mini { width: 180px; height: 110px; border:1px solid var(--line); border-radius: 6px; background: rgba(11,12,14,0.85); position: relative; }
.mini__view { position:absolute; left: 25%; top: 30%; width: 50%; height: 45%; border:1.5px solid var(--accent); border-radius: 3px; }
.zooms { display:flex; flex-direction: column; gap: 1px; padding: 3px; background: rgba(11,12,14,0.85); border:1px solid var(--line); border-radius: 6px; }
.zooms button { width: 28px; height: 28px; border:0; background: transparent; color: var(--ink-2); cursor:pointer; border-radius: 4px; }
.zooms button:hover { background: var(--surf); color: var(--ink); }
.cm__graph-wrap { position:absolute; inset: 0; }
`;

export default async function ConceptMapPage() {
  const allTopics = await db
    .select()
    .from(topics)
    .orderBy(asc(topics.categoryOrder), asc(topics.topicOrder));
  const links = await db.select().from(topicLinks);

  return (
    <div className="cm-wrap">
      <style dangerouslySetInnerHTML={{ __html: CSS }} />
      <div className="cm__hud">
        <div className="cm__title">
          <b>Concept map</b>
          <span>{allTopics.length} topics · {links.length} relationships</span>
        </div>
      </div>
      <div className="cm__filters">
        <span className="cm-pill is-on">All</span>
        <span className="cm-pill">Focus</span>
      </div>
      <div className="cm__graph-wrap">
        <ConceptMap
          topics={allTopics.map((t) => ({
            id: t.id,
            slug: t.slug,
            title: t.title,
            category: t.category,
            categoryOrder: t.categoryOrder,
            topicOrder: t.topicOrder,
            mastery: t.mastery,
            track: t.track,
          }))}
          links={links.map((l) => ({
            fromTopicId: l.fromTopicId,
            toTopicId: l.toTopicId,
            relation: l.relation,
          }))}
        />
      </div>
      <div className="cm__ctrl">
        <div className="mini"><div className="mini__view"/></div>
      </div>
    </div>
  );
}
