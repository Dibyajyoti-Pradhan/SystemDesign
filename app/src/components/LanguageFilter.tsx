import Link from "next/link";
import { cn } from "@/lib/utils";
import { Code } from "lucide-react";

interface Props {
  languages: string[];
  activeLanguage: string | null;
  basePath: string;
}

/**
 * Inline chip filter for picking a language on Coding track pages.
 * Renders "All" + each language as a chip. Active chip is filled.
 *
 * Uses query params (?lang=) so the URL is shareable and the filter survives
 * server rendering.
 */
export function LanguageFilter({ languages, activeLanguage, basePath }: Props) {
  if (languages.length === 0) return null;
  return (
    <div className="flex items-center gap-2 flex-wrap text-xs">
      <span className="text-muted-foreground inline-flex items-center gap-1">
        <Code className="h-3 w-3" /> Language:
      </span>
      <Chip href={basePath} active={!activeLanguage}>All</Chip>
      {languages.map((lang) => (
        <Chip
          key={lang}
          href={`${basePath}?lang=${encodeURIComponent(lang)}`}
          active={activeLanguage === lang}
        >
          <span className="capitalize">{lang}</span>
        </Chip>
      ))}
    </div>
  );
}

function Chip({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "px-2.5 py-1 rounded-full border transition-colors",
        active
          ? "bg-primary text-primary-foreground border-primary"
          : "border-input hover:bg-accent hover:text-accent-foreground",
      )}
    >
      {children}
    </Link>
  );
}
