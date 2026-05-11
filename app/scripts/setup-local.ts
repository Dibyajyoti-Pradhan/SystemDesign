/**
 * Local dev setup — runs automatically before `npm run dev` (predev hook).
 * Safe to run multiple times: skips each step if already done.
 *
 * Steps:
 *   1. Ensure .env.local exists with SQLite + empty ANTHROPIC_API_KEY
 *   2. Push DB schema (drizzle-kit push)
 *   3. Seed initial data if the DB is empty
 */
import { execSync } from "child_process";
import fs from "fs";
import path from "path";

const ROOT = path.resolve(__dirname, "..");

function log(msg: string) {
  process.stdout.write(`[setup] ${msg}\n`);
}

// ── 1. .env.local ────────────────────────────────────────────────────────────
const envPath = path.join(ROOT, ".env.local");
if (!fs.existsSync(envPath)) {
  log(".env.local not found — creating with SQLite defaults");
  fs.writeFileSync(
    envPath,
    [
      "# Auth — stripped for local dev",
      "NEXTAUTH_SECRET=local-dev-secret-change-in-production",
      "NEXTAUTH_URL=http://localhost:3000",
      "",
      "# Database — SQLite for local dev",
      "DATABASE_URL=sqlite:./local.db",
      "",
      "# Anthropic — leave EMPTY so the claude CLI fallback is used",
      "ANTHROPIC_API_KEY=",
      "",
      "# Dev mode",
      "NODE_ENV=development",
      "",
    ].join("\n")
  );
} else {
  log(".env.local already exists — skipping");
}

// ── 2. DB schema push ────────────────────────────────────────────────────────
// Check if the topics table exists as a proxy for whether schema was pushed
const dbPath = path.join(ROOT, "local.db");
let needsPush = !fs.existsSync(dbPath);

if (!needsPush) {
  try {
    const Database = require("better-sqlite3");
    const db = new Database(dbPath);
    const tables = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='topics'")
      .all();
    needsPush = tables.length === 0;
    db.close();
  } catch {
    needsPush = true;
  }
}

if (needsPush) {
  log("Pushing DB schema via drizzle-kit...");
  execSync("npx drizzle-kit push", {
    cwd: ROOT,
    stdio: "inherit",
    env: { ...process.env, DATABASE_URL: "sqlite:./local.db" },
  });
} else {
  log("DB schema already up-to-date — skipping push");
}

// ── 3. Seed ──────────────────────────────────────────────────────────────────
try {
  const Database = require("better-sqlite3");
  const db = new Database(dbPath);
  const rows = db.prepare("SELECT COUNT(*) as n FROM topics").get() as { n: number };
  db.close();

  if (rows.n === 0) {
    log("DB is empty — seeding local data...");
    execSync("npx tsx scripts/seed-local.ts", {
      cwd: ROOT,
      stdio: "inherit",
      env: { ...process.env, DATABASE_URL: "sqlite:./local.db" },
    });
  } else {
    log(`DB already has data (${rows.n} topics) — skipping seed`);
  }
} catch (e) {
  log("Seed check failed, attempting seed anyway...");
  execSync("npx tsx scripts/seed-local.ts", {
    cwd: ROOT,
    stdio: "inherit",
    env: { ...process.env, DATABASE_URL: "sqlite:./local.db" },
  });
}

log("Setup complete. Starting dev server...");
