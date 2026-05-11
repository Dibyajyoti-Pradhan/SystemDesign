'use client'
import { signOut } from 'next-auth/react'

export function SignOutButton() {
  return (
    <button
      onClick={() => signOut({ callbackUrl: '/sign-in' })}
      className="text-xs text-muted-foreground hover:text-foreground px-2 py-1"
    >
      Sign out
    </button>
  )
}
