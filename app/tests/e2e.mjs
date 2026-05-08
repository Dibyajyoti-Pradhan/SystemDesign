// End-to-end QA suite for Career Lab.
// Tests real flows: CRUD mutations, SRS scheduling, session lifecycle,
// AI-vs-AI steer, search, plus 1 light AI smoke (assistant chat).

import { execSync } from "node:child_process";

const BASE = "http://localhost:3000";
const DB = "/Users/dibyajyotipradhan/Desktop/Career Hub/SystemDesign/app/data/study.db";

function sqlite(query) {
  return execSync(`sqlite3 "${DB}" "${query.replace(/"/g, '\\"')}"`, { encoding: "utf8" }).trim();
}

const log = {
  pass: (n) => console.log(`  ✓ ${n}`),
  fail: (n, msg) => console.log(`  ✗ ${n}  ${msg ?? ""}`),
  step: (n) => console.log(`\n══ ${n} ══`),
  info: (m) => console.log(`    ${m}`),
};

let passed = 0;
let failed = 0;
function assert(cond, name, msg) {
  if (cond) { log.pass(name); passed++; }
  else      { log.fail(name, msg); failed++; }
}

const cleanup = { noteIds: [], cardIds: [], sessionIds: [] };

// ============ READ-ONLY SANITY ============
async function readOnly() {
  log.step("Read-only sanity");
  const checks = [
    ["/system-design", 200],
    ["/coding", 200],
    ["/system-design/topics", 200],
    ["/coding/questions?lang=java", 200],
    ["/concept-map", 200],
  ];
  for (const [p, expect] of checks) {
    const r = await fetch(BASE + p, { redirect: "manual" });
    assert(r.status === expect, `GET ${p} (${expect})`, `got ${r.status}`);
  }
}

// ============ NOTES CRUD ============
async function notesCrud() {
  log.step("Notes CRUD");

  // CREATE
  const create = await fetch(BASE + "/api/notes", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ body: "E2E test note — caching is one cache too many" }),
  });
  const note = await create.json();
  assert(create.status === 200 && note.id > 0, "POST /api/notes creates", `status=${create.status}`);
  cleanup.noteIds.push(note.id);

  // READ — note appears on /notes page
  const list = await fetch(BASE + "/notes");
  const html = await list.text();
  assert(html.includes("E2E test note"), "Note appears on /notes page");

  // VALIDATION — empty body should 400
  const bad = await fetch(BASE + "/api/notes", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ body: "" }),
  });
  assert(bad.status === 400, "POST /api/notes 400 on empty body", `got ${bad.status}`);

  // DELETE via DELETE method
  const del = await fetch(BASE + `/api/notes/${note.id}`, { method: "DELETE" });
  assert(del.ok, "DELETE /api/notes/:id", `status=${del.status}`);

  // DB should reflect deletion
  const remaining = sqlite(`SELECT count(*) FROM notes WHERE id=${note.id};`);
  assert(remaining === "0", "Note row gone from DB", `count=${remaining}`);
  cleanup.noteIds = cleanup.noteIds.filter((id) => id !== note.id);
}

