import fs from "node:fs";
import path from "node:path";

const LOG_PATH = path.join(process.cwd(), "dev.log");
const MAX_BYTES = 5 * 1024 * 1024; // 5MB rolling
const ENABLED = process.env.NODE_ENV !== "production";

type Entry = {
  source: "server" | "client";
  level?: "info" | "warn" | "error";
  method?: string;
  url?: string;
  status?: number;
  durationMs?: number;
  message?: string;
  stack?: string;
  meta?: unknown;
};

function rotateIfNeeded() {
  try {
    const stat = fs.statSync(LOG_PATH);
    if (stat.size > MAX_BYTES) {
      fs.renameSync(LOG_PATH, LOG_PATH + ".prev");
    }
  } catch {}
}

export function devlog(entry: Entry) {
  if (!ENABLED) return;
  const line = JSON.stringify({ ts: new Date().toISOString(), level: entry.level ?? "info", ...entry });
  try {
    rotateIfNeeded();
    fs.appendFileSync(LOG_PATH, line + "\n");
  } catch {}
  // Mirror to stdout/stderr so it also shows in the next dev terminal.
  if (entry.level === "error") console.error(line);
  else if (entry.level === "warn") console.warn(line);
  else console.log(line);
}

/**
 * Wrap a Next.js API route handler. Logs method+url+status+duration on success
 * and method+url+error on throw.
 *
 * Usage:
 *   export const POST = withDevLog(async (req, ctx) => { ... });
 */
export function withDevLog<H extends (...args: any[]) => Promise<Response>>(handler: H): H {
  return (async (...args: any[]) => {
    const req = args[0] as Request;
    const start = Date.now();
    const method = req?.method ?? "?";
    const url = (() => {
      try { return new URL(req.url).pathname + new URL(req.url).search; } catch { return req?.url ?? "?"; }
    })();
    try {
      const res = await handler(...args);
      devlog({ source: "server", level: res.status >= 500 ? "error" : res.status >= 400 ? "warn" : "info", method, url, status: res.status, durationMs: Date.now() - start });
      return res;
    } catch (e: any) {
      devlog({ source: "server", level: "error", method, url, durationMs: Date.now() - start, message: e?.message ?? String(e), stack: e?.stack });
      throw e;
    }
  }) as H;
}
