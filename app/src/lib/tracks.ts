/**
 * Track names + labels — client-safe (no node: imports).
 *
 * Server-only filesystem paths live in @/lib/paths.
 */
export const TRACKS = ["system-design", "coding"] as const;
export type Track = (typeof TRACKS)[number];

export const TRACK_LABELS: Record<Track, string> = {
  "system-design": "System Design",
  coding: "Coding",
};

export function isTrack(value: string): value is Track {
  return (TRACKS as readonly string[]).includes(value);
}

export function parseTrack(value: string | undefined): Track | null {
  if (!value) return null;
  return isTrack(value) ? value : null;
}
