/**
 * Seed script for local SQLite dev database.
 * Run: DATABASE_URL=sqlite:./local.db npx tsx scripts/seed-local.ts
 */
import { db } from "../src/db/client";
import { topics, questions, cards, reviews, topicLinks, interviewSessions, notes } from "../src/db/schema";

const SEED_VERSION = 3; // bump to force reseed

const C = "system-design/topics/core-system-design-fundamentals";
const D = "system-design/topics/databases-data-management";

async function main() {
  console.log("Seeding local SQLite database...");

  // Check version file to avoid duplicate seeding
  const existing = db.select().from(topics).all();
  if (existing.length >= 10) {
    console.log(`Already fully seeded (${existing.length} topics). Skipping.`);
    return;
  }

  // Wipe existing partial data — order matters for FK constraints
  if (existing.length > 0) {
    db.delete(reviews).run();
    db.delete(cards).run();
    db.delete(interviewSessions).run();
    db.delete(notes).run();
    db.delete(topicLinks).run();
    db.delete(questions).run();
    db.delete(topics).run();
    console.log("Cleared partial seed data.");
  }

  // ── Topics ──────────────────────────────────────────────────────────────────
  const insertedTopics = db
    .insert(topics)
    .values([
      // Core Concepts
      {
        userId: "dev-user", track: "system-design",
        slug: "latency-and-throughput", category: "Core Concepts", categoryOrder: 1, topicOrder: 1,
        title: "Latency, throughput, and the back-of-envelope",
        summary: "The numbers a senior engineer should know cold, and how to reason from them.",
        mastery: 92, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-latency-and-throughput.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "cap-theorem", category: "Core Concepts", categoryOrder: 1, topicOrder: 2,
        title: "CAP and PACELC",
        summary: "CAP is a starting point; PACELC is the thing you actually argue about.",
        mastery: 88, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-cap-theorem.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "consistency-models", category: "Core Concepts", categoryOrder: 1, topicOrder: 3,
        title: "Consistency models, ranked",
        summary: "Strict serializable through eventual — what each costs and what each buys.",
        mastery: 72, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-consistency-models.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "fallacies-distributed-computing", category: "Core Concepts", categoryOrder: 1, topicOrder: 4,
        title: "The fallacies of distributed computing",
        summary: "Eight things every system assumes that aren't true. Includes \"the network is reliable.\"",
        mastery: 60, generationStatus: "pending",
      },
      // Storage
      {
        userId: "dev-user", track: "system-design",
        slug: "btrees-vs-lsm", category: "Storage", categoryOrder: 2, topicOrder: 1,
        title: "B-trees vs. LSM-trees",
        summary: "Where each wins, and the modern hybrids (Sorted Sets, Tiered LSM) that blur the line.",
        mastery: 78, generationStatus: "pending",
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "replication-strategies", category: "Storage", categoryOrder: 2, topicOrder: 2,
        title: "Replication strategies",
        summary: "Single leader, multi-leader, leaderless — failure modes, ordering guarantees, and operator pain.",
        mastery: 54, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-replication.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "indexing-read-write-asymmetry", category: "Storage", categoryOrder: 2, topicOrder: 3,
        title: "Indexing for read/write asymmetry",
        summary: "Why \"just add an index\" is the wrong reflex past 100M rows.",
        mastery: 0, generationStatus: "pending",
      },
      // Distributed Systems
      {
        userId: "dev-user", track: "system-design",
        slug: "consistent-hashing", category: "Distributed Systems", categoryOrder: 3, topicOrder: 1,
        title: "Consistent hashing",
        summary: "A hashing scheme that minimises remappings when nodes join or leave the ring.",
        mastery: 72, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-consistent-hashing.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "quorum-replication", category: "Distributed Systems", categoryOrder: 3, topicOrder: 2,
        title: "Quorum-based replication",
        summary: "Why R + W > N is the rule, and the surprising number of ways it still goes wrong.",
        mastery: 44, generationStatus: "pending",
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "distributed-snapshots", category: "Distributed Systems", categoryOrder: 3, topicOrder: 3,
        title: "Distributed snapshots",
        summary: "Chandy-Lamport, what a \"consistent cut\" actually means, and where it shows up in practice.",
        mastery: 0, generationStatus: "pending",
      },
    ])
    .returning()
    .all();

  console.log(`Inserted ${insertedTopics.length} topics.`);

  // ── Questions ────────────────────────────────────────────────────────────────
  const insertedQuestions = db
    .insert(questions)
    .values([
      {
        userId: "dev-user", track: "system-design",
        slug: "design-url-shortener", number: 1,
        title: "Design a URL shortener at scale", difficulty: "medium",
        tags: JSON.stringify(["storage", "caching", "sharding"]), estMinutes: 30,
        mdxPath: "system-design/questions/design-url-shortener.mdx",
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-twitter-feed", number: 2,
        title: "Design Twitter / a high-fanout feed", difficulty: "hard",
        tags: JSON.stringify(["fanout", "feed", "timeline"]), estMinutes: 45,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-rate-limiter", number: 3,
        title: "Design a global rate limiter", difficulty: "medium",
        tags: JSON.stringify(["rate-limit", "distributed", "clocks"]), estMinutes: 30,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-dropbox", number: 4,
        title: "Design Dropbox / a file sync service", difficulty: "hard",
        tags: JSON.stringify(["sync", "crdt", "blob"]), estMinutes: 45,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-typeahead", number: 5,
        title: "Design a typeahead / autocomplete service", difficulty: "easy",
        tags: JSON.stringify(["search", "trie", "cache"]), estMinutes: 25,
        mdxPath: "system-design/questions/01-typeahead-and-autocomplete.mdx",
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-notification-system", number: 6,
        title: "Design a notification system at scale", difficulty: "medium",
        tags: JSON.stringify(["queue", "delivery", "retry"]), estMinutes: 30,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-metrics-pipeline", number: 7,
        title: "Design a metrics + alerting pipeline", difficulty: "hard",
        tags: JSON.stringify(["ts-db", "aggregation"]), estMinutes: 45,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-chat-app", number: 8,
        title: "Design a chat / messaging app", difficulty: "medium",
        tags: JSON.stringify(["realtime", "push", "presence"]), estMinutes: 35,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-distributed-scheduler", number: 9,
        title: "Design a distributed scheduler (cron at scale)", difficulty: "medium",
        tags: JSON.stringify(["leader", "schedule", "clocks"]), estMinutes: 30,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-payment-ledger", number: 10,
        title: "Design a payment ledger", difficulty: "hard",
        tags: JSON.stringify(["acid", "idempotency", "audit"]), estMinutes: 45,
      },
    ])
    .returning()
    .all();

  console.log(`Inserted ${insertedQuestions.length} questions.`);

  // ── Cards (SRS deck) ─────────────────────────────────────────────────────────
  const now = new Date();
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);

  // Helper: find topic by slug
  const bySlug = (slug: string) => insertedTopics.find((t) => t.slug === slug)!;

  const cardRows = db
    .insert(cards)
    .values([
      // Consistent hashing (3 cards, already reviewed)
      {
        userId: "dev-user", topicId: bySlug("consistent-hashing").id, type: "definition",
        front: "What is consistent hashing?",
        back: "A hashing technique where the hash space forms a ring. When a node is added or removed, only keys in the arc between that node and its predecessor need remapping — ~1/n of the total keyspace.",
        status: "active", dueAt: yesterday, lastReviewedAt: yesterday,
        ease: 2.5, intervalDays: 1, repetitions: 1,
      },
      {
        userId: "dev-user", topicId: bySlug("consistent-hashing").id, type: "tradeoff",
        front: "What problem do virtual nodes solve in consistent hashing?",
        back: "Non-uniform load distribution. Without vnodes, one physical server may own 40% of keys. With 150+ vnodes per server, variance drops to O(1/√vnodes), giving near-uniform distribution even with heterogeneous hardware.",
        status: "active", dueAt: yesterday, lastReviewedAt: yesterday,
        ease: 2.6, intervalDays: 2, repetitions: 2,
      },
      {
        userId: "dev-user", topicId: bySlug("consistent-hashing").id, type: "scenario",
        front: "When would you use consistent hashing in a system design?",
        back: "Distributed caches (Memcached, Redis Cluster), distributed databases (Cassandra token ring), CDN edge selection, load balancers needing session affinity without a lookup table.",
        status: "active", dueAt: now, lastReviewedAt: yesterday,
        ease: 2.4, intervalDays: 1, repetitions: 1,
      },
      // CAP theorem (3 cards)
      {
        userId: "dev-user", topicId: bySlug("cap-theorem").id, type: "definition",
        front: "What does CAP's C actually mean — and what does it NOT mean?",
        back: "CAP C means linearizability: every read reflects the most recently completed write, globally ordered as if through a single log. It does NOT mean ACID consistency or eventual consistency. This distinction costs candidates interviews.",
        status: "active", dueAt: yesterday, lastReviewedAt: yesterday,
        ease: 2.3, intervalDays: 1, repetitions: 1,
      },
      {
        userId: "dev-user", topicId: bySlug("cap-theorem").id, type: "tradeoff",
        front: "CP vs AP — what does each sacrifice during a partition?",
        back: "CP: reject writes or return errors to maintain consistency. AP: accept writes and serve potentially stale reads to remain available. Because partitions are unavoidable in multi-node systems, the operative choice is always CP vs AP.",
        status: "active", dueAt: yesterday,
        ease: 2.5, intervalDays: 3, repetitions: 3,
      },
      {
        userId: "dev-user", topicId: bySlug("cap-theorem").id, type: "scenario",
        front: "Give a real example of a CP system and an AP system.",
        back: "CP: HBase, Zookeeper, etcd (refuse writes during partition to preserve linearizability). AP: Cassandra, DynamoDB, CouchDB (accept writes, reconcile via last-write-wins or CRDTs). Postgres single-node is CA but not partition-tolerant.",
        status: "active", dueAt: now,
        ease: 2.5, intervalDays: 1, repetitions: 1,
      },
      // Consistency models (3 cards)
      {
        userId: "dev-user", topicId: bySlug("consistency-models").id, type: "definition",
        front: "Rank the main consistency models from strongest to weakest.",
        back: "Strict serializability → Serializability → Linearizability → Sequential → Causal → Read-your-writes → Monotonic reads → Eventual. Each weaker model trades correctness guarantees for latency or availability.",
        status: "active", dueAt: yesterday,
        ease: 2.2, intervalDays: 1, repetitions: 1,
      },
      {
        userId: "dev-user", topicId: bySlug("consistency-models").id, type: "tradeoff",
        front: "What's the difference between linearizability and serializability?",
        back: "Linearizability is a single-object guarantee: operations appear instantaneous with respect to wall-clock time. Serializability is a multi-object (transaction) guarantee: transactions execute as if in some serial order, but that order need not match real time.",
        status: "active", dueAt: now,
        ease: 2.5, intervalDays: 1, repetitions: 1,
      },
      // Latency (2 cards)
      {
        userId: "dev-user", topicId: bySlug("latency-and-throughput").id, type: "definition",
        front: "Name 5 latency numbers every engineer should know.",
        back: "L1 cache ~1ns · RAM access ~100ns · SSD random read ~100μs · Network round-trip same DC ~500μs · HDD seek ~10ms · Network cross-region ~100ms. These anchor back-of-envelope estimates.",
        status: "active", dueAt: yesterday,
        ease: 2.6, intervalDays: 4, repetitions: 4,
      },
      {
        userId: "dev-user", topicId: bySlug("latency-and-throughput").id, type: "scenario",
        front: "A service has 1ms p50 and 800ms p99. What's most likely causing this?",
        back: "High p99 with low p50 typically signals: lock contention on hot keys, GC pauses (JVM/Go), queue depth spikes under bursty load, or head-of-line blocking in connection pools. Profile with percentile breakdown and check tail-latency amplification from fan-out.",
        status: "active", dueAt: now,
        ease: 2.5, intervalDays: 1, repetitions: 1,
      },
    ])
    .returning()
    .all();

  console.log(`Inserted ${cardRows.length} cards.`);
  console.log("Done seeding.");
}

main().catch((err) => {
  console.error("Seed failed:", err);
  process.exit(1);
});
