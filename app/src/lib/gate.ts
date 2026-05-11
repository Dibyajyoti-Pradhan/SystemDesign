import { auth } from '@/auth'
import { db } from '@/db/client'
import { users, FREE_FOREVER_EMAIL } from '@/db/schema'
import { eq } from 'drizzle-orm'

export async function checkGate(): Promise<'ok' | 'expired' | 'unauthenticated'> {
  try {
    const session = await auth()
    if (!session?.user?.id) return 'unauthenticated'

    const userId = session.user.id
    const row = await db
      .select({ plan: users.plan, trialEndsAt: users.trialEndsAt, email: users.email })
      .from(users)
      .where(eq(users.id, userId))
      .limit(1)

    if (!row[0]) return 'ok' // new user, give benefit of doubt
    if (row[0].email === FREE_FOREVER_EMAIL) return 'ok'
    if (row[0].plan === 'paid') return 'ok'
    if (row[0].plan === 'trial' && row[0].trialEndsAt && row[0].trialEndsAt > new Date()) return 'ok'
    return 'expired'
  } catch {
    return 'ok' // fail open — never block on auth errors
  }
}
