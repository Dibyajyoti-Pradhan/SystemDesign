import { NextRequest, NextResponse } from 'next/server'
import { getStripe } from '@/lib/stripe'
import { db } from '@/db/client'
import { users } from '@/db/schema'
import { eq } from 'drizzle-orm'
import Stripe from 'stripe'

export async function POST(req: NextRequest) {
  const body = await req.text()
  const sig = req.headers.get('stripe-signature')
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET

  if (!sig || !webhookSecret) {
    return NextResponse.json({ error: 'Missing signature' }, { status: 400 })
  }

  let event: Stripe.Event
  try {
    event = getStripe().webhooks.constructEvent(body, sig, webhookSecret)
  } catch {
    return NextResponse.json({ error: 'Invalid signature' }, { status: 400 })
  }

  if (event.type === 'checkout.session.completed') {
    // In Stripe v22, the data object for checkout.session.completed is Stripe.Checkout.Session
    const session = event.data.object as Stripe.Checkout.Session
    const email = session.customer_details?.email
    if (email) {
      await db
        .update(users)
        .set({ plan: 'paid', trialEndsAt: null })
        .where(eq(users.email, email))
    }
  }

  if (
    event.type === 'customer.subscription.deleted' ||
    event.type === 'invoice.payment_failed'
  ) {
    const obj = event.data.object as { customer?: string | null }
    if (obj.customer) {
      const stripe = getStripe()
      const customer = (await stripe.customers.retrieve(
        obj.customer as string,
      )) as Stripe.Customer
      if (customer.email) {
        await db
          .update(users)
          .set({ plan: 'free' })
          .where(eq(users.email, customer.email))
      }
    }
  }

  return NextResponse.json({ received: true })
}
