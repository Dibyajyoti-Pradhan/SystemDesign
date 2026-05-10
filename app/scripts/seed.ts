import fs from "node:fs";
import path from "node:path";
import { db } from "../src/db/client";
import { topics, questions, type NewTopic, TRACKS, type Track } from "../src/db/schema";
import { slugify } from "../src/lib/utils";
import { REPO_ROOT, TRACK_PATHS } from "../src/lib/paths";

function readDir(p: string): string[] {
  if (!fs.existsSync(p)) return [];
  return fs.readdirSync(p).sort();
}

function parseCategoryFolder(name: string): { order: number; category: string } | null {
  const m = name.match(/^(\d+)\s*-\s*(.+)$/);
  if (!m) return null;
  return { order: parseInt(m[1], 10), category: m[2].trim() };
}

function parseTopicFile(name: string): { order: number; title: string; ext: string } | null {
  const m = name.match(/^(\d+)\s*-\s*(.+?)\.(pdf|docx|md)$/i);
  if (!m) return null;
  return { order: parseInt(m[1], 10), title: m[2].trim(), ext: m[3].toLowerCase() };
}

function parseQuestionFile(name: string): { number: number; title: string; ext: string } | null {
  const m = name.match(/^(\d+)\s*-\s*(.+?)\.(pdf|docx|md)$/i);
  if (!m) return null;
  return { number: parseInt(m[1], 10), title: m[2].trim(), ext: m[3].toLowerCase() };
}

async function seedTopicsForTrack(track: Track) {
  const root = TRACK_PATHS[track].studyGuideSources;
  const categories = readDir(root);
  const rows: NewTopic[] = [];

  for (const catName of categories) {
    const catDir = path.join(root, catName);
    if (!fs.statSync(catDir).isDirectory()) continue;
    const cat = parseCategoryFolder(catName);
    if (!cat) continue;

    const files = readDir(catDir).filter((f) => /\.(pdf|docx|md)$/i.test(f));
    for (const file of files) {
      const t = parseTopicFile(file);
      if (!t) continue;
      const slug = slugify(`${cat.category}-${t.title}`);
      rows.push({
        userId: "system", // TODO: replace with real user id when auth is wired
        track,
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

  let inserted = 0;
  for (const r of rows) {
    try {
      const result = await db.insert(topics).values(r).onConflictDoNothing().returning({ id: topics.id });
      if (result.length > 0) inserted++;
    } catch (e) {
      console.error(`[${track}] topic insert failed`, r.slug, e);
    }
  }
  console.log(`[${track}] seeded ${inserted}/${rows.length} topics across ${new Set(rows.map((r) => r.category)).size} categories.`);
}

interface AuthoredQuestion {
  number: number;
  title: string;
  difficulty?: "easy" | "medium" | "hard";
  tags?: string[];
}

async function seedQuestionsForTrack(track: Track) {
  const root = TRACK_PATHS[track].questionsSources;
  if (!fs.existsSync(root)) {
    console.log(`[${track}] no questions source dir (${root}); skipping.`);
    return;
  }

  if (track === "coding") {
    // Coding questions are hand-authored title lists in JSON, one file per
    // language: `coding/interview-questions/<lang>.json`. We don't generate
    // briefs for these — the title IS the question (per user direction).
    const files = readDir(root).filter((f) => f.toLowerCase().endsWith(".json"));
    let total = 0;
    for (const file of files) {
      const lang = file.replace(/\.json$/i, "");
      let raw: AuthoredQuestion[];
      try {
        raw = JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));
      } catch (e) {
        console.error(`[coding] failed to parse ${file}:`, e);
        continue;
      }
      let inserted = 0;
      for (const q of raw) {
        if (!q?.title || typeof q.number !== "number") continue;
        const slug = slugify(`${lang}-${String(q.number).padStart(2, "0")}-${q.title}`);
        try {
          const result = await db
            .insert(questions)
            .values({
              userId: "system", // TODO: replace with real user id when auth is wired
              track,
              language: lang,
              slug,
              number: q.number,
              title: q.title,
              difficulty: q.difficulty ?? "medium",
              tags: JSON.stringify(q.tags ?? []),
            })
            .onConflictDoNothing()
            .returning({ id: questions.id });
          if (result.length > 0) inserted++;
        } catch (e) {
          console.error(`[coding/${lang}] question insert failed`, slug, e);
        }
      }
      console.log(`[coding/${lang}] seeded ${inserted}/${raw.length} questions.`);
      total += inserted;
    }
    if (files.length === 0) console.log(`[coding] no language JSON files found.`);
    return;
  }

  // system-design: PDF-backed questions (existing behaviour)
  const files = readDir(root).filter((f) => /\.(pdf|docx|md)$/i.test(f));
  let inserted = 0;
  for (const file of files) {
    const q = parseQuestionFile(file);
    if (!q) continue;
    const slug = slugify(`${String(q.number).padStart(2, "0")}-${q.title}`);
    try {
      const result = await db
        .insert(questions)
        .values({
          userId: "system", // TODO: replace with real user id when auth is wired
          track,
          slug,
          number: q.number,
          title: q.title,
          difficulty: "medium",
          tags: "[]",
          pdfPath: path.relative(REPO_ROOT, path.join(root, file)),
        })
        .onConflictDoNothing()
        .returning({ id: questions.id });
      if (result.length > 0) inserted++;
    } catch (e) {
      console.error(`[${track}] question insert failed`, slug, e);
    }
  }
  console.log(`[${track}] seeded ${inserted}/${files.length} questions.`);
}

async function main() {
  for (const track of TRACKS) {
    await seedTopicsForTrack(track);
    await seedQuestionsForTrack(track);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
