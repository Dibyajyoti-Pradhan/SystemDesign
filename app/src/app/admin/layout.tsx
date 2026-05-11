import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { FREE_FOREVER_EMAIL } from "@/db/schema";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user) redirect("/sign-in");
  if (session.user.email !== FREE_FOREVER_EMAIL) redirect("/");

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center gap-6">
          <span className="font-semibold text-sm">CareerLab Admin</span>
          <nav className="flex items-center gap-4 text-sm text-muted-foreground">
            <Link href="/admin" className="hover:text-foreground">
              Dashboard
            </Link>
            <Link href="/admin/cards" className="hover:text-foreground">
              Cards
            </Link>
          </nav>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
