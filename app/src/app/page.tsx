import Link from "next/link";

// ─── Nav ─────────────────────────────────────────────────────────────────────
function Nav() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-zinc-950/90 backdrop-blur border-b border-zinc-800">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        <span className="text-base font-bold tracking-tight text-white">CareerLab</span>
        <Link
          href="/sign-in"
          className="text-sm text-zinc-400 hover:text-white transition-colors"
        >
          Sign in
        </Link>
      </div>
    </nav>
  );
}

// ─── Hero ─────────────────────────────────────────────────────────────────────
function Hero() {
  return (
    <section className="pt-32 pb-24 px-4 sm:px-6 text-center">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white leading-tight">
          Ace your system design interview.
        </h1>
        <p className="mt-6 text-lg sm:text-xl text-zinc-400 max-w-2xl mx-auto leading-relaxed">
          AI voice interviewer + live whiteboard + real-time feedback. Built for
          SWEs targeting Google, Meta, and Amazon.
        </p>
        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/sign-in"
            className="w-full sm:w-auto inline-flex items-center justify-center rounded-lg bg-emerald-500 px-7 py-3.5 text-sm font-semibold text-white hover:bg-emerald-400 transition-colors shadow-lg shadow-emerald-500/20"
          >
            Start free 7-day trial &rarr;
          </Link>
          <a
            href="#features"
            className="w-full sm:w-auto inline-flex items-center justify-center rounded-lg border border-zinc-700 px-7 py-3.5 text-sm font-semibold text-zinc-300 hover:border-zinc-500 hover:text-white transition-colors"
          >
            See how it works &darr;
          </a>
        </div>
        <p className="mt-5 text-xs text-zinc-500">
          No credit card required. Cancel anytime.
        </p>
      </div>
    </section>
  );
}

// ─── Problem ──────────────────────────────────────────────────────────────────
const PROBLEMS = [
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      </svg>
    ),
    title: "Mock interviews cost £200/hour",
    desc: "Inaccessible for most candidates who need consistent practice.",
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75 22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3-4.5 16.5" />
      </svg>
    ),
    title: "LeetCode won't save you",
    desc: "System design needs a different muscle — architecture thinking, not algorithms.",
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z" />
      </svg>
    ),
    title: "No real feedback",
    desc: "You finish and have no idea how you did or where you lost points.",
  },
];