// ============ SRS FLOW ============
async function srsFlow() {
  log.step("SRS card flow (pending → approve → review → schedule)");

  // Pick a topic to attach the card to
  const topicId = Number(sqlite(`SELECT id FROM topics WHERE track='system-design' LIMIT 1;`));
  assert(topicId > 0, "Found a topic to attach card to");

  // Insert a pending card directly. Use RETURNING so we get the id back from
  // the same connection (each sqlite3 invocation is a new connection so
  // last_insert_rowid() across calls is unreliable).
  const inserted = sqlite(
    `INSERT INTO cards (topic_id, type, front, back, status) VALUES (${topicId}, 'definition', 'E2E TEST: What is caching?', 'Storing computed/fetched data closer to consumers to cut latency and load on origins.', 'pending_review') RETURNING id;`,
  );
  const cardId = Number(inserted);
  cleanup.cardIds.push(cardId);
  assert(cardId > 0, "Pending card created in DB", `inserted=${inserted}`);

  // Should appear on /admin/cards
  const adminPage = await fetch(BASE + "/admin/cards");
  const adminHtml = await adminPage.text();
  assert(adminHtml.includes("E2E TEST: What is caching?"), "Pending card visible on /admin/cards");

  // PATCH — edit content
  const patch = await fetch(BASE + `/api/cards/${cardId}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ front: "E2E TEST V2: Define caching", back: "Storing recently/often-accessed data in faster storage." }),
  });
  assert(patch.ok, "PATCH /api/cards/:id");
  const after = sqlite(`SELECT front FROM cards WHERE id=${cardId};`);
  assert(after.includes("V2"), "Card content updated in DB", `got "${after}"`);

  // POST action=approve
  const approve = await fetch(BASE + `/api/cards/${cardId}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ action: "approve" }),
  });
  assert(approve.ok, "POST /api/cards/:id approve");
  const status = sqlite(`SELECT status FROM cards WHERE id=${cardId};`);
  assert(status === "active", "Card status now 'active'", `got "${status}"`);

  // Now the card should appear on /system-design/review
  const review = await fetch(BASE + "/system-design/review");
  const reviewHtml = await review.text();
  assert(reviewHtml.includes("V2: Define caching") || reviewHtml.includes("Define caching"), "Approved card appears on /review");

  // Submit a "Good" rating
  const rate = await fetch(BASE + `/api/cards/${cardId}/review`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ rating: 3 }),
  });
  assert(rate.ok, "POST /api/cards/:id/review rating=3", `status=${rate.status}`);

  // Verify scheduling: ease should still be 2.5, interval/dueAt set
  const sched = sqlite(`SELECT ease, interval_days, repetitions, due_at FROM cards WHERE id=${cardId};`);
  const [ease, interval, reps, dueAt] = sched.split("|");
  assert(Number(reps) >= 1, "Repetitions incremented", `reps=${reps}`);
  assert(Number(interval) >= 1, "Interval scheduled (≥1 day)", `interval=${interval}`);
  assert(Number(dueAt) > 0, "dueAt set in future");

  // Reviews row inserted
  const reviewRows = sqlite(`SELECT count(*) FROM reviews WHERE card_id=${cardId};`);
  assert(reviewRows === "1", "Review row recorded");

  // Test "Again" rating resets schedule
  const rateAgain = await fetch(BASE + `/api/cards/${cardId}/review`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ rating: 1 }),
  });
  assert(rateAgain.ok, "Submit rating=1 (Again)");
  const lapses = sqlite(`SELECT lapses FROM cards WHERE id=${cardId};`);
  assert(Number(lapses) >= 1, "Lapses incremented on Again", `lapses=${lapses}`);
}

// ============ SESSION CRUD ============
async function sessionFlow() {
  log.step("Session lifecycle (create, view, delete)");

  // Create AI-vs-AI session via the start route
  const slug = "01-typeahead-and-autocomplete";
  const start = await fetch(BASE + `/interview/ai-vs-ai/start/${slug}`, { redirect: "manual" });
  assert(start.status === 307, "Start route returns 307");
  const loc = start.headers.get("location") ?? "";
  const sessionId = Number(loc.split("/").pop());
  assert(sessionId > 0, "Session ID extracted from redirect", `loc=${loc}`);
  cleanup.sessionIds.push(sessionId);

  // Verify DB row
  const row = sqlite(`SELECT mode FROM interview_sessions WHERE id=${sessionId};`);
  assert(row === "ai_vs_ai", "Session created with mode=ai_vs_ai", `got "${row}"`);

  // Detail page renders
  const detail = await fetch(BASE + `/interview/sessions/${sessionId}`);
  const html = await detail.text();
  assert(detail.ok, `GET /interview/sessions/${sessionId}`);
  assert(html.includes("AI vs AI"), "Detail page renders AI-vs-AI UI");
  assert(html.includes("TypeAhead"), "Detail page shows question title");

  // Inject a steer (no streaming, no quota burn)
  const steer = await fetch(BASE + "/api/interview/ai-vs-ai/steer", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ sessionId, content: "E2E: focus on partition key choice", target: "interviewer" }),
  });
  assert(steer.ok, "POST /api/interview/ai-vs-ai/steer accepts steer");

  // Steer should be in transcript JSON
  const transcript = sqlite(`SELECT transcript FROM interview_sessions WHERE id=${sessionId};`);
  assert(transcript.includes("partition key choice"), "Steer message persisted to transcript");
  assert(transcript.includes('"target":"interviewer"'), "Steer target=interviewer recorded");

  // DELETE
  const del = await fetch(BASE + `/api/interview/sessions/${sessionId}`, { method: "DELETE" });
  assert(del.ok, "DELETE /api/interview/sessions/:id");
  const remaining = sqlite(`SELECT count(*) FROM interview_sessions WHERE id=${sessionId};`);
  assert(remaining === "0", "Session removed from DB");
  cleanup.sessionIds = cleanup.sessionIds.filter((id) => id !== sessionId);

  // Idempotent delete: second time = 404
  const delAgain = await fetch(BASE + `/api/interview/sessions/${sessionId}`, { method: "DELETE" });
  assert(delAgain.status === 404, "Second DELETE returns 404");
}

