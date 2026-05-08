import { notFound } from "next/navigation";
import Link from "next/link";
import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import { CONTENT_ROOT } from "@/lib/paths";
import { MdxRenderer } from "@/components/MdxRenderer";
import { ArrowLeft } from "lucide-react";

export default async function CheatsheetPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const dir = path.join(CONTENT_ROOT, "cheatsheets");
  const candidates = [`${slug}.mdx`, `${slug}.md`];
  let raw: string | null = null;
  for (const c of candidates) {
    try {
      raw = await fs.readFile(path.join(dir, c), "utf8");
      break;
    } catch {}
  }
  if (!raw) notFound();

  const { data, content } = matter(raw);

  return (
    <div className="max-w-3xl mx-auto p-8 space-y-6">
      <Link href="/cheatsheets" className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
        <ArrowLeft className="h-4 w-4" /> All cheatsheets
      </Link>
      <header>
        <h1 className="text-4xl font-bold tracking-tight">{(data.title as string) ?? slug}</h1>
        {data.description && <p className="text-muted-foreground mt-2 text-lg">{data.description as string}</p>}
      </header>
      <div className="prose-system">
        <MdxRenderer source={content} />
      </div>
    </div>
  );
}
