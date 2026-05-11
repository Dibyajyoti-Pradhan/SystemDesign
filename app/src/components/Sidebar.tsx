"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import {
  Layers,
  HelpCircle,
  Repeat,
  ScrollText,
  Network,
  Notebook,
  Search,
} from "lucide-react";
import { TRACKS, TRACK_LABELS, type Track } from "@/lib/tracks";

const NAV_TOP = [
  { id: "topics",      label: "Topics",      icon: Layers,     slug: "topics" },
  { id: "questions",   label: "Questions",   icon: HelpCircle, slug: "questions" },
  { id: "review",      label: "Review",      icon: Repeat,     slug: "review" },
  { id: "cheatsheets", label: "Cheatsheets", icon: ScrollText, slug: "cheatsheets" },
] as const;

const NAV_FOOT = [
  { id: "concept-map", label: "Concept Map", icon: Network,  slug: "concept-map", global: false },
  { id: "notes",       label: "Notes",       icon: Notebook, slug: "notes",       global: true },
  { id: "search",      label: "Search",      icon: Search,   slug: "search",      global: true, kbd: "⌘K" },
] as const;

function activeTrack(pathname: string): Track | null {
  for (const t of TRACKS) {
    if (pathname === `/${t}` || pathname.startsWith(`/${t}/`)) return t;
  }
  return null;
}

function activeId(pathname: string, track: Track | null): string {
  if (!track) return "";
  for (const n of NAV_TOP) {
    const href = `/${track}/${n.slug}`;
    if (pathname === href || pathname.startsWith(`${href}/`)) return n.id;
  }
  for (const n of NAV_FOOT) {
    const href = n.global ? `/${n.slug}` : `/${track}/${n.slug}`;
    if (pathname === href || pathname.startsWith(`${href}/`)) return n.id;
  }
  return "";
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const track = activeTrack(pathname) ?? "system-design";
  const active = activeId(pathname, track);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        router.push("/search");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);

  return (
    <aside className="sb">
      <div className="sb__brand">
        <div className="sb__mark" />
        <div className="sb__name">Career Lab</div>
        <div className="sb__ver">v0.4</div>
      </div>

      <div className="track" role="tablist" aria-label="Track">
        {TRACKS.map((t) => (
          <Link
            key={t}
            href={`/${t}`}
            className={`track__pill${t === track ? " is-on" : ""}`}
          >
            {TRACK_LABELS[t]}
          </Link>
        ))}
      </div>

      <nav className="nav">
        <div className="nav__group">Study</div>
        {NAV_TOP.map((n) => {
          const Icon = n.icon;
          const href = `/${track}/${n.slug}`;
          return (
            <Link
              key={n.id}
              href={href}
              className={`nav__item${active === n.id ? " is-on" : ""}`}
            >
              <Icon className="nav__icon" style={{ width: 14, height: 14 }} />
              <span>{n.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="sb__foot">
        {NAV_FOOT.map((n) => {
          const Icon = n.icon;
          const href = n.global ? `/${n.slug}` : `/${track}/${n.slug}`;
          return (
            <Link
              key={n.id}
              href={href}
              className={`nav__item${active === n.id ? " is-on" : ""}`}
            >
              <Icon className="nav__icon" style={{ width: 14, height: 14 }} />
              <span>{n.label}</span>
              {"kbd" in n && n.kbd && (
                <span className="nav__count" style={{ fontSize: 10 }}>
                  {n.kbd}
                </span>
              )}
            </Link>
          );
        })}
      </div>
    </aside>
  );
}
