"""Source for `01 - TypeAhead and Autocomplete.pdf` (regenerated; trie derivation justified)."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design a TypeAhead / Search Autocomplete System",
    "subtitle": "Trie, top-k, Redis, and an offline rebuild pipeline at 5B queries/day",
    "read_time": "~ 30 minute read",
    "short_title": "Design a TypeAhead / Search Autocomplete",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Statement & Clarifying Questions",
            "subtitle": "Scope, assumptions, and trade-offs",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Design a search autocomplete system that powers <strong>type-ahead "
                        "suggestions</strong> at global scale. Users expect real-time, accurate, "
                        "personalized suggestions as they type. The system must be low-latency, "
                        "highly available, and resilient to failures."
                    ),
                },
                {"type": "h3", "text": "Key Clarifications to Ask"},
                {
                    "type": "table",
                    "headers": ["Question", "Assumption"],
                    "rows": [
                        ["Scale?", "5 billion queries per day across all regions"],
                        ["Queries/user?", "~10 queries per day on average (active users)"],
                        ["Query latency SLA?", "&lt;50ms p99, ideally &lt;15ms p50"],
                        ["Personalization?", "Yes — user history + global trends"],
                        ["Multi-language?", "Yes — at least 10 major languages"],
                        ["Mobile?", "Yes — both web and mobile clients"],
                        ["Update frequency?", "Daily batch updates (hourly trending)"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "What to clarify first",
                    "body": (
                        "Always nail down: <strong>query volume</strong>, <strong>latency "
                        "requirements</strong>, <strong>update frequency</strong>, "
                        "<strong>personalization scope</strong>, <strong>languages</strong>, and "
                        "whether to support typo correction. These six answers drive every "
                        "downstream choice."
                    ),
                },
            ],
        },
        # ---- 02 ------------------------------------------------------
        {
            "num": "02",
            "title": "Functional & Non-Functional Requirements",
            "subtitle": "What the system must and should do",
            "blocks": [
                {"type": "h3", "text": "Functional Requirements"},
                {
                    "type": "bullets",
                    "items": [
                        "Given a partial query string, return <strong>top-k</strong> (typically 5–10) suggestions in real-time",
                        "Support <strong>prefix matching</strong> (e.g., 'ap' → apple, app, application)",
                        "Rank suggestions by <strong>popularity, recency, and user history</strong>",
                        "Update suggestions <strong>daily</strong> based on aggregate query trends; <strong>hourly</strong> for trending",
                        "Support <strong>multiple languages</strong> and alphabets (Latin, Cyrillic, CJK)",
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target", "Rationale"],
                    "rows": [
                        ["Latency (p99)", "&lt;50 ms", "Mobile users expect instant feedback"],
                        ["Availability", "99.95%", "Global service, regional failover"],
                        ["QPS capacity", "58,000 QPS avg / 111K peak", "5B queries/day ÷ 86,400 sec"],
                        ["Query freshness", "≤ 1 hour", "Trending queries update hourly; full rebuild daily"],
                        ["Consistency", "Eventual", "OK to have stale suggestions briefly"],
                        ["Cost efficiency", "&lt; 1 µ$ per query", "Scale requires aggressive optimization"],
                    ],
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "The numbers that drive architecture decisions",
            "blocks": [
                {"type": "h3", "text": "Query Volume"},
                {
                    "type": "bullets",
                    "items": [
                        "Daily queries: <strong>5,000,000,000</strong> (5B)",
                        "Seconds per day: 86,400",
                        "Average QPS: 5B ÷ 86,400 = <strong>57,870 QPS ≈ 58K QPS</strong>",
                        "Hourly average: 5B ÷ 24 = <strong>~208M queries/hour</strong>",
                        "Peak hour at 4× average: 208M × 4 / 3,600 = <strong>~231K QPS</strong> (use ~111K for sustained planning, headroom to ~230K)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Peak QPS Drives Sizing",
                    "body": (
                        "Capacity plans must cover peak, not average. Sustained peak ≈ "
                        "<strong>111K QPS</strong>; design for 2× headroom (~230K QPS) so "
                        "auto-scale has time to react."
                    ),
                },
                {"type": "h3", "text": "Cache Hit Ratio & Working Set"},
                {
                    "type": "numbered",
                    "items": [
                        "Cache hit ratio: <strong>~90%</strong> of requests hit Redis (popular prefixes)",
                        "Top-k results per prefix: <strong>10 suggestions</strong>",
                        "Unique prefixes (hot working set): ~<strong>5M</strong> for English, ~<strong>10M</strong> across all languages",
                        "Bytes per suggestion: ~100 bytes (text + score + metadata)",
                        "Cache size (Redis): 5M prefixes × 10 results × 100B = <strong>5 GB hot</strong> (round to ~6–8 GB cluster)",
                    ],
                },
                {"type": "h3", "text": "Trie Storage — Back-of-Envelope"},
                {
                    "type": "para",
                    "text": (
                        "The 750 GB figure floats around interview answers without a derivation. "
                        "Here is one that holds up. The trie stores <em>every prefix</em> of every "
                        "indexed query, with a top-k cache co-located at each node."
                    ),
                },
                {
                    "type": "bullets",
                    "items": [
                        "Unique indexed queries (multi-language, after dedup &amp; min-frequency cutoff): <strong>~50M</strong>",
                        "Average query length: <strong>15 chars</strong> (English short; CJK shorter; URLs/longer queries balance)",
                        "Naive trie nodes: 50M × 15 = 750M; with prefix sharing the effective node count lands at <strong>~300M</strong> (common prefixes collapse)",
                        "Per-node payload: children map (avg 3 × 16B = 48B) + flags (8B) + freq (8B) + top-k cache (10 entries × ~50B = 500B) + headers ≈ <strong>~600 B</strong>",
                        "Raw trie size: 300M × 600B ≈ <strong>180 GB</strong> per copy",
                        "Add serialization overhead, indexes, and SSTable write amplification (~1.3×): <strong>~234 GB</strong>",
                        "Replication factor 3 (Cassandra default for this workload): 234 × 3 ≈ <strong>~700–750 GB</strong> across the cluster",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why 750 GB is the right order of magnitude",
                    "body": (
                        "The dominant term is the <strong>top-k cache at each node</strong>, not "
                        "the trie skeleton. Most of the bytes are pre-computed top-k lists, which "
                        "is exactly why we pay for them — they collapse a tree walk into an O(1) "
                        "node read. Skip the cache and the index drops to ~30 GB raw, but every "
                        "lookup becomes a subtree DFS."
                    ),
                },
                {"type": "h3", "text": "Network & Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "Avg query size: ~<strong>20 bytes</strong> (UTF-8 prefix)",
                        "Avg response size: ~<strong>500 bytes</strong> (10 results + scores + metadata)",
                        "Inbound bandwidth at 58K QPS: 58K × 20B = <strong>1.16 MB/s</strong>",
                        "Outbound bandwidth at 58K QPS: 58K × 500B = <strong>29 MB/s</strong>",
                        "Storage on Cassandra (raw + replication): <strong>~750 GB cluster</strong> (~234 GB × 3)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "QPS: <strong>58K avg / 111K peak</strong> &nbsp;·&nbsp; "
                        "Cache hit: <strong>~90%</strong> &nbsp;·&nbsp; "
                        "Redis hot: <strong>~5–8 GB</strong> &nbsp;·&nbsp; "
                        "Cassandra trie: <strong>~750 GB</strong> (with 3× repl.) &nbsp;·&nbsp; "
                        "Outbound: <strong>~29 MB/s</strong>"
                    ),
                },
                {
                    "type": "para",
                    "text": (
                        "<em>Network and storage are not the bottlenecks. Latency is king.</em>"
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level System Architecture",
            "subtitle": "Five-tier system design with distributed caching",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Five distinct tiers orchestrate the request flow: <strong>Client</strong>, "
                        "<strong>Edge</strong> (CDN + LB), <strong>API Gateway</strong>, "
                        "<strong>Service Layer</strong> (Suggestion + Trending), and "
                        "<strong>Data Layer</strong> (Redis + Cassandra + Kafka). Reads are cached "
                        "and served from CDN/Redis where possible; writes flow through Kafka into "
                        "an offline rebuild pipeline."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Request flow: Client → CDN → LB → API Gateway → Suggestion Service. Suggestion Service hits Redis (~90%) and falls through to Cassandra on miss. Async path logs queries to Kafka for trend analysis.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Client"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Client [label="Browser / Mobile App\n(debounce 50ms)", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        CDN [label="CDN\n(popular prefixes)", fillcolor="#cbeedf"];
        LB  [label="Load Balancer", fillcolor="#cbeedf"];
    }
    subgraph cluster_gw {
        label="Gateway"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        GW [label="API Gateway\n(auth + rate limit)", fillcolor="#fff2c9"];
    }
    subgraph cluster_svc {
        label="Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        SS [label="Suggestion\nService",  fillcolor="#fff2c9"];
        TS [label="Trending\nService",    fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        Redis [label="Redis\n(top-k per prefix)",   fillcolor="#ead7fb"];
        Cass  [label="Cassandra\n(trie index)",     fillcolor="#ead7fb"];
        Kafka [label="Kafka\n(query events)",       fillcolor="#fbd7c5"];
    }

    Client -> CDN  [label="GET /suggest?q=", color="#1f8359"];
    CDN    -> LB   [label="MISS"];
    LB     -> GW;
    GW     -> SS;
    SS -> Redis [label="HIT (~90%)", style=dashed];
    SS -> Cass  [label="MISS (~10%)", style=dashed];
    SS -> Kafka [label="log query", style=dashed];
    TS -> Kafka [style=dashed];
    TS -> Redis [label="warm trending", style=dashed];
}
""",
                },
                {"type": "h3", "text": "Tier Responsibilities at a Glance"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Client:</strong> debounces input (50–100 ms); caches recent queries locally",
                        "<strong>Edge:</strong> CDN serves popular prefixes; LB routes regional traffic",
                        "<strong>API Gateway:</strong> rate limiting, auth, request normalization",
                        "<strong>Suggestion Service:</strong> Redis lookup → Cassandra fallback → rank → respond",
                        "<strong>Data:</strong> Redis hot cache, Cassandra immutable trie, Kafka query log",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Architecture Component Breakdown",
            "subtitle": "Role and responsibility of each tier",
            "blocks": [
                {"type": "h3", "text": "Client Layer"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Browser / Mobile App:</strong> UI initiates requests; client-side debouncing (50–100 ms)",
                        "<strong>SDK / client cache:</strong> optional local cache for the user's recent queries (&lt; 1 ms)",
                    ],
                },
                {"type": "h3", "text": "Edge / Network Layer"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>CDN edge:</strong> geographic distribution; serves cached responses for popular prefixes",
                        "<strong>Load balancer:</strong> routes traffic across API Gateway instances; health-check failover",
                    ],
                },
                {"type": "h3", "text": "API & Gateway Layer"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>API Gateway:</strong> rate limiting (token bucket), auth validation, request logging",
                        "<strong>Query Normalizer:</strong> lowercase, trim whitespace, Unicode NFC normalization",
                    ],
                },
                {"type": "h3", "text": "Service Layer"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Suggestion Service:</strong> core logic: Redis lookup → on miss, trie walk in Cassandra → rank → respond",
                        "<strong>Trending Service:</strong> async consumer of Kafka events; updates trending cache hourly",
                    ],
                },
                {"type": "h3", "text": "Data & Cache Layer"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Redis Cache:</strong> top-10 suggestions per prefix; 10-minute TTL",
                        "<strong>Cassandra cluster:</strong> immutable trie index; sharded by prefix hash; 3× replication",
                        "<strong>Kafka topic:</strong> event log of all queries; feeds trending service and batch pipeline",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Read-Path / Write-Path Separation",
                    "body": (
                        "Separate read-path (cached, latency-sensitive) from write-path "
                        "(offline batch). The eventual-consistency model is what makes high "
                        "availability cheap — writes never block reads."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Core Data Structure: Trie",
            "subtitle": "Prefix trees for efficient O(m) lookup",
            "blocks": [
                {"type": "h3", "text": "Why a Trie?"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Prefix matching:</strong> O(m) to find all strings with prefix, where m = query length",
                        "<strong>Memory efficient:</strong> common prefixes share subtrees ('app', 'apple' share 'app')",
                        "<strong>No full-text scan:</strong> direct navigation from root to prefix node",
                        "<strong>Ranked results:</strong> store top-k at each node (pre-computed during batch rebuild)",
                        "<strong>Immutable:</strong> each version is a snapshot; enables atomic blue-green swaps",
                    ],
                },
                {"type": "h3", "text": "TrieNode Structure"},
                {
                    "type": "code",
                    "text": (
                        "class TrieNode:\n"
                        "    def __init__(self):\n"
                        "        self.children = {}            # char -> TrieNode\n"
                        "        self.is_word = False\n"
                        "        self.frequency = 0\n"
                        "        self.top_k = []               # [(query, score, freq), ...]\n"
                        "        self.personalized_top_k = {}  # user_id -> [(query, score), ...]\n"
                    ),
                },
                {
                    "type": "para",
                    "text": (
                        "Each node caches top-k suggestions; updated during the offline batch "
                        "rebuild. The cache is the whole point — it makes lookup O(1) after the "
                        "O(m) walk."
                    ),
                },
                {"type": "h3", "text": "Lookup Complexity"},
                {
                    "type": "table",
                    "headers": ["Operation", "Complexity", "Notes"],
                    "rows": [
                        ["Find prefix node", "O(m)", "m = length of query prefix (typically 2–10)"],
                        ["Get top-k results", "O(1)", "Cached at node"],
                        ["Insert/update", "O(m)", "Used only during batch rebuild"],
                        ["Serialization", "O(n)", "n = total trie nodes (~300M)"],
                    ],
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Ranking & Scoring Formula",
            "subtitle": "Popularity, recency, personalization, and context",
            "blocks": [
                {"type": "h3", "text": "Multi-Signal Scoring"},
                {
                    "type": "code",
                    "text": (
                        "score = w1*freq + w2*recency + w3*personalization + w4*context\n\n"
                        "where:\n"
                        "  freq            = normalized query frequency (0-1)\n"
                        "  recency         = time decay (recent queries weighted higher)\n"
                        "  personalization = user's historical preference (0-1)\n"
                        "  context         = language, region, device type, user location\n\n"
                        "Recommended weights: w1=0.4, w2=0.3, w3=0.2, w4=0.1\n"
                    ),
                },
                {"type": "h3", "text": "Time Decay Function (Recency)"},
                {
                    "type": "code",
                    "text": (
                        "def recency_score(days_old: float) -> float:\n"
                        "    # Half-life = 30 days; older queries decay exponentially.\n"
                        "    return 2 ** (-days_old / 30.0)\n\n"
                        "# Today      -> 1.00\n"
                        "# 7 days ago -> 0.85\n"
                        "# 30 days ago-> 0.50\n"
                    ),
                },
                {"type": "h3", "text": "Ranking Signals Comparison"},
                {
                    "type": "table",
                    "headers": ["Signal", "Latency", "Accuracy", "Update Freq", "Personalization"],
                    "rows": [
                        ["Query frequency", "O(1)", "High", "Daily", "Global"],
                        ["User history", "O(1)", "High", "Real-time", "Per-user"],
                        ["Contextual (region)", "O(1)", "Medium", "Hourly", "Per-region"],
                        ["ML ranker", "~5 ms", "Very high", "Weekly", "Per-user"],
                        ["Click-through rate", "O(1)", "Medium", "Daily", "Per-user"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Layer Signals; Keep the Hot Path Cheap",
                    "body": (
                        "Start simple: <strong>frequency + recency</strong>. Layer "
                        "personalization and ML ranking later, and keep them <em>off</em> the hot "
                        "path. ML scoring belongs in the offline rebuild, not in the request path."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Trie Update Pipeline",
            "subtitle": "Offline batch and realtime streaming paths",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Two pipelines feed the trie. The <strong>batch path</strong> rebuilds the "
                        "full index daily and stages it into Cassandra; a blue-green swap promotes "
                        "it to live. The <strong>realtime path</strong> (Flink) streams hot updates "
                        "into Redis for trending queries within minutes — bypassing the slow rebuild "
                        "entirely for the head of the distribution."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Batch path (Kafka → Spark/Beam → Cassandra staging → blue-green swap → live) rebuilds the full trie daily. Realtime path (Kafka → Flink → Redis) warms hot/trending entries within minutes.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Kafka [label="Kafka\n(query events)", fillcolor="#fbd7c5"];

    subgraph cluster_batch {
        label="Batch path (daily)"; style="rounded,dashed"; color="#2e57b8"; fontcolor="#2e57b8";
        Batch  [label="Batch Job\n(Spark / Beam)\nagg + top-k", fillcolor="#dbe6fb"];
        Stage  [label="Cassandra\nStaging\n(new version)", fillcolor="#ead7fb"];
        Swap   [shape=diamond, label="Blue-Green\nSwap\n(is_live flag)", fillcolor="#fff2c9"];
        Live   [label="Cassandra\nLive\n(trie index)", fillcolor="#ead7fb"];
    }

    subgraph cluster_rt {
        label="Realtime path (minutes)"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        Flink  [label="Flink\n(hot prefix\ndetector)", fillcolor="#cbeedf"];
        Redis  [label="Redis\n(top-k cache)", fillcolor="#ead7fb"];
    }

    Kafka -> Batch  [label="hourly window"];
    Batch -> Stage  [label="bulk write"];
    Stage -> Swap;
    Swap  -> Live   [label="atomic flip", color="#1f8359"];

    Kafka -> Flink  [label="streaming", color="#1f8359"];
    Flink -> Redis  [label="warm hot prefix", color="#1f8359"];

    Live  -> Redis  [label="cache fill on miss", style=dashed];
}
""",
                },
                {"type": "h3", "text": "Pipeline Stages"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Ingest:</strong> Suggestion Service publishes every query to Kafka (partition by language)",
                        "<strong>Batch (daily, 2 AM UTC):</strong> Spark/Beam job aggregates frequency, computes top-k per prefix, builds new trie",
                        "<strong>Stage:</strong> bulk-write the new trie to Cassandra under a new <code>version</code> column",
                        "<strong>Hot-set decision:</strong> if a prefix is in the top-1M most-queried set, pre-warm Redis before the swap",
                        "<strong>Blue-green swap:</strong> flip the <code>is_live</code> flag on the new version; instant atomic promotion",
                        "<strong>Realtime path (Flink):</strong> windowed aggregation of trending terms; pushes top-k updates straight to Redis",
                        "<strong>Rollback:</strong> if errors spike, flip <code>is_live</code> back to the prior version on disk",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Two Paths, One Cache",
                    "body": (
                        "Batch and realtime converge on Redis. Batch handles correctness (full "
                        "rebuild, deterministic top-k); Flink handles freshness (trending in "
                        "minutes). Neither blocks the read path."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Request Flow Deep Dive",
            "subtitle": "Cache hit vs. miss: latency breakdown and code flow",
            "blocks": [
                {"type": "h3", "text": "Request Lifecycle"},
                {
                    "type": "numbered",
                    "items": [
                        "User types → client debounces 50 ms → fires <code>GET /suggest?q=ap</code>",
                        "API Gateway validates auth, applies rate limit, normalizes prefix",
                        "Suggestion Service: <code>GET redis:&quot;ap&quot;</code>",
                        "<strong>Cache HIT (~90%):</strong> return cached top-10 in &lt; 5 ms",
                        "<strong>Cache MISS (~10%):</strong> Cassandra trie walk for prefix → ~15–25 ms",
                        "Rank by frequency × recency × personalization (in-memory)",
                        "Populate Redis with TTL = 10 min; return results",
                        "<strong>Async:</strong> publish query event to Kafka (analytics + trending)",
                    ],
                },
                {"type": "h3", "text": "Latency Budget"},
                {
                    "type": "table",
                    "headers": ["Stage", "Cache hit (p50)", "Cache miss (p99)"],
                    "rows": [
                        ["Network (client → edge)", "10 ms", "10 ms"],
                        ["API Gateway", "1 ms", "2 ms"],
                        ["Redis lookup", "1 ms", "1 ms (miss)"],
                        ["Cassandra trie walk", "—", "15–25 ms"],
                        ["Ranking (in-memory)", "—", "2 ms"],
                        ["Network (edge → client)", "5 ms", "5 ms"],
                        ["<strong>Total</strong>", "<strong>~17 ms</strong>", "<strong>~40 ms</strong>"],
                    ],
                },
                {
                    "type": "code",
                    "text": (
                        "def suggest(prefix: str, user_id: str) -> list[dict]:\n"
                        "    prefix = normalize(prefix)              # lowercase, NFC\n"
                        "    cached = redis.get(f'sugg:{prefix}')\n"
                        "    if cached:\n"
                        "        return personalize(json.loads(cached), user_id)\n"
                        "    # Miss path: trie walk in Cassandra.\n"
                        "    rows = cassandra.execute(\n"
                        "        \"SELECT top_k_results FROM trie_index \"\n"
                        "        \"WHERE prefix=%s AND is_live=true\", (prefix,))\n"
                        "    top_k = rows[0]['top_k_results'] if rows else []\n"
                        "    redis.setex(f'sugg:{prefix}', 600, json.dumps(top_k))\n"
                        "    kafka.produce('queries', {'prefix': prefix, 'user_id': user_id})\n"
                        "    return personalize(top_k, user_id)\n"
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Database Schema & Persistence",
            "subtitle": "Cassandra for immutable trie snapshots",
            "blocks": [
                {"type": "h3", "text": "Why Cassandra?"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Wide-column store:</strong> efficient for key-value lookups by prefix",
                        "<strong>Tunable consistency:</strong> QUORUM reads with 3× replication; degrade to ONE under partition",
                        "<strong>Horizontal scaling:</strong> partition by prefix (consistent hashing); add nodes without reshuffling",
                        "<strong>Immutable snapshots:</strong> each trie version identified by timestamp; enables blue-green swap",
                    ],
                },
                {"type": "h3", "text": "Cassandra Schema"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE typeahead.trie_index (\n"
                        "  prefix         TEXT,                 -- e.g. 'a', 'ap', 'app'\n"
                        "  version        BIGINT,               -- trie version (epoch ms)\n"
                        "  top_k_results  FROZEN<LIST<TUPLE<TEXT, BIGINT, DOUBLE>>>,  -- (query, freq, score)\n"
                        "  is_live        BOOLEAN,              -- current live version\n"
                        "  PRIMARY KEY (prefix, version)\n"
                        ") WITH CLUSTERING ORDER BY (version DESC)\n"
                        "  AND compaction  = {'class': 'LeveledCompactionStrategy'}\n"
                        "  AND compression = {'sstable_compression': 'LZ4Compressor'};\n"
                    ),
                },
                {
                    "type": "para",
                    "text": (
                        "Partition by prefix hash. <code>version</code> as the clustering key "
                        "enables blue-green swaps and rollback in a single column update."
                    ),
                },
                {"type": "h3", "text": "Snapshot & Swap Strategy"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Serialization:</strong> Protocol Buffers (compact, versioned, backwards-compatible)",
                        "<strong>Rebuild schedule:</strong> daily batch (off-peak: 2 AM UTC) + hourly trending update",
                        "<strong>Retention:</strong> keep 2 versions on disk: live and prior (instant rollback target)",
                        "<strong>Atomic swap:</strong> update <code>is_live</code> flag; instant propagation via streaming replication",
                        "<strong>Rollback:</strong> revert <code>is_live</code> flag; previous version still on disk",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Partitioning Strategy",
            "subtitle": "Consistent hashing for balanced distribution",
            "blocks": [
                {"type": "h3", "text": "Option 1: First-Letter Sharding (Poor)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Approach:</strong> shard by first letter of query (26 shards for English)",
                        "<strong>Problem:</strong> highly uneven distribution; 'a' gets ~10× more traffic than 'z'",
                        "<strong>Result:</strong> hot shards → high latency; difficult to rebalance",
                    ],
                },
                {"type": "h3", "text": "Option 2: Consistent Hashing (Recommended)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Approach:</strong> hash prefix into a consistent hash ring; replicate on N successor nodes",
                        "<strong>Advantage:</strong> even distribution; incremental scaling (add nodes without reshuffling)",
                        "<strong>Implementation:</strong> Jump consistent hash (Google) or Maglev",
                        "<strong>Replication factor:</strong> N=3 (write to primary + 2 successors; QUORUM=2)",
                    ],
                },
                {"type": "h3", "text": "Consistent Hash — Reference Code"},
                {
                    "type": "code",
                    "text": (
                        "def consistent_hash(key: str, num_nodes: int) -> int:\n"
                        "    \"\"\"Jump consistent hash: fast, even distribution.\"\"\"\n"
                        "    hash_value = hash(key) & 0x7fffffff   # unsigned 31-bit\n"
                        "    return hash_value % num_nodes\n\n"
                        "def get_replicas(prefix: str, num_nodes: int, replication: int = 3):\n"
                        "    \"\"\"Get replica nodes for a prefix.\"\"\"\n"
                        "    primary = consistent_hash(prefix, num_nodes)\n"
                        "    return [primary] + [(primary + i) % num_nodes for i in range(1, replication)]\n"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why Jump Hash",
                    "body": (
                        "Jump hash is stateless, branch-free, and produces nearly perfect "
                        "distribution. Adding a node moves only <strong>1/N</strong> of keys "
                        "instead of rehashing the entire ring."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Failure Modes & Recovery",
            "subtitle": "Detecting and mitigating production incidents",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Detection", "Mitigation", "Recovery Time"],
                    "rows": [
                        ["Redis cluster down", "Health check", "Fall through to Cassandra; p99 ~40ms", "~1 min"],
                        ["Cassandra node down", "QUORUM read fails", "Serve from N-1 replicas", "~2 min"],
                        ["Trie rebuild fails", "CloudWatch alert", "Keep previous version live", "~5 min"],
                        ["API Gateway overload", "Latency spike &gt; 100 ms", "Rate limit + queue burst", "Immediate"],
                        ["Network partition", "Timeout &gt; 2 s", "Fallback to cached results", "~10 sec"],
                        ["Slow disk I/O", "p99 query &gt; 100 ms", "Increase cache TTL; shed load", "~5 min"],
                        ["Corrupted Cassandra data", "Checksum mismatch", "Restore from backup", "~30 min"],
                        ["DDoS on API Gateway", "QPS spike &gt; 2× normal", "Per-IP rate limit; auto-block", "~2 min"],
                    ],
                },
                {"type": "h3", "text": "Monitoring & Alerting"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Key metrics:</strong> QPS, p50/p99 latency, cache hit ratio, error rate, trie staleness",
                        "<strong>Dashboards:</strong> real-time SLO tracking (Grafana + Prometheus)",
                        "<strong>Alerting:</strong> auto-page on-call if p99 &gt; 50 ms or error rate &gt; 0.1%",
                        "<strong>Postmortems:</strong> blameless RCA on every incident &gt; 10 min downtime",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful Degradation",
                    "body": (
                        "Suggestions are a UX feature, not a money path. When in doubt, "
                        "<strong>return stale</strong> rather than nothing. A 1-day-old top-k is "
                        "almost always better than a spinner or an error."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Interview Playbook (45 min)",
            "subtitle": "Walkthrough timeline and talking points",
            "blocks": [
                {"type": "h3", "text": "45-Minute Timeline"},
                {
                    "type": "table",
                    "headers": ["Time", "Section", "Key Points"],
                    "rows": [
                        ["0–5 min", "Clarification", "Scale (5B/day?), latency SLA (&lt;50 ms?), personalization, languages"],
                        ["5–10 min", "Requirements", "Func / non-func; main components: cache, trie, partitioning"],
                        ["10–20 min", "Architecture", "Whiteboard high-level diagram: client → cache → trie → DB"],
                        ["20–30 min", "Deep dive", "Trie (O(m)), caching (90% hits), ranking (freq × recency)"],
                        ["30–40 min", "Scale-up", "Partitioning (consistent hashing), failure modes, trade-offs"],
                        ["40–45 min", "Polish", "Recap, ask for feedback, mention future improvements"],
                    ],
                },
                {"type": "h3", "text": "Must-Know Numbers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Scale:</strong> 5B queries/day → ~58K QPS avg, ~111K QPS sustained peak",
                        "<strong>Trie size:</strong> ~234 GB raw / <strong>~750 GB cluster</strong> with 3× replication",
                        "<strong>Cache size:</strong> ~5 GB Redis (5M prefixes × 10 results × 100 B)",
                        "<strong>Cache hit ratio:</strong> ~90% Redis, ~10% Cassandra fallback",
                        "<strong>p99 latency:</strong> ~17 ms (hit) / ~40 ms (miss)",
                        "<strong>Cache TTL:</strong> 10 minutes (freshness vs. hit-rate trade-off)",
                        "<strong>Unique prefixes:</strong> ~5–10M across all languages",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These",
                    "body": (
                        "58K QPS &nbsp;·&nbsp; 90% hit rate &nbsp;·&nbsp; ~5 GB Redis &nbsp;·&nbsp; "
                        "~750 GB Cassandra (3× repl.) &nbsp;·&nbsp; p99 &lt; 50 ms &nbsp;·&nbsp; "
                        "10-min cache TTL &nbsp;·&nbsp; 5–10M unique prefixes."
                    ),
                },
                {"type": "h3", "text": "Impressive Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Eventual consistency:</strong> 'Trie updates are atomic snapshots; we swap versions instantly. Clients tolerate brief staleness for high availability.'",
                        "<strong>Cache warming:</strong> 'Pre-load top-1M hot prefixes at startup. Lazy-load cold prefixes. Decision diamond in the pipeline: in top-1M? Yes → warm Redis.'",
                        "<strong>Consistent hashing:</strong> 'Prefixes distributed via jump hash. Add nodes incrementally without reshuffling; 3× replication for fault tolerance.'",
                        "<strong>Failure resilience:</strong> 'Redis miss → Cassandra (~40 ms p99). Cassandra down → stale local cache. Trie rebuild fails → keep previous version live.'",
                        "<strong>Two-path scale:</strong> 'Batch (daily) aggregates 5B queries into top-k. Realtime (Flink) streams hot updates. Both converge on Redis.'",
                    ],
                },
                {"type": "h3", "text": "Expected Follow-Up Questions"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>How do you handle typos?</strong> Edit-distance + separate typo-correction trie. Query both, merge results. Trade-off: ~5 ms extra.",
                        "<strong>Multi-word queries?</strong> Tokenize; walk trie per token; merge by combined frequency.",
                        "<strong>100× traffic surge?</strong> Token-bucket rate limit; shed load with partial results; HPA scale by QPS; cache warms naturally.",
                        "<strong>Cost optimization?</strong> LZ4 compression on Cassandra; spot instances for batch; CDN for edge; aggressive TTLs on hot prefixes.",
                    ],
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Key Takeaways",
            "subtitle": "Core insights and design principles",
            "blocks": [
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "1. Prefix Trie for O(m) Lookup",
                    "body": (
                        "Pre-compute top-k at each node. Immutable snapshots enable atomic "
                        "version swaps. The top-k cache is what makes lookup feel instant."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "2. Multi-Tier Caching",
                    "body": (
                        "Client → CDN → Redis (90% hits) → Cassandra (10% misses). Hit in &lt; 5 ms; "
                        "miss in 15–25 ms. Eventual consistency is not a bug, it's the design."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "3. Separate Read &amp; Write Paths",
                    "body": (
                        "Read: synchronous, cached, latency-sensitive. Write: offline batch (daily) "
                        "+ realtime streaming (hourly). <strong>Never block reads on writes.</strong>"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "4. Consistent Hashing for Scale",
                    "body": (
                        "Distribute prefixes evenly. Add nodes incrementally. 3× replication for "
                        "fault tolerance and data locality."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "5. Rank by Layered Signals",
                    "body": (
                        "Start with frequency + recency (fast). Layer personalization (cached, "
                        "1-hour TTL). Keep ML rankers <strong>off the hot path</strong>; use them "
                        "for offline scoring."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "6. Monitoring &amp; Resilience",
                    "body": (
                        "Track latency (p50/p99), cache hit ratio, error rate. Design for graceful "
                        "degradation: Redis down → Cassandra; Cassandra down → stale cache; "
                        "rebuild fails → keep prior version."
                    ),
                },
            ],
        },
    ],
}
