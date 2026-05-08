import { db } from "@/db/client";
import { topics, topicLinks } from "@/db/schema";
import { asc } from "drizzle-orm";
import { ConceptMap } from "@/components/ConceptMap";

export default async function ConceptMapPage() {
  const allTopics = await db
    .select()
    .from(topics)
    .orderBy(asc(topics.categoryOrder), asc(topics.topicOrder));
  const links = await db.select().from(topicLinks);

  return (
    <div className="max-w-7xl mx-auto p-8 space-y-4">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Concept Map</h1>
        <p className="text-muted-foreground mt-1">
          {allTopics.length} topics · {links.length} relationships. Click any node to jump to its page.
        </p>
      </header>

      <ConceptMap
        topics={allTopics.map((t) => ({
          id: t.id,
          slug: t.slug,
          title: t.title,
          category: t.category,
          categoryOrder: t.categoryOrder,
          topicOrder: t.topicOrder,
          mastery: t.mastery,
        }))}
        links={links.map((l) => ({
          fromTopicId: l.fromTopicId,
          toTopicId: l.toTopicId,
          relation: l.relation,
        }))}
      />

      {links.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Tip: relationships are seeded in <code className="bg-muted px-1 rounded">scripts/seed-links.ts</code> (run <code className="bg-muted px-1 rounded">npx tsx scripts/seed-links.ts</code>) or added manually as you study.
        </p>
      )}
    </div>
  );
}
