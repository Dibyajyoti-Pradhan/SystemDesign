"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** Distinct voice personas — interviewer vs candidate get different timbres. */
export type VoicePersona = "interviewer" | "candidate";

export interface SpeakOptions {
  persona?: VoicePersona;
  /** Fires per-word as Web Speech advances through the utterance. */
  onBoundary?: (charIndex: number, charLength: number) => void;
  onStart?: () => void;
  onEnd?: () => void;
}

interface UseVoicePlaybackReturn {
  speak: (text: string, opts?: SpeakOptions) => void;
  /** Queue text but wait for voices to load if they haven't yet. */
  speakWhenReady: (text: string, opts?: SpeakOptions) => void;
  stop: () => void;
  isSpeaking: boolean;
  voicesReady: boolean;
}

// Rank candidates so we always pick the most natural-sounding voice the OS has.
const QUALITY_KEYWORDS = ["premium", "enhanced", "neural", "natural"];
const INTERVIEWER_NAMES = ["Samantha", "Karen", "Allison", "Ava", "Susan", "Serena"];
const CANDIDATE_NAMES = ["Daniel", "Alex", "Tom", "Aaron", "Fred", "Oliver"];

function rankVoice(v: SpeechSynthesisVoice, preferredNames: string[]): number {
  let score = 0;
  const name = v.name.toLowerCase();
  for (const kw of QUALITY_KEYWORDS) if (name.includes(kw)) score += 10;
  if (preferredNames.some((n) => v.name.includes(n))) score += 6;
  if (v.lang === "en-US") score += 4;
  else if (v.lang === "en-GB") score += 3;
  else if (v.lang.startsWith("en")) score += 1;
  if (v.localService) score += 2; // local = faster, no network blip
  return score;
}

function pickVoice(
  voices: SpeechSynthesisVoice[],
  persona: VoicePersona,
): SpeechSynthesisVoice | undefined {
  const preferred = persona === "interviewer" ? INTERVIEWER_NAMES : CANDIDATE_NAMES;
  const ranked = voices
    .filter((v) => v.lang.startsWith("en"))
    .map((v) => ({ v, score: rankVoice(v, preferred) }))
    .sort((a, b) => b.score - a.score);
  return ranked[0]?.v;
}

export function useVoicePlayback(): UseVoicePlaybackReturn {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [voicesReady, setVoicesReady] = useState(false);

  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);
  const pendingRef = useRef<{ text: string; opts?: SpeakOptions } | null>(null);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  const doSpeak = useCallback((text: string, opts?: SpeakOptions) => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    const persona = opts?.persona ?? "interviewer";

    // Slight rate + pitch differentiation so the two AIs (and the interviewer in
    // AI-vs-Human) feel like distinct people.
    if (persona === "interviewer") {
      utterance.rate = 0.96;
      utterance.pitch = 1.0;
    } else {
      utterance.rate = 0.98;
      utterance.pitch = 0.93;
    }

    const voices = voicesRef.current.length
      ? voicesRef.current
      : window.speechSynthesis.getVoices();
    const picked = pickVoice(voices, persona);
    if (picked) utterance.voice = picked;

    utterance.onstart = () => {
      setIsSpeaking(true);
      opts?.onStart?.();
    };
    utterance.onend = () => {
      setIsSpeaking(false);
      opts?.onEnd?.();
    };
    utterance.onerror = () => {
      setIsSpeaking(false);
      opts?.onEnd?.();
    };
    if (opts?.onBoundary) {
      utterance.onboundary = (ev: SpeechSynthesisEvent) => {
        opts.onBoundary!(ev.charIndex, ev.charLength ?? 0);
      };
    }

    utteranceRef.current = utterance;
    window.speechSynthesis.speak(utterance);
    setIsSpeaking(true);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const refresh = () => {
      const v = window.speechSynthesis.getVoices();
      if (v.length > 0) {
        voicesRef.current = v;
        setVoicesReady(true);
        if (pendingRef.current) {
          const { text, opts } = pendingRef.current;
          pendingRef.current = null;
          doSpeak(text, opts);
        }
      }
    };
    refresh();
    window.speechSynthesis.addEventListener("voiceschanged", refresh);
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", refresh);
      window.speechSynthesis.cancel();
    };
  }, [doSpeak]);

  const speak = useCallback((text: string, opts?: SpeakOptions) => {
    doSpeak(text, opts);
  }, [doSpeak]);

  const speakWhenReady = useCallback((text: string, opts?: SpeakOptions) => {
    if (voicesRef.current.length > 0) doSpeak(text, opts);
    else pendingRef.current = { text, opts };
  }, [doSpeak]);

  const stop = useCallback(() => {
    pendingRef.current = null;
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
  }, []);

  return { speak, speakWhenReady, stop, isSpeaking, voicesReady };
}
