"""Source for `12 - Distributed Cache.pdf`."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design a Distributed Cache",
    "subtitle": "Memcached / Redis Cluster / DynamoDB-style key-value store at scale",
    "read_time": "~ 45 minute read",
    "short_title": "Design a Distributed Cache",
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
                        "Design a <strong>distributed in-memory cache / key-value store</strong> "
                        "comparable to <strong>Memcached</strong>, <strong>Redis Cluster</strong>, "
                        "or a DynamoDB-style backend. The cache must absorb hot-read traffic for an "
                        "upstream database, scale horizontally to billions of keys, survive node "
                        "loss, and offer tunable consistency and durability."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Workload?", "1M ops/sec sustained, mix 80% reads / 20% writes"],
                        ["Working set?", "10 TB hot data; total may be much larger but we cache hot subset"],
                        ["Latency target?", "p99 &lt; 1 ms intra-DC, &lt; 10 ms cross-AZ"],
                        ["Durability?", "Optional: pure cache (lossy) OR primary KV store (persistent)"],
                        ["Consistency?", "Tunable: quorum reads/writes (R, W); strong-ish or fastest"],
                        ["Cross-region?", "Single region first; async replication for DR"],
                        ["Value sizes?", "Mostly &lt; 10 KB; reject &gt; 1 MB at the client"],
                        ["Failure model?", "Node, AZ, network partitions; cold restarts"],
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
                        ["GET / SET / DEL", "Primitive KV operations on string/binary values"],
                        ["TTL", "Per-key expiry; lazy + active eviction"],
                        ["Atomic ops", "INCR, CAS (compare-and-swap), SETNX (set-if-not-exists)"],
                        ["Replication", "RF=3 with sync or async per shard"],
                        ["Persistence", "Optional snapshots (RDB) or append-only log (AOF)"],
                        ["Eviction", "Configurable: LRU / LFU / TinyLFU / allkeys-random"],
                        ["Membership", "Add / remove nodes online; minimal key movement"],
                        ["Tunable consistency", "Per-call R and W quorum (R+W&gt;N for strong-ish)"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Throughput", "1M ops/sec sustained, 2M peak"],
                        ["Latency", "p50 &lt; 200 us, p99 &lt; 1 ms intra-DC"],
                        ["Cross-AZ p99", "&lt; 10 ms (quorum spans AZs)"],
                        ["Availability", "99.99% (52 min/yr); survive 1 AZ loss"],
                        ["Durability (KV mode)", "RPO &lt; 1 sec with AOF fsync=everysec"],
                        ["Working set", "10 TB usable in RAM"],
                        ["Scale-out", "Add 1 node → only ~1/N of keys move"],
                    ],
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "Sizing the cluster",
            "blocks": [
                {"type": "h3", "text": "Throughput Math"},
                {
                    "type": "bullets",
                    "items": [
                        "Total: <strong>1,000,000 ops/sec</strong> sustained",
                        "Reads: 80% × 1M = <strong>800K reads/sec</strong>",
                        "Writes: 20% × 1M = <strong>200K writes/sec</strong>",
                        "Per-node target: 25K ops/sec (conservative; modern Redis can hit 100K+ on a single core)",
                        "Nodes for throughput: 1M / 25K = <strong>~40 nodes</strong>; round up to <strong>50</strong> for headroom",
                    ],
                },
                {"type": "h3", "text": "Memory Math"},
                {
                    "type": "bullets",
                    "items": [
                        "Hot working set: <strong>10 TB</strong> usable",
                        "Per node RAM: <strong>256 GB</strong> (commodity 2-socket box)",
                        "Raw cluster RAM: 50 × 256 GB = <strong>12.8 TB</strong>",
                        "After RF=3 replication: 12.8 TB / 3 ≈ <strong>4.3 TB usable</strong> per copy if every node held a replica",
                        "We instead shard then replicate: <strong>10 TB usable working set</strong> with overhead headroom (slab fragmentation ~15%, replication metadata ~5%)",
                        "Per-key overhead: ~80 bytes (Redis dictEntry + robj + expiry); plan for it",
                    ],
                },
                {"type": "h3", "text": "Network Math"},
                {
                    "type": "bullets",
                    "items": [
                        "Avg value size: 1 KB; avg op payload incl. protocol: ~1.2 KB",
                        "1M ops/sec × 1.2 KB = <strong>1.2 GB/sec ≈ 9.6 Gb/sec</strong> aggregate",
                        "Per node: 9.6 / 50 ≈ <strong>200 Mb/sec</strong> — well within a 10 GbE NIC",
                        "Replication amplifies writes by RF: 200K writes × 1.2 KB × 2 followers = <strong>480 MB/sec replication traffic</strong>",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "<strong>1M ops/sec</strong> (80/20 R/W) &nbsp;·&nbsp; "
                        "<strong>50 nodes × 256 GB = 12.8 TB raw → 10 TB usable</strong> &nbsp;·&nbsp; "
                        "<strong>RF=3</strong>, R=2 W=2 quorum &nbsp;·&nbsp; "
                        "<strong>p99 &lt; 1 ms intra-DC</strong>, &lt; 10 ms cross-AZ &nbsp;·&nbsp; "
                        "consistent hashing with 100-200 vnodes per physical."
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level Architecture",
            "subtitle": "Smart client → ring → shards",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "A <strong>smart client</strong> embeds the consistent-hash ring and routes "
                        "directly to the owning shard. Each shard is a <strong>master + 2 replicas</strong> "
                        "across AZs. A separate <strong>persistence layer</strong> (S3 / disk) holds RDB "
                        "snapshots and AOF segments for durability. A <strong>config service</strong> "
                        "(ZooKeeper / etcd / Redis Sentinel) coordinates membership and failover."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Smart client hashes the key, picks the owning shard, and talks to master + replicas. Persistence is offloaded to S3.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Application"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        App  [label="App Server", fillcolor="#dbe6fb"];
        SC   [label="Smart Client\n(consistent hash ring,\nretry/hedge,\nclient-side cache)", fillcolor="#dbe6fb"];
    }
    subgraph cluster_cfg {
        label="Control Plane"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        ZK [label="ZooKeeper / etcd\n(ring, membership,\nleader election)", fillcolor="#fff2c9"];
    }
    subgraph cluster_shardA {
        label="Shard A"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        MA [label="Master A\n(AZ-1)", fillcolor="#cbeedf"];
        RA1[label="Replica A1\n(AZ-2)", fillcolor="#cbeedf"];
        RA2[label="Replica A2\n(AZ-3)", fillcolor="#cbeedf"];
    }
    subgraph cluster_shardB {
        label="Shard B"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        MB [label="Master B\n(AZ-2)", fillcolor="#cbeedf"];
        RB1[label="Replica B1\n(AZ-1)", fillcolor="#cbeedf"];
        RB2[label="Replica B2\n(AZ-3)", fillcolor="#cbeedf"];
    }
    subgraph cluster_pers {
        label="Persistence"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        S3   [label="S3 / Object Store\n(RDB snapshots,\nAOF archive)", fillcolor="#ead7fb"];
        Disk [label="Local NVMe\n(AOF tail)", fillcolor="#ead7fb"];
    }

    App -> SC [label="GET/SET k"];
    SC -> ZK  [label="ring lookup", style=dashed];
    SC -> MA  [label="GET/SET (R=2, W=2)"];
    SC -> RA1 [style=dashed];
    SC -> MB  [label="GET/SET"];
    SC -> RB1 [style=dashed];
    MA -> RA1 [label="async repl"];
    MA -> RA2 [label="async repl"];
    MB -> RB1 [label="async repl"];
    MB -> RB2 [label="async repl"];
    MA -> Disk [label="AOF fsync"];
    MB -> Disk [label="AOF fsync"];
    Disk -> S3 [label="archive"];
    MA -> S3   [label="RDB snapshot"];
    MB -> S3   [label="RDB snapshot"];
}
""",
                },
                {"type": "h3", "text": "Component Responsibilities"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Smart client:</strong> embeds ring, hashes keys, retries on timeout, hedges p99-tail reads, optional client-side cache for hot keys",
                        "<strong>Master:</strong> serves writes for its shard; ships changes to replicas",
                        "<strong>Replicas:</strong> serve quorum reads; promotable on master failure",
                        "<strong>Control plane:</strong> ZooKeeper / etcd holds the ring map, runs leader election, gates topology changes",
                        "<strong>Persistence:</strong> NVMe holds the AOF tail; S3 stores RDB snapshots and AOF archives for crash recovery",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Partitioning: Consistent Hashing",
            "subtitle": "Virtual nodes and the math",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Naive hash(key) % N <strong>breaks</strong> when N changes — almost every "
                        "key remaps. <strong>Consistent hashing</strong> places nodes on a ring "
                        "(0 .. 2^32-1); each key maps to the next node clockwise. Adding/removing "
                        "1 node moves only <strong>~1/N of keys</strong>."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Consistent-hash ring with 4 physical nodes; each placed at multiple positions (vnodes) for load balance.",
                    "dot": r"""
digraph Ring {
    layout=circo;
    bgcolor="white";
    node [shape=circle, style="filled", fontname="Helvetica", fontsize=9, fixedsize=true, width=0.7];
    edge [color="#586278", arrowhead=none];

    A1 [label="A v1", fillcolor="#cbeedf", color="#1f8359"];
    B1 [label="B v1", fillcolor="#dbe6fb", color="#2e57b8"];
    C1 [label="C v1", fillcolor="#fff2c9", color="#b8862e"];
    D1 [label="D v1", fillcolor="#ead7fb", color="#7a3eb8"];
    A2 [label="A v2", fillcolor="#cbeedf", color="#1f8359"];
    B2 [label="B v2", fillcolor="#dbe6fb", color="#2e57b8"];
    C2 [label="C v2", fillcolor="#fff2c9", color="#b8862e"];
    D2 [label="D v2", fillcolor="#ead7fb", color="#7a3eb8"];
    A3 [label="A v3", fillcolor="#cbeedf", color="#1f8359"];
    B3 [label="B v3", fillcolor="#dbe6fb", color="#2e57b8"];
    C3 [label="C v3", fillcolor="#fff2c9", color="#b8862e"];
    D3 [label="D v3", fillcolor="#ead7fb", color="#7a3eb8"];

    A1 -> B1 -> C1 -> D1 -> A2 -> B2 -> C2 -> D2 -> A3 -> B3 -> C3 -> D3 -> A1;
}
""",
                },
                {"type": "h3", "text": "Why Virtual Nodes (vnodes)"},
                {
                    "type": "bullets",
                    "items": [
                        "Without vnodes: 4 random ring positions can land unevenly — one node gets 50% of keys, another 5%",
                        "With <strong>100-200 vnodes per physical</strong>: law of large numbers smooths load to within ~5% of mean",
                        "Resharding: removing node X removes its 100-200 vnodes; their keys flow to neighbours, evenly",
                        "Heterogeneous nodes: a 2× larger box gets 2× the vnodes — capacity-weighted distribution",
                        "Tools: Ketama (libmemcached), Jump Hash (Google), Rendezvous (HRW) — same idea, different math",
                    ],
                },
                {"type": "h3", "text": "The 1/N Move-Set Math"},
                {
                    "type": "code",
                    "text": (
                        "# Adding one node to a cluster of N\n"
                        "# - new node owns 1/(N+1) of the ring\n"
                        "# - that share comes uniformly from the existing N nodes\n"
                        "# - each existing node loses 1/(N(N+1)) of its keys\n"
                        "# - total keys moved = 1/(N+1)  (~ 1/N for large N)\n\n"
                        "# Example: N = 50 → adding node 51\n"
                        "share_of_new_node = 1 / 51        # ≈ 1.96% of all keys\n"
                        "loss_per_existing = 1 / (50 * 51) # ≈ 0.039% per old node\n"
                        "# Compare with hash%N which would re-map ~98% of keys."
                    ),
                },
                {"type": "h3", "text": "Lookup Pseudocode"},
                {
                    "type": "code",
                    "text": (
                        "# Ring is a sorted list of (token, node_id) pairs\n"
                        "# 100-200 tokens per physical node\n"
                        "import bisect, hashlib\n\n"
                        "def hash64(key: bytes) -> int:\n"
                        "    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), 'big')\n\n"
                        "def lookup(key: bytes, ring_tokens, ring_nodes, N=3):\n"
                        "    h = hash64(key)\n"
                        "    idx = bisect.bisect_right(ring_tokens, h)\n"
                        "    seen, owners = set(), []\n"
                        "    while len(owners) < N:\n"
                        "        node = ring_nodes[idx % len(ring_tokens)]\n"
                        "        if node not in seen:           # skip extra vnodes of same physical\n"
                        "            seen.add(node)\n"
                        "            owners.append(node)\n"
                        "        idx += 1\n"
                        "    return owners                       # primary, replica1, replica2\n"
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Replication & Quorum",
            "subtitle": "RF=3 with tunable R and W",
            "blocks": [
                {"type": "h3", "text": "Replication Factor"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>RF = 3</strong>: every key lives on 1 master + 2 replicas, spread across AZs",
                        "Survives single-node loss <strong>and</strong> single-AZ loss with no data loss",
                        "Cost: 3× storage and 3× write bandwidth — usually worth it for a stateful tier",
                        "RF=2 saves money but loses both copies if both nodes go (e.g., correlated AZ failure)",
                    ],
                },
                {"type": "h3", "text": "Quorum Math (Dynamo Style)"},
                {
                    "type": "table",
                    "headers": ["Mode", "R", "W", "R+W&gt;N?", "Use Case"],
                    "rows": [
                        ["Strong-ish", "2", "2", "Yes (4&gt;3)", "Default; survives 1 replica loss with consistent reads"],
                        ["Read-heavy fast", "1", "3", "Yes (4&gt;3)", "Read latency critical; writes can be slower"],
                        ["Write-heavy fast", "3", "1", "Yes (4&gt;3)", "Write throughput first; reads pay quorum cost"],
                        ["Fastest (AP)", "1", "1", "No (2&lt;3)", "Pure cache; eventual; willing to read stale"],
                        ["Paranoid", "3", "3", "Yes (6&gt;3)", "Cannot lose any replica; both ops fail on 1 down"],
                    ],
                },
                {"type": "h3", "text": "Why R+W &gt; N Gives Strong-ish Reads"},
                {
                    "type": "bullets",
                    "items": [
                        "Write touches W nodes; read touches R nodes",
                        "If R + W &gt; N, the read set <strong>must intersect</strong> the write set",
                        "At least one node in the read quorum has the latest value",
                        "Use <strong>vector clocks or per-key version</strong> to pick the freshest copy",
                        "Caveat: not linearizable across operations — read-your-writes only if same client sticky-routes",
                    ],
                },
                {"type": "h3", "text": "Sync vs Async Replication"},
                {
                    "type": "table",
                    "headers": ["Mode", "Master Latency", "Durability", "Failure Risk"],
                    "rows": [
                        ["Async (default Redis)", "Lowest (~ master fsync)", "RPO &gt; 0 if master dies first", "Dataloss window: ms-seconds"],
                        ["Semi-sync (W=2)", "+1 cross-AZ RTT (~ 2-5 ms)", "Survives master loss", "One follower must ack"],
                        ["Sync (W=3)", "+max RTT to all replicas", "Strongest", "Slowest; one slow node blocks all writes"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Recommendation",
                    "body": (
                        "Default to <strong>RF=3, R=2, W=2</strong>. Tune per workload: cache-mostly "
                        "traffic can use R=1, W=1 for the lowest latency; financial/idempotency keys "
                        "use W=3 for absolute write durability."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Persistence",
            "subtitle": "RDB snapshots vs AOF append-only log",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "A pure cache (Memcached-style) <strong>has no persistence</strong> — it's "
                        "lossy by design. A Redis-style KV store offers two persistence modes which "
                        "can be combined for belt-and-braces durability."
                    ),
                },
                {"type": "h3", "text": "RDB (Snapshot)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>How:</strong> periodic fork() + serialize entire keyspace to a single binary file",
                        "<strong>Pros:</strong> compact, fast restart (load one file), great for backups → S3",
                        "<strong>Cons:</strong> RPO = snapshot interval (e.g., 5-15 min lost on crash)",
                        "<strong>Fork overhead:</strong> COW pages; large dataset + heavy writes can spike RAM 2× briefly",
                    ],
                },
                {"type": "h3", "text": "AOF (Append-Only File)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>How:</strong> log every write op to disk; replay on restart",
                        "<strong>fsync policies:</strong> always (per write), everysec (1-sec window), no (OS-buffered)",
                        "<strong>Pros:</strong> RPO ≈ 1 sec with everysec; replays exact ops; easy to reason about",
                        "<strong>Cons:</strong> file grows; periodic rewrite/compaction needed; slower restart than RDB",
                    ],
                },
                {"type": "h3", "text": "Comparison"},
                {
                    "type": "table",
                    "headers": ["Aspect", "RDB only", "AOF only", "RDB + AOF"],
                    "rows": [
                        ["RPO", "Minutes", "≈ 1 sec (everysec)", "≈ 1 sec"],
                        ["Restart speed", "Fast", "Slow (replay log)", "Fast (RDB) + AOF tail"],
                        ["Disk usage", "Low (compact)", "High (verbose log)", "Medium"],
                        ["Throughput cost", "Low (async fork)", "Medium (fsync)", "Medium"],
                        ["Forensics", "Snapshots only", "Op-level history", "Both"],
                    ],
                },
                {"type": "h3", "text": "Recommended Setup"},
                {
                    "type": "code",
                    "text": (
                        "# redis.conf — production durability\n"
                        "save 900 1            # RDB if 1 key changed in 15 min\n"
                        "save 300 10           # RDB if 10 keys changed in 5 min\n"
                        "save 60  10000        # RDB if 10000 keys changed in 1 min\n\n"
                        "appendonly yes\n"
                        "appendfsync everysec  # RPO ~ 1 second\n"
                        "auto-aof-rewrite-percentage 100\n"
                        "auto-aof-rewrite-min-size 64mb\n\n"
                        "# Operational: ship RDB to S3 every 15 min,\n"
                        "# AOF segments to S3 every 5 min (rolling)."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Trade-off: Durability vs Throughput",
                    "body": (
                        "<strong>fsync=always</strong> caps writes at the disk's IOPS (≈ 10K/sec on "
                        "SSD) — order of magnitude below in-memory rates. <strong>fsync=everysec</strong> "
                        "is the pragmatic sweet spot: RPO ~ 1 sec, near-RAM throughput. "
                        "<strong>fsync=no</strong> is fastest but you lose whatever the OS hadn't "
                        "flushed (seconds to minutes)."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Eviction Policies",
            "subtitle": "LRU, LFU, TinyLFU, allkeys-random",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "When a node hits <strong>maxmemory</strong>, the cache must evict something. "
                        "The policy determines hit rate under churn."
                    ),
                },
                {"type": "h3", "text": "Policies Compared"},
                {
                    "type": "table",
                    "headers": ["Policy", "What it Evicts", "Hit Rate", "Cost", "Best For"],
                    "rows": [
                        ["allkeys-random", "Any key uniformly", "Poor", "O(1)", "Uniform key access (rare)"],
                        ["allkeys-lru", "Least recently used", "Good", "O(1) approx", "General purpose; recency-skewed workloads"],
                        ["allkeys-lfu", "Least frequently used", "Better on hot/cold mix", "O(1) approx", "Long-tail with stable hot set"],
                        ["volatile-lru", "LRU among keys with TTL", "Targeted", "O(1) approx", "Mixed perm + cache keys"],
                        ["volatile-ttl", "Soonest to expire", "Predictable", "O(log n) heap", "TTL-driven workloads"],
                        ["TinyLFU (Caffeine)", "Frequency-sketched LRU", "Best in benchmarks", "Bloom-filter-ish", "Modern Java caches; hot-key sparse"],
                    ],
                },
                {"type": "h3", "text": "Why LRU Is the Default"},
                {
                    "type": "bullets",
                    "items": [
                        "Approximates 'likely to be reused soon' from temporal locality",
                        "Redis uses <strong>sampled LRU</strong>: pick K random keys, evict the oldest — O(1), tunable K",
                        "Fails on a one-shot scan (cache pollution): the scan promotes itself, evicts hot data",
                    ],
                },
                {"type": "h3", "text": "LFU and TinyLFU"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>LFU:</strong> evict the key accessed least often. Resists scan pollution. Risk: stale 'forever popular' keys never age out",
                        "<strong>Redis LFU:</strong> tracks an 8-bit logarithmic counter per key; counter <em>decays</em> over time so old popularity fades",
                        "<strong>TinyLFU (Caffeine library):</strong> a count-min-sketch frequency filter <em>in front of</em> an LRU window. New entries must beat the LFU score of the candidate victim",
                        "TinyLFU uses ~ <strong>1 byte / entry</strong> of metadata; gets ~95% of optimal hit rate on real traces",
                    ],
                },
                {"type": "h3", "text": "Sampled LFU Promotion (Pseudocode)"},
                {
                    "type": "code",
                    "text": (
                        "# Redis-style approximate LFU on access\n"
                        "# 8-bit log counter; saturates at 255\n"
                        "LFU_LOG_FACTOR = 10  # smaller -> faster ramp-up\n"
                        "LFU_DECAY_MIN  = 1   # decay 1 unit per minute idle\n\n"
                        "def on_access(entry, now_min):\n"
                        "    # decay first\n"
                        "    elapsed = now_min - entry.last_decay_min\n"
                        "    entry.counter = max(0, entry.counter - elapsed * LFU_DECAY_MIN)\n"
                        "    entry.last_decay_min = now_min\n\n"
                        "    # probabilistic increment (saturating log curve)\n"
                        "    if entry.counter < 255:\n"
                        "        baseval = entry.counter\n"
                        "        p = 1.0 / (baseval * LFU_LOG_FACTOR + 1)\n"
                        "        if random.random() < p:\n"
                        "            entry.counter += 1\n\n"
                        "def evict_one(sampled):  # sampled = K random entries\n"
                        "    return min(sampled, key=lambda e: e.counter)"
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Hot Key Problem",
            "subtitle": "When one key gets 10% of all traffic",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "A celebrity's profile, a product on the homepage, or a flash-sale SKU can "
                        "suddenly take <strong>10-50% of all reads</strong>. That key lives on one "
                        "shard — that shard melts. Symptoms: a single CPU pinned at 100%, p99 spikes, "
                        "queue depth grows."
                    ),
                },
                {"type": "h3", "text": "Mitigations"},
                {
                    "type": "table",
                    "headers": ["Strategy", "How", "Trade-off"],
                    "rows": [
                        ["Read replicas", "Route reads of hot key to replicas (R=1)",
                         "Eventual consistency on that key"],
                        ["Hot-key replication", "Copy hot key to extra shards; client picks at random",
                         "Writes must fan out; staleness window"],
                        ["Client-side cache", "Cache hot keys in app process for ~1 sec",
                         "Staleness; needs invalidation channel"],
                        ["Request coalescing", "Single in-flight fetch per key per node",
                         "Adds a wait; reduces backend QPS dramatically"],
                        ["Tiered cache (L1+L2)", "Per-app L1 + cluster L2",
                         "Memory cost; 2-level invalidation"],
                        ["Sharding the value", "Split list/counter into N sub-keys",
                         "App must aggregate on read"],
                    ],
                },
                {"type": "h3", "text": "Detection"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Server-side:</strong> per-key counter sketches (count-min-sketch over 1-sec windows)",
                        "<strong>Client-side:</strong> sample 1% of requests, bucket by key prefix, alert on outliers",
                        "<strong>Heuristic:</strong> any key &gt; 1% of node QPS is suspect; &gt; 5% is on fire",
                    ],
                },
                {"type": "h3", "text": "Hot-Key Replication Pattern"},
                {
                    "type": "code",
                    "text": (
                        "# Promote a hot key to N shadow shards.\n"
                        "# Client picks 1 of N at random on read; writes fan out to all N.\n\n"
                        "HOT_FANOUT = 4  # 4 shadow copies → ~25% load each\n\n"
                        "def get_hot(key):\n"
                        "    if key in HOT_SET:\n"
                        "        suffix = random.randint(0, HOT_FANOUT - 1)\n"
                        "        return cache.get(f'{key}#hot{suffix}')\n"
                        "    return cache.get(key)\n\n"
                        "def set_hot(key, val):\n"
                        "    if key in HOT_SET:\n"
                        "        for i in range(HOT_FANOUT):\n"
                        "            cache.set(f'{key}#hot{i}', val)\n"
                        "    else:\n"
                        "        cache.set(key, val)"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Client-side caching is the real win",
                    "body": (
                        "For read-mostly hot keys, a 1-second client-side cache in front of Redis "
                        "collapses 100K reads/sec from one app instance into 1 read/sec to the "
                        "cluster. Redis 6+ supports server-assisted invalidation (CLIENT TRACKING) "
                        "so the client knows when its local copy goes stale."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Cache Stampede & Thundering Herd",
            "subtitle": "When TTL expires for a hot key",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "A hot key serving 50K reads/sec expires. <strong>50,000 clients</strong> "
                        "miss in the same millisecond and all stampede the database. The DB melts; "
                        "the cache stays cold. This is the <strong>thundering herd / cache stampede</strong>."
                    ),
                },
                {"type": "h3", "text": "Three Defences"},
                {
                    "type": "table",
                    "headers": ["Technique", "How", "Best For"],
                    "rows": [
                        ["Lock-and-fill (singleflight)",
                         "First miss takes a Redis SETNX lock; others wait or serve stale",
                         "Single-host or coordinated workers"],
                        ["Probabilistic early refresh (XFetch)",
                         "Refresh probabilistically before TTL based on remaining time and recompute cost",
                         "Best general-purpose; no coordination"],
                        ["Request collapsing",
                         "App-server level: combine concurrent identical requests into 1 backend call",
                         "Per-process; complements the others"],
                    ],
                },
                {"type": "h3", "text": "XFetch (Vattani et al., 2015)"},
                {
                    "type": "para",
                    "text": (
                        "Each cached entry stores a <strong>delta</strong> (cost to recompute, in "
                        "seconds) and an <strong>expiry timestamp</strong>. On every read, decide "
                        "probabilistically whether to <em>also</em> kick off a background refresh. "
                        "The closer to expiry, the higher the probability."
                    ),
                },
                {
                    "type": "code",
                    "text": (
                        "# XFetch probabilistic early refresh\n"
                        "# Stored with each value: delta (recompute cost), expiry\n"
                        "import math, random, time\n\n"
                        "BETA = 1.0  # higher beta = refresh earlier (more aggressive)\n\n"
                        "def get_with_xfetch(key, recompute):\n"
                        "    val, delta, expiry = cache.get_with_meta(key)\n"
                        "    now = time.time()\n"
                        "    if val is None or now >= expiry:\n"
                        "        return _refill(key, recompute)\n"
                        "    # probability rises as we approach expiry\n"
                        "    if now - delta * BETA * math.log(random.random()) >= expiry:\n"
                        "        # async background refresh; current request still serves cached val\n"
                        "        spawn(lambda: _refill(key, recompute))\n"
                        "    return val\n\n"
                        "def _refill(key, recompute):\n"
                        "    # Lock so only one filler runs (singleflight)\n"
                        "    if cache.set_nx(f'lock:{key}', '1', ex=30):\n"
                        "        try:\n"
                        "            t0 = time.time()\n"
                        "            v = recompute()\n"
                        "            delta = time.time() - t0\n"
                        "            cache.set_with_meta(key, v, delta, ttl=300)\n"
                        "            return v\n"
                        "        finally:\n"
                        "            cache.delete(f'lock:{key}')\n"
                        "    # someone else is filling; serve stale or wait briefly\n"
                        "    return cache.get(key)"
                    ),
                },
                {"type": "h3", "text": "Lock-and-Fill (Singleflight) Variants"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Strict lock:</strong> losers block on a short poll → low DB load, higher tail latency",
                        "<strong>Stale-while-revalidate:</strong> losers serve the previous (just-expired) value while the winner refills — best UX",
                        "<strong>Negative caching:</strong> cache 'not found' for a few seconds to absorb miss storms on garbage keys",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Data Model & API",
            "subtitle": "Redis ops vs DynamoDB-style schema",
            "blocks": [
                {"type": "h3", "text": "Redis Command Sequence"},
                {
                    "type": "code",
                    "text": (
                        "# Session cache: fast GET / SET with TTL\n"
                        "SET sess:u123 '{\"uid\":123,\"role\":\"admin\"}' EX 3600\n"
                        "GET sess:u123\n"
                        "DEL sess:u123\n\n"
                        "# Atomic counter — no race even at 1M ops/sec\n"
                        "INCR  page_views:home\n"
                        "INCRBY balance:u123 -50\n\n"
                        "# Compare-and-swap with WATCH/MULTI/EXEC (optimistic)\n"
                        "WATCH inventory:sku-42\n"
                        "MULTI\n"
                        "  DECR inventory:sku-42\n"
                        "  ZADD orders 1714000000 order:9001\n"
                        "EXEC                          # nil if WATCH key changed → retry\n\n"
                        "# Hot-key fan-out: write to N shards, read 1 at random\n"
                        "MSET hot:product:42#0 v hot:product:42#1 v hot:product:42#2 v hot:product:42#3 v\n"
                        "GET hot:product:42#${random 0..3}\n\n"
                        "# Stream-processing primitives\n"
                        "XADD events * type click user 123\n"
                        "XREAD COUNT 100 STREAMS events $"
                    ),
                },
                {"type": "h3", "text": "DynamoDB-Style Table Definition"},
                {
                    "type": "code",
                    "text": (
                        "-- Conceptual SQL of a DynamoDB-like KV table\n"
                        "CREATE TABLE kv_items (\n"
                        "  partition_key   VARBINARY(256) NOT NULL,  -- hash → shard\n"
                        "  sort_key        VARBINARY(256) NOT NULL,  -- range within partition\n"
                        "  value           VARBINARY(400000),        -- 400 KB max per item\n"
                        "  version         BIGINT       NOT NULL,    -- for CAS / vector clocks\n"
                        "  ttl_epoch       BIGINT,                   -- background TTL sweeper\n"
                        "  updated_at      TIMESTAMP    NOT NULL,\n"
                        "  PRIMARY KEY (partition_key, sort_key)\n"
                        ");\n\n"
                        "-- Conditional write (CAS): only succeed if version matches\n"
                        "UPDATE kv_items\n"
                        "   SET value = ?, version = version + 1, updated_at = NOW()\n"
                        " WHERE partition_key = ? AND sort_key = ? AND version = ?;\n\n"
                        "-- TTL sweeper (lazy + background)\n"
                        "DELETE FROM kv_items WHERE ttl_epoch < UNIX_TIMESTAMP() LIMIT 10000;"
                    ),
                },
                {"type": "h3", "text": "Memcached vs Redis vs DynamoDB"},
                {
                    "type": "table",
                    "headers": ["Aspect", "Memcached", "Redis Cluster", "DynamoDB"],
                    "rows": [
                        ["Data model", "Opaque blob", "Strings, lists, hashes, sets, sorted sets, streams",
                         "Items with attributes; partition + sort key"],
                        ["Persistence", "None (pure cache)", "RDB / AOF", "Always durable (SSD + RF=3)"],
                        ["Consistency", "Per-node only", "Async repl by default", "Tunable: eventual or strongly consistent reads"],
                        ["Sharding", "Client-side (consistent hash)", "Built-in slots (16384 hash slots)",
                         "Managed; auto-split partitions"],
                        ["Eviction", "LRU only", "8 policies incl. LRU/LFU", "TTL-based; no LRU"],
                        ["Threading", "Multi-threaded", "Single-threaded per shard", "Managed"],
                        ["Best for", "Simple LRU object cache", "Rich ops, atomic primitives, queues",
                         "Durable KV at any scale; pay-per-use"],
                    ],
                },
                {"type": "h3", "text": "Consistency Models Compared"},
                {
                    "type": "table",
                    "headers": ["Model", "Guarantee", "Example"],
                    "rows": [
                        ["Linearizable", "All ops appear in real-time order; expensive",
                         "Spanner, etcd Raft writes"],
                        ["Sequential", "Single global order, may lag real time",
                         "Multi-Paxos read from leader"],
                        ["Quorum (R+W&gt;N)", "Read sees latest acked write; not linearizable",
                         "Dynamo, Cassandra, our default"],
                        ["Read-your-writes", "Client sees own writes; sticky session",
                         "App-level; client tracks last-seen version"],
                        ["Eventual", "Replicas converge eventually; reads may be stale",
                         "Pure cache (R=1, W=1)"],
                    ],
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Failure Modes & Recovery",
            "subtitle": "What can go wrong (and what we do)",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["Master node down",
                         "Writes fail for that shard until promotion",
                         "Heartbeat miss (3 consecutive)",
                         "Sentinel/etcd promotes a replica; client reroutes via gossip"],
                        ["Replica node down",
                         "Reduced read capacity; possible quorum miss",
                         "Health check + lag metric",
                         "Re-replicate to spare; bootstrap from RDB + AOF tail"],
                        ["Whole AZ down",
                         "1/3 of every shard offline",
                         "Cloud provider event + multi-target ping",
                         "RF=3 across 3 AZs ensures W=2 still works; degrade to R=2 reads"],
                        ["Network partition (split-brain)",
                         "Two nodes both think they're master",
                         "Quorum loss in control plane",
                         "Fence the loser via STONITH; client rejects writes without lease"],
                        ["Hot shard / hot key",
                         "Single CPU pinned; cluster looks idle",
                         "Per-shard QPS skew &gt; 5×",
                         "Hot-key replication, client-cache, request coalescing (§09-10)"],
                        ["GC stall / slow swap",
                         "p99 latency multi-second; timeouts",
                         "p99 vs p50 ratio &gt; 50",
                         "Disable swap; pin CPU/NUMA; alert on long GC; jemalloc"],
                        ["Cold restart after crash",
                         "Empty cache → DB stampede",
                         "Hit rate drops to ~0",
                         "Restart from RDB; warm-up replay; rate-limit upstream"],
                        ["Disk full (AOF growth)",
                         "Master refuses writes",
                         "Disk-usage alert at 80%",
                         "Auto-trigger AOF rewrite; ship segment to S3; expand volume"],
                    ],
                },
                {"type": "h3", "text": "Failover Sequence"},
                {
                    "type": "numbered",
                    "items": [
                        "Sentinel/etcd loses heartbeat from master M for &gt; 3× interval (e.g., 9 sec)",
                        "Quorum of sentinels agree M is down (avoids false positives from network blips)",
                        "Pick replica with the highest replication offset (most up-to-date)",
                        "Promote: <code>SLAVEOF NO ONE</code>; reconfigure other replicas to follow it",
                        "Update ring map in etcd; gossip new master to clients",
                        "Smart clients receive the new map (push or next request) and reroute",
                        "Old master, on rejoin, becomes a replica of the new master after sync",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Split-Brain Is the Real Killer",
                    "body": (
                        "Two masters writing the same key = silent data divergence. Always use a "
                        "<strong>quorum-based control plane</strong> (etcd / ZooKeeper / Sentinel "
                        "with majority) so only one side of a partition can elect a master. The "
                        "minority side returns errors — better than corrupting state."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Design Trade-offs",
            "subtitle": "Decisions and rationale",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Decision", "Choice", "Trade-off"],
                    "rows": [
                        ["CAP positioning",
                         "AP with quorum (favor availability)",
                         "Brief staleness on partition; we lose linearizability but stay up. CP would refuse writes during partition."],
                        ["Replication factor",
                         "RF = 3",
                         "3× cost; survives single-AZ loss. RF = 2 saves 33% but two correlated failures = data loss."],
                        ["Quorum",
                         "R = 2, W = 2",
                         "Strong-ish reads, ~5 ms cross-AZ latency. R=1/W=1 halves latency but reads can be stale."],
                        ["Persistence",
                         "RDB + AOF everysec",
                         "RPO ≈ 1 sec; ~10% throughput cost vs no-persistence. fsync=always is safer but 10× slower."],
                        ["In-memory vs SSD",
                         "RAM-only with cold tier in S3",
                         "$$$/GB high; sub-ms p99. SSD-backed (Aerospike) is 5× cheaper but 5-10× higher p99."],
                        ["Eviction policy",
                         "allkeys-lfu",
                         "Resists scan pollution; keeps hot keys hot. Pure LRU is simpler but vulnerable to one-shot scans."],
                        ["Topology mgmt",
                         "Smart client + ring in etcd",
                         "Client complexity; lowest hop count. Proxy layer (twemproxy) is simpler but adds 1 RTT and a SPOF."],
                        ["Hot key strategy",
                         "Detect + fan-out + client-cache",
                         "Code complexity; saves the cluster. Doing nothing means one shard melts under any virality."],
                        ["Hash function",
                         "Blake2b (64-bit truncated)",
                         "Fast (~1 GB/s), uniform. CRC32 is faster but more skew; SHA1 is overkill."],
                        ["Vnode count",
                         "150 per physical",
                         "Smooths load to ±5%; ~7.5K ring entries for 50 nodes (cheap to scan/serialize)."],
                    ],
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Operations & Observability",
            "subtitle": "Running it in production",
            "blocks": [
                {"type": "h3", "text": "Key SLIs to Monitor"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Hit rate</strong> per node and global: alert if drops &gt; 5% in 1 min",
                        "<strong>Latency:</strong> p50, p99, p999 — separately per shard (catches hot shards)",
                        "<strong>Memory:</strong> used / maxmemory ratio per node; evicted_keys/sec",
                        "<strong>Replication lag:</strong> master_repl_offset - replica_offset (bytes)",
                        "<strong>Connection count:</strong> too many clients → file-descriptor exhaustion",
                        "<strong>Slow-log:</strong> any command &gt; 10 ms in a sub-ms cache is a red flag",
                        "<strong>Per-key QPS skew:</strong> top-K keys via count-min-sketch sampling",
                    ],
                },
                {"type": "h3", "text": "Capacity Planning"},
                {
                    "type": "bullets",
                    "items": [
                        "Trigger scale-out at <strong>70% memory</strong> or <strong>60% CPU</strong> per node",
                        "Adding a node = ~1/N rebalance; throttle migration to 50 MB/s/node to protect QPS",
                        "Plan for 2× peak headroom — viral events spike 5-10× normal",
                        "Pre-create shard slots at cluster init (e.g., 1024 logical shards on 50 physical nodes) to make later splits cheap",
                    ],
                },
                {"type": "h3", "text": "Rolling Upgrades"},
                {
                    "type": "numbered",
                    "items": [
                        "Drain replica B1 (mark not-ready in etcd; clients stop sending it reads)",
                        "Stop replica; upgrade binary; restart; let it catch up via AOF tail + replication",
                        "Verify replication lag &lt; 1 s and hit rate stable",
                        "Repeat for replica B2",
                        "<strong>Failover:</strong> demote master B; promote B1; upgrade old master B; rejoin as replica",
                        "Move on to shard A — never upgrade more than 1 replica per shard at once",
                    ],
                },
                {"type": "h3", "text": "Backup & Restore"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>RDB snapshot → S3</strong> every 15 min; 30-day retention",
                        "<strong>AOF segments → S3</strong> every 5 min; rolling",
                        "Restore drill quarterly: spin up cluster from S3, verify hit rate, kill it",
                        "Cross-region async replication for DR (+ 100-500 ms lag)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "The 4 Golden Signals (Cache Edition)",
                    "body": (
                        "<strong>Latency</strong> (p99 by shard) &nbsp;·&nbsp; "
                        "<strong>Traffic</strong> (ops/sec, R:W ratio) &nbsp;·&nbsp; "
                        "<strong>Errors</strong> (timeouts, MOVED redirects, OOM evictions) &nbsp;·&nbsp; "
                        "<strong>Saturation</strong> (memory %, CPU %, replication lag). "
                        "Dashboard them per-shard, not just cluster-wide — averages hide hot shards."
                    ),
                },
            ],
        },
        # ---- 15 ------------------------------------------------------
        {
            "num": "15",
            "title": "Interview Playbook",
            "subtitle": "How to present this",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "A 45-minute interview on distributed cache design typically rewards "
                        "depth on <strong>partitioning math</strong>, <strong>quorum logic</strong>, "
                        "<strong>hot-key handling</strong>, and <strong>stampede prevention</strong>. "
                        "Drive the conversation through these four pillars."
                    ),
                },
                {"type": "h3", "text": "45-Minute Interview Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Clarify (3 min):</strong> ops/sec, working set, latency, durability requirements",
                        "<strong>Capacity (5 min):</strong> 1M ops/sec, 10 TB → 50 nodes × 256 GB, RF=3",
                        "<strong>Partitioning (7 min):</strong> consistent hashing with vnodes; show 1/N math",
                        "<strong>Replication & quorum (6 min):</strong> RF=3, R=2 W=2; why R+W&gt;N",
                        "<strong>Persistence (4 min):</strong> RDB vs AOF; everysec sweet spot",
                        "<strong>Eviction (3 min):</strong> LRU vs LFU vs TinyLFU",
                        "<strong>Hot keys & stampede (8 min):</strong> detection, fan-out, XFetch, singleflight",
                        "<strong>Failures (5 min):</strong> AZ loss, split-brain, hot shard, cold restart",
                        "<strong>Wrap (4 min):</strong> trade-offs explicit; what you'd do differently with more time",
                    ],
                },
                {"type": "h3", "text": "Common Follow-Ups"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why not hash%N?</strong> A: ~98% of keys remap when N changes; consistent hashing limits movement to ~1/N.",
                        "<strong>Q: How many vnodes per node?</strong> A: 100-200. Below 50, load is uneven; above 500, ring metadata overhead grows without benefit.",
                        "<strong>Q: Strong consistency?</strong> A: R+W&gt;N gives strong-ish quorum reads; for true linearizability use a Raft-based KV (etcd) or Spanner-style — at cost of latency.",
                        "<strong>Q: Cache vs DB consistency?</strong> A: Cache-aside on read; on write, update DB then DEL cache (not SET — avoids stale-write race). Or write-through if app can tolerate the cost.",
                        "<strong>Q: Defend against thundering herd?</strong> A: Three layers: XFetch probabilistic refresh, lock-and-fill singleflight, request collapsing in app server.",
                        "<strong>Q: How do you find a hot key?</strong> A: Per-shard count-min-sketch over a 1-sec window; alert if any key exceeds 5% of node QPS.",
                        "<strong>Q: What if a master and one replica die together?</strong> A: With RF=3 across 3 AZs, surviving replica becomes master; quorum drops to W=1 until rebuild — accept the risk window.",
                    ],
                },
                {"type": "h3", "text": "Talking Points That Score"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>'1/N keys move'</strong> — proves you understand consistent hashing",
                        "<strong>'R + W &gt; N'</strong> — quorum reasoning in one inequality",
                        "<strong>'fsync=everysec is the sweet spot'</strong> — durability vs throughput trade",
                        "<strong>'TinyLFU beats LRU on real traces'</strong> — modern eviction awareness",
                        "<strong>'XFetch + singleflight'</strong> — stampede defence in depth",
                        "<strong>'AZ-aware replica placement'</strong> — survives correlated failure",
                        "<strong>'Smart client cuts a hop'</strong> — vs proxy-based architectures",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "<strong>1M ops/sec</strong> @ 80/20 R/W &nbsp;·&nbsp; "
                        "<strong>50 nodes × 256 GB = 12.8 TB raw → 10 TB usable</strong> &nbsp;·&nbsp; "
                        "<strong>RF=3, R=2, W=2</strong> (R+W &gt; N) &nbsp;·&nbsp; "
                        "<strong>p99 &lt; 1 ms intra-DC</strong>, &lt; 10 ms cross-AZ &nbsp;·&nbsp; "
                        "<strong>150 vnodes/node</strong> &nbsp;·&nbsp; "
                        "adding 1 node moves <strong>1/(N+1) ≈ 2%</strong> of keys &nbsp;·&nbsp; "
                        "<strong>fsync=everysec, RPO ≈ 1 s</strong> &nbsp;·&nbsp; "
                        "TinyLFU ~ <strong>1 byte/entry</strong>, ~95% of optimal hit rate."
                    ),
                },
            ],
        },
    ],
}
