import { notFound } from "next/navigation";
import Link from "next/link";
import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import { TRACK_PATHS, parseTrack, TRACK_LABELS } from "@/lib/paths";
import { MdxRenderer } from "@/components/MdxRenderer";

async function listSlugs(track: ReturnType<typeof parseTrack>) {
  if (!track) return [];
  const dir = TRACK_PATHS[track].cheatsheetsContent;
  try {
    const files = await fs.readdir(dir);
    return files
      .filter((f) => f.endsWith(".md") || f.endsWith(".mdx"))
      .sort()
      .map((f) => f.replace(/\.(md|mdx)$/, ""));
  } catch {
    return [];
  }
}

export default async function CheatsheetPage({
  params,
}: {
  params: Promise<{ track: string; slug: string }>;
}) {
  const { track: trackParam, slug } = await params;
  const track = parseTrack(trackParam);
  if (!track) notFound();

  const dir = TRACK_PATHS[track].cheatsheetsContent;
  const candidates = [`${slug}.mdx`, `${slug}.md`];
  let raw: string | null = null;
  for (const c of candidates) {
    try {
      raw = await fs.readFile(path.join(dir, c), "utf8");
      break;
    } catch {}
  }
  if (!raw) notFound();

  const { data, content } = matter(raw);
  const title = (data.title as string) ?? slug;
  const description = data.description as string | undefined;

  const allSlugs = await listSlugs(track);
  const currentIdx = allSlugs.indexOf(slug);
  const prevSlug = currentIdx > 0 ? allSlugs[currentIdx - 1] : null;
  const nextSlug = currentIdx < allSlugs.length - 1 ? allSlugs[currentIdx + 1] : null;

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        .csd { height:100%; display:grid; grid-template-columns: 1fr 200px; overflow:hidden; }
        .csd__col { overflow:auto; }
        .csd__inner { max-width: 760px; margin: 0 auto; padding: 48px 24px 80px; }
        .csd__meta { display:flex; align-items:center; gap: 10px; font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .12em; }
        .csd__meta a { color: var(--mute); text-decoration:none; }
        .csd__meta a:hover { color: var(--ink); }
        .csd__t { font-family: var(--font-read); font-style: italic; font-weight: 400; font-size: 44px; letter-spacing: -0.022em; line-height: 1.05; margin: 14px 0 8px; color: var(--ink); }
        .csd__sub { font-family: var(--font-read); font-size: 18px; line-height: 1.55; color: var(--mute); max-width: 50ch; margin-bottom: 32px; }
        .csd-body { font-family: var(--font-read); font-size: 17.5px; line-height: 1.7; color: var(--ink-2); }
        .csd__rail { border-left: 1px solid var(--line); padding: 36px 18px; font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); display:flex; flex-direction: column; gap: 18px; background: var(--bg-2); overflow:auto; }
        .csd__rail .h { color: var(--mute-2); text-transform: uppercase; letter-spacing: .14em; }
        .csd__rail a { display:block; color: var(--mute); padding: 4px 0 4px 12px; border-left: 1.5px solid var(--line); cursor:pointer; text-decoration:none; }
        .csd__rail a:hover { color: var(--ink); border-left-color: var(--accent); }
        .csd__head-bar { position: sticky; top:0; z-index: 2; padding: 10px 0; border-bottom: 1px solid var(--line); background: linear-gradient(to bottom, var(--bg) 80%, transparent); margin-bottom: 22px; display:flex; align-items: center; gap: 12px; }
        .csd__head-bar .pos { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .12em; }
        .csd__head-bar .pos b { color: var(--ink); font-weight: 500; }
        .csd__nav { display:flex; flex-direction:column; gap: 8px; }
        .csd__nav-btn { display:flex; flex-direction: column; gap: 2px; padding: 8px 10px; border-radius: 6px; text-decoration:none; background: var(--surf); border: 1px solid var(--line); }
        .csd__nav-btn:hover { border-color: var(--line-2); background: var(--surf-2); }
        .csd__nav-btn .dir { font-family: var(--font-mono); font-size: 9px; color: var(--mute-2); text-transform: uppercase; letter-spacing: .12em; }
        .csd__nav-btn .lbl { font-family: var(--font-mono); font-size: 10.5px; color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      ` }} />
      <div className="csd">
        <div className="csd__col">
          <div className="csd__inner">
            <div className="csd__head-bar">
              <Link href={`/${track}/cheatsheets`} className="csd__meta" style={{gap:6}}>
                ← {TRACK_LABELS[track]}
              </Link>
              <div className="pos" style={{marginLeft:"auto"}}>
                {currentIdx >= 0 && (
                  <>Sheet <b>{currentIdx + 1}</b> of {allSlugs.length}</>
                )}
              </div>
            </div>

            <div className="csd__meta">
              <Link href={`/${track}/cheatsheets`}>{TRACK_LABELS[track]}</Link>
              <span>·</span>
              <span>Cheatsheets</span>
              <span>·</span>
              <span>{slug}</span>
            </div>
            <div className="csd__t">{title}</div>
            {description && <div className="csd__sub">{description}</div>}

            <div className="csd-body">
              <MdxRenderer source={content} />
            </div>
          </div>
        </div>

        <div className="csd__rail">
          <div className="h">On this page</div>
          <a href="#top">Introduction</a>
          <a href="#key-concepts">Key Concepts</a>
          <a href="#examples">Examples</a>

          <div style={{marginTop:"auto"}}>
            <div className="h" style={{marginBottom:8}}>Navigation</div>
            <div className="csd__nav">
              {prevSlug ? (
                <Link href={`/${track}/cheatsheets/${prevSlug}`} className="csd__nav-btn">
                  <span className="dir">← Prev</span>
                  <span className="lbl">{prevSlug}</span>
                </Link>
              ) : (
                <div className="csd__nav-btn" style={{opacity:0.35, pointerEvents:"none"}}>
                  <span className="dir">← Prev</span>
                  <span className="lbl">—</span>
                </div>
              )}
              {nextSlug ? (
                <Link href={`/${track}/cheatsheets/${nextSlug}`} className="csd__nav-btn">
                  <span className="dir">Next →</span>
                  <span className="lbl">{nextSlug}</span>
                </Link>
              ) : (
                <div className="csd__nav-btn" style={{opacity:0.35, pointerEvents:"none"}}>
                  <span className="dir">Next →</span>
                  <span className="lbl">—</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
