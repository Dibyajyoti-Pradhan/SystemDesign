import * as schema from "./schema";

const url = process.env.DATABASE_URL ?? "";
const isSqlite = !url || url.startsWith("sqlite:") || url === "FILL_FROM_NEON";

function makeSqliteDb() {
  const path = url.startsWith("sqlite:") ? url.slice("sqlite:".length) : "./local.db";
  const Database = require("better-sqlite3");
  const { drizzle } = require("drizzle-orm/better-sqlite3");
  const sqlite = new Database(path);
  sqlite.pragma("journal_mode = WAL");
  sqlite.pragma("synchronous = NORMAL");
  // Wait up to 5s for a held lock before throwing SQLITE_BUSY (which surfaces
  // as "disk I/O error" through better-sqlite3 in some cases).
  sqlite.pragma("busy_timeout = 5000");
  sqlite.pragma("foreign_keys = ON");
  return drizzle(sqlite, { schema });
}

function makePgDb() {
  const { Pool } = require("pg");
  const { drizzle } = require("drizzle-orm/node-postgres");
  const pool = new Pool({ connectionString: url });
  return drizzle(pool, { schema });
}

export const db = isSqlite ? makeSqliteDb() : makePgDb();
export { schema };
