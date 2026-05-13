import { NextRequest } from "next/server";
import { apiAuthGuard } from "@/lib/auth-guards";
import { NextResponse } from "next/server";
import logger from "@/lib/logger";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Voice picks. Cross-gender pairing for instant observer differentiation —
// two same-gender voices (Brian + Liam) blurred together under headphones.
//   Interviewer → Brian  (deep, calm, senior US male)
//   Candidate   → Rachel (confident, articulate US female)
const VOICE_IDS = {
  interviewer: "nPczCjzI2devNBz1zQrb", // Brian
  candidate:   "21m00Tcm4TlvDq8ikWAM", // Rachel
} as const;

type Persona = keyof typeof VOICE_IDS;

interface TtsBody {
  text: string;
  persona?: Persona;
}

/**
 * Streams ElevenLabs TTS audio (mpeg) back to the client.
 * Uses the `eleven_turbo_v2_5` model — lowest latency among ElevenLabs
 * production tiers (~300-400ms first byte) with quality close to multilingual.
 * The client plays it via an <audio> element to keep DOM simple.
 */
export async function POST(req: NextRequest) {
  const guard = await apiAuthGuard();
  if (guard instanceof NextResponse) return guard;

  const apiKey = process.env.ELEVENLABS_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "ELEVENLABS_API_KEY not configured" },
      { status: 503 },
    );
  }

  let body: TtsBody;
  try {
    body = (await req.json()) as TtsBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const text = (body.text ?? "").trim();
  if (!text) return NextResponse.json({ error: "Empty text" }, { status: 400 });
  const persona: Persona = body.persona === "candidate" ? "candidate" : "interviewer";
  const voiceId = VOICE_IDS[persona];

  // Clip very long inputs — ElevenLabs' turbo model handles a lot but a single
  // request shouldn't blow past a typical interview turn.
  const safeText = text.length > 4_000 ? text.slice(0, 4_000) : text;

  const t0 = performance.now();
  const upstream = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}/stream?optimize_streaming_latency=2&output_format=mp3_44100_128`,
    {
      method: "POST",
      headers: {
        "xi-api-key": apiKey,
        "accept": "audio/mpeg",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        text: safeText,
        model_id: "eleven_turbo_v2_5",
        // Small voice tweaks per persona — interviewer slower/steadier,
        // candidate slightly more energetic.
        voice_settings:
          persona === "interviewer"
            ? { stability: 0.55, similarity_boost: 0.75, style: 0.15, use_speaker_boost: true }
            : { stability: 0.45, similarity_boost: 0.70, style: 0.35, use_speaker_boost: true },
      }),
    },
  );

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    logger.warn(
      { status: upstream.status, detail: detail.slice(0, 200), persona, len: safeText.length },
      "[tts/stream] elevenlabs error",
    );
    return NextResponse.json(
      { error: `ElevenLabs ${upstream.status}: ${detail.slice(0, 200)}` },
      { status: 502 },
    );
  }

  logger.info(
    { persona, voiceId, textLen: safeText.length, firstByteMs: Math.round(performance.now() - t0) },
    "[tts/stream] streaming",
  );

  return new Response(upstream.body, {
    headers: {
      "content-type": "audio/mpeg",
      "cache-control": "no-store",
      "x-accel-buffering": "no",
    },
  });
}
