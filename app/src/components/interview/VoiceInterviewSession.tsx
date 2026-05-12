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
  const [transcript, setTranscript] = useState<Message[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [hintLevel, setHintLevel] = useState<HintLevel>(0);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const whiteboardElementsRef = useRef<WhiteboardElements>([]);
  const whiteboardStateRef = useRef<WhiteboardAppState>(null);
  const isStreamingRef = useRef(false);
  const hasMountedRef = useRef(false);

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

  const { speak, stop: stopSpeaking, isSpeaking } = useVoicePlayback();
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
    <div className="flex flex-col h-screen overflow-hidden bg-background">
      {/* Top bar */}
      <header className="shrink-0 border-b px-4 py-2 flex items-center gap-3 bg-background">
        <span className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
          CareerLab
        </span>
        <span className="text-sm font-semibold flex-1 truncate">{questionTitle}</span>
        <button
          type="button"
          onClick={() => setHintLevel((h) => ((h + 1) % 4) as HintLevel)}
          className={`inline-flex items-center gap-1 text-xs font-mono px-2.5 py-1 rounded border transition-colors ${
            hintLevel > 0
              ? "border-primary text-primary"
              : "border-input text-muted-foreground hover:text-foreground hover:bg-accent"
          }`}
          title="Cycle hint level"
        >
          <Lightbulb className="h-3 w-3" />
          {hintLevel === 0 ? "Hint" : `Hint L${hintLevel}`}
        </button>
        <button
          type="button"
          onClick={endSession}
          className="inline-flex items-center gap-1 text-xs px-3 py-1 rounded border border-input hover:bg-accent"
        >
          <X className="h-3 w-3" />
          End
        </button>
      </header>

      {/* Main area */}
      <div className="flex flex-1 min-h-0">
        {/* Whiteboard */}
        <div className="flex-1 min-h-0" style={{ minHeight: 300 }}>
          <Whiteboard onChange={handleWhiteboardChange} />
        </div>

        {/* Transcript sidebar */}
        <aside className="w-80 shrink-0 flex flex-col border-l bg-background">
          <div className="flex-1 min-h-0 overflow-y-auto p-4 flex flex-col gap-2.5">
            {transcript.length === 0 ? (
              <div className="flex-1 flex items-center justify-center text-sm italic text-muted-foreground">
                Conversation will appear here
              </div>
            ) : (
              transcript.map((msg, i) => {
                const isIv = msg.role === "interviewer";
                return (
                  <div
                    key={i}
                    className={`flex flex-col gap-1 ${isIv ? "items-start" : "items-end"}`}
                  >
                    <span className="text-[9.5px] font-mono uppercase tracking-widest text-muted-foreground">
                      {isIv ? "Interviewer" : "You"}
                    </span>
                    <div
                      className={`max-w-[90%] rounded-lg px-3 py-2 text-[13px] leading-relaxed whitespace-pre-wrap ${
                        isIv
                          ? "bg-muted text-foreground rounded-tl-sm"
                          : "bg-primary text-primary-foreground rounded-tr-sm"
                      }`}
                    >
                      {msg.content}
                    </div>
                  </div>
                );
              })
            )}
            {isListening && interimTranscript && (
              <div className="text-xs italic text-muted-foreground px-3 py-1">
                {interimTranscript}
              </div>
            )}
            {status === "thinking" && (
              <div className="flex flex-col gap-1 items-start">
                <span className="text-[9.5px] font-mono uppercase tracking-widest text-muted-foreground">
                  Interviewer
                </span>
                <div className="max-w-[90%] rounded-lg rounded-tl-sm px-3 py-2 bg-muted">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                </div>
              </div>
            )}
            <div ref={transcriptEndRef} />
          </div>

          {combinedError && (
            <div className="shrink-0 text-xs font-mono text-destructive px-4 py-1.5 border-t">
              {combinedError}
            </div>
          )}

          {/* Voice strip */}
          <div className="shrink-0 border-t px-4 py-3 flex items-center gap-3 bg-background">
            <button
              type="button"
              onClick={toggleMic}
              title={isListening ? "Stop recording" : "Start recording"}
              disabled={micDisabled}
              className={`w-11 h-11 rounded-full flex items-center justify-center shrink-0 transition-colors ${
                isListening
                  ? "bg-destructive text-destructive-foreground animate-pulse"
                  : micDisabled
                    ? "bg-muted text-muted-foreground opacity-50 cursor-not-allowed"
                    : "bg-muted text-foreground hover:bg-accent"
              }`}
            >
              {isListening ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
            </button>
            <span className="flex-1 text-xs font-mono text-muted-foreground">
              {statusText[status]}
            </span>
            {isSpeaking && (
              <div className="h-2 w-2 rounded-full bg-primary animate-pulse shrink-0" />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
