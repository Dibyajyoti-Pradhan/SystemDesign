import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db/client";
import { cards } from "@/db/schema";
import { eq } from "drizzle-orm";
import { revalidatePath } from "next/cache";

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id: idStr } = await params;
  const id = Number(idStr);
  if (!Number.isFinite(id)) {
    return NextResponse.json({ error: "Invalid card id" }, { status: 400 });
  }

  let body: {
    front?: string;
    back?: string;
    diagramMermaid?: string | null;
    type?: "definition" | "tradeoff" | "scenario" | "comparison";
  };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const update: Record<string, unknown> = {};
  if (typeof body.front === "string") update.front = body.front;
  if (typeof body.back === "string") update.back = body.back;
  if (body.diagramMermaid === null || typeof body.diagramMermaid === "string") {
    update.diagramMermaid = body.diagramMermaid || null;
  }
  if (body.type) update.type = body.type;

  if (Object.keys(update).length === 0) {
    return NextResponse.json({ error: "No fields to update" }, { status: 400 });
  }

  await db.update(cards).set(update).where(eq(cards.id, id));
  const [updated] = await db.select().from(cards).where(eq(cards.id, id)).limit(1);
  if (!updated) return NextResponse.json({ error: "Card not found" }, { status: 404 });

  revalidatePath("/admin/cards");
  revalidatePath(`/admin/cards/${id}/edit`);
  revalidatePath("/review");

  return NextResponse.json({ card: updated });
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id: idStr } = await params;
  const id = Number(idStr);
  if (!Number.isFinite(id)) {
    return NextResponse.json({ error: "Invalid card id" }, { status: 400 });
  }

  let body: { action?: "approve" | "reject" | "archive" };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const action = body.action;
  if (action !== "approve" && action !== "reject" && action !== "archive") {
    return NextResponse.json(
      { error: "Action must be approve, reject, or archive" },
      { status: 400 },
    );
  }

  const [card] = await db.select().from(cards).where(eq(cards.id, id)).limit(1);
  if (!card) return NextResponse.json({ error: "Card not found" }, { status: 404 });

  if (action === "approve") {
    // Send into rotation today.
    await db
      .update(cards)
      .set({ status: "active", dueAt: new Date() })
      .where(eq(cards.id, id));
  } else if (action === "reject" || action === "archive") {
    await db.update(cards).set({ status: "archived" }).where(eq(cards.id, id));
  }

  revalidatePath("/admin/cards");
  revalidatePath("/review");

  const [updated] = await db.select().from(cards).where(eq(cards.id, id)).limit(1);
  return NextResponse.json({ card: updated });
}
