export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const { init } = await import('@sentry/nextjs')
    const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN
    if (dsn) init({ dsn, tracesSampleRate: 0.1 })
  }
}
