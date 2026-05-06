"""Source for `09 - Real-Time Collaborative Editor.pdf` (regenerated with errata applied)."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design a Real-Time Collaborative Editor",
    "subtitle": "Operational Transform, CRDTs & Multi-User Conflict Resolution",
    "read_time": "~ 35 minute read",
    "short_title": "Real-Time Collaborative Editor",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Overview & Scale",
            "subtitle": "What we are building",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Design a real-time collaborative document editor similar to "
                        "<strong>Google Docs</strong>. Multiple users edit the same document "
                        "simultaneously, see each other's cursors and edits within sub-second "
                        "latency, and continue working when offline — with all changes merging "
                        "deterministically when they reconnect."
                    ),
                },
                {"type": "h3", "text": "Scale Targets"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>1 billion documents</strong> stored across all users",
                        "<strong>100 million daily active users</strong> opening, editing, and sharing documents",
                        "<strong>50 concurrent users</strong> editing the same document simultaneously (typical; can spike higher)",
                        "<strong>Sub-second latency</strong> for seeing others' edits (cursor positions, text changes)",
                        "<strong>Offline support:</strong> users can edit without internet; sync when reconnecting",
                        "<strong>Conflict resolution:</strong> concurrent edits from multiple users must merge correctly",
                    ],
                },
                {"type": "h3", "text": "Key Challenges"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Consistency:</strong> ensure final document state is identical across all clients (eventual consistency)",
                        "<strong>Low latency:</strong> optimistic updates on the client for instant UI response",
                        "<strong>Conflict resolution:</strong> when two users insert text at the same position, one must win deterministically",
                        "<strong>Scalability:</strong> support millions of documents, billions of edits, high-throughput revision logs",
                        "<strong>Undo/Redo:</strong> per-user undo must not affect others' edits",
                        "<strong>Offline &amp; sync:</strong> buffer ops locally (IndexedDB), merge on reconnect",
                    ],
                },
            ],
        },
        # ---- 02 ------------------------------------------------------
        {
            "num": "02",
            "title": "Clarifying Questions",
            "subtitle": "Pinning down the scope",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Scope", "Question", "Assumption"],
                    "rows": [
                        ["Scope", "Real-time consistency requirement?",
                         "Eventual consistency; broadcast within 500ms–1s"],
                        ["Strategy", "Conflict resolution approach?",
                         "Operational Transform (simpler) or CRDT (better at scale)"],
                        ["Offline", "Must support offline editing?",
                         "Yes; sync on reconnect with conflict detection"],
                        ["Size", "Document size limits?",
                         "Up to 50MB per document (typical: &lt;1MB for collaborative editing)"],
                        ["History", "Revision history retention?",
                         "Last 30 days of full history; snapshots every 100 edits"],
                        ["Users", "Max concurrent users per doc?",
                         "Design for 50; graceful degradation up to 100+"],
                        ["Presence", "Show cursor positions &amp; user list?",
                         "Yes; real-time presence, color-coded cursors, typing indicators"],
                        ["Permissions", "Access control needed?",
                         "Yes; owner, editor, viewer roles; share permissions"],
                    ],
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "Math for scale",
            "blocks": [
                {"type": "h3", "text": "Concurrent Sessions & Operations"},
                {
                    "type": "bullets",
                    "items": [
                        "100M DAU × 10% concurrent: <strong>10M users online at peak</strong>",
                        "Avg 3 docs per user session: <strong>~30M active document sessions</strong> at peak",
                        "50 users per doc (median; 90th percentile 100+): key bottleneck = document session",
                        "Per-user edit rate: 1–5 operations/second (typing, delete, format changes)",
                        "Peak edit throughput: 30M docs × 2 ops/sec avg = <strong>60M ops/sec</strong> globally",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Worst-Case, Not Steady-State",
                    "body": (
                        "The 60M ops/sec figure assumes <strong>every</strong> active session is "
                        "actively typing at 2 ops/sec at the same instant — a worst-case envelope "
                        "for capacity planning, not a steady-state load. Real traffic is bursty: "
                        "most sessions are idle (reading, scrolling, formatting). A more realistic "
                        "steady-state is 5–10× lower. Size the system for the peak; don't pay for "
                        "it 24/7."
                    ),
                },
                {"type": "h3", "text": "Bandwidth & Latency"},
                {
                    "type": "bullets",
                    "items": [
                        "Op size: ~200 bytes per operation (JSON: type, pos, text, user_id, timestamp)",
                        "Broadcast fanout: 50 concurrent users per doc → 50 × 200 bytes = <strong>10KB per op per doc</strong>",
                        # ERRATUM 1 applied verbatim:
                        "Peak inbound: 60M ops/sec × 200 bytes = <strong>12 GB/sec</strong> (aggregated across regions)",
                        "Presence updates: 1 cursor/user/100ms = 500 cursors/doc per second at 50 users",
                        "Target latency: optimistic update immediate (0ms); server ack &lt;100ms; peer ops &lt;500ms",
                    ],
                },
                {"type": "h3", "text": "Storage & Revision History"},
                {
                    "type": "bullets",
                    "items": [
                        "Document snapshots: 1B docs × 50KB avg = <strong>50PB</strong> (compressed: ~20PB with gzip)",
                        "Revision log: 1 doc may have 10K–100K ops over lifetime; 1B docs × 50K ops avg × 200 bytes = <strong>10EB</strong> (archived/pruned)",
                        "Hot storage (last 30 days): ~100M active docs × 100 ops/day × 200 bytes = <strong>2PB</strong>",
                        "Index: <code>{doc_id, user_id, timestamp}</code> for revision lookup; sharded by doc_id",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "Peak ops: <strong>60M/sec</strong> (envelope) &nbsp;·&nbsp; "
                        "Inbound bandwidth: <strong>12 GB/sec</strong> &nbsp;·&nbsp; "
                        "Snapshot storage: <strong>~20PB</strong> compressed &nbsp;·&nbsp; "
                        "Hot tier: <strong>~2PB</strong> for the last 30 days"
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level System Architecture",
            "subtitle": "Three layers: client, real-time, persistence",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The system is divided into three main layers — clients, the real-time "
                        "collaboration tier (WebSocket gateway + OT engine + presence), and "
                        "persistence (snapshots, op log, archive). Each document is pinned to a "
                        "single OT engine instance via sticky session so the engine can serialize "
                        "ops without distributed consensus."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Figure 4.1: Client → WebSocket gateway → OT engine (sticky session per doc) → Postgres snapshots, Redis op log, Kafka events, S3 archive.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Clients"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Web    [label="Web / Mobile\n(IndexedDB cache)", fillcolor="#dbe6fb"];
    }
    subgraph cluster_rt {
        label="Real-Time Tier"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        WS  [label="WebSocket\nGateway", fillcolor="#cbeedf"];
        OT  [label="OT Engine\n(sticky per doc_id)", fillcolor="#cbeedf"];
        Pres[label="Presence /\nCursor Service", fillcolor="#cbeedf"];
    }
    subgraph cluster_data {
        label="Persistence"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        PG  [label="Postgres\n(snapshots)", fillcolor="#ead7fb"];
        RD  [label="Redis\n(op log + session)", fillcolor="#ead7fb"];
        KQ  [label="Kafka\n(events / notifs)", fillcolor="#fbd7c5"];
        S3  [label="S3 / Glacier\n(archived ops)", fillcolor="#ead7fb"];
    }

    Web -> WS [label="WebSocket\n(persistent)"];
    WS  -> OT  [label="route by\nhash(doc_id)"];
    WS  -> Pres [label="cursor msgs", style=dashed];
    OT  -> RD  [label="append op"];
    OT  -> PG  [label="snapshot\nevery 100 ops", style=dashed];
    OT  -> KQ  [label="doc events", style=dashed];
    RD  -> S3  [label="archive\n>30d", style=dashed];
    Pres -> RD [style=dashed];
}
""",
                },
                {"type": "h3", "text": "Client Layer"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Web/Mobile clients:</strong> browser or native app; maintains local doc state in memory",
                        "<strong>WebSocket connection:</strong> persistent bidirectional channel to collaboration server",
                        "<strong>Local cache (IndexedDB):</strong> store snapshot + recent ops for offline mode",
                        "<strong>Optimistic updates:</strong> apply edits immediately to UI while sending to server",
                    ],
                },
                {"type": "h3", "text": "WebSocket Gateway & Load Balancing"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Per-document routing:</strong> all users editing doc_id=X route to same server instance (sticky session)",
                        "<strong>Horizontal scaling:</strong> Hash(doc_id) → server instance; scale by sharding docs across backends",
                        "<strong>Connection multiplexing:</strong> one WebSocket per client; multiple docs per session via msg routing",
                        "<strong>Heartbeat & reconnection:</strong> detect stale connections; fast reconnect with op backfill",
                    ],
                },
                {"type": "h3", "text": "Collaboration Services"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>OT/CRDT Engine:</strong> transform incoming ops against concurrent ops; compute final state",
                        "<strong>Document Session Manager:</strong> maintain active doc state, session metadata, user list per doc",
                        "<strong>Cursor/Presence Service:</strong> track real-time cursor positions, typing indicators, user colors",
                    ],
                },
                {"type": "h3", "text": "Storage Layer"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Document Store (Postgres / Firestore / Bigtable):</strong> persistent snapshots; schema: <code>{doc_id, snapshot, version, timestamp}</code>",
                        "<strong>Op Log (Redis):</strong> append-only log of recent operations; indexed by <code>{doc_id, version}</code> for quick replay",
                        "<strong>Redis session cache:</strong> hot session state (active user list, last known version, in-flight ops)",
                        "<strong>S3 / Glacier archive:</strong> ops older than 30 days flushed for long-term retention",
                    ],
                },
                {"type": "h3", "text": "Background Services (Async)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Async Persistence:</strong> periodically save snapshots (every 100 ops or 30 seconds)",
                        "<strong>Spell Check Engine:</strong> real-time spell checking; flag errors without blocking edits",
                        "<strong>Notification Service (Kafka):</strong> broadcast doc changes, @mentions, permission updates",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Core Design Decisions: OT vs CRDT",
            "subtitle": "The defining trade-off for this system",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The choice between <strong>Operational Transform (OT)</strong> and "
                        "<strong>Conflict-free Replicated Data Types (CRDT)</strong> is the "
                        "single most consequential decision in this design. It cascades into "
                        "the data model, the offline story, the server topology, and how undo "
                        "behaves."
                    ),
                },
                {
                    "type": "table",
                    "headers": ["Aspect", "Operational Transform (OT)", "CRDT"],
                    "rows": [
                        ["Consistency", "Strong eventual consistency; requires central server",
                         "Weak eventual consistency; decentralized possible"],
                        ["Transformation", "Must compute transform(op_a, op_b); non-commutative",
                         "Ops commute; no transform needed"],
                        ["Offline support", "Harder; must detect &amp; resolve conflicts on reconnect",
                         "Natural; automatic merge via unique IDs"],
                        ["Complexity", "Complex xform logic; hard to implement correctly",
                         "Simpler to reason about; deterministic"],
                        ["Performance", "Fast for small N users; slower with many concurrent edits",
                         "Consistent performance; scales well"],
                        ["Undo/Redo", "Complex; must track op dependencies",
                         "Simpler; each op has unique ID"],
                        ["Production use", "Google Docs, Wave (centralized)",
                         "Figma, Apple Notes, Automerge, Yjs (local-first)"],
                    ],
                },
                {"type": "h3", "text": "Recommended Approach: Hybrid (Central OT)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Primary:</strong> central server-side OT engine for authoritative conflict resolution",
                        "<strong>Backup:</strong> client-side CRDT-like merge for offline sync and eventual consistency fallback",
                        "<strong>Rationale:</strong> OT + central server = predictable, testable, audit-friendly (Google Docs approach)",
                        "<strong>Scaling:</strong> shard by doc_id to keep OT engine simple per shard; docs don't move between servers",
                    ],
                },
                # ERRATUM 2: Reconciled design-decision callout. Verbatim from ERRATA.
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Design Decision",
                    "body": (
                        "We will use Operational Transform with a central OT engine and sticky "
                        "sessions per doc. All edits route to one server; that server transforms "
                        "ops and broadcasts results. This trades some scalability (can't "
                        "horizontally scale per doc) for simplicity and correctness. As a rough "
                        "estimate, with ~10MB of in-memory state per active doc (snapshot + "
                        "recent op buffer + presence) and ~100 ops/sec per doc to transform and "
                        "fan out to 50 peers, a 16-core / 64GB server can plausibly host on the "
                        "order of a few thousand concurrent docs before memory or fanout CPU "
                        "saturates; treat this as an envelope, not an SLA."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Data Models & Storage",
            "subtitle": "Documents, ops, and session state",
            "blocks": [
                {"type": "h3", "text": "Document Entity"},
                {
                    "type": "code",
                    "text": (
                        "message Document {\n"
                        "  string    doc_id        = 1; // unique ID (UUID)\n"
                        "  string    title         = 2;\n"
                        "  string    content       = 3; // current full text (UTF-8)\n"
                        "  int64     version       = 4; // Lamport version counter\n"
                        "  Timestamp created_at    = 5;\n"
                        "  Timestamp updated_at    = 6;\n"
                        "  string    owner_user_id = 7;\n"
                        "  repeated  Permission permissions = 8; // owner / editor / viewer\n"
                        "}"
                    ),
                },
                {
                    "type": "para",
                    "text": "Core document metadata stored in Postgres / Firestore / Bigtable.",
                },
                {"type": "h3", "text": "Operation Log Entry"},
                {
                    "type": "code",
                    "text": (
                        "message Operation {\n"
                        "  string    doc_id    = 1;\n"
                        "  int64     version   = 2; // monotonic version for this doc\n"
                        "  string    user_id   = 3;\n"
                        "  Timestamp timestamp = 4;\n"
                        "  string    type      = 5; // 'insert' | 'delete' | 'format'\n"
                        "  int32     position  = 6; // char position in document\n"
                        "  string    content   = 7; // inserted text (for insert)\n"
                        "  int32     length    = 8; // chars deleted (for delete)\n"
                        "  map<string,string> attrs = 9; // {bold, italic, ...}\n"
                        "}"
                    ),
                },
                {
                    "type": "para",
                    "text": "Immutable operation logged in append-only revision log.",
                },
                {"type": "h3", "text": "Session & Cursor State (Redis)"},
                {
                    "type": "code",
                    "text": (
                        "// Redis key: session:{doc_id}\n"
                        "{\n"
                        "  \"version\": 12500,                  // latest applied op version\n"
                        "  \"users\": {\n"
                        "    \"alice\": {user_id, cursor_pos, color, typing: true},\n"
                        "    \"bob\":   {user_id, cursor_pos, color, typing: false}\n"
                        "  },\n"
                        "  \"pending_ops\": [\n"
                        "    {version: 12501, op_obj},\n"
                        "    {version: 12502, op_obj}\n"
                        "  ]\n"
                        "}"
                    ),
                },
                {
                    "type": "para",
                    "text": "Volatile session state for active document editing.",
                },
                {"type": "h3", "text": "Snapshot Storage Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Periodic snapshots:</strong> every 100 operations or 30 seconds; store <code>{doc_id, snapshot_version, content, timestamp}</code>",
                        "<strong>Snapshot + log:</strong> on load, fetch latest snapshot, then replay ops from that version forward",
                        "<strong>Log cleanup:</strong> archive ops older than 30 days; keep only last 3 snapshots per doc to save space",
                        "<strong>Compression:</strong> store snapshots as gzipped JSON; 50KB avg → 5KB compressed",
                    ],
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Concurrent Edit Processing",
            "subtitle": "How OT actually transforms two edits",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The heart of the system: how concurrent edits from multiple users are "
                        "transformed and merged into a convergent state. The transform diagram "
                        "below shows the canonical case — two users insert at overlapping "
                        "positions; the server transforms one against the other so all clients "
                        "end at the same final string."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Figure 7.1: Two concurrent inserts at v=100 → server transforms B's position past A's insertion → both clients converge at v=102.",
                    "dot": r"""
digraph T {
    rankdir=TB;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_v0 {
        label="v=100 (shared base)"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Base [label="content =\n'previous text'", fillcolor="#dbe6fb"];
    }

    subgraph cluster_clients {
        label="Concurrent edits"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        A [label="User A\ninsert(pos=5, 'hello')", fillcolor="#fff2c9"];
        B [label="User B\ninsert(pos=10, 'world')", fillcolor="#fff2c9"];
    }

    subgraph cluster_server {
        label="OT Engine (authoritative)"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        ApplyA [label="apply A → v=101\nbroadcast to B", fillcolor="#cbeedf"];
        Xform  [label="transform B against A\npos: 10 → 10 + len('hello') = 15", fillcolor="#cbeedf"];
        ApplyB [label="apply B' → v=102\nbroadcast to A", fillcolor="#cbeedf"];
    }

    subgraph cluster_v2 {
        label="v=102 (convergent)"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        Final [label="all clients agree\non final string", fillcolor="#ead7fb"];
    }

    Base -> A;
    Base -> B;
    A -> ApplyA;
    B -> Xform;
    ApplyA -> Xform [label="A is now\npart of state"];
    Xform -> ApplyB;
    ApplyB -> Final;
}
""",
                },
                {"type": "h3", "text": "The OT Transformation Algorithm (Simplified)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Scenario:</strong> User A inserts 'hello' at position 5; User B inserts 'world' at position 10. Both arrive at server.",
                        "<strong>Server state before either op:</strong> <code>version=100, content='previous text'</code>",
                        "<strong>Op A arrives:</strong> <code>insert(pos=5, 'hello')</code>, applied → version=101, broadcast to B",
                        "<strong>Op B arrives:</strong> <code>insert(pos=10, 'world')</code>, but conflicts with A's position shift",
                        "<strong>Transform step:</strong> adjust B's position against A: <code>pos = 10 + len('hello') = 15</code> (because A's insertion shifts everything after)",
                        "<strong>Apply transformed B:</strong> <code>insert(pos=15, 'world')</code>, applied → version=102",
                        "<strong>Broadcast:</strong> both A and B receive transformed ops; convergence guaranteed",
                    ],
                },
                {"type": "h3", "text": "Why This Works (Convergence Proof Sketch)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Commutativity:</strong> if the transform function is commutative, final state is independent of op order",
                        "<strong>Idempotency:</strong> a client that sent op_i won't re-apply it when broadcast back (dedup by op_id)",
                        "<strong>Causality:</strong> each op includes a version number; ops must be applied in version order",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "OT Transformation Invariant",
                    "body": (
                        "The key invariant: <code>transform(op_a, op_b) ≡ transform(op_b, op_a)</code> "
                        "(up to reordering). This ensures all clients converge to the same final "
                        "state even if they apply ops in different orders. The server is "
                        "authoritative; it decides version order."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "OT/CRDT Deep Dive",
            "subtitle": "Why production OT is harder than it looks",
            "blocks": [
                {"type": "h3", "text": "Operational Transform (OT) Essentials"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Core idea:</strong> given two concurrent ops, compute a third op that applies both edits correctly",
                        "<strong>Transform function:</strong> <code>op' = T(op_a, op_b)</code> where op' is op_a adjusted for op_b's effects",
                        "<strong>For insert operations:</strong> if op_b inserts before op_a's position, shift op_a's position forward",
                        "<strong>For delete operations:</strong> delete positions shift based on prior insertions; overlapping deletes handled carefully",
                        "<strong>String vs tree:</strong> most collaborative editors use string (linear sequence); complex docs use tree (nodes, hierarchy)",
                    ],
                },
                # ERRATUM 3: TP1/TP2, intent preservation, why CRDTs won. Verbatim.
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Why This Is Hard in Practice",
                    "body": (
                        "Correct OT requires the transform function to satisfy <strong>TP1</strong> "
                        "(convergence for two concurrent ops) and <strong>TP2</strong> "
                        "(convergence for three or more concurrent ops applied in any order). "
                        "TP2 is famously difficult to satisfy — multiple published OT algorithms "
                        "were later shown to violate it under specific edit sequences. OT must "
                        "also preserve user <em>intent</em> (e.g., not splitting a word a user "
                        "just typed), which adds further case analysis. These pitfalls are why "
                        "most modern collaborative systems (<strong>Figma, Automerge, Yjs</strong>) "
                        "chose CRDTs instead, trading larger payloads for a merge function that "
                        "is correct by construction."
                    ),
                },
                {"type": "h3", "text": "CRDT (Conflict-free Replicated Data Type) Alternative"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Core idea:</strong> assign unique IDs to each character; no transform needed because order is via ID comparison",
                        "<strong>Example — Yjs CRDT:</strong> each char gets <code>{unique_client_id, sequence_num}</code>; merge sorts by ID",
                        "<strong>Advantage:</strong> works offline; automatic eventual consistency; simpler merge logic",
                        "<strong>Disadvantage:</strong> higher memory overhead (IDs per char); harder to implement undo/redo per-user",
                        "<strong>Best for:</strong> local-first apps (Figma, Apple Notes); eventual consistency acceptable",
                    ],
                },
                {"type": "h3", "text": "Practical Trade-Offs"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>OT:</strong> smaller payloads, faster (no metadata per char), audit-friendly (linear history); needs central server",
                        "<strong>CRDT:</strong> scales offline editing, supports true P2P, deterministic merge; larger payloads, complex internal data structures",
                        "<strong>Hybrid approach:</strong> use OT on the server for consistency; clients cache CRDT-style IDs for offline merge",
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Presence & Cursor Tracking",
            "subtitle": "Showing who's there and where",
            "blocks": [
                {"type": "h3", "text": "Real-Time Cursor Positions"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Update frequency:</strong> send cursor position every 100ms (or on significant movement) to avoid flooding",
                        "<strong>Payload:</strong> <code>{user_id, cursor_pos, selection_start, selection_end, color}</code> ~50 bytes",
                        "<strong>Broadcast:</strong> server multicasts to all other users in the session (fanout to N-1 clients)",
                        "<strong>Latency:</strong> target &lt;200ms for cursor visibility",
                    ],
                },
                {"type": "h3", "text": "Presence Heartbeat & Timeout"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Heartbeat:</strong> client sends keepalive every 30 seconds; includes user status (online, away, typing)",
                        "<strong>Server timeout:</strong> remove user from active list if no heartbeat for 2 minutes (network stale)",
                        "<strong>Graceful exit:</strong> user closes editor → send 'user left' event → remove from all clients' presence list",
                    ],
                },
                {"type": "h3", "text": "User Colors & Avatars"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Color assignment:</strong> on session join, server picks next color from palette (8–10 colors, rotate through users)",
                        "<strong>Avatar display:</strong> show user initials + color in sidebar and next to cursor",
                        "<strong>Consistency:</strong> same user always same color across all docs and sessions",
                    ],
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Document Load, Save & Offline Mode",
            "subtitle": "The read/persistence path and offline sync strategy",
            "blocks": [
                {"type": "h3", "text": "Loading a Document"},
                {
                    "type": "numbered",
                    "items": [
                        "User opens doc → fetch latest snapshot from Postgres/Firestore (indexed by doc_id)",
                        "Query revision log: get all ops since snapshot version",
                        "Replay ops on snapshot in version order → current document state",
                        "Initialize WebSocket session; subscribe to real-time ops for this doc",
                        "Render UI with full document + user list",
                    ],
                },
                {"type": "h3", "text": "Periodic Snapshot & Save"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Trigger:</strong> every 100 operations OR 30 seconds, whichever comes first",
                        "<strong>Process:</strong> server saves <code>{doc_id, snapshot_content, version, timestamp}</code> to Postgres",
                        "<strong>Log cleanup:</strong> ops older than snapshot version can be archived (keep 30 days for audit)",
                        "<strong>Latency:</strong> async; doesn't block real-time editing",
                    ],
                },
                {"type": "h3", "text": "Offline Mode & Reconnection"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>On disconnect:</strong> client detects WebSocket close; stop sending ops to server",
                        "<strong>Local buffering:</strong> cache all edits to IndexedDB (browser's local database)",
                        "<strong>Optimistic UI:</strong> continue showing edits in UI immediately (local only)",
                        "<strong>Reconnection detect:</strong> periodically try to reconnect (exponential backoff)",
                        "<strong>Sync on reconnect:</strong> send buffered ops to server; server transforms against concurrent edits during offline period",
                        "<strong>Conflict resolution:</strong> if conflict detected, show user merge UI or accept server version",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Offline Design",
                    "body": (
                        "Offline is supported via local IndexedDB cache + buffered ops. When "
                        "reconnecting, send buffered ops with version info. Server compares "
                        "against its state; if diverged, apply transformation or ask client to "
                        "resolve. For most use cases (single user editing offline), automatic "
                        "merge succeeds."
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Failure Modes & Recovery",
            "subtitle": "What can go wrong and how we recover",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure Mode", "Impact", "Recovery Strategy"],
                    "rows": [
                        ["WebSocket disconnect",
                         "Ops don't reach server; client unaware",
                         "Client detects close event; buffer ops; exponential backoff reconnect"],
                        ["Server crashes",
                         "All active sessions lost; pending ops may be lost",
                         "Failover to hot standby (Redis backup); clients reconnect; re-sync from snapshot + log"],
                        ["Op loss during persist",
                         "Ops applied to docs but not persisted",
                         "Periodic snapshots are synchronous/durable; ops logged to journal before ACK"],
                        ["Split-brain (network partition)",
                         "Clients diverge; can't reach server",
                         "Clients buffer ops locally; on reconnect, server version wins; client merges or discards local ops"],
                        ["Concurrent op collision",
                         "Same position edited by 2+ users simultaneously",
                         "OT transform resolves; server version order is authoritative"],
                        ["Slow client (lagging)",
                         "Client receives ops out of order or with gaps",
                         "Client queues ops by version; applies once version is contiguous"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful Degradation",
                    "body": (
                        "Prioritise the editing path: if presence, spell check, or notifications "
                        "fail, the document must still be editable. Always serve the latest "
                        "snapshot from cache; degrade real-time fanout before degrading the OT "
                        "engine itself."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Interview Playbook",
            "subtitle": "How to present this in 45 minutes",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Structure for a 45-minute interview on real-time collaborative editing. "
                        "Lead with the OT-vs-CRDT trade-off — that's the test of whether you "
                        "understand the problem."
                    ),
                },
                {
                    "type": "table",
                    "headers": ["Time", "Topic", "What to Cover", "Depth"],
                    "rows": [
                        ["0–5 min", "Problem statement",
                         "1B docs, 100M DAU, 50 users/doc, sub-second latency",
                         "Clarifying questions"],
                        ["5–10 min", "Requirements",
                         "Functional (edit, share, history) &amp; non-functional (99.9% availability, &lt;500ms op latency)",
                         "Trade-off discussion"],
                        ["10–15 min", "Capacity estimation",
                         "60M ops/sec envelope, 12 GB/sec inbound, 50PB snapshots, 2PB hot storage",
                         "Back-of-envelope math"],
                        ["15–25 min", "High-level architecture",
                         "WebSocket gateway, OT engine, doc store, Redis session cache",
                         "Draw both diagrams"],
                        ["25–30 min", "OT vs CRDT",
                         "Compare approaches; justify OT for this use case (central + sticky sessions); mention TP1/TP2",
                         "Design decision"],
                        ["30–35 min", "Deep dive: one topic",
                         "OT algorithm &amp; transform, or presence/cursors, or offline sync",
                         "Interviewer picks"],
                        ["35–40 min", "Failure scenarios",
                         "Handle WebSocket drops, server crashes, op loss, merge conflicts",
                         "Resilience discussion"],
                        ["40–45 min", "Wrap-up &amp; trade-offs",
                         "Scalability limits (per-doc shard), latency (network RTT), cost (storage)",
                         "Summary &amp; questions"],
                    ],
                },
                {"type": "h3", "text": "Key Points to Emphasize"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Scalability:</strong> shard by doc_id (sticky sessions); each shard handles a few thousand docs (envelope, not SLA)",
                        "<strong>Consistency:</strong> strong eventual consistency via OT; server authoritative",
                        "<strong>Latency:</strong> optimistic updates (0ms), server ack (&lt;100ms), broadcast (&lt;500ms)",
                        "<strong>Reliability:</strong> async persistence; hot failover; offline sync on reconnect",
                        "<strong>Trade-offs:</strong> OT is conceptually simpler than CRDT but production-correct OT is hard (TP2, intent preservation) — that's why Figma / Automerge / Yjs picked CRDTs",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Takeaways",
                    "body": (
                        "Real-time collaborative editing hinges on <strong>Operational Transform</strong> "
                        "for conflict resolution and <strong>central server authority</strong> for "
                        "consistency. Use sticky sessions per doc to avoid distributed consensus. "
                        "Store snapshots + op logs for durability and recovery. Support offline "
                        "editing via local cache and merge on reconnect. Design for 50 concurrent "
                        "users per doc with sub-500ms op propagation latency — and remember that "
                        "modern systems (Figma, Automerge, Yjs) chose CRDTs precisely because "
                        "production-grade OT is hard to get right."
                    ),
                },
                {"type": "h3", "text": "Further Reading & References"},
                {
                    "type": "bullets",
                    "items": [
                        "Google Wave / Docs architecture: USENIX OSDI '10 — Real-Time Collaborative Editing",
                        "Operational Transform (Ellis &amp; Gibbs, 1989): foundational OT paper",
                        "Yjs library: <code>github.com/yjs/yjs</code> — production CRDT for collaborative editing",
                        "Automerge: <code>automerge.org</code> — JSON-like CRDT with rich text support",
                        "Figma multiplayer tech: <code>figma.com/blog/how-figmas-multiplayer-technology-works/</code>",
                    ],
                },
            ],
        },
    ],
}
