"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Library, BookOpen, Sparkles, Layers } from "lucide-react";
import { SignOutButton } from "@/components/SignOutButton";
import { TRACKS, TRACK_LABELS, type Track } from "@/lib/tracks";
import { cn } from "@/lib/utils";

const NAV: Array<{ slug: "topics" | "questions" | "review" | "cheatsheets"; label: string; icon: any }> = [
  { slug: "topics", label: "Topics", icon: Library },
  { slug: "questions", label: "Questions", icon: BookOpen },
  { slug: "review", label: "Review", icon: Sparkles },
  { slug: "cheatsheets", label: "Cheatsheets", icon: Layers },
];

function activeTrack(pathname: string): Track | null {
  for (const t of TRACKS) {
    if (pathname === `/${t}` || pathname.startsWith(`/${t}/`)) return t;
  }
  return null;
}

export function Sidebar() {
  const pathname = usePathname();
  const track = activeTrack(pathname);

  return (
    <aside className="w-56 shrink-0 border-r bg-muted/20 h-screen sticky top-0">
      <div className="p-5 border-b">
        <Link href={track ? `/${track}` : "/"} className="block">
          <div className="text-base font-semibold tracking-tight">Career Lab</div>
        </Link>
      </div>

      <div className="p-2 border-b">
        <div className="grid grid-cols-2 gap-1 p-1 rounded-md bg-muted/40">
          {TRACKS.map((t) => (
            <Link
              key={t}
              href={`/${t}`}
              className={cn(
                "text-center text-xs font-medium py-1.5 rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                t === track ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {TRACK_LABELS[t]}
            </Link>
          ))}
        </div>
      </div>

      <nav className="p-2">
        {track && NAV.map((item) => {
          const Icon = item.icon;
          const href = `/${track}/${item.slug}`;
          const isActive = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={item.slug}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isActive ? "bg-accent text-foreground" : "text-foreground hover:bg-accent",
              )}
            >
              <Icon className="h-4 w-4 text-muted-foreground" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto p-4 border-t">
        <SignOutButton />
      </div>
    </aside>
  );
}
