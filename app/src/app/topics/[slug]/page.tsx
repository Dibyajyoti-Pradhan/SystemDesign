import { notFound } from "next/navigation";
import Link from "next/link";
import { db } from "@/db/client";
import { topics, topicLinks, cards } from "@/db/schema";
import { eq, and, or, count, inArray } from "drizzle-orm";
import { readTopicMdx } from "@/lib/mdx";
import { MdxRenderer } from "@/components/MdxRenderer";
import { DepthTabs } from "@/components/DepthTabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ArrowLeft, ExternalLink, FileText, Sparkles } from "lucide-react";
import { GenerateTopicButton } from "@/components/topic/GenerateTopicButton";

export default async function TopicPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [topic] = await db.select().from(topics).where(eq(topics.slug, slug)).limit(1);
  if (!topic) notFound();

  const parsed = topic.mdxPath ? await readTopicMdx(topic.mdxPath) : null;

  const [cardsForTopic] = await db
    .select({ n: count() })
    .from(cards)
    .where(and(eq(cards.topicId, topic.id), eq(cards.status, "active")));

  const links = await db
    .select({ otherId: topicLinks.toTopicId })
    .from(topicLinks)
    .where(eq(topicLinks.fromTopicId, topic.id));

  const relatedTopics = links.length
    ? await db
        .select()
        .from(topics)
        .where(inArray(topics.id, links.map((l) => l.otherId)))
    : [];

  // Fire-and-forget visit tracking. No revalidation — the freshness only
  // matters next render anyway, and revalidatePath during render would loop.
  db.update(topics)
    .set({ lastVisitedAt: new Date() })
    .where(eq(topics.id, topic.id))
    .catch(() => {});

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href="/topics"
          className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <ArrowLeft className="h-4 w-4" /> All topics
        </Link>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline">{topic.category}</Badge>
          {cardsForTopic.n > 0 && <Badge variant="muted">{cardsForTopic.n} cards</Badge>}
          {!parsed && <Badge variant="outline">PDF only</Badge>}
        </div>
      </div>

      <header>
        <h1 className="text-4xl font-bold tracking-tight">{topic.title}</h1>
        {topic.summary && <p className="text-muted-foreground mt-2 text-lg">{topic.summary}</p>}
      </header>

      <div className="flex items-center gap-3">
        <Progress value={topic.mastery} className="flex-1" />
        <span className="text-xs text-muted-foreground w-16 text-right">Mastery {topic.mastery}%</span>
      </div>

      {parsed ? (
        <DepthTabs
          tldr={<MdxRenderer source={parsed.sections.tldr} />}
          standard={<MdxRenderer source={parsed.sections.standard} />}
          deep={<MdxRenderer source={parsed.sections.deep} />}
        />
      ) : (
        <div className="space-y-4">
          <Card className="border-primary/20 bg-primary/5">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles className="h-4 w-4" /> Turn this PDF into an interactive page
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Generate a structured TL;DR / Standard / Deep view with Mermaid diagrams from the source PDF.
                Uses your Claude Code subscription. ~30–60 seconds.
              </p>
              <GenerateTopicButton slug={topic.slug} />
            </CardContent>
          </Card>

          {topic.pdfPath && (
            <Card>
              <CardHeader className="pb-3 flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileText className="h-4 w-4" /> Source PDF
                </CardTitle>
                <Button variant="outline" size="sm" asChild>
                  <a
                    href={`/api/pdf?path=${encodeURIComponent(topic.pdfPath)}`}
                    target="_blank"
                    rel="noopener"
                  >
                    <ExternalLink className="h-4 w-4" /> Open in new tab
                  </a>
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                <iframe
                  src={`/api/pdf?path=${encodeURIComponent(topic.pdfPath)}#view=FitH`}
                  className="w-full h-[75vh] rounded-b-lg border-t"
                  title={`${topic.title} (PDF)`}
                />
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {relatedTopics.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">See also</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {relatedTopics.map((r) => (
                <Link key={r.id} href={`/topics/${r.slug}`}>
                  <Badge variant="outline" className="hover:bg-accent cursor-pointer">{r.title}</Badge>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex gap-2 pt-4 border-t">
        <Button asChild variant="outline" size="sm">
          <Link href={`/review?topic=${topic.slug}`}>
            <Sparkles className="h-4 w-4" /> Review cards
          </Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href={`/notes?topic=${topic.slug}`}>Notes</Link>
        </Button>
      </div>
    </div>
  );
}
