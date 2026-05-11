import { auth } from '@/auth'
import { db } from '@/db/client'
import { users, FREE_FOREVER_EMAIL } from '@/db/schema'
import { eq } from 'drizzle-orm'
import { NextResponse } from 'next/server'
import { redirect } from 'next/navigation'

/**
 * Checks the current session and plan gating for API routes.
 *
 * Returns `{ userId }` on success.
 * Returns a NextResponse with an appropriate error status if the request
 * should be rejected (unauthenticated or trial expired).
 *
 * Usage in an API route:
 *   const result = await apiAuthGuard()
 *   if (result instanceof NextResponse) return result
 *   const { userId } = result
 */
export async function apiAuthGuard(): Promise<{ userId: string } | NextResponse> {
  const session = await auth()
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const userId = session.user.id

  const row = await db
    .select({ plan: users.plan, trialEndsAt: users.trialEndsAt, email: users.email })
    .from(users)
    .where(eq(users.id, userId))
    .limit(1)

  if (row[0]) {
    const { plan, trialEndsAt, email } = row[0]
    if (email !== FREE_FOREVER_EMAIL && plan !== 'paid') {
      if (plan === 'trial' && trialEndsAt && trialEndsAt < new Date()) {
        return NextResponse.json({ error: 'Trial expired', upgradeUrl: '/upgrade' }, { status: 402 })
      }
    }
  }

  return { userId }
}

/**
 * Server-component / server-action guard.
 *
 * Returns `userId` on success.
 * Redirects to `/sign-in` if unauthenticated, or `/upgrade` if trial expired.
 */
export async function requireAuthOrRedirect(): Promise<string> {
  const session = await auth()
  if (!session?.user?.id) {
    redirect('/sign-in')
  }

  const userId = session.user.id

  const row = await db
    .select({ plan: users.plan, trialEndsAt: users.trialEndsAt, email: users.email })
    .from(users)
    .where(eq(users.id, userId))
    .limit(1)

  if (row[0]) {
    const { plan, trialEndsAt, email } = row[0]
    if (email !== FREE_FOREVER_EMAIL && plan !== 'paid') {
      if (plan === 'trial' && trialEndsAt && trialEndsAt < new Date()) {
        redirect('/upgrade')
      }
    }
  }

  return userId
}
