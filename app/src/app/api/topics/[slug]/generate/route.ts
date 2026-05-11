import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import { db } from "@/db/client";
import { topics } from "@/db/schema";
import { requireUser } from "@/lib/auth";
import { eq } from "drizzle-orm";
import { claudeRun } from "@/lib/anthropic";
import { REPO_ROOT, CONTENT_ROOT, TRACK_PATHS } from "@/lib/paths";
import { slugify } from "@/lib/utils";
import { extractSourceText } from "@/lib/sourceExtract";
import { enqueueContentJob } from "@/lib/queue";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

function loadPrompt(name: string, fallback: string): string {
  try {
    return fsSync.readFileSync(path.join(process.cwd(), "../prompts", name), "utf8");
  } catch {
    return fallback;
  }
}

const SYSTEM_PROMPT_FALLBACK = `You are an expert system-design educator writing study material for a senior engineer preparing for FAANG-level interviews.

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

const SYSTEM_PROMPT = loadPrompt("topic-generate.txt", SYSTEM_PROMPT_FALLBACK);

export async function POST(_req: NextRequest, ctx: { params: Promise<{ slug: string }> }) {
  let userId: string;
  try {
    userId = await requireUser();
  } catch {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { slug } = await ctx.params;

  const [topic] = await db.select().from(topics).where(eq(topics.slug, slug)).limit(1);
  if (!topic) {
    return NextResponse.json({ error: "Topic not found" }, { status: 404 });
  }

  // If MDX already exists, do nothing — caller can refresh to see it.
  if (topic.mdxPath) {
    return NextResponse.json({ ok: true, mdxPath: topic.mdxPath, alreadyExists: true });
  }

  if (!topic.pdfPath) {
    return NextResponse.json({ error: "Topic has no source PDF" }, { status: 400 });
  }

  // ---------------------------------------------------------------------------
  // Attempt to enqueue the job asynchronously via BullMQ.
  // Falls back to inline execution when Redis is not configured (dev / CI).
  // ---------------------------------------------------------------------------
  const jobId = await enqueueContentJob("topic", slug, userId);

  if (jobId !== null) {
    // Job successfully queued — return immediately so the HTTP request doesn't
    // hang for the 2-4 minutes Claude takes.
    await db.update(topics).set({ generationStatus: "pending" }).where(eq(topics.id, topic.id));
    return NextResponse.json({ ok: true, queued: true, jobId });
  }

  // ---------------------------------------------------------------------------
  // Fallback: inline generation (no Redis configured)
  // ---------------------------------------------------------------------------
  const sourceAbs = path.join(REPO_ROOT, topic.pdfPath);
  const pdfText = await extractSourceText(sourceAbs);

  await db.update(topics).set({ generationStatus: "pending" }).where(eq(topics.id, topic.id));

  let mdx = "";
  try {
    mdx = await claudeRun({
      systemPrompt: SYSTEM_PROMPT,
      prompt: `Topic: ${topic.title}
Category: ${topic.category}
Slug: ${topic.slug}

Source material extracted from PDF:

${pdfText.slice(0, 20000) || "(PDF extraction failed — write from your own knowledge of the topic.)"}

Generate the MDX now.`,
      model: "sonnet",
      timeoutMs: 240_000,
    });
  } catch (err) {
    console.error("[topics/generate] claude error", err);
    await db.update(topics).set({ generationStatus: "error" }).where(eq(topics.id, topic.id));
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Generation failed" },
      { status: 502 },
    );
  }

  const cleaned = mdx
    .replace(/^```(?:mdx|md)?\n?/, "")
    .replace(/\n?```\s*$/, "")
    .trim();

  if (!cleaned) {
    return NextResponse.json({ error: "Empty output from Claude" }, { status: 502 });
  }

  const categorySlug = slugify(topic.category);
  const outDir = path.join(TRACK_PATHS[topic.track].topicsContent, categorySlug);
  await fs.mkdir(outDir, { recursive: true });
  const outPath = path.join(outDir, `${topic.slug}.mdx`);
  await fs.writeFile(outPath, cleaned, "utf8");

  const relPath = path.relative(CONTENT_ROOT, outPath);
  await db.update(topics).set({
    mdxPath: relPath,
    generationStatus: "done",
    generatedAt: new Date(),
    version: (topic.version ?? 0) + 1,
  }).where(eq(topics.id, topic.id));

  return NextResponse.json({ ok: true, mdxPath: relPath, version: (topic.version ?? 0) + 1 });
}
