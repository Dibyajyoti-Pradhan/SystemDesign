export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const { init } = await import('@sentry/nextjs')
    const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN
    if (dsn) init({ dsn, tracesSampleRate: 0.1 })

    // Unified dev log: mirror server-side console output to app/dev.log so
    // every server error (SQLite, route handlers, SSR) ends up in the same
    // file as client logs. Dev only.
    if (process.env.NODE_ENV !== 'production') {
      const fs = await import('node:fs');
      const path = await import('node:path');
      const LOG_PATH = path.join(process.cwd(), 'dev.log');
      const fmt = (level: string, args: unknown[]) => {
        const parts = args.map((a) => {
          if (a instanceof Error) return a.stack ?? a.message;
          if (typeof a === 'string') return a;
          try { return JSON.stringify(a); } catch { return String(a); }
        });
        return JSON.stringify({ ts: new Date().toISOString(), source: 'server', level, message: parts.join(' ') }) + '\n';
      };
      const write = (s: string) => { try { fs.appendFileSync(LOG_PATH, s); } catch {} };
      const origLog = console.log.bind(console);
      const origWarn = console.warn.bind(console);
      const origErr = console.error.bind(console);
      console.log = (...a: unknown[]) => { write(fmt('info', a)); origLog(...a); };
      console.warn = (...a: unknown[]) => { write(fmt('warn', a)); origWarn(...a); };
      console.error = (...a: unknown[]) => { write(fmt('error', a)); origErr(...a); };
      // Catch uncaught
      process.on('uncaughtException', (e) => { write(fmt('error', ['uncaughtException', e])); });
      process.on('unhandledRejection', (e) => { write(fmt('error', ['unhandledRejection', e])); });
    }
  }
}
