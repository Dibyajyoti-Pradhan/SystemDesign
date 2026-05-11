/**
 * Local SQLite dev seed.
 * Scans the same PDF source directories as seed.ts, so topic/question counts
 * always match the repo's actual content — no manual list to keep in sync.
 *
 * Adds a handful of SRS cards and mastery scores for a realistic demo.
 */
import fs from "node:fs";
import path from "node:path";
import { db } from "../src/db/client";
import { topics, questions, cards, reviews, topicLinks, interviewSessions, notes, type NewTopic } from "../src/db/schema";
import { eq } from "drizzle-orm";
import { slugify } from "../src/lib/utils";
import { REPO_ROOT, TRACK_PATHS, CONTENT_ROOT } from "../src/lib/paths";
import type { Track } from "../src/db/schema";

const TRACKS: Track[] = ["system-design", "coding"];

// ── helpers (mirrors seed.ts) ────────────────────────────────────────────────
function readDir(p: string): string[] {
  if (!fs.existsSync(p)) return [];
  return fs.readdirSync(p).sort();
}
function parseCategoryFolder(name: string) {
  const m = name.match(/^(\d+)\s*-\s*(.+)$/);
  if (!m) return null;
  return { order: parseInt(m[1], 10), category: m[2].trim() };
}
function parseTopicFile(name: string) {
  const m = name.match(/^(\d+)\s*-\s*(.+?)\.(pdf|docx|md)$/i);
  if (!m) return null;
  return { order: parseInt(m[1], 10), title: m[2].trim(), ext: m[3].toLowerCase() };
}
function parseQuestionFile(name: string) {
  const m = name.match(/^(\d+)\s*-\s*(.+?)\.(pdf|docx|md)$/i);
  if (!m) return null;
  return { number: parseInt(m[1], 10), title: m[2].trim(), ext: m[3].toLowerCase() };
}

// ── MDX path lookup: if generated content exists, wire it up ─────────────────
const mdxTopicMap: Record<string, string> = {};
function buildMdxMap() {
  const sd = path.join(CONTENT_ROOT, "system-design/topics");
  for (const dir of readDir(sd)) {
    const abs = path.join(sd, dir);
    if (!fs.statSync(abs).isDirectory()) continue;
    for (const f of readDir(abs)) {
      if (!f.endsWith(".mdx")) continue;
      const slug = f.replace(/\.mdx$/, "");
      mdxTopicMap[slug] = `system-design/topics/${dir}/${f}`;
    }
  }
  // questions MDX
  const sq = path.join(CONTENT_ROOT, "system-design/questions");
  for (const f of readDir(sq)) {
    if (!f.endsWith(".mdx")) continue;
    const slug = f.replace(/\.mdx$/, "");
    mdxTopicMap[`q:${slug}`] = `system-design/questions/${f}`;
  }
}

// Try to find an mdxPath for a topic slug (fuzzy: match any key that contains the slug words)
function findMdxPath(slug: string): string | undefined {
  // Exact match first
  if (mdxTopicMap[slug]) return mdxTopicMap[slug];
  // Partial: any stored key that ends with the slug
  const key = Object.keys(mdxTopicMap).find((k) => k.endsWith(slug) || k.includes(slug));
  return key ? mdxTopicMap[key] : undefined;
}

function findQuestionMdx(slug: string): string | undefined {
  return mdxTopicMap[`q:${slug}`] ?? mdxTopicMap[`q:${slug.replace(/^0*(\d+)-/, "$1-")}`];
}

// ── seeding ──────────────────────────────────────────────────────────────────
async function seedTopics(track: Track): Promise<number> {
  const root = TRACK_PATHS[track].studyGuideSources;
  const rows: NewTopic[] = [];

  for (const catName of readDir(root)) {
    const catDir = path.join(root, catName);
    if (!fs.statSync(catDir).isDirectory()) continue;
    const cat = parseCategoryFolder(catName);
    if (!cat) continue;

    const files = readDir(catDir).filter((f) => /\.(pdf|docx|md)$/i.test(f));
    for (const file of files) {
      const t = parseTopicFile(file);
      if (!t) continue;
      const slug = slugify(`${cat.category}-${t.title}`);
      rows.push({
        userId: "dev-user",
        track,
        slug,
        category: cat.category,
        categoryOrder: cat.order,
        topicOrder: t.order,
        title: t.title,
        summary: "",
        pdfPath: path.relative(REPO_ROOT, path.join(catDir, file)),
        mdxPath: findMdxPath(slug),
        generationStatus: findMdxPath(slug) ? "done" : "pending",
      });
    }
  }

  let count = 0;
  for (const r of rows) {
    try {
      const res = db.insert(topics).values(r).onConflictDoNothing().returning({ id: topics.id }).all();
      if (res.length > 0) count++;
    } catch (e) {
      console.error(`[${track}] topic insert failed:`, r.slug, e);
    }
  }
  console.log(`[${track}] ${count}/${rows.length} topics across ${new Set(rows.map((r) => r.category)).size} categories`);
  return count;
}

