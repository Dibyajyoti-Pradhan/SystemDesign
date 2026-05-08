import fs from "node:fs";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";
import { REPO_ROOT } from "@/lib/paths";

export async function GET(req: NextRequest) {
  const rel = req.nextUrl.searchParams.get("path");
  if (!rel) return new NextResponse("Missing path", { status: 400 });

  const safe = path.normalize(rel).replace(/^[/\\]+/, "");
  const abs = path.join(REPO_ROOT, safe);
  if (!abs.startsWith(REPO_ROOT)) return new NextResponse("Forbidden", { status: 403 });
  if (!fs.existsSync(abs)) return new NextResponse("Not found", { status: 404 });

  const data = fs.readFileSync(abs);
  return new NextResponse(data, {
    headers: {
      "content-type": "application/pdf",
      "content-disposition": `inline; filename="${path.basename(abs)}"`,
    },
  });
}
