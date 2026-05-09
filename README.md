# Career Lab

Self-hosted study tool for system-design and coding interviews. Turns a folder of PDFs into an interactive learning surface — topic explorer, spaced-repetition cards, mock interviews with Claude, and a concept map across them.

Runs entirely on your machine. SQLite for data, Next.js for the UI, the `claude` CLI for the AI features (uses your existing Claude subscription — no API key).

---

## What's inside

- **Topic explorer** — every concept becomes one MDX page with TL;DR / Standard / Deep tabs and inline Mermaid diagrams.
- **Spaced-repetition cards** — daily review queue. SM-2 scheduler. Cards are generated from your topics by Claude and queued for your approval before going live.
- **Mock interview** — Claude plays interviewer over a question of your choice, then auto-grades to a rubric. Two modes:
  - **Self mode** — you're the candidate, Claude is the interviewer.
  - **AI vs AI** — two Claudes interview each other while you watch and inject "steers" mid-conversation.
- **Concept map** — clickable graph of every topic and how they relate.
- **Cheatsheets / notes / search** — synthesis layer once the basics are in place.

Two **tracks** ship out of the box: `system-design` and `coding`.

---

## Prerequisites

| Tool | Version | Why |
|---|---|---|
| Node.js | **22** (pinned in `.nvmrc`) | runtime + Next.js |
| `claude` CLI | latest | AI features (interview, topic gen, card gen) |
| `sqlite3` | any modern | optional — only for inspecting the DB or running `npm run test:e2e` |

Set up Claude:

```bash
# install (if you don't have it)
npm i -g @anthropic-ai/claude-code

# log in once — uses your Pro/Max subscription, no API key needed
claude login
```

If you'd rather pay per token, set `ANTHROPIC_API_KEY=sk-ant-...` in `.env` and the CLI will use that instead.

---

## Quick start

```bash
git clone <repo-url> career-lab
cd career-lab/app

cp .env.example .env       # defaults are fine
npm install
npm run db:push            # apply Drizzle schema to SQLite
npm run seed               # index PDFs from ../system-design and ../coding
npm run dev                # http://localhost:3000
```

That gives you a working app with topics + questions seeded from the PDFs in the repo. The MDX content for each topic is generated lazily — open any topic and click **Generate** to have Claude write it (then commits to `../content/`).

To bulk-generate content up front:

```bash
npm run generate-topic <slug>     # one topic
npm run generate-cards <slug>     # flashcards for one topic (queued for review)
```

---

## ⚠️ macOS users — read this before cloning

If you have **iCloud Drive's "Desktop & Documents Folders"** sync enabled, do **NOT** clone this repo into `~/Desktop` or `~/Documents`. macOS will silently evict build artifacts and SQLite pages under disk pressure, and you'll get random `MODULE_NOT_FOUND`, `Cannot find module './vendor-chunks/…'`, and `disk I/O error` failures that have nothing to do with your code.

