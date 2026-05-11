import { auth } from '@/auth'
import { db } from '@/db/client'
import { users, FREE_FOREVER_EMAIL } from '@/db/schema'
import { eq } from 'drizzle-orm'

export async function requireUser(): Promise<string> {
  const session = await auth()
  if (!session?.user?.id) throw new Error('Unauthorized')
  return session.user.id
}

export async function getUserPlan(userId: string): Promise<'free' | 'trial' | 'paid'> {
  const row = await db.select({ plan: users.plan, trialEndsAt: users.trialEndsAt, email: users.email })
    .from(users).where(eq(users.id, userId)).limit(1)
  if (!row[0]) return 'trial'
  if (row[0].email === FREE_FOREVER_EMAIL) return 'free'
  if (row[0].plan === 'trial' && row[0].trialEndsAt && row[0].trialEndsAt < new Date()) return 'free'
  return row[0].plan
}
