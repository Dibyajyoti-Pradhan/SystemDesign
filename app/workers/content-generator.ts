/**
 * BullMQ worker for async content generation.
 *
 * Run standalone (outside Next.js) with:
 *   npx tsx workers/content-generator.ts
 *
 * Gracefully exits with a log message if Redis is not configured.
 */

import "dotenv/config";
import path from "node:path";
import fs from "node:fs/promises";
import fsSync from "node:fs";

// ---------------------------------------------------------------------------
// Guard — exit early if Redis not configured
// ---------------------------------------------------------------------------
if (!process.env.UPSTASH_REDIS_URL || !process.env.UPSTASH_REDIS_TOKEN) {
  console.log(
    "[content-generator] UPSTASH_REDIS_URL / UPSTASH_REDIS_TOKEN not set — worker running in no-op mode (exiting).",
  );
  process.exit(0);
}

import { Worker, type Job } from "bullmq";
import { eq } from "drizzle-orm";
import { db, schema } from "../src/db/client";
import type { ContentJobData } from "../src/lib/queue";

// ---------------------------------------------------------------------------
// Helpers shared with generate route (copy-free — replicate the same logic)
// ---------------------------------------------------------------------------
const REPO_ROOT = path.resolve(process.cwd(), "..");
const CONTENT_ROOT = path.join(REPO_ROOT, "content");

async function extractSourceText(absPath: string): Promise<string> {
  const ext = path.extname(absPath).toLowerCase();
  try {
    if (ext === ".pdf") {
      const buf = await fs.readFile(absPath);
      const pdfParse = (await import("pdf-parse")).default;
      const data = await pdfParse(buf);
      return data.text ?? "";
    }
    if (ext === ".docx") {
      const buf = await fs.readFile(absPath);
      const mammoth = await import("mammoth");
      const result = await mammoth.extractRawText({ buffer: buf });
      return result.value ?? "";
    }
    if (ext === ".md" || ext === ".mdx" || ext === ".txt") {
      return await fs.readFile(absPath, "utf8");
    }
  } catch (err) {
    console.error(`[content-generator] extractSourceText failed for ${absPath}:`, err);
  }
  return "";
}