Use `~/Code/`, `~/dev/`, `~/src/`, or any path outside iCloud's sync. If you must keep it on Desktop, the project ships with a `.next.nosync` build directory and you'll need to symlink `node_modules`/`data` to `.nosync` siblings — see [Troubleshooting](#troubleshooting).

---

## Project layout

The git repo root contains both the app and its source materials:

```
career-lab/
├── app/                    # ← this Next.js app
│   ├── src/
│   ├── scripts/            # seed + generate scripts
│   ├── tests/              # e2e + stress
│   └── data/               # SQLite DB (gitignored)
│
├── system-design/
│   ├── study-guide/        # PDFs → become topics
│   └── design-questions/   # PDFs → become interview questions
│
├── coding/
│   ├── study-guide/        # PDFs → become topics
│   ├── interview-questions/ # PDFs → become questions
│   └── JavaSheet.md        # extra source for `npm run seed:java`
│
├── content/                # generated MDX (committed — edit and changes stick)
│   ├── system-design/{topics,questions,cheatsheets}/
│   └── coding/{topics,questions,cheatsheets}/
│
└── tools/                  # one-off helper scripts
```

The seed script reads the PDF directories at the repo root, so the relative path `../system-design/` from `app/` matters — don't move things around.

---

## Scripts

Run all scripts from the `app/` directory.

| Command | What it does |
|---|---|
| `npm run dev` | Start Next.js dev server on `localhost:3000` |
| `npm run build` | Production build (artifacts go to `.next.nosync/`) |
| `npm start` | Run the production build |
| `npm run start:fresh` | Wipe `.next/` + tsbuildinfo, rebuild, start |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run db:push` | Apply Drizzle schema to SQLite (idempotent) |
| `npm run db:studio` | Open Drizzle Studio at `localhost:4983` for browsing the DB |
| `npm run seed` | Index PDFs from `../system-design/` into topics + questions |
| `npm run seed:java` | Same for the coding track via `coding/JavaSheet.md` |
| `npm run backfill-mdx` | Re-link existing MDX files to DB rows after a re-seed |
| `npm run generate-topic <slug>` | Have Claude write MDX for one topic |
| `npm run generate-cards <slug>` | Have Claude write flashcards for one topic |
| `npm run test:e2e` | Full end-to-end suite (57 tests, hits real DB + AI) |
| `npm run test:stress` | Stress test (concurrent reads/writes) |

---

## How the AI calls work

Every AI feature shells out to the `claude` CLI. There's exactly one wrapper at [`app/src/lib/claude-cli.ts`](app/src/lib/claude-cli.ts). It calls `spawn("claude", args, { env: process.env })` — relies on `claude` being on your `PATH` and your own `claude login` for auth. No API tokens hardcoded anywhere.

Two modes:
- **`claudeRun`** — one-shot text generation (used for topic generation, card generation, interview grading).
- **`claudeStream`** — streaming with chunk-by-chunk delivery (used for the interview chat and the AI-vs-AI loop).

If `claude` isn't on your `PATH`, the routes return a clear `ClaudeCliNotFoundError` rather than failing silently.

---

## Database

SQLite at `app/data/study.db`. Schema in [`app/src/db/schema.ts`](app/src/db/schema.ts) via Drizzle.

- `db:push` is safe to re-run — it diffs against the live schema.
- For ad-hoc queries: `sqlite3 app/data/study.db` or `npm run db:studio` (from `app/`).
- Backups: `cp app/data/study.db app/data/study.db.bak`. The DB is gitignored.

The seed scripts are **idempotent**: re-running `npm run seed` updates existing rows by slug instead of duplicating.

---

## Troubleshooting

### `Cannot find module './vendor-chunks/...'` or `disk I/O error`
You're almost certainly on iCloud-synced storage. See the [macOS warning above](#-macos-users--read-this-before-cloning). Quick remedy if you can't move the project:

```bash
cd app
mv node_modules node_modules.nosync && ln -s node_modules.nosync node_modules
mv data data.nosync && ln -s data.nosync data
# (next.config.mjs already sets distDir: ".next.nosync")
rm -rf .next.nosync && npm run build && npm start
```

### `claude: command not found` when starting an interview
The `claude` CLI isn't on the path of the user that started `next dev`/`next start`. Check with `which claude` from the same shell. If you launch via VS Code's integrated terminal it'll often work; from a GUI launcher it may not.

### Empty topics / questions list after seeding
The seed script needs the PDF directories to exist. Verify `../system-design/study-guide/` and friends are populated. If you cloned a partial repo or mis-shaped the folder layout, the seed will silently produce zero rows.

### Port 3000 in use
```bash
PORT=3001 npm run dev
```

### Build/dev process won't die
```bash
pkill -f "next dev"; pkill -f "next-server"; pkill -f "next start"
```

---

## Stack

Next.js 14 (App Router) · TypeScript · Tailwind · shadcn-style UI primitives (Radix) · Drizzle ORM + better-sqlite3 · MDX (`next-mdx-remote`) · Mermaid · React Flow · `claude` CLI subprocess · Fuse.js search.

No external services other than the local `claude` CLI. No telemetry. Everything stays on your machine.
