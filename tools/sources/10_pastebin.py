"""Source for `10 - Pastebin.pdf` — anonymous text/code paste service."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Pastebin",
    "subtitle": "anonymous text and code paste service with expiry, syntax highlighting, and abuse controls",
    "read_time": "~ 45 minute read",
    "short_title": "Design Pastebin",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Statement",
            "subtitle": "Requirements and scope",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Design a paste service like <strong>Pastebin</strong>, "
                        "<strong>GitHub Gist</strong>, or <strong>hastebin</strong>. "
                        "Users submit a blob of text or source code and receive a short "
                        "shareable URL. The service must store the body, render it (often "
                        "with syntax highlighting), serve it on demand, expire old pastes, "
                        "and resist abuse."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Pastes/day?", "1 million creates; 10:1 read:write → 10 million reads"],
                        ["Paste size?", "Avg ~10 KB; cap at 10 MB; reject larger"],
                        ["Anonymous?", "Yes; optional account for management"],
                        ["Expiry?", "10 min / 1 h / 1 d / 1 mo / never (default 1 mo)"],
                        ["Privacy modes?", "Public, unlisted (URL only), password-protected"],
                        ["Syntax highlighting?", "Yes; ~50 languages, auto-detect on submit"],
                        ["Edits?", "No; pastes are immutable. New paste = new URL"],
                        ["Abuse controls?", "Safe Browsing scan, DMCA flow, rate limit"],
                    ],
                },
            ],
        },
        # ---- 02 ------------------------------------------------------
        {
            "num": "02",
            "title": "Requirements",
            "subtitle": "Functional and non-functional",
            "blocks": [
                {"type": "h3", "text": "Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Details"],
                    "rows": [
                        ["Create", "POST /pastes { body, language?, expiry?, privacy?, password? } → short URL"],
                        ["Read", "GET /:key → render paste with syntax highlighting"],
                        ["Raw", "GET /:key/raw → plain text body (for curl/wget)"],
                        ["Expiry", "Configurable TTL; lazy delete on read after expiry"],
                        ["Privacy", "Public (listed), unlisted (URL-only), password-protected"],
                        ["Highlighting", "Server-side render at write time; cache HTML"],
                        ["Abuse report", "POST /report → flag for moderator review"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Availability", "99.9% reads; 99.5% writes"],
                        ["Latency", "&lt;200 ms read p99 (cached); &lt;500 ms write p99"],
                        ["Consistency", "Read-your-writes for the creator; eventual for others"],
                        ["Storage", "~10 GB/day raw; ~3.6 TB/yr hot tier"],
                        ["Throughput", "~12 writes/sec; ~120 reads/sec average; 10× peak"],
                        ["Durability", "11 nines (S3-class) for paste bodies"],
                        ["Key space", "Base62 8-char → 62^8 ≈ 218 trillion keys"],
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
                {"type": "h3", "text": "Traffic"},
                {
                    "type": "bullets",
                    "items": [
                        "Pastes created/day: <strong>1 million</strong>",
                        "Read:write ratio: <strong>10:1</strong> (most pastes read a handful of times)",
                        "Reads/day: 1M × 10 = <strong>10 million</strong>",
                        "Write QPS avg: 1,000,000 / 86,400 ≈ <strong>~12 writes/sec</strong>",
                        "Read QPS avg: 10,000,000 / 86,400 ≈ <strong>~116 reads/sec ≈ 120/sec</strong>",
                        "Peak factor ~10× → <strong>120 writes/sec, 1,200 reads/sec</strong> at peak",
                    ],
                },
                {"type": "h3", "text": "Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "Average paste size: <strong>~10 KB</strong> (10,000 bytes) of body text",
                        "Daily body volume: 1M × 10 KB = <strong>10 GB/day</strong>",
                        "Metadata: ~500 B/row × 1M = <strong>~500 MB/day</strong> in Postgres",
                        "Highlighted HTML cache: ~3× source ≈ 30 KB ⇒ <strong>~30 GB/day</strong> if everything cached",
                        "Annual hot tier (1-year retention of warm pastes): <strong>~3.6 TB/yr</strong>",
                        "After 5 years with cold tiering to Glacier: ~18 TB total, &lt;4 TB hot",
                    ],
                },
                {"type": "h3", "text": "Bandwidth"},
                {
                    "type": "bullets",
                    "items": [
                        "Ingress: 12 writes/sec × 10 KB ≈ <strong>120 KB/sec</strong> (negligible)",
                        "Egress: 120 reads/sec × 10 KB ≈ <strong>1.2 MB/sec</strong> avg; ~12 MB/sec at peak",
                        "CDN absorbs the long-tail re-reads of the same paste; egress at origin ~30%",
                    ],
                },
                {"type": "h3", "text": "Cache"},
                {
                    "type": "bullets",
                    "items": [
                        "Hot working set: pastes accessed in the last 24 h ≈ ~2–3 M unique keys",
                        "At ~10 KB each: <strong>~25 GB Redis</strong> (rendered HTML kept on CDN, body kept in S3)",
                        "Inline-in-DB shortcut: pastes &lt;4 KB live in Postgres → no S3 round-trip",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "Writes: <strong>~12/sec avg, ~120/sec peak</strong> &nbsp;·&nbsp; "
                        "Reads: <strong>~120/sec avg, ~1.2K/sec peak</strong> &nbsp;·&nbsp; "
                        "Body storage: <strong>10 GB/day, ~3.6 TB/yr</strong> hot &nbsp;·&nbsp; "
                        "Cache: <strong>~25 GB</strong> Redis &nbsp;·&nbsp; "
                        "Key space: <strong>62^8 ≈ 218T</strong>"
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level Architecture",
            "subtitle": "System overview",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The system splits into <strong>Edge</strong> (CDN + API Gateway), "
                        "<strong>Service Layer</strong> (Write Service, Read Service, Highlight worker), "
                        "and <strong>Data Tier</strong> (KGS, Postgres metadata, S3 paste bodies, Redis "
                        "rendered-HTML cache, Kafka analytics, Safe Browsing). The <em>body</em> of a "
                        "paste is large and immutable, so it lives in object storage; the <em>metadata</em> "
                        "is small and queryable, so it lives in a relational store."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Top-level data flow: clients hit the CDN; misses go through the API gateway to Write/Read services; bodies sit in S3 with a Redis cache in front; analytics and abuse scanning are async.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Client"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Client [label="Browser / curl / IDE", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        CDN [label="CDN\n(rendered HTML +\nraw bodies)", fillcolor="#cbeedf"];
        GW  [label="API Gateway\n(rate limit, auth)", fillcolor="#cbeedf"];
    }
    subgraph cluster_svc {
        label="Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        WS [label="Write Service\n(create paste)", fillcolor="#fff2c9"];
        RS [label="Read Service\n(serve paste)",  fillcolor="#fff2c9"];
        HL [label="Highlight Worker\n(Pygments)",  fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        KGS [label="KGS\n(Base62 keys)", fillcolor="#ead7fb"];
        PG  [label="Postgres\n(metadata + tiny bodies)", fillcolor="#ead7fb"];
        S3  [label="S3\n(paste bodies)", fillcolor="#ead7fb"];
        R   [label="Redis\n(rendered HTML)", fillcolor="#ead7fb"];
        KQ  [label="Kafka\n(views, abuse)", fillcolor="#fbd7c5"];
        SB  [label="Safe Browsing\n+ AV scan", fillcolor="#fbd7c5"];
    }

    Client -> CDN  [label="GET /:key", color="#1f8359"];
    Client -> GW   [label="POST /pastes\nGET miss"];
    GW -> WS;
    GW -> RS;
    WS -> KGS [label="reserve key"];
    WS -> PG  [label="INSERT metadata"];
    WS -> S3  [label="PUT body (≥4 KB)"];
    WS -> SB  [label="async scan"];
    WS -> HL  [label="enqueue render"];
    HL -> R   [label="cache HTML"];
    RS -> R   [label="HIT", style=dashed];
    RS -> PG  [label="metadata", style=dashed];
    RS -> S3  [label="MISS body", style=dashed];
    RS -> KQ  [label="view event", style=dashed];
}
""",
                },
                {"type": "h3", "text": "Architecture Highlights"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>CDN:</strong> caches both rendered HTML and raw bodies; absorbs viral pastes",
                        "<strong>API Gateway:</strong> auth, rate limiting (10/hr/IP for anonymous), routing",
                        "<strong>Write Service:</strong> validates, reserves a key from KGS, persists metadata + body, enqueues highlight + safety scan",
                        "<strong>Read Service:</strong> serves rendered HTML from cache; falls back to S3 + on-the-fly render",
                        "<strong>Highlight Worker:</strong> pulls from queue, runs Pygments, writes HTML to Redis + CDN origin",
                        "<strong>KGS:</strong> pre-generated Base62 8-char keys, atomic reservation",
                        "<strong>Postgres:</strong> metadata + tiny pastes inline (&lt;4 KB) to skip S3 round-trips",
                        "<strong>S3:</strong> immutable paste bodies; 11 nines durability; lifecycle to Glacier",
                        "<strong>Redis:</strong> rendered HTML for hot pastes; TTL 24 h",
                        "<strong>Kafka:</strong> view events, abuse signals, analytics",
                        "<strong>Safe Browsing / AV:</strong> async scan; takedown if flagged",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Key Generation",
            "subtitle": "Short, unique paste IDs",
            "blocks": [
                {"type": "h3", "text": "Goal"},
                {
                    "type": "para",
                    "text": (
                        "Each paste gets a short, opaque, URL-safe key. Unlike a URL shortener, "
                        "we are <em>not</em> hashing user input — the input is a blob of text. The "
                        "key is purely an identifier. We mint it before we touch S3 so we can use "
                        "it as the S3 object key and the Postgres primary key."
                    ),
                },
                {"type": "h3", "text": "Comparison"},
                {
                    "type": "table",
                    "headers": ["Approach", "Pros", "Cons"],
                    "rows": [
                        ["UUIDv4", "No coordination; trivial", "26 chars in Base32; ugly URLs"],
                        ["MD5(body)", "Dedup identical pastes for free", "Long; must truncate; collision risk; leaks identical content across users"],
                        ["Sequential ID + Base62", "Compact; ordered; small", "Predictable; enumerable; needs distributed counter"],
                        ["KGS (pre-generated Base62)", "Atomic; non-enumerable; small", "Requires a service; pool refill logic"],
                    ],
                },
                {"type": "h3", "text": "Choice: Base62 8-char from a KGS Pool"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Alphabet:</strong> 0–9, a–z, A–Z = 62 characters",
                        "<strong>Length:</strong> 8 chars (vs URL shortener's 7) → <strong>62^8 ≈ 218 trillion</strong> keys",
                        "<strong>Why 8 not 7?</strong> Pastes are content not redirects; longer key reduces enumeration risk for unlisted pastes",
                        "<strong>KGS:</strong> generates random keys, deduplicates against a Bloom filter, and hands out batches of 1,000 to each Write Service instance",
                        "<strong>Years to exhaust:</strong> 218T / (1M/day × 365) ≈ <strong>~600 million years</strong>",
                    ],
                },
                {"type": "h3", "text": "Base62 Reference"},
                {
                    "type": "code",
                    "text": (
                        "import secrets, string\n\n"
                        "ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase\n"
                        "KEY_LEN = 8\n\n"
                        "def random_key():\n"
                        "    # 8 chars × 6 bits ≈ 48 bits of entropy\n"
                        "    return ''.join(secrets.choice(ALPHABET) for _ in range(KEY_LEN))\n\n"
                        "# 62^8 = 218,340,105,584,896 ≈ 2.18 × 10^14 unique keys\n"
                        "TOTAL = 62 ** KEY_LEN"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Why not hash the body?",
                    "body": (
                        "Hashing the paste content would let us deduplicate identical pastes — useful "
                        "for storage, but bad for privacy. Two users posting the same secret would "
                        "land on the same URL. Use random KGS keys; deduplicate at the storage layer "
                        "via a separate content hash if needed (S3 server-side dedup or a body_sha256 "
                        "column)."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Storage Architecture",
            "subtitle": "Metadata vs body split",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Pastes have two kinds of state: small structured <strong>metadata</strong> "
                        "(creator, expiry, language, privacy mode) and large unstructured "
                        "<strong>body</strong> (the actual text). Putting both in Postgres works "
                        "for tiny pastes but bloats the row store; putting both in S3 makes "
                        "metadata queries impossibly slow. The standard answer is to split."
                    ),
                },
                {"type": "h3", "text": "Split-Store Comparison"},
                {
                    "type": "table",
                    "headers": ["Strategy", "Read latency", "Storage cost", "When"],
                    "rows": [
                        ["All in Postgres", "Fastest (1 hop)", "Expensive at TB scale; row size hurts vacuum", "Tiny site, bodies &lt; 1 KB"],
                        ["All in S3", "Slow (2 hops + JSON parse)", "Cheap (~$0.023/GB-mo)", "Pure archive, no queries"],
                        ["Postgres + S3 split", "1 hop for hot, 2 for cold", "Cheap bodies, fast metadata", "<strong>Default for Pastebin</strong>"],
                        ["Postgres inline (&lt;4 KB) + S3 (≥4 KB)", "1 hop for &gt;50% of pastes", "Optimal", "<strong>Production sweet-spot</strong>"],
                    ],
                },
                {"type": "h3", "text": "Schema (Postgres)"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE pastes (\n"
                        "  paste_key      CHAR(8)      PRIMARY KEY,         -- Base62 KGS key\n"
                        "  user_id        BIGINT       NULL,                -- NULL for anonymous\n"
                        "  language       VARCHAR(32)  NULL,                -- 'python', 'json', ...\n"
                        "  privacy        SMALLINT     NOT NULL,            -- 0 public 1 unlisted 2 password\n"
                        "  password_hash  TEXT         NULL,                -- bcrypt; NULL unless privacy=2\n"
                        "  body_inline    TEXT         NULL,                -- inline if size_bytes < 4096\n"
                        "  body_s3_key    TEXT         NULL,                -- S3 object key otherwise\n"
                        "  size_bytes     INT          NOT NULL,\n"
                        "  body_sha256    CHAR(64)     NOT NULL,            -- for dedup / integrity\n"
                        "  created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),\n"
                        "  expires_at     TIMESTAMPTZ  NULL,                -- NULL = never\n"
                        "  retention      SMALLINT     NOT NULL,            -- enum 10m/1h/1d/1mo/never\n"
                        "  view_count     BIGINT       NOT NULL DEFAULT 0,\n"
                        "  abuse_status   SMALLINT     NOT NULL DEFAULT 0,  -- 0 ok 1 pending 2 blocked\n"
                        "  CHECK ((body_inline IS NULL) <> (body_s3_key IS NULL))\n"
                        ");\n\n"
                        "CREATE INDEX idx_pastes_expires_at ON pastes (expires_at)\n"
                        "  WHERE expires_at IS NOT NULL;\n"
                        "CREATE INDEX idx_pastes_user_created ON pastes (user_id, created_at DESC)\n"
                        "  WHERE user_id IS NOT NULL;\n"
                        "CREATE INDEX idx_pastes_abuse ON pastes (abuse_status) WHERE abuse_status > 0;"
                    ),
                },
                {"type": "h3", "text": "S3 Layout"},
                {
                    "type": "bullets",
                    "items": [
                        "Bucket: <code>pastebin-bodies-{region}</code>; one object per paste",
                        "Key format: <code>{shard}/{paste_key}</code> where <code>shard = paste_key[:2]</code> — spreads partitions across S3 prefixes",
                        "Server-side encryption (SSE-KMS); integrity checked via stored body_sha256",
                        "Lifecycle: hot → S3 Standard for 30 days; → S3 IA for 11 months; → Glacier afterward",
                        "Versioning: off (pastes are immutable; new content = new key)",
                    ],
                },
                {"type": "h3", "text": "Why Inline Small Pastes"},
                {
                    "type": "bullets",
                    "items": [
                        "Distribution of paste sizes is heavily skewed — ~60% are &lt; 4 KB (snippets, error logs, configs)",
                        "Inline avoids: extra network hop, S3 GET cost (~$0.0004/1k requests), and S3 latency tail (~30–80 ms p99)",
                        "4 KB threshold matches Postgres' default TOAST boundary — rows stay in the heap, no out-of-line storage",
                        "Above 4 KB, body lives in S3 and Postgres holds only the S3 key (cheap, predictable rows)",
                    ],
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Write Path Deep Dive",
            "subtitle": "Creating a paste",
            "blocks": [
                {"type": "h3", "text": "Step-by-Step"},
                {
                    "type": "numbered",
                    "items": [
                        "Client submits: <code>POST /pastes { body, language?, retention, privacy, password? }</code>",
                        "API Gateway: rate limit (10/hr/IP for anonymous, 100/hr authed); reject if over",
                        "Validate: size ≤ 10 MB; language in allow-list; retention ∈ {10m, 1h, 1d, 1mo, never}",
                        "Reserve key: pop one from local KGS batch (refill from KGS service when &lt; 100 left)",
                        "Persist body: if size &lt; 4 KB inline in <code>body_inline</code>; else <code>PUT s3://.../shard/key</code>",
                        "Persist metadata: <code>INSERT INTO pastes ...</code> with computed <code>expires_at</code>",
                        "Enqueue side-effects: highlight render to Kafka <code>render_jobs</code>; Safe Browsing scan to <code>abuse_jobs</code>",
                        "Return: <code>201 { url, raw_url, expires_at }</code> — total p99 ≤ 500 ms",
                    ],
                },
                {"type": "h3", "text": "KGS Batch Reservation"},
                {
                    "type": "code",
                    "text": (
                        "# Pseudocode: write service holds a local key buffer\n"
                        "BATCH_SIZE = 1000\n"
                        "REFILL_AT  = 100\n"
                        "local_keys = collections.deque()\n\n"
                        "def get_key():\n"
                        "    if len(local_keys) <= REFILL_AT:\n"
                        "        threading.Thread(target=refill, daemon=True).start()\n"
                        "    if not local_keys:                  # cold start fallback\n"
                        "        local_keys.extend(kgs.reserve(BATCH_SIZE))\n"
                        "    return local_keys.popleft()\n\n"
                        "def refill():\n"
                        "    new = kgs.reserve(BATCH_SIZE)        # atomic on KGS side\n"
                        "    local_keys.extend(new)\n\n"
                        "# KGS guarantees: each key handed out exactly once across all instances.\n"
                        "# UNIQUE constraint on pastes.paste_key is the safety net."
                    ),
                },
                {"type": "h3", "text": "Highlight on Write vs on Read"},
                {
                    "type": "table",
                    "headers": ["Strategy", "Pros", "Cons"],
                    "rows": [
                        ["Highlight on write (server-side)", "Read path is O(memcpy); CDN can cache HTML; consistent rendering", "Wastes work for never-read pastes; render time adds to write latency unless async"],
                        ["Highlight on read (server-side, cached)", "Don't pay for never-read pastes", "First reader is slow; thundering herd on viral pastes"],
                        ["Highlight on read (client-side, e.g. highlight.js)", "Server stays trivial", "JS bundle ~100 KB; doesn't help raw / curl / no-JS clients; CPU on client"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Decision: server-side highlight, async at write",
                    "body": (
                        "Render with <strong>Pygments</strong> (or shiki for JS) inside the highlight worker, "
                        "triggered by the Kafka render_jobs topic. The Read Service first checks Redis for "
                        "rendered HTML; on miss it falls back to rendering inline (and warms the cache) so "
                        "the first reader of a brand-new paste never waits for the worker. We pay render "
                        "cost once per paste, the result is cacheable on the CDN, and curl/IDE clients "
                        "still get plain text via <code>/raw</code>."
                    ),
                },
                {"type": "h3", "text": "Error Handling"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>S3 PUT fails:</strong> retry with exponential backoff; if persistent, return 503; metadata row is never inserted (S3 first, DB second)",
                        "<strong>Postgres insert fails after S3 PUT:</strong> orphaned object; nightly reaper deletes S3 objects whose key has no matching row",
                        "<strong>KGS unavailable:</strong> fall back to local random + UNIQUE constraint retry (max 3 retries before 503)",
                        "<strong>Body too large:</strong> 413 Payload Too Large; suggest user split or use a different service",
                        "<strong>Safe Browsing async fails:</strong> paste created but flagged <code>abuse_status=1 pending</code>; reviewed within 1 h",
                    ],
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Read Path & Cache Hierarchy",
            "subtitle": "Serving a paste fast",
            "blocks": [
                {"type": "h3", "text": "Cache Hierarchy"},
                {
                    "type": "para",
                    "text": (
                        "Reads traverse a four-level hierarchy. Each level gets faster but smaller. "
                        "The expected hit-rate distribution for a viral paste roughly looks like: "
                        "CDN ~70%, Redis ~20%, Postgres metadata + S3 body ~10%."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Read path: each level falls through to the next. CDN serves rendered HTML directly; Redis serves rendered HTML to origin; Postgres provides metadata + (sometimes) inline body; S3 holds the rest.",
                    "dot": r"""
digraph R {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Cli  [label="Client", fillcolor="#dbe6fb"];
    CDN  [label="CDN edge\n~70% HIT", fillcolor="#cbeedf"];
    RS   [label="Read Service", fillcolor="#fff2c9"];
    Red  [label="Redis\n(rendered HTML)\n~20% of misses", fillcolor="#ead7fb"];
    PG   [label="Postgres\n(metadata + inline body)", fillcolor="#ead7fb"];
    S3   [label="S3\n(body for ≥4 KB)", fillcolor="#ead7fb"];
    HL   [label="Pygments render\n(inline, warms cache)", fillcolor="#fff2c9"];

    Cli -> CDN [label="GET /:key"];
    CDN -> RS  [label="MISS", style=dashed];
    RS  -> Red [label="GET html:key"];
    Red -> RS  [label="MISS", style=dashed];
    RS  -> PG  [label="SELECT *"];
    PG  -> RS  [label="inline body?"];
    RS  -> S3  [label="if ≥4 KB", style=dashed];
    RS  -> HL  [label="render"];
    HL  -> Red [label="SET html:key TTL=24h"];
    RS  -> Cli [label="200 OK"];
    Red -> Cli [label="200 OK (via RS)"];
    CDN -> Cli [label="200 OK"];
}
""",
                },
                {"type": "h3", "text": "Step-by-Step"},
                {
                    "type": "numbered",
                    "items": [
                        "Client requests <code>GET /abc12345</code>",
                        "CDN edge: serves cached HTML if present (TTL 1 h, longer for popular)",
                        "Miss CDN → Read Service",
                        "Redis lookup: <code>GET html:abc12345</code> — if hit, return immediately and let CDN cache",
                        "Miss Redis: <code>SELECT * FROM pastes WHERE paste_key = 'abc12345'</code>",
                        "Check expiry: if <code>expires_at &lt; now()</code> → 404 + lazy delete",
                        "Check privacy: if password-protected, demand auth (401) or session token check",
                        "Body fetch: use <code>body_inline</code> if present; else <code>GET s3://.../shard/key</code>",
                        "Render: Pygments by language; produce HTML; <code>SET html:key</code> with TTL = 24 h",
                        "Async: publish <code>view_event</code> to Kafka; increment view_count via async aggregator",
                        "Return 200 with HTML; CDN caches for 1 h based on Cache-Control headers",
                    ],
                },
                {"type": "h3", "text": "Cache TTLs"},
                {
                    "type": "table",
                    "headers": ["Layer", "TTL", "Reason"],
                    "rows": [
                        ["CDN edge", "1 h (10 min for unlisted)", "Pastes are immutable but expiry is dynamic; short TTL bounds staleness"],
                        ["Redis HTML", "24 h", "Re-render on miss is cheap; longer wastes memory on cold pastes"],
                        ["Postgres row cache (PG buffers)", "managed by PG", "Hot rows naturally pinned in shared_buffers"],
                        ["S3 body", "n/a (immutable)", "Object never changes; only deleted on expiry"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Cache Bypass for Password-Protected Pastes",
                    "body": (
                        "Never let a CDN cache the rendered HTML of a password-protected paste — a "
                        "second visitor would see the body without the password. Mark such responses "
                        "<code>Cache-Control: private, no-store</code>. The auth handshake happens at "
                        "the Read Service; CDN caches only the auth-prompt page."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Syntax Highlighting",
            "subtitle": "Pygments at write, cached forever",
            "blocks": [
                {"type": "h3", "text": "Pipeline"},
                {
                    "type": "numbered",
                    "items": [
                        "Write Service publishes <code>render_jobs { paste_key, language }</code> to Kafka",
                        "Highlight Worker consumes the topic; pulls body (inline or S3); runs Pygments",
                        "Output is HTML with inline span classes (e.g. <code>&lt;span class=\"k\"&gt;def&lt;/span&gt;</code>)",
                        "Worker writes to Redis: <code>SET html:&lt;key&gt; &lt;html&gt; EX 86400</code>",
                        "First reader either gets cached HTML (Redis) or triggers an inline render fallback (and warms the cache)",
                    ],
                },
                {"type": "h3", "text": "Highlight + Cache-fill (Read Service Fallback)"},
                {
                    "type": "code",
                    "text": (
                        "from pygments import highlight\n"
                        "from pygments.lexers import get_lexer_by_name, guess_lexer\n"
                        "from pygments.formatters import HtmlFormatter\n\n"
                        "FORMATTER = HtmlFormatter(cssclass='paste', linenos='inline', wrapcode=True)\n\n"
                        "def render_and_cache(paste_key, body, language):\n"
                        "    try:\n"
                        "        lexer = get_lexer_by_name(language) if language else guess_lexer(body)\n"
                        "    except Exception:\n"
                        "        lexer = get_lexer_by_name('text')   # fallback: no highlighting\n"
                        "    html_out = highlight(body, lexer, FORMATTER)\n\n"
                        "    # SETNX so we don't clobber a worker that won the race\n"
                        "    pipe = redis.pipeline()\n"
                        "    pipe.set(f'html:{paste_key}', html_out, ex=86400, nx=True)\n"
                        "    pipe.execute()\n"
                        "    return html_out"
                    ),
                },
                {"type": "h3", "text": "Language Auto-Detect"},
                {
                    "type": "bullets",
                    "items": [
                        "Client may submit <code>language</code>; if not, server runs <code>guess_lexer(body)</code>",
                        "Pygments guesses by token frequency / regex hints; ~80% accurate on samples &gt; 200 chars",
                        "On low-confidence guesses, fall back to <code>text</code> lexer (no highlighting; still escaped)",
                        "Persist the chosen language in Postgres so re-renders are deterministic",
                    ],
                },
                {"type": "h3", "text": "Why Server-Side"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>curl/wget/IDE clients</strong> get plain text via <code>/raw</code>; no JS execution",
                        "<strong>CDN-cacheable</strong>: rendered HTML is a static blob, sized in tens of KB",
                        "<strong>Consistent</strong>: every viewer sees the same colorization, regardless of browser",
                        "<strong>SEO/preview</strong>: link unfurlers (Slack, Twitter) get fully rendered code in the OG image preview",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "The Cost of a Render",
                    "body": (
                        "Pygments highlights ~10 MB/sec/core for typical source. A 10 KB paste takes "
                        "~1 ms of CPU. At 12 writes/sec we use &lt; 2% of a single core for rendering. "
                        "The bottleneck is not CPU — it is the Redis write and HTML-versus-source size "
                        "ratio (HTML is ~2–4× the source). Budget cache size accordingly."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Expiry & Lifecycle",
            "subtitle": "TTL, lazy delete, cold tiering",
            "blocks": [
                {"type": "h3", "text": "Retention Options"},
                {
                    "type": "table",
                    "headers": ["Option", "expires_at", "Use Case"],
                    "rows": [
                        ["10 minutes", "now() + 10 min", "One-time secrets, paste-and-forget"],
                        ["1 hour",     "now() + 1 h",   "Quick code review snippet"],
                        ["1 day",      "now() + 24 h",  "Default for ephemeral chats"],
                        ["1 month",    "now() + 30 d",  "Default for casual sharing"],
                        ["Never",      "NULL",          "Public archive, blog post"],
                    ],
                },
                {"type": "h3", "text": "Lazy Delete on Read"},
                {
                    "type": "numbered",
                    "items": [
                        "On every read, check <code>expires_at &lt; now()</code>",
                        "If expired: return 410 Gone; mark row for cleanup; delete cached HTML from Redis",
                        "Don't synchronously delete the S3 object — that costs a round-trip on the read path",
                        "A nightly reaper job picks up rows flagged for cleanup and deletes their S3 objects in batch",
                    ],
                },
                {"type": "h3", "text": "Background Reaper"},
                {
                    "type": "code",
                    "text": (
                        "-- Pages expired pastes in chunks; runs every 30 min off-peak\n"
                        "WITH expired AS (\n"
                        "  SELECT paste_key, body_s3_key\n"
                        "  FROM pastes\n"
                        "  WHERE expires_at IS NOT NULL\n"
                        "    AND expires_at < NOW() - INTERVAL '5 minutes'\n"
                        "  ORDER BY expires_at\n"
                        "  LIMIT 10000\n"
                        "  FOR UPDATE SKIP LOCKED\n"
                        ")\n"
                        "DELETE FROM pastes\n"
                        "USING expired\n"
                        "WHERE pastes.paste_key = expired.paste_key\n"
                        "RETURNING pastes.paste_key, pastes.body_s3_key;\n"
                        "-- caller batches RETURNING into S3 DeleteObjects (1000 keys per call)"
                    ),
                },
                {"type": "h3", "text": "S3 Lifecycle Policy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>0–30 days:</strong> S3 Standard — frequent reads expected",
                        "<strong>30–365 days:</strong> S3 Standard-IA (~50% cheaper, retrieval fee)",
                        "<strong>365+ days:</strong> S3 Glacier Instant Retrieval (~$0.004/GB-mo)",
                        "Lifecycle moves are free if &gt; 128 KB and ≥ 30 days; we batch-tag at write time",
                        "Pastes with expiry ≤ 30 d never tier — they die in Standard before policy fires",
                    ],
                },
                {"type": "h3", "text": "Why Lazy + Reaper, not Cron-only"},
                {
                    "type": "bullets",
                    "items": [
                        "Lazy on read: zero work for pastes that nobody re-reads after expiry",
                        "Reaper: catches the long tail (pastes that expired and were never re-read) — frees S3 storage",
                        "Combined approach amortizes deletion cost; no thundering-herd at midnight",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Privacy Modes",
            "subtitle": "Public, unlisted, password-protected",
            "blocks": [
                {"type": "h3", "text": "Three Modes"},
                {
                    "type": "table",
                    "headers": ["Mode", "Discoverability", "Auth", "Indexed?"],
                    "rows": [
                        ["Public",            "Listed in /trending and search", "None", "Yes"],
                        ["Unlisted",          "Only via direct URL",            "None", "No (robots noindex)"],
                        ["Password-protected", "Only via direct URL",            "Password challenge",  "No"],
                    ],
                },
                {"type": "h3", "text": "Implementation"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Public:</strong> <code>privacy=0</code>; surfaced in trending feed; Cache-Control public",
                        "<strong>Unlisted:</strong> <code>privacy=1</code>; not in trending; <code>X-Robots-Tag: noindex, nofollow</code>; key length (8 chars) makes brute-force enumeration impractical (62^8 ≈ 218T)",
                        "<strong>Password:</strong> <code>privacy=2</code>; bcrypt-hashed password in <code>password_hash</code>; client supplies password → server verifies → issues short-lived JWT cookie scoped to that paste_key",
                        "<strong>Cache rule:</strong> <code>Cache-Control: private, no-store</code> for password mode; CDN must not cache decoded HTML",
                    ],
                },
                {"type": "h3", "text": "Password Verification Flow"},
                {
                    "type": "numbered",
                    "items": [
                        "Client GETs <code>/abc12345</code>",
                        "Read Service sees <code>privacy=2</code>; renders password prompt page (cacheable, no body)",
                        "Client POSTs <code>/abc12345/unlock { password }</code>",
                        "Server bcrypt-verifies; if OK, issues HttpOnly JWT cookie <code>paste_token=...</code> scoped to paste_key, TTL 1 h",
                        "Subsequent GETs include the cookie; Read Service verifies signature and serves the paste",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Unlisted is not private",
                    "body": (
                        "Unlisted means \"not advertised\" — the URL is still secret-by-obscurity. Anyone "
                        "the link is shared with can re-share it. Tell users this explicitly. For real "
                        "secrecy, recommend password mode or end-to-end client-side encryption (the "
                        "PrivateBin model: encrypt body in browser, key lives in URL fragment, server "
                        "stores only ciphertext)."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Abuse Prevention",
            "subtitle": "Malware, phishing, copyright, rate limits",
            "blocks": [
                {"type": "h3", "text": "Threat Model"},
                {
                    "type": "table",
                    "headers": ["Threat", "How", "Mitigation"],
                    "rows": [
                        ["Malware/phishing payload", "Paste contains exploit kit, credentials harvest, etc.",
                         "Async Safe Browsing scan; flag → block"],
                        ["DMCA / copyright violation", "Pirated source code, leaked book chapter",
                         "Takedown form; manual review; legal hold"],
                        ["Spam flood", "Bot creates thousands of SEO-bait pastes",
                         "Rate limit 10/hr/IP anonymous, 100/hr authed; CAPTCHA on suspicious patterns"],
                        ["Doxxing / PII leak", "Personal info, credit cards in paste body",
                         "Regex pre-scan (PAN, SSN); user-report flow; right-to-delete"],
                        ["Resource exhaustion", "Single client uploads many 10 MB pastes",
                         "Per-IP daily byte cap (e.g. 100 MB/day anon); 413 above 10 MB single-paste"],
                        ["Enumeration", "Attacker scans short keys to find unlisted pastes",
                         "8-char keys (62^8 ≈ 218T); CDN/WAF burst limit; honeypot keys"],
                    ],
                },
                {"type": "h3", "text": "Safe Browsing Pipeline"},
                {
                    "type": "numbered",
                    "items": [
                        "Write Service publishes <code>abuse_jobs { paste_key }</code> to Kafka",
                        "Abuse Worker fetches body; extracts URLs (regex); calls Google Safe Browsing API in batches of 500",
                        "If any URL is UNSAFE: <code>UPDATE pastes SET abuse_status = 2 WHERE paste_key = ?</code>; evict cache; return 451 on read",
                        "Otherwise: <code>UPDATE pastes SET abuse_status = 0</code> (cleared)",
                        "Pending state during scan: paste is viewable but tagged \"under review\" in metadata response",
                    ],
                },
                {"type": "h3", "text": "DMCA Takedown Flow"},
                {
                    "type": "numbered",
                    "items": [
                        "Rights-holder submits <code>POST /report</code> with paste URL, evidence, sworn statement",
                        "Trust & Safety queue: SLA 24 h for review",
                        "Reviewer marks paste <code>abuse_status = 2</code>; original body archived under legal hold (90 d)",
                        "Counter-notice flow: original poster (if authed) can dispute; auto-restore after 14 d if no court order",
                        "Public transparency report: monthly aggregate counts (no paste content)",
                    ],
                },
                {"type": "h3", "text": "Rate Limiting"},
                {
                    "type": "code",
                    "text": (
                        "# Sliding-window rate limit at API gateway (Redis)\n"
                        "ANON_LIMIT  = 10   # writes per hour per IP\n"
                        "AUTH_LIMIT  = 100\n"
                        "WINDOW_SEC  = 3600\n\n"
                        "def allow_write(ip, user_id):\n"
                        "    key = f'wl:{user_id or ip}'\n"
                        "    limit = AUTH_LIMIT if user_id else ANON_LIMIT\n"
                        "    now = int(time.time())\n"
                        "    pipe = redis.pipeline()\n"
                        "    pipe.zremrangebyscore(key, 0, now - WINDOW_SEC)  # drop old\n"
                        "    pipe.zcard(key)                                  # count in window\n"
                        "    pipe.zadd(key, {f'{now}-{uuid()}': now})         # add this hit\n"
                        "    pipe.expire(key, WINDOW_SEC)\n"
                        "    _, count, _, _ = pipe.execute()\n"
                        "    return count < limit"
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Scalability & Distribution",
            "subtitle": "Growing past the prototype",
            "blocks": [
                {"type": "h3", "text": "Horizontal Scaling"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Write Service:</strong> stateless behind ALB; scale on CPU + queue depth",
                        "<strong>Read Service:</strong> stateless; scale independently on QPS",
                        "<strong>Highlight Worker:</strong> Kafka consumer group; partition by paste_key for ordering; scale on lag",
                        "<strong>KGS:</strong> 2–3 instances; each reserves a non-overlapping numeric range from the master pool",
                    ],
                },
                {"type": "h3", "text": "Postgres Sharding"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Shard key:</strong> <code>hash(paste_key) % N</code>; start N=16, scale to 64+",
                        "<strong>Per-shard:</strong> primary + 2 replicas; read replicas absorb spikes",
                        "<strong>Tooling:</strong> Citus, Vitess, or Postgres logical replication; failover via Patroni",
                        "<strong>Why shard early:</strong> retention=never pastes accumulate forever; metadata grows unbounded",
                    ],
                },
                {"type": "h3", "text": "Redis Cluster"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Topology:</strong> 6 nodes (3 primary, 3 replica); ~25 GB working set",
                        "<strong>Sharding:</strong> hash slot of paste_key; consistent hashing handles node moves",
                        "<strong>Eviction:</strong> <code>allkeys-lru</code> — rendered HTML is regenerable",
                        "<strong>Persistence:</strong> RDB snapshots only; no AOF (cache, not source of truth)",
                    ],
                },
                {"type": "h3", "text": "Global Distribution"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Primary region:</strong> writes pin to one region (e.g. us-east-1) for strong consistency",
                        "<strong>Read replicas:</strong> Postgres async replicas in eu-west-1, ap-southeast-1 (~1–2 s lag)",
                        "<strong>S3:</strong> Cross-Region Replication for paste bodies; reads served from nearest region",
                        "<strong>CDN:</strong> ~200 PoPs globally; absorbs &gt; 70% of read traffic",
                        "<strong>Acceptable lag:</strong> a fresh paste may not be readable in eu-west-1 for ~2 s — fine for the use case",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Read replica vs CDN",
                    "body": (
                        "For a paste service, the CDN is the dominant scale lever — most reads hit the "
                        "same 0.1% of pastes (the viral ones). Read replicas help with the long tail "
                        "of <em>different</em> pastes being read once each. Spend cache budget on the "
                        "CDN first; replicas second."
                    ),
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Failure Modes & Recovery",
            "subtitle": "What can go wrong",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["Redis down", "Every read renders inline; ~5× CPU on Read Service",
                         "Redis health check; latency spike", "Failover to replica; degrade to on-the-fly render only"],
                        ["S3 region outage", "Reads of ≥4 KB pastes fail in that region",
                         "PUT/GET 5xx", "Serve from replicated bucket in secondary region; new writes still work via inline if &lt; 4 KB"],
                        ["Postgres primary down", "All writes fail; reads on that shard fail",
                         "Connection timeout", "Patroni promotes replica (~30 s); writes buffer on client and retry"],
                        ["KGS exhausted/down", "Cannot create new pastes",
                         "KGS error metric", "Standby instance; fall back to local random + UNIQUE retry"],
                        ["CDN edge down", "Slow reads from that region",
                         "Provider alert; latency", "Reroute to nearest edge; origin can absorb 100% briefly"],
                        ["Highlight worker lag", "New pastes show plain (escaped) text for ~minutes",
                         "Kafka consumer lag metric", "Inline render fallback in Read Service papers over the lag"],
                        ["Safe Browsing API down", "New pastes stay in pending review",
                         "HTTP error rate", "Allow viewing with banner; re-scan when API recovers"],
                        ["Spam flood / DDoS", "Write QPS spikes; Postgres connections exhausted",
                         "Anomaly detector", "WAF rules; raise CAPTCHA threshold; throttle anonymous to 1/hr"],
                    ],
                },
                {"type": "h3", "text": "Disaster Recovery Targets"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>RTO:</strong> &lt; 15 min for read service; &lt; 60 min for write service",
                        "<strong>RPO:</strong> &lt; 5 min for paste bodies (S3 CRR); &lt; 1 min for metadata (synchronous WAL replication)",
                        "<strong>Backups:</strong> Postgres base backup nightly + WAL archive; S3 versioning for accidental delete (30-day window)",
                        "<strong>DR drill:</strong> quarterly region failover; chaos test on Redis loss",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful Degradation",
                    "body": (
                        "Reads are the core use case — protect them. If Redis is down, render inline. "
                        "If highlighting fails, serve plain text. If S3 is slow, serve <code>/raw</code> "
                        "from cache and hide the rendered view. Writes can fail loudly with 503; readers "
                        "must always see <em>something</em> for a known paste."
                    ),
                },
            ],
        },
        # ---- 15 ------------------------------------------------------
        {
            "num": "15",
            "title": "Design Trade-offs",
            "subtitle": "Decisions and rationale",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Decision", "Choice", "Trade-off"],
                    "rows": [
                        ["Body storage", "Postgres inline if &lt;4 KB else S3",
                         "1 hop for ~60% of pastes; 2 hops + S3 cost for the rest. Simpler designs (all-S3 or all-PG) hurt either tail latency or storage cost."],
                        ["Key generation", "KGS pre-generated Base62 8-char",
                         "Extra service vs near-zero collisions and non-enumerable keys. Random + retry is simpler but flaky under contention."],
                        ["Highlight timing", "Server-side, async at write",
                         "Render once, cache forever; first read may inline-render. Client-side (highlight.js) is simpler but breaks curl and adds 100 KB JS."],
                        ["Highlighter", "Pygments",
                         "Mature, ~500 lexers, ~10 MB/sec/core. Tree-sitter is faster and more accurate but harder to deploy in Python services."],
                        ["Privacy default", "Unlisted (not public)",
                         "Friendlier default for users sharing logs/configs. Public-by-default would feed a trending feed but invite accidental leaks."],
                        ["Expiry default", "1 month",
                         "Most pastes are ephemeral; \"never\" is opt-in. Saves storage. Loses the archive use case unless user explicitly chooses never."],
                        ["Edits", "Immutable; new paste = new URL",
                         "Caching becomes trivial; CDN can cache forever. Users who want edits use a Gist instead."],
                        ["Database", "Postgres sharded",
                         "Strong consistency, real schema, JSONB for flexibility. NoSQL would scale further but lose the abuse-status query patterns."],
                        ["Anonymous default", "Anonymous OK; auth for management",
                         "Lowers friction (the use case). Costs us abuse vectors; rate limits and Safe Browsing reclaim them."],
                        ["Cache layer", "CDN + Redis (rendered HTML)",
                         "Two layers feel redundant but solve different problems: CDN handles geo + viral; Redis handles cold-but-not-frozen."],
                    ],
                },
            ],
        },
        # ---- 16 ------------------------------------------------------
        {
            "num": "16",
            "title": "Interview Playbook",
            "subtitle": "How to present this in 45 minutes",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Pastebin is the canonical \"URL shortener for content\" interview question. "
                        "The trap is treating it as a URL shortener clone — you need to address "
                        "<em>body storage</em>, <em>rendering</em>, <em>privacy</em>, and "
                        "<em>abuse</em> in ways the shortener doesn't."
                    ),
                },
                {"type": "h3", "text": "45-Minute Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (3 min):</strong> clarify scope — anonymous OK, immutable, ~1M pastes/day, 10:1 read:write, 10 KB avg, expiry options, syntax highlighting needed",
                        "<strong>Capacity (5 min):</strong> 12 writes/sec avg, 120 reads/sec avg, 10× peak, 10 GB/day body, 3.6 TB/yr hot, ~25 GB Redis cache",
                        "<strong>Architecture (5 min):</strong> CDN, API gateway, Write/Read services, KGS, Postgres metadata, S3 body, Redis HTML cache, Kafka, Safe Browsing — draw the diagram",
                        "<strong>Storage split (8 min):</strong> why metadata in Postgres, body in S3, &lt;4 KB inline; show the schema; explain TOAST boundary",
                        "<strong>Write path (5 min):</strong> KGS reservation; S3 PUT before Postgres INSERT to avoid orphaned rows; async render + scan",
                        "<strong>Read path (6 min):</strong> CDN → Redis → Postgres → S3 fallthrough; render inline if cache miss; show the diagram",
                        "<strong>Highlighting (3 min):</strong> server-side Pygments, async, cached HTML; defend over client-side",
                        "<strong>Privacy + abuse (5 min):</strong> public/unlisted/password modes; rate limits; Safe Browsing; DMCA flow",
                        "<strong>Expiry (2 min):</strong> lazy on read + nightly reaper; S3 lifecycle to Glacier",
                        "<strong>Failures (3 min):</strong> top 3 — Redis loss, S3 region outage, KGS exhausted",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why split body and metadata?</strong> A: Bodies are 10 KB on average and unstructured; rows in Postgres get fat. S3 is purpose-built for blobs at $0.023/GB-mo, vs Postgres' ~$0.10+/GB-mo with operational overhead. Metadata stays in Postgres because we need to query expiry, privacy, and abuse_status.",
                        "<strong>Q: Why server-side highlighting?</strong> A: <code>/raw</code> users (curl, IDEs) get plain text; HTML users get a CDN-cacheable rendered blob. Client-side breaks no-JS clients and bloats the page by ~100 KB.",
                        "<strong>Q: How do you prevent unlisted pastes from being scraped?</strong> A: 8-char Base62 → 218T keyspace; 1M valid pastes means 1 in 218 million guesses hits. Combined with WAF burst limits and honeypot keys, enumeration is impractical.",
                        "<strong>Q: What if a paste body never makes it to S3 but the row was inserted?</strong> A: We PUT to S3 first, then INSERT into Postgres. If S3 fails, no row exists. If Postgres fails after S3 succeeds, we have an orphan S3 object — cleaned up nightly by a reaper that diffs S3 keys against Postgres rows.",
                        "<strong>Q: Password-protected paste — how do you stop the CDN from caching it?</strong> A: <code>Cache-Control: private, no-store</code> on the rendered response. The CDN caches only the password prompt page (which has no body).",
                        "<strong>Q: How do you handle a viral paste — say a leaked source code that gets 1M views in an hour?</strong> A: CDN absorbs nearly all of it (it's an immutable rendered HTML page). Origin sees only the cache-fill miss in each PoP — at most a few hundred origin hits regardless of view count.",
                        "<strong>Q: Why immutable?</strong> A: Caching becomes trivial — CDN and Redis can cache effectively forever (until expiry). Editable pastes need versioning, cache invalidation, and a different UX. If you want edits, you want Gist, not Pastebin.",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "“1 M pastes/day, 10:1 read:write, 10 KB avg → 10 GB/day, 3.6 TB/year hot” — capacity in one breath",
                        "“Postgres for metadata, S3 for body, inline if &lt; 4 KB” — the storage split is the headline answer",
                        "“KGS Base62 8-char, 62^8 ≈ 218T keys” — answers both uniqueness and enumeration concerns",
                        "“Server-side Pygments, async on write, cached HTML” — explains why curl and the CDN both work",
                        "“Lazy expiry on read + nightly reaper” — covers correctness and cost",
                        "“Public, unlisted, password — three modes, three Cache-Control policies”",
                        "“Safe Browsing async + DMCA queue” — abuse story without slowing the write path",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "1M pastes/day · 10:1 read:write · ~10 KB avg paste &nbsp;·&nbsp; "
                        "12 writes/sec avg, 120 reads/sec avg (10× peak) &nbsp;·&nbsp; "
                        "10 GB/day body, 3.6 TB/yr hot &nbsp;·&nbsp; "
                        "62^8 ≈ 218 trillion keys &nbsp;·&nbsp; "
                        "&lt;4 KB inline in Postgres else S3 &nbsp;·&nbsp; "
                        "Redis ~25 GB rendered HTML cache &nbsp;·&nbsp; "
                        "Anon rate limit 10/hr/IP."
                    ),
                },
            ],
        },
    ],
}
