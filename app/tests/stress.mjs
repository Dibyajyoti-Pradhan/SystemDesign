// Production stress test for the Career Lab study app.
// Hits every public route, both tracks, edge cases, plus concurrent burst.

const BASE = "http://localhost:3000";

const SD_TOPIC = "core-system-design-fundamentals-cap-theorem";
const SD_TOPIC_RAW = "core-system-design-fundamentals-mapreduce";
const SD_QUESTION = "01-typeahead-and-autocomplete";
const CODING_TOPIC_GENERATED = "jvm-internals-jdk-vs-jre-vs-jvm";
const CODING_TOPIC_RAW = "jvm-internals-class-loading-phases";
const CODING_QUESTION = "java-01-explain-jdk-vs-jre-vs-jvm-what-does-each-contain-and-when-do-you-reach-for-which";
const SD_CHEATSHEET = "latency-numbers";
const CODING_CHEATSHEET = "big-o";

const checks = [
  ["/",                                    307, "root → /system-design"],
  ["/topics",                              307, "legacy redirect"],
  ["/questions",                           307, "legacy redirect"],
  ["/review",                              307, "legacy redirect"],
  ["/cheatsheets",                         307, "legacy redirect"],
  ["/interview",                           307, "legacy redirect"],
  ["/interview/ai-vs-ai",                  307, "legacy redirect"],
  ["/system-design",                       200, "SD home"],
  ["/coding",                              200, "Coding home"],
  ["/system-design/topics",                200, "SD topics list"],
  ["/coding/topics",                       200, "Coding topics list"],
  ["/coding/topics?lang=java",             200, "Coding topics filtered"],
  ["/coding/topics?lang=python",           200, "Coding topics empty"],
  ["/system-design/questions",             200, "SD questions"],
  ["/coding/questions",                    200, "Coding questions"],
  ["/coding/questions?lang=java",          200, "Coding questions filtered"],
  ["/system-design/review",                200, "SD review"],
  ["/coding/review",                       200, "Coding review"],
  ["/system-design/cheatsheets",           200, "SD cheatsheets"],
  ["/coding/cheatsheets",                  200, "Coding cheatsheets"],
  [`/system-design/topics/${SD_TOPIC}`,            200, "SD topic detail (MDX)"],
  [`/system-design/topics/${SD_TOPIC_RAW}`,        200, "SD topic detail (raw PDF)"],
  [`/system-design/questions/${SD_QUESTION}`,      200, "SD question detail"],
  [`/coding/topics/${CODING_TOPIC_GENERATED}`,     200, "Coding topic (MDX)"],
  [`/coding/topics/${CODING_TOPIC_RAW}`,           200, "Coding topic (raw)"],
  [`/coding/questions/${CODING_QUESTION}`,         200, "Coding question (title-only)"],
  [`/system-design/cheatsheets/${SD_CHEATSHEET}`,  200, "SD cheatsheet"],
  [`/coding/cheatsheets/${CODING_CHEATSHEET}`,     200, "Coding cheatsheet"],
  ["/concept-map",                         200, "Concept map"],
  ["/notes",                               200, "Notes"],
  ["/search",                              200, "Search empty"],
  ["/search?q=cache",                      200, "Search with query"],
  ["/admin/cards",                         200, "Admin cards"],
  ["/badtrack/topics",                     404, "Bad track 404"],
  ["/system-design/topics/nope-x",         404, "Bad topic slug 404"],
  ["/system-design/questions/nope",        404, "Bad question slug 404"],
  ["/coding/cheatsheets/nope",             404, "Bad cheatsheet 404"],
  ["/api/search?q=cache",                  200, "Search API"],
  ["/api/search?q=",                       200, "Search API empty"],
];

async function once(p, expect) {
  const t0 = performance.now();
  try {
    const r = await fetch(BASE + p, { redirect: "manual" });
    return { p, expect, status: r.status, ok: r.status === expect, ms: Math.round(performance.now() - t0) };
  } catch (e) {
    return { p, expect, status: -1, ok: false, ms: -1, err: e.message };
  }
}

function pct(arr, p) {
  const sorted = [...arr].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length))];
}

