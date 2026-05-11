import { notFound } from "next/navigation";
import Link from "next/link";
import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import { TRACK_PATHS, parseTrack, TRACK_LABELS } from "@/lib/paths";
import type { Track } from "@/db/schema";

async function listCheatsheets(track: Track) {
  const dir = TRACK_PATHS[track].cheatsheetsContent;
  try {
    const files = await fs.readdir(dir);
    const out: Array<{ slug: string; title: string; description: string }> = [];
    for (const f of files.sort()) {
      if (!f.endsWith(".md") && !f.endsWith(".mdx")) continue;
      const raw = await fs.readFile(path.join(dir, f), "utf8");
      const { data } = matter(raw);
      out.push({
        slug: f.replace(/\.(md|mdx)$/, ""),
        title: (data.title as string) ?? f,
        description: (data.description as string) ?? "",
      });
    }
    return out;
  } catch {
    return [];
  }
}

export default async function CheatsheetsPage({
  params,
}: {
  params: Promise<{ track: string }>;
}) {
  const { track: trackParam } = await params;
  const track = parseTrack(trackParam);
  if (!track) notFound();
  const sheets = await listCheatsheets(track);

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        .cs { height:100%; overflow:auto; }
        .cs__inner { max-width: 920px; margin: 0 auto; padding: 36px 36px 64px; }
        .cs__head { display:flex; align-items:end; gap:24px; padding-bottom: 24px; border-bottom: 1px solid var(--line); }
        .cs__h { font-size: 30px; font-weight: 600; letter-spacing: -0.024em; }
        .cs__h em { font-family: var(--font-read); font-style: italic; font-weight: 400; color: var(--mute); }
        .cs__sub { color: var(--mute); font-size: 14px; margin-top: 8px; max-width: 56ch; }
        .cs__r { margin-left: auto; }
        .cs__row { display:grid; grid-template-columns: 32px 1fr 90px 90px 24px; gap: 22px; padding: 18px 6px; border-bottom: 1px solid var(--line); align-items: center; cursor: pointer; text-decoration:none; color:inherit; }
        .cs__row:hover { background: var(--bg-2); }
        .row__n { font-family: var(--font-mono); font-size: 11px; color: var(--mute-2); padding-left: 6px; }
        .row__t { font-family: var(--font-read); font-size: 18px; line-height: 1.3; color: var(--ink); letter-spacing: -0.012em; }
        .row__d { color: var(--mute); font-size: 13px; line-height: 1.5; margin-top: 4px; max-width: 70ch; }
        .row__w { font-family: var(--font-mono); font-size: 11px; color: var(--mute); text-align: right; }
        .row__e { font-family: var(--font-mono); font-size: 11px; color: var(--mute-2); text-align: right; }
        .row__chev { color: var(--mute-2); display:flex; justify-content:center; }
        .cs__row:hover .row__chev { color: var(--ink); }
        .cs__empty { padding: 60px 0; text-align: center; font-family: var(--font-mono); font-size: 12px; color: var(--mute); text-transform: uppercase; letter-spacing: .12em; }
      ` }} />
      <div className="cs">
        <div className="cs__inner">
          <div className="cs__head">
            <div>
              <div className="cs__h">Cheatsheets <em>&amp; quick ref</em></div>
              <div className="cs__sub">{TRACK_LABELS[track]} · quick references you should be able to recite cold.</div>
            </div>
            <div className="cs__r">
              <span className="badge">{sheets.length} sheets</span>
            </div>
          </div>

          {sheets.length === 0 && (
            <div className="cs__empty">No cheatsheets yet</div>
          )}

          {sheets.map((s, i) => (
            <Link key={s.slug} href={`/${track}/cheatsheets/${s.slug}`} className="cs__row">
              <span className="row__n">{String(i + 1).padStart(2, "0")}</span>
              <span>
                <div className="row__t">{s.title}</div>
                {s.description && <div className="row__d">{s.description}</div>}
              </span>
              <span className="row__w">—</span>
              <span className="row__e">{s.slug}</span>
              <span className="row__chev">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 18l6-6-6-6"/>
                </svg>
              </span>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}
