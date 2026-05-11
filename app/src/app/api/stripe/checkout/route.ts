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

  // Look up or create customer by email
  const existing = await stripe.customers.list({ email, limit: 1 })
  let customerId: string
  if (existing.data.length > 0) {
    customerId = existing.data[0].id
  } else {
    const customer = await stripe.customers.create({ email })
    customerId = customer.id
  }

  const priceId = process.env.STRIPE_PRICE_ID
  if (!priceId) {
    return NextResponse.json({ error: 'STRIPE_PRICE_ID not configured' }, { status: 500 })
  }

  const trialDays = parseInt(process.env.STRIPE_TRIAL_DAYS ?? '7', 10)

  const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'

  const checkoutSession = await stripe.checkout.sessions.create({
    customer: customerId,
    mode: 'subscription',
    line_items: [{ price: priceId, quantity: 1 }],
    subscription_data: {
      trial_period_days: trialDays,
    },
    success_url: `${baseUrl}/dashboard?upgraded=1`,
    cancel_url: `${baseUrl}/upgrade`,
  })

  return NextResponse.json({ url: checkoutSession.url })
}

// Allow GET too for convenience
export async function GET(req: NextRequest) {
  return POST(req)
}
