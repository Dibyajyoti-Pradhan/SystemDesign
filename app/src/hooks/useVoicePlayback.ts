"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseVoicePlaybackReturn {
  speak: (text: string) => void;
  stop: () => void;
  isSpeaking: boolean;
}

export function useVoicePlayback(): UseVoicePlaybackReturn {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);

  // Voices in many browsers (notably Chrome) load asynchronously — listening
  // to voiceschanged ensures we have them by the time we speak().
  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const refresh = () => {
      voicesRef.current = window.speechSynthesis.getVoices();
    };
    refresh();
    window.speechSynthesis.addEventListener("voiceschanged", refresh);
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", refresh);
      window.speechSynthesis.cancel();
    };
  }, []);

  const stop = useCallback(() => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
  }, []);

  const speak = useCallback(
    (text: string) => {
      if (typeof window === "undefined" || !window.speechSynthesis) return;

      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.95;
      utterance.pitch = 1.0;

      const voices =
        voicesRef.current.length > 0
          ? voicesRef.current
          : window.speechSynthesis.getVoices();
      const preferred =
        voices.find((v) => v.lang === "en-GB" && v.name.includes("Neural")) ??
        voices.find((v) => v.lang === "en-GB") ??
        voices.find((v) => v.lang === "en-US" && v.name.includes("Neural")) ??
        voices.find((v) => v.lang.startsWith("en"));
      if (preferred) utterance.voice = preferred;

      utterance.onstart = () => setIsSpeaking(true);
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);

      utteranceRef.current = utterance;
      window.speechSynthesis.speak(utterance);
      setIsSpeaking(true);
    },
    [],
  );

  return { speak, stop, isSpeaking };
}
