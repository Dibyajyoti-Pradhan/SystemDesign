import posthog from 'posthog-js'

let initialised = false

export function initAnalytics() {
  if (initialised || typeof window === 'undefined') return
  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY
  if (!key) return
  posthog.init(key, { api_host: 'https://eu.posthog.com', capture_pageview: false })
  initialised = true
}

export function track(event: string, props?: Record<string, unknown>) {
  if (!initialised) return
  posthog.capture(event, props)
}
