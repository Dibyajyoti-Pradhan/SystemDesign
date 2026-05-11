/**
 * Seed script for local SQLite dev database.
 * Run: DATABASE_URL=sqlite:./local.db npx tsx scripts/seed-local.ts
 */
import { db } from "../src/db/client";
import { topics, questions, cards } from "../src/db/schema";
import { eq } from "drizzle-orm";

async function main() {
  console.log("Seeding local SQLite database...");

  // Check if already seeded
  const existing = db.select().from(topics).all();
  if (existing.length > 0) {
    console.log(`Already seeded (${existing.length} topics found). Skipping.`);
    return;
  }

  // Insert 2 topics
  const insertedTopics = db
    .insert(topics)
    .values([
      {
        userId: "dev-user",
        track: "system-design",
        slug: "consistent-hashing",
        category: "Core Concepts",
        categoryOrder: 1,
        topicOrder: 1,
        title: "Consistent Hashing",
        summary:
          "Consistent hashing is a distributed hashing scheme that operates independently of the number of servers or objects in a distributed hash table. It allows nodes to be added or removed with minimal reorganization of the key space.",
        mastery: 72,
        generationStatus: "done",
      },
      {
        userId: "dev-user",
        track: "system-design",
        slug: "cap-theorem",
        category: "Core Concepts",
        categoryOrder: 1,
        topicOrder: 2,
        title: "CAP Theorem",
        summary:
          "The CAP theorem states that a distributed system can only guarantee two of the three properties: Consistency, Availability, and Partition tolerance. Understanding the trade-offs is essential for designing distributed databases.",
        mastery: 60,
        generationStatus: "done",
      },
    ])
    .returning()
    .all();

  console.log(`Inserted ${insertedTopics.length} topics.`);

  // Insert 1 question
  const insertedQuestions = db
    .insert(questions)
    .values([
      {
        userId: "dev-user",
        track: "system-design",
        slug: "design-url-shortener",
        number: 1,
        title: "Design a URL shortener at scale",
        difficulty: "medium",
        tags: JSON.stringify(["hashing", "databases", "caching"]),
        estMinutes: 30,
      },
    ])
    .returning()
    .all();

  console.log(`Inserted ${insertedQuestions.length} questions.`);

  // Insert 3 cards for first topic
  const firstTopic = insertedTopics[0];
  const now = new Date();

  const insertedCards = db
    .insert(cards)
    .values([
      {
        userId: "dev-user",
        topicId: firstTopic.id,
        type: "definition",
        front: "What is consistent hashing?",
        back: "A hashing technique where the hash space is arranged in a ring. When a node is added or removed, only keys between that node and its predecessor need to be remapped, minimizing data movement.",
        status: "active",
        dueAt: now,
      },
      {
        userId: "dev-user",
        topicId: firstTopic.id,
        type: "tradeoff",
        front: "What are the trade-offs of consistent hashing?",
        back: "Pros: Minimal key remapping on node changes, good load distribution with virtual nodes. Cons: Non-uniform distribution without virtual nodes, added complexity in implementation and debugging.",
        status: "active",
        dueAt: now,
      },
      {
        userId: "dev-user",
        topicId: firstTopic.id,
        type: "scenario",
        front: "When would you use consistent hashing in a system design?",
        back: "Use consistent hashing for distributed caches (e.g., Memcached, Redis Cluster), distributed databases that need horizontal scaling, load balancers that require session affinity, and CDN edge servers.",
        status: "active",
        dueAt: now,
      },
    ])
    .returning()
    .all();

  console.log(`Inserted ${insertedCards.length} cards.`);
  console.log("Done seeding.");
}

main().catch((err) => {
  console.error("Seed failed:", err);
  process.exit(1);
});
