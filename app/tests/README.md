# Tests

Two scripts. Both expect a server already running at `http://localhost:3000`.

## `npm run test:stress`

Sequential coverage of every public route + a 200-request concurrent burst + sustained waves to look for memory/connection leaks. ~3-5s wall time.

Run against production mode for accurate numbers:

```bash
npm run start:fresh   # in one terminal
npm run test:stress   # in another
```

## `npm run test:e2e`

Real end-to-end mutations — notes CRUD, SRS scheduling, session lifecycle, AI-vs-AI steer injection, topic visit tracking, search, PDF route + path-traversal block, MDX/Mermaid render, concept map, and one live assistant chat call.

Cleans up its own test artifacts (cards, sessions, notes) at the end. Burns ~$0.05 of subscription quota on the assistant chat smoke.

```bash
npm run start:fresh   # in one terminal
npm run test:e2e      # in another
```

## What's NOT covered

| Feature | Why |
|---|---|
| `generate-topic` end-to-end | Burns real quota; verified manually + via parallel-agent runs |
| `generate-brief` end-to-end | Same |
| AI-vs-AI streaming step | Each step is ~$0.05 quota; the steer write-path is tested |
| Mock interview self-mode | Same as AI-vs-AI step |
| Grading rubric round-trip | Needs real conversation history |

These all share the `claudeRun` / `claudeStream` wrapper, and the assistant chat smoke proves the wrapper streams correctly. Spot-test by clicking through the UI when needed.
