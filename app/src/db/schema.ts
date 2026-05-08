import { sqliteTable, text, integer, real, index } from "drizzle-orm/sqlite-core";
import { sql } from "drizzle-orm";

export const topics = sqliteTable("topics", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  slug: text("slug").notNull().unique(),
  category: text("category").notNull(),
  categoryOrder: integer("category_order").notNull().default(0),
  topicOrder: integer("topic_order").notNull().default(0),
  title: text("title").notNull(),
  summary: text("summary").notNull().default(""),
  mdxPath: text("mdx_path"),
  pdfPath: text("pdf_path"),
  mastery: integer("mastery").notNull().default(0),
  lastVisitedAt: integer("last_visited_at", { mode: "timestamp" }),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull().default(sql`(unixepoch())`),
});

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
  slug: text("slug").notNull().unique(),
  number: integer("number"),
  title: text("title").notNull(),
  difficulty: text("difficulty").notNull().default("medium"),
  tags: text("tags").notNull().default("[]"),
  pdfPath: text("pdf_path"),
  mdxPath: text("mdx_path"),
  estMinutes: integer("est_minutes").notNull().default(45),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull().default(sql`(unixepoch())`),
});

export const cards = sqliteTable(
  "cards",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
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
    dueAt: integer("due_at", { mode: "timestamp" }),
    lastReviewedAt: integer("last_reviewed_at", { mode: "timestamp" }),
    generatedByModel: text("generated_by_model"),
    createdAt: integer("created_at", { mode: "timestamp" }).notNull().default(sql`(unixepoch())`),
  },
  (t) => ({
    statusDueIdx: index("cards_status_due_idx").on(t.status, t.dueAt),
    topicIdx: index("cards_topic_idx").on(t.topicId),
  }),
);

export const reviews = sqliteTable(
  "reviews",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    cardId: integer("card_id").notNull().references(() => cards.id),
    rating: integer("rating").notNull(),
    prevInterval: real("prev_interval").notNull(),
    nextInterval: real("next_interval").notNull(),
    reviewedAt: integer("reviewed_at", { mode: "timestamp" }).notNull().default(sql`(unixepoch())`),
  },
  (t) => ({
    cardIdx: index("reviews_card_idx").on(t.cardId),
  }),
);

export const interviewSessions = sqliteTable("interview_sessions", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  questionId: integer("question_id").notNull().references(() => questions.id),
  mode: text("mode", { enum: ["self", "ai_vs_ai"] }).notNull().default("self"),
  startedAt: integer("started_at", { mode: "timestamp" }).notNull().default(sql`(unixepoch())`),
  endedAt: integer("ended_at", { mode: "timestamp" }),
  transcript: text("transcript").notNull().default("[]"),
  rubric: text("rubric"),
  score: integer("score"),
});

export const notes = sqliteTable(
  "notes",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    topicId: integer("topic_id").references(() => topics.id),
    questionId: integer("question_id").references(() => questions.id),
    body: text("body").notNull(),
    createdAt: integer("created_at", { mode: "timestamp" }).notNull().default(sql`(unixepoch())`),
    updatedAt: integer("updated_at", { mode: "timestamp" }).notNull().default(sql`(unixepoch())`),
  },
  (t) => ({
    topicIdx: index("notes_topic_idx").on(t.topicId),
    questionIdx: index("notes_question_idx").on(t.questionId),
  }),
);

export type Topic = typeof topics.$inferSelect;
export type NewTopic = typeof topics.$inferInsert;
export type Question = typeof questions.$inferSelect;
export type Card = typeof cards.$inferSelect;
export type NewCard = typeof cards.$inferInsert;
export type Review = typeof reviews.$inferSelect;
export type InterviewSession = typeof interviewSessions.$inferSelect;
export type Note = typeof notes.$inferSelect;
