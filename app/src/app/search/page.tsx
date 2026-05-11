import Link from "next/link";
import { search } from "@/lib/search";

export default async function SearchPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams;
  const hits = q ? await search(q, 30) : [];

  const topics = hits.filter((h) => h.kind === "topic");
  const questions = hits.filter((h) => h.kind === "question");

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        .sr { height:100%; overflow:auto; }
        .sr__inner { max-width: 880px; margin: 0 auto; padding: 28px 28px 64px; }
        .sr__input { display:flex; align-items: center; gap: 12px; padding: 14px 18px; background: var(--bg-2); border:1px solid var(--line-2); border-radius: 10px; }
        .sr__icon { color: var(--mute); flex-shrink:0; }
        .sr__q { flex:1; background: transparent; border: 0; outline: 0; font-family: var(--font-ui); font-size: 18px; color: var(--ink); letter-spacing: -0.012em; }
        .sr__q::placeholder { color: var(--mute); }
        .sr__bar { display:flex; align-items: center; gap: 10px; padding: 14px 4px 0; font-family: var(--font-mono); font-size: 11px; color: var(--mute); }
        .sr__bar b { color: var(--ink); font-weight: 500; }
        .sec { margin-top: 22px; }
        .sec__h { display:flex; align-items: center; gap:14px; margin-bottom: 4px; }
        .sec__h b { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .14em; font-weight: 500; }
        .sec__h::after { content:""; flex:1; height:1px; background: var(--line); }
        .sec__h em { font-family: var(--font-mono); font-size: 11px; color: var(--mute-2); font-style: normal; }
        .res { display:grid; grid-template-columns: 60px 1fr 100px; gap: 18px; padding: 14px 8px; border-radius: 6px; align-items: start; cursor:pointer; text-decoration:none; color:inherit; }
        .res:hover { background: var(--surf); }
        .res__kind { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute-2); text-transform: uppercase; letter-spacing: .12em; padding-top: 4px; }
        .res__t { font-family: var(--font-ui); font-size: 15px; font-weight: 500; color: var(--ink-2); letter-spacing: -0.005em; }
        .res__cat { display:block; font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); margin-top: 4px; text-transform: uppercase; letter-spacing: .08em; }
        .res__r { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute-2); text-align: right; padding-top: 4px; }
        .sr__hint { display:flex; align-items: center; gap: 14px; padding: 18px 4px; margin-top: 18px; border-top: 1px solid var(--line); font-family: var(--font-mono); font-size: 11px; color: var(--mute); }
        .sr__hint span { display:flex; align-items: center; gap: 6px; }
        .sr__empty { padding: 48px 0; text-align: center; font-family: var(--font-mono); font-size: 12px; color: var(--mute); text-transform: uppercase; letter-spacing: .12em; }
      ` }} />
      <div className="sr">
        <div className="sr__inner">
          <form className="sr__input">
            <svg className="sr__icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <input
              type="text"
              name="q"
              className="sr__q"
              defaultValue={q}
              autoFocus
              placeholder="caching, sharding, instagram, rate limit…"
            />
          </form>

          {q && (
            <div className="sr__bar">
              <b>{hits.length}</b> result{hits.length === 1 ? "" : "s"} for &ldquo;{q}&rdquo;
            </div>
          )}

          {q && hits.length === 0 && (
            <div className="sr__empty">No matches found</div>
          )}

          {topics.length > 0 && (
            <div className="sec">
              <div className="sec__h">
                <b>Topics</b>
                <em>{topics.length}</em>
              </div>
              {topics.map((h) => (
                <Link key={`topic-${h.id}`} href={`/topics/${h.slug}`} className="res">
                  <span className="res__kind">Topic</span>
                  <span>
                    <span className="res__t">{h.title}</span>
                    {h.category && <span className="res__cat">{h.category}</span>}
                  </span>
                  <span className="res__r">{Math.round((1 - h.score) * 100)}% match</span>
                </Link>
              ))}
            </div>
          )}

          {questions.length > 0 && (
            <div className="sec">
              <div className="sec__h">
                <b>Questions</b>
                <em>{questions.length}</em>
              </div>
              {questions.map((h) => (
                <Link key={`question-${h.id}`} href={`/questions/${h.slug}`} className="res">
                  <span className="res__kind">Question</span>
                  <span>
                    <span className="res__t">{h.title}</span>
                    {h.category && <span className="res__cat">{h.category}</span>}
                  </span>
                  <span className="res__r">{Math.round((1 - h.score) * 100)}% match</span>
                </Link>
              ))}
            </div>
          )}

          <div className="sr__hint">
            <span>
              <kbd style={{padding:"2px 6px", background:"var(--surf-2)", borderRadius:4, border:"1px solid var(--line-2)"}}>↵</kbd>
              open
            </span>
            <span>
              <kbd style={{padding:"2px 6px", background:"var(--surf-2)", borderRadius:4, border:"1px solid var(--line-2)"}}>↑↓</kbd>
              navigate
            </span>
            <span>
              <kbd style={{padding:"2px 6px", background:"var(--surf-2)", borderRadius:4, border:"1px solid var(--line-2)"}}>esc</kbd>
              clear
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
