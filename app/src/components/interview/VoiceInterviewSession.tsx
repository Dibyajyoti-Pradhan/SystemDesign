"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { Mic, MicOff, Loader2, Lightbulb, X } from "lucide-react";
import { useVoiceCapture } from "@/hooks/useVoiceCapture";
import { useVoicePlayback } from "@/hooks/useVoicePlayback";
import {
  getWhiteboardJSON,
  type WhiteboardElements,
  type WhiteboardAppState,
} from "@/components/Whiteboard";

const Whiteboard = dynamic(
  () => import("@/components/Whiteboard").then((m) => ({ default: m.Whiteboard })),
  { ssr: false },
);

type HintLevel = 0 | 1 | 2 | 3;

interface Message {
  role: "interviewer" | "candidate";
  content: string;
  timestamp: Date;
}

type Status = "idle" | "listening" | "thinking" | "speaking";

interface VoiceInterviewSessionProps {
  sessionId: number;
  questionTitle: string;
  firstInterviewerMessage?: string;
}

export function VoiceInterviewSession({
  sessionId,
  questionTitle,
  firstInterviewerMessage,
}: VoiceInterviewSessionProps) {
  const router = useRouter();
  const [started, setStarted] = useState(false);
  const [transcript, setTranscript] = useState<Message[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [hintLevel, setHintLevel] = useState<HintLevel>(0);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const whiteboardElementsRef = useRef<WhiteboardElements>([]);
  const whiteboardStateRef = useRef<WhiteboardAppState>(null);
  const isStreamingRef = useRef(false);
  const hasMountedRef = useRef(false);
  const openingSpokenRef = useRef(false);

  // Refs that mirror state so async callbacks see fresh values without
  // having to re-create the callback for every change (avoids stale-closure
  // bugs when handleTranscript is fired from the speech-recognition event).
  const transcriptRef = useRef<Message[]>([]);
  const hintLevelRef = useRef<HintLevel>(0);
  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);
  useEffect(() => {
    hintLevelRef.current = hintLevel;
  }, [hintLevel]);

  const { speak, speakWhenReady, stop: stopSpeaking, isSpeaking } = useVoicePlayback();
  const isSpeakingRef = useRef(false);
  useEffect(() => {
    isSpeakingRef.current = isSpeaking;
    if (isSpeaking) {
      setStatus("speaking");
    } else {
      // Only drop back to idle from the speaking state — don't stomp on
      // listening/thinking transitions that may have happened concurrently.
      setStatus((cur) => (cur === "speaking" ? "idle" : cur));
    }
  }, [isSpeaking]);

  const handleWhiteboardChange = useCallback(
    (elements: WhiteboardElements, state: WhiteboardAppState) => {
      whiteboardElementsRef.current = elements;
      whiteboardStateRef.current = state;
    },
    [],
  );

  useEffect(() => {
    const el = transcriptEndRef.current;
    if (el) el.scrollIntoView({ behavior: "smooth" });
  }, [transcript.length]);

  const sendMessage = useCallback(
    async (messageText: string, useHint = false) => {
      if (isStreamingRef.current) return;
      isStreamingRef.current = true;
      setStatus("thinking");
      setError(null);

      const whiteboardState = getWhiteboardJSON(
        whiteboardElementsRef.current,
        whiteboardStateRef.current,
      );

      setTranscript((prev) => [
        ...prev,
        { role: "candidate", content: messageText, timestamp: new Date() },
      ]);

      // Read live transcript from the ref so concurrent sends never see a stale snapshot.
      const transcriptForApi = transcriptRef.current.map((m) => ({
        role: m.role,
        content: m.content,
      }));
      transcriptForApi.push({ role: "candidate", content: messageText });

      const currentHint = hintLevelRef.current;

      try {
        const res = await fetch(`/api/interview/session/${sessionId}/message`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            message: messageText,
            whiteboardState: whiteboardState !== "[]" ? whiteboardState : undefined,
            transcriptHistory: transcriptForApi.slice(0, -1),
            hintLevel: useHint ? currentHint : 0,
          }),
        });

        if (!res.ok || !res.body) throw new Error(`Server error: ${res.status}`);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let accumulated = "";

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          accumulated += decoder.decode(value, { stream: true });
        }

        if (!accumulated) throw new Error("Empty response");
        if (accumulated.includes("[error:")) {
          const match = accumulated.match(/\[error: ([^\]]+)\]/);
          throw new Error(match ? match[1] : "Stream error");
        }

        const cleaned = accumulated.replace(/<<INTERVIEW_END>>/g, "").trimEnd();
        setTranscript((prev) => [
          ...prev,
          { role: "interviewer", content: cleaned, timestamp: new Date() },
        ]);

        if (useHint && currentHint > 0) setHintLevel(0);

        speak(cleaned);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to get response");
        // Make sure we don't get stuck in "thinking" if an error fires before
        // the speech-synthesis effect has a chance to flip status back.
        setStatus((cur) => (cur === "thinking" ? "idle" : cur));
      } finally {
        isStreamingRef.current = false;
        // Read isSpeaking from the ref to avoid stale-closure misreads.
        if (!isSpeakingRef.current) {
          setStatus((cur) => (cur === "thinking" ? "idle" : cur));
        }
      }
    },
    [sessionId, speak],
  );

  const handleTranscript = useCallback(
    (text: string) => {
      void sendMessage(text);
    },
    [sendMessage],
  );

  const { isListening, startListening, stopListening, interimTranscript, error: sttError } =
    useVoiceCapture({ onTranscript: handleTranscript });

  useEffect(() => {
    if (isListening) {
      setStatus("listening");
    } else {
      setStatus((cur) => (cur === "listening" ? "idle" : cur));
    }
  }, [isListening]);

  // Populate transcript on mount (no audio yet — browser requires user gesture).
  useEffect(() => {
    if (hasMountedRef.current) return;
    hasMountedRef.current = true;
    if (firstInterviewerMessage) {
      setTranscript([
        { role: "interviewer", content: firstInterviewerMessage, timestamp: new Date() },
      ]);
    }
  }, [firstInterviewerMessage]);

  // Called from the start overlay — this IS a user gesture so speech is allowed.
  // Use speak() (immediate) not speakWhenReady() — the deferred voiceschanged path
  // fires outside the gesture handler and Chrome silently blocks it.
  function startSession() {
    setStarted(true);
    if (firstInterviewerMessage) speak(firstInterviewerMessage);
  }

  async function endSession() {
    if (!confirm("End this voice interview and get a score?")) return;

    stopSpeaking();
    setStatus("thinking");

    const transcriptForApi = transcriptRef.current.map((m) => ({
      role: m.role,
      content: m.content,
    }));
    const whiteboardState = getWhiteboardJSON(
      whiteboardElementsRef.current,
      whiteboardStateRef.current,
    );

    try {
      const res = await fetch(`/api/interview/session/${sessionId}/score`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          transcriptHistory: transcriptForApi,
          whiteboardSnapshot: whiteboardState !== "[]" ? whiteboardState : undefined,
        }),
      });

      if (!res.ok) throw new Error(`Scoring failed: ${res.status}`);
      router.push(`/interview/sessions/${sessionId}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to end session");
      setStatus("idle");
    }
  }

  function toggleMic() {
    if (status === "thinking" || status === "speaking") return;
    if (isListening) {
      stopListening();
    } else {
      stopSpeaking();
      startListening();
    }
  }

  const statusText: Record<Status, string> = {
    idle: "Press mic to speak",
    listening: "Listening…",
    thinking: "Interviewer thinking…",
    speaking: "Interviewer speaking…",
  };

  const combinedError = error ?? sttError;
  const micDisabled = status === "thinking" || status === "speaking";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "var(--bg)", color: "var(--ink)", fontFamily: "var(--font-ui)" }}>
      {/* Top bar — matches .topbar pattern */}
      <header style={{ flexShrink: 0, height: 44, display: "flex", alignItems: "center", padding: "0 18px", borderBottom: "1px solid var(--line)", gap: 14, background: "var(--bg)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }} className="crumbs">
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.1em" }}>CareerLab</span>
          <span style={{ color: "var(--subtle)" }}>›</span>
          <b style={{ color: "var(--ink-2)", fontWeight: 500, fontSize: 13, letterSpacing: "-0.005em", maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{questionTitle}</b>
        </div>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          onClick={() => setHintLevel((h) => ((h + 1) % 4) as HintLevel)}
          className="btn btn--ghost"
          style={{ fontSize: 12, padding: "4px 10px", gap: 5, color: hintLevel > 0 ? "var(--accent)" : undefined }}
          title="Cycle hint level"
        >
          <Lightbulb style={{ width: 12, height: 12 }} />
          {hintLevel === 0 ? "Hint" : `Hint L${hintLevel}`}
        </button>
        <button type="button" onClick={endSession} className="btn" style={{ fontSize: 12, padding: "4px 10px", gap: 5 }}>
          <X style={{ width: 12, height: 12 }} />
          End
        </button>
      </header>

      {/* Main area */}
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* Whiteboard */}
        <div style={{ flex: 1, minHeight: 0, minWidth: 0, position: "relative" }}>
          <Whiteboard onChange={handleWhiteboardChange} />
          {!started && (
            <div style={{
              position: "absolute", inset: 0,
              background: "color-mix(in srgb, var(--bg) 82%, transparent)",
              backdropFilter: "blur(2px)",
              display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
              gap: 18, zIndex: 10,
            }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.12em" }}>Voice Interview · Beta</div>
              <div style={{ fontSize: 20, fontWeight: 600, color: "var(--ink)", letterSpacing: "-0.02em", maxWidth: 400, textAlign: "center", lineHeight: 1.25 }}>{questionTitle}</div>
              <button
                type="button"
                onClick={startSession}
                style={{ marginTop: 4, display: "inline-flex", alignItems: "center", gap: 10, padding: "11px 26px", borderRadius: 8, background: "var(--accent)", color: "var(--accent-ink)", border: "none", fontSize: 14, fontWeight: 600, cursor: "pointer", letterSpacing: "-0.01em" }}
              >
                <Mic style={{ width: 16, height: 16 }} />
                Begin Interview
              </button>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute-2)" }}>Interviewer will speak when you click</div>
            </div>
          )}
        </div>

        {/* Transcript sidebar */}
        <aside style={{ width: 300, flexShrink: 0, display: "flex", flexDirection: "column", borderLeft: "1px solid var(--line)", background: "var(--bg-2)" }}>
          {/* Sidebar header */}
          <div style={{ flexShrink: 0, padding: "10px 16px 8px", borderBottom: "1px solid var(--line)" }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--mute)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Interviewer</span>
          </div>

          {/* Messages */}
          <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "14px 14px 6px", display: "flex", flexDirection: "column", gap: 10 }}>
            {transcript.length === 0 ? (
              <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-read)", fontStyle: "italic", fontSize: 13, color: "var(--mute-2)" }}>
                Conversation will appear here
              </div>
            ) : (
              transcript.map((msg, i) => {
                const isIv = msg.role === "interviewer";
                return (
                  <div key={i} style={{ display: "flex", flexDirection: "column", gap: 3, alignItems: isIv ? "flex-start" : "flex-end" }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 9.5, color: "var(--mute-2)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      {isIv ? "Interviewer" : "You"}
                    </span>
                    <div style={{
                      maxWidth: "92%", borderRadius: isIv ? "3px 10px 10px 10px" : "10px 3px 10px 10px",
                      padding: "8px 12px", fontSize: 13, lineHeight: 1.55, whiteSpace: "pre-wrap",
                      background: isIv ? "var(--surf)" : "var(--accent)",
                      color: isIv ? "var(--ink-2)" : "var(--accent-ink)",
                    }}>
                      {msg.content}
                    </div>
                  </div>
                );
              })
            )}
            {isListening && interimTranscript && (
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute)", fontStyle: "italic", padding: "2px 4px" }}>
                {interimTranscript}
              </div>
            )}
            {status === "thinking" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 3, alignItems: "flex-start" }}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 9.5, color: "var(--mute-2)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Interviewer</span>
                <div style={{ background: "var(--surf)", borderRadius: "3px 10px 10px 10px", padding: "8px 12px" }}>
                  <Loader2 style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} />
                </div>
              </div>
            )}
            <div ref={transcriptEndRef} />
          </div>

          {combinedError && (
            <div style={{ flexShrink: 0, fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--bad)", padding: "6px 16px 8px", borderTop: "1px solid var(--line)" }}>
              {combinedError}
            </div>
          )}

          {/* Voice strip */}
          <div style={{ flexShrink: 0, borderTop: "1px solid var(--line)", padding: "12px 14px", display: "flex", alignItems: "center", gap: 10, background: "var(--surf)" }}>
            <button
              type="button"
              onClick={toggleMic}
              title={isListening ? "Stop" : "Speak"}
              disabled={micDisabled}
              style={{
                width: 40, height: 40, borderRadius: "50%", border: "none", cursor: micDisabled ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "background 0.15s",
                background: isListening ? "var(--bad)" : "var(--surf-3)",
                color: isListening ? "#fff" : "var(--ink)",
                opacity: micDisabled ? 0.4 : 1,
                animation: isListening ? "mic-pulse 1s ease-in-out infinite" : undefined,
              }}
            >
              {isListening ? <MicOff style={{ width: 18, height: 18 }} /> : <Mic style={{ width: 18, height: 18 }} />}
            </button>
            <span style={{ flex: 1, fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--mute)" }}>
              {statusText[status]}
            </span>
            {isSpeaking && (
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--accent)", animation: "speak-pulse 0.8s ease-in-out infinite", flexShrink: 0 }} />
            )}
          </div>
        </aside>
      </div>
      <style>{`
        @keyframes mic-pulse { 0%,100%{ box-shadow: 0 0 0 4px color-mix(in srgb, var(--bad) 25%, transparent); } 50%{ box-shadow: 0 0 0 8px color-mix(in srgb, var(--bad) 10%, transparent); } }
        @keyframes speak-pulse { 0%,100%{ opacity:1; } 50%{ opacity:0.3; } }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
