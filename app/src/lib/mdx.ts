import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import { CONTENT_ROOT } from "./paths";

export interface TopicFrontmatter {
  title: string;
  slug: string;
  category?: string;
  tldr?: string;
  related?: string[];
  diagrams?: number;
}

export interface ParsedMdx {
  frontmatter: TopicFrontmatter;
  body: string;
  sections: {
    tldr: string;
    standard: string;
    deep: string;
  };
}

/**
 * Convention: a topic MDX file has three sections separated by HTML comments:
 *   <!-- tldr -->
 *   ...short summary + 1 diagram
 *   <!-- standard -->
 *   ...mid-depth content
 *   <!-- deep -->
 *   ...full content
 *
 * This keeps everything in one file (one source of truth) while letting the UI
 * render three depth views.
 */
export function splitDepthSections(body: string): ParsedMdx["sections"] {
  const tldrIdx = body.indexOf("<!-- tldr -->");
  const stdIdx = body.indexOf("<!-- standard -->");
  const deepIdx = body.indexOf("<!-- deep -->");

  if (tldrIdx === -1 && stdIdx === -1 && deepIdx === -1) {
    return { tldr: body.trim(), standard: body.trim(), deep: body.trim() };
  }

  const sliceBetween = (start: number, ...ends: number[]) => {
    if (start === -1) return "";
    const validEnds = ends.filter((e) => e > start);
    const end = validEnds.length ? Math.min(...validEnds) : body.length;
    return body.slice(start, end).replace(/^<!--[^>]*-->/, "").trim();
  };

  return {
    tldr: sliceBetween(tldrIdx, stdIdx, deepIdx),
    standard: sliceBetween(stdIdx, deepIdx) || sliceBetween(tldrIdx, stdIdx, deepIdx),
    deep: sliceBetween(deepIdx) || sliceBetween(stdIdx, deepIdx) || sliceBetween(tldrIdx, stdIdx, deepIdx),
  };
}

export async function readTopicMdx(mdxPath: string): Promise<ParsedMdx | null> {
  const abs = path.isAbsolute(mdxPath) ? mdxPath : path.join(CONTENT_ROOT, mdxPath);
  try {
    const raw = await fs.readFile(abs, "utf8");
    const { data, content } = matter(raw);
    return {
      frontmatter: data as TopicFrontmatter,
      body: content,
      sections: splitDepthSections(content),
    };
  } catch {
    return null;
  }
}
