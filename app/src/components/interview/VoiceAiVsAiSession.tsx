"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Play, Pause, StepForward, X, Loader2, Bot } from "lucide-react";

interface Msg {
  role: "interviewer" | "candidate";
  content: string;
  ts: number;
}

interface Props {
  sessionId: number;
  questionTitle: string;
  initialTranscript: Msg[];
  initialEnded: boolean;
}

// Speak text and fire onEnd when done — bypasses useVoicePlayback so we can
// wire the callback for auto-advance without restructuring the shared hook.
function speakTurn(
  text: string,
  role: "interviewer" | "candidate",
  onEnd: () => void,
) {
  if (typeof window === "undefined" || !window.speechSynthesis) { onEnd(); return; }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = role === "interviewer" ? 0.92 : 0.97;
  u.pitch = role === "interviewer" ? 1.0 : 0.95;
  const voices = window.speechSynthesis.getVoices();
  if (role === "interviewer") {
    const v =
      voices.find((v) => v.lang === "en-GB" && v.name.includes("Neural")) ??
      voices.find((v) => v.lang === "en-GB") ??
      voices.find((v) => v.lang.startsWith("en"));
    if (v) u.voice = v;
  } else {
    const v =
      voices.find((v) => v.lang === "en-US" && v.name.includes("Neural")) ??
      voices.find((v) => v.lang === "en-US") ??
      voices.find((v) => v.lang.startsWith("en"));
    if (v) u.voice = v;
  }
  u.onend = onEnd;
  u.onerror = onEnd;
  window.speechSynthesis.speak(u);
}

