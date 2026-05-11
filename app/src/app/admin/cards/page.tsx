import Link from "next/link";
import { db } from "@/db/client";
import { cards, topics, FREE_FOREVER_EMAIL } from "@/db/schema";
import { eq, asc } from "drizzle-orm";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, Pencil, X, ArrowLeft } from "lucide-react";

export const dynamic = "force-dynamic";

async function approveCard(formData: FormData) {
  "use server";
  const id = Number(formData.get("id"));
  if (!Number.isFinite(id)) return;
  await db
    .update(cards)
    .set({ status: "active", dueAt: new Date() })
    .where(eq(cards.id, id));
  revalidatePath("/admin/cards");
  revalidatePath("/review");
}

async function rejectCard(formData: FormData) {
  "use server";
  const id = Number(formData.get("id"));
  if (!Number.isFinite(id)) return;
  await db.update(cards).set({ status: "archived" }).where(eq(cards.id, id));
  revalidatePath("/admin/cards");
}

async function editCard(formData: FormData) {
  "use server";
  const id = Number(formData.get("id"));
  if (!Number.isFinite(id)) return;
  redirect(`/admin/cards/${id}/edit`);
}

export default async function AdminCardsPage() {
  const session = await auth();
  if (!session?.user) redirect("/sign-in");
  if (session.user.email !== FREE_FOREVER_EMAIL) redirect("/");

  const rows = await db
    .select({
      id: cards.id,
      type: cards.type,
      front: cards.front,
      back: cards.back,
      diagramMermaid: cards.diagramMermaid,
      generatedByModel: cards.generatedByModel,
      createdAt: cards.createdAt,
      topicTitle: topics.title,
      topicSlug: topics.slug,
      topicCategory: topics.category,
    })
    .from(cards)
    .leftJoin(topics, eq(cards.topicId, topics.id))
    .where(eq(cards.status, "pending_review"))
    .orderBy(asc(topics.categoryOrder), asc(topics.topicOrder), asc(cards.id));

  const grouped = new Map<string, typeof rows>();
  for (const r of rows) {
    const key = r.topicTitle ?? "Unassigned";
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(r);
  }

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8">
      <div className="flex items-center justify-between">
        <Link
          href="/topics"
          className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <ArrowLeft className="h-4 w-4" /> Topics
        </Link>
        <Badge variant="muted">{rows.length} pending</Badge>
      </div>

      <header>
        <h1 className="text-3xl font-bold tracking-tight">Pending cards</h1>
        <p className="text-muted-foreground mt-1">
          Review Claude-generated flashcards before they enter your daily rotation.
        </p>
      </header>

      {rows.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground space-y-3">
            <p>No cards waiting for review.</p>
            <div className="bg-muted px-3 py-2 rounded font-mono text-xs inline-block">
              npm run generate-cards &lt;topic-slug&gt;
            </div>
          </CardContent>
        </Card>
      )}

      {[...grouped.entries()].map(([topicTitle, items]) => (
        <section key={topicTitle} className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold tracking-tight">{topicTitle}</h2>
            <Badge variant="outline" className="text-[10px]">
              {items.length} {items.length === 1 ? "card" : "cards"}
            </Badge>
          </div>

          <div className="space-y-3">
            {items.map((c) => (
              <Card key={c.id}>
                <CardHeader className="pb-3">
                  <div className="flex justify-between items-start gap-2">
                    <CardTitle className="text-sm font-medium leading-snug">
                      {c.front}
                    </CardTitle>
                    <div className="flex gap-1.5 shrink-0">
                      <Badge variant="outline" className="text-[10px] uppercase">
                        {c.type}
                      </Badge>
                      {c.diagramMermaid && (
                        <Badge variant="muted" className="text-[10px]">
                          diagram
                        </Badge>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="text-sm text-muted-foreground whitespace-pre-wrap line-clamp-4">
                    {c.back}
                  </div>
                  {c.diagramMermaid && (
                    <details className="border rounded">
                      <summary className="px-3 py-1.5 text-xs cursor-pointer text-muted-foreground hover:bg-accent">
                        Mermaid source
                      </summary>
                      <pre className="text-[11px] bg-muted p-3 overflow-x-auto rounded-b">
                        {c.diagramMermaid}
                      </pre>
                    </details>
                  )}

                  <div className="flex gap-2 pt-1">
                    <form action={approveCard}>
                      <input type="hidden" name="id" value={c.id} />
                      <Button type="submit" size="sm">
                        <CheckCircle2 className="h-4 w-4" /> Approve
                      </Button>
                    </form>
                    <form action={editCard}>
                      <input type="hidden" name="id" value={c.id} />
                      <Button type="submit" size="sm" variant="outline">
                        <Pencil className="h-4 w-4" /> Edit
                      </Button>
                    </form>
                    <form action={rejectCard}>
                      <input type="hidden" name="id" value={c.id} />
                      <Button type="submit" size="sm" variant="ghost">
                        <X className="h-4 w-4" /> Reject
                      </Button>
                    </form>
                    <span className="ml-auto text-[11px] text-muted-foreground self-center">
                      {c.generatedByModel ?? "manual"}
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
