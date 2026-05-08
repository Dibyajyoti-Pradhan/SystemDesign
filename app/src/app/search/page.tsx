import Link from "next/link";
import { search } from "@/lib/search";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Search } from "lucide-react";

export default async function SearchPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams;
  const hits = q ? await search(q, 30) : [];

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Search</h1>
        <p className="text-muted-foreground mt-1">Across topics and design questions.</p>
      </header>

      <form className="relative">
        <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground pointer-events-none" />
        <input
          type="text"
          name="q"
          defaultValue={q}
          autoFocus
          placeholder="caching, sharding, instagram, rate limit..."
          className="w-full pl-9 pr-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </form>

      {q && (
        <p className="text-xs text-muted-foreground">{hits.length} result{hits.length === 1 ? "" : "s"} for &quot;{q}&quot;</p>
      )}

      {q && hits.length === 0 && (
        <Card><CardContent className="py-8 text-center text-muted-foreground">No matches.</CardContent></Card>
      )}

      <div className="space-y-2">
        {hits.map((h) => (
          <Link key={`${h.kind}-${h.id}`} href={h.kind === "topic" ? `/topics/${h.slug}` : `/questions/${h.slug}`}>
            <Card className="hover:border-primary/40 transition-colors">
              <CardHeader className="py-4">
                <CardTitle className="text-base flex items-center justify-between gap-2">
                  <span>{h.title}</span>
                  <Badge variant={h.kind === "topic" ? "muted" : "outline"} className="text-[10px] uppercase">{h.kind}</Badge>
                </CardTitle>
                {h.category && <p className="text-xs text-muted-foreground">{h.category}</p>}
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
