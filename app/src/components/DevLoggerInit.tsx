"use client";

import { useEffect } from "react";

/**
 * Dev-only client-side instrumentation. Installs:
 *  - fetch wrapper that logs every request + response (method/url/status/ms)
 *  - window.onerror and unhandledrejection handlers
 *  - a console.error proxy
 *
 * All logs are batched and POSTed to /api/log, which writes to app/dev.log
 * alongside server logs. One unified file to share.
 */
export function DevLoggerInit() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const w = window as any;
    if (w.__devLoggerInstalled) return;
    w.__devLoggerInstalled = true;

    const queue: any[] = [];
    let flushTimer: any = null;
    const flush = () => {
      if (queue.length === 0) return;
      const batch = queue.splice(0, queue.length);
      // Best-effort; ignore failures so we don't loop on /api/log errors.
      fetch("/api/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(batch),
        keepalive: true,
      }).catch(() => {});
    };
    const schedule = () => {
      if (flushTimer) return;
      flushTimer = setTimeout(() => { flushTimer = null; flush(); }, 250);
    };
    const push = (entry: any) => {
      queue.push(entry);
      // Hard cap to avoid runaway in error loops
      if (queue.length > 100) queue.splice(0, queue.length - 100);
      schedule();
    };

    // ── fetch wrapper ─────────────────────────────────────────────────
    const origFetch = window.fetch.bind(window);
    window.fetch = async (input: any, init?: any) => {
      const start = Date.now();
      const url = typeof input === "string" ? input : input?.url ?? "?";
      const method = (init?.method ?? (typeof input === "object" ? input?.method : "GET") ?? "GET").toUpperCase();
      // Skip our own log endpoint to avoid loops
      if (typeof url === "string" && url.includes("/api/log")) {
        return origFetch(input, init);
      }
      try {
        const res = await origFetch(input, init);
        push({
          level: res.status >= 500 ? "error" : res.status >= 400 ? "warn" : "info",
          method, url, status: res.status, durationMs: Date.now() - start,
        });
        return res;
      } catch (e: any) {
        push({
          level: "error", method, url, durationMs: Date.now() - start,
          message: e?.message ?? String(e), stack: e?.stack,
        });
        throw e;
      }
    };

    // ── unhandled error handlers ──────────────────────────────────────
    const onErr = (ev: ErrorEvent) => {
      push({ level: "error", url: location.pathname + location.search, message: ev.message, stack: ev.error?.stack, meta: { filename: ev.filename, lineno: ev.lineno, colno: ev.colno } });
    };
    const onRej = (ev: PromiseRejectionEvent) => {
      const reason: any = ev.reason;
      push({ level: "error", url: location.pathname + location.search, message: "unhandledrejection: " + (reason?.message ?? String(reason)), stack: reason?.stack });
    };
    window.addEventListener("error", onErr);
    window.addEventListener("unhandledrejection", onRej);

    // ── console.error proxy ───────────────────────────────────────────
    const origConsoleError = console.error.bind(console);
    console.error = (...args: any[]) => {
      try {
        push({ level: "error", url: location.pathname + location.search, message: args.map((a) => (a instanceof Error ? a.message : typeof a === "string" ? a : safeStringify(a))).join(" "), stack: args.find((a) => a instanceof Error)?.stack });
      } catch {}
      origConsoleError(...args);
    };

    // Flush on page hide
    window.addEventListener("pagehide", flush);
    window.addEventListener("beforeunload", flush);

    push({ level: "info", url: location.pathname + location.search, message: "page loaded" });
  }, []);

  return null;
}

function safeStringify(v: any): string {
  try { return JSON.stringify(v); } catch { return String(v); }
}
