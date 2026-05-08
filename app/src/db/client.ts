import Database from "better-sqlite3";
import { drizzle } from "drizzle-orm/better-sqlite3";
import * as schema from "./schema";
import path from "node:path";

const dbPath = process.env.DATABASE_URL ?? path.join(process.cwd(), "data/study.db");

const sqlite = new Database(dbPath);
sqlite.pragma("journal_mode = WAL");
sqlite.pragma("foreign_keys = ON");
// 10s patience for concurrent writes (multiple generate-topic processes hammering the
// same file). Without this, a contended UPDATE throws SQLITE_BUSY immediately.
sqlite.pragma("busy_timeout = 10000");

export const db = drizzle(sqlite, { schema });
export { schema };
