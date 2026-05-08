import fs from "node:fs";

// pdf-parse has no usable type defs in this repo, so we do a CJS require
// to avoid the global side-effect debug code that runs when the package
// is `require`d via its `main` entry point.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let _pdfParse: ((buf: Buffer) => Promise<{ text: string }>) | null = null;

async function getPdfParse() {
  if (_pdfParse) return _pdfParse;
  // Reach directly into the lib so we skip the index.js test harness that
  // tries to read a sample file from disk on first import.
  // eslint-disable-next-line @typescript-eslint/no-require-imports, @typescript-eslint/no-var-requires
  const mod = require("pdf-parse/lib/pdf-parse.js") as
    | ((buf: Buffer) => Promise<{ text: string }>)
    | { default: (buf: Buffer) => Promise<{ text: string }> };
  _pdfParse = (typeof mod === "function" ? mod : mod.default) as (
    buf: Buffer,
  ) => Promise<{ text: string }>;
  return _pdfParse;
}

const cache = new Map<string, string>();

export async function extractPdfText(absPath: string): Promise<string> {
  const cached = cache.get(absPath);
  if (cached) return cached;

  if (!fs.existsSync(absPath)) {
    throw new Error(`PDF not found at ${absPath}`);
  }
  const buf = fs.readFileSync(absPath);
  const pdfParse = await getPdfParse();
  const result = await pdfParse(buf);
  const text = result.text.trim();
  cache.set(absPath, text);
  return text;
}
