import { sqliteTable, text, integer, real, index } from "drizzle-orm/sqlite-core";
import { sql } from "drizzle-orm";
import { TRACKS } from "@/lib/tracks";

export type { Track } from "@/lib/tracks";
export { TRACKS } from "@/lib/tracks";

// Special email that always gets the free plan and never expires
const FREE_FOREVER_EMAIL = "dibyojyotipradhan@gmail.com";
export { FREE_FOREVER_EMAIL };

// Helper: SQLite timestamp stored as integer milliseconds, maps to/from Date
const ts = (name: string) => integer(name, { mode: "timestamp_ms" });

export const users = sqliteTable("users", {
  id: text("id").primaryKey(),
  email: text("email").notNull().unique(),
  name: text("name"),
  image: text("image"),
  // If email === FREE_FOREVER_EMAIL, plan is always 'free' and never expires (enforced in app layer)
  plan: text("plan", { enum: ["free", "trial", "paid"] }).notNull().default("trial"),
  trialEndsAt: ts("trial_ends_at"),
  createdAt: ts("created_at").notNull().default(sql`(unixepoch('now') * 1000)`),
});

export const topics = sqliteTable("topics", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  userId: text("user_id").notNull(),
  track: text("track", { enum: TRACKS }).notNull().default("system-design"),
  language: text("language"),
  slug: text("slug").notNull().unique(),
  category: text("category").notNull(),
  categoryOrder: integer("category_order").notNull().default(0),
  topicOrder: integer("topic_order").notNull().default(0),
  title: text("title").notNull(),
  summary: text("summary").notNull().default(""),
  mdxPath: text("mdx_path"),
  pdfPath: text("pdf_path"),
  mastery: integer("mastery").notNull().default(0),
  lastVisitedAt: ts("last_visited_at"),
  createdAt: ts("created_at").notNull().default(sql`(unixepoch('now') * 1000)`),
  generatedAt: ts("generated_at"),
  version: integer("version").notNull().default(0),
  generationStatus: text("generation_status", { enum: ["pending", "done", "error"] }).notNull().default("pending"),
}, (t) => ({
  userIdx: index("topics_user_idx").on(t.userId),
}));

export const topicLinks = sqliteTable(
  "topic_links",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    fromTopicId: integer("from_topic_id").notNull().references(() => topics.id),
    toTopicId: integer("to_topic_id").notNull().references(() => topics.id),
    relation: text("relation").notNull().default("related"),
  },
  (t) => ({
    fromIdx: index("topic_links_from_idx").on(t.fromTopicId),
    toIdx: index("topic_links_to_idx").on(t.toTopicId),
  }),
);

export const questions = sqliteTable("questions", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  userId: text("user_id").notNull(),
  track: text("track", { enum: TRACKS }).notNull().default("system-design"),
  language: text("language"),
  slug: text("slug").notNull().unique(),
  number: integer("number"),
  title: text("title").notNull(),
  difficulty: text("difficulty").notNull().default("medium"),
  tags: text("tags").notNull().default("[]"),
  pdfPath: text("pdf_path"),
  mdxPath: text("mdx_path"),
  estMinutes: integer("est_minutes").notNull().default(45),
  createdAt: ts("created_at").notNull().default(sql`(unixepoch('now') * 1000)`),
}, (t) => ({
  userIdx: index("questions_user_idx").on(t.userId),
}));

export const cards = sqliteTable(
  "cards",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    userId: text("user_id").notNull(),
    topicId: integer("topic_id").references(() => topics.id),
    questionId: integer("question_id").references(() => questions.id),
    type: text("type", { enum: ["definition", "tradeoff", "scenario", "comparison"] }).notNull(),
    front: text("front").notNull(),
    back: text("back").notNull(),
    diagramMermaid: text("diagram_mermaid"),
    status: text("status", { enum: ["pending_review", "active", "archived"] }).notNull().default("pending_review"),
    ease: real("ease").notNull().default(2.5),
    intervalDays: real("interval_days").notNull().default(0),
    repetitions: integer("repetitions").notNull().default(0),
    lapses: integer("lapses").notNull().default(0),
    dueAt: ts("due_at"),
    lastReviewedAt: ts("last_reviewed_at"),
    generatedByModel: text("generated_by_model"),
    createdAt: ts("created_at").notNull().default(sql`(unixepoch('now') * 1000)`),
    difficulty: integer("difficulty").notNull().default(3),
    lastScore: integer("last_score"),
  },
  (t) => ({
    statusDueIdx: index("cards_status_due_idx").on(t.status, t.dueAt),
    topicIdx: index("cards_topic_idx").on(t.topicId),
    userIdx: index("cards_user_idx").on(t.userId),
  }),
);

export const reviews = sqliteTable(
  "reviews",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    userId: text("user_id").notNull(),
    cardId: integer("card_id").notNull().references(() => cards.id),
    rating: integer("rating").notNull(),
    prevInterval: real("prev_interval").notNull(),
    nextInterval: real("next_interval").notNull(),
    reviewedAt: ts("reviewed_at").notNull().default(sql`(unixepoch('now') * 1000)`),
  },
  (t) => ({
    cardIdx: index("reviews_card_idx").on(t.cardId),
    userIdx: index("reviews_user_idx").on(t.userId),
  }),
);

export const interviewSessions = sqliteTable("interview_sessions", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  userId: text("user_id").notNull(),
  questionId: integer("question_id").notNull().references(() => questions.id),
  mode: text("mode", { enum: ["self", "ai_vs_ai", "voice"] }).notNull().default("self"),
  startedAt: ts("started_at").notNull().default(sql`(unixepoch('now') * 1000)`),
  endedAt: ts("ended_at"),
  transcript: text("transcript").notNull().default("[]"),
  rubric: text("rubric"),
  score: integer("score"),
  whiteboardSnapshot: text("whiteboard_snapshot"),
}, (t) => ({
  userIdx: index("interview_sessions_user_idx").on(t.userId),
}));

export const notes = sqliteTable(
  "notes",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    userId: text("user_id").notNull(),
    topicId: integer("topic_id").references(() => topics.id),
    questionId: integer("question_id").references(() => questions.id),
    body: text("body").notNull(),
    createdAt: ts("created_at").notNull().default(sql`(unixepoch('now') * 1000)`),
    updatedAt: ts("updated_at").notNull().default(sql`(unixepoch('now') * 1000)`),
  },
  (t) => ({
    topicIdx: index("notes_topic_idx").on(t.topicId),
    questionIdx: index("notes_question_idx").on(t.questionId),
    userIdx: index("notes_user_idx").on(t.userId),
  }),
);

export type User = typeof users.$inferSelect;
export type NewUser = typeof users.$inferInsert;
export type Topic = typeof topics.$inferSelect;
export type NewTopic = typeof topics.$inferInsert;
export type Question = typeof questions.$inferSelect;
export type Card = typeof cards.$inferSelect;
export type NewCard = typeof cards.$inferInsert;
export type Review = typeof reviews.$inferSelect;
export type InterviewSession = typeof interviewSessions.$inferSelect;
export type Note = typeof notes.$inferSelect;
