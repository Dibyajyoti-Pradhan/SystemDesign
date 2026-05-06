"""Source for `13 - Message Queue.pdf` — Distributed Message Queue (Kafka-style)."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design a Distributed Message Queue",
    "subtitle": "Kafka-style partitioned log with brief comparison to RabbitMQ, SQS, and Pub/Sub",
    "read_time": "~ 45 minute read",
    "short_title": "Design a Distributed Message Queue",
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
                        "Design a distributed message queue like <strong>Apache Kafka</strong>. "
                        "The system must accept events from many producers, persist them durably, "
                        "and deliver them to many consumers in order, at high throughput, with "
                        "tunable delivery semantics — all while surviving broker failures and "
                        "network partitions."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Peak throughput?", "10M messages/sec across cluster (1M sustained)"],
                        ["Avg message size?", "1 KB (range: 100 B to 1 MB)"],
                        ["Retention?", "7 days default; configurable up to 30 days"],
                        ["Ordering?", "Per-partition (per-key) ordering, not global"],
                        ["Delivery semantics?", "Configurable: at-most, at-least, exactly-once"],
                        ["Multi-tenant?", "Yes; quotas per producer / consumer group"],
                        ["Geo-replicated?", "Single region first; cross-region later (MirrorMaker)"],
                        ["Use-cases?", "Event streaming, log aggregation, CDC, async services"],
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
                        ["Publish", "Producer sends record to topic; gets ack with offset"],
                        ["Subscribe", "Consumer joins group; auto-rebalances partitions"],
                        ["Retention", "Time-based (7d) or size-based (e.g. 1 TB/partition)"],
                        ["Replay", "Consumers can seek to any offset within retention"],
                        ["Ordering", "FIFO within a partition (key-based hashing)"],
                        ["Compaction", "Optional log compaction by key (latest value wins)"],
                        ["ACL / quotas", "Per-topic ACLs; per-client byte/sec quotas"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Throughput", "10M msg/sec peak; 1M sustained (cluster-wide)"],
                        ["Latency", "p50 &lt;10 ms publish; p99 &lt;100 ms end-to-end"],
                        ["Durability", "No data loss with acks=all + min.insync=2"],
                        ["Availability", "99.99% (multi-AZ); cluster survives 1 broker loss"],
                        ["Retention", "7 days default → ~600 TB/cluster"],
                        ["Scalability", "Add brokers / partitions linearly"],
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
                {"type": "h3", "text": "Throughput"},
                {
                    "type": "bullets",
                    "items": [
                        "Peak ingest: <strong>10M msg/sec</strong> × 1 KB = <strong>10 GB/sec</strong> raw",
                        "Sustained ingest: <strong>1M msg/sec</strong> × 1 KB = <strong>1 GB/sec</strong>",
                        "Read amplification: typically 3 consumer groups × producers ≈ <strong>3 GB/sec out</strong>",
                        "Replication amplification: factor 3 (1 leader + 2 followers) ⇒ inter-broker traffic ≈ 2 GB/sec",
                    ],
                },
                {"type": "h3", "text": "Storage (7-day retention)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>If 10M/sec retained 7 days:</strong> 10 GB/s × 86,400 × 7 ≈ <strong>6 PB</strong> raw, ×3 RF = <strong>~18 PB</strong> on disk",
                        "Annualized at peak: 10 GB/s × 365 × 86,400 ≈ <strong>~315 PB/yr</strong> raw (~80 PB/yr usable after 4× index/overhead at 7-day rolling)",
                        "<strong>Realistic (1M sustained):</strong> 1 GB/s × 86,400 × 7 ≈ <strong>600 TB</strong> raw, ×3 RF = <strong>~1.8 PB</strong>",
                        "Per broker (30 brokers): ~60 TB/broker — fits 12× 8 TB HDD JBOD comfortably",
                    ],
                },
                {"type": "h3", "text": "Partitioning"},
                {
                    "type": "bullets",
                    "items": [
                        "Per-partition write throughput ceiling: ~<strong>50 MB/s</strong> (sequential disk + replication)",
                        "Sustained 1 GB/s ÷ 50 MB/s ≈ <strong>20 partitions minimum</strong>; pick <strong>200</strong> for headroom + parallelism",
                        "Peak 10 GB/s ÷ 50 MB/s = <strong>~200 partitions</strong> minimum at peak; recommend <strong>500–1000</strong>",
                        "<strong>Brokers:</strong> 30–50 brokers; each owns ~20–30 partition leaders",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "Peak: <strong>10M msg/sec</strong> = <strong>10 GB/sec</strong> &nbsp;·&nbsp; "
                        "Sustained: <strong>1M msg/sec</strong> = <strong>1 GB/sec</strong> &nbsp;·&nbsp; "
                        "7-day storage: <strong>~600 TB</strong> sustained, <strong>~6 PB</strong> peak &nbsp;·&nbsp; "
                        "RF=3 &nbsp;·&nbsp; ~<strong>500 partitions</strong>, ~<strong>30 brokers</strong>."
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
                        "<strong>Producers</strong> publish records to <strong>topics</strong>, "
                        "which are split into <strong>partitions</strong> distributed across a "
                        "<strong>broker cluster</strong>. Each partition has one leader and N "
                        "followers replicated via the <strong>ISR</strong> (In-Sync Replica) "
                        "protocol. Consumers join <strong>consumer groups</strong> and each "
                        "partition is assigned to exactly one consumer in the group. A coordinator "
                        "(KRaft / Raft quorum, replacing legacy ZooKeeper) manages metadata, "
                        "leader election, and group membership."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Producers hash by key into partitioned topics on a replicated broker cluster; consumer groups read independently. KRaft quorum holds metadata.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_prod {
        label="Producers"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        P1 [label="App A\n(orders)", fillcolor="#dbe6fb"];
        P2 [label="App B\n(clicks)", fillcolor="#dbe6fb"];
        P3 [label="CDC\n(DB → Connect)", fillcolor="#dbe6fb"];
    }

    subgraph cluster_brokers {
        label="Broker Cluster (3 brokers shown of N)"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        B1 [label="Broker 1\nP0 leader\nP1 follower\nP2 follower", fillcolor="#cbeedf"];
        B2 [label="Broker 2\nP1 leader\nP0 follower\nP2 follower", fillcolor="#cbeedf"];
        B3 [label="Broker 3\nP2 leader\nP0 follower\nP1 follower", fillcolor="#cbeedf"];
    }

    subgraph cluster_meta {
        label="Metadata Quorum"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        K1 [label="KRaft\nController", fillcolor="#ead7fb"];
    }

    subgraph cluster_cons {
        label="Consumer Groups"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        G1 [label="Group: payments\n3 consumers", fillcolor="#fff2c9"];
        G2 [label="Group: analytics\n6 consumers", fillcolor="#fff2c9"];
    }

    subgraph cluster_ext {
        label="Ecosystem"; style="rounded,dashed"; color="#c45a3b"; fontcolor="#c45a3b";
        CN [label="Kafka Connect\n(sinks/sources)", fillcolor="#fbd7c5"];
        SR [label="Schema Registry\n(Avro/Protobuf)", fillcolor="#fbd7c5"];
        ST [label="Streams / Flink\n(stream proc.)", fillcolor="#fbd7c5"];
    }

    P1 -> B1 [label="hash(key)"];
    P2 -> B2 [label="hash(key)"];
    P3 -> B3 [label="hash(key)"];

    B1 -> B2 [label="replicate", style=dashed, dir=both, color="#1f8359"];
    B2 -> B3 [label="replicate", style=dashed, dir=both, color="#1f8359"];
    B1 -> B3 [label="replicate", style=dashed, dir=both, color="#1f8359"];

    B1 -> K1 [style=dotted, dir=both];
    B2 -> K1 [style=dotted, dir=both];
    B3 -> K1 [style=dotted, dir=both];

    B1 -> G1 [label="fetch"];
    B2 -> G1 [label="fetch"];
    B3 -> G2 [label="fetch"];
    B1 -> G2 [label="fetch"];

    P1 -> SR [style=dotted, label="schema"];
    G2 -> ST [style=dashed];
    CN -> B2 [style=dashed];
}
""",
                },
                {"type": "h3", "text": "Architecture Highlights"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Producers:</strong> batch & compress records; route by hash(key) % num_partitions",
                        "<strong>Brokers:</strong> stateless protocol over a stateful append-only log on disk",
                        "<strong>Partitions:</strong> unit of parallelism, ordering, and replication",
                        "<strong>ISR replication:</strong> leader + followers; only in-sync replicas can be elected",
                        "<strong>KRaft controller:</strong> Raft quorum holds metadata (replaces ZooKeeper since Kafka 3.3)",
                        "<strong>Consumer groups:</strong> partition-to-consumer assignment; offset commits per partition",
                        "<strong>Ecosystem:</strong> Connect (ETL), Streams/Flink (processing), Schema Registry (contracts)",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Topic & Partition Model",
            "subtitle": "How records are addressed",
            "blocks": [
                {"type": "h3", "text": "The Hierarchy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Topic</strong> = named, ordered, append-only stream (e.g. <code>orders.v1</code>)",
                        "<strong>Partition</strong> = a sub-log of a topic; records strictly ordered within it",
                        "<strong>Offset</strong> = monotonically increasing 64-bit ID of a record within a partition",
                        "<strong>Record</strong> = (key, value, headers, timestamp). Key drives partition routing.",
                    ],
                },
                {"type": "h3", "text": "Partition Assignment by Producer"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>If key present:</strong> <code>partition = murmur2(key) % num_partitions</code> — same key always routes to same partition (preserves ordering)",
                        "<strong>If key absent:</strong> sticky partitioner — batches records to one partition per linger window for throughput",
                        "<strong>Custom partitioner:</strong> implement <code>Partitioner</code> interface for tenant isolation, hot-key spreading, etc.",
                        "<strong>Hot key warning:</strong> celebrity-key skew breaks partition parallelism; use composite key or salted prefix",
                    ],
                },
                {"type": "h3", "text": "Choosing Partition Count"},
                {
                    "type": "table",
                    "headers": ["Driver", "Rule of Thumb", "Why"],
                    "rows": [
                        ["Throughput", "≥ target_MBps / 50 MB/s/partition", "Per-partition cap from disk + replication"],
                        ["Consumer parallelism", "≥ max consumers in any group", "Each partition = 1 consumer; extras idle"],
                        ["Ordering", "≥ N where N = ordering scope count", "All records of one key share a partition"],
                        ["Cost", "≤ 4,000 per broker, ≤ 200,000 cluster", "Each partition costs file handles + memory"],
                        ["Future-proof", "Pick 2–3× current need", "Reducing partitions later requires recreate"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Repartitioning Is Painful",
                    "body": (
                        "Adding partitions changes the hash output for existing keys, breaking "
                        "ordering for those keys going forward. Plan partition count generously up "
                        "front, or design downstream consumers to tolerate key-route changes during "
                        "migration windows."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Storage: The Append-Only Log",
            "subtitle": "Why disks are fast for streaming",
            "blocks": [
                {"type": "h3", "text": "Segmented Log on Disk"},
                {
                    "type": "bullets",
                    "items": [
                        "Each partition is a directory of <strong>segment files</strong> (default 1 GB each)",
                        "Active segment is mutable; older segments are sealed and immutable",
                        "Files: <code>000000.log</code> (records), <code>000000.index</code> (offset→byte), <code>000000.timeindex</code> (ts→offset)",
                        "<strong>Retention</strong> is per-segment: drop entire segments older than 7 days or beyond size cap",
                        "<strong>Log compaction</strong>: optional alt mode that keeps the latest record per key (used for state stores)",
                    ],
                },
                {"type": "h3", "text": "Why Sequential I/O Matters"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Spinning HDD random:</strong> ~100 IOPS × 4 KB ≈ 0.4 MB/s — terrible",
                        "<strong>Spinning HDD sequential:</strong> ~<strong>600 MB/s sustained</strong> per drive — surprisingly fast",
                        "Append-only write pattern is purely sequential ⇒ HDDs are competitive with SSD on cost/GB",
                        "<strong>Page cache</strong>: kernel keeps recent log tail in RAM; consumers reading the tail hit cache",
                        "<strong>Zero-copy:</strong> <code>sendfile(2)</code> ships bytes from page cache to NIC without user-space copy",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Zero-Copy Path",
                    "body": (
                        "Without zero-copy, a fetch round-trip is: disk → kernel buffer → user buffer "
                        "→ socket buffer → NIC (4 copies). With <code>sendfile</code>: disk → kernel "
                        "buffer → NIC (2 copies, no user-space transition). This is one of Kafka's "
                        "biggest wins — it lets a single broker push tens of GB/sec to consumers."
                    ),
                },
                {"type": "h3", "text": "Index Files"},
                {
                    "type": "code",
                    "text": (
                        "# .index file: sparse map of logical offset -> byte position in .log\n"
                        "# Stored every ~4 KB of data (configurable: index.interval.bytes)\n"
                        "# Lookup an offset:\n"
                        "#   1. binary-search index file -> nearest (offset, byte) pair\n"
                        "#   2. scan forward in .log from that byte until exact offset hit\n"
                        "# Memory-mapped (mmap) for fast reads\n\n"
                        "# Example layout for partition orders-7:\n"
                        "/var/kafka/orders-7/\n"
                        "  00000000000000000000.log       # records 0..1,048,575\n"
                        "  00000000000000000000.index     # sparse offset index\n"
                        "  00000000000000000000.timeindex # sparse timestamp index\n"
                        "  00000000000001048576.log       # active segment, records 1,048,576..\n"
                        "  00000000000001048576.index\n"
                        "  00000000000001048576.timeindex"
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Replication & ISR",
            "subtitle": "Durability through followers",
            "blocks": [
                {"type": "h3", "text": "Leader / Follower / ISR"},
                {
                    "type": "bullets",
                    "items": [
                        "Each partition has <strong>one leader</strong> + <strong>RF − 1 followers</strong> on different brokers",
                        "Producers write only to the leader; followers <em>fetch</em> from the leader (pull, not push)",
                        "<strong>In-Sync Replica (ISR)</strong>: a follower that has caught up to within <code>replica.lag.time.max.ms</code> (default 30 s)",
                        "Only an ISR member is eligible for leader election (under default safe config)",
                        "<strong>High Watermark (HW):</strong> highest offset replicated to all ISRs — only HW-and-below records are visible to consumers",
                        "<strong>Log End Offset (LEO):</strong> next free offset on each replica",
                    ],
                },
                {
                    "type": "diagram",
                    "caption": "Leader holds full log; followers fetch and ack. High Watermark = min(LEO across ISRs) — only committed records visible to consumers.",
                    "dot": r"""
digraph R {
    rankdir=LR;
    bgcolor="white";
    node [shape=record, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8", fillcolor="#dbe6fb"];
    edge [fontname="Helvetica", fontsize=9, color="#586278"];

    Leader [label="{ Leader (Broker 1) | { 0 | 1 | 2 | 3 | 4 | 5 } | LEO=6 \\n HW=4 }", fillcolor="#cbeedf"];
    F1     [label="{ Follower (Broker 2) | { 0 | 1 | 2 | 3 | 4 | 5 } | LEO=6 \\n in ISR }", fillcolor="#fff2c9"];
    F2     [label="{ Follower (Broker 3) | { 0 | 1 | 2 | 3 | 4 } | LEO=5 \\n in ISR }", fillcolor="#fff2c9"];
    F3     [label="{ Follower (Broker 4) | { 0 | 1 | 2 } | LEO=3 \\n LAGGING — not ISR }", fillcolor="#fbd7c5"];

    Leader -> F1 [label="fetch resp", color="#1f8359"];
    Leader -> F2 [label="fetch resp", color="#1f8359"];
    Leader -> F3 [label="fetch resp", color="#c45a3b", style=dashed];

    F1 -> Leader [label="fetch req\nLEO=6", style=dotted];
    F2 -> Leader [label="fetch req\nLEO=5", style=dotted];
    F3 -> Leader [label="fetch req\nLEO=3 (slow)", style=dotted];

    HW [label="High Watermark = 4\n(committed; visible to consumers)", shape=note, fillcolor="#fbf7ee", color="#b8862e"];
    HW -> Leader [style=dashed, color="#b8862e"];
}
""",
                },
                {"type": "h3", "text": "acks: Producer Durability Knob"},
                {
                    "type": "table",
                    "headers": ["acks", "Behavior", "Latency", "On Loss"],
                    "rows": [
                        ["0", "Fire and forget; no broker ack", "Lowest", "Drops on broker crash, network drop"],
                        ["1", "Leader writes locally then acks", "Low", "Loses if leader crashes before replication"],
                        ["all (-1)", "Wait for all ISRs to replicate", "Highest", "No loss as long as ≥ min.insync.replicas alive"],
                    ],
                },
                {"type": "h3", "text": "min.insync.replicas & Unclean Election"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>min.insync.replicas=2</strong> with RF=3 + acks=all: tolerate 1 broker loss, never lose data",
                        "If ISR shrinks below this, producer gets <code>NotEnoughReplicas</code> — fail loud, don't lose",
                        "<strong>unclean.leader.election.enable=false</strong> (default): if all ISRs die, partition stays unavailable until one returns",
                        "<strong>unclean=true</strong>: a non-ISR replica may be elected leader → <em>data loss possible</em>, but availability restored sooner",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "The Classic Trade-off",
                    "body": (
                        "RF=3, min.insync=2, acks=all, unclean=false ⇒ <strong>maximum durability</strong>. "
                        "But two simultaneous follower failures stall writes until one recovers. "
                        "Lowering min.insync to 1 or enabling unclean election trades correctness for "
                        "availability — explicit business decision."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Producer Path",
            "subtitle": "Batching, idempotence, transactions",
            "blocks": [
                {"type": "h3", "text": "Producer Lifecycle"},
                {
                    "type": "numbered",
                    "items": [
                        "App calls <code>send(record)</code> — non-blocking, returns a <code>Future&lt;RecordMetadata&gt;</code>",
                        "Record assigned to a partition (key hash or sticky)",
                        "Appended to per-partition <strong>RecordAccumulator</strong> batch buffer in memory",
                        "Sender thread waits up to <code>linger.ms</code> or until batch fills <code>batch.size</code>",
                        "Batch compressed (lz4 / zstd / gzip / snappy) and sent in one <code>ProduceRequest</code> to the partition leader",
                        "Leader appends, awaits ISR replication if acks=all, then responds with <code>RecordMetadata{offset, partition}</code>",
                        "Future completes; callback fires with offset or error",
                    ],
                },
                {"type": "h3", "text": "Producer Configuration (Java)"},
                {
                    "type": "code",
                    "text": (
                        "Properties props = new Properties();\n"
                        "props.put(\"bootstrap.servers\", \"b1:9092,b2:9092,b3:9092\");\n"
                        "props.put(\"key.serializer\",   \"org.apache.kafka.common.serialization.StringSerializer\");\n"
                        "props.put(\"value.serializer\", \"io.confluent.kafka.serializers.KafkaAvroSerializer\");\n"
                        "\n"
                        "// Durability\n"
                        "props.put(\"acks\",                              \"all\");\n"
                        "props.put(\"enable.idempotence\",                \"true\");   // dedup retries\n"
                        "props.put(\"max.in.flight.requests.per.connection\", \"5\"); // safe with idempotence\n"
                        "props.put(\"retries\",                           \"2147483647\");\n"
                        "props.put(\"delivery.timeout.ms\",               \"120000\");\n"
                        "\n"
                        "// Throughput\n"
                        "props.put(\"linger.ms\",        \"10\");        // wait up to 10 ms to batch\n"
                        "props.put(\"batch.size\",       \"131072\");    // 128 KB per partition batch\n"
                        "props.put(\"compression.type\", \"lz4\");       // ~3-4x compression on JSON\n"
                        "props.put(\"buffer.memory\",    \"67108864\");  // 64 MB total buffer\n"
                        "\n"
                        "// Exactly-once across topics (transactions)\n"
                        "props.put(\"transactional.id\", \"orders-svc-1\");\n"
                        "\n"
                        "Producer<String, Order> p = new KafkaProducer<>(props);\n"
                        "p.initTransactions();\n"
                        "p.beginTransaction();\n"
                        "p.send(new ProducerRecord<>(\"orders.v1\", order.userId(), order));\n"
                        "p.send(new ProducerRecord<>(\"audit.v1\",  order.userId(), audit));\n"
                        "p.commitTransaction();   // or abortTransaction() on failure"
                    ),
                },
                {"type": "h3", "text": "Idempotent Producer"},
                {
                    "type": "bullets",
                    "items": [
                        "Each producer assigned a <strong>PID</strong> (Producer ID) on init",
                        "Each (PID, partition) carries a monotonic <strong>sequence number</strong>",
                        "Broker dedups on (PID, partition, seq); retried sends after a successful but unacked write don't duplicate",
                        "<strong>Cost:</strong> ~1% throughput; gives <em>per-session</em> exactly-once into one partition",
                    ],
                },
                {"type": "h3", "text": "Backpressure"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>buffer.memory</strong> bound: when full, <code>send()</code> blocks up to <code>max.block.ms</code>, then throws",
                        "<strong>Broker quotas:</strong> per-client byte/sec; broker throttles by delaying responses (no errors thrown)",
                        "<strong>Linger trade-off:</strong> linger.ms=0 ⇒ low latency, low throughput; linger.ms=20 ⇒ ~10× throughput, +20 ms p50",
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Consumer Groups & Rebalance",
            "subtitle": "Cooperative partition ownership",
            "blocks": [
                {"type": "h3", "text": "The Group Protocol"},
                {
                    "type": "bullets",
                    "items": [
                        "Consumers join a <strong>group.id</strong>; broker-side <strong>Group Coordinator</strong> assigns partitions",
                        "<strong>Invariant:</strong> each partition is consumed by exactly one consumer in the group at a time",
                        "If <code>num_consumers &gt; num_partitions</code>: extra consumers stay idle (still good for HA)",
                        "Multiple groups consume the same topic independently — each has its own offset cursor",
                        "<strong>Assignment strategies:</strong> Range, RoundRobin, Sticky, <strong>CooperativeSticky</strong> (incremental rebalance)",
                    ],
                },
                {"type": "h3", "text": "Offset Commits"},
                {
                    "type": "bullets",
                    "items": [
                        "Committed offsets stored in internal topic <code>__consumer_offsets</code> (50 partitions, RF=3)",
                        "<strong>Auto-commit</strong> (every 5 s): simple, but at-least-once with potential reprocessing on crash",
                        "<strong>Manual commit:</strong> <code>commitSync()</code> (blocks, retries) or <code>commitAsync()</code> (fire-and-forget)",
                        "<strong>Best practice:</strong> process record → commit; if process is non-idempotent, design downstream to dedup",
                    ],
                },
                {"type": "h3", "text": "Rebalance Algorithm (Pseudocode)"},
                {
                    "type": "code",
                    "text": (
                        "# Cooperative-sticky rebalance (no full stop-the-world)\n"
                        "# Triggered by: new consumer joining, heartbeat timeout, topic-partition added\n"
                        "\n"
                        "function on_join_group(group_id, member_id):\n"
                        "    coordinator = locate_coordinator(group_id)\n"
                        "    coordinator.send(JoinGroupRequest{member_id, subscribed_topics})\n"
                        "    # Coordinator picks one member as 'leader' (first to arrive)\n"
                        "    response = coordinator.recv()\n"
                        "    if response.is_leader:\n"
                        "        new_assignment = sticky_assign(\n"
                        "            members      = response.members,\n"
                        "            partitions   = topic_metadata.all_partitions(),\n"
                        "            previous     = response.current_assignment,\n"
                        "        )\n"
                        "        coordinator.send(SyncGroupRequest{assignments=new_assignment})\n"
                        "    else:\n"
                        "        coordinator.send(SyncGroupRequest{})\n"
                        "    my_assignment = coordinator.recv().assignment\n"
                        "    revoked = old_assignment - my_assignment\n"
                        "    added   = my_assignment   - old_assignment\n"
                        "    on_partitions_revoked(revoked)   # commit offsets, flush state\n"
                        "    on_partitions_assigned(added)    # seek to last committed offset\n"
                        "\n"
                        "# Heartbeat thread keeps membership alive every 3 s\n"
                        "function heartbeat_loop():\n"
                        "    while running:\n"
                        "        coordinator.send(HeartbeatRequest{member_id, generation_id})\n"
                        "        if response.error == REBALANCE_IN_PROGRESS:\n"
                        "            trigger_rejoin()\n"
                        "        sleep(heartbeat_interval_ms)\n"
                        "\n"
                        "# Fetch / commit happens between heartbeats\n"
                        "function poll_loop():\n"
                        "    while running:\n"
                        "        records = coordinator.fetch(my_assignment, last_committed_offsets)\n"
                        "        for r in records:\n"
                        "            process(r)              # idempotent ideally\n"
                        "        coordinator.commit(highest_offset_per_partition)"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Avoiding Rebalance Storms",
                    "body": (
                        "Each rebalance pauses processing on revoked partitions. Tune "
                        "<code>session.timeout.ms</code> and <code>max.poll.interval.ms</code> "
                        "above expected GC pauses. Use <strong>CooperativeStickyAssignor</strong> "
                        "(default since Kafka 3.0) for incremental rebalances — only the moving "
                        "partitions pause, not the whole group."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Delivery Semantics",
            "subtitle": "At-most, at-least, exactly-once",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Semantic", "Producer", "Consumer", "Use Case"],
                    "rows": [
                        ["At-most-once", "acks=0/1, no retries",
                         "commit before process", "Metrics; loss tolerable"],
                        ["At-least-once", "acks=all, retries on",
                         "process before commit", "Default; downstream dedup"],
                        ["Exactly-once (in-Kafka)", "idempotent + transactional.id",
                         "isolation.level=read_committed", "Stream-to-stream pipelines"],
                        ["Effectively-once (end-to-end)", "at-least-once + idempotent sink",
                         "dedupe by key/seq downstream", "Writes to DB, external API"],
                    ],
                },
                {"type": "h3", "text": "How Exactly-Once Works (Two-Phase Commit)"},
                {
                    "type": "code",
                    "text": (
                        "# Producer transaction across multiple partitions / topics\n"
                        "# (atomic from the consumer's read_committed view)\n"
                        "\n"
                        "function consume_process_produce_loop():\n"
                        "    producer.init_transactions()                    # registers txn.id with TxnCoordinator\n"
                        "    while running:\n"
                        "        records = consumer.poll(timeout=100ms)\n"
                        "        if records.empty(): continue\n"
                        "\n"
                        "        producer.begin_transaction()\n"
                        "        try:\n"
                        "            for r in records:\n"
                        "                out = transform(r)\n"
                        "                producer.send('out_topic', out)     # buffered in txn\n"
                        "\n"
                        "            # Critical: commit consumer offsets WITHIN the producer txn\n"
                        "            offsets = consumer.position_per_partition()\n"
                        "            producer.send_offsets_to_transaction(\n"
                        "                offsets, consumer.group_metadata()\n"
                        "            )\n"
                        "            producer.commit_transaction()           # 2PC: prepare + commit markers\n"
                        "        except:\n"
                        "            producer.abort_transaction()\n"
                        "            consumer.seek(last_committed_offsets)   # rewind\n"
                        "\n"
                        "# Broker side:\n"
                        "#   1. Producer sends records with txn.id — broker buffers them in the log,\n"
                        "#      marked uncommitted (not visible to read_committed consumers).\n"
                        "#   2. commit_transaction() -> TxnCoordinator writes commit marker to each\n"
                        "#      involved partition (including __consumer_offsets).\n"
                        "#   3. Once marker written, records become visible. Atomic across partitions."
                    ),
                },
                {"type": "h3", "text": "Trade-offs"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>At-most-once</strong>: simplest; <em>only</em> for replaceable signals (heartbeats, sampled metrics)",
                        "<strong>At-least-once</strong>: cheap and reliable — most pipelines run here with idempotent consumers",
                        "<strong>Exactly-once</strong>: ~10–30% throughput hit + complexity; only worth it for in-Kafka stream processing chains",
                        "<strong>End-to-end EOS to a DB:</strong> Kafka's transaction does NOT cover the external sink; need outbox / idempotent upsert",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Comparison: Kafka vs RabbitMQ vs SQS vs Pub/Sub",
            "subtitle": "Picking the right tool",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Aspect", "Kafka", "RabbitMQ", "AWS SQS", "Google Pub/Sub"],
                    "rows": [
                        ["Model", "Partitioned log (pull)", "AMQP broker (push)", "Distributed queue", "Topic + sub (pull/push)"],
                        ["Ordering", "Per-partition FIFO", "Per-queue FIFO (single consumer)", "FIFO queues only (limited TPS)", "Per-key with ordering keys"],
                        ["Throughput", "Millions/sec/cluster", "10s of K/sec/node", "~3K/sec/queue (FIFO 300/sec)", "Millions/sec (managed)"],
                        ["Retention", "Days–years; replay", "Until consumed (default)", "1 min – 14 days", "Up to 31 days; replay via snapshots"],
                        ["Delivery", "At-least, exactly-once", "At-least; at-most", "At-least (visibility timeout)", "At-least; exactly-once (regional)"],
                        ["Routing", "Hash partition by key", "Exchanges + routing keys (rich)", "Flat queue; one consumer pool", "Topic → many subs (fan-out)"],
                        ["Strength", "High-throughput log, replay", "Complex routing, low latency", "Zero-ops AWS native", "Zero-ops GCP native, global"],
                        ["Weakness", "Ops complexity; partition planning", "Storage on broker; harder to scale", "No replay; small messages only (256 KB)", "Vendor lock-in; cost at scale"],
                    ],
                },
                {"type": "h3", "text": "When to Pick What"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Kafka:</strong> event sourcing, log aggregation, stream processing, CDC, anywhere replay matters",
                        "<strong>RabbitMQ:</strong> task queues with priority/TTL/DLX, complex routing topologies, request/reply",
                        "<strong>SQS:</strong> simple decoupling on AWS, work queues with visibility timeout, no replay needed",
                        "<strong>Pub/Sub:</strong> fan-out events across services on GCP, push to HTTP/Cloud Run, global delivery",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Push vs Pull",
                    "body": (
                        "RabbitMQ <em>pushes</em> to consumers (broker-driven flow). Kafka and SQS "
                        "<em>pull</em> (consumer-driven). Pull naturally handles backpressure — slow "
                        "consumers just lag — and lets brokers stay simple, append-only servers. Push "
                        "needs broker-side flow control (prefetch, credit) to avoid overwhelming "
                        "consumers."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Operations & Observability",
            "subtitle": "Running the cluster",
            "blocks": [
                {"type": "h3", "text": "Topic Lifecycle (CLI)"},
                {
                    "type": "code",
                    "text": (
                        "# Create a topic with explicit replication and partition count\n"
                        "kafka-topics.sh --bootstrap-server b1:9092 \\\n"
                        "  --create --topic orders.v1 \\\n"
                        "  --partitions 200 --replication-factor 3 \\\n"
                        "  --config min.insync.replicas=2 \\\n"
                        "  --config retention.ms=604800000 \\\n"
                        "  --config compression.type=producer \\\n"
                        "  --config segment.bytes=1073741824\n"
                        "\n"
                        "# Inspect a consumer group's lag\n"
                        "kafka-consumer-groups.sh --bootstrap-server b1:9092 \\\n"
                        "  --group payments --describe\n"
                        "# GROUP    TOPIC     PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG  CONSUMER-ID\n"
                        "# payments orders.v1 0          1432901         1432955         54   pay-pod-7\n"
                        "# payments orders.v1 1          1428770         1432892         4122 pay-pod-3  <-- hot!\n"
                        "\n"
                        "# Reassign partitions when adding brokers (rebalance)\n"
                        "kafka-reassign-partitions.sh --bootstrap-server b1:9092 \\\n"
                        "  --reassignment-json-file plan.json --execute"
                    ),
                },
                {"type": "h3", "text": "Key Metrics to Alert On"},
                {
                    "type": "table",
                    "headers": ["Metric", "Healthy", "Page When"],
                    "rows": [
                        ["UnderReplicatedPartitions", "0", "&gt; 0 sustained &gt; 5 min"],
                        ["OfflinePartitionsCount", "0", "&gt; 0 — partition unavailable"],
                        ["ActiveControllerCount", "1 (cluster-wide)", "≠ 1 — split brain risk"],
                        ["RequestHandlerAvgIdlePercent", "&gt; 30%", "&lt; 20% — broker saturated"],
                        ["NetworkProcessorAvgIdlePercent", "&gt; 30%", "&lt; 20% — network saturated"],
                        ["Consumer lag (per group)", "Bounded, decreasing", "Growing &gt; 10 min"],
                        ["ISR shrinks/sec", "~0", "Spikes — flaky followers"],
                        ["Disk usage", "&lt; 70%", "&gt; 80% — retention or scale up"],
                    ],
                },
                {"type": "h3", "text": "Capacity Planning Heuristics"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Brokers:</strong> N = peak_MBps_in × RF / per-broker-cap. With 200 MB/s/broker cap and 10 GB/s × 3 = 30 GB/s ⇒ 150 brokers at peak; 30 brokers at sustained.",
                        "<strong>Partitions per broker:</strong> ≤ 4,000; at ~500 partitions × RF 3 = 1500 replicas / 30 brokers = 50/broker — very comfortable",
                        "<strong>Disk:</strong> retention_GB / num_brokers + 30% headroom; plan re-replication time",
                        "<strong>Network:</strong> producers → leader = 1×, leader → followers = (RF−1)× — biggest pipe is replication",
                    ],
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Failure Modes & Recovery",
            "subtitle": "What can go wrong",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["Broker process crash", "Followers it led re-elect; brief unavailability per partition",
                         "ZK/KRaft session timeout", "Auto failover; replay from disk on restart"],
                        ["Disk failure / corruption", "Replica offline; ISR shrinks",
                         "Read errors; log corruption marker", "Reformat + re-replicate from leader (hours at TB scale)"],
                        ["Network partition", "Some brokers think others dead; split risk",
                         "Heartbeat timeouts; ISR churn", "KRaft quorum prevents split brain; min.insync gates writes"],
                        ["Slow follower", "ISR shrinks; throughput drops if min.insync=RF",
                         "replica lag metric", "Dial replica.lag.time.max; investigate disk/GC"],
                        ["Slow consumer", "Group lag grows; possible rebalance",
                         "Consumer lag metric", "Scale consumers; tune max.poll.records / interval"],
                        ["Hot partition (key skew)", "One broker saturated; head-of-line blocking",
                         "Per-partition byte rate", "Re-key with salt; spread across more partitions"],
                        ["Producer overflow", "send() blocks/throws BufferExhausted",
                         "buffer-available-bytes", "Increase buffer.memory; lower throughput; quotas upstream"],
                        ["Schema break", "Consumers can't deserialize",
                         "Deserialization errors", "Schema Registry compatibility checks (BACKWARD)"],
                        ["KRaft quorum loss", "No metadata changes; existing partitions still read/write",
                         "Controller election fails", "Restore quorum majority; periodic backups of metadata log"],
                    ],
                },
                {"type": "h3", "text": "Disaster Recovery"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Multi-AZ:</strong> spread replicas via <code>broker.rack</code>; rack-aware assignment guarantees one replica per AZ",
                        "<strong>Cross-region:</strong> MirrorMaker 2 (async); typically active/passive — RPO seconds, RTO minutes",
                        "<strong>Tiered storage</strong> (Kafka 3.6+): offload old segments to S3 — cheaper retention, faster broker recovery",
                        "<strong>Backup of __consumer_offsets:</strong> include in MM2 mirroring so failover preserves consumer cursors",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Re-replication Is Slow",
                    "body": (
                        "Losing a broker that held 60 TB means the cluster must copy ~60 TB across the "
                        "network to bring replicas back to RF=3. At 1 Gbps that's ~6 days; at 10 Gbps "
                        "~14 hours. During that window you have reduced redundancy. <strong>Tiered "
                        "storage</strong> dramatically shrinks recovery because the broker only "
                        "re-replicates the local hot tail."
                    ),
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Design Trade-offs",
            "subtitle": "Decisions and rationale",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Decision", "Choice", "Trade-off"],
                    "rows": [
                        ["Durability vs latency", "acks=all + min.insync=2",
                         "+5–20 ms p99 vs acks=1, but no loss on single broker failure."],
                        ["Replication factor", "RF=3",
                         "3× storage cost; tolerates 1 broker loss with min.insync=2. RF=2 risky; RF=5 expensive."],
                        ["Partition count", "500 (10× peak need)",
                         "More parallelism but more file handles + rebalance time. Repartitioning is hard, so over-provision."],
                        ["Retention", "7 days time-based",
                         "Enables replay/backfill; ~600 TB cost. Longer = more storage; shorter = no recovery window."],
                        ["Storage media", "HDD JBOD",
                         "5–10× cheaper than SSD; sequential I/O hides HDD latency. SSD only if random reads dominate."],
                        ["Compression", "lz4 producer-side",
                         "~3–4× shrink with small CPU cost; gzip = better ratio, more CPU; zstd = best modern balance."],
                        ["Delivery semantics", "At-least-once + idempotent consumers",
                         "Simpler than EOS; downstream must dedup. EOS only for in-Kafka stream chains."],
                        ["Push vs pull", "Pull",
                         "Consumers control flow; brokers stay simple/stateless protocol; modest extra fetch RTTs."],
                        ["Broker controller", "KRaft (Raft quorum)",
                         "One fewer system to run vs ZooKeeper; younger code path."],
                        ["Message format", "Avro + Schema Registry",
                         "Compact, evolvable; vs JSON's human-readability or Protobuf's static typing."],
                    ],
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
                        "A 45-minute interview on this topic almost always anchors on Kafka's "
                        "partitioned-log model. Start with throughput math, derive partitions and "
                        "brokers from it, then drill into ISR replication, delivery semantics, and "
                        "consumer groups. Have the comparison table ready for the inevitable "
                        "“why not RabbitMQ?” follow-up."
                    ),
                },
                {"type": "h3", "text": "45-Minute Interview Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (2 min):</strong> clarify peak vs sustained, retention, ordering scope, semantics needed",
                        "<strong>Capacity (5 min):</strong> 10M/s peak → 10 GB/s in, ×3 RF replication, 600 TB at 7-day sustained",
                        "<strong>High-level (3 min):</strong> producers → topics/partitions on broker cluster → consumer groups; KRaft for metadata",
                        "<strong>Storage (5 min):</strong> append-only segmented log, sequential I/O, page cache, sendfile zero-copy",
                        "<strong>Replication (8 min):</strong> ISR, leader/follower, HW vs LEO, acks, min.insync, unclean election",
                        "<strong>Producer (4 min):</strong> batching/linger, idempotence (PID + seq), transactions",
                        "<strong>Consumer groups (6 min):</strong> partition-per-consumer invariant, rebalance, offset commits",
                        "<strong>Semantics (4 min):</strong> at-most/at-least/exactly-once; transactional 2PC across topics + offsets",
                        "<strong>Compare (4 min):</strong> Kafka vs RabbitMQ vs SQS vs Pub/Sub — pick the right tool",
                        "<strong>Failures + trade-offs (4 min):</strong> hot partition, slow consumer, broker loss, network partition",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why is Kafka so fast on commodity disks?</strong> A: Append-only sequential I/O (~600 MB/s on HDD), kernel page cache for tail reads, zero-copy <code>sendfile</code> avoids user-space copies.",
                        "<strong>Q: How is ordering preserved?</strong> A: Per-partition FIFO. Producers route by <code>hash(key) % partitions</code>, so same key = same partition. There is no global order.",
                        "<strong>Q: What if a leader crashes mid-write?</strong> A: Controller elects a new leader from the ISR. With acks=all + min.insync=2, the writes are safe on at least 2 replicas before ack. Followers truncate uncommitted suffix on becoming leaders.",
                        "<strong>Q: Exactly-once explained?</strong> A: Idempotent producer (PID + sequence dedup) + transactional.id wrapping <code>send_offsets_to_transaction</code> so consumer offsets and produced records commit atomically (2PC via TxnCoordinator).",
                        "<strong>Q: When NOT to use Kafka?</strong> A: When you need rich routing (use RabbitMQ), when ops budget is zero (use SQS/Pub-Sub), when retention &lt; minutes and message size &gt; MB (use object store + queue).",
                        "<strong>Q: How do you handle a hot key?</strong> A: Composite key (key + bucket suffix) to spread across N partitions, accepting per-bucket ordering instead of per-key. Or move that key to a dedicated topic.",
                        "<strong>Q: Why pull instead of push?</strong> A: Consumers absorb backpressure naturally (just lag); brokers stay simple servers; batch sizes can match consumer capability.",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "“10 GB/s peak ÷ 50 MB/s/partition ⇒ ~200 partitions floor; pick 500 for headroom”",
                        "“RF=3 + min.insync=2 + acks=all = no data loss with 1 broker down”",
                        "“Sequential disk + page cache + sendfile = why HDDs are competitive”",
                        "“Per-partition order, not global — by design”",
                        "“At-least-once + idempotent sinks beats exactly-once in most pipelines”",
                        "“KRaft replaced ZooKeeper — one fewer system to run”",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "Peak <strong>10M msg/sec</strong> &nbsp;·&nbsp; Sustained <strong>1M msg/sec</strong> "
                        "&nbsp;·&nbsp; Avg msg <strong>1 KB</strong> &nbsp;·&nbsp; "
                        "<strong>50 MB/s/partition</strong> ceiling &nbsp;·&nbsp; "
                        "<strong>RF=3, min.insync=2</strong> &nbsp;·&nbsp; "
                        "<strong>500 partitions, 30 brokers</strong> &nbsp;·&nbsp; "
                        "<strong>~600 TB</strong> at 7-day sustained &nbsp;·&nbsp; "
                        "HDD sequential <strong>~600 MB/s</strong> &nbsp;·&nbsp; "
                        "linger.ms=10, batch.size=128 KB."
                    ),
                },
            ],
        },
    ],
}
