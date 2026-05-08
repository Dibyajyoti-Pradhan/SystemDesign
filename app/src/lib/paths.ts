import path from "node:path";

export const REPO_ROOT = path.resolve(process.cwd(), "..");
export const CONTENT_ROOT = path.join(REPO_ROOT, "content");
export const TOPICS_CONTENT = path.join(CONTENT_ROOT, "topics");
export const QUESTIONS_CONTENT = path.join(CONTENT_ROOT, "questions");
export const STUDY_GUIDE_PDFS = path.join(REPO_ROOT, "study-guide");
export const DESIGN_QUESTIONS_PDFS = path.join(REPO_ROOT, "design-questions");
