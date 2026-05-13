"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface SpeechRecognitionResult {
  readonly isFinal: boolean;
  readonly [index: number]: { readonly transcript: string };
}

interface SpeechRecognitionResultList {
  readonly length: number;
  readonly resultIndex: number;
  readonly [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
}

interface ISpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

interface ISpeechRecognitionConstructor {
  new (): ISpeechRecognition;
}

declare global {
  interface Window {
    SpeechRecognition?: ISpeechRecognitionConstructor;
    webkitSpeechRecognition?: ISpeechRecognitionConstructor;
  }
}

interface UseVoiceCaptureOptions {
  /** Called once per turn when the candidate has stopped talking. */
  onTranscript: (text: string) => void;
  /** Called whenever new interim text arrives — used for barge-in detection. */
  onInterim?: (text: string) => void;
  /** Silence (in ms) after the last word before we commit the turn. */
  silenceMs?: number;
}

interface UseVoiceCaptureReturn {
  transcript: string;
  interimTranscript: string;
  isListening: boolean;
  startListening: () => void;
  stopListening: () => void;
  /** Throw away anything in progress without firing onTranscript. */
  cancelListening: () => void;
  error: string | null;
}

/**
 * Continuous speech capture with silence-based commit.
 *
 * Real candidates think out loud — they pause, ramble, restart. We keep the
 * recognizer running through pauses and only fire `onTranscript` once a stretch
 * of silence (~1.5s by default) follows the last bit of speech. `stopListening`
 * commits immediately; `cancelListening` discards.
 */
export function useVoiceCapture({
  onTranscript,
  onInterim,
  silenceMs = 1500,
}: UseVoiceCaptureOptions): UseVoiceCaptureReturn {
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<ISpeechRecognition | null>(null);
  const finalBufferRef = useRef("");
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  const onInterimRef = useRef(onInterim);
  const silenceMsRef = useRef(silenceMs);
  const wantsRunningRef = useRef(false);

  useEffect(() => { onTranscriptRef.current = onTranscript; }, [onTranscript]);
  useEffect(() => { onInterimRef.current = onInterim; }, [onInterim]);
  useEffect(() => { silenceMsRef.current = silenceMs; }, [silenceMs]);

  const clearSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  }, []);

  const commit = useCallback(() => {
    clearSilenceTimer();
    const text = finalBufferRef.current.trim();
    finalBufferRef.current = "";
    setInterimTranscript("");
    setTranscript("");
    wantsRunningRef.current = false;
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch {}
    }
    if (text) onTranscriptRef.current(text);
  }, [clearSilenceTimer]);

  const armSilenceTimer = useCallback(() => {
    clearSilenceTimer();
    silenceTimerRef.current = setTimeout(() => {
      if (finalBufferRef.current.trim()) commit();
    }, silenceMsRef.current);
  }, [clearSilenceTimer, commit]);

  useEffect(() => () => {
    clearSilenceTimer();
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch {}
    }
  }, [clearSilenceTimer]);

  const startListening = useCallback(() => {
    const SpeechRecognitionAPI =
      typeof window !== "undefined"
        ? (window.SpeechRecognition ?? window.webkitSpeechRecognition)
        : undefined;

    if (!SpeechRecognitionAPI) {
      setError("Speech recognition is not supported in this browser.");
      return;
    }

    // Abort any existing instance — Safari in particular can leak.
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch {}
    }
    clearSilenceTimer();
    finalBufferRef.current = "";

    const recognition = new SpeechRecognitionAPI();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => {
      setIsListening(true);
      setError(null);
      setTranscript("");
      setInterimTranscript("");
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        if (r.isFinal) {
          finalBufferRef.current += (finalBufferRef.current ? " " : "") + r[0].transcript.trim();
        } else {
          interim += r[0].transcript;
        }
      }
      const combined = (finalBufferRef.current + " " + interim).trim();
      setInterimTranscript(interim);
      setTranscript(combined);
      if (combined && onInterimRef.current) onInterimRef.current(combined);
      // Any speech arrives → reset the silence timer; commit fires after silenceMs
      // of nothing further.
      armSilenceTimer();
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error !== "aborted" && event.error !== "no-speech") {
        setError(`Speech recognition: ${event.error}`);
      }
      // For no-speech, the recognizer ends on its own; if the user still wants
      // to be listening we'll restart in onend.
    };

    recognition.onend = () => {
      // Safari/Chrome both fire onend on idle. If the user hasn't asked to stop
      // and we still have buffered text waiting on the silence timer, restart so
      // the timer can fire; otherwise mark the session as ended.
      if (wantsRunningRef.current) {
        try { recognition.start(); return; } catch {}
      }
      setIsListening(false);
      setInterimTranscript("");
    };

    recognitionRef.current = recognition;
    wantsRunningRef.current = true;
    try {
      recognition.start();
    } catch (err) {
      // Most commonly: another instance still alive in Safari.
      setError(err instanceof Error ? err.message : "Failed to start recognition");
      wantsRunningRef.current = false;
    }
  }, [armSilenceTimer, clearSilenceTimer]);

  const stopListening = useCallback(() => {
    // Manual stop = commit whatever's in the buffer immediately.
    commit();
    setIsListening(false);
  }, [commit]);

  const cancelListening = useCallback(() => {
    clearSilenceTimer();
    finalBufferRef.current = "";
    wantsRunningRef.current = false;
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch {}
    }
    setIsListening(false);
    setInterimTranscript("");
    setTranscript("");
  }, [clearSilenceTimer]);

  return {
    transcript,
    interimTranscript,
    isListening,
    startListening,
    stopListening,
    cancelListening,
    error,
  };
}
