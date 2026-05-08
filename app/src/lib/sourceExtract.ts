import fs from "node:fs/promises";
import path from "node:path";

/**
 * Extract plain text from a study source. Handles .pdf, .docx, .md, .txt.
 * Returns "" on extraction failure rather than throwing — generation flows
 * fall back to model-knowledge in that case.
 */
export async function extractSourceText(absPath: string): Promise<string> {
  const ext = path.extname(absPath).toLowerCase();
  try {
    if (ext === ".pdf") {
      const buf = await fs.readFile(absPath);
      const pdfParse = (await import("pdf-parse")).default;
      const data = await pdfParse(buf);
      return data.text ?? "";
    }
    if (ext === ".docx") {
      const buf = await fs.readFile(absPath);
      const mammoth = await import("mammoth");
      const result = await mammoth.extractRawText({ buffer: buf });
      return result.value ?? "";
    }
    if (ext === ".md" || ext === ".mdx" || ext === ".txt") {
      return await fs.readFile(absPath, "utf8");
    }
  } catch (err) {
    console.error(`[sourceExtract] failed for ${absPath}:`, err);
    return "";
  }
  return "";
}
