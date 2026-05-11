import { auth } from '@/auth'
import { NextResponse } from 'next/server'

const publicPaths = ['/', '/sign-in', '/sign-up', '/api/auth', '/api/stripe/webhook']

function isPublic(pathname: string): boolean {
  return publicPaths.some((p) => pathname === p || pathname.startsWith(p + '/') || pathname.startsWith(p + '?'))
}

export default auth((req) => {
  const { pathname } = req.nextUrl
  if (!req.auth && !isPublic(pathname)) {
    const signInUrl = new URL('/sign-in', req.url)
    signInUrl.searchParams.set('callbackUrl', req.url)
    return NextResponse.redirect(signInUrl)
  }
  return NextResponse.next()
})

export const config = {
  matcher: ['/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)', '/(api|trpc)(.*)'],
}