async function seedQuestions(track: Track): Promise<number> {
  if (track === "coding") return 0; // coding questions need language JSON; skip for local dev

  const root = TRACK_PATHS[track].questionsSources;
  if (!fs.existsSync(root)) return 0;

  const files = readDir(root).filter((f) => /\.(pdf|docx|md)$/i.test(f));
  let count = 0;
  for (const file of files) {
    const q = parseQuestionFile(file);
    if (!q) continue;
    const slug = slugify(`${String(q.number).padStart(2, "0")}-${q.title}`);
    const mdxSlug = slug.replace(/^0+/, "");
    try {
      const res = db
        .insert(questions)
        .values({
          userId: "dev-user",
          track,
          slug,
          number: q.number,
          title: q.title,
          difficulty: "medium",
          tags: "[]",
          pdfPath: path.relative(REPO_ROOT, path.join(root, file)),
          mdxPath: findQuestionMdx(slug) ?? findQuestionMdx(mdxSlug),
        })
        .onConflictDoNothing()
        .returning({ id: questions.id })
        .all();
      if (res.length > 0) count++;
    } catch (e) {
      console.error(`[${track}] question insert failed:`, slug, e);
    }
  }
  console.log(`[${track}] ${count}/${files.length} questions`);
  return count;
}

// ── demo mastery + SRS cards ─────────────────────────────────────────────────
function seedDemoCards() {
  const allTopics = db.select().from(topics).all();
  const find = (slug: string) => allTopics.find((t) => t.slug === slug);

  const now = new Date();
  const d1 = new Date(now.getTime() - 1 * 86400000);
  const d2 = new Date(now.getTime() - 2 * 86400000);

  // Spot-set mastery on a handful of topics so the UI looks lived-in
  const masteryMap: Record<string, number> = {
    "core-system-design-fundamentals-latency-and-throughput": 92,
    "core-system-design-fundamentals-cap-theorem": 88,
    "core-system-design-fundamentals-consistency-models": 72,
    "core-system-design-fundamentals-caching": 78,
    "core-system-design-fundamentals-consistent-hashing": 72,
    "core-system-design-fundamentals-scalability": 81,
    "core-system-design-fundamentals-availability": 65,
    "core-system-design-fundamentals-replication": 54,
    "core-system-design-fundamentals-partitioning-and-sharding": 60,
    "databases-data-management-relational-databases": 70,
  };
  for (const [slug, mastery] of Object.entries(masteryMap)) {
    const t = find(slug);
    if (t) db.update(topics).set({ mastery }).where(eq(topics.id, t.id)).run();
  }

  const cardDefs = [
    {
      slug: "core-system-design-fundamentals-consistent-hashing",
      items: [
        {
          type: "definition" as const,
          front: "What is consistent hashing?",
          back: "A hashing technique where keys and nodes share a ring. Adding/removing a node only remaps ~1/n keys — not the whole keyspace.",
          dueAt: d1, ease: 2.5, intervalDays: 1, repetitions: 1,
        },
        {
          type: "tradeoff" as const,
          front: "What problem do virtual nodes solve in consistent hashing?",
          back: "Non-uniform load. Without vnodes one server may own 40% of keys. With 150+ vnodes variance drops to O(1/√vnodes).",
          dueAt: d2, ease: 2.6, intervalDays: 2, repetitions: 2,
        },
        {
          type: "scenario" as const,
          front: "When would you use consistent hashing in a design?",
          back: "Distributed caches (Redis Cluster, Memcached), Cassandra token ring, CDN PoP selection, sticky load balancers.",
          dueAt: now, ease: 2.4, intervalDays: 1, repetitions: 1,
        },
      ],
    },
    {
      slug: "core-system-design-fundamentals-cap-theorem",
      items: [
        {
          type: "definition" as const,
          front: "What does CAP's C actually mean?",
          back: "Linearizability — every read reflects the most recently completed write, globally ordered. NOT ACID consistency, NOT eventual consistency.",
          dueAt: d1, ease: 2.3, intervalDays: 1, repetitions: 1,
        },
        {
          type: "tradeoff" as const,
          front: "CP vs AP — what does each sacrifice during a partition?",
          back: "CP: reject writes to preserve consistency. AP: accept writes and serve possibly stale reads. Because partitions are unavoidable, the real choice is always CP vs AP.",
          dueAt: d2, ease: 2.5, intervalDays: 3, repetitions: 3,
        },
      ],
    },
    {
      slug: "core-system-design-fundamentals-caching",
      items: [
        {
          type: "definition" as const,
          front: "Difference between cache-aside and write-through?",
          back: "Cache-aside: app reads cache, on miss reads DB and populates. Write-through: every write goes to cache AND DB synchronously — avoids stale reads but adds write latency.",
          dueAt: d1, ease: 2.4, intervalDays: 2, repetitions: 2,
        },
        {
          type: "tradeoff" as const,
          front: "What is the cache stampede problem?",
          back: "When a hot key expires, many requests simultaneously read DB and populate cache, spiking load. Fix: probabilistic early expiry, single-writer lock, or background refresh.",
          dueAt: now, ease: 2.3, intervalDays: 1, repetitions: 1,
        },
      ],
    },
    {
      slug: "core-system-design-fundamentals-latency-and-throughput",
      items: [
        {
          type: "definition" as const,
          front: "Five latency numbers every engineer should know.",
          back: "L1 cache ~1ns · RAM ~100ns · SSD random read ~100μs · Same-DC RTT ~500μs · Cross-region RTT ~100ms.",
          dueAt: d2, ease: 2.6, intervalDays: 4, repetitions: 4,
        },
      ],
    },
  ];

  let count = 0;
  for (const { slug, items } of cardDefs) {
    const topic = find(slug);
    if (!topic) continue;
    for (const item of items) {
      db.insert(cards).values({
        userId: "dev-user",
        topicId: topic.id,
        type: item.type,
        front: item.front,
        back: item.back,
        status: "active",
        dueAt: item.dueAt,
        lastReviewedAt: d2,
        ease: item.ease,
        intervalDays: item.intervalDays,
        repetitions: item.repetitions,
      }).run();
      count++;
    }
  }
  console.log(`Demo: ${count} SRS cards added`);
}

