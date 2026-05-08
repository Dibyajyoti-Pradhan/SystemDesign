import Link from "next/link";
import { db } from "@/db/client";
import { topics } from "@/db/schema";
import { asc } from "drizzle-orm";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { FileText, CheckCircle2, Network } from "lucide-react";

export default async function TopicsPage() {
  const all = await db.select().from(topics).orderBy(asc(topics.categoryOrder), asc(topics.topicOrder));
  const grouped = new Map<string, typeof all>();
  for (const t of all) {
    if (!grouped.has(t.category)) grouped.set(t.category, []);
    grouped.get(t.category)!.push(t);
  }

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Topics</h1>
          <p className="text-muted-foreground mt-1">{all.length} concepts across {grouped.size} categories.</p>
        </div>
        <Link
          href="/concept-map"
          className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <Network className="h-4 w-4" /> Map view
        </Link>
      </header>

      {grouped.size === 0 && (
        <Card><CardContent className="py-8 text-center text-muted-foreground">
          No topics yet. Run <code className="bg-muted px-1.5 py-0.5 rounded text-sm">npm run seed</code>.
        </CardContent></Card>
      )}

      {[...grouped.entries()].map(([category, items]) => (
        <section key={category} className="space-y-3">
          <h2 className="text-xl font-semibold tracking-tight">{category}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {items.map((t) => (
              <Link key={t.id} href={`/topics/${t.slug}`} className="block group">
                <Card className="h-full transition-all hover:border-primary/40 hover:shadow-md">
                  <CardHeader className="pb-3">
                    <div className="flex justify-between items-start gap-2">
                      <CardTitle className="text-base group-hover:text-primary transition-colors">{t.title}</CardTitle>
                      {t.mdxPath ? (
                        <Badge variant="muted" className="text-[10px]"><CheckCircle2 className="h-3 w-3 mr-1" />MDX</Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px]"><FileText className="h-3 w-3 mr-1" />PDF</Badge>
                      )}
                    </div>
                    {t.summary && <CardDescription className="line-clamp-2">{t.summary}</CardDescription>}
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-2">
                      <Progress value={t.mastery} className="flex-1" />
                      <span className="text-xs text-muted-foreground w-10 text-right">{t.mastery}%</span>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
