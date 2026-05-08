import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs/promises";
import path from "node:path";
import { db } from "@/db/client";
import { questions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { claudeRun } from "@/lib/claude-cli";
import { REPO_ROOT, CONTENT_ROOT, TRACK_PATHS } from "@/lib/paths";
import { extractSourceText } from "@/lib/sourceExtract";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 180;

const SYSTEM_PROMPT = `You are summarizing a system-design interview question for a candidate who is about to attempt it.

Output an MDX document with:
- Problem statement (1-2 sentences)
- Functional requirements (3-5 bullets)
- Non-functional / scale targets (DAU, QPS, latency, storage if applicable)
- What's out of scope

# CRITICAL — never reveal the solution
The source PDF likely contains the FULL reference solution (architecture, technologies, partitioning, etc.). DO NOT include any of that. Your output must contain ONLY the question — what to design and the constraints. The candidate should think the design through themselves.

# Format
---
title: <question title>
slug: <slug>
---

# Problem
<1-2 sentences stating what the candidate must design>

## Functional requirements
- <bullet>
- <bullet>
- <bullet>

## Scale & non-functional
- DAU: <number>
- QPS (peak): <number>
- Latency target: <p99 number>
- Storage growth: <number>
- Availability: <SLA>

## Out of scope
- <bullet>
- <bullet>

Keep it tight, ~150 words. No prose padding. Use real numbers when present in the source. If a section doesn't apply, omit it.

Output ONLY the MDX. No commentary before or after.`;

export async function POST(_req: NextRequest, ctx: { params: Promise<{ slug: string }> }) {
  const { slug } = await ctx.params;

  const [q] = await db.select().from(questions).where(eq(questions.slug, slug)).limit(1);
  if (!q) return NextResponse.json({ error: "Question not found" }, { status: 404 });
  if (q.mdxPath) {
    return NextResponse.json({ ok: true, mdxPath: q.mdxPath, alreadyExists: true });
  }
  if (!q.pdfPath) {
    return NextResponse.json({ error: "No source PDF" }, { status: 400 });
  }

  const pdfText = await extractSourceText(path.join(REPO_ROOT, q.pdfPath));

  let mdx = "";
  try {
    mdx = await claudeRun({
      systemPrompt: SYSTEM_PROMPT,
      prompt: `Question: ${q.title}
Slug: ${q.slug}
Difficulty: ${q.difficulty}

Source material extracted from PDF (likely contains the solution — IGNORE the solution part):

${pdfText.slice(0, 18000) || "(PDF extraction failed — write the brief from your own knowledge of this question.)"}

Produce the MDX brief now. Remember: question only, never the solution.`,
      model: "sonnet",
      timeoutMs: 120_000,
    });
  } catch (err) {
    console.error("[questions/generate-brief] claude error", err);
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
    return NextResponse.json({ error: "Empty output" }, { status: 502 });
  }

  const outDir = TRACK_PATHS[q.track].questionsContent;
  await fs.mkdir(outDir, { recursive: true });
  const outPath = path.join(outDir, `${q.slug}.mdx`);
  await fs.writeFile(outPath, cleaned, "utf8");

  const relPath = path.relative(CONTENT_ROOT, outPath);
  await db.update(questions).set({ mdxPath: relPath }).where(eq(questions.id, q.id));

  return NextResponse.json({ ok: true, mdxPath: relPath });
}