// ── wipe in FK-safe order ────────────────────────────────────────────────────
function wipeAll() {
  db.delete(reviews).run();
  db.delete(cards).run();
  db.delete(interviewSessions).run();
  db.delete(notes).run();
  db.delete(topicLinks).run();
  db.delete(questions).run();
  db.delete(topics).run();
}

// ── main ─────────────────────────────────────────────────────────────────────
async function main() {
  console.log("Seeding local SQLite database...");

  buildMdxMap();
  console.log(`MDX map: ${Object.keys(mdxTopicMap).length} entries`);

  const existing = db.select().from(topics).all();
  // Count total source PDFs to know the expected minimum
  const expectedTopics = TRACKS.flatMap((track) => {
    const root = TRACK_PATHS[track].studyGuideSources;
    if (!fs.existsSync(root)) return [];
    return readDir(root).flatMap((catName) => {
      const catDir = path.join(root, catName);
      if (!fs.existsSync(catDir) || !fs.statSync(catDir).isDirectory()) return [];
      return readDir(catDir).filter((f) => /\.(pdf|docx|md)$/i.test(f));
    });
  }).length;

  if (existing.length >= expectedTopics) {
    console.log(`Already fully seeded (${existing.length}/${expectedTopics} topics). Skipping.`);
    return;
  }

  if (existing.length > 0) {
    console.log(`Partial seed (${existing.length}/${expectedTopics}) — wiping and reseeding...`);
    wipeAll();
  }

  for (const track of TRACKS) {
    await seedTopics(track);
    await seedQuestions(track);
  }

  seedDemoCards();
  console.log("Done seeding.");
}

main().catch((err) => {
  console.error("Seed failed:", err);
  process.exit(1);
});
