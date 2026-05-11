import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/auth'
import { getStripe } from '@/lib/stripe'
import { db } from '@/db/client'
import { users } from '@/db/schema'
import { eq } from 'drizzle-orm'

export async function POST(_req: NextRequest) {
  const session = await auth()
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const row = await db
    .select({ email: users.email })
    .from(users)
    .where(eq(users.id, session.user.id))
    .limit(1)

  const email = row[0]?.email
  if (!email) {
    return NextResponse.json({ error: 'User not found' }, { status: 404 })
  }

  const stripe = getStripe()

  const existing = await stripe.customers.list({ email, limit: 1 })
  if (existing.data.length === 0) {
    return NextResponse.json({ error: 'No Stripe customer found' }, { status: 404 })
  }

  const customerId = existing.data[0].id
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'

  const portalSession = await stripe.billingPortal.sessions.create({
    customer: customerId,
    return_url: `${baseUrl}/upgrade`,
  })

  return NextResponse.json({ url: portalSession.url })
}
