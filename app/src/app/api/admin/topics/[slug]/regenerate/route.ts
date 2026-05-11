import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import { db } from "@/db/client";
import { topics, FREE_FOREVER_EMAIL } from "@/db/schema";
import { auth } from "@/auth";
import { eq } from "drizzle-orm";
import { claudeRun } from "@/lib/anthropic";
import { REPO_ROOT, CONTENT_ROOT, TRACK_PATHS } from "@/lib/paths";
import { slugify } from "@/lib/utils";
import { extractSourceText } from "@/lib/sourceExtract";

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

export async function POST(
  _req: NextRequest,
  ctx: { params: Promise<{ slug: string }> },
) {
  const session = await auth();
  if (!session?.user || session.user.email !== FREE_FOREVER_EMAIL) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const { slug } = await ctx.params;

  const [topic] = await db.select().from(topics).where(eq(topics.slug, slug)).limit(1);
  if (!topic) {
    return NextResponse.json({ error: "Topic not found" }, { status: 404 });
  }

  if (!topic.pdfPath) {
    return NextResponse.json({ error: "Topic has no source PDF" }, { status: 400 });
  }

  const sourceAbs = path.join(REPO_ROOT, topic.pdfPath);
  const pdfText = await extractSourceText(sourceAbs);

  await db.update(topics).set({ generationStatus: "pending" }).where(eq(topics.id, topic.id));

  const SYSTEM_PROMPT = loadPrompt("topic-generate.txt", "You are an expert system-design educator. Write an MDX study guide for this topic.");

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
    console.error("[admin/topics/regenerate] claude error", err);
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
    await db.update(topics).set({ generationStatus: "error" }).where(eq(topics.id, topic.id));
    return NextResponse.json({ error: "Empty output from Claude" }, { status: 502 });
  }

  const categorySlug = slugify(topic.category);
  const outDir = path.join(TRACK_PATHS[topic.track].topicsContent, categorySlug);
  await fs.mkdir(outDir, { recursive: true });
  const outPath = path.join(outDir, `${topic.slug}.mdx`);
  await fs.writeFile(outPath, cleaned, "utf8");

  const relPath = path.relative(CONTENT_ROOT, outPath);
  const newVersion = (topic.version ?? 0) + 1;

  await db.update(topics).set({
    mdxPath: relPath,
    generationStatus: "done",
    generatedAt: new Date(),
    version: newVersion,
  }).where(eq(topics.id, topic.id));

  return NextResponse.json({ status: "ok", version: newVersion });
}