async function main() {
  console.log(`\n══════ Sequential coverage (${checks.length} routes) ══════`);
  const seq = [];
  for (const [p, expect, desc] of checks) {
    const r = await once(p, expect);
    seq.push({ ...r, desc });
    console.log(`${r.ok ? "✓" : "✗"} ${String(r.status).padEnd(3)} ${r.ms.toString().padStart(4)}ms  ${p}  ${desc}`);
  }
  const seqPass = seq.filter((r) => r.ok).length;
  const seqFail = seq.filter((r) => !r.ok).length;
  console.log(`\nSequential: ${seqPass} pass · ${seqFail} fail`);

  if (seqFail > 0) {
    console.log("Failures:");
    for (const r of seq.filter((r) => !r.ok)) {
      console.log(`  ✗ got ${r.status} expected ${r.expect}  ${r.p}${r.err ? "  " + r.err : ""}`);
    }
  }

  // Concurrent burst on 4 hot pages
  console.log(`\n══════ Concurrent burst (200 reqs across 4 pages, 50 each) ══════`);
  const hot = ["/system-design/topics", "/coding/questions", "/concept-map", "/system-design/topics/" + SD_TOPIC];
  const reqs = [];
  for (let i = 0; i < 50; i++) for (const p of hot) reqs.push(once(p, 200));
  const t0 = performance.now();
  const burst = await Promise.all(reqs);
  const burstMs = Math.round(performance.now() - t0);
  const ms = burst.map((r) => r.ms).filter((x) => x >= 0);
  console.log(`200 requests in ${burstMs}ms`);
  console.log(`  pass: ${burst.filter((r) => r.ok).length} · fail: ${burst.filter((r) => !r.ok).length}`);
  console.log(`  p50: ${pct(ms, 50)}ms · p95: ${pct(ms, 95)}ms · p99: ${pct(ms, 99)}ms · max: ${Math.max(...ms)}ms`);
  console.log(`  effective throughput: ${Math.round((200 / burstMs) * 1000)} req/s`);

  // 3 sustained waves to look for memory leaks / connection exhaustion
  console.log(`\n══════ Sustained: 3 waves of 100 mixed reqs ══════`);
  const mixed = checks.filter(([, expect]) => expect === 200).map(([p]) => p);
  for (let wave = 1; wave <= 3; wave++) {
    const r = [];
    for (let i = 0; i < 100; i++) r.push(once(mixed[i % mixed.length], 200));
    const tw = performance.now();
    const w = await Promise.all(r);
    const wms = Math.round(performance.now() - tw);
    const wmss = w.map((x) => x.ms).filter((x) => x >= 0);
    console.log(`  wave ${wave}: ${wms}ms · ${w.filter((x) => x.ok).length}/100 pass · p50 ${pct(wmss, 50)}ms p95 ${pct(wmss, 95)}ms`);
  }

  // PDF stream test
  console.log(`\n══════ PDF streaming (10 concurrent) ══════`);
  const pdfPath = "system-design/design-questions/01 - TypeAhead and Autocomplete.pdf";
  const pdfReqs = Array.from({ length: 10 }, () => fetch(BASE + "/api/pdf?path=" + encodeURIComponent(pdfPath)));
  const tp = performance.now();
  const pdfRes = await Promise.all(pdfReqs);
  let totalBytes = 0;
  for (const r of pdfRes) totalBytes += (await r.arrayBuffer()).byteLength;
  const pms = Math.round(performance.now() - tp);
  console.log(`  10 PDFs · ${(totalBytes / 1024 / 1024).toFixed(1)} MB total · ${pms}ms · ${(totalBytes / pms / 1024).toFixed(1)} KB/ms`);

  // Memory snapshot via /api/search (cheap enough endpoint)
  const totalPass = seqPass + burst.filter((r) => r.ok).length;
  const totalFail = seqFail + burst.filter((r) => !r.ok).length;
  console.log(`\n══════ TOTAL: ${totalPass} pass · ${totalFail} fail ══════`);
  process.exit(totalFail > 0 ? 1 : 0);
}

main();
