"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { Mic, MicOff, Loader2, Lightbulb, X } from "lucide-react";
import { useVoiceCapture } from "@/hooks/useVoiceCapture";
import { useVoicePlayback } from "@/hooks/useVoicePlayback";
import { getWhiteboardJSON } from "@/components/Whiteboard";

const Whiteboard = dynamic(
  () => import("@/components/Whiteboard").then((m) => ({ default: m.Whiteboard })),
  { ssr: false },
);

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
  const [transcript, setTranscript] = useState<Message[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [hintLevel, setHintLevel] = useState<0 | 1 | 2 | 3>(0);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const whiteboardElementsRef = useRef<readonly unknown[]>([]);
  const whiteboardStateRef = useRef<unknown>(null);
  const isStreamingRef = useRef(false);
  const hasMountedRef = useRef(false);

  const { speak, stop: stopSpeaking, isSpeaking } = useVoicePlayback();

  useEffect(() => {
    if (isSpeaking) {
      setStatus("speaking");
    } else if (status === "speaking") {
      setStatus("idle");
    }
  }, [isSpeaking, status]);

  const handleWhiteboardChange = useCallback((elements: readonly unknown[], state: unknown) => {
    whiteboardElementsRef.current = elements;
    whiteboardStateRef.current = state;
  }, []);

  useEffect(() => {
    const el = transcriptEndRef.current;
    if (el) el.scrollIntoView({ behavior: "smooth" });
  }, [transcript.length]);

  async function sendMessage(messageText: string, useHint = false) {
    if (isStreamingRef.current) return;
    isStreamingRef.current = true;
    setStatus("thinking");
    setError(null);

    const whiteboardState = getWhiteboardJSON(
      whiteboardElementsRef.current as readonly Record<string, unknown>[],
      whiteboardStateRef.current,
    );

    setTranscript((prev) => [
      ...prev,
      { role: "candidate", content: messageText, timestamp: new Date() },
    ]);

    const transcriptForApi = transcript.map((m) => ({ role: m.role, content: m.content }));
    transcriptForApi.push({ role: "candidate", content: messageText });

    try {
      const res = await fetch(`/api/interview/session/${sessionId}/message`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          message: messageText,
          whiteboardState: whiteboardState !== "[]" ? whiteboardState : undefined,
          transcriptHistory: transcriptForApi.slice(0, -1),
          hintLevel: useHint ? hintLevel : 0,
        }),
      });

      if (!res.ok || !res.body) throw new Error(`Server error: ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";

      while (true) {
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

      if (useHint && hintLevel > 0) setHintLevel(0);

      speak(cleaned);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to get response");
      setStatus("idle");
    } finally {
      isStreamingRef.current = false;
      if (!isSpeaking) setStatus("idle");
    }
  }

  const handleTranscript = useCallback(
    (text: string) => {
      void sendMessage(text);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [transcript, hintLevel, sessionId],
  );

  const { isListening, startListening, stopListening, interimTranscript, error: sttError } =
    useVoiceCapture({ onTranscript: handleTranscript });

  useEffect(() => {
    if (isListening) setStatus("listening");
    else if (status === "listening") setStatus("idle");
  }, [isListening, status]);

  useEffect(() => {
    if (hasMountedRef.current) return;
    hasMountedRef.current = true;
    if (firstInterviewerMessage) {
      setTranscript([
        { role: "interviewer", content: firstInterviewerMessage, timestamp: new Date() },
      ]);
      speak(firstInterviewerMessage);
    }
  }, [firstInterviewerMessage, speak]);

  async function endSession() {
    if (!confirm("End this voice interview and get a score?")) return;

    stopSpeaking();
    setStatus("thinking");

    const transcriptForApi = transcript.map((m) => ({ role: m.role, content: m.content }));
    const whiteboardState = getWhiteboardJSON(
      whiteboardElementsRef.current as readonly Record<string, unknown>[],
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

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", background: "var(--bg)" }}>
      <style dangerouslySetInnerHTML={{ __html: `
        .vi-bar { display:flex; align-items:center; gap:12px; padding: 10px 16px; border-bottom: 1px solid var(--line); background: var(--bg); flex-shrink:0; }
        .vi-logo { font-family: var(--font-mono); font-size: 11px; color: var(--mute); text-transform: uppercase; letter-spacing: .12em; }
        .vi-qtitle { flex:1; font-size: 14px; font-weight: 600; letter-spacing: -0.01em; color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .vi-body { display:flex; flex:1; min-height:0; }
        .vi-wb { flex:1; min-height:0; min-width:0; }
        .vi-sidebar { width: 320px; flex-shrink:0; display:flex; flex-direction:column; border-left: 1px solid var(--line); background: var(--bg); }
        .vi-tx { flex:1; overflow-y:auto; padding: 16px; display:flex; flex-direction:column; gap: 10px; min-height:0; }
        .vi-tx-msg { display:flex; flex-direction:column; gap:3px; }
        .vi-tx-msg.iv { align-items: flex-start; }
        .vi-tx-msg.cd { align-items: flex-end; }
        .vi-tx-who { font-family: var(--font-mono); font-size: 9.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .1em; }
        .vi-tx-bubble { max-width: 90%; border-radius: 10px; padding: 8px 12px; font-size: 13px; line-height: 1.5; white-space: pre-wrap; }
        .vi-tx-bubble.iv { background: var(--surf); color: var(--ink); border-top-left-radius: 3px; }
        .vi-tx-bubble.cd { background: var(--accent); color: #fff; border-top-right-radius: 3px; }
        .vi-tx-interim { font-size: 12px; color: var(--mute); font-style: italic; padding: 4px 12px; }
        .vi-strip { display:flex; align-items:center; gap:12px; padding: 12px 16px; border-top: 1px solid var(--line); flex-shrink:0; }
        .vi-mic { width:44px; height:44px; border-radius:999px; border:none; cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0; transition: background 0.15s, box-shadow 0.15s; }
        .vi-mic.idle { background: var(--surf); color: var(--ink); }
        .vi-mic.listening { background: var(--bad); color: #fff; box-shadow: 0 0 0 4px color-mix(in srgb, var(--bad) 30%, transparent); animation: mic-pulse 1s ease-in-out infinite; }
        .vi-mic.disabled { background: var(--surf); color: var(--mute); cursor: not-allowed; opacity: 0.5; }
        @keyframes mic-pulse { 0%,100%{ box-shadow: 0 0 0 4px color-mix(in srgb, var(--bad) 30%, transparent); } 50%{ box-shadow: 0 0 0 8px color-mix(in srgb, var(--bad) 15%, transparent); } }
        .vi-status { flex:1; font-family: var(--font-mono); font-size: 11.5px; color: var(--mute); }
        .vi-speaking-dot { width:8px; height:8px; border-radius:999px; background: var(--accent); animation: speak-pulse 0.8s ease-in-out infinite; flex-shrink:0; }
        @keyframes speak-pulse { 0%,100%{ opacity:1; } 50%{ opacity:0.3; } }
        .vi-hint-btn { font-family: var(--font-mono); font-size: 10.5px; padding: 4px 10px; border:1px solid var(--line); border-radius: var(--r-1); cursor: pointer; background: transparent; color: var(--mute); transition: background 0.12s, color 0.12s; }
        .vi-hint-btn:hover { background: var(--surf); color: var(--ink); }
        .vi-hint-btn.active { border-color: var(--accent); color: var(--accent); }
        .vi-err { font-family: var(--font-mono); font-size: 11px; color: var(--bad); padding: 4px 16px 8px; flex-shrink:0; }
        .vi-tx-empty { flex:1; display:flex; align-items:center; justify-content:center; font-family: var(--font-read); font-style:italic; font-size:14px; color:var(--mute-2); }
      ` }} />

      {/* Top bar */}
      <div className="vi-bar">
        <span className="vi-logo">CareerLab</span>
        <span className="vi-qtitle">{questionTitle}</span>
        <button
          onClick={() => setHintLevel((h) => ((h + 1) % 4) as 0 | 1 | 2 | 3)}
          className={`vi-hint-btn${hintLevel > 0 ? " active" : ""}`}
          title="Cycle hint level"
        >
          <Lightbulb style={{ width: 11, height: 11, display: "inline", marginRight: 4 }} />
          {hintLevel === 0 ? "Hint" : `Hint L${hintLevel}`}
        </button>
        <button
          onClick={endSession}
          className="btn"
          style={{ fontSize: 12, padding: "5px 14px" }}
        >
          <X style={{ width: 12, height: 12, display: "inline", marginRight: 4 }} />
          End
        </button>
      </div>

      {/* Main area */}
      <div className="vi-body">
        {/* Whiteboard */}
        <div className="vi-wb">
          <Whiteboard onChange={handleWhiteboardChange} />
        </div>

        {/* Transcript sidebar */}
        <div className="vi-sidebar">
          <div className="vi-tx">
            {transcript.length === 0 ? (
              <div className="vi-tx-empty">Conversation will appear here</div>
            ) : (
              transcript.map((msg, i) => {
                const isIv = msg.role === "interviewer";
                return (
                  <div key={i} className={`vi-tx-msg ${isIv ? "iv" : "cd"}`}>
                    <span className="vi-tx-who">{isIv ? "Interviewer" : "You"}</span>
                    <div className={`vi-tx-bubble ${isIv ? "iv" : "cd"}`}>{msg.content}</div>
                  </div>
                );
              })
            )}
            {isListening && interimTranscript && (
              <div className="vi-tx-interim">{interimTranscript}</div>
            )}
            {status === "thinking" && (
              <div className="vi-tx-msg iv">
                <span className="vi-tx-who">Interviewer</span>
                <div className="vi-tx-bubble iv">
                  <Loader2 style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} />
                </div>
              </div>
            )}
            <div ref={transcriptEndRef} />
          </div>

          {combinedError && (
            <div className="vi-err">{combinedError}</div>
          )}

          {/* Bottom strip */}
          <div className="vi-strip">
            <button
              onClick={toggleMic}
              className={`vi-mic${isListening ? " listening" : status === "thinking" || status === "speaking" ? " disabled" : " idle"}`}
              title={isListening ? "Stop recording" : "Start recording"}
              disabled={status === "thinking" || status === "speaking"}
            >
              {isListening ? (
                <MicOff style={{ width: 20, height: 20 }} />
              ) : (
                <Mic style={{ width: 20, height: 20 }} />
              )}
            </button>
            <span className="vi-status">{statusText[status]}</span>
            {isSpeaking && <div className="vi-speaking-dot" />}
          </div>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `@keyframes spin { to { transform: rotate(360deg); } }` }} />
    </div>
  );
}
