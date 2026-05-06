"""Source for `02 - URL Shortener.pdf` (regenerated with errata applied)."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design a URL Shortener",
    "subtitle": "bit.ly-style distributed service for shortening and redirecting URLs",
    "read_time": "~ 40 minute read",
    "short_title": "Design a URL Shortener",
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
                        "Design a URL shortening service like <strong>bit.ly</strong> or "
                        "<strong>TinyURL</strong>. The service must convert long URLs into short, "
                        "memorable links; handle user redirects efficiently; track analytics; and "
                        "scale to billions of URLs."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["URLs/day?", "100 million read-heavy (100:1 read:write ratio)"],
                        ["Expiry?", "5 years; lazy expiry on read"],
                        ["Custom aliases?", "Yes, optional per-user feature"],
                        ["Scale?", "Global; handle single region first"],
                        ["Private URLs?", "Yes, with auth + access control"],
                        ["Vanity URLs?", "Yes, if available and reserved by user"],
                        ["Analytics required?", "Yes: click counts, geographic, referrer"],
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
                        ["Shorten", "Accept long URL → return short URL (POST /shorten)"],
                        ["Redirect", "GET /:key → 301 redirect to original URL"],
                        ["Analytics", "Track clicks, referrer, geo, user agent per URL"],
                        ["Expiry", "URLs expire after configurable TTL (default 5 years)"],
                        ["Custom Key", "Users can specify custom alias if available"],
                        ["Private URLs", "Owner-only access with auth token"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Availability", "99.9% uptime; graceful degradation"],
                        ["Latency", "&lt;100ms for redirect; &lt;200ms for shorten"],
                        ["Consistency", "Eventual consistency acceptable; dedup via keys"],
                        ["Storage", "~91 TB over 5 years"],
                        ["Throughput", "1.2K writes/sec; 115K reads/sec"],
                        ["Scalability", "Geo-distributed; 62^7 ≈ 3.5 trillion keys"],
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
                {"type": "h3", "text": "Traffic Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        "URLs created/day: <strong>100 million</strong>",
                        "Read:Write ratio: <strong>100:1</strong> (typical for shorteners)",
                        "Write throughput: 100M / 86,400 sec = <strong>1,157 writes/sec ≈ 1.2K/sec</strong>",
                        "Read throughput: 1.2K × 100 = <strong>115,700 reads/sec ≈ 120K/sec</strong>",
                    ],
                },
                {"type": "h3", "text": "Storage Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        "Per URL record: short_key (7B) + original_url (avg 100B) + metadata (100B) ≈ 500 bytes",
                        "Daily storage: 100M × 500B = <strong>50 GB/day</strong>",
                        "Retention: 5 years = 1,825 days",
                        "Total: 50 GB × 1,825 = <strong>91.25 TB</strong>",
                    ],
                },
                {"type": "h3", "text": "Cache Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        # ERRATUM 1: Pareto stated correctly.
                        "Hot URLs: <strong>80% of reads hit ~20% of URLs</strong> (Pareto principle)",
                        # ERRATUM 2: Reconciled cache derivation.
                        "Hot working set is the recently-active URLs over a 24h window — not the 5-year corpus",
                        "24h reads ≈ 115K/sec × 86,400 ≈ <strong>9.9B requests</strong>; 80% (~7.9B) target ~20% of recently-active URLs",
                        "Cardinality of that hot set: ~20–30M unique keys",
                        "Cache size needed: ~25M URLs × 500B ≈ <strong>12 GB Redis</strong> (round to ~11.5 GB cluster, TTL = 24h)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "Write throughput: <strong>1.2K/sec</strong> &nbsp;·&nbsp; "
                        "Read throughput: <strong>120K/sec</strong> &nbsp;·&nbsp; "
                        "Total storage: <strong>91 TB</strong> &nbsp;·&nbsp; "
                        "Hot cache: <strong>~12 GB</strong> Redis cluster"
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
                        "The system is divided into <strong>Edge</strong> (CDN + Load Balancer), "
                        "<strong>Service Layer</strong> (Write, Read, Analytics), and "
                        "<strong>Data Tier</strong> (KGS, MySQL, Redis, Kafka). Reads are cached "
                        "and served from CDN for popular URLs; writes reserve keys from a "
                        "pre-generated pool."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Request flow: reads served from CDN/Redis where possible; writes reserve a key from KGS, persist to MySQL, and warm the cache.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Client"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Client [label="Browser / App", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        CDN [label="CDN\n(popular URLs)", fillcolor="#cbeedf"];
        LB  [label="Load Balancer", fillcolor="#cbeedf"];
    }
    subgraph cluster_svc {
        label="Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        WS [label="Write Service\n(shorten)", fillcolor="#fff2c9"];
        RS [label="Read Service\n(redirect)",  fillcolor="#fff2c9"];
        AS [label="Analytics\nService",       fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        KGS  [label="KGS\n(Key Gen Service)", fillcolor="#ead7fb"];
        DB   [label="MySQL\n(url_mappings)",  fillcolor="#ead7fb"];
        Cache[label="Redis Cache\n(hot URLs)", fillcolor="#ead7fb"];
        KQ   [label="Kafka\n(click events)",  fillcolor="#fbd7c5"];
    }

    Client -> CDN  [label="GET /:key (60%)", color="#1f8359"];
    Client -> LB   [label="POST /shorten\nGET /:key (40%)"];
    LB -> WS;
    LB -> RS;
    WS -> KGS [label="reserve key"];
    WS -> DB  [label="INSERT"];
    RS -> Cache [label="HIT (80%)", style=dashed];
    RS -> DB    [label="MISS (20%)", style=dashed];
    RS -> KQ    [label="click event", style=dashed];
    AS -> KQ    [style=dashed];
}
""",
                },
                {"type": "h3", "text": "Architecture Highlights"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>CDN Edge:</strong> caches ~60% of requests (popular URLs); serves 301 redirects",
                        "<strong>Load Balancer:</strong> routes write requests to Write Service, reads to Read Service",
                        "<strong>Write Service:</strong> validates input, reserves short key from KGS, persists to MySQL, warms cache",
                        "<strong>Read Service:</strong> checks Redis (~80% hit rate), falls back to MySQL, logs analytics to Kafka",
                        "<strong>KGS:</strong> maintains pre-generated key pool; assigns keys atomically to avoid collisions",
                        "<strong>MySQL:</strong> persistent storage; sharded by short_key hash for scalability",
                        "<strong>Redis:</strong> in-memory cache for hot URLs; replicated cluster for HA",
                        "<strong>Kafka:</strong> event stream for click logging; async ingestion to Analytics",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Key Generation Strategy",
            "subtitle": "MD5 vs Base62 vs KGS",
            "blocks": [
                {"type": "h3", "text": "Overview"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Goal:</strong> convert long URL → short, unique, memorable string",
                        "<strong>Candidates:</strong> MD5 hash, Base62 encoding, Pre-generated Key Service (KGS)",
                    ],
                },
                {"type": "h3", "text": "Comparison"},
                {
                    "type": "table",
                    "headers": ["Approach", "Pros", "Cons"],
                    "rows": [
                        ["MD5 hash", "Deterministic; no DB lookup", "Not memorable; collision possible"],
                        ["Base62 from counter", "Compact; sequential", "Predictable; needs distributed counter"],
                        ["KGS (pre-generated)", "Atomic; no collisions; load-balanced", "Requires separate service; pre-warming"],
                    ],
                },
                {"type": "h3", "text": "Why KGS Wins"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Atomicity:</strong> keys reserved from a pre-generated pool, no race conditions",
                        "<strong>No collisions:</strong> each key issued exactly once; dedup via DB unique constraint",
                        "<strong>Load balancing:</strong> standby KGS instances for HA; keys pre-loaded on startup",
                        "<strong>Predictability:</strong> latency unaffected by hash computation or counter coordination",
                    ],
                },
                {"type": "h3", "text": "Base62 Encoding (Fallback)"},
                {
                    "type": "code",
                    "text": (
                        "import string\n\n"
                        "charset = string.digits + string.ascii_lowercase + string.ascii_uppercase\n\n"
                        "def to_base62(num):\n"
                        "    if num == 0: return charset[0]\n"
                        "    s = []\n"
                        "    while num > 0:\n"
                        "        s.append(charset[num % 62])\n"
                        "        num //= 62\n"
                        "    return ''.join(reversed(s))\n\n"
                        "# 62^7 = 3,521,614,606,208 unique keys\n"
                        "keys = 62 ** 7"
                    ),
                },
                {"type": "h3", "text": "Key Pool Size Math"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Alphabet:</strong> 0–9, a–z, A–Z = 62 characters",
                        "<strong>Key length:</strong> 7 characters (bit.ly standard)",
                        "<strong>Total keys:</strong> 62^7 = 3,521,614,606,208 (3.5 trillion)",
                        "<strong>Years to exhaust:</strong> 3.5T / (100M/day × 365) ≈ 95,910 years",
                    ],
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Database Design & Schema",
            "subtitle": "SQL schema and indexing",
            "blocks": [
                {"type": "h3", "text": "Primary Table: url_mappings"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE url_mappings (\n"
                        "  short_key      VARCHAR(7) PRIMARY KEY,\n"
                        "  original_url   TEXT NOT NULL,\n"
                        "  user_id        BIGINT,\n"
                        "  created_at     TIMESTAMP DEFAULT NOW(),\n"
                        "  expires_at     TIMESTAMP,\n"
                        "  is_custom      BOOLEAN DEFAULT FALSE,\n"
                        "  click_count    INT DEFAULT 0,\n"
                        "  last_accessed  TIMESTAMP,\n"
                        "  UNIQUE KEY uk_user_custom (user_id, short_key) WHERE is_custom,\n"
                        "  INDEX idx_user_id    (user_id),\n"
                        "  INDEX idx_expires_at (expires_at)\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "Indexing Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>PRIMARY KEY (short_key):</strong> fast lookup on redirect; sharded",
                        "<strong>INDEX (user_id):</strong> for user's URL list queries",
                        "<strong>INDEX (expires_at):</strong> for background cleanup job",
                        "<strong>UNIQUE (user_id, is_custom):</strong> prevent duplicate custom URLs per user",
                    ],
                },
                {"type": "h3", "text": "Sharding Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Shard key:</strong> hash(short_key) % num_shards (e.g., 256 shards)",
                        "<strong>Reasoning:</strong> distributes writes evenly; enables parallel reads",
                        "<strong>Resharding:</strong> consistent hashing or shard migration tool (Vitess)",
                        "<strong>Shard count:</strong> start with 256; scale to 1024+ as needed",
                    ],
                },
                {"type": "h3", "text": "SQL vs NoSQL Decision"},
                {
                    "type": "table",
                    "headers": ["Aspect", "SQL (MySQL)", "NoSQL (DynamoDB / Cassandra)"],
                    "rows": [
                        ["Schema", "Fixed; good for structured data", "Flexible; harder to query"],
                        ["Transactions", "Full ACID support", "Limited (eventual consistency)"],
                        ["Joins", "Yes; useful for analytics", "No; denormalize instead"],
                        ["Scalability", "Sharding required; complex", "Built-in replication; easier"],
                        ["Cost", "Cheaper at scale; self-managed", "Expensive at high write throughput"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Recommendation",
                    "body": (
                        "Use MySQL with sharding: structured data, strong consistency needed, "
                        "and analytics queries are useful. Shard by short_key hash to distribute "
                        "load evenly."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Write Path Deep Dive",
            "subtitle": "Shortening a URL",
            "blocks": [
                {"type": "h3", "text": "Step-by-Step"},
                {
                    "type": "numbered",
                    "items": [
                        "Client submits: <code>POST /shorten { url, alias?, ttl? }</code>",
                        "Validate: URL format, length, Safe Browsing check",
                        "Custom alias? If provided, check uniqueness in MySQL; reject if taken",
                        "Reserve key: if no custom alias, request one from KGS (atomic)",
                        "Persist: <code>INSERT INTO url_mappings ...</code>",
                        "Warm cache: SET Redis key with TTL (24 hours for hot URLs)",
                        "Async event: publish to Kafka for the analytics pipeline",
                        "Return: <code>201 { short_url, created_at, expires_at }</code>",
                    ],
                },
                {"type": "h3", "text": "Optimizations"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Batch KGS requests:</strong> reserve 100 keys per Write Service instance startup",
                        "<strong>Local cache:</strong> in-memory queue of reserved keys; refill when depleted",
                        "<strong>Async persistence:</strong> write to MySQL; log to Kafka in parallel",
                        "<strong>Dedup check:</strong> UNIQUE constraint backs up application-level checks",
                    ],
                },
                {"type": "h3", "text": "Error Handling"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>KGS exhausted:</strong> scale KGS horizontally; widen key length to 8 chars (62^8 ≈ 218T)",
                        "<strong>MySQL down:</strong> return 503; client retries with backoff",
                        "<strong>Duplicate key:</strong> rare (~1 in 3.5T); KGS prevents it; UNIQUE constraint catches",
                        "<strong>Malicious URL:</strong> Safe Browsing returns UNSAFE → reject with 400",
                    ],
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Read Path & Redirect",
            "subtitle": "Fast redirects",
            "blocks": [
                {"type": "h3", "text": "Step-by-Step"},
                {
                    "type": "numbered",
                    "items": [
                        "Browser requests: <code>GET /abc123</code>",
                        "CDN cache? If HIT (~60% popular URLs), serve 301 directly from edge",
                        "Miss CDN: route to Read Service",
                        "Redis lookup: GET abc123 → ~80% hit rate (hot URLs)",
                        "Cache miss: query MySQL shard for original_url",
                        "Warm cache: SET Redis with TTL = 24 hours",
                        "Return: <code>301 Moved Permanently → original_url</code>",
                        "Async log: publish click event to Kafka (referrer, geo, user agent)",
                    ],
                },
                {"type": "h3", "text": "301 vs 302 Redirect"},
                {
                    "type": "table",
                    "headers": ["Type", "Use Case", "Pros", "Cons"],
                    "rows": [
                        ["301", "Permanent move", "Browsers cache; reduces load",
                         "Cannot retarget; SEO transfers link equity"],
                        ["302", "Temporary move", "Can retarget any time",
                         "No client cache; every hit goes to origin"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Recommendation",
                    "body": (
                        "Use 301 for bit.ly. Permanent redirects reduce server load by leveraging "
                        "browser cache. SEO benefit is secondary to performance at this scale."
                    ),
                },
                {"type": "h3", "text": "CDN Caching Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Cache key:</strong> <code>GET /:short_key</code> → origin (Read Service)",
                        "<strong>TTL:</strong> 1 hour default; 24 hours for viral URLs",
                        "<strong>Invalidation:</strong> on custom URL update or expiry; manual purge if needed",
                        "<strong>Geographic:</strong> replicate across regions (US, EU, APAC)",
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Analytics Pipeline",
            "subtitle": "Click tracking and insights",
            "blocks": [
                {"type": "h3", "text": "Architecture"},
                {
                    "type": "bullets",
                    "items": [
                        "Click events logged asynchronously by Read Service to Kafka",
                        "Kafka topic: <code>url_clicks</code> (partition by short_key for ordering)",
                        "Stream processor: Apache Flink or Kafka Streams",
                        "Aggregations: count, geo, referrer, user agent; time windows (1min / 1h / 1d)",
                        "Storage: Cassandra (time-series) for analytics; Redis for dashboard hot reads",
                    ],
                },
                {"type": "h3", "text": "Event Schema"},
                {
                    "type": "code",
                    "text": (
                        "{\n"
                        "  \"short_key\":  \"abc123\",\n"
                        "  \"user_id\":    12345,\n"
                        "  \"timestamp\":  \"2026-03-18T10:30:45Z\",\n"
                        "  \"ip_address\": \"203.0.113.42\",\n"
                        "  \"country\":    \"US\",\n"
                        "  \"referrer\":   \"twitter.com\",\n"
                        "  \"user_agent\": \"Mozilla/5.0 ...\",\n"
                        "  \"click_id\":   \"<uuid>\"\n"
                        "}"
                    ),
                },
                {"type": "h3", "text": "Metrics"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Total clicks:</strong> sum by short_key over time window",
                        "<strong>Unique visitors:</strong> HyperLogLog for approx distinct count",
                        "<strong>Geographic heatmap:</strong> clicks by country; top 10 regions",
                        "<strong>Referrer breakdown:</strong> top referrers by click count",
                        "<strong>Trending:</strong> clicks in last 1 hour; identify viral URLs",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "HyperLogLog",
                    "body": (
                        "For unique-visitor counts use HyperLogLog (a probabilistic data structure). "
                        "Uses ~1.5 KB per key, handles billions of unique values with ~2% error. "
                        "Trade accuracy for memory efficiency."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "URL Expiry & Cleanup",
            "subtitle": "Managing data retention",
            "blocks": [
                {"type": "h3", "text": "Expiry Mechanism"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Default TTL:</strong> 5 years from creation",
                        "<strong>Lazy expiry:</strong> on read, check expires_at; if expired, return 404",
                        "<strong>No explicit delete:</strong> reduces write load; cleanup runs async",
                        "<strong>Custom TTL:</strong> users can specify shorter expiry (e.g., 7 days)",
                    ],
                },
                {"type": "h3", "text": "Background Cleanup Job"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Frequency:</strong> daily at 2 AM UTC (off-peak)",
                        "<strong>Cursor pagination:</strong> scan shards incrementally to prevent long locks",
                        "<strong>Delete:</strong> <code>DELETE FROM url_mappings WHERE short_key IN (...)</code>",
                        "<strong>Evict cache:</strong> DEL from Redis for deleted keys",
                        "<strong>Log:</strong> track deleted keys for analytics retention",
                    ],
                },
                {
                    "type": "code",
                    "text": (
                        "-- Background cleanup (runs daily, off-peak)\n"
                        "SELECT short_key, original_url FROM url_mappings\n"
                        "WHERE expires_at < NOW()\n"
                        "LIMIT 100000\n"
                        "FOR UPDATE SKIP LOCKED;\n\n"
                        "-- Cursor-based pagination per shard\n"
                        "SELECT short_key FROM url_mappings\n"
                        "WHERE shard_id = ? AND short_key > ?\n"
                        "ORDER BY short_key LIMIT 10000;"
                    ),
                },
                {"type": "h3", "text": "Cold Archive"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Retention:</strong> deleted URLs in S3 Glacier for 7 years",
                        "<strong>Cost:</strong> ~$0.004/GB-mo Glacier vs ~$0.023/GB-mo S3 Standard vs ~$0.10+/GB-mo MySQL",
                        "<strong>Query:</strong> archive by month; allow user export for compliance",
                    ],
                },
                {"type": "h3", "text": "Compliance"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>GDPR right-to-delete:</strong> anonymise user_id, retain short_key for reference",
                        "<strong>Audit log:</strong> log all deletions (short_key, user_id, deleted_at, reason)",
                        "<strong>Retention:</strong> keep audit logs for 2 years minimum",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Security & Abuse Prevention",
            "subtitle": "Protecting the system",
            "blocks": [
                {"type": "h3", "text": "Malicious URL Detection"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Google Safe Browsing API:</strong> phishing, malware, unwanted software",
                        "<strong>Call on shorten:</strong> synchronously block unsafe URLs",
                        "<strong>Fallback:</strong> log to Kafka for manual review if API unavailable",
                        "<strong>Rate limit:</strong> 5 req/sec per IP for Safe Browsing calls",
                    ],
                },
                {"type": "h3", "text": "Rate Limiting"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Per-user:</strong> token bucket; 1,000 shortened URLs/day per user",
                        "<strong>Per-IP:</strong> 100 req/min for anonymous users",
                        "<strong>Implementation:</strong> Redis INCR + EXPIRE; check on every request",
                        "<strong>Tiers:</strong> premium 10K/day, enterprise custom limits",
                    ],
                },
                {
                    "type": "code",
                    "text": (
                        "# Token bucket (Redis)\n"
                        "key = f'rate_limit:{user_id}'\n"
                        "current = redis.get(key) or 0\n"
                        "if current >= limit:\n"
                        "    return 429  # Too Many Requests\n"
                        "redis.incr(key)\n"
                        "redis.expire(key, 86400)  # 1 day"
                    ),
                },
                {"type": "h3", "text": "Private URLs & Access Control"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Private flag:</strong> boolean column in url_mappings",
                        "<strong>Access check:</strong> on read, if private, verify auth token matches owner",
                        "<strong>Shared access:</strong> access_control table (url_id, user_id, expires_at)",
                        "<strong>Token:</strong> JWT with user_id, url_id, expiry; signed",
                    ],
                },
                {"type": "h3", "text": "DDoS & SQL-Injection Protection"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>CDN DDoS:</strong> Cloudflare or AWS Shield; absorbs volumetric attacks",
                        "<strong>App-layer:</strong> rate limit per IP; detect patterns (same short_key)",
                        "<strong>Auto-scale:</strong> Read Service scales on QPS (threshold 200K/sec)",
                        "<strong>SQL safety:</strong> parameterized queries (sqlalchemy/PDO); input validation <code>^[0-9a-zA-Z]{1,7}$</code>",
                    ],
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Key Generation Service (KGS)",
            "subtitle": "Generating unique keys",
            "blocks": [
                {"type": "h3", "text": "Architecture"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>KGS instance:</strong> stateless service with in-memory key pool",
                        "<strong>Key pool DB:</strong> separate MySQL instance for reserved counter ranges",
                        "<strong>Pre-generation:</strong> KGS generates 100K keys at startup",
                        "<strong>Local cache:</strong> in-memory queue; refill when &lt; 10K remaining",
                        "<strong>Standby KGS:</strong> secondary instance for failover (heartbeat every 5 sec)",
                    ],
                },
                {"type": "h3", "text": "Key Pool Schema"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE key_pool (\n"
                        "  pool_id        INT PRIMARY KEY AUTO_INCREMENT,\n"
                        "  start_counter  BIGINT NOT NULL,\n"
                        "  end_counter    BIGINT NOT NULL,\n"
                        "  status         ENUM('AVAILABLE','RESERVED','EXHAUSTED'),\n"
                        "  reserved_by    VARCHAR(50),\n"
                        "  reserved_at    TIMESTAMP,\n"
                        "  INDEX idx_status (status)\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "Reservation Flow"},
                {
                    "type": "numbered",
                    "items": [
                        "KGS startup: <code>SELECT FROM key_pool WHERE status='AVAILABLE' LIMIT 1</code>",
                        "Reserve range: <code>UPDATE key_pool SET status='RESERVED', reserved_by=? WHERE pool_id=?</code>",
                        "Fetch keys: load start_counter to end_counter; convert to Base62",
                        "Local cache: store in-memory queue; increment per request",
                        "Refill: when queue &lt; 10K keys, SELECT next available pool",
                    ],
                },
                {"type": "h3", "text": "Edge Case: KGS Exhaustion"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Problem:</strong> all 62^7 keys exhausted (unlikely in &gt; 90,000 years at this rate)",
                        "<strong>Solution 1:</strong> increase key length to 8 (62^8 ≈ 218 trillion)",
                        "<strong>Solution 2:</strong> recycle expired keys (rescan and return to pool)",
                        "<strong>Monitoring:</strong> alert when pool utilization &gt; 90%",
                    ],
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Scalability & Distribution",
            "subtitle": "Growing to billions",
            "blocks": [
                {"type": "h3", "text": "Horizontal Scaling"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Write Service:</strong> stateless; add instances behind load balancer",
                        "<strong>Read Service:</strong> stateless; scale independently from writes",
                        "<strong>KGS:</strong> multiple instances; each owns a non-overlapping pool range",
                        "<strong>Database:</strong> shard by short_key hash (256–1024 shards)",
                    ],
                },
                {"type": "h3", "text": "Database Sharding"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Shard key:</strong> hash(short_key) % 256",
                        "<strong>Replication:</strong> primary + 2 replicas per shard (3-way)",
                        "<strong>Read replicas:</strong> serve analytics queries; eventual consistency OK",
                        "<strong>Write failover:</strong> automatic promotion (Orchestrator)",
                    ],
                },
                {"type": "h3", "text": "Global Distribution"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Primary region:</strong> US-East (writes; strong consistency)",
                        "<strong>Read replicas:</strong> US-West, EU, APAC (1–2 sec replication lag)",
                        "<strong>CDN:</strong> global edge caches popular URLs",
                        "<strong>Kafka:</strong> multi-region cluster; replicate analytics across regions",
                    ],
                },
                {"type": "h3", "text": "Cache Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Redis cluster:</strong> 16 nodes, sharded by short_key (~12 GB hot working set)",
                        "<strong>Cache-aside:</strong> Read Service checks Redis; miss = MySQL query + cache fill",
                        "<strong>TTL:</strong> 24 hours for hot URLs; 1 hour for cooler ones",
                        "<strong>Invalidation:</strong> manual purge on custom URL update; periodic refresh",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Consistent Hashing",
                    "body": (
                        "Use consistent hashing for cache and database sharding. Allows "
                        "adding/removing nodes with minimal key redistribution (only 1/N keys "
                        "move). Examples: Jump Hash, Ketama."
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
                        ["Redis down", "Cache miss; ~5× MySQL load",
                         "Redis health check", "Failover to replica; degrade gracefully"],
                        ["MySQL shard down", "Reads/writes to that shard fail",
                         "Connection timeout", "Auto-promote replica; reroute hot keys"],
                        ["KGS exhausted", "Cannot create new URLs",
                         "KGS error metric", "Scale KGS; increase key length; recycle"],
                        ["CDN edge down", "Slow redirects from that region",
                         "CDN provider alert", "Reroute to nearest edge; fall back to origin"],
                        ["Kafka down", "Analytics not logged; writes still work",
                         "Broker dead alert", "Async retry; local buffer + replay"],
                        ["Safe Browsing timeout", "Shorten request slow",
                         "HTTP timeout (&gt;2s)", "Allow with 'pending review' flag; async re-check"],
                        ["Network partition", "Cross-region unavailable",
                         "Latency spike; conn errors", "Local DC serves; eventual consistency on repair"],
                    ],
                },
                {"type": "h3", "text": "Disaster Recovery"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>RTO:</strong> &lt;30 minutes for any single service",
                        "<strong>RPO:</strong> &lt;1 minute for analytics (Kafka); &lt;5 min for URLs (MySQL)",
                        "<strong>Backups:</strong> incremental MySQL hourly; S3 30-day retention",
                        "<strong>Failover:</strong> automatic for cache and KGS; manual for DB to ensure consistency",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful Degradation",
                    "body": (
                        "In failures, prioritize redirects (the core function). Degrade analytics "
                        "logging and custom aliases first. Always return 200 for known URLs, 404 "
                        "for unknown; never 5xx unless truly critical."
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
                        ["Redirect type", "301 Permanent",
                         "Browser cache reduces load; cannot retarget. 302 allows flexibility but increases origin traffic."],
                        ["Cache consistency", "Eventual",
                         "Stale data briefly; faster reads. Strong consistency would slow the redirect path."],
                        ["Analytics", "Async (Kafka)",
                         "Delayed by 1–2 sec; doesn't block shorten. Sync logging would add ~50 ms to every shorten."],
                        ["Database", "MySQL sharded",
                         "Operational complexity; strong consistency. NoSQL is easier to scale but weaker on consistency."],
                        ["Key generation", "Pre-generated (KGS)",
                         "Extra service; no collisions. Base62 counter is simpler but needs distributed coordination."],
                        ["Expiry", "Lazy",
                         "Stale rows briefly; very low overhead. Active scan adds DB pressure."],
                        ["CDN coverage", "60% popular URLs",
                         "Reduced origin load; ~40% miss rate. 100% coverage costs more and adds invalidation pain."],
                        ["Sharding", "256 shards",
                         "Good parallelism; manageable ops. 64 contention; 1024+ overhead."],
                    ],
                },
            ],
        },
        # ---- 16 ------------------------------------------------------
        {
            "num": "16",
            "title": "Interview Playbook",
            "subtitle": "How to present this",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "This guide distils a 40-minute interview into a structured narrative. "
                        "Use it to practice explaining system design clearly, defending trade-offs, "
                        "and handling follow-ups with confidence."
                    ),
                },
                {"type": "h3", "text": "45-Minute Interview Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (2 min):</strong> clarify requirements: 100M URLs/day, 100:1 read:write, 5-yr retention, global",
                        "<strong>Capacity (5 min):</strong> 1.2K writes/sec, 120K reads/sec, 91 TB storage, ~12 GB cache",
                        "<strong>High-level arch (3 min):</strong> CDN, LB, services, data tier",
                        "<strong>Write path (8 min):</strong> KGS, MySQL, Redis warming; explain atomicity",
                        "<strong>Read path (7 min):</strong> cache hit-rate, redirect type, analytics logging",
                        "<strong>Deep dive (12 min):</strong> KGS counter ranges & HA, sharding, or analytics",
                        "<strong>Scalability (5 min):</strong> horizontal scaling, global distribution, monitoring",
                        "<strong>Failures (3 min):</strong> top 3 failure modes; mitigation for each",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "“1.2K writes/sec, 120K reads/sec” — demonstrates capacity math",
                        "“62^7 = 3.5 trillion keys” — why KGS works and won't exhaust",
                        "“91 TB storage” — justifies database sharding strategy",
                        "“KGS pre-generates keys” — prevents collisions; enables atomicity",
                        "“301 + CDN cache” — reduces load; handles 100:1 ratio",
                        "“Async Kafka for analytics” — doesn't block the critical path",
                        "“Eventual consistency acceptable” — explicit trade-off rationale",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: How do you prevent collisions?</strong> A: KGS reserves keys from a pre-generated pool; every key issued once. UNIQUE constraint catches any duplicates.",
                        "<strong>Q: What if MySQL goes down?</strong> A: Reads to that shard fail; auto-failover (Orchestrator) promotes a replica. Writes buffer locally and retry on recovery.",
                        "<strong>Q: How do you scale the cache?</strong> A: Redis cluster, sharded by short_key with consistent hashing; adding nodes moves only 1/N of keys.",
                        "<strong>Q: 301 vs 302 cost?</strong> A: 301 reduces origin traffic by ~80% via browser cache. 302 reaches the origin every time. At 120K reads/sec, 301 wins by a wide margin.",
                        "<strong>Q: Malicious URLs?</strong> A: Block at shorten via Safe Browsing; rate-limit per user (1000/day) to prevent abuse.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "1.2K writes/sec &nbsp;·&nbsp; 120K reads/sec &nbsp;·&nbsp; "
                        "62^7 = 3.5T keys &nbsp;·&nbsp; 91 TB over 5 years &nbsp;·&nbsp; "
                        "80% Redis hit rate &nbsp;·&nbsp; 60% CDN hit rate &nbsp;·&nbsp; "
                        "~12 GB hot cache."
                    ),
                },
            ],
        },
    ],
}
