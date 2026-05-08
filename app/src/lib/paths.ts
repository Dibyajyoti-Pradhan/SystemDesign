import path from "node:path";
import type { Track } from "@/lib/tracks";

// Re-export client-safe types/utilities for consumers that import from paths.
export { TRACKS, TRACK_LABELS, isTrack, parseTrack } from "@/lib/tracks";
export type { Track };

export const REPO_ROOT = path.resolve(process.cwd(), "..");
export const CONTENT_ROOT = path.join(REPO_ROOT, "content");

/**
 * Per-track filesystem paths. Sources sit at the repo root under the track
 * name; generated MDX content sits under content/<track>/.
 */
export interface TrackPaths {
  studyGuideSources: string;
  questionsSources: string;
  topicsContent: string;
  questionsContent: string;
  cheatsheetsContent: string;
}

export const TRACK_PATHS: Record<Track, TrackPaths> = {
  "system-design": {
    studyGuideSources: path.join(REPO_ROOT, "system-design/study-guide"),
    questionsSources: path.join(REPO_ROOT, "system-design/design-questions"),
    topicsContent: path.join(CONTENT_ROOT, "system-design/topics"),
    questionsContent: path.join(CONTENT_ROOT, "system-design/questions"),
    cheatsheetsContent: path.join(CONTENT_ROOT, "system-design/cheatsheets"),
  },
  coding: {
    studyGuideSources: path.join(REPO_ROOT, "coding/study-guide"),
    questionsSources: path.join(REPO_ROOT, "coding/interview-questions"),
    topicsContent: path.join(CONTENT_ROOT, "coding/topics"),
    questionsContent: path.join(CONTENT_ROOT, "coding/questions"),
    cheatsheetsContent: path.join(CONTENT_ROOT, "coding/cheatsheets"),
  },
};

