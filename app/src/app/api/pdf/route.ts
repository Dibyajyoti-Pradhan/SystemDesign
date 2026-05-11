import fs from "node:fs";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";
import { REPO_ROOT } from "@/lib/paths";
import { apiAuthGuard } from "@/lib/auth-guards";
import logger from "@/lib/logger";

const CONTENT_TYPE_BY_EXT: Record<string, string> = {
  ".pdf": "application/pdf",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".doc": "application/msword",
  ".md": "text/markdown; charset=utf-8",
  ".mdx": "text/markdown; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
};

export async function GET(req: NextRequest) {
  const guard = await apiAuthGuard();
  if (guard instanceof NextResponse) return guard;

  const rel = req.nextUrl.searchParams.get("path");
  if (!rel) return new NextResponse("Missing path", { status: 400 });

  const safe = path.normalize(rel).replace(/^[/\\]+/, "");
  const abs = path.join(REPO_ROOT, safe);
  if (!abs.startsWith(REPO_ROOT)) return new NextResponse("Forbidden", { status: 403 });
  if (!fs.existsSync(abs)) return new NextResponse("Not found", { status: 404 });

  const data = fs.readFileSync(abs);
  const ext = path.extname(abs).toLowerCase();
  const contentType = CONTENT_TYPE_BY_EXT[ext] ?? "application/octet-stream";

  logger.info({
    route: "pdf",
    userId: guard.userId,
    filename: path.basename(abs),
    filesize: data.length,
  }, "pdf served");
  // .docx is not viewable inline — force download. PDFs and text inline.
  const disposition = ext === ".docx" || ext === ".doc" ? "attachment" : "inline";

  return new NextResponse(data, {
    headers: {
      "content-type": contentType,
      "content-disposition": `${disposition}; filename="${path.basename(abs)}"`,
    },
  });
}
