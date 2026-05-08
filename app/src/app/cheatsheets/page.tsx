import Link from "next/link";
import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CONTENT_ROOT } from "@/lib/paths";

async function listCheatsheets() {
  const dir = path.join(CONTENT_ROOT, "cheatsheets");
  try {
    const files = await fs.readdir(dir);
    const out: Array<{ slug: string; title: string; description: string }> = [];
    for (const f of files.sort()) {
      if (!f.endsWith(".md") && !f.endsWith(".mdx")) continue;
      const raw = await fs.readFile(path.join(dir, f), "utf8");
      const { data } = matter(raw);
      out.push({
        slug: f.replace(/\.(md|mdx)$/, ""),
        title: (data.title as string) ?? f,
        description: (data.description as string) ?? "",
      });
    }
    return out;
  } catch {
    return [];
  }
}

export default async function CheatsheetsPage() {
  const sheets = await listCheatsheets();
  return (
    <div className="max-w-5xl mx-auto p-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Cheatsheets</h1>
        <p className="text-muted-foreground mt-1">Quick references you should be able to recite cold.</p>
      </header>

      {sheets.length === 0 && (
        <Card><CardContent className="py-8 text-center text-muted-foreground">No cheatsheets yet.</CardContent></Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {sheets.map((s) => (
          <Link key={s.slug} href={`/cheatsheets/${s.slug}`} className="block group">
            <Card className="h-full hover:border-primary/40 transition-colors">
              <CardHeader>
                <CardTitle className="text-base group-hover:text-primary transition-colors">{s.title}</CardTitle>
                <CardDescription>{s.description}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
