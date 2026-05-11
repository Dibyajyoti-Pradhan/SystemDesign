import Fuse from "fuse.js";
import { db } from "@/db/client";
import { topics, questions } from "@/db/schema";

export type SearchHit = {
  kind: "topic" | "question";
  id: number;
  slug: string;
  title: string;
  category?: string;
  track: string;
  score: number;
};

let _index: { fuse: Fuse<any>; built: number } | null = null;
const TTL_MS = 30_000;

async function buildIndex() {
  const allTopics = await db.select().from(topics);
  const allQuestions = await db.select().from(questions);
  const docs = [
    ...allTopics.map((t) => ({ kind: "topic" as const, id: t.id, slug: t.slug, title: t.title, category: t.category, summary: t.summary, track: t.track })),
    ...allQuestions.map((q) => ({ kind: "question" as const, id: q.id, slug: q.slug, title: q.title, category: "Design Question", summary: "", track: q.track })),
  ];
  const fuse = new Fuse(docs, {
    keys: [{ name: "title", weight: 2 }, { name: "category", weight: 1 }, { name: "summary", weight: 0.5 }],
    threshold: 0.4,
    includeScore: true,
    ignoreLocation: true,
    minMatchCharLength: 2,
  });
  return { fuse, built: Date.now() };
}

export async function search(query: string, limit = 20): Promise<SearchHit[]> {
  if (!query.trim()) return [];
  if (!_index || Date.now() - _index.built > TTL_MS) {
    _index = await buildIndex();
  }
  const results = _index.fuse.search(query, { limit });
  return results.map((r) => ({
    kind: r.item.kind,
    id: r.item.id,
    slug: r.item.slug,
    title: r.item.title,
    category: r.item.category,
    track: r.item.track,
    score: r.score ?? 1,
  }));
}
