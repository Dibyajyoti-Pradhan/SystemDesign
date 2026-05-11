import NextAuth from 'next-auth'
import Google from 'next-auth/providers/google'
import { db } from '@/db/client'
import { users, FREE_FOREVER_EMAIL } from '@/db/schema'
import { eq } from 'drizzle-orm'
import logger from '@/lib/logger'

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID ?? '',
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? '',
    }),
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
