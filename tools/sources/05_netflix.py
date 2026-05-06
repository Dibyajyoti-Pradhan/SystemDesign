"""Source for `05 - Netflix.pdf` (regenerated with errata applied)."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Netflix",
    "subtitle": "Video streaming platform serving 250M+ subscribers, 15M concurrent streams globally",
    "read_time": "~ 35 minute read",
    "short_title": "Design Netflix",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Statement & Clarifying Questions",
            "subtitle": "Define the scope",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Design <strong>Netflix</strong>: a global video streaming platform with 250M+ "
                        "subscribers, 15M concurrent streams at peak, a catalog of ~5K titles, and "
                        "personalized homepages per profile. The system must deliver high-quality video "
                        "with sub-second startup, &lt;0.5% stall rate, and DRM-protected playback across "
                        "190+ countries."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Scope", "Question", "Assumption"],
                    "rows": [
                        ["Video Types", "Streaming only, or include downloads?", "Streaming primary; downloads secondary"],
                        ["Live Content", "Live TV / sports, or VOD only?", "Primarily VOD; live is edge case"],
                        ["DRM", "Content protection required?", "Yes — Widevine, PlayReady, FairPlay"],
                        ["Profiles", "Multiple user profiles per account?", "Yes — child / adult; recommendations per profile"],
                        ["Geographic", "Global deployment required?", "Yes — 190+ countries, localized CDN"],
                        ["Recommendations", "Personalized homepage essential?", "Yes — three-stage ranking pipeline"],
                        ["Offline", "Offline viewing (downloads)?", "Yes but secondary focus"],
                    ],
                },
                {
                    "type": "para",
                    "text": (
                        "We focus on the <strong>streaming architecture for VOD content globally</strong>, "
                        "with DRM, personalized recommendations, and multi-profile support."
                    ),
                },
            ],
        },
        # ---- 02 ------------------------------------------------------
        {
            "num": "02",
            "title": "Functional & Non-Functional Requirements",
            "subtitle": "What the system must do",
            "blocks": [
                {"type": "h3", "text": "Functional Requirements"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Browse / search catalog</strong> (metadata API): instant (&lt;100ms)",
                        "<strong>Personalized recommendations:</strong> list 100 tiles in &lt;200ms",
                        "<strong>Initiate playback:</strong> fetch OCA URL + DRM token within &lt;500ms",
                        "<strong>Stream video continuously:</strong> adaptive bitrate, seamless quality switches",
                        "<strong>Track viewing history:</strong> record play / pause / seek / stop events",
                        "<strong>Multi-profile management:</strong> switch profiles instantly",
                        "<strong>Download for offline:</strong> queue + background sync",
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Availability", "99.95% uptime; graceful degradation if recommendation/billing fails"],
                        ["Latency", "Initial playback &lt;3s; segment delivery &lt;50ms p99; UI &lt;100ms"],
                        ["Scale", "250M subscribers; 15M concurrent streams; 5K+ titles; 700B events/day"],
                        ["Quality", "Adaptive bitrate (240p–4K); device codecs; multi-lang audio/subs"],
                        ["Security", "End-to-end DRM; HTTPS; rate limiting; account security"],
                        ["Cost", "Minimize CDN egress; aggressive caching; strategic content placement"],
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
                {"type": "h3", "text": "Users & Concurrency"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>250M subscribers</strong>; 30–40% watch on any given day (~100M DAU)",
                        "<strong>Peak hour:</strong> 15M concurrent streams (typical 8–10M; peak ~15M in US/EU primetime)",
                        "<strong>Device mix:</strong> 40% TV, 45% mobile, 15% web/tablet",
                        "<strong>Avg session:</strong> 1–2 hours; <strong>avg bitrate 5 Mbps</strong> (range 1–25 Mbps per device profile)",
                    ],
                },
                {"type": "h3", "text": "Bandwidth & CDN"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Peak CDN traffic:</strong> 15M streams × 5 Mbps = <strong>75 Tbps</strong>",
                        "Annual content egress: <strong>~350–400 EB</strong> (exabytes) from origin/caches to users",
                        "<strong>OCA hit rate:</strong> 99%+ from ISP-embedded appliances; &lt;1% miss → regional PoP or origin",
                        "Cache efficiency: proactive nightly push of top-N content; reactive caching for long-tail",
                    ],
                },
                {"type": "h3", "text": "Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Catalog size:</strong> ~5K titles; ~100 GB per title (all variants) = <strong>~500 TB aggregate</strong>",
                        "<strong>Viewing history:</strong> ~500B records (user_id, title_id, position, ts); ~100 GB hot in Cassandra",
                        "<strong>Metadata:</strong> ~100 GB (posters, descriptions, reviews, ratings, availability matrix)",
                        "<strong>Event logs:</strong> 700B events/day × 7-day retention ≈ <strong>~2 PB</strong> in Kafka / cloud",
                    ],
                },
                {"type": "h3", "text": "Cache Layer"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>EVCache (Memcached):</strong> ~800M queries/day (metadata, viewing history, OCA URL); 99% hit rate target; ~10 TB heap",
                        "<strong>Elasticsearch:</strong> ~2 TB for searchable catalog + ratings/reviews; sharded by region",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "15M concurrent streams &nbsp;·&nbsp; <strong>75 Tbps</strong> peak CDN traffic &nbsp;·&nbsp; "
                        "OCA hit rate <strong>99%+</strong> &nbsp;·&nbsp; ~500 TB catalog &nbsp;·&nbsp; "
                        "700B events/day &nbsp;·&nbsp; ~10 TB EVCache heap."
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level Architecture",
            "subtitle": "Three planes — control, data, async",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Netflix separates the system into three distinct planes: a <strong>Control "
                        "Plane</strong> on AWS for orchestration, a <strong>Data Plane</strong> on the "
                        "Open Connect CDN for video delivery, and an <strong>Async Plane</strong> for "
                        "event processing and ML."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Playback flow: client resolves an OCA URL via the Control Plane, then streams segments directly from the ISP-embedded appliance, falling back to a regional PoP or S3 origin only on a cache miss.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Client"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Client [label="Browser / TV / Mobile", fillcolor="#dbe6fb"];
    }
    subgraph cluster_data {
        label="Data Plane (Open Connect)"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        OCA [label="OCA at ISP\n(100TB SSD, FreeBSD)\n~5ms latency", fillcolor="#cbeedf"];
        PoP [label="Regional PoP\n(AWS / GCP)", fillcolor="#cbeedf"];
        S3  [label="S3 Origin\n(master copies)", fillcolor="#cbeedf"];
    }
    subgraph cluster_ctrl {
        label="Control Plane (AWS)"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        Zuul [label="Zuul\nAPI Gateway", fillcolor="#fff2c9"];
        Stream [label="Streaming\nService", fillcolor="#fff2c9"];
        Reco [label="Recommendation\nService", fillcolor="#fff2c9"];
        User [label="User / Billing\nService", fillcolor="#fff2c9"];
    }
    subgraph cluster_async {
        label="Async Plane"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        Cosmos [label="Cosmos\nEncoder Orchestrator", fillcolor="#ead7fb"];
        Archer [label="Archer\nEncoding Engine", fillcolor="#ead7fb"];
        Meson  [label="Meson\nML Workflow",  fillcolor="#ead7fb"];
        Kafka  [label="Kafka\n(700B events/day)", fillcolor="#fbd7c5"];
        Cass   [label="Cassandra\n(viewing history)", fillcolor="#ead7fb"];
    }

    Client -> Zuul   [label="1. /playback"];
    Zuul   -> Stream [label="2. resolve OCA"];
    Stream -> Reco   [label="rows", style=dashed];
    Stream -> User   [label="auth/DRM", style=dashed];
    Zuul   -> Client [label="3. manifest + OCA URL", color="#1f8359"];
    Client -> OCA    [label="4. fetch segments", color="#1f8359"];
    OCA    -> PoP    [label="MISS (<1%)", style=dashed];
    PoP    -> S3     [label="MISS", style=dashed];
    S3     -> Cosmos [label="encode", style=dashed];
    Cosmos -> Archer;
    Archer -> S3     [label="variants"];
    S3     -> OCA    [label="nightly push (BGP)", color="#1f8359"];
    Client -> Kafka  [label="play/pause/seek", style=dashed];
    Kafka  -> Meson  [style=dashed];
    Kafka  -> Cass   [style=dashed];
}
""",
                },
                {"type": "h3", "text": "Control Plane (AWS)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Zuul API Gateway:</strong> request routing, auth, rate limiting; filters for logging, metrics, DRM tokens",
                        "<strong>User Service:</strong> account, profiles, settings; backed by MySQL (ACID for billing)",
                        "<strong>Streaming Service:</strong> core orchestrator; resolves OCA endpoint for client IP; queries EVCache for metadata / URL mappings",
                        "<strong>Recommendation Service:</strong> three-stage ranking — candidate gen → filter → rank (150+ features)",
                        "<strong>Billing Service:</strong> subscription state, payment processing, entitlements; MySQL + event journal",
                    ],
                },
                {"type": "h3", "text": "Data Plane (Open Connect CDN)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>OCA Appliances:</strong> custom hardware (100TB SSD, FreeBSD) embedded in 1,000+ ISPs globally; serves 99%+ of segments at ~5ms latency",
                        "<strong>Regional PoPs:</strong> fallback caches in major cloud regions (AWS / GCP); serve cache misses from OCA",
                        "<strong>S3 Origin:</strong> master video copies; proactive nightly push to OCAs via BGP-controlled distribution",
                    ],
                },
                {"type": "h3", "text": "Async Plane (Event-Driven)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Kafka:</strong> ingest 700B events/day (play, pause, seek, rate, search, errors); partitioned by event type; 7-day retention",
                        "<strong>Spark:</strong> daily batch jobs — model retraining, offline analytics, data warehouse ETL",
                        "<strong>Flink:</strong> real-time stream processing — trending content, live dashboards, anomaly detection",
                        "<strong>Meson:</strong> ML workflow orchestrator; chains feature gen, training, evaluation, deployment",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Open Connect CDN Deep Dive",
            "subtitle": "Why Netflix doesn't use AWS CloudFront",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Netflix's proprietary CDN, <strong>Open Connect (OCA)</strong>, is the backbone "
                        "of the data plane. <strong>Cost</strong> and <strong>performance</strong> are "
                        "the drivers."
                    ),
                },
                {"type": "h3", "text": "Why Custom CDN?"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Cost:</strong> CloudFront egress ~$0.085/GB; OCA $0.01–$0.02/GB (5–10× cheaper via ISP partnerships, shared infra, bulk agreements)",
                        "<strong>Control:</strong> content placement, eviction, codec/resolution variants per ISP; no third-party constraints",
                        "<strong>Scale:</strong> 30–40% of global internet traffic is Netflix; no commercial CDN can compete on efficiency at that volume",
                        "<strong>Latency:</strong> ISP-embedded appliances serve from local network — <strong>~5ms vs 20–50ms</strong> from regional edge",
                    ],
                },
                {"type": "h3", "text": "OCA Hardware & Deployment"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Appliance specs:</strong> custom <strong>FreeBSD</strong> appliance; <strong>100 TB SSD</strong>; 10 Gbps NIC; low-power, silent for ISP NOCs",
                        "<strong>Placement:</strong> 1,000+ ISPs across 190+ countries; serves ~50–60% of peak global traffic",
                        "<strong>Regional PoPs:</strong> AWS/GCP regions + backbone providers as fallback for OCA misses",
                    ],
                },
                {"type": "h3", "text": "Content Distribution Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Proactive caching (nightly push):</strong> Netflix predicts top-N content per ISP based on regional popularity, time zone, device profile; BGP-announced routes push during off-peak hours",
                        "<strong>Reactive caching:</strong> OCA miss → fetch from regional PoP or S3; cache result for future requests (LRU eviction)",
                        "<strong>Cache hit rate:</strong> 99%+ for top-50% of catalog; 90%+ for long-tail",
                        "<strong>Pre-position new releases:</strong> trending content + new releases auto-sync nightly",
                    ],
                },
                {"type": "h3", "text": "Segment & Manifest Delivery"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Manifests:</strong> device-specific DASH manifests returned by Streaming Service; include optimal OCA URL for client's ISP",
                        "<strong>Segments:</strong> client fetches 2–4 second MPEG-DASH segments directly from OCA; bitrate adapts per segment",
                        "<strong>Fallback logic:</strong> if OCA unavailable, client retries regional PoP, then origin",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why ISP-embedded matters",
                    "body": (
                        "Embedding OCAs inside ISP networks turns Netflix's egress into the ISP's <em>internal</em> "
                        "traffic — cheaper for the ISP (less peering bandwidth) and faster for the user "
                        "(one network hop). The arrangement is mutually beneficial, which is why ISPs host "
                        "the appliances for free."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Video Encoding Pipeline",
            "subtitle": "Cosmos & Archer orchestration",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Netflix encodes every title into <strong>100+ variants</strong> "
                        "(codec / resolution / bitrate combinations) to optimise for device capability and "
                        "network conditions."
                    ),
                },
                {"type": "h3", "text": "Per-Title Encoding (Revolutionary)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Shot detection:</strong> analyse master file for shot boundaries, scene complexity, motion intensity",
                        "<strong>Variable bitrate by scene:</strong> complex scenes (explosions, CGI) get higher bitrate; simple scenes (dialogue, static) get lower",
                        "<strong>Result:</strong> 20–30% bandwidth savings vs uniform bitrate at the same perceptual quality",
                        "<strong>Example:</strong> 1080p H.264 averages 5 Mbps but rises to 8 Mbps for action and falls to 2 Mbps for dialogue",
                    ],
                },
                {"type": "h3", "text": "Codec Ladder & Device Profiles"},
                {
                    "type": "table",
                    "headers": ["Device Profile", "Codec Preference", "Resolutions", "Bitrate Range"],
                    "rows": [
                        ["Smart TV (2023+)", "HEVC (H.265), VP9", "4K, 1080p", "8–25 Mbps"],
                        ["Modern Smartphone", "H.264, VP9", "1080p, 720p", "3–8 Mbps"],
                        ["Older Mobile / Tablet", "H.264 only", "720p, 480p", "1–4 Mbps"],
                        ["Web Browser", "H.264, VP9", "1080p, 720p", "3–8 Mbps"],
                        ["Fire Stick", "H.264, HEVC", "4K, 1080p", "5–15 Mbps"],
                    ],
                },
                {"type": "h3", "text": "Cosmos Orchestration"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Cosmos:</strong> distributed encoding orchestrator; schedules parallel transcoding across the encoding fleet",
                        "<strong>Archer:</strong> encoding engine; runs FFmpeg (with custom plugins for per-title bitrate optimisation) on CPU/GPU clusters",
                        "<strong>Parallel encoding:</strong> each title encoded to all variants in parallel (4K HEVC, 1080p H.264, 720p VP9, AAC audio, etc.)",
                        "<strong>Cost:</strong> ~$0.25–$0.50 per hour of video encoded; 5K titles × 100 variants = ~500K encoding jobs; ~$2–5M annual encoding spend",
                    ],
                },
                {"type": "h3", "text": "Packaging & Distribution"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>DASH</strong> (Dynamic Adaptive Streaming over HTTP): industry-standard format; client-side adaptive bitrate selection",
                        "<strong>Segmentation:</strong> 2–4 second segments; manifest lists all available qualities; player chooses based on bandwidth",
                        "<strong>DRM packaging:</strong> Widevine, PlayReady, FairPlay licences embedded per variant",
                        "<strong>S3 storage:</strong> master copies; nightly batch push to OCAs via BGP-directed distribution",
                    ],
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Adaptive Streaming (DASH)",
            "subtitle": "Client-side quality selection",
            "blocks": [
                {"type": "h3", "text": "Playback Flow"},
                {
                    "type": "numbered",
                    "items": [
                        "Client calls Zuul <code>/playback</code> with title_id, device profile, user IP",
                        "Streaming Service queries EVCache for OCA URL mapping (geo-aware; nearest ISP appliance)",
                        "EVCache returns optimal OCA endpoint for client's IP range",
                        "Zuul returns playback URL + DASH manifest to client",
                        "Client fetches DASH manifest from manifest server (metadata)",
                        "Client initiates segment fetch from OCA endpoint",
                        "OCA serves segment from local cache (HIT 99%+) or fetches from regional PoP (MISS &lt;1%)",
                    ],
                },
                {"type": "h3", "text": "BOLA Algorithm (Buffer-Occupancy Bitrate Adaptation)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Goal:</strong> maximise bitrate while avoiding stalls; minimise re-buffering events",
                        "<strong>Key metric:</strong> buffer occupancy (seconds of video buffered locally), not network bandwidth alone",
                        "<strong>Logic:</strong> if buffer &gt; 30s, increase bitrate; if buffer &lt; 10s, decrease quality; target ~15s buffer",
                        "<strong>Advantage:</strong> more stable quality switching than network-speed-only; reduces stalls in congested networks",
                        "<strong>SLA:</strong> stall rate &lt; 0.5% (less than 3 seconds stalled per hour of viewing)",
                    ],
                },
                {"type": "h3", "text": "Segment Details"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Segment duration:</strong> 2–4 seconds; granular quality switching; ~50KB–5MB per segment depending on quality",
                        "<strong>Prefetching:</strong> client prefetches 3–5 segments ahead to maintain buffer",
                        "<strong>Geo-aware URL:</strong> IPv4 GeoIP lookup determines nearest OCA appliance",
                        "<strong>Fallback chain:</strong> OCA → Regional PoP → S3 origin; client retries with exponential backoff",
                    ],
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Microservices & Resilience",
            "subtitle": "How Netflix avoids catastrophic failures",
            "blocks": [
                {"type": "h3", "text": "Stateless Services"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Zuul, Streaming, Recommendation:</strong> all stateless; horizontally scalable; any instance can serve any request",
                        "<strong>No local caches or sessions:</strong> all state in EVCache or databases; failures don't lose in-flight state",
                        "<strong>Load balancing:</strong> Eureka (service discovery) + Ribbon (client-side LB) for intelligent request routing",
                    ],
                },
                {"type": "h3", "text": "Circuit Breaker (Resilience Pattern — resilience4j / concurrency-limits)"},
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Hystrix is in maintenance mode",
                    "body": (
                        "Netflix put <strong>Hystrix into maintenance mode in 2018</strong>; new services use "
                        "<strong>resilience4j</strong> (or Spring Cloud Circuit Breaker), and Netflix internally adopted "
                        "<strong>adaptive concurrency limits</strong> via the <code>concurrency-limits</code> "
                        "library. The patterns below describe what those libraries implement; the library "
                        "names matter when an interviewer probes."
                    ),
                },
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Fallback catalog:</strong> if Recommendation Service fails, fall back to 'Popular Now' or 'Trending Globally' (pre-computed offline)",
                        "<strong>Circuit-breaker logic:</strong> fail fast; don't retry downstream if a service is down; return cached response or 'degraded' UI",
                        "<strong>Metrics:</strong> error rate, latency p99, timeouts trigger <code>OPEN</code>; <code>HALF_OPEN</code> allows slow recovery testing",
                        "<strong>Timeouts:</strong> all inter-service calls have &lt;500ms timeout; fail fast rather than cascade latency",
                        "<strong>Adaptive concurrency:</strong> the <code>concurrency-limits</code> library adjusts in-flight call limits using TCP-Vegas-style gradient feedback, shedding load before queues blow up",
                    ],
                },
                {"type": "h3", "text": "Chaos Engineering"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Chaos Monkey:</strong> randomly kills instances during business hours; teams must architect for recovery",
                        "<strong>Chaos Kong:</strong> kills entire AWS region; tests multi-region failover (Route53 latency-based routing)",
                        "<strong>Latency Monkey:</strong> injects artificial delays to test timeout handling and fallback logic",
                        "<strong>Culture:</strong> failure injection is proactive testing; failures found in chaos tests don't surprise production",
                    ],
                },
                {"type": "h3", "text": "Service Discovery (Eureka) & Client-Side LB (Ribbon)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Eureka:</strong> central service registry; services heartbeat every 30s; Netflix's internal DNS alternative",
                        "<strong>Ribbon:</strong> client-side LB; caches instance list from Eureka; retries failed requests against healthy instances",
                        "<strong>Benefit:</strong> no single LB bottleneck; routing considers instance health, latency zones, canary deployments",
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Database Architecture",
            "subtitle": "MySQL + Cassandra + EVCache + Elasticsearch",
            "blocks": [
                {"type": "h3", "text": "MySQL (Billing, Users, ACID)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Use case:</strong> user accounts, subscription tier, billing history, payment methods, entitlements",
                        "<strong>Why MySQL:</strong> ACID essential; billing must be precise; transactions required for payment processing",
                        "<strong>Scale:</strong> ~250M user records; write-heavy (daily billing, subscription changes); replicated across multi-master setup",
                        "<strong>Sharding:</strong> by <code>user_id</code> modulo; thousands of shards to distribute load",
                    ],
                },
                {"type": "h3", "text": "Cassandra (Viewing History, Write-Heavy)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Use case:</strong> viewing history (play position, watched status, resume timestamp); ~500B records; append-only log",
                        "<strong>Why Cassandra:</strong> extremely write-heavy; distributed; no SPOF; tunable consistency (eventual ok for history)",
                        "<strong>Data model:</strong> wide rows by <code>user_id</code>; columns = <code>{title_id: {position, ts, watched}}</code>",
                        "<strong>Throughput:</strong> ~2.5K ops/sec per node; &gt;100 nodes per cluster; millions of writes/sec aggregate",
                        "<strong>Consistency:</strong> eventual (RF=3, quorum reads/writes for critical data)",
                    ],
                },
                {"type": "h3", "text": "EVCache (Memcached, Metadata & Playback URLs)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Use case:</strong> metadata (title, poster, description), OCA playback URLs, viewing-history snippets",
                        "<strong>Scale:</strong> ~800M hits/day; 99% hit rate target; &lt;30ms p99 latency",
                        "<strong>Cluster:</strong> ~10 TB total heap; distributed across hundreds of nodes; replicated 2–3×",
                        "<strong>Eviction:</strong> LRU when memory full; keys expire after 24h (auto-refresh from source)",
                        "<strong>Key benefit:</strong> avoids expensive Cassandra or S3 lookups; metadata in-memory",
                    ],
                },
                {"type": "h3", "text": "Elasticsearch (Search & Catalog)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Use case:</strong> full-text search (title, description, actor, director); faceted (genre, year, rating)",
                        "<strong>Scale:</strong> ~2 TB index across 50+ shards; sharded by region/language for locality",
                        "<strong>Consistency:</strong> near real-time; new titles indexed within minutes",
                        "<strong>Features:</strong> typo tolerance, synonym matching, personalised results (rating history influences ranking)",
                    ],
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Recommendation System",
            "subtitle": "Three-stage ranking pipeline",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Netflix's homepage personalises ~100 rows per user, each with 10–30 titles. The "
                        "algorithm runs in three stages to balance quality and speed."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Recommendation funnel: a ~5K-title catalog narrows monotonically through ALS candidate generation, business-rule filtering, and LightGBM ranking before the top ~100 land in the user's feed.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=9, color="#586278"];

    Catalog [label="Catalog\n~5K titles", fillcolor="#dbe6fb"];
    Stage1 [label="Stage 1\nALS candidate gen\n(matrix factorization,\nbatch / daily)", fillcolor="#cbeedf"];
    Cand   [label="~10K\nuser-specific\ncandidates", fillcolor="#fff2c9"];
    Stage2 [label="Stage 2\nFiltering\n(watched, region, age,\nlicensing)", fillcolor="#cbeedf"];
    Surv   [label="~1–2K\nsurvivors", fillcolor="#fff2c9"];
    Stage3 [label="Stage 3\nLightGBM ranking\n(150+ features,\nrequest-time)", fillcolor="#cbeedf"];
    Top    [label="~100\nranked titles\ndisplayed", fillcolor="#ead7fb"];
    Feed   [label="User\nHomepage", fillcolor="#dbe6fb"];

    Catalog -> Stage1 [label="user × item\nmatrix"];
    Stage1  -> Cand;
    Cand    -> Stage2;
    Stage2  -> Surv;
    Surv    -> Stage3 [label="LightGBM scores\nthe survivors"];
    Stage3  -> Top;
    Top     -> Feed;
}
""",
                },
                {"type": "h3", "text": "Stage 1 — Candidate Generation (~10K candidates per user)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Algorithm:</strong> Alternating Least Squares (ALS) matrix factorisation; collaborative filtering",
                        "<strong>Input:</strong> user-title interaction matrix (viewing history, ratings, search, clicks); item embeddings (metadata features)",
                        "<strong>Output:</strong> top <strong>~10K candidate titles per user</strong> (not yet ranked; sorted by relevance score)",
                        "<strong>Scale:</strong> batch job; retrains daily on Spark; maps users and titles to low-dimensional vectors",
                        "<strong>Latency:</strong> generation is offline; runtime lookup is O(1) hash or in-memory vector search",
                    ],
                },
                {"type": "h3", "text": "Stage 2 — Filtering (~1–2K candidates after filtering)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Rules:</strong> remove already-watched, region-locked, or age-restricted titles for the profile",
                        "<strong>Business logic:</strong> prioritise licensed content expiring soon; boost originals; remove low-quality titles",
                        "<strong>Latency:</strong> &lt;100ms; deterministic rules; computed in real time or cached",
                    ],
                },
                {"type": "h3", "text": "Stage 3 — Ranking (~100 titles to display; per-row ranking)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Algorithm:</strong> Gradient Boosting (LightGBM); predicts CTR (click-through rate) for each title in context",
                        "<strong>Features (150+):</strong> user (age, country, tier), item (genre, IMDb score, release date), context (time-of-day, device, row position)",
                        "<strong>Training:</strong> offline daily batch; Spark pipeline on Kafka events (clicks, watches, searches)",
                        "<strong>Personalisation:</strong> artwork selection per user (e.g., thumbnail of an actor the user has rated highly; or an action scene if the user watches action)",
                        "<strong>A/B testing:</strong> homepage layout, row ordering, thumbnail variants — winner picked on CTR + watch time",
                    ],
                },
                {"type": "h3", "text": "Why Three Stages?"},
                {
                    "type": "bullets",
                    "items": [
                        # ERRATUM 2 fix verbatim from ERRATA.md.
                        "<strong>Speed:</strong> each stage narrows the set monotonically — <strong>~5K-title catalog → ~10K user-specific candidates (Stage 1 ALS) → ~1–2K after filtering (Stage 2) → ~100 ranked titles displayed (Stage 3)</strong>; LightGBM only scores the ~1–2K survivors, not the full catalog",
                        "<strong>Quality:</strong> specialised algorithms at each stage; ALS captures broad taste; LightGBM captures interaction effects",
                        "<strong>Cost:</strong> ALS + filtering offline; only LightGBM runs at request time; &lt;200ms total latency",
                        "<strong>Explainability:</strong> can inspect why a title ranked highly (similar title watched; high score; popular now)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why ALS expands before filtering shrinks",
                    "body": (
                        "Stage 1 deliberately produces ~10K candidates — <em>more</em> than the 5K catalog "
                        "size — because the ALS scoring is per-user and unique titles can appear with "
                        "different relevance scores across multiple synthetic 'rows' (e.g. action, "
                        "trending-in-country). Filtering then collapses duplicates and drops ineligible "
                        "titles down to ~1–2K survivors before LightGBM does the expensive ranking."
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Data Pipeline",
            "subtitle": "Kafka → Spark / Flink → Analytics",
            "blocks": [
                {"type": "h3", "text": "Kafka Ingest (700B Events/Day)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Event types:</strong> play, pause, seek, stop, rate, search, error, subscription change, profile switch",
                        "<strong>Volume:</strong> 250M users × 2–3 events/min during watching = 700B events/day",
                        "<strong>Schema:</strong> JSON; timestamp, user_id, title_id, device, playback position, event type, client IP",
                        "<strong>Retention:</strong> 7 days hot; older events archived to S3 for long-term analytics",
                        "<strong>Partitioning:</strong> by <code>user_id</code> or <code>event_type</code>; ensures ordering per user",
                    ],
                },
                {"type": "h3", "text": "Spark Batch Pipeline (Daily)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Jobs:</strong> model retraining (ALS, LightGBM), data warehouse ETL, offline analytics, reporting",
                        "<strong>Input:</strong> Kafka events + viewing history (Cassandra snapshots) + content metadata",
                        "<strong>Output:</strong> trained models (ALS embeddings, LightGBM weights) → online serving; aggregated metrics → Druid",
                        "<strong>Latency:</strong> ~4 hours per daily job; models deployed by morning for next day's recommendations",
                    ],
                },
                {"type": "h3", "text": "Flink Real-Time Stream (Live Metrics)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Jobs:</strong> trending content (titles gaining play rate in last hour), anomaly detection (errors, stalls), live dashboards",
                        "<strong>Latency:</strong> &lt;5 second lag; results published to Kafka topics or websockets for dashboards",
                        "<strong>Stateful:</strong> count plays per title per minute; detect &gt;3σ deviations as anomalies",
                    ],
                },
                {"type": "h3", "text": "Druid OLAP (Ad-Hoc Analytics)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Use case:</strong> dashboard queries (titles watched per country, device, tier); near real-time exploration",
                        "<strong>Metrics:</strong> plays, stall rate, bitrate distribution, recommendations CTR",
                        "<strong>Latency:</strong> &lt;1s for pre-aggregated dashboards; &lt;5s for ad-hoc analysis",
                    ],
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Resilience & Chaos Engineering",
            "subtitle": "How Netflix survives disasters",
            "blocks": [
                {"type": "h3", "text": "Multi-Region Active-Active Deployment"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Regions:</strong> US-East, US-West, EU-West, APAC (minimum 3 active regions)",
                        "<strong>Traffic routing:</strong> Route53 latency-based routing → user lands on nearest region",
                        "<strong>Database replication:</strong> MySQL multi-master (cross-region); Cassandra multi-DC (RF=3 across DCs)",
                        "<strong>Failover:</strong> if a region fails, Route53 reroutes traffic automatically — no manual intervention",
                        "<strong>Data loss:</strong> RPO &lt;5 minutes (replication lag); RTO &lt;30 seconds (Route53 + LB failover)",
                    ],
                },
                {"type": "h3", "text": "Chaos Monkey (Instance-Level Failures)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Action:</strong> randomly terminates instances during business hours (production for some teams; staging for others)",
                        "<strong>Frequency:</strong> approximately one instance per service per region per hour",
                        "<strong>Culture:</strong> teams must be on-call; assume instances will fail; architect accordingly",
                        "<strong>Benefit:</strong> uncovers single points of failure before they cause production incidents",
                    ],
                },
                {"type": "h3", "text": "Chaos Kong (Region-Level Failures)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Action:</strong> simulates entire AWS region failure; yanks network cables (test mode in staging)",
                        "<strong>Test:</strong> verify Route53 failover, DB failover, client reconnection logic all work",
                        "<strong>Cadence:</strong> quarterly; part of disaster recovery drill",
                    ],
                },
                {"type": "h3", "text": "Latency Monkey (Network Delays)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Action:</strong> injects 100–500ms artificial delay on inter-service calls",
                        "<strong>Purpose:</strong> ensure all timeouts are configured correctly; fallback logic triggers before timeout",
                        "<strong>Result:</strong> prevents cascade failures when one service degrades; circuit breaker opens gracefully",
                    ],
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Failure Modes & Recovery",
            "subtitle": "8 critical scenarios",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Cause", "Impact", "Mitigation"],
                    "rows": [
                        ["OCA Appliance Outage",
                         "Hardware failure; ISP power loss",
                         "Users in that ISP routed to regional PoP; latency 5ms → 50ms; 1–5% QoE impact",
                         "Health checks; automatic fallback chain; redundant appliances per ISP"],
                        ["Cassandra Partition",
                         "Network split; DC unreachable",
                         "Viewing-history writes fail; reads serve stale data (eventual consistency)",
                         "Quorum reads/writes; RF=3 across regions; application fallback to cache"],
                        ["EVCache Miss Storm",
                         "Memcached cluster crash; cache stampede",
                         "Metadata lookups hit Cassandra; p99 latency spikes to 500ms",
                         "Circuit breaker; fallback to cached manifest; preload hot keys at startup"],
                        ["Recommendation Lag",
                         "Model training delayed; batch job failure",
                         "Homepage shows generic 'Popular Now' instead of personalised rows",
                         "Serve previous day's model; A/B impact minimal (CTR diff &lt;1%)"],
                        ["Encoding Pipeline Failure",
                         "Cosmos orchestrator down; encoder crash",
                         "New title cannot be encoded; release delayed",
                         "Manual restart; on-demand encoding fallback; pre-compute common profiles"],
                        ["DRM Service Down",
                         "Licence server unavailable",
                         "Playback blocked; users cannot watch any content",
                         "Cache DRM licences locally for 24h; offline viewing if downloaded"],
                        ["Zuul Gateway Overload",
                         "Thundering herd; DDoS attack",
                         "API latency &gt;1s; some requests time out and retry",
                         "Rate limiting; circuit breaker; shed load via 429 (client backoff)"],
                        ["Billing Service Failure",
                         "MySQL replication lag; payment processor down",
                         "Subscription state unknown; allow stream to continue (billing retries later)",
                         "Optimistic UI; async reconciliation; manual dispute resolution"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful Degradation Hierarchy",
                    "body": (
                        "Always preserve playback (the core function). Degrade in this order: "
                        "personalised recommendations → custom artwork → search ranking quality → "
                        "billing reconciliation. Never block a paid user from watching content they're "
                        "entitled to because of a non-essential service failing."
                    ),
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Trade-offs & Design Decisions",
            "subtitle": "Why these choices?",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Decision", "Alternative", "Why Netflix Chose It"],
                    "rows": [
                        ["Own CDN (OCA)", "AWS CloudFront / Akamai",
                         "Cost (5–10× cheaper); control over content placement; latency (ISP embedding)"],
                        ["Cassandra", "DynamoDB / MongoDB",
                         "Write throughput (2.5K ops/sec/node); no SPOF; operational maturity"],
                        ["DASH (HTTP)", "RTMP / custom protocol",
                         "Firewall-friendly; standards-based; client-controlled adaptive bitrate"],
                        ["Eventual Consistency", "Strong consistency",
                         "Viewing history 'eventual ok'; availability + latency &gt;&gt; precision"],
                        ["Separate 3 Planes", "Monolith",
                         "Independent scaling; failure isolation; team ownership"],
                        ["Three-Stage Ranking", "Single model",
                         "&lt;200ms latency achieved by filtering + LightGBM only on ~1–2K candidates"],
                        ["Daily Model Retraining", "Real-time updates",
                         "Cost / complexity trade-off; daily refresh sufficient for CTR; A/B catches bugs"],
                        ["Proactive CDN Push", "Reactive only",
                         "Bandwidth savings; 99%+ hit rate; scale advantages at Netflix's size"],
                        ["resilience4j / concurrency-limits", "Hystrix",
                         "Hystrix in maintenance since 2018; resilience4j is actively developed; concurrency-limits handles adaptive shedding"],
                    ],
                },
            ],
        },
        # ---- 15 ------------------------------------------------------
        {
            "num": "15",
            "title": "Interview Playbook",
            "subtitle": "How to present this design (45 minutes)",
            "blocks": [
                {"type": "h3", "text": "Opening (5 min): Clarifying Questions & Scope"},
                {
                    "type": "bullets",
                    "items": [
                        "Start with 2–3 clarifying questions: VOD only? Global? Recommendations essential?",
                        "Confirm assumptions: 250M subscribers, 15M concurrent streams, ~5K titles, multi-region",
                        "Set scope: focus on streaming architecture (not downloads or live)",
                    ],
                },
                {"type": "h3", "text": "Capacity (2 min)"},
                {
                    "type": "bullets",
                    "items": [
                        "Memorise: 250M subscribers, 15M concurrent (peak), <strong>75 Tbps</strong> CDN traffic, ~500 TB catalog",
                        "Draw on whiteboard: user base → concurrent → bandwidth calculation",
                        "Point out the scale problem: standard CDN (CloudFront) would be cost-prohibitive",
                    ],
                },
                {"type": "h3", "text": "Architecture (10 min): 3 Planes + Diagrams"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Control plane:</strong> Zuul → microservices (User, Billing, Streaming, Recommendation); stateless + circuit breakers",
                        "<strong>Data plane:</strong> Open Connect CDN; 1,000+ ISP-embedded appliances; 99%+ hit rate; nightly proactive push",
                        "<strong>Async plane:</strong> Kafka (700B events/day) → Spark (daily retraining) → Flink (live metrics)",
                        "Use diagrams; explain why custom CDN is critical for cost & scale",
                    ],
                },
                {"type": "h3", "text": "Deep Dives (20 min): Pick 2–3 Topics"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>CDN:</strong> OCA hardware, ISP partnerships, proactive vs reactive caching; why 99%+ hit rate",
                        "<strong>Recommendations:</strong> three-stage ranking; <strong>5K → 10K → 1–2K → 100</strong>; 150+ features; personalisation",
                        "<strong>Encoding:</strong> per-title encoding; scene-based variable bitrate; codec ladder; Cosmos orchestration",
                        "<strong>Resilience:</strong> Chaos Monkey/Kong; resilience4j circuit breaker; multi-region active-active",
                        "Common probes: 'How would you handle a Cassandra partition?', 'Why not use CloudFront?', 'How do you scale recommendations?'",
                    ],
                },
                {"type": "h3", "text": "Wrap-Up (5 min): Trade-offs"},
                {
                    "type": "bullets",
                    "items": [
                        "Discuss cost vs quality vs latency trade-offs",
                        "Mention operational complexity (Chaos Monkey culture, multi-region databases)",
                        "End with: <em>Netflix is unique at scale; most companies don't justify a custom CDN, but Netflix streams 30–40% of global internet traffic</em>",
                    ],
                },
                {"type": "h3", "text": "Key Numbers to Memorise"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>250M subscribers, 15M concurrent streams, 75 Tbps</strong> CDN traffic",
                        "<strong>OCA hit rate 99%+</strong>; latency 5ms vs 50ms regional",
                        "<strong>700B events/day</strong> to Kafka; daily model retraining",
                        "Cassandra: 2.5K ops/sec/node; EVCache: 99% hit rate; 800M queries/day",
                        "DASH 2–4s segments; BOLA buffer algorithm; &lt;0.5% stall-rate SLA",
                        "Encoding: 100+ variants per title; per-title VBR saves 20–30% bandwidth",
                        "Recommendation funnel: <strong>~5K → ~10K → ~1–2K → ~100</strong>",
                    ],
                },
                {"type": "h3", "text": "What Interviewers Are Testing"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Systems thinking:</strong> can you connect pieces? (Why custom CDN affects encoding and caching strategy)",
                        "<strong>Scale intuition:</strong> 15M concurrent = how much bandwidth? How many DB ops?",
                        "<strong>Trade-off reasoning:</strong> why OCA over CloudFront? Why Cassandra over MySQL?",
                        "<strong>Resilience:</strong> what fails? How do you recover? Do you have a fallback?",
                        "<strong>Communication:</strong> can you explain a complex system simply? Use diagrams. Admit uncertainty.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorise These",
                    "body": (
                        "75 Tbps peak &nbsp;·&nbsp; 99%+ OCA hit &nbsp;·&nbsp; 700B events/day &nbsp;·&nbsp; "
                        "5K → 10K → 1–2K → 100 funnel &nbsp;·&nbsp; resilience4j (not Hystrix) &nbsp;·&nbsp; "
                        "5ms vs 50ms latency."
                    ),
                },
            ],
        },
    ],
}