export function VoiceAiVsAiSession({
  sessionId,
  questionTitle,
  initialTranscript,
  initialEnded,
}: Props) {
  const router = useRouter();
  const [transcript, setTranscript] = useState<Msg[]>(initialTranscript);
  const [started, setStarted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [ended, setEnded] = useState(initialEnded);
  const [error, setError] = useState<string | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const isPlayingRef = useRef(false);
  const endedRef = useRef(initialEnded);
  const isSteppingRef = useRef(false);

  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);
  useEffect(() => { endedRef.current = ended; }, [ended]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript.length]);

  const stepAndSpeak = useCallback(async () => {
    if (isSteppingRef.current || endedRef.current) return;
    isSteppingRef.current = true;
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/interview/ai-vs-ai/step", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId }),
      });
      if (!res.ok || !res.body) throw new Error(`Server error ${res.status}`);

      const role = (res.headers.get("x-agent-role") ?? "interviewer") as "interviewer" | "candidate";
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let text = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        text += decoder.decode(value, { stream: true });
      }

      const isEnd = text.includes("<<INTERVIEW_END>>");
      const cleaned = text.replace(/<<INTERVIEW_END>>/g, "").trimEnd();

      setTranscript((prev) => [...prev, { role, content: cleaned, ts: Date.now() }]);

      if (isEnd) {
        setEnded(true);
        setIsPlaying(false);
        endedRef.current = true;
      }

      isSteppingRef.current = false;
      setIsLoading(false);

      if (isPlayingRef.current) {
        setIsSpeaking(true);
        speakTurn(cleaned, role, () => {
          setIsSpeaking(false);
          // Auto-advance: if still playing and not ended, fetch next turn
          if (isPlayingRef.current && !endedRef.current) {
            void stepAndSpeak();
          }
        });
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Step failed");
      setIsPlaying(false);
      isSteppingRef.current = false;
      setIsLoading(false);
    }
  }, [sessionId]);

  function beginAndPlay() {
    setStarted(true);
    setIsPlaying(true);
    isPlayingRef.current = true;
    void stepAndSpeak();
  }

  function togglePlay() {
    if (ended) return;
    if (isPlaying) {
      setIsPlaying(false);
      window.speechSynthesis?.cancel();
      setIsSpeaking(false);
    } else {
      setIsPlaying(true);
      if (!isSteppingRef.current && !isSpeaking) {
        void stepAndSpeak();
      }
    }
  }

  function stepOnce() {
    if (ended || isSteppingRef.current || isSpeaking) return;
    setIsPlaying(false);
    isPlayingRef.current = false;
    void stepAndSpeak();
  }

  async function endSession() {
    if (!confirm("End session and score it?")) return;
    window.speechSynthesis?.cancel();
    try {
      const res = await fetch(`/api/interview/session/${sessionId}/score`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          transcriptHistory: transcript.map((m) => ({ role: m.role, content: m.content })),
        }),
      });
      if (!res.ok) throw new Error(`Scoring failed: ${res.status}`);
      router.push(`/interview/sessions/${sessionId}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to end session");
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "var(--bg)", color: "var(--ink)", fontFamily: "var(--font-ui)" }}>
      {/* Top bar */}
      <header style={{ flexShrink: 0, height: 44, display: "flex", alignItems: "center", padding: "0 18px", borderBottom: "1px solid var(--line)", gap: 12, background: "var(--bg)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Bot style={{ width: 14, height: 14, color: "var(--mute)" }} />
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.1em" }}>AI vs AI</span>
          <span style={{ color: "var(--subtle)" }}>›</span>
          <b style={{ color: "var(--ink-2)", fontWeight: 500, fontSize: 13, letterSpacing: "-0.005em", maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{questionTitle}</b>
        </div>
        <div style={{ flex: 1 }} />
        {started && !ended && (
          <>
            <button
              type="button"
              onClick={togglePlay}
              className="btn"
              style={{ fontSize: 12, padding: "4px 10px", gap: 5 }}
            >
              {isPlaying ? <Pause style={{ width: 12, height: 12 }} /> : <Play style={{ width: 12, height: 12 }} />}
              {isPlaying ? "Pause" : "Play"}
            </button>
            <button
              type="button"
              onClick={stepOnce}
              disabled={isSteppingRef.current || isSpeaking || isPlaying}
              className="btn btn--ghost"
              style={{ fontSize: 12, padding: "4px 10px", gap: 5 }}
              title="Step one turn"
            >
              <StepForward style={{ width: 12, height: 12 }} />
              Step
            </button>
          </>
        )}
        <button type="button" onClick={endSession} className="btn" style={{ fontSize: 12, padding: "4px 10px", gap: 5 }}>
          <X style={{ width: 12, height: 12 }} />
          End
        </button>
      </header>

      {/* Transcript feed */}
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "28px 36px 48px" }}>
        <div style={{ maxWidth: 760, margin: "0 auto", display: "flex", flexDirection: "column", gap: 20 }}>
          {transcript.length === 0 && started && (
            <div style={{ fontFamily: "var(--font-read)", fontStyle: "italic", fontSize: 15, color: "var(--mute-2)", textAlign: "center", paddingTop: 48 }}>
              Waiting for first turn…
            </div>
          )}
          {transcript.map((msg, i) => {
            const isIv = msg.role === "interviewer";
            return (
              <div key={i} style={{ display: "grid", gridTemplateColumns: "88px 1fr", gap: 16 }}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", paddingTop: 4 }}>
                  <span style={{
                    fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em",
                    color: isIv ? "var(--accent)" : "var(--info)",
                  }}>
                    {isIv ? "Interviewer" : "Candidate"}
                  </span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute-2)" }}>#{i + 1}</span>
                </div>
                <div style={{
                  fontSize: 14, lineHeight: 1.65, color: "var(--ink-2)",
                  padding: "10px 14px", borderRadius: 8,
                  border: "1px solid var(--line)",
                  background: isIv ? "var(--surf)" : "var(--bg-2)",
                }}>
                  {msg.content}
                </div>
              </div>
            );
          })}
          {(isLoading || isSpeaking) && (
            <div style={{ display: "grid", gridTemplateColumns: "88px 1fr", gap: 16 }}>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", paddingTop: 4 }}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute-2)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                  {isLoading ? "Thinking" : "Speaking"}
                </span>
              </div>
              <div style={{ padding: "12px 14px" }}>
                {isLoading
                  ? <Loader2 style={{ width: 14, height: 14, animation: "spin 1s linear infinite", color: "var(--mute)" }} />
                  : <div style={{ display: "flex", gap: 3, alignItems: "center" }}>
                      {[0, 1, 2].map((j) => (
                        <div key={j} style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--accent)", animation: `speak-dot 1s ease-in-out ${j * 0.2}s infinite` }} />
                      ))}
                    </div>
                }
              </div>
            </div>
          )}
          {ended && (
            <div style={{ textAlign: "center", padding: "24px 0", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
              Interview ended
            </div>
          )}
          {error && (
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--bad)", padding: "8px 14px", border: "1px solid var(--bad)", borderRadius: 6 }}>
              {error}
            </div>
          )}
          <div ref={transcriptEndRef} />
        </div>
      </div>

      {/* Begin overlay — sits on top until user clicks (Chrome gesture unlock) */}
      {!started && (
        <div style={{
          position: "fixed", inset: 0,
          background: "color-mix(in srgb, var(--bg) 88%, transparent)",
          backdropFilter: "blur(3px)",
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          gap: 20, zIndex: 20,
        }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.12em" }}>AI vs AI · Voice</div>
          <div style={{ fontSize: 20, fontWeight: 600, color: "var(--ink)", letterSpacing: "-0.02em", maxWidth: 420, textAlign: "center", lineHeight: 1.25 }}>{questionTitle}</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute-2)", textAlign: "center", maxWidth: "36ch", lineHeight: 1.6 }}>
            Two AIs will interview each other with voice. You watch and listen.
          </div>
          <button
            type="button"
            onClick={beginAndPlay}
            style={{ marginTop: 4, display: "inline-flex", alignItems: "center", gap: 10, padding: "11px 26px", borderRadius: 8, background: "var(--accent)", color: "var(--accent-ink)", border: "none", fontSize: 14, fontWeight: 600, cursor: "pointer", letterSpacing: "-0.01em" }}
          >
            <Play style={{ width: 16, height: 16 }} />
            Start Interview
          </button>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute-2)" }}>Audio starts on click</div>
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes speak-dot {
          0%, 100% { transform: scaleY(1); opacity: 0.6; }
          50% { transform: scaleY(1.8); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
