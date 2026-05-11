import type { Metadata } from "next";
import "./globals.css";
import { SessionProvider } from "next-auth/react";
import { Sidebar } from "@/components/Sidebar";
import { AssistantPanel } from "@/components/AssistantPanel";
import { auth } from "@/auth";
import { checkGate } from "@/lib/gate";
import { redirect } from "next/navigation";
import { headers } from "next/headers";

export const metadata: Metadata = {
  title: "CareerLab — AI System Design Interview Prep",
  description: "AI voice interviewer + live whiteboard + real-time feedback. Built for SWEs targeting Google, Meta, and Amazon.",
};

const UNPROTECTED_PATHS = ["/upgrade", "/sign-in", "/sign-up", "/"];
const LANDING_PATH = "/";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();

  let pathname = "";
  try {
    const headersList = await headers();
    pathname = headersList.get("x-pathname") ?? "";
  } catch {
    // headers not available
  }

  const isLanding = pathname === LANDING_PATH;

  // Gate check — fail open on any error so the layout never crashes
  if (!isLanding) {
    try {
      const isUnprotected = UNPROTECTED_PATHS.some(
        (p) => pathname === p || pathname.startsWith(p + "/"),
      );

      if (!isUnprotected) {
        const gate = await checkGate();
        if (gate === "expired") {
          redirect("/upgrade");
        }
      }
    } catch {
      // Auth or DB not ready — fail open
    }
  }

  if (isLanding) {
    return (
      <SessionProvider session={session}>
        <html lang="en" className="scroll-smooth">
          <body className="antialiased bg-zinc-950 text-zinc-100">
            {children}
          </body>
        </html>
      </SessionProvider>
    );
  }

  return (
    <SessionProvider session={session}>
      <html lang="en">
        <body className="antialiased">
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 min-w-0">{children}</main>
          </div>
          <AssistantPanel />
        </body>
      </html>
    </SessionProvider>
  );
}
