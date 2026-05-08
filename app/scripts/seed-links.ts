import { db } from "../src/db/client";
import { topics, topicLinks } from "../src/db/schema";
import { inArray } from "drizzle-orm";

const RELATIONS: Array<[string, string]> = [
  ["scalability", "load-balancing"],
  ["scalability", "caching"],
  ["scalability", "partitioning-and-sharding"],
  ["scalability", "replication"],
  ["availability", "replication"],
  ["availability", "load-balancing"],
  ["availability", "reliability"],
  ["latency-and-throughput", "caching"],
  ["latency-and-throughput", "proxies"],
  ["reliability", "replication"],
  ["cap-theorem", "consistency-models"],
  ["cap-theorem", "replication"],
  ["consistency-models", "replication"],
  ["partitioning-and-sharding", "consistent-hashing"],
  ["partitioning-and-sharding", "replication"],
  ["caching", "proxies"],
  ["caching", "in-memory-stores"],
  ["caching", "cdn"],
  ["proxies", "load-balancing"],
  ["message-queues-and-pub-sub", "streaming-vs-batch-processing"],
  ["message-queues-and-pub-sub", "kafka"],
  ["streaming-vs-batch-processing", "mapreduce"],
  ["relational-databases", "indexing"],
  ["relational-databases", "transactions"],
  ["nosql-databases", "consistency-models"],
  ["search-and-indexing", "elasticsearch"],
  ["microservices", "api-gateway"],
  ["microservices", "service-discovery"],
  ["api-gateway", "rate-limiting"],
  ["circuit-breaker", "reliability"],
  ["rate-limiting", "load-balancing"],
];

async function main() {
  const allTopics = await db.select().from(topics);
  const bySlugFragment = new Map<string, number>();
  for (const t of allTopics) {
    // store by trailing path token to allow short keys above
    const trail = t.slug.split("-").slice(-3).join("-");
    bySlugFragment.set(trail, t.id);
    bySlugFragment.set(t.slug, t.id);
  }

  function findId(needle: string): number | null {
    for (const [k, id] of bySlugFragment) {
      if (k.endsWith(needle) || k.includes(needle)) return id;
    }
    return null;
  }

  const rows: Array<{ fromTopicId: number; toTopicId: number; relation: string }> = [];
  let missing = 0;
  for (const [a, b] of RELATIONS) {
    const aid = findId(a);
    const bid = findId(b);
    if (!aid || !bid) {
      missing++;
      console.log(`  skip: ${a} <-> ${b} (missing topic)`);
      continue;
    }
    rows.push({ fromTopicId: aid, toTopicId: bid, relation: "related" });
    rows.push({ fromTopicId: bid, toTopicId: aid, relation: "related" });
  }

  // Wipe and reinsert (idempotent)
  await db.delete(topicLinks);
  for (const r of rows) {
    await db.insert(topicLinks).values(r);
  }
  console.log(`Seeded ${rows.length} links (${missing} pairs skipped due to missing topics).`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
