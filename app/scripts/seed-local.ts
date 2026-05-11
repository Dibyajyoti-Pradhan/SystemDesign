/**
 * Seed script for local SQLite dev database.
 * Bump SEED_VERSION to force a fresh reseed on next npm run dev.
 */
import { db } from "../src/db/client";
import { topics, questions, cards, reviews, topicLinks, interviewSessions, notes } from "../src/db/schema";

export const SEED_VERSION = 4;

const C = "system-design/topics/core-system-design-fundamentals";
const D = "system-design/topics/databases-data-management";

async function main() {
  console.log("Seeding local SQLite database...");

  const existing = db.select().from(topics).all();
  if (existing.length >= 18) {
    console.log(`Already fully seeded (${existing.length} topics). Skipping.`);
    return;
  }

  // Wipe in FK-safe order
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

  // ── Topics ────────────────────────────────────────────────────────────────
  const insertedTopics = db
    .insert(topics)
    .values([
      // ── Core Concepts ──────────────────────────────────────────────────────
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
        slug: "scalability", category: "Core Concepts", categoryOrder: 1, topicOrder: 4,
        title: "Scalability patterns",
        summary: "Vertical vs horizontal scaling, stateless services, and the limits of each approach.",
        mastery: 81, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-scalability.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "availability", category: "Core Concepts", categoryOrder: 1, topicOrder: 5,
        title: "Availability and reliability",
        summary: "SLAs, nines of availability, fault tolerance patterns, and the difference between availability and reliability.",
        mastery: 65, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-availability.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "caching", category: "Core Concepts", categoryOrder: 1, topicOrder: 6,
        title: "Caching strategies",
        summary: "Cache-aside, write-through, write-behind — eviction policies and the cache invalidation problem.",
        mastery: 78, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-caching.mdx`,
      },

      // ── Storage ─────────────────────────────────────────────────────────────
      {
        userId: "dev-user", track: "system-design",
        slug: "replication-strategies", category: "Storage", categoryOrder: 2, topicOrder: 1,
        title: "Replication strategies",
        summary: "Single leader, multi-leader, leaderless — failure modes, ordering guarantees, and operator pain.",
        mastery: 54, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-replication.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "partitioning-and-sharding", category: "Storage", categoryOrder: 2, topicOrder: 2,
        title: "Partitioning and sharding",
        summary: "Range vs hash partitioning, hot-key problems, and resharding without downtime.",
        mastery: 60, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-partitioning-and-sharding.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "relational-databases", category: "Storage", categoryOrder: 2, topicOrder: 3,
        title: "Relational databases deep-dive",
        summary: "ACID guarantees, isolation levels, MVCC, and when to reach for Postgres vs MySQL.",
        mastery: 70, generationStatus: "done",
        mdxPath: `${D}/databases-data-management-relational-databases.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "nosql-databases", category: "Storage", categoryOrder: 2, topicOrder: 4,
        title: "NoSQL databases",
        summary: "Document, column-family, key-value, and graph stores — choosing the right model.",
        mastery: 55, generationStatus: "done",
        mdxPath: `${D}/databases-data-management-nosql-databases.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "data-warehousing", category: "Storage", categoryOrder: 2, topicOrder: 5,
        title: "Data warehousing and OLAP",
        summary: "Columnar storage, star schemas, and why OLAP queries are fundamentally different from OLTP.",
        mastery: 40, generationStatus: "done",
        mdxPath: `${D}/databases-data-management-data-warehousing-and-olap.mdx`,
      },

      // ── Distributed Systems ──────────────────────────────────────────────────
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
        slug: "load-balancing", category: "Distributed Systems", categoryOrder: 3, topicOrder: 2,
        title: "Load balancing",
        summary: "L4 vs L7, round-robin to least-connections, health checks, and sticky sessions.",
        mastery: 68, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-load-balancing.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "message-queues", category: "Distributed Systems", categoryOrder: 3, topicOrder: 3,
        title: "Message queues and pub/sub",
        summary: "Kafka vs SQS vs RabbitMQ, at-least-once delivery, consumer groups, and back-pressure.",
        mastery: 58, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-message-queues-and-pub-sub.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "proxies", category: "Distributed Systems", categoryOrder: 3, topicOrder: 4,
        title: "Proxies and reverse proxies",
        summary: "Forward vs reverse proxy, service mesh, API gateway patterns, and where nginx fits.",
        mastery: 50, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-proxies.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "mapreduce", category: "Distributed Systems", categoryOrder: 3, topicOrder: 5,
        title: "MapReduce and batch processing",
        summary: "The map/shuffle/reduce model, Spark vs Hadoop, and when batch beats stream.",
        mastery: 45, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-mapreduce.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "streaming-vs-batch", category: "Distributed Systems", categoryOrder: 3, topicOrder: 6,
        title: "Streaming vs batch processing",
        summary: "Lambda architecture, Flink, Kafka Streams — when to use stream processing and the trade-offs.",
        mastery: 38, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-streaming-vs-batch-processing.mdx`,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "reliability", category: "Distributed Systems", categoryOrder: 3, topicOrder: 7,
        title: "Reliability patterns",
        summary: "Circuit breakers, bulkheads, retries with backoff — making distributed systems tolerate failure.",
        mastery: 62, generationStatus: "done",
        mdxPath: `${C}/core-system-design-fundamentals-reliability.mdx`,
      },
    ])
    .returning()
    .all();

  console.log(`Inserted ${insertedTopics.length} topics.`);

  // ── Questions ─────────────────────────────────────────────────────────────
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
      {
        userId: "dev-user", track: "system-design",
        slug: "design-youtube", number: 11,
        title: "Design YouTube / a video streaming platform", difficulty: "hard",
        tags: JSON.stringify(["cdn", "encoding", "streaming"]), estMinutes: 45,
        mdxPath: "system-design/questions/04-youtube.mdx",
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-search-engine", number: 12,
        title: "Design a web crawler + search engine", difficulty: "hard",
        tags: JSON.stringify(["crawl", "index", "ranking"]), estMinutes: 45,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-ride-sharing", number: 13,
        title: "Design a ride-sharing app (Uber/Lyft)", difficulty: "hard",
        tags: JSON.stringify(["geospatial", "matching", "realtime"]), estMinutes: 45,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-cdn", number: 14,
        title: "Design a CDN", difficulty: "medium",
        tags: JSON.stringify(["cdn", "edge", "caching"]), estMinutes: 35,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-key-value-store", number: 15,
        title: "Design a distributed key-value store", difficulty: "hard",
        tags: JSON.stringify(["kvstore", "raft", "consensus"]), estMinutes: 45,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-api-gateway", number: 16,
        title: "Design an API gateway", difficulty: "medium",
        tags: JSON.stringify(["gateway", "rate-limit", "auth"]), estMinutes: 30,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-google-docs", number: 17,
        title: "Design Google Docs / collaborative editing", difficulty: "hard",
        tags: JSON.stringify(["crdt", "ot", "realtime"]), estMinutes: 45,
      },
      {
        userId: "dev-user", track: "system-design",
        slug: "design-stock-exchange", number: 18,
        title: "Design a stock exchange matching engine", difficulty: "hard",
        tags: JSON.stringify(["orderbook", "latency", "consistency"]), estMinutes: 45,
      },
    ])
    .returning()
    .all();

  console.log(`Inserted ${insertedQuestions.length} questions.`);

  // ── SRS Cards ─────────────────────────────────────────────────────────────
  const now = new Date();
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  const twoDaysAgo = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000);

  const t = (slug: string) => insertedTopics.find((x) => x.slug === slug)!;

  const cardRows = db
    .insert(cards)
    .values([
      // Consistent hashing
      {
        userId: "dev-user", topicId: t("consistent-hashing").id, type: "definition",
        front: "What is consistent hashing?",
        back: "A hashing technique where the hash space forms a ring. When a node is added or removed, only keys in the arc between that node and its predecessor need remapping — ~1/n of the total keyspace.",
        status: "active", dueAt: yesterday, lastReviewedAt: twoDaysAgo,
        ease: 2.5, intervalDays: 1, repetitions: 1,
      },
      {
        userId: "dev-user", topicId: t("consistent-hashing").id, type: "tradeoff",
        front: "What problem do virtual nodes solve in consistent hashing?",
        back: "Non-uniform load distribution. Without vnodes, one server may own 40% of keys. With 150+ vnodes per server, variance drops to O(1/√vnodes), giving near-uniform distribution.",
        status: "active", dueAt: yesterday, lastReviewedAt: twoDaysAgo,
        ease: 2.6, intervalDays: 2, repetitions: 2,
      },
      {
        userId: "dev-user", topicId: t("consistent-hashing").id, type: "scenario",
        front: "When would you use consistent hashing in a system design?",
        back: "Distributed caches (Memcached, Redis Cluster), distributed databases (Cassandra token ring), CDN edge selection, load balancers needing session affinity without a lookup table.",
        status: "active", dueAt: now, lastReviewedAt: yesterday,
        ease: 2.4, intervalDays: 1, repetitions: 1,
      },
      // CAP theorem
      {
        userId: "dev-user", topicId: t("cap-theorem").id, type: "definition",
        front: "What does CAP's C actually mean — and what does it NOT mean?",
        back: "CAP C means linearizability: every read reflects the most recently completed write. It does NOT mean ACID consistency or eventual consistency. This distinction costs candidates interviews.",
        status: "active", dueAt: yesterday, lastReviewedAt: twoDaysAgo,
        ease: 2.3, intervalDays: 1, repetitions: 1,
      },
      {
        userId: "dev-user", topicId: t("cap-theorem").id, type: "tradeoff",
        front: "CP vs AP — what does each sacrifice during a network partition?",
        back: "CP: reject writes or return errors to maintain consistency. AP: accept writes and serve potentially stale reads to remain available. Because partitions are unavoidable, the real choice is always CP vs AP.",
        status: "active", dueAt: twoDaysAgo, lastReviewedAt: twoDaysAgo,
        ease: 2.5, intervalDays: 3, repetitions: 3,
      },
      {
        userId: "dev-user", topicId: t("cap-theorem").id, type: "scenario",
        front: "Give a real example of a CP system and an AP system.",
        back: "CP: HBase, Zookeeper, etcd (refuse writes during partition). AP: Cassandra, DynamoDB, CouchDB (accept writes, reconcile with LWW or CRDTs).",
        status: "active", dueAt: now,
        ease: 2.5, intervalDays: 1, repetitions: 1,
      },
      // Consistency models
      {
        userId: "dev-user", topicId: t("consistency-models").id, type: "definition",
        front: "Rank the main consistency models from strongest to weakest.",
        back: "Strict serializability → Serializability → Linearizability → Sequential → Causal → Read-your-writes → Monotonic reads → Eventual. Each weaker model trades correctness for latency/availability.",
        status: "active", dueAt: yesterday, lastReviewedAt: twoDaysAgo,
        ease: 2.2, intervalDays: 1, repetitions: 1,
      },
      {
        userId: "dev-user", topicId: t("consistency-models").id, type: "tradeoff",
        front: "What's the difference between linearizability and serializability?",
        back: "Linearizability is a single-object, real-time guarantee. Serializability is a multi-object (transaction) guarantee that doesn't require real-time ordering. Strict serializability is both combined.",
        status: "active", dueAt: now,
        ease: 2.5, intervalDays: 1, repetitions: 1,
      },
      // Latency
      {
        userId: "dev-user", topicId: t("latency-and-throughput").id, type: "definition",
        front: "Name 5 latency numbers every engineer should know.",
        back: "L1 cache ~1ns · RAM ~100ns · SSD random read ~100μs · Same-DC network RTT ~500μs · Cross-region RTT ~100ms. These anchor back-of-envelope estimates.",
        status: "active", dueAt: twoDaysAgo, lastReviewedAt: twoDaysAgo,
        ease: 2.6, intervalDays: 4, repetitions: 4,
      },
      {
        userId: "dev-user", topicId: t("latency-and-throughput").id, type: "scenario",
        front: "A service has 1ms p50 and 800ms p99. What's most likely causing this?",
        back: "Lock contention on hot keys, GC pauses, queue depth spikes under burst, or head-of-line blocking in connection pools. Profile percentile breakdown and check tail-latency amplification from fan-out calls.",
        status: "active", dueAt: now,
        ease: 2.5, intervalDays: 1, repetitions: 1,
      },
      // Caching
      {
        userId: "dev-user", topicId: t("caching").id, type: "definition",
        front: "What's the difference between cache-aside and write-through caching?",
        back: "Cache-aside: app reads from cache, on miss reads DB and populates cache. Write-through: every write goes to cache AND DB synchronously. Write-through avoids stale reads but adds write latency.",
        status: "active", dueAt: yesterday,
        ease: 2.4, intervalDays: 2, repetitions: 2,
      },
      {
        userId: "dev-user", topicId: t("caching").id, type: "tradeoff",
        front: "What is the cache stampede problem and how do you mitigate it?",
        back: "When a hot key expires, many requests simultaneously read DB and try to populate the cache, causing a DB spike. Mitigations: probabilistic early expiration, lock-based refresh (only one goroutine refreshes), or background refresh before expiry.",
        status: "active", dueAt: now,
        ease: 2.3, intervalDays: 1, repetitions: 1,
      },
      // Replication
      {
        userId: "dev-user", topicId: t("replication-strategies").id, type: "definition",
        front: "What are the three main replication topologies?",
        back: "Single-leader (one write node, replicas are read-only), multi-leader (multiple write nodes, conflict resolution required), leaderless (any node accepts writes, quorum reads/writes for consistency).",
        status: "active", dueAt: yesterday,
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
