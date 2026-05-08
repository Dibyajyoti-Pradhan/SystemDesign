import fs from "node:fs/promises";
import path from "node:path";
import { db } from "../src/db/client";
import { topics } from "../src/db/schema";
import { eq } from "drizzle-orm";
import { claudeRun } from "../src/lib/claude-cli";
import { REPO_ROOT, CONTENT_ROOT, TRACK_PATHS } from "../src/lib/paths";
import { slugify } from "../src/lib/utils";

import { extractSourceText } from "../src/lib/sourceExtract";

const SYSTEM_PROMPT = `You are an expert system-design educator writing study material for a senior engineer preparing for FAANG-level interviews.

Output an MDX document with three depth levels and at least one Mermaid diagram. Follow this exact structure:

---
title: <exact topic title>
slug: <slug>
category: <category>
tldr: <one sentence ≤25 words>
related: [<topic slug>, <topic slug>]
---

<!-- tldr -->
# <Topic>

A 2-4 sentence summary that gives a senior engineer the gist. Then ONE small Mermaid diagram showing the core concept.

\`\`\`mermaid
<diagram>
\`\`\`

<!-- standard -->

A 5-min read covering: what it is, why it matters, primary techniques, key tradeoffs. Use bullet lists, a comparison table where useful, and a second Mermaid diagram if it adds clarity. ≤450 words of prose.

<!-- deep -->

A 15-min read with: concrete algorithms / formulas, real-world systems that use this (Cassandra, DynamoDB, Kafka, etc.), failure modes, capacity / latency numbers, interview pitfalls, and a "when to reach for this" decision rubric. Include another Mermaid diagram for an architecture or sequence flow. Use h2/h3 headings.

Rules:
- Mermaid diagrams must be valid and self-contained. Prefer flowchart, sequenceDiagram, or stateDiagram-v2.
- No fluff sentences ("In today's world..."). Get straight to the substance.
- Use real numbers when relevant (P99 < 100ms, 1M QPS, 100GB/day, etc.).
- Write for someone who already knows what a server is.
- Output ONLY the MDX. No commentary before or after.`;

async function generateForSlug(slug: string) {
  const [topic] = await db.select().from(topics).where(eq(topics.slug, slug)).limit(1);
  if (!topic) {
    console.error(`No topic with slug "${slug}"`);
    process.exit(1);
  }
  if (!topic.pdfPath) {
    console.error(`Topic "${slug}" has no PDF source`);
    process.exit(1);
  }

  const sourceAbs = path.join(REPO_ROOT, topic.pdfPath);
  console.log(`[${slug}] extracting text from ${path.basename(sourceAbs)}...`);
  const pdfText = await extractSourceText(sourceAbs);

  console.log(`[${slug}] calling Claude Code...`);
  const userPrompt = `Topic: ${topic.title}
Category: ${topic.category}
Slug: ${topic.slug}

Source material extracted from PDF:

${pdfText.slice(0, 20000) || "(PDF extraction failed — write from your own knowledge of the topic.)"}

Generate the MDX now.`;

  const text = await claudeRun({
    systemPrompt: SYSTEM_PROMPT,
    prompt: userPrompt,
    model: "sonnet",
  });

  const cleaned = text
    .replace(/^```(?:mdx|md)?\n?/, "")
    .replace(/\n?```\s*$/, "")
    .trim();

  const categorySlug = slugify(topic.category);
  const outDir = path.join(TRACK_PATHS[topic.track].topicsContent, categorySlug);
  await fs.mkdir(outDir, { recursive: true });
  const outPath = path.join(outDir, `${topic.slug}.mdx`);
  await fs.writeFile(outPath, cleaned, "utf8");

  const relPath = path.relative(CONTENT_ROOT, outPath);
  await db.update(topics).set({ mdxPath: relPath }).where(eq(topics.id, topic.id));

  console.log(`[${slug}] ✓ wrote ${outPath}`);
}

const arg = process.argv[2];
if (!arg) {
  console.error("Usage: npm run generate-topic -- <slug>");
  console.error("       npm run generate-topic -- --all-missing");
  console.error("");
  console.error("Note the '--' separator. npm needs it to pass flags through to the script.");
  process.exit(1);
}

(async () => {
  if (arg === "--all-missing") {
    const all = await db.select().from(topics);
    const todo = all.filter((t) => !t.mdxPath && t.pdfPath);
    console.log(`${todo.length} topics need MDX generation.`);
    for (const t of todo) {
      try {
        await generateForSlug(t.slug);
      } catch (e: any) {
        console.error(`Failed for ${t.slug}:`, e.message);
      }
    }
  } else {
    await generateForSlug(arg);
  }
})();