function slugify(str: string): string {
  return str
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function loadPrompt(name: string, fallback: string): string {
  try {
    return fsSync.readFileSync(path.join(process.cwd(), "../prompts", name), "utf8");
  } catch {
    return fallback;
  }
}

const TOPIC_SYSTEM_PROMPT = loadPrompt(
  "topic-generate.txt",
  `You are an expert system-design educator writing study material for a senior engineer preparing for FAANG-level interviews.

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

A 2-4 sentence summary. Then ONE small Mermaid diagram showing the core concept.

\`\`\`mermaid
<diagram>
\`\`\`

<!-- standard -->

A 5-min read. ≤450 words of prose.

<!-- deep -->

A 15-min read with concrete algorithms, real-world systems, failure modes, capacity numbers, and interview pitfalls.

Rules:
- Mermaid diagrams must be valid. Prefer flowchart, sequenceDiagram, or stateDiagram-v2.
- Output ONLY the MDX. No commentary before or after.`,
);

// ---------------------------------------------------------------------------
// Anthropic client
// ---------------------------------------------------------------------------
async function callClaude(systemPrompt: string, userPrompt: string): Promise<string> {
  const Anthropic = (await import("@anthropic-ai/sdk")).default;
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  const response = await client.messages.create({
    model: "claude-sonnet-4-6",
    max_tokens: 8192,
    system: systemPrompt,
    messages: [{ role: "user", content: userPrompt }],
  });
  return response.content
    .filter((b) => b.type === "text")
    .map((b) => (b as { type: "text"; text: string }).text)
    .join("");
}

// ---------------------------------------------------------------------------
// Per-track paths (mirrors src/lib/paths.ts without importing Next.js)
// ---------------------------------------------------------------------------
const TRACK_TOPICS_CONTENT: Record<string, string> = {
  "system-design": path.join(CONTENT_ROOT, "system-design/topics"),
  coding: path.join(CONTENT_ROOT, "coding/topics"),
};

// ---------------------------------------------------------------------------
// Job processors
// ---------------------------------------------------------------------------
async function processTopic(slug: string, userId: string): Promise<void> {
  const [topic] = await db
    .select()
    .from(schema.topics)
    .where(eq(schema.topics.slug, slug))
    .limit(1);

  if (!topic) throw new Error(`Topic not found: ${slug}`);
  if (topic.mdxPath) {
    console.log(`[content-generator] topic ${slug} already has MDX — skipping`);
    return;
  }
  if (!topic.pdfPath) throw new Error(`Topic ${slug} has no pdfPath`);

  await db
    .update(schema.topics)
    .set({ generationStatus: "pending" })
    .where(eq(schema.topics.id, topic.id));

  const sourceAbs = path.join(REPO_ROOT, topic.pdfPath);
  const pdfText = await extractSourceText(sourceAbs);

  const mdx = await callClaude(
    TOPIC_SYSTEM_PROMPT,
    `Topic: ${topic.title}
Category: ${topic.category}
Slug: ${topic.slug}

Source material extracted from PDF:

${pdfText.slice(0, 20000) || "(PDF extraction failed — write from your own knowledge of the topic.)"}

Generate the MDX now.`,
  );

  const cleaned = mdx
    .replace(/^```(?:mdx|md)?\n?/, "")
    .replace(/\n?```\s*$/, "")
    .trim();

  if (!cleaned) throw new Error("Empty output from Claude");

  const categorySlug = slugify(topic.category);
  const topicsContentDir = TRACK_TOPICS_CONTENT[topic.track] ?? TRACK_TOPICS_CONTENT["system-design"];
  const outDir = path.join(topicsContentDir, categorySlug);
  await fs.mkdir(outDir, { recursive: true });
  const outPath = path.join(outDir, `${topic.slug}.mdx`);
  await fs.writeFile(outPath, cleaned, "utf8");

  const relPath = path.relative(CONTENT_ROOT, outPath);
  await db
    .update(schema.topics)
    .set({
      mdxPath: relPath,
      generationStatus: "done",
      generatedAt: new Date(),
      version: (topic.version ?? 0) + 1,
    })
    .where(eq(schema.topics.id, topic.id));

  console.log(`[content-generator] topic ${slug} generated → ${relPath}`);
}

async function processCards(slug: string, userId: string): Promise<void> {
  // Placeholder — card generation can be wired up when the cards generate
  // endpoint is moved to async. For now, log and succeed.
  console.log(`[content-generator] cards job for ${slug} received (not yet implemented)`);
}

// ---------------------------------------------------------------------------
// Connection config (mirrors src/lib/queue.ts)
// ---------------------------------------------------------------------------
function buildConnection() {
  const url = process.env.UPSTASH_REDIS_URL!;
  const token = process.env.UPSTASH_REDIS_TOKEN!;
  const parsed = new URL(url);
  return {
    host: parsed.hostname,
    port: parsed.port ? parseInt(parsed.port, 10) : 6380,
    password: token,
    tls: { rejectUnauthorized: false },
    maxRetriesPerRequest: null,
  };
}

// ---------------------------------------------------------------------------
// Worker
// ---------------------------------------------------------------------------
const worker = new Worker<ContentJobData>(
  "careerlab-content",
  async (job: Job<ContentJobData>) => {
    const { type, slug, userId } = job.data;
    console.log(`[content-generator] processing job ${job.id} — ${type}:${slug}`);

    if (type === "topic") {
      await processTopic(slug, userId);
    } else if (type === "cards") {
      await processCards(slug, userId);
    } else {
      throw new Error(`Unknown job type: ${type}`);
    }
  },
  {
    connection: buildConnection(),
    concurrency: 2,
  },
);

worker.on("completed", (job) => {
  console.log(`[content-generator] job ${job.id} completed`);
});

worker.on("failed", (job, err) => {
  console.error(`[content-generator] job ${job?.id} failed:`, err.message);
});

console.log("[content-generator] worker started, waiting for jobs...");