function Problem() {
  return (
    <section className="py-20 px-4 sm:px-6 bg-zinc-900">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-2xl sm:text-3xl font-bold text-white text-center mb-12">
          Interview prep is broken.
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          {PROBLEMS.map((p) => (
            <div key={p.title} className="rounded-xl bg-zinc-800 p-6">
              <div className="text-emerald-500 mb-4">{p.icon}</div>
              <h3 className="font-semibold text-white mb-2">{p.title}</h3>
              <p className="text-sm text-zinc-400 leading-relaxed">{p.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Features ─────────────────────────────────────────────────────────────────
const FEATURES = [
  {
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.53 16.122a3 3 0 0 0-5.78 1.128 2.25 2.25 0 0 1-2.4 2.245 4.5 4.5 0 0 0 8.4-2.245c0-.399-.078-.78-.22-1.128Zm0 0a15.998 15.998 0 0 0 3.388-1.62m-5.043-.025a15.994 15.994 0 0 1 1.622-3.395m3.42 3.42a15.995 15.995 0 0 0 4.764-4.648l3.876-5.814a1.151 1.151 0 0 0-1.597-1.597L14.146 6.32a15.996 15.996 0 0 0-4.649 4.763m3.42 3.42a6.776 6.776 0 0 0-3.42-3.42" />
      </svg>
    ),
    title: "Live Whiteboard",
    desc: "Draw your architecture as you explain. The AI sees it and responds to what you're building.",
  },
  {
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
      </svg>
    ),
    title: "AI Interviewer",
    desc: "Realistic voice interviews tuned to Google, Meta, or Amazon style. No scheduling, no waiting.",
  },
  {
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
      </svg>
    ),
    title: "Instant Scoring",
    desc: "Communication, correctness, and efficiency scored after every session. See exactly where you lost points.",
  },
];

function Features() {
  return (
    <section id="features" className="py-20 px-4 sm:px-6">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-2xl sm:text-3xl font-bold text-white text-center mb-12">
          Everything you need to pass system design.
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-xl bg-zinc-900 border border-zinc-800 p-7">
              <div className="text-emerald-500 mb-4">{f.icon}</div>
              <h3 className="font-semibold text-white text-lg mb-2">{f.title}</h3>
              <p className="text-sm text-zinc-400 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── How it works ─────────────────────────────────────────────────────────────
const STEPS = [
  {
    num: "1",
    title: "Pick a topic",
    desc: "Choose System Design, Coding, or Behavioural. Select your target company.",
  },
  {
    num: "2",
    title: "Start a session",
    desc: "The AI asks questions, you draw and talk. It probes, pushes back, and digs deeper.",
  },
  {
    num: "3",
    title: "Get scored and improve",
    desc: "See exactly where you lost points — communication, correctness, efficiency — and what to fix.",
  },
];

function HowItWorks() {
  return (
    <section className="py-20 px-4 sm:px-6 bg-zinc-900">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-2xl sm:text-3xl font-bold text-white text-center mb-14">
          Three steps.
        </h2>
        <div className="space-y-8">
          {STEPS.map((s) => (
            <div key={s.num} className="flex gap-6 items-start">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
                <span className="text-emerald-400 font-bold text-sm">{s.num}</span>
              </div>
              <div>
                <h3 className="font-semibold text-white mb-1">{s.title}</h3>
                <p className="text-sm text-zinc-400 leading-relaxed">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Social proof ─────────────────────────────────────────────────────────────
const TESTIMONIALS = [
  {
    quote:
      "Finally a tool that makes me think out loud, not just grind Leetcode.",
    author: "Senior SWE, ex-Amazon",
  },
  {
    quote:
      "The AI interviewer is eerily realistic. Better than any mock I've paid for.",
    author: "Staff Eng, London",
  },
  {
    quote:
      "I got the Meta offer after 3 weeks of CareerLab sessions.",
    author: "SWE L5, Meta",
  },
];

function SocialProof() {
  return (
    <section className="py-20 px-4 sm:px-6">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-2xl sm:text-3xl font-bold text-white text-center mb-12">
          What engineers say.
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          {TESTIMONIALS.map((t) => (
            <div key={t.author} className="rounded-xl bg-zinc-900 border border-zinc-800 p-7">
              <p className="text-zinc-300 text-sm leading-relaxed mb-5">
                &ldquo;{t.quote}&rdquo;
              </p>
              <p className="text-xs text-zinc-500 font-medium">&mdash; {t.author}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Pricing ──────────────────────────────────────────────────────────────────
const PRICING_FEATURES = [
  "Unlimited AI interview sessions",
  "Live whiteboard in every session",
  "Google, Meta, Amazon interview styles",
  "Instant scoring + feedback",
  "Card review system",
];

function Pricing() {
  return (
    <section id="pricing" className="py-20 px-4 sm:px-6 bg-zinc-900">
      <div className="max-w-md mx-auto">
        <h2 className="text-2xl sm:text-3xl font-bold text-white text-center mb-10">
          One plan. Everything included.
        </h2>
        <div className="rounded-2xl bg-zinc-800 border border-zinc-700 overflow-hidden">
          {/* Price header */}
          <div className="bg-emerald-500/10 border-b border-zinc-700 px-8 py-8 text-center">
            <div className="flex items-end justify-center gap-1">
              <span className="text-5xl font-extrabold text-white">£35</span>
              <span className="mb-2 text-zinc-400 text-lg">/month</span>
            </div>
            <p className="mt-2 text-sm text-zinc-400">
              7-day free trial &mdash; cancel anytime
            </p>
          </div>
          {/* Features list */}
          <div className="px-8 py-8">
            <ul className="space-y-3 mb-8">
              {PRICING_FEATURES.map((f) => (
                <li key={f} className="flex items-center gap-3 text-sm text-zinc-300">
                  <svg
                    className="w-4 h-4 text-emerald-500 flex-shrink-0"
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2.5}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="2 8 6 12 14 4" />
                  </svg>
                  {f}
                </li>
              ))}
            </ul>
            <Link
              href="/sign-in"
              className="block w-full text-center rounded-lg bg-emerald-500 px-6 py-3.5 text-sm font-semibold text-white hover:bg-emerald-400 transition-colors shadow-lg shadow-emerald-500/20"
            >
              Start free 7-day trial
            </Link>
            <p className="mt-4 text-center text-xs text-zinc-500">
              No credit card required.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── FAQ ──────────────────────────────────────────────────────────────────────
const FAQS = [
  {
    q: "What is CareerLab?",
    a: "An AI-powered interview prep platform combining voice interviews, live whiteboard, and instant scoring.",
  },
  {
    q: "How is this different from mock interviews?",
    a: "Available 24/7, costs a fraction of human mocks, and gives consistent objective scoring every time.",
  },
  {
    q: "What companies are supported?",
    a: "Google, Meta, Amazon, and a generic mode for other companies.",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes. Cancel from your account settings. No lock-in, no questions asked.",
  },
  {
    q: "Is my data private?",
    a: "Yes. Your sessions are private and not used to train any AI models.",
  },
];

function FAQ() {
  return (
    <section className="py-20 px-4 sm:px-6">
      <div className="max-w-2xl mx-auto">
        <h2 className="text-2xl sm:text-3xl font-bold text-white text-center mb-12">
          Questions.
        </h2>
        <div className="space-y-6">
          {FAQS.map((faq) => (
            <div key={faq.q} className="border-b border-zinc-800 pb-6">
              <h3 className="font-semibold text-white mb-2">{faq.q}</h3>
              <p className="text-sm text-zinc-400 leading-relaxed">{faq.a}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Footer ───────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer className="border-t border-zinc-800 py-10 px-4 sm:px-6 bg-zinc-950">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <p className="text-sm text-zinc-500 text-center sm:text-left">
          &copy; 2026 CareerLab. Built for engineers who want the job.
        </p>
        <div className="flex items-center gap-6">
          <Link href="/sign-in" className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors">
            Sign in
          </Link>
          <a href="#pricing" className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors">
            Pricing
          </a>
        </div>
      </div>
    </footer>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function LandingPage() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <Problem />
        <Features />
        <HowItWorks />
        <SocialProof />
        <Pricing />
        <FAQ />
      </main>
      <Footer />
    </>
  );
}
