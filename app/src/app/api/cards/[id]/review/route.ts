import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db/client";
import { cards, reviews } from "@/db/schema";
import { eq } from "drizzle-orm";
import { schedule, type Rating } from "@/lib/srs";
import { revalidatePath } from "next/cache";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id: idStr } = await params;
  const id = Number(idStr);
  if (!Number.isFinite(id)) {
    return NextResponse.json({ error: "Invalid card id" }, { status: 400 });
  }

  let body: { rating?: number };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const rating = body.rating;
  if (rating !== 1 && rating !== 2 && rating !== 3 && rating !== 4) {
    return NextResponse.json(
      { error: "Rating must be 1 (Again), 2 (Hard), 3 (Good), or 4 (Easy)" },
      { status: 400 },
    );
  }

  const [card] = await db.select().from(cards).where(eq(cards.id, id)).limit(1);
  if (!card) {
    return NextResponse.json({ error: "Card not found" }, { status: 404 });
  }

  const prevInterval = card.intervalDays;
  const now = new Date();
  const next = schedule(
    {
      ease: card.ease,
      intervalDays: card.intervalDays,
      repetitions: card.repetitions,
      lapses: card.lapses,
    },
    rating as Rating,
    now,
  );

  await db
    .update(cards)
    .set({
      ease: next.ease,
      intervalDays: next.intervalDays,
      repetitions: next.repetitions,
      lapses: next.lapses,
      dueAt: next.dueAt,
      lastReviewedAt: now,
    })
    .where(eq(cards.id, id));

  await db.insert(reviews).values({
    userId: "system", // TODO: replace with real user id when auth is wired
    cardId: id,
    rating,
    prevInterval,
    nextInterval: next.intervalDays,
    reviewedAt: now,
  });

  revalidatePath("/review");

  const [updated] = await db.select().from(cards).where(eq(cards.id, id)).limit(1);
  return NextResponse.json({ card: updated, schedule: next });
}
