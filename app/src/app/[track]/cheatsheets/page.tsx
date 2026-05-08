import { notFound } from "next/navigation";
import Link from "next/link";
import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { TRACK_PATHS, parseTrack, TRACK_LABELS } from "@/lib/paths";
import type { Track } from "@/db/schema";

async function listCheatsheets(track: Track) {
  const dir = TRACK_PATHS[track].cheatsheetsContent;
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

export default async function CheatsheetsPage({
  params,
}: {
  params: Promise<{ track: string }>;
}) {
  const { track: trackParam } = await params;
  const track = parseTrack(trackParam);
  if (!track) notFound();
  const sheets = await listCheatsheets(track);

  return (
    <div className="max-w-5xl mx-auto p-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Cheatsheets</h1>
        <p className="text-muted-foreground mt-1">
          {TRACK_LABELS[track]} · quick references you should be able to recite cold.
        </p>
      </header>

      {sheets.length === 0 && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">No cheatsheets yet.</CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {sheets.map((s) => (
          <Link key={s.slug} href={`/${track}/cheatsheets/${s.slug}`} className="block group">
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
