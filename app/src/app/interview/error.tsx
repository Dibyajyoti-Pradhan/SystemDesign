'use client'

import Link from 'next/link'

export default function InterviewError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4">
      <div className="text-center space-y-4 max-w-md">
        <h2 className="text-2xl font-bold tracking-tight">Interview error</h2>
        <p className="text-muted-foreground text-sm">
          {error.message || 'Something went wrong loading this interview. Please try again.'}
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={reset}
            className="inline-flex items-center justify-center rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Try again
          </button>
          <Link
            href="/interview"
            className="inline-flex items-center justify-center rounded-md border border-border px-5 py-2.5 text-sm font-semibold hover:bg-muted transition-colors"
          >
            Back to interviews
          </Link>
        </div>
      </div>
    </div>
  )
}