// ============ TOPIC VISIT TRACKING ============
async function visitTracking() {
  log.step("Topic visit tracking");
  const slug = "core-system-design-fundamentals-cap-theorem";
  const before = sqlite(`SELECT last_visited_at FROM topics WHERE slug='${slug}';`);

  // Visit it
  const visit = await fetch(BASE + `/system-design/topics/${slug}`);
  assert(visit.ok, `GET /system-design/topics/${slug}`);

  // Wait briefly for fire-and-forget DB update
  await new Promise((r) => setTimeout(r, 600));

  const after = sqlite(`SELECT last_visited_at FROM topics WHERE slug='${slug}';`);
  assert(after !== before && after !== "", "lastVisitedAt updated", `before="${before}" after="${after}"`);
}

// ============ SEARCH ============
async function searchApi() {
  log.step("Search API");
  const r = await fetch(BASE + "/api/search?q=cache");
  const data = await r.json();
  assert(r.ok, "GET /api/search?q=cache");
  assert(Array.isArray(data.hits) && data.hits.length > 0, "Search returns hits", `count=${data.hits?.length}`);
  const titles = data.hits.map((h) => h.title.toLowerCase());
  assert(titles.some((t) => t.includes("cach")), "Hits include 'cach' substring");

  // Empty query
  const empty = await fetch(BASE + "/api/search?q=");
  const emptyData = await empty.json();
  assert(empty.ok && Array.isArray(emptyData.hits) && emptyData.hits.length === 0, "Empty query returns empty hits");
}

// ============ ASSISTANT VALIDATION ============
async function assistantValidation() {
  log.step("Assistant API validation");
  // Empty messages
  const empty = await fetch(BASE + "/api/assistant/chat", {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ messages: [] }),
  });
  assert(empty.status === 400, "Empty messages → 400");

  // Last message must be user
  const wrong = await fetch(BASE + "/api/assistant/chat", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ messages: [{ role: "assistant", content: "x" }] }),
  });
  assert(wrong.status === 400, "Last-message-not-user → 400");

  // Bad JSON
  const badJson = await fetch(BASE + "/api/assistant/chat", {
    method: "POST", headers: { "content-type": "application/json" }, body: "{nope",
  });
  assert(badJson.status === 400, "Bad JSON → 400");
}

// ============ PDF STREAM ============
async function pdfStream() {
  log.step("PDF route");
  const ok = await fetch(BASE + "/api/pdf?path=" + encodeURIComponent("system-design/design-questions/01 - TypeAhead and Autocomplete.pdf"));
  assert(ok.ok && ok.headers.get("content-type") === "application/pdf", "Valid PDF served as application/pdf");

  // Path traversal blocked
  const bad = await fetch(BASE + "/api/pdf?path=" + encodeURIComponent("../../etc/passwd"));
  assert(bad.status === 403 || bad.status === 404, "Path traversal blocked", `status=${bad.status}`);

  // Nonexistent
  const missing = await fetch(BASE + "/api/pdf?path=" + encodeURIComponent("nope.pdf"));
  assert(missing.status === 404, "Missing PDF → 404");
}

