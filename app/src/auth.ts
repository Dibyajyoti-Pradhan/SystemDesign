import NextAuth from 'next-auth'
import Google from 'next-auth/providers/google'
import Credentials from 'next-auth/providers/credentials'
import { db } from '@/db/client'
import { users, FREE_FOREVER_EMAIL } from '@/db/schema'
import { eq } from 'drizzle-orm'
import logger from '@/lib/logger'
import { track } from '@/lib/analytics'
import { sendWelcomeEmail } from '@/lib/email'

const isDev = process.env.NODE_ENV === 'development'

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID ?? '',
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? '',
    }),
    // Dev-only: sign in with any email + password "dev" — no OAuth needed locally.
    ...(isDev ? [Credentials({
      name: 'Dev Login',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password (type "dev")', type: 'password' },
      },
      async authorize(credentials) {
        if (credentials?.password !== 'dev') return null
        const email = String(credentials.email || 'dev@careerlab.local')
        return { id: `dev-${email}`, email, name: 'Dev User' }
      },
    })] : []),
  ],
  session: { strategy: 'jwt' },
  callbacks: {
    async jwt({ token, user }) {
      if (user?.email) {
        token.email = user.email
        // Upsert user in our DB
        const existing = await db.select({ id: users.id, plan: users.plan })
          .from(users).where(eq(users.email, user.email)).limit(1)
        if (existing.length === 0) {
          const isForeverFree = user.email === FREE_FOREVER_EMAIL
          const newUser = await db.insert(users).values({
            id: crypto.randomUUID(),
            email: user.email,
            name: user.name ?? null,
            image: user.image ?? null,
            plan: isForeverFree ? 'free' : 'trial',
            trialEndsAt: isForeverFree ? null : new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
          }).returning({ id: users.id })
          token.sub = newUser[0]?.id
          logger.info({ email: user.email, userId: newUser[0]?.id, plan: isForeverFree ? 'free' : 'trial' }, 'new user created')
          track('signup', { userId: newUser[0]?.id, email: user.email, plan: isForeverFree ? 'free' : 'trial' })
          if (!isForeverFree) {
            track('trial_start', { userId: newUser[0]?.id, email: user.email })
            sendWelcomeEmail(user.email, user.name ?? user.email).catch(() => { /* fire-and-forget */ })
          }
        } else {
          token.sub = existing[0]?.id
          logger.info({ email: user.email, userId: existing[0]?.id }, 'existing user signed in')
        }
      }
      return token
    },
    async session({ session, token }) {
      if (token.sub) session.user.id = token.sub
      if (token.email) session.user.email = token.email
      return session
    },
  },
  pages: {
    signIn: '/sign-in',
    error: '/sign-in',
  },
})
