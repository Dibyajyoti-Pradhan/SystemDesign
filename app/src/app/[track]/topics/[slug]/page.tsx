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
import { parseTrack } from "@/lib/paths";
import { relativeTime } from "@/lib/utils";

const CSS = `
.td { height:100%; display:grid; grid-template-columns: 1fr 220px; overflow:hidden; }
.td__col { overflow: auto; }
.td__rail { border-left: 1px solid var(--line); padding: 28px 22px; background: var(--bg); overflow:auto; }
.td__inner { padding: 28px 40px 64px; max-width: 760px; }
.td__hdr { display:flex; flex-direction: column; gap: 14px; padding-bottom: 22px; border-bottom: 1px solid var(--line); }
.td__meta { display:flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.td__title { font-size: 30px; font-weight: 600; letter-spacing: -0.024em; line-height: 1.1; }
.td__sum { color: var(--mute); font-size: 14.5px; max-width: 60ch; line-height: 1.55; }
.td__mastery { display:flex; align-items: center; gap: 14px; padding-top: 4px; }
.td__mastery .label { font-family: var(--font-mono); font-size: 10.5px; color: var(--mute); text-transform: uppercase; letter-spacing: .08em; }
.td__mastery .pct { font-family: var(--font-mono); font-size: 11px; color: var(--ink); }
.td__mastery .bar { flex:1; max-width: 320px; }
.td__back { display:inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--mute); text-decoration: none; margin-bottom: 18px; }
.td__back:hover { color: var(--ink); }
.td__content { padding-top: 24px; }
.rail__group { margin-bottom: 28px; }
.rail__h { font-family: var(--font-mono); font-size: 10px; color: var(--mute); text-transform: uppercase; letter-spacing: .1em; margin-bottom: 10px; }
.rail__related { display:flex; flex-direction: column; gap: 8px; }
.rail__rel { display:flex; flex-direction: column; gap: 2px; padding: 8px 10px; border:1px solid var(--line); border-radius: 6px; background: var(--bg-2); text-decoration: none; }
.rail__rel .ttl { font-size: 12.5px; color: var(--ink); }
.rail__rel .sub { font-family: var(--font-mono); font-size: 10px; color: var(--mute-2); }
.rail__rel:hover { border-color: var(--line-2); background: var(--surf); }
.rail__cta { background: var(--surf); border: 1px solid var(--line-2); border-radius: 8px; padding: 12px; margin-bottom: 20px; }
.rail__cta .n { font-family: var(--font-mono); font-size: 24px; color: var(--accent); letter-spacing: -0.02em; }
.rail__cta .lbl { font-size: 12px; color: var(--ink-2); margin-top: 2px; }
.rail__cta .go { font-family: var(--font-mono); font-size: 10.5px; color: var(--accent); margin-top: 8px; display:flex; align-items:center; gap:6px; text-transform: uppercase; letter-spacing: .1em; text-decoration: none; }
.rail__cta .go:hover { text-decoration: underline; }
.rail__toc { margin-bottom: 24px; }
.rail__toc-item { display:block; font-size: 12px; color: var(--mute); padding: 4px 0; text-decoration: none; border-bottom: 1px solid transparent; }
.rail__toc-item:hover { color: var(--ink); }
.depth-wrap { padding-top: 4px; }
`;

/**
 * Source-file card. Inlines the iframe only for PDFs and plain text;
 * .docx/.doc are not browser-renderable inline so we offer a download
 * link plus a nudge to use the Generate button.
 */
