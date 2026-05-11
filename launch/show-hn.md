Title: Show HN: CareerLab – AI voice interviewer + live whiteboard for system design prep

---

Hey HN,

I'm Dibyo — Senior SWE at HubSpot, previously at Meta and Amazon. I've been through the full big-tech interview loop more times than I'd like to count, and every time I walked out of a system design round I had the same problem: I had no idea how I'd actually done.

Mock interviews were expensive (£150–200/hour on Pramp Pro or with a coach) and the feedback was inconsistent. Most tools online are either just question banks, or they give you a text prompt and a timer. Nothing really simulates the dynamic of drawing out a system, talking through trade-offs in real time, and getting structured feedback afterwards.

So I built CareerLab.

**What it does:**

- You get an AI interviewer that asks system design questions in the style of your target company (Google, Meta, Amazon — each has a noticeably different interview culture)
- You talk through your answer while drawing on a live Excalidraw whiteboard, same as you would in a real interview
- At the end, you get a scored breakdown: communication, architecture, trade-off reasoning, completeness

The combination of voice + whiteboard + instant scoring is the thing I couldn't find anywhere else. Most tools pick one or two of these. CareerLab does all three in one session.

**Tech stack (briefly, since HN asks):**

Next.js 14, NextAuth, Postgres on Neon, Claude (Anthropic) for question generation and scoring, Fly.io for hosting. The whiteboard is Excalidraw embedded and synced to the session. Voice will use Deepgram for STT and ElevenLabs for TTS.

**Honest about where it is right now:**

Voice is the headline feature but it's shipping text-first. The voice pipeline (Deepgram + ElevenLabs) is built and working in development — I didn't want to block launch on it. If you want to test voice in the trial, I can send you the setup steps; it needs API keys you bring yourself for now. Text mode works fully.

**Current state:** Just launched. 7-day free trial, £35/month after that. No credit card required for the trial.

**What I'm looking for:**

Feedback from engineers who've actually prepared for or conducted system design interviews. Does the scoring rubric feel right? Are the per-company question styles accurate to your experience? Is there a workflow pain point I've missed?

I built this to solve my own problem — I'd be genuinely grateful to hear whether it solves yours.

Link: https://careerlab.so (placeholder — update before posting)

Happy to answer anything in the comments.
