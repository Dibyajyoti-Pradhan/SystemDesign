import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db/client";
import { notes } from "@/db/schema";
import { z } from "zod";

const createSchema = z.object({
  body: z.string().min(1).max(20_000),
  topicId: z.number().nullable().optional(),
  questionId: z.number().nullable().optional(),
});

export async function POST(req: NextRequest) {
  const json = await req.json();
  const parsed = createSchema.safeParse(json);
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.issues }, { status: 400 });
  }
  const [row] = await db
    .insert(notes)
    .values({
      body: parsed.data.body,
      topicId: parsed.data.topicId ?? null,
      questionId: parsed.data.questionId ?? null,
    })
    .returning();
  return NextResponse.json(row);
}
