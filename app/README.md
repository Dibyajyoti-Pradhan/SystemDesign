# System Design Lab

Long-running, visual-first study tool for system design interviews. Sits next to your existing `study-guide/` and `design-questions/` PDFs and turns them into an interactive learning surface.

## What it does

- **Topic explorer** — every concept is one MDX page with TL;DR / Standard / Deep tabs and inline Mermaid diagrams. Replaces dense PDF reading.
- **Spaced-repetition cards** — daily 15-min review loop. SM-2 scheduler. Cards generated from your topics by Claude, queued for your review before they go live.
- **Mock interview** — Claude plays interviewer over a question of your choice, then generates a graded rubric.
- **Concept map / cheatsheets / notes / search** — synthesis layer once the basics are in place.

## Setup

```bash
cd app
cp .env.example .env       # nothing to fill in — defaults are fine
npm install
npm run db:push            # apply Drizzle schema to SQLite
npm run seed               # seed topics + questions from PDFs in ../study-guide and ../design-questions
npm run dev                # http://localhost:3000
```

## AI features (no API key, uses your Claude Code subscription)

The mock-interview chat and the content-generation scripts shell out to the
`claude` CLI and use whatever Claude Code is logged in with — typically your
Pro/Max subscription. Make sure `claude` is on your PATH and you've run
`claude login` once.

```bash
npm run generate-topic <slug>     # generate MDX for one topic from its PDF
npm run generate-cards <slug>     # generate flashcards (land in pending review)
```

Generated MDX files live in `../content/topics/<category>/<slug>.mdx` — they're committed to git, so you edit them and the changes stick.

## Stack

Next.js 14 · TypeScript · Tailwind · shadcn/ui patterns · Drizzle ORM + SQLite · MDX · Mermaid · Claude Code CLI (subprocess) · React Flow.
