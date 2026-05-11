"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { marked } from "marked";
import { Mermaid } from "@/components/Mermaid";
import { Play, Pause, StepForward, Send } from "lucide-react";

type AgentRole = "interviewer" | "candidate";
type SteerTarget = "interviewer" | "candidate" | "both";

type Msg =
  | { role: AgentRole; content: string; ts: number }
  | { role: "steer"; content: string; target: SteerTarget; consumed: boolean; ts: number };

interface Props {
  sessionId: number;
  questionTitle: string;
  initialTranscript: Msg[];
  initialEnded: boolean;
}

const CSS = `
.vsai { height:100%; display:grid; grid-template-rows: auto 1fr auto; background: var(--bg); overflow:hidden; }

/* meta strip */
.vs__meta { display:flex; align-items: center; gap: 14px; padding: 14px 36px 12px; border-bottom: 1px solid var(--line); }
.vs__title { font-size: 16px; font-weight: 600; letter-spacing: -0.012em; }
.vs__title small { color: var(--mute); font-weight: 400; margin-left: 8px; }
.vs__chips { display:flex; gap: 6px; }

/* turn budget stave */
.stave { display:flex; align-items: center; gap: 10px; margin-left: auto; }
.stave__lbl { font-family: var(--font-mono); font-size: 10px; color: var(--mute); text-transform: uppercase; letter-spacing: .1em; }
.stave__bar { display:flex; gap: 2px; }
.stave__tick { width: 6px; height: 14px; background: var(--surf-3); border-radius: 1px; }
.stave__tick.is-done { background: var(--ink-2); }
.stave__tick.is-now  { background: var(--accent); box-shadow: 0 0 0 2px rgba(212,165,116,0.18); }
.stave__tick.is-soft { background: var(--surf-3); border: 1px dashed rgba(212,165,116,0.5); }
.stave__tick.is-hard { background: transparent; border: 1px solid var(--bad); }
.stave__num { font-family: var(--font-mono); font-size: 11px; color: var(--ink-2); }
.stave__num em { color: var(--mute); font-style: normal; }

/* transcript */
.vs__feed { overflow:auto; padding: 24px 36px 28px; }
.vs__lane { max-width: 920px; margin: 0 auto; display:flex; flex-direction: column; gap: 22px; }

.vs-turn { display:grid; grid-template-columns: 92px 1fr; gap: 18px; }
.vs-turn .gut { display:flex; flex-direction: column; align-items: flex-end; padding-top: 4px; gap: 4px; }
.vs-turn .who { font-family: var(--font-mono); font-size: 10.5px; text-transform: uppercase; letter-spacing: .1em; }
.vs-turn .num { font-family: var(--font-mono); font-size: 10px; color: var(--mute-2); }
.vs-turn.t-i .who { color: var(--accent); }
.vs-turn.t-c .who { color: var(--info, #6aa3f8); }
.vs-turn .body {
  font-size: 14.5px; line-height: 1.6; color: var(--ink-2);
  padding: 10px 14px; border-radius: 8px;
  border: 1px solid var(--line);
  max-width: 70ch;
  position: relative;
}
.vs-turn.t-i .body { background: var(--bg-2); border-color: var(--line); }
.vs-turn.t-c .body { background: var(--surf); border-color: var(--line-2); }
.vs-turn.t-i .body::before {
  content:""; position:absolute; left:-1px; top:14px; bottom:14px; width:2px;
  background: var(--accent); border-radius: 2px;
}
.vs-turn.t-c .body::before {
  content:""; position:absolute; left:-1px; top:14px; bottom:14px; width:2px;
  background: var(--info, #6aa3f8); border-radius: 2px;
}

/* streaming cursor */
.vs-cursor { display:inline-block; width: 7px; height: 14px; background: var(--info, #6aa3f8); vertical-align: -2px; margin-left: 2px; animation: vs-bl 1s steps(2) infinite; }
@keyframes vs-bl { 50% { opacity: 0.2 } }

/* steer banner in transcript */
.vs-steer { display:grid; grid-template-columns: 92px 1fr; gap: 18px; }
.vs-steer .gut { padding-top: 8px; display:flex; flex-direction: column; align-items: flex-end; gap: 2px; }
.vs-steer .gut .who { font-family: var(--font-mono); font-size: 10px; color: var(--warn, #D4A574); text-transform: uppercase; letter-spacing: .1em; }
.vs-steer .gut .num { font-family: var(--font-mono); font-size: 10px; color: var(--mute-2); }
.vs-steer__line {
  padding: 8px 12px; border-radius: 6px;
  background: rgba(212,165,116,0.06);
  border: 1px dashed rgba(212,165,116,0.45);
  color: var(--ink-2); font-size: 13.5px; line-height: 1.5;
  display:flex; gap: 10px; align-items:flex-start;
}
.vs-steer__line .arrow { color: var(--warn, #D4A574); font-family: var(--font-mono); font-size: 11px; }
.vs-steer__line .to { color: var(--warn, #D4A574); font-family: var(--font-mono); font-size: 10.5px; text-transform: uppercase; letter-spacing: .1em; margin-right: 8px; }

/* error banner */
.vs-err { display:grid; grid-template-columns: 92px 1fr; gap: 18px; }
.vs-err__inner { padding: 8px 12px; border-radius: 6px; background: rgba(239,68,68,0.06); border: 1px solid rgba(239,68,68,0.3); color: var(--bad, #ef4444); font-size: 13px; display:flex; gap: 10px; align-items: center; }
.vs-err__inner button { font-family: var(--font-mono); font-size: 11px; color: inherit; background: none; border: 1px solid rgba(239,68,68,0.4); border-radius: 4px; padding: 3px 8px; cursor:pointer; }
.vs-err__inner button:hover { background: rgba(239,68,68,0.08); }

/* control bar */
.vs-bar {
  border-top: 1px solid var(--line);
  background: var(--bg-2);
  padding: 12px 36px;
  display:grid; grid-template-columns: auto 1fr auto; gap: 18px; align-items: center;
}
.vs-bar__pb { display:flex; align-items:center; gap: 6px; }
.pb__btn { width: 34px; height: 34px; border-radius: 6px; display:grid; place-items:center; background: var(--surf); border: 1px solid var(--line-2); color: var(--ink); cursor:pointer; transition: background .1s; }
.pb__btn:hover { background: var(--surf-2); }
.pb__btn.is-primary { background: var(--accent); border-color: var(--accent); color: #1a1208; }
.pb__btn.is-primary:hover { opacity: .9; }
.pb__btn:disabled { opacity: .4; cursor: not-allowed; }
.pb__div { width:1px; height: 22px; background: var(--line); margin: 0 4px; }
.pb__lbl { font-family: var(--font-mono); font-size: 10px; color: var(--mute); text-transform: uppercase; letter-spacing: .1em; padding: 0 6px; }

/* steer composer */
.vs-comp {
  background: var(--surf); border: 1px solid var(--line-2); border-radius: 8px;
  padding: 8px 10px 8px 12px;
  display:flex; align-items:center; gap: 12px;
  min-height: 38px;
}
.vs-comp__pre { font-family: var(--font-mono); font-size: 10.5px; color: var(--warn, #D4A574); text-transform: uppercase; letter-spacing: .1em; flex:0 0 auto; }
.vs-comp__seg { display:flex; gap:1px; padding: 2px; border:1px solid var(--line); border-radius: 6px; background: var(--bg); flex:0 0 auto; }
.vs-comp__seg span { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); padding: 4px 9px; border-radius: 4px; cursor:pointer; text-transform: uppercase; letter-spacing: .05em; user-select: none; }
.vs-comp__seg span.is-on { background: var(--surf-2); color: var(--ink); }
.vs-comp__inp { flex:1; min-width: 0; background: none; border: none; outline: none; font-size: 13.5px; color: var(--ink-2); font-family: var(--font-ui); }
.vs-comp__inp::placeholder { color: var(--mute-2); }
.vs-comp__send { background: none; border: 0; color: var(--accent); cursor:pointer; padding: 4px; display:flex; align-items:center; }
.vs-comp__send:disabled { opacity: .35; cursor: not-allowed; }

.vs-endbtn { background: var(--bg); border: 1px solid var(--line-2); color: var(--ink-2); padding: 7px 12px; border-radius: 6px; font-size: 13px; cursor:pointer; display:inline-flex; align-items:center; gap:6px; white-space: nowrap; }
.vs-endbtn:hover { color: var(--ink); border-color: var(--accent); }
.vs-endbtn:disabled { opacity: .5; cursor: not-allowed; }

/* prose in bubbles */
.vs-body-html { font-size: 14.5px; line-height: 1.6; color: var(--ink-2); }
.vs-body-html p { margin: 0 0 8px; }
.vs-body-html p:last-child { margin-bottom: 0; }
.vs-body-html code { font-family: var(--font-mono); font-size: 13px; background: var(--bg); padding: 1px 4px; border-radius: 3px; border: 1px solid var(--line); }
.vs-body-html pre { background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 10px 12px; overflow: auto; margin: 8px 0; }
.vs-body-html pre code { background: none; border: none; padding: 0; }
.vs-body-html ul, .vs-body-html ol { padding-left: 20px; margin: 6px 0; }
.vs-body-html li { margin-bottom: 4px; }
.vs-body-html strong { color: var(--ink); }
.vs-body-html h1,.vs-body-html h2,.vs-body-html h3 { font-size: 15px; font-weight: 600; margin: 12px 0 6px; color: var(--ink); }
`;

