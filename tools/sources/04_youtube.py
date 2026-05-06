"""Source for `04 - YouTube.pdf` (regenerated with errata applied).

ERRATA APPLIED (see design-questions/ERRATA.md, "04 - YouTube"):
  Erratum 1 — concurrent-viewer math: 1B h/day ÷ 24 h/day ≈ 41.7M concurrent
              (was: 1B h/day ÷ 86,400 sec = 11.6M, mixed units). Recomputed
              the entire bandwidth chain: 41.7M × 2 Mbps ≈ 83 Tbps avg egress,
              ~170 Tbps peak, origin pull ≈ 4 Tbps.
  Erratum 2 — upload-count math: 30,000 h/day × 60 min/h ÷ 10 min/video =
              180,000 videos/day (was: 30,000 × 60 = 1.8M videos/day, mixed
              units). All downstream QPS numbers recomputed.
"""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design YouTube",
    "subtitle": (
        "A global video streaming platform handling 2B+ users, "
        "500 hours/minute uploads, 1B hours/day watched"
    ),
    "read_time": "~ 45 minute read",
    "short_title": "Design YouTube",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Statement",
            "subtitle": "Ask 7 clarifying questions",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "You are asked to design <strong>YouTube</strong>, a global video "
                        "streaming platform where users can upload, watch, and share videos. "
                        "The interviewer expects you to start with clarifying questions to "
                        "scope the problem before sketching architecture."
                    ),
                },
                {"type": "h3", "text": "Key Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer / Scope"],
                    "rows": [
                        ["1. Scale: how many users?",
                         "2 billion total users; ~500 million monthly active users"],
                        ["2. Video upload volume?",
                         "500 hours of video uploaded per minute globally"],
                        ["3. Video storage duration?",
                         "Indefinite (≥ 10 years); some pruning of very old unwatched content"],
                        ["4. Geographic reach?",
                         "Global; must support playback in all regions with local CDN"],
                        ["5. Real-time features?",
                         "Live streaming out of scope for MVP; focus on stored video on-demand"],
                        ["6. Video resolution?",
                         "Multiple: 144p (mobile) up to 4K; client-side device adaptivity"],
                        ["7. Core product focus?",
                         "Watch experience &gt; upload experience. Search, recommendations, "
                         "comments are secondary."],
                    ],
                },
                {"type": "h3", "text": "Design Constraints (from clarifications)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Global scale:</strong> 500M MAU spread across 6 continents → "
                        "geographically distributed CDN",
                        "<strong>Upload velocity:</strong> 500 h/min = 30,000 h/day → massive ingestion pipeline",
                        "<strong>Watch volume:</strong> ~1 billion video hours watched per day globally (estimated)",
                        "<strong>Read-heavy:</strong> watch:upload ratio ≈ 2000:1; bias the architecture toward playback",
                        "<strong>Quality expectations:</strong> &lt;2 sec startup, near-zero buffering, instant pause/resume",
                    ],
                },
            ],
        },
        # ---- 02 ------------------------------------------------------
        {
            "num": "02",
            "title": "Functional & Non-Functional Requirements",
            "subtitle": "What the system must do, and how well",
            "blocks": [
                {"type": "h3", "text": "Functional Requirements"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Upload video:</strong> chunk-based resumable upload with progress tracking",
                        "<strong>Watch video:</strong> stream with ABR (adaptive bitrate), low latency, seek support",
                        "<strong>List videos:</strong> search by title/tags, browse by category, trending videos",
                        "<strong>Recommend videos:</strong> personalised picks based on watch history &amp; collaborative filtering",
                        "<strong>Comments:</strong> post, reply, like; nested threads with pagination",
                        "<strong>Subscriptions:</strong> subscribe to channels and get notifications for new uploads",
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Metric", "Target"],
                    "rows": [
                        ["Video startup latency", "&lt;2 seconds (p99)"],
                        ["Rebuffer rate", "&lt;0.5% of streams"],
                        ["Availability", "99.99% (4 nines)"],
                        ["Search latency", "&lt;100ms (p99)"],
                        ["Recommendation latency", "&lt;500ms (p99)"],
                        ["Storage durability", "99.999999999% (11 nines, triple replication)"],
                        ["Video encoding latency", "&lt;4 hours for 1 TB (≈ 2 Mbps processing)"],
                    ],
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "Calculate QPS, storage, bandwidth",
            "blocks": [
                {"type": "h3", "text": "Daily Upload Volume"},
                # ERRATUM 2 — corrected upload math: 30,000 h/day × 60 min/h ÷ 10 min/video.
                {
                    "type": "code",
                    "text": (
                        "500 hours/minute × 60 minutes = 30,000 hours/day\n"
                        "\n"
                        "Assuming average video is 10 minutes:\n"
                        "30,000 h/day × 60 min/h ÷ 10 min/video = 180,000 videos/day\n"
                        "\n"
                        "Upload QPS (spread over 24h = 86,400 sec):\n"
                        "180,000 / 86,400 ≈ 2.1 video_uploads/second average\n"
                        "\n"
                        "Peak-hour ≈ 3× average = ~6–7 uploads/sec at peak"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Don't mix units",
                    "body": (
                        "An earlier draft wrote <em>30,000 hours = 30,000 × 60 min = 1,800,000 videos/day</em> "
                        "— that multiplies hours by minutes-per-hour and labels the result as videos. "
                        "The correct formula divides total minutes by minutes-per-video, giving "
                        "<strong>180,000 videos/day</strong> (10× smaller)."
                    ),
                },
                {"type": "h3", "text": "Daily Storage Requirement"},
                {
                    "type": "code",
                    "text": (
                        "Raw video storage:\n"
                        "  30,000 hours/day × 1 GB/hour = 30 TB raw video/day\n"
                        "\n"
                        "Transcoded (~10 variants: 4K + 1080p + 720p + 480p + 360p\n"
                        "+ 240p + 144p, each in H.264 / VP9):\n"
                        "  30 TB × ~10 transcoded formats ≈ 300 TB/day\n"
                        "\n"
                        "Annual storage needed:\n"
                        "  300 TB/day × 365 = 109.5 PB/year\n"
                        "\n"
                        "With 3× replication for durability:\n"
                        "  109.5 PB × 3 ≈ 328 PB/year of replicated storage"
                    ),
                },
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Raw daily ingest:</strong> 30 TB/day at 1 GB per hour of source video",
                        "<strong>After transcoding:</strong> ~300 TB/day across the resolution &amp; codec ladder",
                        "<strong>Annual replicated:</strong> 109.5 PB/year × 3 ≈ <strong>328 PB</strong> per year of stored content",
                        "<strong>5-year retention:</strong> ~547 PB logical / ~1.6 EB replicated, assuming linear growth",
                    ],
                },
                {"type": "h3", "text": "Streaming (Watch) Volume & Bandwidth"},
                # ERRATUM 1 — concurrent-viewer math corrected: 1B h/day ÷ 24 h/day ≈ 41.7M.
                {
                    "type": "code",
                    "text": (
                        "Estimated daily watch hours: ~1 billion hours/day\n"
                        "\n"
                        "Concurrent streams (uniform across the day):\n"
                        "  1B hours/day ÷ 24 h/day ≈ 41.7 million concurrent viewers\n"
                        "\n"
                        "Bandwidth requirement (at 2 Mbps average adaptive bitrate):\n"
                        "  41.7M streams × 2 Mbps ≈ 83 Tbps average egress\n"
                        "\n"
                        "Peak ≈ 2× average (diurnal / regional skew):\n"
                        "  ~170 Tbps CDN egress at peak\n"
                        "\n"
                        "With 95% edge cache hit rate, origin pull:\n"
                        "  5% × 83 Tbps ≈ 4 Tbps to origin"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Hours per day, not seconds per day",
                    "body": (
                        "An earlier draft divided <em>1 B hours/day by 86,400 seconds/day</em>, mixing "
                        "hours with seconds and arriving at 11.6M concurrent viewers. The correct "
                        "denominator is 24 hours/day, giving "
                        "<strong>≈ 41.7M concurrent viewers</strong>. Every downstream bandwidth "
                        "number (egress, peak, origin pull) is ~3.6× larger as a result."
                    ),
                },
                {"type": "h3", "text": "Database Metrics"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Videos table:</strong> ~660M total over 10 years "
                        "(180K/day × 365 × 10); ~500 B/row ≈ 330 GB",
                        "<strong>Users table:</strong> ~2 billion users; ~1 KB/row ≈ 2 TB",
                        "<strong>Comments:</strong> ~5 B comments (assume 7:1 comment:video ratio); Cassandra sharded by video_id",
                        "<strong>Likes / views:</strong> ~50 B+ events; Redis counters with async flush to Cassandra",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "Uploads: <strong>180K videos/day</strong> (~2 QPS avg, ~6–7 peak) &nbsp;·&nbsp; "
                        "Raw ingest: <strong>30 TB/day</strong> &nbsp;·&nbsp; "
                        "Transcoded: <strong>~300 TB/day</strong> → <strong>328 PB/yr</strong> (3×) &nbsp;·&nbsp; "
                        "Concurrent viewers: <strong>~41.7M</strong> &nbsp;·&nbsp; "
                        "CDN egress: <strong>~83 Tbps</strong> avg / <strong>~170 Tbps</strong> peak &nbsp;·&nbsp; "
                        "Origin pull: <strong>~4 Tbps</strong>."
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level Architecture",
            "subtitle": "Multi-tier service design",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The system is divided into several layers: <strong>client</strong>, "
                        "<strong>edge / CDN</strong>, <strong>API gateway</strong>, "
                        "<strong>core services</strong>, and <strong>data tier</strong>. "
                        "Each layer is independently scalable and fault-tolerant. The key "
                        "split is <strong>write path</strong> (upload → transcode) versus "
                        "<strong>read path</strong> (stream from CDN); they scale on entirely "
                        "different curves."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Figure 4.1 — Viewer and creator traffic flow through distinct paths so each side can scale independently.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Client"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Client [label="Browser / Mobile / TV", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        CDN [label="CDN PoPs\n(segments + manifests)", fillcolor="#cbeedf"];
        LB  [label="Load Balancer", fillcolor="#cbeedf"];
        GW  [label="API Gateway\n(authn / rate limit)", fillcolor="#cbeedf"];
    }
    subgraph cluster_svc {
        label="Core Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        UP [label="Upload\nService", fillcolor="#fff2c9"];
        ST [label="Streaming\nService", fillcolor="#fff2c9"];
        RC [label="Recommendation\nService", fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        MY [label="MySQL\n(videos, users)",       fillcolor="#ead7fb"];
        S3 [label="S3 / GCS\n(raw + transcoded)",  fillcolor="#ead7fb"];
        CA [label="Cassandra / HBase\n(comments, watch hist.)", fillcolor="#ead7fb"];
        KQ [label="Kafka\n(upload, view events)",  fillcolor="#fbd7c5"];
        BT [label="Bigtable\n(analytics, counters)", fillcolor="#ead7fb"];
    }

    Client -> CDN [label="GET segment\n(95% hit)", color="#1f8359"];
    Client -> LB  [label="upload / API"];
    LB -> GW;
    GW -> UP [label="POST /upload"];
    GW -> ST [label="GET /manifest"];
    GW -> RC [label="GET /home"];
    UP -> S3  [label="raw bytes"];
    UP -> KQ  [label="upload_done"];
    UP -> MY  [label="metadata"];
    ST -> MY  [label="manifest meta", style=dashed];
    ST -> S3  [label="origin pull (5%)", style=dashed];
    RC -> CA  [label="watch hist", style=dashed];
    RC -> BT  [label="model features", style=dashed];
    CDN -> S3 [label="origin pull", style=dashed, color="#7a3eb8"];
}
""",
                },
                {"type": "h3", "text": "Component Overview"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Client:</strong> Web browser, mobile app, smart TV; initiates playback or upload",
                        "<strong>Load Balancer:</strong> distributes inbound requests across API gateways",
                        "<strong>API Gateway:</strong> authentication, rate limiting, request routing",
                        "<strong>Upload Service:</strong> chunked / resumable uploads (TUS protocol)",
                        "<strong>Streaming Service:</strong> serves HLS / DASH manifests and segments",
                        "<strong>Search Service:</strong> Elasticsearch for title / tag search with ranking",
                        "<strong>Recommendation Service:</strong> two-tower model (candidates → ranking)",
                        "<strong>Transcoding Cluster:</strong> parallel workers encoding videos into the resolution × codec ladder",
                        "<strong>Message Queue (Kafka):</strong> event-driven pipeline; <code>upload_done</code> → <code>transcode_trigger</code>",
                        "<strong>S3 / GCS:</strong> raw video storage (ingest) and transcoded segments (streaming)",
                        "<strong>CDN PoPs:</strong> geographically distributed Points-of-Presence caching segments",
                        "<strong>MySQL:</strong> transactional metadata (videos, users)",
                        "<strong>Cassandra / HBase:</strong> time-series comments &amp; watch history; scales horizontally",
                        "<strong>Bigtable:</strong> view counts, model features, analytics aggregations",
                        "<strong>Redis:</strong> caching, session store, real-time counters (likes, views)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Read path vs write path",
                    "body": (
                        "The architecture explicitly separates the write path "
                        "(<em>upload → transcode → object store</em>) from the read path "
                        "(<em>CDN → streaming service → object store</em>). Uploads happen "
                        "at single-digit QPS; reads happen at tens of millions of concurrent "
                        "streams. Decoupling lets each side scale on its own clock."
                    ),
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Video Upload & Ingestion",
            "subtitle": "Resumable uploads, deduplication",
            "blocks": [
                {
                    "type": "diagram",
                    "caption": "Figure 5.1 — Transcoding pipeline. Raw bytes land in S3, an SQS message fans out to a worker pool, each variant is written back to S3 and the CDN is warmed.",
                    "dot": r"""
digraph T {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Up   [label="Raw upload\n(TUS chunks)", fillcolor="#dbe6fb"];
    S3R  [label="S3: raw-videos/\n{video_id}.mp4", fillcolor="#cbeedf"];
    Q    [label="SQS\ntranscode_jobs", fillcolor="#fbd7c5"];
    W1   [label="Transcoder\n4K / 1080p", fillcolor="#fff2c9"];
    W2   [label="Transcoder\n720p / 480p", fillcolor="#fff2c9"];
    W3   [label="Transcoder\n360p / 240p / 144p", fillcolor="#fff2c9"];
    S3T  [label="S3: transcoded/\n{video_id}/{res}/seg*.ts", fillcolor="#cbeedf"];
    CDN  [label="CDN warm\n(pre-push popular)", fillcolor="#ead7fb"];
    DB   [label="MySQL: videos\nstatus = 'ready'", fillcolor="#ead7fb"];

    Up -> S3R [label="PUT chunks"];
    S3R -> Q  [label="upload_done"];
    Q  -> W1;
    Q  -> W2;
    Q  -> W3;
    W1 -> S3T;
    W2 -> S3T;
    W3 -> S3T;
    S3T -> CDN [label="invalidate +\npre-warm", style=dashed];
    S3T -> DB  [label="manifest URL", style=dashed];
}
""",
                },
                {"type": "h3", "text": "TUS Protocol (Resumable Upload)"},
                {
                    "type": "para",
                    "text": (
                        "The Tus protocol (<code>https://tus.io/</code>) standardises resumable "
                        "uploads. YouTube-scale requires:"
                    ),
                },
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Chunking:</strong> split video into 5–10 MB chunks (standard chunk size)",
                        "<strong>Resumability:</strong> track which chunks uploaded; client resumes from last chunk on network failure",
                        "<strong>Server acknowledgment:</strong> Upload Service returns offset and next chunk index",
                        "<strong>Atomic commits:</strong> mark upload complete only when all chunks received and checksummed",
                    ],
                },
                {"type": "h3", "text": "Upload Flow (Step-by-Step)"},
                {
                    "type": "numbered",
                    "items": [
                        "Creator initiates upload: <code>POST /upload</code> → receives <code>upload_id</code>, chunk size hints",
                        "Client chunks &amp; sends: <code>PATCH /upload/{id}/chunk/{n}</code> with chunk + checksum",
                        "Server acknowledges: returns offset progress; client buffers retries on transient error",
                        "Upload completes: final chunk triggers verification; checksum mismatch → re-upload chunk",
                        "Kafka event published: <code>upload_complete {video_id, creator_id, original_size}</code>",
                        "Transcoding orchestrator consumes the event and dispatches tasks to transcoding workers",
                        "Raw video stored: S3 at <code>s3://raw-videos/{creator_id}/{video_id}.mp4</code>",
                    ],
                },
                {"type": "h3", "text": "Deduplication & Content-Addressed Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Perceptual hashing:</strong> compute pHash of uploaded video during transcoding",
                        "<strong>pHash lookup:</strong> check if hash exists in Cassandra; if match → link <code>video_id</code> to existing content",
                        "<strong>Space savings:</strong> avoid 50+ TB/day duplicate storage (estimated 10–15% duplicate rate)",
                        "<strong>Copyright enforcement:</strong> identical pHashes flag potential copyright violations for review",
                    ],
                },
                {"type": "h3", "text": "Handling Upload Failures"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Transient network failure:</strong> client retries chunk with exponential backoff",
                        "<strong>Timeout on chunk:</strong> Upload Service holds state; client resumes after 5 min",
                        "<strong>Corrupted chunk (checksum mismatch):</strong> client re-sends; server re-computes checksum",
                        "<strong>Upload abandoned:</strong> garbage collector cleans incomplete uploads after 7 days",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Abuse mitigation",
                    "body": (
                        "YouTube accepts uploads from anyone. Initial uploads land in a "
                        "<strong>moderation queue</strong> for bot detection (content-hash lookup, "
                        "NSFW classifier, copyright fingerprint). Cleared uploads then proceed to "
                        "the transcoding pipeline."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Transcoding",
            "subtitle": "Codec selection, resolution ladder, cost",
            "blocks": [
                {"type": "h3", "text": "Codec Comparison"},
                {
                    "type": "table",
                    "headers": ["Codec", "Bitrate (1080p)", "Compression", "Adoption", "Notes"],
                    "rows": [
                        ["H.264 (AVC)", "3–5 Mbps", "Good (2003)", "Universal (99.9%)",
                         "Highest compatibility; patent-pool licences"],
                        ["VP9", "2–3 Mbps", "Excellent", "~80% devices",
                         "Open-source; better compression than H.264"],
                        ["AV1", "1–1.5 Mbps", "Excellent+", "Emerging (~40%)",
                         "Next-gen; high CPU cost; 5–10× encode time"],
                        ["HEVC (H.265)", "2–3 Mbps", "Excellent", "~75% devices",
                         "Patent-heavy licensing; superior quality at bitrate"],
                    ],
                },
                {"type": "h3", "text": "YouTube's Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Primary:</strong> H.264 — universal fallback for all browsers",
                        "<strong>Secondary:</strong> VP9 — Chrome, Firefox; saves ~30% bandwidth",
                        "<strong>Tertiary:</strong> HEVC — Apple devices (iOS / macOS); saves ~40% vs H.264",
                        "<strong>Future:</strong> AV1 for premium content (4K+); encoding cost too high for bulk",
                    ],
                },
                {"type": "h3", "text": "Resolution Ladder"},
                {
                    "type": "code",
                    "text": (
                        "Standard ladder (~10 resolutions × 2–3 codecs):\n"
                        "\n"
                        "  4K (2160p): H.264 (8–12 Mbps) | VP9 (5–7 Mbps) | HEVC (4–6 Mbps)\n"
                        "  1440p:      H.264 (5–8 Mbps)  | VP9 (3–5 Mbps) | HEVC (2.5–4 Mbps)\n"
                        "  1080p:      H.264 (3–5 Mbps)  | VP9 (2–3 Mbps) | HEVC (1.5–2.5 Mbps)\n"
                        "  720p:       H.264 (2–3 Mbps)  | VP9 (1–2 Mbps) | HEVC (1–1.5 Mbps)\n"
                        "  480p:       H.264 (1–1.5 Mbps)| VP9 (0.8–1.2 Mbps)\n"
                        "  360p / 240p / 144p: H.264 only (mobile-optimised, lowest bitrate)"
                    ),
                },
                {"type": "h3", "text": "Transcoding Cost & Performance"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>CPU-intensive:</strong> 1 hour of 1080p H.264 encoding ≈ 45 min CPU on an 8-core machine",
                        "<strong>Parallel strategy:</strong> 8 workers per node; each encodes a different resolution simultaneously",
                        "<strong>Cost optimisation:</strong> ~$0.015 per hour of video transcoded (compute + storage + bandwidth)",
                        "<strong>SLA:</strong> &gt;90% of uploads transcoded within 4 hours; &lt;10% within 24 hours",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Why parallelise per-resolution",
                    "body": (
                        "Each variant is independent — different resolutions read the same source "
                        "but produce disjoint outputs. Fan out to workers per (resolution × codec) "
                        "pair; the highest-resolution rung dominates wall-clock time, but the "
                        "smaller rungs finish quickly and start hitting the CDN sooner."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Adaptive Bitrate Streaming",
            "subtitle": "ABR algorithms, manifest format",
            "blocks": [
                {"type": "h3", "text": "HLS (HTTP Live Streaming) Manifest"},
                {
                    "type": "code",
                    "text": (
                        "#EXTM3U\n"
                        "#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720\n"
                        "720p/segment_list.m3u8\n"
                        "#EXT-X-STREAM-INF:BANDWIDTH=1500000,RESOLUTION=854x480\n"
                        "480p/segment_list.m3u8\n"
                        "#EXT-X-STREAM-INF:BANDWIDTH=500000,RESOLUTION=426x240\n"
                        "240p/segment_list.m3u8\n"
                        "\n"
                        "# master.m3u8 lists all available quality levels;\n"
                        "# each child playlist lists the .ts segments for its rung."
                    ),
                },
                {"type": "h3", "text": "Adaptive Bitrate (ABR) Algorithms"},
                {
                    "type": "table",
                    "headers": ["Algorithm", "Strategy", "Latency", "Fairness"],
                    "rows": [
                        ["BOLA (Buffer-based)", "Maximise quality while maintaining buffer", "Low", "High"],
                        ["Pensieve (ML-based)", "RL model predicts optimal bitrate", "Very low", "Very high"],
                        ["Rate-based", "Adjust bitrate based on network probe", "Medium", "Medium"],
                        ["Buffer-filling", "Ramp up quality until buffer &gt; threshold", "High", "Low"],
                    ],
                },
                {"type": "h3", "text": "BOLA (Buffer-Optimal Latency-Aware)"},
                {
                    "type": "para",
                    "text": (
                        "BOLA uses a utility function to maximise quality while avoiding stalls. "
                        "The decision rule per segment:"
                    ),
                },
                {
                    "type": "code",
                    "text": (
                        "Q(r) = log(bitrate[r]) − stall_penalty × P(stall | buffer, rate)\n"
                        "\n"
                        "Decision: select the highest Q(r) such that buffering won't occur.\n"
                        "Re-evaluate every 1–3 segments based on (buffer level, throughput).\n"
                    ),
                },
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Provably optimal</strong> in the offline (Lyapunov) setting",
                        "<strong>Stable:</strong> rarely switches bitrate (reduces audio / visual artefacts)",
                        "<strong>Fairness:</strong> balances competing streams sharing the same bottleneck",
                        "<strong>Buffer-aware:</strong> escalates quality only when buffer is healthy",
                    ],
                },
                {"type": "h3", "text": "Manifest Request Flow"},
                {
                    "type": "numbered",
                    "items": [
                        "Player requests manifest: <code>GET /manifest?video_id=abc&amp;device=mobile</code>",
                        "Streaming Service resolves: Redis cache hit (~99%); returns cached <code>.m3u8</code>",
                        "Cache miss (&lt; 1%): hits MySQL → retrieves list of quality tiers + segment URLs",
                        "Manifest sent to player: includes <code>master.m3u8</code> with bandwidth hints",
                        "Player selects quality: BOLA picks the highest sustainable rung",
                        "Segment fetch: <code>GET /segments/720p_seg001.ts</code> → CDN PoP (~95% hit rate)",
                        "Adaptive switch: every 1–3 segments, player re-evaluates buffer + bandwidth",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "DASH vs HLS",
                    "body": (
                        "DASH (Dynamic Adaptive Streaming over HTTP) is the codec-agnostic ISO "
                        "standard; HLS is Apple's manifest format and dominates on iOS / Safari. "
                        "Both use the same primitives — fragmented MP4 (or MPEG-TS), a master "
                        "manifest, and per-rung playlists — so a single transcoded library can "
                        "serve both with minimal duplication."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "CDN Architecture",
            "subtitle": "Multi-tier caching, geo-distribution",
            "blocks": [
                {"type": "h3", "text": "CDN Tier Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Tier 1 (Edge PoPs):</strong> closest to users; cache popular content (hot videos)",
                        "<strong>Tier 2 (Regional):</strong> larger caches; fallback for Tier 1 misses",
                        "<strong>Tier 3 (Origin):</strong> primary S3 / object storage; holds all transcoded segments",
                    ],
                },
                {"type": "h3", "text": "Cache Optimisation"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Hit-rate targets:</strong> 95–99% at edge; 99.5%+ at regional",
                        "<strong>Popular content:</strong> pre-warm Tier 1 for trending videos (auto-detected by analytics)",
                        "<strong>TTL strategy:</strong> long-lived content (&gt; 30 days) → TTL 365d; new content → TTL 7d",
                        "<strong>Purge on update:</strong> if creator re-uploads thumbnail / metadata, invalidate cache entries",
                    ],
                },
                {"type": "h3", "text": "Geo-Distribution"},
                {
                    "type": "code",
                    "text": (
                        "Estimated PoP locations (simplified):\n"
                        "\n"
                        "  North America:  ~50 PoPs (NYC, LA, Chicago, Denver, …)\n"
                        "  Europe:         ~40 PoPs (London, Paris, Frankfurt, Moscow, …)\n"
                        "  Asia-Pacific:   ~60 PoPs (Tokyo, Singapore, Sydney, Delhi, …)\n"
                        "  South America:  ~15 PoPs (São Paulo, Buenos Aires, …)\n"
                        "  Africa:         ~10 PoPs (Johannesburg, Cairo, …)\n"
                        "\n"
                        "  Total: ~175 PoPs globally"
                    ),
                },
                {"type": "h3", "text": "Traffic Flow & Load Balancing"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>DNS Anycast:</strong> user resolves <code>video.youtube.com</code> → closest PoP via GeoDNS",
                        "<strong>HTTP redirect:</strong> if PoP is full / low-capacity, redirect to next-nearest PoP",
                        "<strong>Load balancing:</strong> round-robin across PoP servers; monitor CPU and bandwidth per server",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Why 95% edge hit rate matters",
                    "body": (
                        "At ~83 Tbps average egress, every percentage point of cache miss is "
                        "~830 Gbps of extra traffic to origin. Pushing edge hit rate from 90% to "
                        "95% halves the origin pull from ~8 Tbps to ~4 Tbps — that's the difference "
                        "between needing one origin region and three."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Database Design",
            "subtitle": "Schema, sharding, consistency",
            "blocks": [
                {"type": "h3", "text": "Primary Databases"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>MySQL (Videos, Users):</strong> strongly consistent; transactional; ACID for critical data",
                        "<strong>Cassandra (Comments, Watch History):</strong> eventually consistent; high write throughput; distributed sharding",
                        "<strong>Redis (Cache, Counters):</strong> in-memory; sub-millisecond latency; volatile but acceptable for ephemeral data",
                        "<strong>Elasticsearch (Search Index):</strong> full-text indexing; ranked search; refreshed every 30 seconds",
                    ],
                },
                {"type": "h3", "text": "MySQL Schema (Simplified)"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE videos (\n"
                        "  video_id      BIGINT PRIMARY KEY,\n"
                        "  creator_id    BIGINT NOT NULL,\n"
                        "  title         VARCHAR(500) NOT NULL,\n"
                        "  description   TEXT,\n"
                        "  duration      INT,                       -- seconds\n"
                        "  created_at    TIMESTAMP,\n"
                        "  updated_at    TIMESTAMP,\n"
                        "  status        ENUM('processing','ready','blocked'),\n"
                        "  manifest_url  VARCHAR(255),               -- s3 origin\n"
                        "  thumbnail_url VARCHAR(255),\n"
                        "  view_count    BIGINT DEFAULT 0,\n"
                        "  like_count    BIGINT DEFAULT 0,\n"
                        "  INDEX idx_creator (creator_id),\n"
                        "  INDEX idx_status  (status)\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "Cassandra Schema (Watch History)"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE watch_history_by_user (\n"
                        "  user_id          BIGINT,\n"
                        "  watched_at       BIGINT,    -- timestamp in millis (sorted DESC)\n"
                        "  video_id         BIGINT,\n"
                        "  watched_duration INT,\n"
                        "  quality          VARCHAR(10),\n"
                        "  PRIMARY KEY (user_id, watched_at)\n"
                        ") WITH CLUSTERING ORDER BY (watched_at DESC);\n"
                        "\n"
                        "-- Distributed: sharded by user_id"
                    ),
                },
                {"type": "h3", "text": "Sharding Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>MySQL (videos):</strong> shard by <code>video_id</code> hash; ~10–20 shards (growth headroom)",
                        "<strong>Cassandra (comments):</strong> shard by <code>video_id</code>; each node replicates 3 copies",
                        "<strong>Consistency:</strong> MySQL = strong; Cassandra = eventual (acceptable for comments)",
                    ],
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Video Search",
            "subtitle": "Elasticsearch, ranking, autocomplete",
            "blocks": [
                {"type": "h3", "text": "Full-Text Search with Elasticsearch"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Index:</strong> video metadata (title, description, tags, category)",
                        "<strong>Indexing latency:</strong> ~30 seconds (near-real-time); updated via Kafka topic",
                        "<strong>Sharding:</strong> 10 primary shards + 2 replicas per shard",
                        "<strong>Typical query:</strong> <code>'python programming'</code> → ranked by relevance, upload date, popularity",
                    ],
                },
                {"type": "h3", "text": "Search Ranking Formula"},
                {
                    "type": "code",
                    "text": (
                        "score(video) =\n"
                        "    TF-IDF(query, title)        × 0.40\n"
                        "  + TF-IDF(query, description)  × 0.20\n"
                        "  + BM25 (query, tags)          × 0.20\n"
                        "  + popularity_score(view_count, likes) × 0.15\n"
                        "  + recency_boost(1 - age_in_days / 365)\n"
                        "\n"
                        "# Results sorted by score DESC, with a freshness boost for recent videos."
                    ),
                },
                {"type": "h3", "text": "Autocomplete / Suggestions"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Data source:</strong> top 1M search queries (aggregated from analytics)",
                        "<strong>Prefix tree (trie):</strong> stores common query prefixes with hit counts",
                        "<strong>Latency:</strong> &lt;100 ms (p99); served from Redis + local cache",
                        "<strong>Updates:</strong> rebuilt hourly from query logs",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Recommendation Engine",
            "subtitle": "Two-tower, collaborative filtering",
            "blocks": [
                {"type": "h3", "text": "Two-Tower Architecture"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Tower 1 (Candidate Generation):</strong> fast, coarse-grained; retrieves ~1000 candidate videos",
                        "<strong>Tower 2 (Ranking):</strong> slow, fine-grained; re-ranks the top 100 with a deep model",
                        "<strong>Advantage:</strong> separates scale (Tower 1) from quality (Tower 2)",
                    ],
                },
                {"type": "h3", "text": "Candidate Generation (Tower 1)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Method:</strong> collaborative filtering (user → user or item → item similarity)",
                        "<strong>Implementation:</strong> user-video embedding space (Word2Vec-style on watch history)",
                        "<strong>Lookup:</strong> nearest-neighbour search in embedding space (Faiss / ScaNN ANN library)",
                        "<strong>Latency:</strong> &lt;50 ms (cached results)",
                    ],
                },
                {"type": "h3", "text": "Ranking (Tower 2)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Model:</strong> deep neural network (user context + video features → CTR probability)",
                        "<strong>Features:</strong> watch history, user profile, video popularity, recency, seasonality",
                        "<strong>Output:</strong> click-through rate (CTR) prediction; rank by expected CTR",
                        "<strong>Latency:</strong> &lt;200 ms for 100 videos via batch scoring",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Latency budget",
                    "body": (
                        "Recommendation latency target: <strong>&lt;500 ms (p99)</strong>. "
                        "Trade-off: faster = fewer candidates, lower quality. The two-tower split "
                        "buys you both — Tower 1 prunes 10⁹ items down to ~1000 cheaply, Tower 2 "
                        "spends its budget on the survivors."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Comments & Engagement",
            "subtitle": "Threading, reply-to, pagination",
            "blocks": [
                {"type": "h3", "text": "Comment Storage Architecture"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Database:</strong> Cassandra (distributed, write-optimised)",
                        "<strong>Sharding:</strong> by <code>video_id</code>; allows efficient range queries (recent comments first)",
                        "<strong>Denormalisation:</strong> store comment + author info in one row (avoid joins)",
                        "<strong>Replication:</strong> 3 copies; quorum reads (2) + writes (2) for consistency",
                    ],
                },
                {"type": "h3", "text": "Comment Thread Model"},
                {
                    "type": "code",
                    "text": (
                        "Top-level comment row:\n"
                        "  comment_id   : unique\n"
                        "  video_id     : sharding key\n"
                        "  author_id    : who wrote\n"
                        "  text         : comment body\n"
                        "  created_at   : timestamp\n"
                        "  reply_count  : cached counter\n"
                        "  like_count   : cached counter\n"
                        "\n"
                        "Replies stored in a separate table:\n"
                        "  reply_id\n"
                        "  parent_comment_id  : foreign key\n"
                        "  author_id, text, created_at, like_count"
                    ),
                },
                {"type": "h3", "text": "Pagination & Sorting"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Top comments:</strong> sorted by <code>like_count</code> (cached in Redis); refreshed every 5 min",
                        "<strong>Recent comments:</strong> sorted by <code>created_at DESC</code> (native Cassandra ordering)",
                        "<strong>Cursor pagination:</strong> use <code>(last_comment_id, limit)</code> for stability",
                        "<strong>Latency:</strong> &lt;100 ms for 20 comments per page",
                    ],
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Caching Strategy",
            "subtitle": "Multi-layer cache hierarchy",
            "blocks": [
                {"type": "h3", "text": "Cache Layers"},
                {
                    "type": "table",
                    "headers": ["Layer", "Technology", "TTL", "Hit Rate", "Use Case"],
                    "rows": [
                        ["L1 Browser",     "LocalStorage / IndexedDB", "1–7 days", "90%+",
                         "Manifest, segment cache"],
                        ["L2 CDN Edge",    "Memcached / in-memory",    "1–7 days", "95%+",
                         "Popular segment cache"],
                        ["L3 Regional",    "Memcached cluster",        "1–7 days", "95%+",
                         "Fallback for edge miss"],
                        ["L4 Application", "Redis (in-process)",       "1 hour",   "98%+",
                         "Metadata, session, counters"],
                        ["L5 Database",    "MySQL / Cassandra",        "N/A",      "N/A",
                         "Source of truth"],
                    ],
                },
                {"type": "h3", "text": "Cache Invalidation Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>TTL-based:</strong> most common; safe but may serve stale data",
                        "<strong>Event-driven:</strong> publish to Kafka when metadata updated; subscribers invalidate",
                        "<strong>Hybrid:</strong> short TTL (5–10 min) + event-based invalidation for critical data",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Cache stampede",
                    "body": (
                        "If a popular item expires, many requests hit the database simultaneously. "
                        "Mitigation: <strong>probabilistic early expiration</strong> (refresh "
                        "before TTL with probability that grows as TTL approaches) or "
                        "<strong>distributed locking</strong> so only one replica refills the entry."
                    ),
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Failure Modes & Resilience",
            "subtitle": "Degradation, fallbacks, SLO targets",
            "blocks": [
                {"type": "h3", "text": "Key Failure Scenarios"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Database shard down:</strong> replica takes over (RTO &lt;10s); alert ops team",
                        "<strong>CDN PoP offline:</strong> Geo-DNS reroutes traffic to next-nearest PoP; users see &lt;200 ms latency bump",
                        "<strong>Transcoding cluster overloaded:</strong> queue uploads; SLA slips to 8–12 hours (acceptable)",
                        "<strong>Streaming Service degradation:</strong> fall back to origin pull (slower but available); CDN load increases",
                        "<strong>Search outage:</strong> disable search UI; show trending videos instead",
                        "<strong>Recommendation model stale:</strong> use fallback heuristic (popular-by-category)",
                    ],
                },
                {"type": "h3", "text": "Circuit Breaker Pattern"},
                {
                    "type": "code",
                    "text": (
                        "if (search_service.failures > 10 in 30s) {\n"
                        "    circuit_breaker.trip()\n"
                        "    return fallback_heuristic()   # popular videos\n"
                        "    alert(\"Search service unhealthy\")\n"
                        "}\n"
                        "\n"
                        "// Retry with exponential backoff\n"
                        "for (attempt = 1 to 5) {\n"
                        "    wait(100ms * 2^attempt)\n"
                        "    if (search_service.health_check()) {\n"
                        "        circuit_breaker.reset()\n"
                        "        break\n"
                        "    }\n"
                        "}"
                    ),
                },
                {"type": "h3", "text": "SLO Targets"},
                {
                    "type": "table",
                    "headers": ["Service", "Latency (p99)", "Availability"],
                    "rows": [
                        ["Streaming API",     "&lt;100 ms", "99.99%"],
                        ["Upload Service",    "&lt;500 ms", "99.9%"],
                        ["Search",            "&lt;150 ms", "99.9%"],
                        ["Recommendations",   "&lt;500 ms", "99.95%"],
                        ["CDN Segment Fetch", "&lt;50 ms",  "99.99%"],
                    ],
                },
            ],
        },
        # ---- 15 ------------------------------------------------------
        {
            "num": "15",
            "title": "Trade-Offs & Design Decisions",
            "subtitle": "Decisions and rationale",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Decision", "Choice", "Trade-off"],
                    "rows": [
                        ["Consistency model",
                         "MySQL (strong) for videos / users; Cassandra (eventual) for comments",
                         "Video metadata must be consistent (avoid serving mismatched manifests). "
                         "Comments tolerate eventual consistency; MySQL is slower to write but "
                         "guarantees correctness."],
                        ["Encoding",
                         "Asynchronous (queue-based) transcoding",
                         "Encoding 1 TB takes 4 hours; blocking the user on a sync encode is "
                         "unacceptable. Users see a 'processing' state and can watch a lower "
                         "rung once the first variant finishes."],
                        ["Transcoding topology",
                         "Distributed (workers in multiple regions)",
                         "Reduces latency for CDN warm-up; isolates regional failures; load-balanced "
                         "across geographies. Cost is operational complexity (regional coordination, "
                         "data transfer) — worth it at scale."],
                        ["Codec strategy",
                         "Multi-codec (H.264 primary, VP9 secondary, HEVC for Apple)",
                         "Device compatibility plus bandwidth savings (VP9 ~30% less, HEVC ~40% "
                         "less). Cost is 3× storage &amp; encoding — justified by bandwidth savings "
                         "on popular content."],
                        ["Read / write split",
                         "CDN + Streaming Service for reads; Upload + Transcode for writes",
                         "Lets each side scale independently. Tens of millions of concurrent "
                         "viewers vs. single-digit upload QPS — sharing infrastructure would "
                         "force one side to over-provision."],
                        ["Comment ordering",
                         "Top comments cached (Redis, 5 min); recent comments native Cassandra order",
                         "Two read patterns, two indices. Top comments are read-heavy and tolerate "
                         "5-min staleness; recent comments need real-time freshness."],
                    ],
                },
            ],
        },
        # ---- 16 ------------------------------------------------------
        {
            "num": "16",
            "title": "Interview Playbook",
            "subtitle": "How to ace the discussion",
            "blocks": [
                {"type": "h3", "text": "Opening (First 5 Minutes)"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Clarify scope:</strong> 'Are we designing upload, playback, or both? What about live?'",
                        "<strong>Estimate scale:</strong> '2B users, 500 hours/min upload, 1B hours/day watched.'",
                        "<strong>State assumptions:</strong> 'I'll focus on on-demand playback; we can discuss live as a follow-up.'",
                    ],
                },
                {"type": "h3", "text": "Architecture Design (Next 15–20 Minutes)"},
                {
                    "type": "numbered",
                    "items": [
                        "Draw high-level diagram: <code>client → CDN → API → services → databases</code>",
                        "Separate <strong>read path</strong> (CDN + streaming) from <strong>write path</strong> (upload + transcode)",
                        "Explain the core trade-off: write-once, read-many → optimise for playback latency",
                        "Name key components: API gateway, upload service, streaming service, transcoding, message queue",
                        "Database choices: MySQL for metadata (consistency), Cassandra for comments (scale)",
                    ],
                },
                {"type": "h3", "text": "Deep Dives (Next 15 Minutes — Interviewer's Choice)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Upload:</strong> TUS protocol, chunking, resumability, deduplication",
                        "<strong>Streaming:</strong> HLS / DASH, ABR algorithms (BOLA), CDN cache hierarchy",
                        "<strong>Transcoding:</strong> codec comparison, resolution ladder, cost optimisation, parallel workers",
                        "<strong>Search:</strong> Elasticsearch, ranking formula, autocomplete, prefix trie",
                        "<strong>Recommendations:</strong> two-tower model, candidate generation, ranking model, CTR prediction",
                    ],
                },
                {"type": "h3", "text": "Resilience & Trade-Offs (Final 5–10 Minutes)"},
                {
                    "type": "numbered",
                    "items": [
                        "Discuss failure modes: CDN down, database shard down, transcoding overload",
                        "Explain fallback strategies: circuit breakers, degraded modes, SLO-based prioritisation",
                        "Compare trade-offs: strong vs eventual consistency, sync vs async, multi-codec vs single",
                    ],
                },
                {"type": "h3", "text": "Common Pitfalls"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Not clarifying scope:</strong> treating live and on-demand the same (very different!)",
                        "<strong>Overcomplicating early:</strong> jumping to database sharding before discussing API design",
                        "<strong>Ignoring the CDN:</strong> assuming all content from origin misses ~90% of the optimisation",
                        "<strong>Single codec:</strong> ignoring the bandwidth savings from VP9 / HEVC",
                        "<strong>No monitoring:</strong> failing to mention SLOs, metrics, or alerting",
                        "<strong>Unit confusion:</strong> mixing hours-per-day with seconds-per-day, or hours with minutes — "
                        "always carry units through the math (the corrected concurrent-viewer and "
                        "upload figures in §03 demonstrate why)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "End strong",
                    "body": (
                        "Mention one recent innovation (e.g., 'I'd explore AV1 for premium content "
                        "if encoding cost improves') or a metric you'd track (e.g., 'I'd monitor "
                        "cache hit ratio by region to optimise CDN warm-up')."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorise These Numbers",
                    "body": (
                        "Uploads: <strong>180K videos/day</strong> &nbsp;·&nbsp; "
                        "Raw ingest: <strong>30 TB/day</strong> &nbsp;·&nbsp; "
                        "Transcoded: <strong>~300 TB/day</strong> → <strong>328 PB/yr</strong> (3×) &nbsp;·&nbsp; "
                        "Concurrent viewers: <strong>~41.7M</strong> &nbsp;·&nbsp; "
                        "CDN egress: <strong>~83 Tbps</strong> avg / <strong>~170 Tbps</strong> peak &nbsp;·&nbsp; "
                        "Origin pull: <strong>~4 Tbps</strong> &nbsp;·&nbsp; "
                        "Edge hit rate: <strong>95%+</strong>."
                    ),
                },
            ],
        },
    ],
}
