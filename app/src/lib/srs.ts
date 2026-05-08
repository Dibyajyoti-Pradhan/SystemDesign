/**
 * SM-2 spaced-repetition scheduler with refinements.
 *
 * Rating scale (1-4):
 *   1 = Again  (forgot — reset repetitions, +1 lapse)
 *   2 = Hard   (recalled with significant difficulty)
 *   3 = Good   (recalled correctly with some effort)
 *   4 = Easy   (instant recall)
 *
 * Refinements over textbook SM-2:
 *   - Ease floored at 1.30 to prevent the "ease hell" runaway-short-interval problem.
 *   - "Again" hard-resets repetitions to 0, leaves the card due in ~10 minutes
 *     (modelled here as 0 days, i.e. due immediately), and increments lapses.
 *   - First two successful reviews use fixed steps: 1 day, then 6 days. Only after
 *     that does the multiplicative `interval = prev_interval * ease` kick in.
 *   - "Hard" still counts as a successful review (no lapse) but uses interval * 1.2
 *     instead of interval * ease, and applies a small ease penalty.
 *   - "Easy" gets an additional 1.3x bonus on top of the ease multiplier.
 */

export type Rating = 1 | 2 | 3 | 4;

export interface SrsState {
  ease: number;
  intervalDays: number;
  repetitions: number;
  lapses: number;
}

export interface ScheduleResult {
  ease: number;
  intervalDays: number;
  repetitions: number;
  lapses: number;
  dueAt: Date;
}

const MIN_EASE = 1.3;
const HARD_INTERVAL_FACTOR = 1.2;
const EASY_BONUS = 1.3;

/**
 * Map a rating in [1,4] to the SM-2 quality grade in [0,5] used by the
 * canonical ease update formula. We use the upper end of each band so that
 * Hard (q=3) doesn't immediately tank ease, but Again (q=0) still bites hard.
 */
function ratingToQuality(rating: Rating): number {
  switch (rating) {
    case 1:
      return 0; // Again
    case 2:
      return 3; // Hard
    case 3:
      return 4; // Good
    case 4:
      return 5; // Easy
  }
}

function addDays(base: Date, days: number): Date {
  // intervalDays may be fractional (e.g. 0 → due now). Convert to ms.
  return new Date(base.getTime() + days * 24 * 60 * 60 * 1000);
}

export function schedule(card: SrsState, rating: Rating, now: Date = new Date()): ScheduleResult {
  const q = ratingToQuality(rating);

  // Standard SM-2 ease update: EF' = EF + (0.1 - (5-q) * (0.08 + (5-q)*0.02))
  const easeDelta = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02);
  let ease = card.ease + easeDelta;
  if (ease < MIN_EASE) ease = MIN_EASE;

  let repetitions: number;
  let lapses = card.lapses;
  let intervalDays: number;

  if (rating === 1) {
    // Lapse — reset and re-show today.
    repetitions = 0;
    lapses += 1;
    intervalDays = 0;
  } else {
    repetitions = card.repetitions + 1;

    if (repetitions === 1) {
      intervalDays = 1;
    } else if (repetitions === 2) {
      intervalDays = 6;
    } else {
      const prev = card.intervalDays > 0 ? card.intervalDays : 1;
      if (rating === 2) {
        // Hard: smaller multiplier, no ease bonus.
        intervalDays = prev * HARD_INTERVAL_FACTOR;
      } else if (rating === 4) {
        // Easy: bonus on top of ease.
        intervalDays = prev * ease * EASY_BONUS;
      } else {
        // Good: textbook SM-2.
        intervalDays = prev * ease;
      }
    }
    // Round to one decimal of a day so we don't drift to weird sub-second boundaries.
    intervalDays = Math.round(intervalDays * 10) / 10;
  }

  const dueAt = addDays(now, intervalDays);

  return {
    ease: Math.round(ease * 1000) / 1000,
    intervalDays,
    repetitions,
    lapses,
    dueAt,
  };
}

export const RATING_LABELS: Record<Rating, string> = {
  1: "Again",
  2: "Hard",
  3: "Good",
  4: "Easy",
};