function SourceCard({ pdfPath, title }: { pdfPath: string; title: string }) {
  const ext = pdfPath.toLowerCase().match(/\.([^.]+)$/)?.[1] ?? "";
  const isPdf = ext === "pdf";
  const isInlineText = ext === "md" || ext === "mdx" || ext === "txt";
  const inlinable = isPdf || isInlineText;
  const sourceLabel = ext.toUpperCase();
  const url = `/api/pdf?path=${encodeURIComponent(pdfPath)}`;

  return (
    <Card>
      <CardHeader className="pb-3 flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2 text-base">
          <FileText className="h-4 w-4" /> Source {sourceLabel}
        </CardTitle>
        <Button variant="outline" size="sm" asChild>
          <a href={url} target="_blank" rel="noopener">
            <ExternalLink className="h-4 w-4" />
            {inlinable ? "Open in new tab" : "Download"}
          </a>
        </Button>
      </CardHeader>
      {isPdf ? (
        <CardContent className="p-0">
          <iframe
            src={`${url}#view=FitH`}
            className="w-full h-[75vh] rounded-b-lg border-t"
            title={`${title} (PDF)`}
          />
        </CardContent>
      ) : (
        <CardContent className="border-t pt-4 space-y-2">
          <p className="text-sm text-muted-foreground">
            {ext === "docx" || ext === "doc"
              ? "Word documents can't preview inline — use the button above to download."
              : `${sourceLabel} source — open in a new tab to view.`}
          </p>
          <p className="text-xs text-muted-foreground">
            Or hit <strong>Generate this page from PDF</strong> above to read the rich version directly.
          </p>
        </CardContent>
      )}
    </Card>
  );
}

export default async function TopicPage({ params }: { params: Promise<{ track: string; slug: string }> }) {
  const { track: trackParam, slug } = await params;
  const track = parseTrack(trackParam);
  if (!track) notFound();
  const [topic] = await db
    .select()
    .from(topics)
    .where(and(eq(topics.slug, slug), eq(topics.track, track)))
    .limit(1);
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
    <div className="td">
      <style>{CSS}</style>

      {/* Left column: main content */}
      <div className="td__col">
        <div className="td__inner">
          {/* Back link */}
          <Link href={`/${track}/topics`} className="td__back">
            ← All topics
          </Link>

          {/* Header */}
          <div className="td__hdr">
            <div className="td__meta">
              <span className="badge">{topic.category}</span>
              {cardsForTopic.n > 0 && (
                <span className="badge badge--accent">{cardsForTopic.n} cards</span>
              )}
              {!parsed && <span className="badge">PDF only</span>}
              {topic.lastVisitedAt && (
                <span className="badge">Visited {relativeTime(topic.lastVisitedAt)}</span>
              )}
            </div>
            <h1 className="td__title">{topic.title}</h1>
            {topic.summary && <p className="td__sum">{topic.summary}</p>}
            <div className="td__mastery">
              <span className="label">Mastery</span>
              <div className="bar">
                <div className="progress">
                  <i
                    className={topic.mastery >= 80 ? "acc" : ""}
                    style={{ width: `${topic.mastery}%` }}
                  />
                </div>
              </div>
              <span className="pct">{topic.mastery}%</span>
            </div>
          </div>

          {/* Content */}
          <div className="td__content">
            {parsed ? (
              <div className="depth-wrap">
                <DepthTabs
                  tldr={<MdxRenderer source={parsed.sections.tldr} />}
                  standard={<MdxRenderer source={parsed.sections.standard} />}
                  deep={<MdxRenderer source={parsed.sections.deep} />}
                />
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
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

                {topic.pdfPath && <SourceCard pdfPath={topic.pdfPath} title={topic.title} />}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Right rail */}
      <div className="td__rail">
        {/* Review cards CTA */}
        <div className="rail__group">
          <div className="rail__cta">
            <div className="n">{cardsForTopic.n}</div>
            <div className="lbl">Active review cards</div>
            <Link
              href={`/${track}/review?topic=${topic.slug}`}
              className="go"
            >
              <span>Review now</span>
              <span>›</span>
            </Link>
          </div>
        </div>

        {/* On this page (static TOC placeholder) */}
        <div className="rail__group rail__toc">
          <div className="rail__h">On this page</div>
          <span className="rail__toc-item" style={{ color: "var(--mute-2)", fontSize: "11px", fontFamily: "var(--font-mono)" }}>
            TL;DR · Standard · Deep
          </span>
        </div>

        {/* Related topics */}
        {relatedTopics.length > 0 && (
          <div className="rail__group">
            <div className="rail__h">Related topics</div>
            <div className="rail__related">
              {relatedTopics.map((r) => (
                <Link
                  key={r.id}
                  href={`/${track}/topics/${r.slug}`}
                  className="rail__rel"
                >
                  <span className="ttl">{r.title}</span>
                  <span className="sub">{r.category}</span>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
