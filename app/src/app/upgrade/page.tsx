'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

const FEATURES = [
  'Unlimited practice sessions',
  'AI interviewer with real-time feedback',
  'Voice mode for spoken interviews',
  'Interactive whiteboard',
  'System design & coding tracks',
  'Spaced-repetition flashcard engine',
]

export default function UpgradePage() {
  const router = useRouter()
  const [loading, setLoading] = useState<'checkout' | 'portal' | null>(null)

  async function handleCheckout() {
    setLoading('checkout')
    try {
      const res = await fetch('/api/stripe/checkout', { method: 'POST' })
      const data = await res.json()
      if (data.url) {
        window.location.href = data.url
      }
    } finally {
      setLoading(null)
    }
  }

  async function handlePortal() {
    setLoading('portal')
    try {
      const res = await fetch('/api/stripe/portal', { method: 'POST' })
      const data = await res.json()
      if (data.url) {
        window.location.href = data.url
      }
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 py-16">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            CareerLab Pro
          </h1>
          <p className="mt-2 text-muted-foreground">
            Everything you need to land your next engineering role.
          </p>
        </div>

        {/* Pricing card */}
        <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
          {/* Price block */}
          <div className="bg-primary px-8 py-10 text-center">
            <div className="flex items-end justify-center gap-1">
              <span className="text-5xl font-extrabold text-primary-foreground">£39</span>
              <span className="mb-2 text-primary-foreground/70 text-lg">/month</span>
            </div>
            <p className="mt-2 text-primary-foreground/80 text-sm">
              7-day free trial — cancel anytime
            </p>
          </div>

          {/* Features */}
          <div className="px-8 py-8">
            <ul className="space-y-3">
              {FEATURES.map((feature) => (
                <li key={feature} className="flex items-center gap-3 text-sm text-foreground">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center">
                    <svg
                      className="w-3 h-3 text-primary"
                      viewBox="0 0 12 12"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <polyline points="2 6 5 9 10 3" />
                    </svg>
                  </span>
                  {feature}
                </li>
              ))}
            </ul>

            {/* CTA buttons */}
            <div className="mt-8 space-y-3">
              <button
                onClick={handleCheckout}
                disabled={loading !== null}
                className="w-full rounded-lg bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60 transition-colors"
              >
                {loading === 'checkout' ? 'Redirecting…' : 'Start Free Trial'}
              </button>

              <button
                onClick={handlePortal}
                disabled={loading !== null}
                className="w-full rounded-lg border border-border bg-background px-6 py-3 text-sm font-semibold text-foreground hover:bg-muted disabled:opacity-60 transition-colors"
              >
                {loading === 'portal' ? 'Opening…' : 'Manage Subscription'}
              </button>
            </div>

            <p className="mt-4 text-center text-xs text-muted-foreground">
              Secure payment via Stripe. No card required during trial.
            </p>
          </div>
        </div>

        <button
          onClick={() => router.back()}
          className="mt-6 w-full text-center text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          ← Go back
        </button>
      </div>
    </div>
  )
}
