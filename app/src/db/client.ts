import * as schema from "./schema";

const url = process.env.DATABASE_URL ?? "";
const isSqlite = !url || url.startsWith("sqlite:") || url === "FILL_FROM_NEON";

// Cache the underlying better-sqlite3 handle so we can reopen it when
// SQLITE_IOERR strikes (the better-sqlite3 connection occasionally enters a
// poisoned state in dev where every subsequent op throws, even though the file
// on disk is fine — direct `sqlite3 local.db` queries succeed).
let underlying: { sqlite: unknown; drizzleDb: unknown; path: string } | null = null;

function openSqlite() {
  const path = url.startsWith("sqlite:") ? url.slice("sqlite:".length) : "./local.db";
  const Database = require("better-sqlite3");
  const { drizzle } = require("drizzle-orm/better-sqlite3");
  const sqlite = new Database(path);
  sqlite.pragma("busy_timeout = 15000");
  // Dev: stick to DELETE rollback journal. WAL's mmap'd shared memory has
  // been failing intermittently with SQLITE_IOERR on this machine; DELETE
  // mode is simpler and has been rock-solid.
  sqlite.pragma("journal_mode = DELETE");
  sqlite.pragma("synchronous = NORMAL");
  sqlite.pragma("foreign_keys = ON");

  // Wrap prepare so EVERY statement is resilient. If a prepare/run/all/get/
  // values call throws SQLITE_IOERR*, we close the handle and reopen, then
  // re-prepare and retry once. After that we surface the error so the caller
  // can decide.
  const origPrepare = sqlite.prepare.bind(sqlite);
  sqlite.prepare = function patchedPrepare(sql: string) {
    let stmt: any;
    try {
      stmt = origPrepare(sql);
    } catch (err) {
      if (isTransientIoErr(err)) {
        reopenInPlace();
        stmt = origPrepare(sql);
      } else {
        throw err;
      }
    }
    return wrapStatement(stmt, sql);
  };

  const drizzleDb = drizzle(sqlite, { schema });
  underlying = { sqlite, drizzleDb, path };
  return drizzleDb;
}

function isTransientIoErr(err: unknown): boolean {
  const code = (err as { code?: string } | null)?.code ?? "";
  return (
    code.startsWith("SQLITE_IOERR") ||
    code === "SQLITE_BUSY" ||
    code === "SQLITE_LOCKED" ||
    code === "SQLITE_CORRUPT"
  );
}

function reopenInPlace() {
  if (!underlying) return;
  const path = underlying.path;
  try { (underlying.sqlite as { close: () => void }).close(); } catch { /* ignore */ }
  const Database = require("better-sqlite3");
  const sqlite = new Database(path);
  sqlite.pragma("busy_timeout = 15000");
  // Dev: stick to DELETE rollback journal. WAL's mmap'd shared memory has
  // been failing intermittently with SQLITE_IOERR on this machine; DELETE
  // mode is simpler and has been rock-solid.
  sqlite.pragma("journal_mode = DELETE");
  sqlite.pragma("synchronous = NORMAL");
  sqlite.pragma("foreign_keys = ON");
  try { sqlite.pragma("wal_checkpoint(TRUNCATE)"); } catch { /* ignore */ }
  // Replace the underlying sqlite reference. We DON'T rebuild drizzleDb because
  // drizzle holds onto the original sqlite via closures; instead we patch the
  // prepare function on the new sqlite and replace it on the original ref.
  const origPrepare = sqlite.prepare.bind(sqlite);
  sqlite.prepare = function patchedPrepare(sql: string) {
    let stmt: any;
    try {
      stmt = origPrepare(sql);
    } catch (err) {
      if (isTransientIoErr(err)) {
        reopenInPlace();
        const inner = (underlying!.sqlite as { prepare: (s: string) => any });
        stmt = inner.prepare(sql);
      } else {
        throw err;
      }
    }
    return wrapStatement(stmt, sql);
  };
  // Mutate the existing references so all consumers see the new connection.
  Object.assign(underlying.sqlite as object, sqlite);
  underlying.sqlite = sqlite;
}

function wrapStatement(stmt: any, sql: string): any {
  const wrapCall = (method: "run" | "all" | "get" | "values") => {
    const orig = stmt[method]?.bind(stmt);
    if (!orig) return undefined;
    return (...args: unknown[]) => {
      try {
        return orig(...args);
      } catch (err) {
        if (!isTransientIoErr(err)) throw err;
        reopenInPlace();
        const inner = (underlying!.sqlite as { prepare: (s: string) => any });
        const fresh = inner.prepare(sql);
        return fresh[method](...args);
      }
    };
  };
  // Drizzle uses .run/.all/.get/.values internally. Wrap them all.
  stmt.run = wrapCall("run");
  stmt.all = wrapCall("all");
  stmt.get = wrapCall("get");
  stmt.values = wrapCall("values");
  return stmt;
}

function makeSqliteDb() {
  return openSqlite();
}

function makePgDb() {
  const { Pool } = require("pg");
  const { drizzle } = require("drizzle-orm/node-postgres");
  const pool = new Pool({ connectionString: url });
  return drizzle(pool, { schema });
}

// Singleton across Next.js dev hot-reloads. Without this, every route-handler
// edit produces a fresh DB connection and the old ones leak file descriptors,
// which on a near-full disk starts surfacing as SQLITE_IOERR_WRITE on the next
// write. In prod this just acts like a normal module-level singleton.
const globalForDb = globalThis as unknown as {
  __sd_db?: ReturnType<typeof makeSqliteDb> | ReturnType<typeof makePgDb>;
};

export const db =
  globalForDb.__sd_db ??
  (globalForDb.__sd_db = isSqlite ? makeSqliteDb() : makePgDb());
export { schema };
