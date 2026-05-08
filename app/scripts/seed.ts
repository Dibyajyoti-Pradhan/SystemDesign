import fs from "node:fs";
import path from "node:path";
import { db } from "../src/db/client";
import { topics, questions, type NewTopic } from "../src/db/schema";
import { slugify } from "../src/lib/utils";
import { REPO_ROOT, STUDY_GUIDE_PDFS, DESIGN_QUESTIONS_PDFS } from "../src/lib/paths";

function readDir(p: string): string[] {
  if (!fs.existsSync(p)) return [];
  return fs.readdirSync(p).sort();
}

function parseCategoryFolder(name: string): { order: number; category: string } | null {
  const m = name.match(/^(\d+)\s*-\s*(.+)$/);
  if (!m) return null;
  return { order: parseInt(m[1], 10), category: m[2].trim() };
}

function parseTopicFile(name: string): { order: number; title: string } | null {
  const m = name.match(/^(\d+)\s*-\s*(.+?)\.pdf$/i);
  if (!m) return null;
  return { order: parseInt(m[1], 10), title: m[2].trim() };
}

function parseQuestionFile(name: string): { number: number; title: string } | null {
  const m = name.match(/^(\d+)\s*-\s*(.+?)\.pdf$/i);
  if (!m) return null;
  return { number: parseInt(m[1], 10), title: m[2].trim() };
}

async function seedTopics() {
  const categories = readDir(STUDY_GUIDE_PDFS);
  const rows: NewTopic[] = [];
  for (const catName of categories) {
    const catDir = path.join(STUDY_GUIDE_PDFS, catName);
    if (!fs.statSync(catDir).isDirectory()) continue;
    const cat = parseCategoryFolder(catName);
    if (!cat) continue;

    const files = readDir(catDir).filter((f) => f.toLowerCase().endsWith(".pdf"));
    for (const file of files) {
      const t = parseTopicFile(file);
      if (!t) continue;
      const slug = slugify(`${cat.category}-${t.title}`);
      rows.push({
        slug,
        category: cat.category,
        categoryOrder: cat.order,
        topicOrder: t.order,
        title: t.title,
        summary: "",
        pdfPath: path.relative(REPO_ROOT, path.join(catDir, file)),
      });
    }
  }
  if (rows.length === 0) {
    console.log("No topic PDFs found.");
    return;
  }
  for (const r of rows) {
    try {
      await db.insert(topics).values(r).onConflictDoNothing();
    } catch (e) {
      console.error("topic insert failed", r.slug, e);
    }
  }
  console.log(`Seeded ${rows.length} topics across ${new Set(rows.map((r) => r.category)).size} categories.`);
}

async function seedQuestions() {
  const files = readDir(DESIGN_QUESTIONS_PDFS).filter((f) => f.toLowerCase().endsWith(".pdf"));
  let n = 0;
  for (const file of files) {
    const q = parseQuestionFile(file);
    if (!q) continue;
    const slug = slugify(`${String(q.number).padStart(2, "0")}-${q.title}`);
    try {
      await db
        .insert(questions)
        .values({
          slug,
          number: q.number,
          title: q.title,
          difficulty: "medium",
          tags: "[]",
          pdfPath: path.relative(REPO_ROOT, path.join(DESIGN_QUESTIONS_PDFS, file)),
        })
        .onConflictDoNothing();
      n++;
    } catch (e) {
      console.error("question insert failed", slug, e);
    }
  }
  console.log(`Seeded ${n} design questions.`);
}

async function main() {
  await seedTopics();
  await seedQuestions();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
