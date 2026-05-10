/**
 * Seed Coding/Java topics from coding/JavaSheet.md.
 *
 * The JavaSheet is the canonical master index — 13 sections, ~140 topics.
 * Most are interview-prep concepts the user wants generatable from Claude's
 * own knowledge (no source PDF). A handful have backing PDFs in
 * coding/study-guide/<section>/. This script:
 *
 *   1. Parses the sheet's sections and table rows.
 *   2. Maps existing PDFs (by filename → title) to corresponding topics.
 *   3. Upserts coding topics by SLUG. New rows get inserted; existing rows
 *      get their category, topicOrder, and pdfPath refreshed (so the
 *      JavaSheet remains the source of truth for category names and order).
 *   4. Existing MDX files are preserved — they stay attached to whichever
 *      slug they were generated under.
 *
 * Run via:  npm run seed:java
 */

import fs from "node:fs";
import path from "node:path";
import { db } from "../src/db/client";
import { topics } from "../src/db/schema";
import { eq } from "drizzle-orm";
import { REPO_ROOT } from "../src/lib/paths";
import { slugify } from "../src/lib/utils";

const SHEET_PATH = path.join(REPO_ROOT, "coding/JavaSheet.md");
const PDF_ROOT = path.join(REPO_ROOT, "coding/study-guide");

interface ParsedTopic {
  sectionNum: number;
  sectionTitle: string;
  number: string; // e.g. "1.05"
  title: string;
  rawCell: string;
}

/** Trim "Topic — descriptor" → "Topic" so titles stay short and stable. */
function normalizeTitle(raw: string): string {
  // Strip a trailing parenthetical hint if present.
  const noParens = raw.replace(/\s*\([^)]+\)\s*$/, "");
  // The em-dash separator: "JDK vs JRE vs JVM — roles" → "JDK vs JRE vs JVM"
  const emDash = noParens.split(/\s+—\s+/)[0];
  return emDash.trim();
}

/** Extract topic title (and link target if present) from a markdown cell. */
function parseCell(cell: string): { title: string; rawCell: string } {
  const linkMatch = cell.match(/^\[([^\]]+)\]\(([^)]+)\)\s*$/);
  if (linkMatch) {
    return { title: linkMatch[1].trim(), rawCell: cell };
  }
  return { title: cell.trim(), rawCell: cell };
}

function parseSheet(text: string): ParsedTopic[] {
  const out: ParsedTopic[] = [];
  let sectionNum = 0;
  let sectionTitle = "";

  for (const line of text.split("\n")) {
    const sectionMatch = line.match(/^##\s+Section\s+(\d+)\s+—\s+(.+)$/);
    if (sectionMatch) {
      sectionNum = parseInt(sectionMatch[1], 10);
      sectionTitle = sectionMatch[2].trim();
      continue;
    }

    // Topic row: | 1.05 | Cell content | - [ ] |
    const rowMatch = line.match(/^\|\s*(\d+\.\d+)\s*\|\s*(.+?)\s*\|\s*[-\s]*\[[\sx]\]\s*\|\s*$/);
    if (rowMatch && sectionTitle) {
      const number = rowMatch[1];
      const cellRaw = rowMatch[2];
      const { title, rawCell } = parseCell(cellRaw);
      out.push({
        sectionNum,
        sectionTitle,
        number,
        title: normalizeTitle(title),
        rawCell,
      });
    }
  }
  return out;
}

/**
 * Walk coding/study-guide/ and produce a map from "title slug" → relative
 * path. We use slug-based matching so spaces, dashes, etc. don't trip us up.
 */
function indexExistingPdfs(): Map<string, string> {
  const map = new Map<string, string>();
  if (!fs.existsSync(PDF_ROOT)) return map;
  const stack = [PDF_ROOT];
  while (stack.length) {
    const dir = stack.pop()!;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        stack.push(full);
      } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".pdf")) {
        // Strip leading "NN - " ordering prefix and ".pdf"
        const stem = entry.name.replace(/^\d+\s*-\s*/, "").replace(/\.pdf$/i, "");
        const titleSlug = slugify(stem);
        map.set(titleSlug, path.relative(REPO_ROOT, full));
      }
    }
  }
  return map;
}

async function main() {
  const sheetText = fs.readFileSync(SHEET_PATH, "utf8");
  const parsed = parseSheet(sheetText);
  const pdfIndex = indexExistingPdfs();

  console.log(`Parsed ${parsed.length} topics from JavaSheet across ${new Set(parsed.map((t) => t.sectionNum)).size} sections.`);
  console.log(`Indexed ${pdfIndex.size} PDFs in coding/study-guide/.`);

  let inserted = 0;
  let updated = 0;
  let pdfMatched = 0;
  let unchanged = 0;

  for (const topic of parsed) {
    const slug = slugify(`${topic.sectionTitle}-${topic.title}`);
    const titleSlug = slugify(topic.title);
    const pdfPath = pdfIndex.get(titleSlug) ?? null;
    if (pdfPath) pdfMatched++;

    const [section, ord] = topic.number.split(".").map((n) => parseInt(n, 10));

    const [existing] = await db.select().from(topics).where(eq(topics.slug, slug)).limit(1);

    if (existing) {
      // Refresh metadata (preserve mdxPath, mastery, lastVisitedAt)
      const needs =
        existing.category !== topic.sectionTitle ||
        existing.categoryOrder !== section ||
        existing.topicOrder !== ord ||
        existing.title !== topic.title ||
        (pdfPath && existing.pdfPath !== pdfPath);

      if (needs) {
        await db
          .update(topics)
          .set({
            track: "coding",
            language: "java",
            category: topic.sectionTitle,
            categoryOrder: section,
            topicOrder: ord,
            title: topic.title,
            ...(pdfPath ? { pdfPath } : {}),
          })
          .where(eq(topics.id, existing.id));
        updated++;
      } else {
        unchanged++;
      }
    } else {
      try {
        await db.insert(topics).values({
          userId: "system", // TODO: replace with real user id when auth is wired
          track: "coding",
          language: "java",
          slug,
          category: topic.sectionTitle,
          categoryOrder: section,
          topicOrder: ord,
          title: topic.title,
          pdfPath,
        });
        inserted++;
      } catch (e) {
        console.error(`failed to insert ${slug}:`, (e as Error).message);
      }
    }
  }

  console.log(`Done. ${inserted} inserted · ${updated} updated · ${unchanged} unchanged · ${pdfMatched} PDF matches`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
