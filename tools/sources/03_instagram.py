"""Source for `03 - Instagram.pdf` (regenerated; bandwidth math fixed; hybrid fan-out math added)."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Instagram",
    "subtitle": "distributed photo-sharing platform at massive scale",
    "read_time": "~ 35 minute read",
    "short_title": "Design Instagram",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Statement",
            "subtitle": "Define the scope and constraints",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Build a photo-sharing platform — <strong>Instagram</strong> — where users upload, "
                        "share, and discover photos and videos in real-time at billion-user scale. The "
                        "design must handle uploads, personalised feeds, Stories, search, and "
                        "notifications without breaking under fan-out load."
                    ),
                },
                {"type": "h3", "text": "Key Features"},
                {
                    "type": "bullets",
                    "items": [
                        "Users upload photos/videos and compose captions with hashtags + location",
                        "Users follow others; see a personalised feed ranked by relevance",
                        "Like, comment, share — engagement primitives drive ranking",
                        "Stories — ephemeral 24-hour content with automatic TTL",
                        "Search by hashtags, usernames, captions",
                        "Explore — trending content surfaced algorithmically",
                        "Notifications — likes, comments, follows, mentions",
                    ],
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Scope?", "Photos + videos + Stories; DMs out of scope for MVP"],
                        ["Scale?", "500M DAU, 100M photos/day"],
                        ["Geography?", "Global; multi-region active-active reads"],
                        ["Latency?", "Feed load &lt; 2s; upload acknowledged &lt; 5s"],
                        ["Resolution?", "Original + 3 thumbnail variants (320, 640, 1080)"],
                        ["Retention?", "Photos kept indefinitely; Stories auto-expire at 24h"],
                        ["Real-time?", "Notifications &lt; 1s; feed eventually consistent"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Assumption",
                    "body": (
                        "We design for <strong>500M DAU</strong>, <strong>100M photos/day</strong>, "
                        "global scale, &lt; 2s feed latency, real-time notifications. Everything else "
                        "follows from those four numbers."
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
                    "type": "bullets",
                    "items": [
                        "<strong>Upload:</strong> photos/videos with caption, location, hashtags",
                        "<strong>Feed:</strong> personalised home feed based on follows + ranking",
                        "<strong>Engagement:</strong> like, unlike, comment, share",
                        "<strong>Search:</strong> by hashtag, username, caption text",
                        "<strong>Stories:</strong> ephemeral 24h content with view receipts",
                        "<strong>Social graph:</strong> follow / unfollow; mutual-follow reciprocity",
                        "<strong>Notifications:</strong> push for likes, comments, follows, mentions",
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Availability", "99.9% uptime (≈ 4.3 min/month downtime)"],
                        ["Latency", "Feed &lt; 2s p99; photo upload ack &lt; 5s"],
                        ["Durability", "11 nines on photos (S3); zero loss of user data"],
                        ["Consistency", "Eventual for feed; strong for user/auth/payment"],
                        ["Throughput", "100M photos/day; ~29K feed reads/sec sustained"],
                        ["Scalability", "Handle 10× growth without redesign"],
                        ["Cost", "Optimise for storage + egress (the dominant line items)"],
                        ["Security", "Auth, encryption-in-transit, rate limiting, abuse prevention"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Availability vs. Consistency",
                    "body": (
                        "Feed service is eventually consistent — a stale read that misses the very "
                        "latest post for a few seconds is fine. Account, auth, and payment data are "
                        "strongly consistent: you cannot show a user the wrong balance or the wrong "
                        "phone number even briefly."
                    ),
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "Math for scale",
            "blocks": [
                {"type": "h3", "text": "Traffic Estimates"},
                {
                    "type": "bullets",
                    "items": [
                        "DAU: <strong>500M</strong>",
                        "Uploads: <strong>100M photos/day</strong>",
                        "Average feeds viewed per user per day: <strong>5</strong>",
                        "Feed read QPS: 500M × 5 / 86,400 sec = <strong>28,935 ≈ 29K reads/sec</strong>",
                        "Upload QPS: 100M / 86,400 = <strong>1,157 ≈ 1.16K uploads/sec</strong>",
                        "Like/comment QPS: ~10× upload rate ≈ <strong>12K writes/sec</strong> (engagement)",
                    ],
                },
                {"type": "h3", "text": "Storage Estimates"},
                {
                    "type": "bullets",
                    "items": [
                        "Average photo size (compressed original): <strong>200 KB</strong>",
                        "Daily raw uploads: 100M × 200 KB = <strong>20 TB/day</strong>",
                        "Variants (3 thumbnails @ 30/60/120 KB ≈ 210 KB extra): <strong>~3× multiplier → ~60 TB/day all-in</strong>",
                        "Annual storage (with variants): 60 TB × 365 = <strong>~22 PB/year</strong>",
                        "5-year corpus: <strong>~110 PB</strong> on S3 (Standard + Glacier tiering)",
                    ],
                },
                {"type": "h3", "text": "Bandwidth Estimates (recomputed)"},
                {
                    "type": "bullets",
                    "items": [
                        "Average rendered photo size on the wire (resized + compressed): <strong>100 KB</strong>",
                        "Daily feed photo loads: 500M DAU × 5 feeds × ~10 photos = <strong>25B images/day</strong>",
                        "Outbound egress: 25B × 100 KB = <strong>2.5 PB/day ≈ 231 Gbps average</strong>",
                        "Inbound (uploads): 100M × 200 KB = 20 TB/day = <strong>~1.85 Gbps average</strong>",
                        "Peak (3× diurnal skew): <strong>~700 Gbps egress, ~5.5 Gbps ingress</strong>",
                        "<strong>CDN absorbs ≥ 95%</strong> of egress at the edge → origin pull ≈ 12 Gbps average",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Bandwidth — Watch Your Units",
                    "body": (
                        "An earlier rev of this guide quoted 2.3 Gbps egress. That number divided "
                        "bytes by seconds and forgot the ×8 to get bits, so it was off by ~10×. "
                        "Real number: 250 TB/day × 8 / 86,400 ≈ <strong>23 Gbps</strong> at "
                        "10 photos/feed × 100 KB; at 25B images/day it's <strong>~231 Gbps</strong>. "
                        "Always sanity-check Gbps vs. GB/s — they differ by a factor of 8."
                    ),
                },
                {"type": "h3", "text": "Storage Strategy"},
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Where Each Byte Lives",
                    "body": (
                        "Originals → <strong>S3</strong> (durable, cheap-ish at scale). "
                        "Thumbnails → <strong>CDN edges</strong> (fast serving). "
                        "User/post metadata → <strong>MySQL</strong> (sharded, strong consistency). "
                        "Feed timelines + follows → <strong>Cassandra</strong> (wide rows, eventual). "
                        "Hot reads → <strong>Redis</strong>. "
                        "Search → <strong>Elasticsearch</strong>. "
                        "Async work → <strong>Kafka</strong>."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers to Memorise",
                    "body": (
                        "<strong>500M</strong> DAU &nbsp;·&nbsp; <strong>100M</strong> photos/day "
                        "(1.16K/sec) &nbsp;·&nbsp; <strong>29K</strong> feed reads/sec &nbsp;·&nbsp; "
                        "<strong>20 TB/day</strong> raw, <strong>60 TB/day</strong> with variants "
                        "&nbsp;·&nbsp; <strong>~231 Gbps</strong> egress average, <strong>~700 Gbps</strong> peak "
                        "&nbsp;·&nbsp; <strong>110 PB</strong> over 5 years."
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
                        "Instagram is a layered service-oriented architecture. Clients hit a global "
                        "edge (CDN + load balancer), authenticate at an API gateway, then talk to "
                        "independent microservices — Upload, Feed, Search, Notifications. Each "
                        "service owns its primary store and communicates with siblings via Kafka "
                        "events. No service shares a database with another."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Top-level flow: clients hit the CDN/LB, auth at the gateway, microservices fan out to purpose-built data stores. Kafka decouples services for async work.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Clients"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Mobile [label="iOS / Android", fillcolor="#dbe6fb"];
        Web    [label="Web",          fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        CDN [label="CDN\n(photos, videos)", fillcolor="#cbeedf"];
        LB  [label="Global LB",             fillcolor="#cbeedf"];
        GW  [label="API Gateway\n(auth, rate-limit)", fillcolor="#cbeedf"];
    }
    subgraph cluster_svc {
        label="Microservices"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        Up   [label="Upload\nService",       fillcolor="#fff2c9"];
        Feed [label="Feed\nService",         fillcolor="#fff2c9"];
        Sea  [label="Search\nService",       fillcolor="#fff2c9"];
        Notif[label="Notification\nService", fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        SQL  [label="MySQL\n(users, posts)",   fillcolor="#ead7fb"];
        Cass [label="Cassandra\n(feed, follows, stories)", fillcolor="#ead7fb"];
        Redis[label="Redis\n(hot cache)",      fillcolor="#ead7fb"];
        S3   [label="S3\n(media)",             fillcolor="#ead7fb"];
        ES   [label="Elasticsearch\n(search)", fillcolor="#ead7fb"];
        Kafka[label="Kafka\n(event bus)",      fillcolor="#fbd7c5"];
    }

    Mobile -> CDN [label="GET media"];
    Mobile -> LB  [label="API calls"];
    Web    -> CDN;
    Web    -> LB;
    LB -> GW;
    GW -> Up;
    GW -> Feed;
    GW -> Sea;
    GW -> Notif;

    Up   -> S3    [label="presigned PUT"];
    Up   -> SQL   [label="INSERT post"];
    Up   -> Kafka [label="post_created", style=dashed];

    Feed -> Cass  [label="timeline rows"];
    Feed -> Redis [label="feed cache"];
    Feed -> SQL   [label="post detail", style=dashed];

    Sea  -> ES    [label="query"];
    Sea  -> Redis [label="trending"];

    Notif -> Kafka [label="consume", style=dashed];
    Notif -> Redis [label="aggregate"];
}
""",
                },
                {"type": "h3", "text": "Layer Responsibilities"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Client SDK:</strong> retries, image compression before upload, prefetches the next 20 feed posts",
                        "<strong>CDN:</strong> serves all photo/video bytes; absorbs &gt; 95% of read egress",
                        "<strong>API Gateway:</strong> JWT auth, per-user/IP rate limits, request routing, request shaping",
                        "<strong>Upload Service:</strong> issues presigned S3 URLs; never sees the bytes itself",
                        "<strong>Feed Service:</strong> hybrid fan-out; reads pre-computed timelines from Cassandra/Redis",
                        "<strong>Search Service:</strong> Elasticsearch for full-text + tag queries; Redis for trending",
                        "<strong>Notification Service:</strong> consumes Kafka events; aggregates; pushes via APNs/FCM",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Design Philosophy",
                    "body": (
                        "Every service owns its own data store and communicates only via async "
                        "events on Kafka. No shared databases, no synchronous cross-service calls "
                        "in the write path. This is what lets Feed, Search, and Notifications "
                        "scale independently and survive each other's outages."
                    ),
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Photo Upload Pipeline",
            "subtitle": "Presigned URLs and async processing",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Uploading a 5–20 MB photo through your service tier is wasteful — the bytes "
                        "ride the request twice (client → API server → S3). The fix: <strong>presigned "
                        "S3 URLs</strong>. Server hands the client a time-limited URL; client PUTs "
                        "directly to S3; an S3 event triggers async processing."
                    ),
                },
                {"type": "h3", "text": "Step-by-Step Flow"},
                {
                    "type": "numbered",
                    "items": [
                        "Client calls <code>POST /upload</code> with metadata (caption, location, hashtags)",
                        "Upload Service returns a <strong>presigned S3 URL</strong>, valid for 15 minutes",
                        "Client PUTs the photo bytes directly to S3 — service tier never sees them",
                        "S3 fires an event: S3 → SNS → SQS → Kafka topic <code>media_uploaded</code>",
                        "Media Processor consumes the event; downloads the original from S3",
                        "Generates 3 thumbnails (320×320, 640×640, 1080×1080); stores variants in S3",
                        "CDN is pre-warmed by issuing a HEAD on each variant from edge POPs",
                        "DB row marked <code>status = ready</code>; <code>post_created</code> emitted to Kafka",
                        "Fan-Out Worker picks up the event; pushes into followers' feeds (see §07)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Why Presigned URLs?",
                    "body": (
                        "Offloads upload bandwidth from the service tier to S3 directly. At 1.16K "
                        "uploads/sec × 200 KB = 1.85 Gbps inbound, the API tier would burn an entire "
                        "service shard just shovelling bytes. Presigned URLs cut that to zero. Bonus: "
                        "S3 supports resumable multipart uploads — flaky mobile networks just retry."
                    ),
                },
                {"type": "h3", "text": "Media Processor — What It Actually Does"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Validate:</strong> EXIF strip, MIME sniff, dimension limits, NSFW classifier",
                        "<strong>Transcode:</strong> re-encode to optimised JPEG (mozjpeg) / HEIC / WebP",
                        "<strong>Thumbnails:</strong> 320 (grid), 640 (feed), 1080 (full-screen)",
                        "<strong>Video:</strong> ffmpeg → H.264 / H.265 with adaptive bitrate ladders",
                        "<strong>Perceptual hash:</strong> pHash for dedup + abuse detection",
                        "<strong>CDN warm:</strong> push to edges so first follower view is &lt; 50 ms",
                    ],
                },
                {
                    "type": "code",
                    "text": (
                        "# Issue a presigned PUT URL (server side, boto3)\n"
                        "url = s3.generate_presigned_url(\n"
                        "    'put_object',\n"
                        "    Params={\n"
                        "        'Bucket':      'ig-uploads',\n"
                        "        'Key':         f'raw/{user_id}/{post_id}.jpg',\n"
                        "        'ContentType': 'image/jpeg',\n"
                        "    },\n"
                        "    ExpiresIn=900,  # 15 minutes\n"
                        ")\n"
                        "return {'upload_url': url, 'post_id': post_id}"
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Database Design",
            "subtitle": "Polyglot persistence",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "No single store fits every access pattern. We pick one per pattern: "
                        "<strong>MySQL</strong> for users and posts (strong consistency, transactional "
                        "writes), <strong>Cassandra</strong> for follows and feed timelines (write-heavy, "
                        "wide rows, multi-region), <strong>Redis</strong> for hot reads, <strong>S3</strong> "
                        "for media bytes."
                    ),
                },
                {"type": "h3", "text": "users (MySQL — sharded by user_id)"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE users (\n"
                        "  user_id           BIGINT PRIMARY KEY,\n"
                        "  username          VARCHAR(255) UNIQUE NOT NULL,\n"
                        "  email             VARCHAR(255) UNIQUE NOT NULL,\n"
                        "  hashed_password   VARCHAR(255),\n"
                        "  avatar_url        VARCHAR(2048),\n"
                        "  bio               TEXT,\n"
                        "  follower_count    INT DEFAULT 0,\n"
                        "  following_count   INT DEFAULT 0,\n"
                        "  created_at        TIMESTAMP,\n"
                        "  updated_at        TIMESTAMP\n"
                        ");\n"
                        "-- Sharded: hash(user_id) % 256"
                    ),
                },
                {"type": "h3", "text": "posts (MySQL — sharded by user_id)"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE posts (\n"
                        "  post_id        BIGINT PRIMARY KEY,\n"
                        "  user_id        BIGINT NOT NULL,\n"
                        "  caption        TEXT,\n"
                        "  photo_urls     JSON,                 -- list of S3 keys\n"
                        "  location       VARCHAR(255),\n"
                        "  hashtags       JSON,                 -- list of strings\n"
                        "  like_count     INT DEFAULT 0,\n"
                        "  comment_count  INT DEFAULT 0,\n"
                        "  created_at     TIMESTAMP,\n"
                        "  INDEX idx_user_created (user_id, created_at DESC)\n"
                        ");\n"
                        "-- Co-locate a user's posts on the same shard for profile reads"
                    ),
                },
                {"type": "h3", "text": "follows + reverse_follows (Cassandra)"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE follows (\n"
                        "  follower_id   BIGINT,\n"
                        "  following_id  BIGINT,\n"
                        "  created_at    TIMESTAMP,\n"
                        "  PRIMARY KEY (follower_id, following_id)\n"
                        ");\n\n"
                        "CREATE TABLE reverse_follows (\n"
                        "  following_id  BIGINT,\n"
                        "  follower_id   BIGINT,\n"
                        "  created_at    TIMESTAMP,\n"
                        "  PRIMARY KEY (following_id, follower_id)\n"
                        ");\n"
                        "-- Two tables: 'who do I follow?' and 'who follows me?' both O(1)."
                    ),
                },
                {"type": "h3", "text": "feed_timeline (Cassandra — wide row per user)"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE feed_timeline (\n"
                        "  user_id        BIGINT,\n"
                        "  created_at     TIMESTAMP,\n"
                        "  post_id        BIGINT,\n"
                        "  post_user_id   BIGINT,\n"
                        "  PRIMARY KEY (user_id, created_at, post_id)\n"
                        ") WITH CLUSTERING ORDER BY (created_at DESC);\n"
                        "-- Denormalised: one row per (user, post) on each follower's timeline"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Denormalisation Trade-off",
                    "body": (
                        "Duplicating posts across all followers' feeds is <strong>write "
                        "amplification</strong>: a single post by a user with 1,000 followers "
                        "becomes 1,000 Cassandra inserts. We pay that write cost so the read path "
                        "is a single partition lookup. At 100:1 read:write ratios this is the right "
                        "trade — but it's the reason §07 exists."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "News Feed Architecture",
            "subtitle": "Hybrid push / pull fan-out",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Building a real-time feed for 500M users is the hardest problem in this "
                        "design. Two pure approaches exist — <strong>fan-out on write (push)</strong> "
                        "and <strong>fan-out on read (pull)</strong>. Neither works alone at the "
                        "Kardashian end of the follower distribution. Real systems use a hybrid."
                    ),
                },
                {"type": "h3", "text": "Push vs. Pull vs. Hybrid"},
                {
                    "type": "table",
                    "headers": ["Aspect", "Push (fan-out on write)", "Pull (fan-out on read)", "Hybrid (recommended)"],
                    "rows": [
                        ["Read latency", "Fast — feed pre-built", "Slow — merge per request",
                         "Fast for both paths"],
                        ["Write cost", "O(followers) per post", "O(1) per post",
                         "O(followers) for &lt; 1M; O(1) for ≥ 1M"],
                        ["Storage", "N copies (one per follower)", "1 copy (in postDB)",
                         "Mostly push, celebrities pull"],
                        ["Worst case", "Celebrity post → 100M writes", "Active user opens app → merge 1000s",
                         "Celebrity post: O(1); user open: merge ~50 celebs"],
                        ["Consistency", "Eventually consistent across followers", "Always fresh on read",
                         "Push lag &lt; 5s; pull always fresh"],
                    ],
                },
                {
                    "type": "diagram",
                    "caption": "Hybrid fan-out: regular users push into followers' Redis caches; celebrities skip the push and live in Cassandra postDB; the read path merges both at request time.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Post   [label="New Post\n(Upload Svc)", fillcolor="#dbe6fb"];
    Kafka  [label="Kafka\nnew_post topic", fillcolor="#fbd7c5"];
    FOW    [label="Fan-Out Worker", fillcolor="#fff2c9"];
    Decide [label="follower_count\n>= 1M ?", shape=diamond, fillcolor="#fff2c9", style="filled"];

    subgraph cluster_push {
        label="Push path (regular user, < 1M followers)"; style="rounded,dashed";
        color="#1f8359"; fontcolor="#1f8359";
        RedisR [label="Redis\nfollower feed caches\n(N writes)", fillcolor="#cbeedf"];
        CassT  [label="Cassandra\nfeed_timeline\n(N inserts)",   fillcolor="#cbeedf"];
    }

    subgraph cluster_pull {
        label="Pull path (celebrity, >= 1M followers)"; style="rounded,dashed";
        color="#b8862e"; fontcolor="#b8862e";
        CassP  [label="Cassandra\npostDB only", fillcolor="#fff2c9"];
    }

    Read   [label="Feed Read\n(GET /feed)", fillcolor="#dbe6fb"];
    Merge  [label="Merge:\npre-built feed\n+ celeb posts\n+ rank",
            fillcolor="#ead7fb"];
    RedisM [label="Redis\nmerged feed\n(TTL 10 min)", fillcolor="#cbeedf"];

    Post -> Kafka -> FOW -> Decide;
    Decide -> RedisR [label="no\n(push)"];
    Decide -> CassT  [label="no\n(durable)"];
    Decide -> CassP  [label="yes\n(skip fan-out)"];

    Read   -> RedisM [label="cache hit?", style=dashed];
    RedisM -> Merge  [label="miss", style=dashed];
    Merge  -> RedisR [label="pre-built rows"];
    Merge  -> CassP  [label="celeb posts\non-the-fly"];
}
""",
                },
                {"type": "h3", "text": "Hybrid Fan-Out Algorithm"},
                {
                    "type": "numbered",
                    "items": [
                        "User A posts → Upload Service emits <code>new_post</code> on Kafka",
                        "Fan-Out Worker consumes the event; reads A's <code>follower_count</code> from MySQL",
                        "If <strong>follower_count &lt; 1M</strong>: push (post_id, A, ts) into each follower's Redis feed list and Cassandra <code>feed_timeline</code>",
                        "If <strong>follower_count ≥ 1M</strong>: skip push entirely; the post is already in Cassandra <code>postDB</code>",
                        "On feed read: hit Redis for the pre-built rows from non-celeb follows; in parallel, query <code>postDB</code> for the celebs the user follows; merge by score; cache the merged result in Redis for 10 minutes",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Write-Amp vs. Merge-on-Read — the 1M Threshold",
                    "body": (
                        "Why is 1M the magic number? Run the math.<br><br>"
                        "<strong>Push cost for one celeb post (1M followers):</strong> 1,000,000 Redis "
                        "SETs + 1,000,000 Cassandra inserts. At typical 50µs Redis SET + 200µs Cassandra "
                        "write, that's <strong>~250 sec of cluster work</strong> for one post. With "
                        "100M posts/day total and assume 0.01% are celebs (10K celeb posts/day) at 1M "
                        "followers each → <strong>10B push ops/day</strong> just for celebrities, "
                        "saturating the Redis cluster.<br><br>"
                        "<strong>Pull cost (skip push, merge on read):</strong> 500M DAU × 5 feed loads × "
                        "~50 celebs followed avg = 125B partition reads/day on Cassandra postDB. "
                        "Each is a single-key wide-row read, ~1 ms with Redis cache in front (≥ 90% "
                        "hit rate after first read). Net: ~12.5B disk reads/day, well within a "
                        "Cassandra cluster's budget.<br><br>"
                        "<strong>Verdict:</strong> push wins by 10× for users below 1M followers; "
                        "pull wins by 100× above it. The 1M threshold is where the curves cross."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why Hybrid?",
                    "body": (
                        "1M is a breakpoint, not a magic number — it tracks the cost-cross-over above. "
                        "Regular users (≈ 99.99% of accounts) get push-based instant feeds. The ~50K "
                        "celebrities get pull. Result: 99.9% of reads are a single Redis lookup; the "
                        "rest pay one extra Cassandra round-trip and merge."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Feed Ranking & Personalization",
            "subtitle": "EdgeRank-style scoring",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Pure chronological feeds bury the good stuff. Instagram's ranker scores "
                        "posts on engagement, recency, relationship strength, and content type, "
                        "then re-orders the merged candidate set. Models train offline daily; "
                        "scoring at serve time is a fast linear combination."
                    ),
                },
                {"type": "h3", "text": "Ranking Signals"},
                {
                    "type": "table",
                    "headers": ["Signal", "Effect"],
                    "rows": [
                        ["Engagement", "Likes + 2× comments + 3× shares; normalised by follower count"],
                        ["Recency", "Exponential decay — newer wins; half-life ≈ 2 hours"],
                        ["Relationship strength", "How often this user interacts with the poster"],
                        ["Content type", "Video &gt; photo &gt; text; Stories scored separately"],
                        ["User preference", "ML learns hashtags / accounts / locations the user engages with"],
                        ["Time zone", "Boost posts from accounts active in overlapping windows"],
                    ],
                },
                {"type": "h3", "text": "EdgeRank-style Formula"},
                {
                    "type": "code",
                    "text": (
                        "score = (\n"
                        "    (1.0 + engagement_factor)\n"
                        "    * recency_decay(hours_since_post)\n"
                        "    * relationship_strength\n"
                        "    * content_type_boost\n"
                        ")\n\n"
                        "engagement_factor    = (likes + 2*comments + 3*shares) / max(100, follower_count)\n"
                        "recency_decay(h)     = 1.0 / (1 + 0.5 * h)\n"
                        "relationship_strength = log(1 + interaction_count) / 10\n"
                        "content_type_boost   = {'video': 1.3, 'photo': 1.0, 'carousel': 1.15}[type]\n\n"
                        "# Real production has 100+ signals fed to a GBDT or two-tower model"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Offline Training, Online Scoring",
                    "body": (
                        "Models train on the previous day's engagement logs in a Spark/PyTorch "
                        "pipeline. The serving tier loads frozen weights and computes a score in "
                        "&lt; 1 ms per candidate. Don't try to train online during feed reads — "
                        "the latency budget is too tight."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Stories Architecture",
            "subtitle": "Ephemeral content with TTL",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Stories are 24-hour photos/videos that auto-delete. They drive higher "
                        "engagement than feed posts — ephemeral FOMO works. The architecture is "
                        "deliberately distinct from the feed: different access pattern, different "
                        "lifecycle, no ranking."
                    ),
                },
                {"type": "h3", "text": "Design Decisions"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Separate Cassandra table</strong> with native TTL — rows tombstone after 86,400 sec",
                        "<strong>Partition by user_id, cluster by created_at DESC</strong> — fast retrieval of a user's recent stories",
                        "<strong>Denormalise</strong> the poster's avatar + name into the story row to avoid join on read",
                        "<strong>View receipts</strong> tracked in a counter table; visible only to the poster",
                        "<strong>Strict chronological order</strong> — no ranker; users expect linear time",
                        "<strong>CDN TTL = 24h</strong> — auto-evicts as Cassandra TTL expires",
                    ],
                },
                {"type": "h3", "text": "Cassandra Schema"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE stories (\n"
                        "  user_id      BIGINT,\n"
                        "  created_at   TIMESTAMP,\n"
                        "  story_id     BIGINT,\n"
                        "  media_url    VARCHAR(2048),\n"
                        "  caption      TEXT,\n"
                        "  poster_name  VARCHAR(255),    -- denormalised\n"
                        "  poster_avatar VARCHAR(2048),  -- denormalised\n"
                        "  PRIMARY KEY (user_id, created_at, story_id)\n"
                        ") WITH CLUSTERING ORDER BY (created_at DESC)\n"
                        "  AND default_time_to_live = 86400;  -- 24h auto-delete"
                    ),
                },
                {"type": "h3", "text": "View Tracking"},
                {
                    "type": "code",
                    "text": (
                        "-- Detailed who-viewed-what (visible to poster only)\n"
                        "CREATE TABLE story_views (\n"
                        "  story_id   BIGINT,\n"
                        "  viewed_at  TIMESTAMP,\n"
                        "  viewer_id  BIGINT,\n"
                        "  PRIMARY KEY (story_id, viewed_at, viewer_id)\n"
                        ") WITH default_time_to_live = 86400;\n\n"
                        "-- Fast view-count aggregate via Cassandra counter\n"
                        "CREATE TABLE story_view_counts (\n"
                        "  story_id   BIGINT PRIMARY KEY,\n"
                        "  view_count COUNTER\n"
                        ");"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why a Separate Table?",
                    "body": (
                        "Stories have <em>fundamentally</em> different access patterns: short TTL, "
                        "no engagement ranking, strict order, view receipts. Co-locating with feed "
                        "posts would force one schema to optimise for both — and lose on each. "
                        "Separate tables let each side pick the right partition key, TTL, and "
                        "compaction strategy."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Search & Explore",
            "subtitle": "Elasticsearch + trending",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Search hits Elasticsearch — full-text on captions, keyword on hashtags and "
                        "usernames, range filters on date and engagement. Explore ranks trending "
                        "hashtags via Redis sorted sets, refreshed hourly per region."
                    ),
                },
                {"type": "h3", "text": "Posts Index Mapping"},
                {
                    "type": "code",
                    "text": (
                        "PUT /posts\n"
                        "{\n"
                        "  \"mappings\": {\n"
                        "    \"properties\": {\n"
                        "      \"post_id\":    { \"type\": \"keyword\" },\n"
                        "      \"user_id\":    { \"type\": \"keyword\" },\n"
                        "      \"caption\":    { \"type\": \"text\", \"analyzer\": \"standard\" },\n"
                        "      \"hashtags\":   { \"type\": \"keyword\" },\n"
                        "      \"location\":   { \"type\": \"geo_point\" },\n"
                        "      \"created_at\": { \"type\": \"date\" },\n"
                        "      \"like_count\": { \"type\": \"integer\" }\n"
                        "    }\n"
                        "  }\n"
                        "}"
                    ),
                },
                {"type": "h3", "text": "Sample Query"},
                {
                    "type": "code",
                    "text": (
                        "GET /posts/_search\n"
                        "{\n"
                        "  \"query\": {\n"
                        "    \"bool\": {\n"
                        "      \"must\":   [{ \"match\": { \"caption\": \"pizza\" } }],\n"
                        "      \"filter\": [\n"
                        "        { \"terms\": { \"hashtags\": [\"#food\", \"#nyc\"] } },\n"
                        "        { \"range\": { \"created_at\": { \"gte\": \"now-30d\" } } }\n"
                        "      ]\n"
                        "    }\n"
                        "  },\n"
                        "  \"sort\": [{ \"like_count\": \"desc\" }],\n"
                        "  \"size\": 20\n"
                        "}\n\n"
                        "# 'pizza' posts tagged #food or #nyc in the last 30 days"
                    ),
                },
                {"type": "h3", "text": "Explore — Trending Hashtags"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Redis sorted set</strong> per region; score = view + like count",
                        "<strong>Hourly windows</strong> — separate keys per hour, easier rollups",
                        "<strong>Decay:</strong> yesterday's scores weighted ½, day-before ¼ — exponential",
                        "<strong>Personalisation:</strong> ZUNIONSTORE trending ∩ user interest vector",
                    ],
                },
                {
                    "type": "code",
                    "text": (
                        "# Increment trending score on each tag use\n"
                        "ZINCRBY trending:global:2026-05-06-10  1 \"#pizza\"\n"
                        "ZINCRBY trending:us-ny:2026-05-06-10   1 \"#nyc\"\n\n"
                        "# Top 20 trending globally right now\n"
                        "ZREVRANGE trending:global:2026-05-06-10 0 19 WITHSCORES\n\n"
                        "# Personalised: combine global trends with user interest vector\n"
                        "ZUNIONSTORE explore:user:123 2 \\\n"
                        "    trending:global:2026-05-06-10 user:123:interests \\\n"
                        "    WEIGHTS 0.6 0.4"
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Caching Strategy",
            "subtitle": "What, where, and TTL",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Caching is what makes 29K reads/sec affordable. We cache at four layers: "
                        "client SDK (prefetch the next 20 posts), CDN (photo bytes), Redis (metadata, "
                        "feed lists, trending), and the database query cache. Each has a different "
                        "TTL tuned to staleness tolerance."
                    ),
                },
                {"type": "h3", "text": "Cache Layers"},
                {
                    "type": "table",
                    "headers": ["Layer", "What", "Where", "TTL", "Reasoning"],
                    "rows": [
                        ["CDN", "Photo / video bytes", "Cloudflare / Akamai edge",
                         "7 days", "Reduce origin S3 egress by ~95%"],
                        ["Redis", "User profile (name, bio, counts)", "Redis cluster sharded by user_id",
                         "1 hour", "Profile updates rare; 1h staleness fine"],
                        ["Redis", "Feed timeline (list of post_ids)", "Redis cluster",
                         "10 min", "Feeds change fast; refresh often"],
                        ["Redis", "Post metadata (caption, like, comment counts)", "Redis cluster",
                         "30 min", "Engagement counts change frequently"],
                        ["Redis", "Trending hashtags", "Redis sorted sets per region",
                         "1 hour", "Trends shift hourly"],
                        ["Client SDK", "Pre-fetched next 20 feed items", "Mobile device",
                         "Session", "Reduce API calls during scroll"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Cache Invalidation Strategies",
                    "body": (
                        "<strong>TTL-based</strong> (simple, eventual): refresh every N minutes — "
                        "tolerable for everything we cache. "
                        "<strong>Event-based</strong> (accurate): on post update, publish to Kafka; "
                        "cache service deletes the affected keys. "
                        "<strong>Hybrid</strong> (both): event-based for accuracy, TTL as a backstop "
                        "if the event is dropped. We use hybrid for posts and profiles."
                    ),
                },
                {"type": "h3", "text": "Event-based Invalidation"},
                {
                    "type": "code",
                    "text": (
                        "# Post-update path emits invalidation event\n"
                        "POST /posts/{post_id}\n"
                        "  1. Update MySQL row\n"
                        "  2. Publish post_updated event to Kafka\n\n"
                        "# Cache invalidator consumer\n"
                        "for event in kafka_consumer:\n"
                        "    pid = event['post_id']\n"
                        "    redis.delete(f'post:meta:{pid}')\n"
                        "    redis.delete(f'post:comments:{pid}')\n"
                        "    # Affected feed caches expire on TTL — too many to enumerate"
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Notifications",
            "subtitle": "Likes, comments, follows, mentions",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Real-time notifications drive engagement. When User A likes User B's post, "
                        "B's phone should buzz within a second. The hard part isn't delivery — it's "
                        "<strong>aggregation and rate limiting</strong> so users aren't spammed."
                    ),
                },
                {"type": "h3", "text": "Notification Flow"},
                {
                    "type": "numbered",
                    "items": [
                        "User A likes B's post → Like Service emits <code>post_liked</code> on Kafka",
                        "Notification Service consumes; reads post → resolves author = B",
                        "Aggregator checks Redis: have we notified B about this post in the last hour?",
                        "Aggregate: <em>“Alice and 7 others liked your post”</em> instead of 8 separate pings",
                        "Dedupe: skip if B was already notified within 5 min",
                        "Hand off to APNs (iOS) / FCM (Android) push providers",
                        "User taps banner → app opens directly to the post",
                    ],
                },
                {"type": "h3", "text": "Aggregation Logic"},
                {
                    "type": "code",
                    "text": (
                        "class NotificationService:\n"
                        "    def on_like(self, ev: LikeEvent):\n"
                        "        post   = db.get_post(ev.post_id)\n"
                        "        author = post.user_id\n\n"
                        "        # pull existing aggregate window\n"
                        "        key = f'notif:{author}:post:{ev.post_id}'\n"
                        "        existing = redis.get(key)\n\n"
                        "        if existing and time.time() - existing.last_sent < 300:\n"
                        "            # within 5 min — append actor, defer\n"
                        "            existing.actors.append(ev.user_id)\n"
                        "            redis.set(key, existing, ex=3600)\n"
                        "            return\n\n"
                        "        agg = self.aggregate(ev, existing)\n"
                        "        self.send_to_apns(author, agg)\n"
                        "        redis.set(key, agg, ex=3600)"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Filtering & Rate Limiting",
                    "body": (
                        "Per-user mute lists in Redis prevent unwanted senders. Hard cap of "
                        "<strong>10 push notifications/min/user</strong> — past that, batch. "
                        "Notification fatigue is the leading cause of users disabling pushes "
                        "entirely; protect that channel."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Scalability & Sharding",
            "subtitle": "Horizontal scaling strategy",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "At 500M DAU, no single database fits. We shard everything horizontally and "
                        "co-locate related rows on the same shard so reads stay single-shard."
                    ),
                },
                {"type": "h3", "text": "Sharding Plan"},
                {
                    "type": "table",
                    "headers": ["Table", "Shard Key", "Shards", "Why"],
                    "rows": [
                        ["users", "hash(user_id) % 256", "256+",
                         "Even distribution; scale users independently"],
                        ["posts", "hash(user_id) % 256", "256+",
                         "Co-locate user's posts on same shard for profile view"],
                        ["follows", "hash(follower_id) % 256", "256+",
                         "Fast 'who do I follow?' lookup; reverse_follows mirrors"],
                        ["feed_timeline (Cass)", "hash(user_id) % 1024", "1024+",
                         "Hottest table — needs more shards for fan-out throughput"],
                        ["comments", "hash(post_id) % 512", "512+",
                         "Group all comments per post together"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Resharding Pain",
                    "body": (
                        "If we go from 256 → 512 shards via plain modulo, ~50% of keys move. "
                        "Use <strong>consistent hashing</strong> (Ketama / jump hash) so only "
                        "1/N keys migrate when a node is added — a 2× scale-out moves ~50% with "
                        "modulo but only ~6% with consistent hashing if doubling ring size."
                    ),
                },
                {"type": "h3", "text": "Replication"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>MySQL:</strong> 1 primary + 3 replicas per shard; semi-sync replication; ~100 ms lag",
                        "<strong>Cassandra:</strong> RF = 3 across AZs; LOCAL_QUORUM reads/writes",
                        "<strong>Redis:</strong> primary-replica pairs; AOF persistence; cross-AZ failover",
                        "<strong>S3:</strong> cross-region replication for the originals bucket",
                    ],
                },
                {"type": "h3", "text": "Connection Pooling"},
                {
                    "type": "code",
                    "text": (
                        "# Pool per shard — never open a fresh TCP for each query\n"
                        "pool = MySQLConnectionPool(\n"
                        "    pool_size=50,\n"
                        "    max_retries=3,\n"
                        "    retry_delay=0.1,\n"
                        ")\n\n"
                        "shard_id = hash(user_id) % 256\n"
                        "with pool.get(shard_id) as conn:\n"
                        "    return conn.execute(query)"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Global Distribution",
                    "body": (
                        "Primary writes pinned to one region per user (locality of access). Reads "
                        "served from the nearest regional replica. Cross-region replication via "
                        "Cassandra and S3 cross-region; lag &lt; 1 sec typical."
                    ),
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Failure Modes & Recovery",
            "subtitle": "Graceful degradation",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Distributed systems fail constantly. The design assumption is not that "
                        "components stay up — it's that any single failure degrades a feature, not "
                        "the whole site."
                    ),
                },
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Mitigation"],
                    "rows": [
                        ["MySQL shard down", "Reads/writes to that shard fail",
                         "Auto-promote replica (Orchestrator); reroute hot keys; ~30s RTO"],
                        ["Cassandra node down", "Up to 1/3 of feed reads slower",
                         "RF=3 + LOCAL_QUORUM tolerates 1 down; gossip detects within seconds"],
                        ["Redis cluster down", "5–10× MySQL/Cassandra load",
                         "Failover to replica; warm standby; degrade to direct DB read"],
                        ["CDN edge down", "+50 ms latency in that region",
                         "DNS failover to backup CDN; origin S3 absorbs the spike"],
                        ["API Gateway failure", "One instance loses traffic",
                         "Auto-scaling group; LB drops unhealthy node within 30s"],
                        ["Kafka broker down", "Async pipeline lags",
                         "RF=3 brokers; in-flight messages buffered up to 7 days"],
                        ["Elasticsearch down", "Search unavailable",
                         "Core features unaffected; show cached trending; ~30 min RTO"],
                        ["Network partition", "Cross-region writes blocked",
                         "Cassandra QUORUM-on-AZ; consistency over availability for the money path"],
                        ["Cascading failure", "Slow downstream collapses upstream",
                         "Circuit breaker — return cached feed when Feed Service slow"],
                        ["Data corruption", "Incorrect data persisted",
                         "Versioned backups every 6h; PITR within 7 days"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Circuit Breaker",
                    "body": (
                        "When a downstream service violates SLA (e.g. Feed Service p99 &gt; 2s), "
                        "the API Gateway opens a circuit breaker and returns cached feed instead "
                        "of waiting. The damaged service gets time to recover; users see slightly "
                        "stale data instead of a spinner. Half-open probes test recovery."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful Degradation Order",
                    "body": (
                        "If we have to drop features to keep the site up, the order is: "
                        "1) ranking falls back to chronological; "
                        "2) trending falls back to yesterday's snapshot; "
                        "3) notifications buffer to Kafka and drain late; "
                        "4) search returns 'temporarily unavailable'; "
                        "5) feed reads + photo views are <strong>never</strong> dropped."
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
                        ["Feed consistency", "Eventual",
                         "Stale reads briefly; fast reads. Strong consistency would slow the read path 5–10×."],
                        ["Fan-out model", "Hybrid push/pull",
                         "Push for &lt; 1M followers (fast reads), pull for celebrities (cheap writes). Pure push fails on celebrities; pure pull fails on regular users at read time."],
                        ["Storage layout", "Denormalised feed",
                         "Write amp (N copies) but O(1) reads. Normalised would force expensive joins per feed read."],
                        ["Cache TTL", "1h profiles, 10min feeds",
                         "Sweet spot between freshness and DB load. Short TTL → 5–10× DB pressure; long TTL → stale UX."],
                        ["Architecture", "Microservices",
                         "Independent scaling, fault isolation. Operational overhead vs. monolith — at this scale, services win."],
                        ["DB choice", "MySQL + Cassandra",
                         "MySQL for transactional rows, Cassandra for write-heavy wide rows. One store cannot do both well."],
                        ["Upload path", "Presigned S3 URLs",
                         "Bytes never touch the service tier. Saves ~1.85 Gbps ingress, ~$1M/year in NAT egress."],
                        ["Stories storage", "Separate Cassandra table with TTL",
                         "Different access pattern from feed; co-locating would compromise both schemas."],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "No Silver Bullet",
                    "body": (
                        "Every choice is a trade-off. The interview signal isn't whether you pick "
                        "the 'right' answer — it's whether you can articulate the trade and defend "
                        "it. Know your constraints (scale, consistency, latency, cost), then "
                        "argue from those."
                    ),
                },
            ],
        },
        # ---- 16 ------------------------------------------------------
        {
            "num": "16",
            "title": "Interview Playbook",
            "subtitle": "45-minute execution",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "45 minutes is tight. You must cover requirements, capacity, architecture, "
                        "the feed deep-dive, scalability, and trade-offs — without rushing any. "
                        "This playbook gives you a tested timing."
                    ),
                },
                {"type": "h3", "text": "Time Budget"},
                {
                    "type": "table",
                    "headers": ["Window", "Phase", "Goal"],
                    "rows": [
                        ["00:00–02:00", "Clarify requirements", "Pin down scope: photos vs. videos, DAU, real-time?"],
                        ["02:00–07:00", "Capacity estimation", "500M DAU → 29K QPS, 100M photos → 20 TB/day, 231 Gbps egress"],
                        ["07:00–20:00", "High-level architecture", "Boxes: client → CDN → LB → GW → services → data tier"],
                        ["20:00–35:00", "Deep dive on feed", "Push vs. pull, 1M threshold, hybrid math"],
                        ["35:00–40:00", "Remaining components", "Upload, search, notifications — quick passes"],
                        ["40:00–45:00", "Trade-offs + recovery", "Failure modes, sharding, consistency choices"],
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>“500M DAU × 5 feeds / 86,400 = 29K QPS”</strong> — capacity math, recited",
                        "<strong>“100M photos × 200 KB = 20 TB/day raw, ~110 PB over 5 years”</strong>",
                        "<strong>“Presigned URLs offload upload bandwidth from the service tier”</strong>",
                        "<strong>“Hybrid fan-out — push under 1M, pull over”</strong>",
                        "<strong>“Cassandra for fan-out wide rows, MySQL for transactional posts”</strong>",
                        "<strong>“Stories: separate table with native TTL = 86,400”</strong>",
                        "<strong>“CDN absorbs ≥ 95% of egress; origin pull ~12 Gbps”</strong>",
                        "<strong>“Eventual consistency for feed; strong for auth and money”</strong>",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: What if a regular user crosses 1M followers?</strong> A: A threshold service flips them to pull mode; their existing pre-built timelines stay valid for the next 24h, then the cache expires naturally.",
                        "<strong>Q: How do you handle a celebrity's celebrity?</strong> A: Same — pull. Their post-DB partition is read on demand. Redis caches the merged feed for 10 min.",
                        "<strong>Q: How do you scale beyond 256 shards?</strong> A: Consistent hashing minimises migration; resharding tool runs online; reads dual-write during cutover.",
                        "<strong>Q: What if Cassandra loses a partition?</strong> A: RF=3 + QUORUM survives one node; gossip detects within seconds; hinted handoff catches up.",
                        "<strong>Q: Why not exactly-once notifications?</strong> A: Cross-system exactly-once is unimplementable; we deliver at-least-once and dedupe at the receiver via event_id.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Numbers to Memorise",
                    "body": (
                        "<strong>500M</strong> DAU &nbsp;·&nbsp; "
                        "<strong>100M photos/day</strong> (1.16K/sec) &nbsp;·&nbsp; "
                        "<strong>29K</strong> feed reads/sec &nbsp;·&nbsp; "
                        "<strong>20 TB/day</strong> raw, <strong>60 TB/day</strong> with variants &nbsp;·&nbsp; "
                        "<strong>~231 Gbps</strong> egress, <strong>~1.85 Gbps</strong> ingress &nbsp;·&nbsp; "
                        "<strong>110 PB</strong> over 5 years &nbsp;·&nbsp; "
                        "<strong>1M-follower</strong> threshold for push/pull &nbsp;·&nbsp; "
                        "<strong>86,400 s</strong> Stories TTL."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "If You Get Stuck",
                    "body": (
                        "Don't panic. Restate the assumption you're working under. "
                        "“If celebs are 0.01% of users, push costs X; otherwise Y.” "
                        "Articulating the branch-point shows the interviewer you're thinking "
                        "about the cost surface, not memorising an answer."
                    ),
                },
            ],
        },
    ],
}
