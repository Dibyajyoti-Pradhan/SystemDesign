import Link from "next/link";
import { Library, BookOpen, Sparkles, Layers } from "lucide-react";

const NAV = [
  { href: "/topics", label: "Topics", icon: Library },
  { href: "/questions", label: "Questions", icon: BookOpen },
  { href: "/review", label: "Review", icon: Sparkles },
  { href: "/cheatsheets", label: "Cheatsheets", icon: Layers },
];

export function Sidebar() {
  return (
    <aside className="w-56 shrink-0 border-r bg-muted/20 h-screen sticky top-0">
      <div className="p-5 border-b">
        <Link href="/" className="block">
          <h1 className="text-base font-semibold tracking-tight">System Design</h1>
        </Link>
      </div>
      <nav className="p-2">
        {NAV.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-3 px-3 py-2 rounded-md text-sm hover:bg-accent transition-colors"
            >
              <Icon className="h-4 w-4 text-muted-foreground" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