function stripSentinel(t: string) {
  return t.replace(/<<INTERVIEW_END>>/g, "").trimEnd();
}

function BodyContent({ text, streaming }: { text: string; streaming?: boolean }) {
  const display = stripSentinel(text);
  const segments = useMemo(() => {
    const parts: Array<{ kind: "md"; text: string } | { kind: "mermaid"; code: string }> = [];
    const re = /```mermaid\n([\s\S]*?)```/g;
    let last = 0, m: RegExpExecArray | null;
    while ((m = re.exec(display)) !== null) {
      if (m.index > last) parts.push({ kind: "md", text: display.slice(last, m.index) });
      parts.push({ kind: "mermaid", code: m[1] });
      last = re.lastIndex;
    }
    if (last < display.length) parts.push({ kind: "md", text: display.slice(last) });
    return parts;
  }, [display]);

  return (
    <>
      {segments.map((seg, i) =>
        seg.kind === "mermaid" ? (
          <Mermaid key={i} chart={seg.code} />
        ) : (
          <div
            key={i}
            className="vs-body-html"
            dangerouslySetInnerHTML={{ __html: marked.parse(seg.text, { async: false }) as string }}
          />
        )
      )}
      {streaming && <span className="vs-cursor" />}
    </>
  );
}

export function AiVsAiSession({ sessionId, questionTitle, initialTranscript, initialEnded }: Props) {
  const router = useRouter();
  const [messages, setMessages] = useState<Msg[]>(initialTranscript);
  const [streamingRole, setStreamingRole] = useState<AgentRole | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [paused, setPaused] = useState<boolean>(initialEnded || true);
  const [ended, setEnded] = useState(initialEnded);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [steerText, setSteerText] = useState("");
  const [steerTarget, setSteerTarget] = useState<SteerTarget>("both");
  const [grading, setGrading] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);

  const nextAgent: AgentRole = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === "interviewer") return "candidate";
      if (m.role === "candidate") return "interviewer";
    }
    return "interviewer";
  }, [messages]);

  const pendingSteers = useMemo(
    () => messages.filter((m): m is Extract<Msg, { role: "steer" }> => m.role === "steer" && !m.consumed),
    [messages]
  );

  const turnCount = messages.filter((m) => m.role !== "steer").length;
  const HARD_CAP = 24;
  const SOFT_CAP = 20;

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: "smooth" });
  }, [streamingText, messages.length]);

  const step = useCallback(async () => {
    if (running || ended) return;
    setRunning(true);
    setError(null);

    const ctl = new AbortController();
    abortRef.current = ctl;
    let accumulated = "";
    let role: AgentRole = nextAgent;

    try {
      const res = await fetch("/api/interview/ai-vs-ai/step", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId }),
        signal: ctl.signal,
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`step failed (${res.status}): ${text || "unknown"}`);
      }

      const headerRole = res.headers.get("x-agent-role");
      if (headerRole === "interviewer" || headerRole === "candidate") role = headerRole;
      const steerConsumed = res.headers.get("x-steer-consumed") === "1";
      const forcedWrap = res.headers.get("x-force-wrap") === "1";

      setStreamingRole(role);
      setStreamingText("");

      if (!res.body) throw new Error("Empty response from server");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        accumulated += chunk;
        setStreamingText((prev) => prev + chunk);
      }

      if (!accumulated) throw new Error("Empty response from server");
      if (accumulated.includes("[error:")) {
        const match = accumulated.match(/\[error: ([^\]]+)\]/);
        throw new Error(match ? match[1] : "upstream error");
      }

      setMessages((prev) => {
        let updated = prev;
        if (steerConsumed) {
          for (let i = updated.length - 1; i >= 0; i--) {
            const m = updated[i];
            if (m.role === "steer" && !m.consumed && (m.target === role || m.target === "both")) {
              updated = updated.map((x, idx) => idx === i && x.role === "steer" ? { ...x, consumed: true } : x);
              break;
            }
          }
        }
        return [...updated, { role, content: accumulated, ts: Date.now() }];
      });

      if (accumulated.includes("<<INTERVIEW_END>>") || forcedWrap) {
        setPaused(true);
      }
    } catch (e: any) {
      if (e?.name !== "AbortError") {
        setError(e?.message ?? String(e));
        setPaused(true);
      }
    } finally {
      setStreamingRole(null);
      setStreamingText("");
      setRunning(false);
      abortRef.current = null;
    }
  }, [nextAgent, running, ended, sessionId]);

  useEffect(() => {
    if (paused || running || ended) return;
    const id = setTimeout(() => { step(); }, 250);
    return () => clearTimeout(id);
  }, [paused, running, ended, step, messages.length]);

  const handleInjectSteer = async () => {
    if (!steerText.trim()) return;
    try {
      const res = await fetch("/api/interview/ai-vs-ai/steer", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, content: steerText.trim(), target: steerTarget }),
      });
      if (!res.ok) throw new Error(await res.text());
      setMessages((prev) => [...prev, { role: "steer", content: steerText.trim(), target: steerTarget, consumed: false, ts: Date.now() }]);
      setSteerText("");
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  };

  const handleEnd = async () => {
    if (running) abortRef.current?.abort();
    setPaused(true);
    setEnded(true);
    setMessages((prev) => prev.map((m) => (m.role === "steer" && !m.consumed ? { ...m, consumed: true } : m)));
    setGrading(true);
    try {
      const res = await fetch("/api/interview/grade", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId }),
      });
      if (!res.ok) throw new Error(await res.text());
    } catch (e: any) {
      setError(`Grading failed: ${e?.message ?? String(e)}`);
    } finally {
      setGrading(false);
      router.refresh();
    }
  };

  // Build allTurns including live streaming entry
  const allMsgs: Msg[] = [
    ...messages,
    ...(streamingRole ? [{ role: streamingRole, content: streamingText, ts: Date.now() } as Msg] : []),
  ];
  const allTurns = allMsgs.filter((m) => m.role !== "steer");

  return (
    <div className="vsai">
      <style dangerouslySetInnerHTML={{ __html: CSS }} />

      {/* ── Meta strip ── */}
      <div className="vs__meta">
        <div>
          <div className="vs__title">
            {questionTitle}
            <small>AI vs AI · observer mode</small>
          </div>
          <div className="vs__chips" style={{ marginTop: 6 }}>
            {ended ? (
              <span className="badge">ended</span>
            ) : paused ? (
              <span className="badge">paused</span>
            ) : running ? (
              <span className="badge" style={{ color: "var(--accent)" }}>
                {streamingRole ?? nextAgent} thinking
              </span>
            ) : (
              <span className="badge">{nextAgent} up</span>
            )}
            {pendingSteers.length > 0 && (
              <span className="badge">{pendingSteers.length} steer{pendingSteers.length === 1 ? "" : "s"} pending</span>
            )}
          </div>
        </div>

        {/* Turn budget stave */}
        <div className="stave">
          <span className="stave__lbl">Turn budget</span>
          <div className="stave__bar">
            {Array.from({ length: HARD_CAP }).map((_, i) => {
              let cls = "";
              if (i < turnCount - (running ? 1 : 0)) cls = "is-done";
              else if (running && i === turnCount - 1) cls = "is-now";
              else if (i >= SOFT_CAP) cls = i >= HARD_CAP - 1 ? "is-hard" : "is-soft";
              return <span key={i} className={`stave__tick${cls ? " " + cls : ""}`} />;
            })}
          </div>
          <span className="stave__num">{turnCount}<em> / {SOFT_CAP} soft · {HARD_CAP} hard</em></span>
        </div>
      </div>

      {/* ── Transcript feed ── */}
      <div className="vs__feed" ref={feedRef}>
        <div className="vs__lane">
          {allMsgs.length === 0 && !running && (
            <div style={{ textAlign: "center", paddingTop: 60, color: "var(--mute)", fontFamily: "var(--font-mono)", fontSize: 12, textTransform: "uppercase", letterSpacing: ".1em" }}>
              Press Resume to start the interview
            </div>
          )}

          {allMsgs.map((m, i) => {
            if (m.role === "steer") {
              const steerTurnNum = allMsgs.slice(0, i).filter((x) => x.role !== "steer").length;
              return (
                <div key={i} className="vs-steer">
                  <div className="gut">
                    <span className="who">Steer</span>
                    <span className="num">obs · {steerTurnNum}½</span>
                  </div>
                  <div className="vs-steer__line">
                    <span className="arrow">→</span>
                    <span>
                      <span className="to">to {m.target}</span>
                      {m.content}
                    </span>
                  </div>
                </div>
              );
            }

            const isStreaming = streamingRole !== null && i === allMsgs.length - 1;
            const turnNum = allMsgs.slice(0, i + 1).filter((x) => x.role !== "steer").length;
            const cls = m.role === "interviewer" ? "t-i" : "t-c";
            const name = m.role === "interviewer" ? "Interviewer" : "Candidate";

            return (
              <div key={i} className={`vs-turn ${cls}`}>
                <div className="gut">
                  <span className="who">{name}</span>
                  <span className="num">turn {turnNum}</span>
                </div>
                <div className="body">
                  <BodyContent text={m.content} streaming={isStreaming} />
                </div>
              </div>
            );
          })}

          {error && (
            <div className="vs-err">
              <div />
              <div className="vs-err__inner">
                <span style={{ flex: 1 }}>{error}</span>
                {!ended && (
                  <button onClick={() => { setError(null); step(); }} disabled={running}>
                    Retry
                  </button>
                )}
                <button onClick={() => setError(null)}>Dismiss</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Control bar ── */}
      {!ended && (
        <div className="vs-bar">
          {/* Playback */}
          <div className="vs-bar__pb">
            <span className="pb__lbl">Playback</span>
            {paused ? (
              <button className="pb__btn is-primary" onClick={() => setPaused(false)} disabled={running} title="Resume">
                <Play size={14} />
              </button>
            ) : (
              <button className="pb__btn" onClick={() => setPaused(true)} title="Pause">
                <Pause size={14} />
              </button>
            )}
            <button
              className="pb__btn"
              onClick={() => { if (!running && !ended) step(); }}
              disabled={running || ended}
              title="Step 1 turn"
            >
              <StepForward size={14} />
            </button>
            <span className="pb__div" />
            <span className="pb__lbl">{running ? "live" : paused ? "paused" : "auto"}</span>
          </div>

          {/* Steer composer */}
          <div className="vs-comp">
            <span className="vs-comp__pre">Steer</span>
            <div className="vs-comp__seg">
              {(["interviewer", "candidate", "both"] as const).map((t) => (
                <span
                  key={t}
                  className={steerTarget === t ? "is-on" : ""}
                  onClick={() => setSteerTarget(t)}
                >
                  {t}
                </span>
              ))}
            </div>
            <input
              className="vs-comp__inp"
              value={steerText}
              onChange={(e) => setSteerText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleInjectSteer(); }}
              placeholder='Inject instruction… e.g. "ask about geo replication"'
            />
            <button className="vs-comp__send" onClick={handleInjectSteer} disabled={!steerText.trim()} title="Inject (⌘↵)">
              <Send size={14} />
            </button>
          </div>

          {/* End & grade */}
          <button className="vs-endbtn" onClick={handleEnd} disabled={grading || turnCount < 2}>
            {grading ? "Grading…" : "∑ End & grade"}
          </button>
        </div>
      )}

      {ended && grading && (
        <div className="vs-bar" style={{ justifyContent: "center" }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--mute)", textTransform: "uppercase", letterSpacing: ".1em" }}>
            Grading… results will appear shortly
          </span>
        </div>
      )}
    </div>
  );
}
