import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs/promises";
import path from "node:path";
import { db } from "@/db/client";
import { topics } from "@/db/schema";
import { eq } from "drizzle-orm";
import { claudeRun } from "@/lib/claude-cli";
import { REPO_ROOT, TOPICS_CONTENT } from "@/lib/paths";
import { slugify } from "@/lib/utils";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

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

async function extractPdfText(absPath: string): Promise<string> {
  const buf = await fs.readFile(absPath);
  const pdfParse = (await import("pdf-parse")).default;
  const data = await pdfParse(buf);
  return data.text;
}

export async function POST(_req: NextRequest, ctx: { params: Promise<{ slug: string }> }) {
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

  const pdfAbs = path.join(REPO_ROOT, topic.pdfPath);
  let pdfText = "";
  try {
    pdfText = await extractPdfText(pdfAbs);
  } catch (err) {
    console.error("[topics/generate] PDF extraction failed", err);
  }

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
  const outDir = path.join(TOPICS_CONTENT, categorySlug);
  await fs.mkdir(outDir, { recursive: true });
  const outPath = path.join(outDir, `${topic.slug}.mdx`);
  await fs.writeFile(outPath, cleaned, "utf8");

  const relPath = path.relative(path.join(REPO_ROOT, "content"), outPath);
  await db.update(topics).set({ mdxPath: relPath }).where(eq(topics.id, topic.id));

  return NextResponse.json({ ok: true, mdxPath: relPath });
}
