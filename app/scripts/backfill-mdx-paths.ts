/**
 * Backfill `topics.mdx_path` from MDX files on disk.
 *
 * Use case: when generate-topic.ts runs in many concurrent processes, the
 * SQLite UPDATE at the end can fail under contention even though the MDX
 * file landed on disk. This script reconciles disk reality with the DB.
 *
 * Walks content/<track>/topics/<category>/<slug>.mdx, finds the matching
 * topics row by slug, and writes the relative path into mdx_path if it's
 * empty. Idempotent.
 *
 * Run via:  npx tsx scripts/backfill-mdx-paths.ts
 */

import fs from "node:fs";
import path from "node:path";
import { db } from "../src/db/client";
import { topics } from "../src/db/schema";
import { eq } from "drizzle-orm";
import { CONTENT_ROOT } from "../src/lib/paths";

interface FoundFile {
  slug: string;
  relPath: string;
}

function findMdxFiles(): FoundFile[] {
  const out: FoundFile[] = [];
  const stack: string[] = [];
  for (const sub of ["system-design", "coding"]) {
    const dir = path.join(CONTENT_ROOT, sub, "topics");
    if (fs.existsSync(dir)) stack.push(dir);
  }
  while (stack.length) {
    const dir = stack.pop()!;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        stack.push(full);
        continue;
      }
      if (!entry.isFile() || !entry.name.toLowerCase().endsWith(".mdx")) continue;
      const slug = entry.name.replace(/\.mdx$/i, "");
      out.push({
        slug,
        relPath: path.relative(CONTENT_ROOT, full),
      });
    }
  }
  return out;
}

async function main() {
  const files = findMdxFiles();
  console.log(`Found ${files.length} MDX files on disk.`);

  let updated = 0;
  let alreadySet = 0;
  let noRow = 0;

  for (const f of files) {
    const [row] = await db.select().from(topics).where(eq(topics.slug, f.slug)).limit(1);
    if (!row) {
      console.warn(`  ! no topic row for slug: ${f.slug}`);
      noRow++;
      continue;
    }
    if (row.mdxPath === f.relPath) {
      alreadySet++;
      continue;
    }
    await db.update(topics).set({ mdxPath: f.relPath }).where(eq(topics.id, row.id));
    updated++;
  }

  console.log(`\n${updated} updated · ${alreadySet} already set · ${noRow} orphan files`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
