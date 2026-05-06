"""Source for `14 - Rate Limiter.pdf`."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design a Distributed Rate Limiter",
    "subtitle": "API gateway throttling at Stripe / Cloudflare scale",
    "read_time": "~ 40 minute read",
    "short_title": "Design a Distributed Rate Limiter",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Statement",
            "subtitle": "What we're building and why",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Design a <strong>distributed rate limiter</strong> that throttles API "
                        "traffic in front of services such as <strong>Stripe</strong>, "
                        "<strong>Cloudflare</strong>, or a <strong>public API gateway</strong>. "
                        "It must enforce per-identity quotas across a fleet of stateless gateways, "
                        "decide accept-or-reject in well under a millisecond, and never become the "
                        "bottleneck for legitimate traffic."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Where does it live?", "Sidecar/library inside the API Gateway tier; centralized counter store"],
                        ["What identifies a caller?", "Tiered: API key &gt; user_id &gt; device &gt; IP"],
                        ["How many quotas?", "Per identity × endpoint × window (e.g., 1K rps, 10K/min, 1M/day)"],
                        ["Hard or soft limits?", "Both: hard 429 by default; soft = log-only for canaries"],
                        ["Burst tolerance?", "Yes — token bucket allows short bursts up to 2× steady rate"],
                        ["Failure policy?", "Fail-open for read traffic, fail-closed for write/billing"],
                        ["Global vs regional?", "Regional cluster of Redis; eventual cross-region reconciliation"],
                        ["Tiers?", "Free / Premium / Enterprise with configurable quotas"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why this matters",
                    "body": (
                        "A rate limiter is on the hot path of every request — every API call pays its "
                        "latency tax. A bad design slows the whole product; a good one is invisible until "
                        "an abuser shows up."
                    ),
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
                        ["Allow / deny", "Return ALLOW (200/202) or DENY (429 Too Many Requests)"],
                        ["Multi-window", "Per-second, per-minute, per-hour, per-day limits coexist"],
                        ["Multi-identity", "Match the tightest of: API key, user_id, IP, device fingerprint"],
                        ["Tiered quotas", "Free / Premium / Enterprise with hot-reloadable config"],
                        ["Headers", "Emit <code>X-RateLimit-Limit</code>, <code>-Remaining</code>, <code>-Reset</code>, <code>Retry-After</code>"],
                        ["Bypass list", "Internal services and health checks skip the limiter"],
                        ["Observability", "Per-key counters, allow/deny ratio, top-N abusers"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Throughput", "<strong>10M requests/sec</strong> across the cluster"],
                        ["Added latency", "<strong>p99 &lt; 1 ms</strong> on the gateway critical path"],
                        ["Accuracy", "± a few percent under burst; exact within a single node"],
                        ["Availability", "99.99% — degrade to fail-open on store outage"],
                        ["Counter cardinality", "<strong>~100M unique keys</strong> (user × endpoint × window)"],
                        ["State storage", "<strong>~10 GB</strong> Redis cluster (replicated, 6+ shards)"],
                        ["Config propagation", "&lt; 5 sec for limit changes to reach all gateways"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Headline Numbers",
                    "body": (
                        "<strong>10M req/sec</strong> &nbsp;·&nbsp; "
                        "<strong>p99 &lt; 1 ms</strong> added &nbsp;·&nbsp; "
                        "<strong>~100M counter keys</strong> &nbsp;·&nbsp; "
                        "<strong>~10 GB Redis</strong> &nbsp;·&nbsp; "
                        "fail-open reads / fail-closed writes."
                    ),
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "Sizing the counter store and gateway tier",
            "blocks": [
                {"type": "h3", "text": "Traffic"},
                {
                    "type": "bullets",
                    "items": [
                        "Aggregate cluster traffic: <strong>10,000,000 req/sec</strong> across regions",
                        "Per-gateway throughput: ~50K rps × 200 gateways = 10M rps",
                        "Limiter calls per request: <strong>1</strong> (one bucket lookup per identity tier)",
                        "Per-Redis-shard QPS: 10M / 16 shards ≈ <strong>625K ops/sec</strong> (well within Redis limits)",
                    ],
                },
                {"type": "h3", "text": "Counter Cardinality"},
                {
                    "type": "bullets",
                    "items": [
                        "Active users: ~10M monthly, ~1M concurrent",
                        "Endpoints per service: ~20 distinct endpoints with their own quotas",
                        "Windows per limit: per-second + per-minute + per-day = 3 windows",
                        "Unique keys: ~1M concurrent users × 20 endpoints × 3 windows ≈ <strong>~60M keys</strong>",
                        "Plus IP-based and API-key buckets: total <strong>~100M unique keys</strong>",
                    ],
                },
                {"type": "h3", "text": "Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "Per key: ~64 B key string + 16 B value (count + TTL metadata) + ~20 B Redis overhead ≈ <strong>~100 B</strong>",
                        "Total: 100M × 100 B = <strong>~10 GB</strong> hot working set",
                        "Replicated 1× for HA → <strong>~20 GB</strong> across the Redis cluster",
                        "TTL policy: every key expires when its window does, so the set self-prunes",
                    ],
                },
                {"type": "h3", "text": "Bandwidth"},
                {
                    "type": "bullets",
                    "items": [
                        "Each Redis call: ~200 B request + ~100 B response ≈ <strong>300 B</strong>",
                        "Cluster bandwidth: 10M × 300 B = <strong>3 GB/s</strong> ≈ 24 Gbps east-west",
                        "Shard out to 16+ Redis nodes; each node sees ~1.5 Gbps — comfortable",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Capacity Recap",
                    "body": (
                        "<strong>10M rps</strong> · <strong>16 Redis shards</strong> · "
                        "<strong>~625K ops/shard</strong> · <strong>~10 GB</strong> hot state · "
                        "<strong>p99 &lt; 1 ms</strong> on the gateway."
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level Architecture",
            "subtitle": "Where the limiter sits and how it fans out",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The limiter is a thin <strong>library or sidecar</strong> embedded in every "
                        "API Gateway pod. On each request it looks up the identity, fetches the limit "
                        "config, consults a sharded <strong>Redis cluster</strong> for the counter, and "
                        "either passes the request to the backend or short-circuits with HTTP 429. The "
                        "Redis cluster is the only piece of shared state — everything else is stateless."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Per-request flow: API Gateway → Rate Limiter (sidecar) → Redis cluster (sharded by key). On allow, the request continues to the backend; on deny, the gateway returns 429 with Retry-After.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Clients"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Client [label="Mobile / Web / 3rd-party", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        LB  [label="L7 Load Balancer", fillcolor="#cbeedf"];
        GW  [label="API Gateway\n(stateless, 200 pods)", fillcolor="#cbeedf"];
    }
    subgraph cluster_rl {
        label="Rate Limiter"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        RL [label="Limiter sidecar\n(token bucket + sliding window)", fillcolor="#fff2c9"];
        Cfg[label="Config Service\n(quotas / tiers)", fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Counter Store"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        R1 [label="Redis shard 1", fillcolor="#ead7fb"];
        R2 [label="Redis shard 2", fillcolor="#ead7fb"];
        Rn [label="Redis shard N", fillcolor="#ead7fb"];
    }
    subgraph cluster_be {
        label="Backend"; style="rounded,dashed"; color="#a13b3b"; fontcolor="#a13b3b";
        BE [label="Service backends", fillcolor="#fbd7c5"];
    }

    Client -> LB;
    LB -> GW;
    GW -> RL [label="check(key)"];
    RL -> Cfg [style=dashed, label="hot reload"];
    RL -> R1  [label="EVAL Lua\n(hash slot)"];
    RL -> R2  [style=dashed];
    RL -> Rn  [style=dashed];
    RL -> GW  [label="ALLOW / DENY"];
    GW -> BE  [label="ALLOW", color="#1f8359"];
    GW -> Client [label="429 Retry-After", style=dashed, color="#a13b3b"];
}
""",
                },
                {"type": "h3", "text": "Component Responsibilities"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>API Gateway:</strong> terminates TLS, authenticates, extracts identity, calls limiter",
                        "<strong>Rate Limiter sidecar/library:</strong> picks identity tier, builds keys, runs Lua check on Redis, attaches headers",
                        "<strong>Config Service:</strong> publishes per-tier quotas; gateways subscribe over gRPC stream",
                        "<strong>Redis Cluster:</strong> sharded by hash(key); holds counter state; replicated 1×",
                        "<strong>Backend:</strong> receives only ALLOWED traffic; never sees abusers",
                        "<strong>Observability:</strong> sample of allow/deny → Kafka → analytics for abuse detection",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Algorithm Comparison",
            "subtitle": "Five canonical rate-limiting algorithms",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Five algorithms dominate the literature. Each makes a different trade between "
                        "memory, accuracy, smoothness, and burst handling. The table below summarises "
                        "what to pick when."
                    ),
                },
                {"type": "h3", "text": "Side-by-Side"},
                {
                    "type": "table",
                    "headers": ["Algorithm", "Accuracy", "Memory / key", "Burst", "Pros", "Cons"],
                    "rows": [
                        ["Fixed Window",
                         "Low",
                         "1 counter (~16 B)",
                         "2× at boundary",
                         "Trivial; one INCR per req",
                         "Edge bursts: 2× at the window flip"],
                        ["Sliding Window Log",
                         "Exact",
                         "O(N) timestamps (~KBs)",
                         "Smooth",
                         "Perfectly precise",
                         "Memory blows up under load"],
                        ["Sliding Window Counter",
                         "High (~1% err)",
                         "2 counters (~32 B)",
                         "Smooth",
                         "Cheap + accurate; weighted blend of two adjacent windows",
                         "Slight approximation; assumes uniform request distribution within a window"],
                        ["Token Bucket",
                         "High",
                         "2 numbers (~32 B)",
                         "Configurable burst (bucket size)",
                         "Smooth allowance + burst; intuitive",
                         "Two parameters to tune (rate, capacity)"],
                        ["Leaky Bucket",
                         "High",
                         "Queue (~KB)",
                         "None — strictly smoothed",
                         "Constant outflow; protects backends",
                         "Latency added by queue; harder to distribute"],
                    ],
                },
                {"type": "h3", "text": "When to Pick Which"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Token Bucket:</strong> default for user-facing APIs — smooth steady rate plus tolerated bursts",
                        "<strong>Sliding Window Counter:</strong> best when memory matters and you want near-exact accuracy",
                        "<strong>Fixed Window:</strong> simple monthly/daily quotas where the boundary effect is acceptable",
                        "<strong>Sliding Window Log:</strong> tiny per-user limits where exactness is required (e.g., login attempts)",
                        "<strong>Leaky Bucket:</strong> when you must guarantee a steady rate to a fragile downstream",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Recommended Default",
                    "body": (
                        "Use <strong>Token Bucket</strong> for the user-facing limit (smooth steady "
                        "rate + configurable burst), and layer a <strong>Sliding Window Counter</strong> "
                        "for the longer-window quotas (per-minute / per-day) where memory matters."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Token Bucket Deep Dive",
            "subtitle": "Smooth rate + burst",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "A token bucket has two parameters: <strong>capacity</strong> (max tokens, "
                        "i.e., burst size) and <strong>refill rate</strong> (tokens added per second). "
                        "Each request takes one token; if the bucket is empty the request is denied. "
                        "Refill is computed lazily, so we don't need a background ticker."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Token bucket state machine: tokens refill at rate r per second up to capacity C; each request consumes a token. If empty, deny.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=circle, style="filled", fontname="Helvetica", fontsize=10, color="#2e57b8", fillcolor="#dbe6fb"];
    edge [fontname="Helvetica", fontsize=9, color="#586278"];

    Full   [label="Full\n(C tokens)", fillcolor="#cbeedf"];
    Mid    [label="Partial\n(0 < t < C)"];
    Empty  [label="Empty\n(0 tokens)", fillcolor="#fbd7c5", color="#a13b3b"];

    Full  -> Mid   [label="request\n(t := C-1)"];
    Mid   -> Mid   [label="request, t > 0\n(t := t-1)"];
    Mid   -> Empty [label="request, t = 1"];
    Empty -> Mid   [label="refill: t := min(C, t + r·dt)"];
    Mid   -> Full  [label="refill (idle)"];
    Empty -> Empty [label="request → 429", color="#a13b3b", fontcolor="#a13b3b"];
}
""",
                },
                {"type": "h3", "text": "Reference Implementation (Pseudocode)"},
                {
                    "type": "code",
                    "text": (
                        "# Lazy token bucket: refill on demand, no background timer\n"
                        "# State per key: (tokens, last_refill_ts)\n"
                        "# Config:        capacity C, refill_rate r tokens/sec\n\n"
                        "def allow(key, C, r, now):\n"
                        "    tokens, last_ts = store.get(key, default=(C, now))\n"
                        "    elapsed   = now - last_ts\n"
                        "    tokens    = min(C, tokens + elapsed * r)   # lazy refill\n"
                        "    if tokens >= 1:\n"
                        "        tokens -= 1\n"
                        "        store.set(key, (tokens, now), ttl=2*C/r)\n"
                        "        return ALLOW, remaining=tokens\n"
                        "    retry_after = (1 - tokens) / r              # seconds until next token\n"
                        "    store.set(key, (tokens, now), ttl=2*C/r)\n"
                        "    return DENY, retry_after"
                    ),
                },
                {"type": "h3", "text": "Tuning"},
                {
                    "type": "table",
                    "headers": ["Tier", "Steady rate (r)", "Burst (C)", "Window math"],
                    "rows": [
                        ["Free",       "10 rps",   "20 tokens",   "≈ 600 req/min sustained"],
                        ["Premium",    "100 rps",  "200 tokens",  "≈ 6,000 req/min sustained"],
                        ["Enterprise", "1,000 rps", "2,000 tokens", "Custom; dedicated Redis shard"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why lazy refill?",
                    "body": (
                        "A background ticker for 100M keys is impossible. Computing refill on demand "
                        "(elapsed × rate) collapses the whole problem to a single read-modify-write per "
                        "request — and Redis can do that atomically with a Lua script."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Sliding Window Counter",
            "subtitle": "Accuracy at low memory",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Sliding Window Counter solves the boundary problem of Fixed Window without "
                        "the memory cost of Sliding Window Log. We keep two adjacent fixed-window "
                        "counters (current + previous) and linearly interpolate based on how far "
                        "into the current window we are."
                    ),
                },
                {"type": "h3", "text": "The Math"},
                {
                    "type": "para",
                    "text": (
                        "Let W = window size (e.g., 60 sec), <code>now</code> = current time, and "
                        "<code>elapsed = now mod W</code>. Define:"
                    ),
                },
                {
                    "type": "bullets",
                    "items": [
                        "<code>curr</code> = count in the current window [now − elapsed, now]",
                        "<code>prev</code> = count in the previous window [now − elapsed − W, now − elapsed]",
                        "<code>weight = (W − elapsed) / W</code> — how much of the previous window still overlaps a sliding W-second view",
                        "<strong>estimated_count = prev × weight + curr</strong>",
                        "Allow if <code>estimated_count &lt; limit</code>, then <code>INCR curr</code>",
                    ],
                },
                {"type": "h3", "text": "Pseudocode"},
                {
                    "type": "code",
                    "text": (
                        "# Sliding Window Counter\n"
                        "# Two keys per quota: rl:{id}:{window_start} stores a single integer count\n\n"
                        "def allow(id, limit, W, now):\n"
                        "    curr_window = (now // W) * W\n"
                        "    prev_window = curr_window - W\n"
                        "    elapsed     = now - curr_window\n"
                        "    weight      = (W - elapsed) / W            # fraction of prev still in view\n\n"
                        "    curr = redis.get(f'rl:{id}:{curr_window}') or 0\n"
                        "    prev = redis.get(f'rl:{id}:{prev_window}') or 0\n"
                        "    estimate = prev * weight + curr\n\n"
                        "    if estimate >= limit:\n"
                        "        return DENY, retry_after = W - elapsed\n\n"
                        "    redis.incr(f'rl:{id}:{curr_window}')\n"
                        "    redis.expire(f'rl:{id}:{curr_window}', 2 * W)   # auto-prune\n"
                        "    return ALLOW, remaining = limit - (estimate + 1)"
                    ),
                },
                {"type": "h3", "text": "Accuracy"},
                {
                    "type": "bullets",
                    "items": [
                        "Assumption: requests are <strong>uniformly distributed</strong> within the previous window",
                        "Empirically the error is ~<strong>0.003%</strong> under steady traffic and at most a few percent under bursts",
                        "Memory: <strong>2 integers per key</strong> (~32 B) regardless of QPS",
                        "Compare to Sliding Window Log: O(N) timestamps — KB-MB per heavy user",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Cloudflare scale",
                    "body": (
                        "Cloudflare published that Sliding Window Counter handled ~400 req/sec average "
                        "with ~0.003% error in their production fleet — small enough to ignore, with "
                        "memory bounded to two counters per key."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Distributed Implementation",
            "subtitle": "Three strategies for sharing counter state",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Once you have N stateless gateway pods, the counter must live somewhere they "
                        "can all see. Three patterns dominate, each with different consistency / "
                        "latency / cost trade-offs."
                    ),
                },
                {"type": "h3", "text": "Three Patterns"},
                {
                    "type": "table",
                    "headers": ["Pattern", "How it works", "Pros", "Cons"],
                    "rows": [
                        ["Centralized Redis",
                         "Every gateway calls the same Redis cluster on every request",
                         "Globally accurate; one source of truth; trivial to reason about",
                         "Adds ~0.3–0.7 ms RTT; Redis is on the critical path"],
                        ["Local + periodic sync",
                         "Each gateway holds its own bucket; pushes deltas to Redis every ~100 ms",
                         "Sub-100 µs decisions; survives Redis hiccups",
                         "Brief over-allow during sync gap; quotas exceeded by ~N pods × tiny amount"],
                        ["Approximate (sketch)",
                         "Count-Min Sketch / HyperLogLog at the edge for huge fan-in",
                         "Fixed memory regardless of cardinality; fast",
                         "Probabilistic; only suits coarse limits (e.g., DDoS detection)"],
                    ],
                },
                {"type": "h3", "text": "Recommendation"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Default:</strong> Centralized Redis with a Lua script for atomicity — accurate and simple",
                        "<strong>Hot keys / latency-sensitive paths:</strong> add a per-pod local bucket as L1 with periodic Redis reconcile",
                        "<strong>DDoS / volumetric:</strong> Count-Min Sketch in front of everything; only hits Redis if sketch crosses threshold",
                    ],
                },
                {"type": "h3", "text": "Atomic Check-and-Increment in Redis (Lua)"},
                {
                    "type": "code",
                    "text": (
                        "-- Token bucket as a Redis Lua script (atomic, ~50 µs round-trip)\n"
                        "-- KEYS[1] = bucket key   e.g. 'rl:user:42:GET:/v1/charges:tb'\n"
                        "-- ARGV[1] = capacity C\n"
                        "-- ARGV[2] = refill rate (tokens / second)\n"
                        "-- ARGV[3] = current timestamp (ms)\n"
                        "-- ARGV[4] = requested tokens (default 1)\n\n"
                        "local capacity   = tonumber(ARGV[1])\n"
                        "local refill     = tonumber(ARGV[2])\n"
                        "local now_ms     = tonumber(ARGV[3])\n"
                        "local requested  = tonumber(ARGV[4] or '1')\n\n"
                        "local state = redis.call('HMGET', KEYS[1], 'tokens', 'ts')\n"
                        "local tokens   = tonumber(state[1]) or capacity\n"
                        "local last_ms  = tonumber(state[2]) or now_ms\n\n"
                        "-- lazy refill\n"
                        "local elapsed_ms = math.max(0, now_ms - last_ms)\n"
                        "tokens = math.min(capacity, tokens + (elapsed_ms * refill / 1000))\n\n"
                        "local allowed = tokens >= requested\n"
                        "if allowed then tokens = tokens - requested end\n\n"
                        "redis.call('HMSET', KEYS[1], 'tokens', tokens, 'ts', now_ms)\n"
                        "-- Auto-expire when bucket would be full again (idle window)\n"
                        "redis.call('PEXPIRE', KEYS[1], math.ceil(capacity * 1000 / refill))\n\n"
                        "return { allowed and 1 or 0, tokens, capacity }"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Why Lua and not WATCH/MULTI",
                    "body": (
                        "EVAL runs as a single atomic blob inside Redis — no round-trip per op, no "
                        "optimistic-locking retry storms. At 10M rps, the cost of optimistic retries "
                        "would dwarf everything else."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Identity Hierarchy & Tiers",
            "subtitle": "Who is the caller, and what are they allowed?",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Each incoming request matches the tightest applicable bucket. We try identity "
                        "in order — API key first (most specific) down to IP (least specific) — and "
                        "rate-limit by all that apply. A single request may consume from multiple "
                        "buckets in parallel."
                    ),
                },
                {"type": "h3", "text": "Identity Hierarchy"},
                {
                    "type": "table",
                    "headers": ["Tier", "Resolved from", "Why we use it", "Caveat"],
                    "rows": [
                        ["API key",
                         "<code>Authorization: Bearer …</code>",
                         "Most specific; ties to billable account",
                         "Useless for unauthenticated traffic"],
                        ["user_id",
                         "JWT subject claim",
                         "Cross-device per-human limit",
                         "Requires login session"],
                        ["device fingerprint",
                         "Cookie / header / SDK",
                         "Catches anonymous client abuse",
                         "Spoofable; combine with IP"],
                        ["IP address",
                         "X-Forwarded-For (trusted hops only)",
                         "Last resort; covers fully anonymous",
                         "NAT shares an IP across many users"],
                    ],
                },
                {"type": "h3", "text": "Tiered Quotas"},
                {
                    "type": "table",
                    "headers": ["Plan", "Per-second", "Per-minute", "Per-day", "Burst"],
                    "rows": [
                        ["Anonymous (IP)", "10 rps",   "300 / min",   "10K / day",    "20"],
                        ["Free",           "20 rps",   "1K / min",    "100K / day",   "40"],
                        ["Premium",        "100 rps",  "5K / min",    "1M / day",     "200"],
                        ["Enterprise",     "1K rps",   "30K / min",   "10M / day",    "2K (custom)"],
                        ["Internal",       "—",        "—",            "—",            "Bypass list"],
                    ],
                },
                {"type": "h3", "text": "Resolution Algorithm"},
                {
                    "type": "numbered",
                    "items": [
                        "Extract identity (API key &gt; JWT &gt; device &gt; IP)",
                        "Look up tier in Config Service (cached locally for 5 sec)",
                        "Build keys: <code>rl:&lt;tier&gt;:&lt;id&gt;:&lt;endpoint&gt;:&lt;window&gt;</code>",
                        "EVAL Lua atomically against each window (per-second + per-minute + per-day)",
                        "DENY if <em>any</em> bucket says deny; ALLOW only if <em>all</em> say allow",
                        "Set headers: <code>X-RateLimit-Limit/Remaining/Reset</code>, <code>Retry-After</code>",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Don't trust raw IPs",
                    "body": (
                        "Always pull the IP from the trusted edge proxy (Cloudflare/ALB) — never the "
                        "client-supplied X-Forwarded-For. Otherwise a bad actor crafts the header and "
                        "drains other users' buckets."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Persistence Schema",
            "subtitle": "What we store and where",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Two stores: a <strong>Redis cluster</strong> for hot counter state, and a "
                        "<strong>Postgres rate_limits table</strong> as the durable mirror of "
                        "configuration and slow-changing per-account overrides."
                    ),
                },
                {"type": "h3", "text": "Redis Counter Layout"},
                {
                    "type": "code",
                    "text": (
                        "# Token bucket state — Redis hash\n"
                        "rl:tb:{tier}:{id}:{endpoint}\n"
                        "  HMSET\n"
                        "    tokens   <float>      # current tokens remaining\n"
                        "    ts       <ms>         # last refill timestamp\n"
                        "  PEXPIRE  <ms>           # auto-prune after a full idle window\n\n"
                        "# Sliding-window counter — two integers\n"
                        "rl:swc:{tier}:{id}:{endpoint}:{window_start}\n"
                        "  INCR ...                # one integer per fixed window\n"
                        "  EXPIRE 2*W              # keep current and previous only\n\n"
                        "# Hot-key shadow set for analytics\n"
                        "rl:topn   ZSET            # top abusers by deny count, last 60 sec"
                    ),
                },
                {"type": "h3", "text": "Postgres rate_limits Table"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE rate_limits (\n"
                        "  tier             VARCHAR(32) NOT NULL,           -- free/premium/enterprise\n"
                        "  endpoint_pattern VARCHAR(128) NOT NULL,          -- e.g. 'GET /v1/charges'\n"
                        "  window_seconds   INT NOT NULL,                   -- 1, 60, 86400\n"
                        "  max_requests    INT NOT NULL,                    -- limit per window\n"
                        "  burst_capacity   INT,                            -- token-bucket capacity\n"
                        "  refill_per_sec   NUMERIC(10,2),\n"
                        "  algorithm        VARCHAR(16) DEFAULT 'token_bucket',\n"
                        "  enabled          BOOLEAN DEFAULT TRUE,\n"
                        "  updated_at       TIMESTAMP DEFAULT NOW(),\n"
                        "  PRIMARY KEY (tier, endpoint_pattern, window_seconds)\n"
                        ");\n\n"
                        "CREATE TABLE rate_limit_overrides (\n"
                        "  account_id        BIGINT NOT NULL,\n"
                        "  endpoint_pattern  VARCHAR(128) NOT NULL,\n"
                        "  window_seconds    INT NOT NULL,\n"
                        "  max_requests      INT NOT NULL,\n"
                        "  burst_capacity    INT,\n"
                        "  expires_at        TIMESTAMP,                    -- temporary boost\n"
                        "  reason            VARCHAR(256),                 -- 'support ticket #1234'\n"
                        "  PRIMARY KEY (account_id, endpoint_pattern, window_seconds)\n"
                        ");\n\n"
                        "CREATE INDEX idx_overrides_acct ON rate_limit_overrides (account_id);"
                    ),
                },
                {"type": "h3", "text": "Config Propagation"},
                {
                    "type": "bullets",
                    "items": [
                        "Config Service polls Postgres every 1 sec; pushes deltas over gRPC stream",
                        "Gateways cache the active config in process memory; refresh on push or 5 sec poll",
                        "Schema versioning: every config has a <code>version</code>; gateways report which version they're running",
                        "Rollout safety: changes deploy as canary tier first, then graduated rollout",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Hot Keys & Sharding",
            "subtitle": "Surviving viral abusers and Black-Friday users",
            "blocks": [
                {"type": "h3", "text": "The Hot Key Problem"},
                {
                    "type": "para",
                    "text": (
                        "When one API key gets hammered (a misconfigured client, a viral integration), "
                        "all the load lands on one Redis shard. At 10M rps cluster-wide, even a tiny "
                        "fraction of a single user can saturate a single shard."
                    ),
                },
                {"type": "h3", "text": "Mitigations"},
                {
                    "type": "table",
                    "headers": ["Technique", "How it works", "When to use"],
                    "rows": [
                        ["Key salting",
                         "Add <code>:shard&lt;0..K&gt;</code> suffix; pick suffix at random; merge counters across",
                         "Single key sees &gt; 10K rps"],
                        ["Local L1 bucket",
                         "Per-pod token bucket; only call Redis on near-empty",
                         "Latency-sensitive paths"],
                        ["Probabilistic admission",
                         "Below a threshold, allow without checking Redis (sample 1 in N)",
                         "Below 10% of limit"],
                        ["Hot-key escape hatch",
                         "Detect via Redis cluster's hot-key tracker; promote to dedicated shard",
                         "Persistent abusive keys"],
                        ["Circuit breaker",
                         "If Redis p99 &gt; 5 ms, fall back to local-only for 30 sec",
                         "Redis under stress"],
                    ],
                },
                {"type": "h3", "text": "Shard Topology"},
                {
                    "type": "bullets",
                    "items": [
                        "Redis Cluster mode: <strong>16 primary shards</strong>, each with 1 replica",
                        "Hash slot = CRC16(key) % 16384; client library routes directly to the right node",
                        "Hot key salting: <code>rl:tb:premium:42:GET:/v1/charges:s7</code> for K=16 sub-buckets",
                        "Resharding: add nodes online; cluster reshuffles slots without downtime",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Don't oversalt",
                    "body": (
                        "Salting trades accuracy for spread. With K=16 sub-buckets the effective burst is "
                        "K× the configured one. Apply salting only to keys that actually hot-spot; default "
                        "to no salting."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Failure Modes",
            "subtitle": "What breaks and how we degrade",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["Redis primary down",
                         "Counter writes fail; deny path uncertain",
                         "Cluster gossip + client error rate",
                         "Auto-failover to replica (~5–15 sec); meanwhile fail-open for reads, fail-closed for writes"],
                        ["Whole Redis cluster outage",
                         "All buckets unavailable",
                         "Cluster client errors &gt; 50%",
                         "Circuit-breaker trips → local-only mode (per-pod best-effort) for 30 sec, then retry"],
                        ["Network partition gateway↔Redis",
                         "Some pods see Redis, others don't",
                         "Per-pod success rate divergence",
                         "Each pod independently decides fail-open/closed by policy table"],
                        ["Lua script bug",
                         "Allow-all or deny-all on one shard",
                         "Anomaly detection on allow ratio",
                         "Rollback config; scripts shipped through canary"],
                        ["Config Service down",
                         "No new quota changes propagate",
                         "Heartbeat from gateway fleet",
                         "Gateways keep last-known config in process memory"],
                        ["Hot key saturating one shard",
                         "p99 latency spike for that shard",
                         "Per-shard p99 + hot-key tracker",
                         "Auto-salt key; promote to dedicated shard; throttle abuser explicitly"],
                        ["Clock skew between pods",
                         "Sliding-window weights drift",
                         "NTP sync alarms",
                         "Use Redis time (TIME command) as canonical; reject if local-Redis Δ &gt; 500 ms"],
                        ["Gateway pod crash",
                         "Loses local L1 bucket state",
                         "Pod restart event",
                         "Stateless: counter lives in Redis; new pod re-derives L1 lazily"],
                    ],
                },
                {"type": "h3", "text": "Fail-Open vs Fail-Closed"},
                {
                    "type": "table",
                    "headers": ["Endpoint class", "Policy on Redis outage", "Why"],
                    "rows": [
                        ["Idempotent reads (<code>GET /v1/products</code>)",
                         "<strong>Fail-open</strong>",
                         "Better to serve a few extra reads than 5xx on outage"],
                        ["Login / auth attempts",
                         "<strong>Fail-closed</strong>",
                         "Brute-force prevention is the whole point"],
                        ["Write traffic / billing",
                         "<strong>Fail-closed</strong>",
                         "Loss of accuracy could cost real money"],
                        ["DDoS-edge limits",
                         "<strong>Fail-closed</strong>",
                         "If we can't measure, we must be conservative"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Fail-open isn't free",
                    "body": (
                        "Fail-open during a Redis outage means real abusers can briefly bypass the "
                        "limiter. Always pair fail-open with a per-pod fallback bucket — even an "
                        "approximate local limit is better than no limit."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Observability & Abuse Detection",
            "subtitle": "Watching the watcher",
            "blocks": [
                {"type": "h3", "text": "Core Metrics"},
                {
                    "type": "table",
                    "headers": ["Metric", "Why we care", "Alert threshold"],
                    "rows": [
                        ["allow_ratio",            "Is the limiter working at all?",          "Drops &lt; 99% suddenly → bug or DDoS"],
                        ["redis_p99_ms",           "Critical-path latency",                   "&gt; 1 ms p99 sustained"],
                        ["hot_key_qps",            "Spot abusers / misconfigured clients",    "Single key &gt; 10K rps for 60 sec"],
                        ["fail_open_seconds",      "Reliability of the limiter itself",       "&gt; 30 s/day"],
                        ["config_age_seconds",     "Stale config propagation",                "&gt; 30 s on any pod"],
                        ["cluster_top_denies",     "Top-N denied (key, endpoint) pairs",      "Track for security review"],
                    ],
                },
                {"type": "h3", "text": "Pipeline"},
                {
                    "type": "bullets",
                    "items": [
                        "Per-request: emit <code>{key, endpoint, allow, latency}</code> at 1% sample to Kafka",
                        "Stream processor (Flink / Kafka Streams): aggregate per-key per-minute denies",
                        "Top-N writer: HLL + count-min sketch for cardinality + top-K abusers",
                        "Anomaly detector: z-score on allow_ratio per endpoint; auto-page if &gt; 3σ",
                        "Long-term: roll up to Postgres for billing-style reporting (per account, per day)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Abuse loop",
                    "body": (
                        "A good limiter is also a good abuse detector: every <strong>429</strong> is a "
                        "data point. Top-N abusers feed back into automated bans, CAPTCHAs, or — in "
                        "extreme cases — Cloudflare WAF rules at the edge."
                    ),
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Design Trade-offs",
            "subtitle": "Why we made each choice",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Decision", "Choice", "Trade-off"],
                    "rows": [
                        ["Algorithm",
                         "Token bucket + sliding window counter",
                         "Smooth burst-friendly user limit; cheap accurate long-window. Pure Fixed Window is simpler but allows 2× edge bursts."],
                        ["Counter store",
                         "Centralized Redis cluster",
                         "Globally accurate at 10M rps. Local-only would be sub-100 µs but allow N× over-quota where N = pod count."],
                        ["Atomicity",
                         "Lua EVAL",
                         "One round-trip; atomic. WATCH/MULTI is portable but blows up with retries under contention."],
                        ["Failure policy",
                         "Mixed (open for reads, closed for writes)",
                         "Maximises availability without sacrificing money-paths. Always-closed sacrifices uptime; always-open sacrifices safety."],
                        ["Identity",
                         "API key &gt; user &gt; device &gt; IP",
                         "Most specific wins; covers anonymous + authenticated. IP-only is unfair to NAT users."],
                        ["Tiered quotas",
                         "Free / Premium / Enterprise + override table",
                         "Simple defaults plus surgical overrides. Per-account-only is hard to manage at scale."],
                        ["Distribution model",
                         "Centralized + L1 fallback",
                         "Accuracy by default; latency win on hot keys. Always-local would over-allow; always-central adds RTT."],
                        ["Sharding",
                         "Redis Cluster, hash by key",
                         "Even spread for most keys; salting for hot ones. Fixed sharding by user_id concentrates load on whales."],
                        ["Config propagation",
                         "Push via gRPC stream",
                         "&lt;5 s convergence. Pull every N sec is simpler but slower to react to incident-time changes."],
                        ["Observability",
                         "1% sample to Kafka",
                         "Cheap, statistically meaningful. Full sampling is 10M events/sec — too expensive."],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Latency budget",
                    "body": (
                        "Of our &lt; 1 ms target: ~0.4 ms Redis RTT (same-AZ), ~0.2 ms Lua execution, "
                        "~0.2 ms gateway overhead, ~0.2 ms slack. If the Redis hop costs more than 0.6 ms "
                        "p99, move to a closer cell or drop to L1-only for that endpoint."
                    ),
                },
            ],
        },
        # ---- 15 ------------------------------------------------------
        {
            "num": "15",
            "title": "Interview Playbook",
            "subtitle": "How to walk through this in 45 minutes",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Rate limiter is one of the most interview-friendly system-design questions: "
                        "the scope is tractable, the algorithms are crisp, and there's a clear "
                        "consistency-vs-latency trade-off to debate. Use the outline below to keep "
                        "the conversation tight."
                    ),
                },
                {"type": "h3", "text": "45-Minute Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Clarify (3 min):</strong> who's the caller, where does the limiter sit, hard or soft, single or multi-window",
                        "<strong>Capacity (4 min):</strong> 10M rps, 100M keys, ~10 GB Redis, p99 &lt; 1 ms",
                        "<strong>Algorithm choice (6 min):</strong> walk the table; pick token bucket + sliding window counter; defend why not Fixed/Log",
                        "<strong>High-level architecture (4 min):</strong> sidecar limiter, Redis cluster, config service, fail policy",
                        "<strong>Lua deep-dive (6 min):</strong> show the script; explain atomicity; why not WATCH/MULTI",
                        "<strong>Hot keys (4 min):</strong> salting, L1 buckets, dedicated shards",
                        "<strong>Failure modes (5 min):</strong> Redis outage, hot key, clock skew; per-endpoint open/closed policy",
                        "<strong>Identity & tiers (5 min):</strong> hierarchy, override table, header contract",
                        "<strong>Trade-offs & follow-ups (8 min):</strong> defend choices; entertain extensions (global, ML-based, GDPR)",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why not just count in memory per pod?</strong> A: With 200 pods, an effective limit of 1K rps becomes 200K rps; centralized counter is the only way to be globally accurate.",
                        "<strong>Q: How do you handle a Redis outage?</strong> A: Per-endpoint policy: read endpoints fail-open with a per-pod best-effort bucket; auth and write endpoints fail-closed.",
                        "<strong>Q: Token bucket vs leaky bucket?</strong> A: Token bucket allows bursts; leaky bucket smooths to a constant rate. For user-facing APIs, bursts are nice; for fragile downstreams, leaky.",
                        "<strong>Q: How do you stop a single key from saturating one shard?</strong> A: Salt the key into K sub-buckets, sum the counters atomically. Trade slight burst inflation for shard spread.",
                        "<strong>Q: What about clock skew?</strong> A: Use Redis TIME as the canonical clock inside Lua; reject the request if local-Redis skew &gt; 500 ms.",
                        "<strong>Q: Sliding window log accuracy is exact — why not?</strong> A: O(N) memory per key. At 100M keys with thousands of timestamps each, that's TBs of state. Counter approach is ~32 B/key.",
                        "<strong>Q: Global rate limit across regions?</strong> A: Either a single global Redis (high RTT) or eventual reconciliation across regional clusters (slight over-allow). Most use regional + slow merge.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "<strong>10M req/sec</strong> &nbsp;·&nbsp; "
                        "<strong>p99 &lt; 1 ms</strong> &nbsp;·&nbsp; "
                        "<strong>~100M keys</strong> &nbsp;·&nbsp; "
                        "<strong>~10 GB Redis</strong> (16 shards, ~625K ops/shard) &nbsp;·&nbsp; "
                        "<strong>~32 B / key</strong> for sliding window counter &nbsp;·&nbsp; "
                        "<strong>~50 µs</strong> Lua eval &nbsp;·&nbsp; "
                        "<strong>0.003%</strong> SWC error &nbsp;·&nbsp; "
                        "Free 20 rps / Premium 100 rps / Enterprise 1K rps &nbsp;·&nbsp; "
                        "fail-open reads / fail-closed writes."
                    ),
                },
            ],
        },
    ],
}
