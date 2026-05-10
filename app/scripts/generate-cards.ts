import { db } from "../src/db/client";
import { cards, topics } from "../src/db/schema";
import { eq } from "drizzle-orm";
import { claudeRun } from "../src/lib/anthropic";
import { readTopicMdx } from "../src/lib/mdx";

const SYSTEM_PROMPT = `You are an expert system-design educator generating spaced-repetition flashcards for a senior engineer preparing for FAANG-level interviews.

Generate high-quality flashcards. Each card must be one of four types:

1. **definition** — front: "What is X?" or "Define X". back: tight 2-4 sentence definition with the *key property* that distinguishes it.
2. **tradeoff** — front: a question about a design choice ("When would you pick X over Y?" or "What's the cost of using X?"). back: enumerate 2-3 concrete tradeoffs with numbers/examples.
3. **scenario** — front: a small system-design scenario ("Your service is seeing P99 latency spike to 2s under 10K QPS. The DB is at 30% CPU. What's the most likely cause?"). back: the answer with the reasoning chain.
4. **comparison** — front: "X vs Y for <use case>". back: 2-4 bullet differences with when to use each.

Quality bar:
- Must be answerable from a senior engineer's working memory in <30 seconds.
- No fluff or filler. Every word must earn its place.
- Use concrete numbers when relevant (P99 < 100ms, 1M QPS, 10GB/day).
- Don't repeat what's literally in the front on the back.
- Mix types: roughly 30% definition, 30% tradeoff, 20% scenario, 20% comparison.

Optionally include a Mermaid diagram on the **back** of cards where a picture helps. Use \`flowchart\`, \`sequenceDiagram\`, or \`stateDiagram-v2\`. Keep diagrams small (<8 nodes). Only ~25% of cards should have a diagram. Omit the diagram_mermaid field entirely when not useful.`;

const CARDS_SCHEMA = {
  type: "object",
  properties: {
    cards: {
      type: "array",
      items: {
        type: "object",
        properties: {
          type: { type: "string", enum: ["definition", "tradeoff", "scenario", "comparison"] },
          front: { type: "string" },
          back: { type: "string" },
          diagram_mermaid: { type: "string" },
        },
        required: ["type", "front", "back"],
        additionalProperties: false,
      },
    },
  },
  required: ["cards"],
  additionalProperties: false,
} as const;

interface GeneratedCard {
  type: "definition" | "tradeoff" | "scenario" | "comparison";
  front: string;
  back: string;
  diagram_mermaid?: string;
}

function parseArgs(): { slug?: string; n: number; all: boolean } {
  const args = process.argv.slice(2);
  let n = 15;
  let all = false;
  let slug: string | undefined;
  for (const a of args) {
    if (a === "--all") all = true;
    else if (a.startsWith("--n=")) n = Number(a.slice(4)) || 15;
    else if (!a.startsWith("--")) slug = a;
  }
  return { slug, n, all };
}

async function generateForTopic(slug: string, n: number) {
  const [topic] = await db.select().from(topics).where(eq(topics.slug, slug)).limit(1);
  if (!topic) {
    console.error(`No topic with slug "${slug}"`);
    return { ok: false as const };
  }
  if (!topic.mdxPath) {
    console.error(`Topic "${slug}" has no MDX yet — run generate-topic first.`);
    return { ok: false as const };
  }

  const parsed = await readTopicMdx(topic.mdxPath);
  if (!parsed) {
    console.error(`Failed to read MDX for "${slug}".`);
    return { ok: false as const };
  }

  const sourceContent = `# ${topic.title}\n\n${parsed.body}`.slice(0, 24000);

  console.log(`[${slug}] calling Claude Code...`);
  const userPrompt = `Topic: ${topic.title}
Category: ${topic.category}
Slug: ${topic.slug}

Source content (MDX):

${sourceContent}

Generate ${n} flashcards now. Return them as { "cards": [...] } per the schema.`;

  const rawText = await claudeRun({
    systemPrompt: SYSTEM_PROMPT,
    prompt: userPrompt,
    jsonSchema: CARDS_SCHEMA,
    model: "sonnet",
  });

  let parsedCards: GeneratedCard[];
  try {
    const obj = JSON.parse(rawText);
    if (!Array.isArray(obj?.cards)) throw new Error("missing 'cards' array");
    parsedCards = obj.cards as GeneratedCard[];
  } catch (e: any) {
    console.error(`[${slug}] JSON parse failed:`, e.message);
    console.error("Raw output:\n", rawText.slice(0, 500));
    return { ok: false as const };
  }

  const valid = parsedCards.filter(
    (c) =>
      c &&
      typeof c.front === "string" &&
      typeof c.back === "string" &&
      ["definition", "tradeoff", "scenario", "comparison"].includes(c.type),
  );

  if (valid.length === 0) {
    console.error(`[${slug}] no valid cards after validation.`);
    return { ok: false as const };
  }

  const inserted = await db
    .insert(cards)
    .values(
      valid.map((c) => ({
        userId: "system", // TODO: replace with real user id when auth is wired
        topicId: topic.id,
        type: c.type,
        front: c.front.trim(),
        back: c.back.trim(),
        diagramMermaid:
          typeof c.diagram_mermaid === "string" && c.diagram_mermaid.trim()
            ? c.diagram_mermaid.trim()
            : null,
        status: "pending_review" as const,
        generatedByModel: "claude-code:sonnet",
      })),
    )
    .returning({ id: cards.id });

  console.log(`[${slug}] inserted ${inserted.length} pending cards.`);
  return { ok: true as const, count: inserted.length };
}

(async () => {
  const { slug, n, all } = parseArgs();

  if (!slug && !all) {
    console.error("Usage:");
    console.error("  npm run generate-cards -- <topic-slug> [--n=15]");
    console.error("  npm run generate-cards -- --all [--n=15]");
    console.error("");
    console.error("Note the '--' separator. npm needs it to pass flags through.");
    process.exit(1);
  }

  if (all) {
    const allTopics = await db.select().from(topics);
    const todo = allTopics.filter((t) => t.mdxPath);
    console.log(`Generating cards for ${todo.length} topics with MDX...`);
    let totalInserted = 0;
    for (const t of todo) {
      try {
        const res = await generateForTopic(t.slug, n);
        if (res.ok) totalInserted += res.count;
      } catch (e: any) {
        console.error(`Failed for ${t.slug}:`, e.message);
      }
    }
    console.log(`\nDone. ${totalInserted} cards inserted across ${todo.length} topics.`);
    return;
  }

  if (slug) {
    const res = await generateForTopic(slug, n);
    if (!res.ok) process.exit(1);
  }
})();