// ============ MERMAID + MDX RENDER ============
async function mdxRender() {
  log.step("MDX/Mermaid topic rendering");
  const r = await fetch(BASE + "/system-design/topics/core-system-design-fundamentals-cap-theorem");
  const html = await r.text();
  assert(r.ok, "Topic detail loads");
  assert(html.includes("CAP"), "Title text rendered");
  // The MDX content contains depth tabs
  assert(html.includes("TL;DR") || html.includes("Standard"), "Depth tabs visible");
  // Mermaid diagram source (the `pre` falls back to a Mermaid component on the client; we just check the source code is server-rendered as part of the page)
  assert(html.includes("flowchart") || html.includes("mermaid"), "Mermaid diagram source present");
}

// ============ CONCEPT MAP DATA ============
async function conceptMap() {
  log.step("Concept map data");
  const r = await fetch(BASE + "/concept-map");
  const html = await r.text();
  assert(r.ok, "GET /concept-map");
  // We seeded 44 directional links; the page should mention "relationships"
  assert(html.includes("relationships") || html.match(/\d+\s+topics/), "Page shows topic+relationship counts");
}

// ============ AI SMOKE: assistant chat (1 small call) ============
async function assistantSmoke() {
  log.step("Assistant chat — 1 light AI call (uses subscription quota)");
  const t0 = Date.now();
  const res = await fetch(BASE + "/api/assistant/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      messages: [{ role: "user", content: "Reply with just one word: PONG" }],
      pathname: "/system-design/topics/core-system-design-fundamentals-cap-theorem",
    }),
  });
  assert(res.ok, "POST /api/assistant/chat 200");

  // Stream the response
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let acc = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    acc += dec.decode(value, { stream: true });
  }
  const ms = Date.now() - t0;
  const matches = /pong/i.test(acc);
  assert(matches, "Streamed response contains 'PONG'", `body="${acc.slice(0, 100)}"`);
  log.info(`stream done in ${ms}ms, ${acc.length} chars`);
}

// ============ MAIN ============
async function main() {
  console.log("════════════════════════════════════════════════════");
  console.log("  Career Lab — End-to-End QA");
  console.log("════════════════════════════════════════════════════");

  try {
    await readOnly();
    await notesCrud();
    await srsFlow();
    await sessionFlow();
    await visitTracking();
    await searchApi();
    await assistantValidation();
    await pdfStream();
    await mdxRender();
    await conceptMap();
    await assistantSmoke();
  } catch (e) {
    console.error("UNCAUGHT ERROR:", e.message);
    failed++;
  }

  // Cleanup test artifacts
  if (cleanup.noteIds.length || cleanup.cardIds.length || cleanup.sessionIds.length) {
    console.log("\n══ Cleanup ══");
    if (cleanup.noteIds.length) sqlite(`DELETE FROM notes WHERE id IN (${cleanup.noteIds.join(",")});`);
    if (cleanup.cardIds.length) {
      sqlite(`DELETE FROM reviews WHERE card_id IN (${cleanup.cardIds.join(",")});`);
      sqlite(`DELETE FROM cards WHERE id IN (${cleanup.cardIds.join(",")});`);
    }
    if (cleanup.sessionIds.length) sqlite(`DELETE FROM interview_sessions WHERE id IN (${cleanup.sessionIds.join(",")});`);
    log.info(`removed: ${cleanup.noteIds.length} note(s), ${cleanup.cardIds.length} card(s), ${cleanup.sessionIds.length} session(s)`);
  }

  console.log("\n════════════════════════════════════════════════════");
  console.log(`  RESULT: ${passed} pass · ${failed} fail`);
  console.log("════════════════════════════════════════════════════");
  process.exit(failed > 0 ? 1 : 0);
}

main();
