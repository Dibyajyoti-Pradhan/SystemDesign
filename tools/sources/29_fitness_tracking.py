"""Source for `29 - Fitness Tracking.pdf` — Strava / Fitbit / Apple Health backend."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design a Fitness Tracking System",
    "subtitle": "Strava / Fitbit / Apple Health backend — wearables, time-series, social",
    "read_time": "~ 45 minute read",
    "short_title": "Fitness Tracking",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Statement",
            "subtitle": "What we are building",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Design the backend for a wearable fitness platform similar to "
                        "<strong>Strava</strong>, <strong>Fitbit</strong>, or the "
                        "<strong>Apple Health</strong> backend. The system ingests "
                        "high-frequency sensor streams (steps, heart rate, GPS), aggregates "
                        "them into daily / weekly / monthly summaries, surfaces insights "
                        "and challenges, supports a social activity feed, and integrates "
                        "two-way with Apple HealthKit and Google Fit."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["How many users?", "~500M registered, ~50M DAU sync"],
                        ["What sensors?", "HR every 5s, steps every 1s, GPS only during workouts"],
                        ["Sync model?", "Device → phone (BLE) → cloud (batched HTTP)"],
                        ["Retention?", "30d hot, 1y warm, lifetime cold (S3/Glacier)"],
                        ["Social?", "Friend graph, activity feed, kudos/comments, challenges"],
                        ["Integrations?", "HealthKit and Google Fit two-way sync"],
                        ["Privacy?", "Per-activity (private/friends/public) + GPS privacy zones"],
                        ["HIPAA?", "HIPAA-adjacent; only triggered if integrated with a provider"],
                    ],
                },
                {"type": "h3", "text": "Why this is interesting"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Bursty, not steady-state ingest</strong> — devices sync when phone gets connectivity, not in real time",
                        "<strong>Time-series at scale</strong> — billions of HR samples per day with strict retention tiers",
                        "<strong>Two-write surface</strong> — same data point can arrive from watch, phone sensor, and HealthKit",
                        "<strong>Sensitive geo data</strong> — GPS tracks reveal home/work; privacy zones are mandatory",
                        "<strong>Social + health</strong> — activity feed mechanics with auto-generated content (no user post)",
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
                    "headers": ["Capability", "Details"],
                    "rows": [
                        ["Sensor ingest", "Accept batched samples (HR, steps, GPS, sleep, calories) from phone"],
                        ["Workout records", "Start/stop a workout; persist GPS track + HR series + summary"],
                        ["Daily summary", "Steps, active minutes, calories, distance, sleep, resting HR"],
                        ["Aggregations", "Per-day at ingest; per-week and per-month rolled up nightly"],
                        ["Social feed", "Friends, follow graph, activity feed, kudos, comments"],
                        ["Challenges", "Weekly/monthly leaderboards (steps, distance) with prize tiers"],
                        ["Integrations", "Two-way sync with Apple HealthKit and Google Fit"],
                        ["Privacy zones", "Suppress GPS within radius of user-defined locations"],
                        ["Insights", "Trend deltas, training load, personal records, anomaly nudges"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Availability", "99.95% on read paths; 99.9% on ingest (offline-tolerant)"],
                        ["Ingest latency", "&lt;5 s p99 from phone POST to TSDB visibility"],
                        ["Read latency", "&lt;200 ms p99 for daily summary; &lt;500 ms for workout map"],
                        ["Durability", "11 nines on cold tier; 0 sample loss after phone ack"],
                        ["Throughput", "Peak ingest ~25 GB/s aggregate at commute hours"],
                        ["Privacy", "GPS encrypted at rest; per-user privacy zones enforced server-side"],
                        ["Eventual consistency", "Feed/leaderboard may lag &lt;30 s; summaries by next sync"],
                    ],
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "How big does this get",
            "blocks": [
                {"type": "h3", "text": "User and traffic"},
                {
                    "type": "bullets",
                    "items": [
                        "Registered users: <strong>500M</strong>",
                        "Daily syncing users (DAU): <strong>50M</strong>",
                        "Peak hour share: ~25% of DAU sync within a 2-hour commute window in any given timezone",
                        "Typical sync batch: ~5–15 minutes of buffered samples sent in one HTTP POST",
                    ],
                },
                {"type": "h3", "text": "Sample volume per device"},
                {
                    "type": "bullets",
                    "items": [
                        "Heart rate: 1 sample per <strong>5 s</strong> = 17,280 samples/day",
                        "Steps: 1 sample per <strong>1 s</strong> when moving (~12 active hours) ≈ 43,200 samples/day",
                        "GPS: only during workouts; ~1 Hz × ~45 min/day for active users ≈ 2,700 fixes/day",
                        "Other (sleep stage, calories, SpO2): ~5,000 samples/day",
                        "Total raw samples per active user: <strong>~70K/day</strong>",
                    ],
                },
                {"type": "h3", "text": "Bytes and aggregate ingest"},
                {
                    "type": "bullets",
                    "items": [
                        "Raw sample tuple uncompressed: ~24 B (timestamp + value + tags)",
                        "Daily uncompressed: 70K × 24 B ≈ <strong>1.7 MB/user/day</strong>",
                        "With time-series compression (delta-of-delta + Gorilla XOR) ~8× → <strong>~210 KB/user/day</strong>",
                        "Add workout media + metadata blobs → <strong>~14 MB/user/day</strong> total written incl. workout payloads",
                        "Aggregate steady: 50M × 14 MB ÷ 86,400 s ≈ <strong>8 GB/sec average</strong>",
                        "Peak commute hour multiplier ~3× → <strong>~25 GB/sec aggregate ingest peak</strong>",
                    ],
                },
                {"type": "h3", "text": "Storage tiering"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Hot 30 days online:</strong> 50M × 14 MB × 30 ≈ 21 PB raw → ~2.6 PB compressed in TSDB",
                        "<strong>Warm 1 year compressed:</strong> ~31 PB on cheaper tier (HDD-backed columnar)",
                        "<strong>Cold lifetime:</strong> S3 / Glacier; tens of PB per year of corpus growth",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "500M users · 50M DAU · ~14 MB/user/day · "
                        "<strong>~25 GB/s peak ingest</strong> · ~2.6 PB hot · 30d hot / 1y warm / lifetime cold."
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level Architecture",
            "subtitle": "End-to-end system overview",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The pipeline starts at a wearable that streams over BLE to the user's "
                        "phone. The phone app is the <strong>first durable buffer</strong> — it "
                        "collects samples for minutes to hours and POSTs batches to the Ingest "
                        "API when connectivity allows. From there, samples fan out to the "
                        "time-series store, the aggregator, the workout service, and the social "
                        "and integration services."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "End-to-end fitness platform: device → phone → batched ingest → fan-out into TSDB, aggregator, workouts, social, integrations.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_device {
        label="On-Body / On-Phone"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Watch [label="Wearable\n(HR 5s, steps 1s, GPS)", fillcolor="#dbe6fb"];
        Phone [label="Phone App\n(buffer + BLE sync)", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        LB    [label="Global LB\n+ Auth (mTLS / JWT)", fillcolor="#cbeedf"];
        Ingest[label="Ingest API\n(batched POST)",     fillcolor="#cbeedf"];
    }
    subgraph cluster_svc {
        label="Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        Agg   [label="Aggregator\n(daily summary)", fillcolor="#fff2c9"];
        WO    [label="Workout Service\n(GPX + HR series)", fillcolor="#fff2c9"];
        Soc   [label="Social Service\n(feed + kudos)",     fillcolor="#fff2c9"];
        Int   [label="Integration\n(HealthKit / Fit)",     fillcolor="#fff2c9"];
        Notif [label="Notifications\n(push + nudges)",     fillcolor="#fff2c9"];
        Lead  [label="Leaderboards\n(challenges)",         fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        TSDB  [label="Time-Series Store\n(Cassandra/Influx/Timescale)", fillcolor="#ead7fb"];
        PG    [label="Postgres\n(users, friends, devices)", fillcolor="#ead7fb"];
        Redis [label="Redis\n(leaderboards, hot reads)",   fillcolor="#ead7fb"];
        S3    [label="Object Store\n(GPX, raw blobs)",     fillcolor="#ead7fb"];
        K     [label="Kafka\n(samples + events)",          fillcolor="#fbd7c5"];
    }

    Watch -> Phone [label="BLE"];
    Phone -> LB    [label="HTTPS batch\n(retry, gzip)"];
    LB    -> Ingest;
    Ingest -> K   [label="raw samples"];
    K -> TSDB     [label="bulk write"];
    K -> Agg      [label="stream"];
    K -> WO       [label="workout chunks"];
    K -> Int      [label="cross-source\nreconcile"];
    Agg -> PG     [label="daily summary"];
    WO  -> S3     [label="GPX blob"];
    WO  -> PG     [label="metadata"];
    Soc -> PG     [label="feed posts"];
    Soc -> Redis  [label="hot timelines"];
    Lead -> Redis [label="ZADD score"];
    Notif -> Phone [label="push (APNs/FCM)", style=dashed];
    Phone -> Int  [label="HealthKit/Fit\nback-channel", style=dashed, color="#1f8359"];
}
""",
                },
                {"type": "h3", "text": "Component responsibilities"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Phone app:</strong> the canonical buffer; decodes BLE, deduplicates, batches, retries with exponential backoff",
                        "<strong>Ingest API:</strong> stateless, validates schema and auth, writes raw to Kafka before ack — never blocks on TSDB",
                        "<strong>Kafka:</strong> the durable spine; partitioned by user_id so a single consumer sees a user's stream in order",
                        "<strong>Time-series store:</strong> Cassandra or Influx or TimescaleDB — keeps 30d hot online",
                        "<strong>Aggregator:</strong> stream job that materialises per-day summaries on the fly",
                        "<strong>Workout service:</strong> upgrades a stream chunk into a structured workout document with simplified GPX",
                        "<strong>Social service:</strong> friend graph, fan-out, auto-generated activity posts, privacy filter",
                        "<strong>Integration service:</strong> HealthKit / Google Fit pairing, conflict resolution across sources",
                        "<strong>Leaderboards:</strong> Redis sorted sets, expire weekly/monthly",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Sync Model — Device → Phone → Cloud",
            "subtitle": "Bursty, offline-tolerant batching",
            "blocks": [
                {"type": "h3", "text": "Three-hop journey"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Sensor → wearable RAM:</strong> on-watch ring buffer of last few hours",
                        "<strong>Wearable → phone (BLE):</strong> opportunistic, when the phone is in range",
                        "<strong>Phone → cloud (HTTPS batch):</strong> when WiFi/cellular is healthy",
                        "Each hop is best-effort with idempotent retries; only the cloud write is the durable commit",
                    ],
                },
                {"type": "h3", "text": "Why batched, not streaming"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Battery:</strong> a radio on for 1 second of bulk transfer beats 60s of trickling",
                        "<strong>Connectivity:</strong> users spend hours offline (gym, subway, flights) — a streaming socket would just churn",
                        "<strong>Cost:</strong> each request has fixed overhead — 5–15 minute batches cut request count by orders of magnitude",
                        "<strong>Compression:</strong> larger payloads compress better (~8× on time-series)",
                    ],
                },
                {
                    "type": "diagram",
                    "caption": "Sample-batch ingest path: device buffer → phone aggregator → bulk-write to TSDB → trigger daily summary job.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Sensor [label="Sensor (HR/steps/GPS)", fillcolor="#dbe6fb"];
    DevBuf [label="Device Ring Buffer\n(~hours)", fillcolor="#dbe6fb"];
    BLE    [label="BLE Sync\n(opportunistic)", fillcolor="#cbeedf"];
    PhoneBuf [label="Phone Aggregator\n(dedup + gzip)", fillcolor="#cbeedf"];
    Ingest [label="Ingest API\n(batched POST)", fillcolor="#fff2c9"];
    K      [label="Kafka\n(samples)", fillcolor="#fbd7c5"];
    TSDB   [label="TSDB Bulk Write", fillcolor="#ead7fb"];
    DailyJob [label="Daily Summary Job\n(materialise)", fillcolor="#ead7fb"];

    Sensor -> DevBuf;
    DevBuf -> BLE -> PhoneBuf;
    PhoneBuf -> Ingest [label="every 5–15 min\nor on WiFi"];
    Ingest -> K;
    K -> TSDB;
    TSDB -> DailyJob [label="trigger\non new chunk"];
}
""",
                },
                {"type": "h3", "text": "Idempotency and dedup"},
                {
                    "type": "bullets",
                    "items": [
                        "Each sample carries a stable <code>(device_id, timestamp, metric)</code> key — re-sending is a no-op",
                        "Phone tags each batch with a <code>batch_uuid</code> the cloud uses to short-circuit replays",
                        "Server stores <code>last_synced_at</code> per device — phone can ask “what's my high-water mark?” after reinstall",
                    ],
                },
                {"type": "h3", "text": "Backfill on reconnect"},
                {
                    "type": "bullets",
                    "items": [
                        "Phone offline for days → device buffer wraps; oldest samples dropped at the device layer",
                        "If phone is online but cloud is unreachable, phone keeps batches in SQLite up to ~1 GB",
                        "On reconnect, phone uploads in chronological order, throttled to avoid swamping a freshly-recovered ingest tier",
                        "Server marks each backfilled day for <strong>re-aggregation</strong>: the daily summary is recomputed",
                    ],
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Time-Series Storage Choice",
            "subtitle": "Cassandra vs Influx vs Timescale for samples",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The time-series store is the load-bearing component: ~25 GB/s peak "
                        "ingest, billions of points per day, predictable per-user range scans, "
                        "and aggressive retention tiering. The three credible candidates are "
                        "<strong>Cassandra with TTL</strong>, <strong>InfluxDB</strong>, and "
                        "<strong>TimescaleDB</strong>."
                    ),
                },
                {"type": "h3", "text": "Comparison"},
                {
                    "type": "table",
                    "headers": ["Aspect", "Cassandra (with TTL)", "InfluxDB", "TimescaleDB"],
                    "rows": [
                        ["Write model", "LSM, partition by (user, day)", "TSM, time-bucketed", "Postgres + hypertable chunks"],
                        ["Throughput", "Excellent at very high write QPS", "Excellent for time-series writes", "Good; limited by Postgres write path"],
                        ["Compression", "Good with chunk-aligned tables (~5×)", "Best-in-class for samples (~10×)", "Native columnar compression on chunks (~8×)"],
                        ["Ad-hoc query", "Limited; pre-design partitions", "Flux/InfluxQL; flexible time-window", "Full SQL + joins to user metadata"],
                        ["Retention TTL", "Per-row TTL native", "Retention policy per bucket", "Drop old chunks (cheap)"],
                        ["Operational fit", "Battle-tested at PB scale (Strava-class)", "Purpose-built TSDB", "Familiar SQL ops"],
                        ["Cost shape", "Cheap on commodity SSD", "Cheap; vendor lock-in risk", "Mid; pays for SQL flexibility"],
                    ],
                },
                {"type": "h3", "text": "Recommendation"},
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Pick Cassandra for samples; Postgres/Timescale for metadata",
                    "body": (
                        "Use <strong>Cassandra (with per-row TTL)</strong> for the raw sample stream — "
                        "predictable partition design (<code>user_id, day_bucket</code>), excellent write throughput, "
                        "and TTL is free retention. Use <strong>Postgres or TimescaleDB</strong> for "
                        "user metadata, daily summaries, friend graph, and workout records — anything "
                        "queried by humans or joined to user data."
                    ),
                },
                {"type": "h3", "text": "Cassandra schema for samples"},
                {
                    "type": "code",
                    "text": (
                        "-- partition: one row per (user, day, metric); clustering by timestamp\n"
                        "CREATE TABLE samples (\n"
                        "    user_id      bigint,\n"
                        "    day_bucket   date,\n"
                        "    metric       text,        -- 'hr', 'steps', 'gps_lat', 'gps_lon', ...\n"
                        "    ts           timestamp,\n"
                        "    value        double,\n"
                        "    source       text,        -- 'watch','phone','healthkit','fit'\n"
                        "    PRIMARY KEY ((user_id, day_bucket, metric), ts)\n"
                        ") WITH CLUSTERING ORDER BY (ts ASC)\n"
                        "  AND default_time_to_live = 2592000   -- 30 days hot\n"
                        "  AND compression = {'class':'LZ4Compressor'};\n\n"
                        "-- workouts go in their own table for blob-style access\n"
                        "CREATE TABLE workouts (\n"
                        "    user_id        bigint,\n"
                        "    workout_id     timeuuid,\n"
                        "    started_at     timestamp,\n"
                        "    ended_at       timestamp,\n"
                        "    sport          text,\n"
                        "    summary        frozen<map<text,double>>,  -- distance, calories, ...\n"
                        "    gpx_blob_url   text,                       -- pointer to S3\n"
                        "    hr_series_url  text,                       -- compressed series in S3\n"
                        "    privacy        text,                       -- 'private'|'friends'|'public'\n"
                        "    PRIMARY KEY (user_id, workout_id)\n"
                        ") WITH CLUSTERING ORDER BY (workout_id DESC);"
                    ),
                },
                {"type": "h3", "text": "Per-sample row vs blob-per-day"},
                {
                    "type": "table",
                    "headers": ["Strategy", "Pros", "Cons"],
                    "rows": [
                        ["Per-sample row", "Easy ad-hoc query, simple ingest path", "Row overhead; bulkier on disk; index pressure"],
                        ["Blob-per-day per metric", "~10× smaller on disk; trivial range read", "Hard to update mid-day; batch must replace blob"],
                        ["Hybrid (chunk per hour)", "Compromise; small re-write window", "Two code paths; chunk boundary edge cases"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Hybrid in practice",
                    "body": (
                        "Most production fitness backends store per-sample rows in Cassandra for "
                        "the hot 30 days, then a nightly compactor rewrites finalised days into "
                        "compressed columnar blobs in object storage for the warm tier. The query "
                        "layer routes by age."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Aggregations & Daily Summary",
            "subtitle": "From raw samples to insights",
            "blocks": [
                {"type": "h3", "text": "Per-day rollup at ingest"},
                {
                    "type": "bullets",
                    "items": [
                        "Stream consumer reads from Kafka samples topic, partitioned by user",
                        "Maintains an <strong>in-memory per-user accumulator</strong> keyed by (user_id, day)",
                        "On a tumbling 1-minute window, flushes incremental updates to the daily-summary row in Postgres",
                        "Tracked metrics: total steps, active minutes, calories, distance, avg HR, max HR, resting HR proxy",
                        "Late-arriving samples (backfill) bump a <code>dirty</code> flag → recompute that day end-to-end",
                    ],
                },
                {"type": "h3", "text": "Sliding-window aggregation"},
                {
                    "type": "code",
                    "text": (
                        "# Stream consumer pseudo-code (Flink/Kafka Streams style)\n"
                        "def on_sample(user_id, day, metric, ts, value):\n"
                        "    state = state_store.get((user_id, day)) or empty_summary()\n"
                        "    if metric == 'steps':\n"
                        "        state.steps += value\n"
                        "        if value > 0:\n"
                        "            state.active_seconds.add(ts // 60)   # bitmap of active minutes\n"
                        "    elif metric == 'hr':\n"
                        "        state.hr_sum   += value\n"
                        "        state.hr_count += 1\n"
                        "        state.hr_max    = max(state.hr_max, value)\n"
                        "    elif metric == 'gps':\n"
                        "        state.distance_m += haversine(state.last_gps, value)\n"
                        "        state.last_gps    = value\n"
                        "    state_store.put((user_id, day), state)\n\n"
                        "# Every 60s flush dirty users to Postgres summary table\n"
                        "for (user_id, day), state in dirty_iter():\n"
                        "    pg.upsert('daily_summary', user_id, day, state.to_row())"
                    ),
                },
                {"type": "h3", "text": "Nightly weekly/monthly rollup"},
                {
                    "type": "bullets",
                    "items": [
                        "Off-peak (per timezone) cron pulls finalised daily rows from Postgres",
                        "Computes weekly_summary and monthly_summary; writes back to Postgres",
                        "Computes <strong>training-load</strong> and <strong>personal records</strong> deltas — feeds insights",
                        "Job is idempotent and cursor-based — restarting reprocesses only its range",
                    ],
                },
                {"type": "h3", "text": "daily_summary table"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE daily_summary (\n"
                        "    user_id          BIGINT,\n"
                        "    day              DATE,\n"
                        "    steps            INT,\n"
                        "    active_minutes   INT,\n"
                        "    distance_m       INT,\n"
                        "    calories         INT,\n"
                        "    hr_avg           SMALLINT,\n"
                        "    hr_max           SMALLINT,\n"
                        "    resting_hr       SMALLINT,\n"
                        "    sleep_minutes    INT,\n"
                        "    sources          TEXT[],     -- which providers contributed\n"
                        "    dirty            BOOLEAN DEFAULT FALSE,\n"
                        "    updated_at       TIMESTAMPTZ DEFAULT NOW(),\n"
                        "    PRIMARY KEY (user_id, day)\n"
                        ");\n"
                        "CREATE INDEX idx_dirty_days ON daily_summary(day) WHERE dirty;"
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Workouts — GPX Tracks & HR Series",
            "subtitle": "First-class structured records",
            "blocks": [
                {"type": "h3", "text": "Why workouts are different"},
                {
                    "type": "bullets",
                    "items": [
                        "Workouts have a <strong>begin/end boundary</strong> the user explicitly demarcated",
                        "They carry GPS — large per-event payload (a 1-hour run is ~3,600 fixes ≈ 50 KB compressed)",
                        "They are <strong>shared on the feed</strong> — the social product hangs off the workout",
                        "They get displayed on a map — geometry must render fast even on slow phones",
                    ],
                },
                {"type": "h3", "text": "Storage layout"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Metadata</strong> (sport, duration, distance, splits, sport-specific stats): Postgres row",
                        "<strong>Raw GPX</strong>: stored as compressed blob in S3, addressed by workout_id",
                        "<strong>Simplified track</strong> (for map display): generated server-side, cached in S3 too",
                        "<strong>HR series</strong>: dense per-second array, stored as blob; hot reads hit Redis",
                    ],
                },
                {"type": "h3", "text": "GPS track simplification (Ramer-Douglas-Peucker)"},
                {
                    "type": "code",
                    "text": (
                        "# Reduce a GPX track to map-display-friendly geometry.\n"
                        "# Recursively keep the point with max perpendicular distance to the\n"
                        "# segment from start to end; drop anything within epsilon.\n"
                        "def rdp(points, epsilon):\n"
                        "    if len(points) < 3:\n"
                        "        return points\n"
                        "    dmax, idx = 0.0, 0\n"
                        "    for i in range(1, len(points) - 1):\n"
                        "        d = perp_distance(points[i], points[0], points[-1])\n"
                        "        if d > dmax:\n"
                        "            dmax, idx = d, i\n"
                        "    if dmax > epsilon:\n"
                        "        left  = rdp(points[:idx + 1], epsilon)\n"
                        "        right = rdp(points[idx:],     epsilon)\n"
                        "        return left[:-1] + right\n"
                        "    return [points[0], points[-1]]\n\n"
                        "# epsilon ~5 m on city runs, ~25 m on bike rides — tuned by sport.\n"
                        "# 10 km run: ~3,600 fixes → ~150 polyline points (24× smaller)."
                    ),
                },
                {"type": "h3", "text": "Full GPX vs simplified track"},
                {
                    "type": "table",
                    "headers": ["Use", "Track", "Why"],
                    "rows": [
                        ["Map preview in feed", "Simplified", "Tiny payload, renders instantly, hides exact route"],
                        ["Detailed analysis screen", "Full", "User wants pace/elevation per segment"],
                        ["Export (.gpx file)", "Full", "Other tools expect raw fidelity"],
                        ["Public sharing", "Simplified + privacy zone clip", "Reduces inadvertent home-address leak"],
                    ],
                },
                {"type": "h3", "text": "workouts metadata table"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE workouts (\n"
                        "    workout_id     UUID PRIMARY KEY,\n"
                        "    user_id        BIGINT NOT NULL,\n"
                        "    sport          TEXT,            -- 'run','bike','swim','strength'\n"
                        "    started_at     TIMESTAMPTZ,\n"
                        "    ended_at       TIMESTAMPTZ,\n"
                        "    distance_m     INT,\n"
                        "    duration_s     INT,\n"
                        "    elevation_gain INT,\n"
                        "    avg_hr         SMALLINT,\n"
                        "    calories       INT,\n"
                        "    privacy        TEXT,            -- 'private'|'friends'|'public'\n"
                        "    gpx_full_url   TEXT,            -- s3://...\n"
                        "    gpx_simple_url TEXT,            -- s3://...\n"
                        "    hr_series_url  TEXT,            -- s3://...\n"
                        "    created_at     TIMESTAMPTZ DEFAULT NOW()\n"
                        ");\n"
                        "CREATE INDEX idx_workouts_user_time ON workouts(user_id, started_at DESC);\n"
                        "CREATE INDEX idx_workouts_public    ON workouts(started_at DESC) WHERE privacy='public';"
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Real-Time Leaderboards & Challenges",
            "subtitle": "Redis sorted sets, weekly/monthly windows",
            "blocks": [
                {"type": "h3", "text": "Mechanics"},
                {
                    "type": "bullets",
                    "items": [
                        "Each challenge has a key like <code>lb:steps:weekly:2026W18</code>",
                        "Member is <code>user_id</code>, score is the cumulative metric for the window",
                        "Aggregator <strong>increments the score</strong> as samples flow in: <code>ZINCRBY lb:steps:weekly:W18 1234 user_id</code>",
                        "Top-N queries: <code>ZREVRANGE lb 0 99 WITHSCORES</code> — O(log N + M)",
                        "Member rank: <code>ZREVRANK</code> — let the user see their own position even if not top-100",
                        "Set <code>EXPIRE</code> to ~1 week past window end to auto-clean",
                    ],
                },
                {"type": "h3", "text": "Real-time leaderboard vs nightly batch"},
                {
                    "type": "table",
                    "headers": ["Approach", "Pros", "Cons"],
                    "rows": [
                        ["Real-time (Redis ZINCRBY)", "Live experience; gamification works", "Memory cost; abuse-vector if not deduped"],
                        ["Nightly batch", "Cheap; simple", "Stale; users can't see today's progress"],
                        ["Hybrid: realtime today + batch finalize", "Best UX; bounded cost", "Two code paths; reconcile on day-end"],
                    ],
                },
                {"type": "h3", "text": "Cheating and abuse"},
                {
                    "type": "bullets",
                    "items": [
                        "Cap implausible per-minute deltas (e.g. &gt; 250 steps/min sustained)",
                        "Reject samples whose <code>source</code> is unverified for prize-tier challenges",
                        "Server-side tally is the source of truth; client-reported totals never feed leaderboards",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Sharded sorted sets",
                    "body": (
                        "At 50M DAU, a single ZSET is too large. Shard the leaderboard "
                        "(e.g. by <code>user_id % 64</code>) into 64 sub-leaderboards, then "
                        "merge top-N at read with a heap. Sacrifices exact global rank for users "
                        "outside top-N, but keeps each ZSET in healthy memory range."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Social Feed & Activity Posts",
            "subtitle": "Friend graph, fan-out, kudos, comments",
            "blocks": [
                {"type": "h3", "text": "What is unique here"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Posts are auto-generated</strong> from completed workouts and milestones — users rarely author them directly",
                        "Auto-summary posts: 'Joe ran 10 km at 5:12/km' or 'Aisha hit a 7-day step streak'",
                        "Engagement: kudos (like), comments, share — same patterns as Instagram",
                        "Privacy-by-default per activity (private / friends / public)",
                    ],
                },
                {"type": "h3", "text": "Feed model"},
                {
                    "type": "bullets",
                    "items": [
                        "Friend graph in Postgres (<code>follows(follower_id, followee_id)</code>)",
                        "<strong>Fan-out on write</strong> for normal users: when a workout finalises, push to friends' timeline lists in Redis",
                        "<strong>Fan-out on read</strong> for celebrities (Strava-famous athletes with millions of followers)",
                        "Hybrid threshold: if followee has &gt; 50K followers, fall back to read-time pull",
                        "Privacy filter applied at both write (skip private) and read (re-check, in case privacy changed)",
                    ],
                },
                {"type": "h3", "text": "Auto-post trigger"},
                {
                    "type": "code",
                    "text": (
                        "# When a workout is finalised:\n"
                        "def on_workout_finalised(w):\n"
                        "    if w.privacy == 'private':\n"
                        "        return\n"
                        "    post = build_auto_post(w)        # pre-rendered card\n"
                        "    feed_db.insert_post(post)\n"
                        "    if w.privacy in ('friends', 'public'):\n"
                        "        followers = graph.followers(w.user_id, privacy_min=w.privacy)\n"
                        "        if len(followers) < 50_000:\n"
                        "            for f in followers:\n"
                        "                redis.lpush(f'timeline:{f}', post.id)\n"
                        "                redis.ltrim(f'timeline:{f}', 0, 999)\n"
                        "        else:\n"
                        "            mark_pull_only(post)     # serve via fan-out on read"
                    ),
                },
                {"type": "h3", "text": "Kudos and comments"},
                {
                    "type": "bullets",
                    "items": [
                        "Kudos: counter on the post + per-user dedup (a user can kudo each post once)",
                        "Comments: append-only table keyed by post_id; small, paginate by id",
                        "Notifications: Kafka → Notifications service → APNs/FCM push to phone",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "HealthKit & Google Fit Integration",
            "subtitle": "Two-way sync and conflict resolution",
            "blocks": [
                {"type": "h3", "text": "Two-way sync model"},
                {
                    "type": "bullets",
                    "items": [
                        "On iOS, the phone app reads HealthKit and writes back via the HealthKit API; on Android, the same with Google Fit",
                        "<strong>Inbound</strong>: HealthKit/Fit samples are batched alongside watch samples — same Ingest API, different <code>source</code> tag",
                        "<strong>Outbound</strong>: when our backend records a workout, it surfaces it in HealthKit/Fit so other apps see it",
                        "All sync goes through the user's phone — there is no direct cloud-to-cloud channel with Apple",
                    ],
                },
                {"type": "h3", "text": "The duplicate problem"},
                {
                    "type": "bullets",
                    "items": [
                        "A 7,000-step walk recorded by an Apple Watch can arrive from <strong>three sources</strong>: the watch directly, the phone's motion coprocessor, and HealthKit aggregating both",
                        "Naively summing them triple-counts the walk",
                        "Dedup must be source-aware and time-aware",
                    ],
                },
                {"type": "h3", "text": "Conflict-resolution rules"},
                {
                    "type": "table",
                    "headers": ["Conflict", "Rule"],
                    "rows": [
                        ["Watch HR + phone HR overlap", "Prefer watch (closer to body, more accurate)"],
                        ["Steps from watch + phone", "Prefer watch when worn; fall back to phone when not"],
                        ["HealthKit reports an aggregate that overlaps a known source", "Drop the aggregate, keep the source-tagged samples"],
                        ["Two devices recorded same workout", "Keep both, but mark one as authoritative for the feed"],
                        ["Manual entry vs sensor", "Sensor wins; manual flagged as 'self-reported'"],
                    ],
                },
                {"type": "h3", "text": "Mechanism"},
                {
                    "type": "bullets",
                    "items": [
                        "Every sample carries <code>source</code> and <code>device_id</code>",
                        "The Integration service runs a <strong>reconciliation pass</strong> per (user, day) when multiple sources have written for that day",
                        "Reconciliation produces a canonical <code>view_samples</code> projection — that is what summary jobs read",
                        "Raw samples are never deleted — the canonical view is rebuilt deterministically from priority rules",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Don't trust client-side dedup",
                    "body": (
                        "HealthKit's own dedup is per-app and unreliable across devices — never assume "
                        "the phone has already deduplicated. Always keep raw samples server-side and "
                        "compute the canonical view yourself."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Privacy — GPS Zones & Sharing Controls",
            "subtitle": "Sensitive data, sensible defaults",
            "blocks": [
                {"type": "h3", "text": "Why this is a first-class concern"},
                {
                    "type": "bullets",
                    "items": [
                        "GPS tracks reveal home, work, school, places of worship, sensitive routines",
                        "A public Strava heatmap once accidentally exposed military base layouts — privacy is not theoretical",
                        "Users grant location with the expectation we do not weaponise it back to them",
                    ],
                },
                {"type": "h3", "text": "Per-activity privacy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>private</strong>: never appears in feed, never aggregated into public leaderboards",
                        "<strong>friends</strong>: visible only to mutual or one-way followers",
                        "<strong>public</strong>: visible to anyone; still privacy-zone clipped",
                        "Default is configurable per user — the safer default for new accounts is <em>friends</em>",
                    ],
                },
                {"type": "h3", "text": "Privacy zones"},
                {
                    "type": "bullets",
                    "items": [
                        "User defines circles (<strong>center, radius 200–1000 m</strong>) around home, work, etc.",
                        "When a track is rendered for any non-self viewer, points inside any zone are <strong>clipped before serving</strong>",
                        "Distance and time totals are preserved; only the geometry is hidden — the user's stats are unchanged",
                        "Server-side enforcement: clipping happens in the workout service, not the client",
                    ],
                },
                {
                    "type": "code",
                    "text": (
                        "def clip_track_for_viewer(track, owner_zones):\n"
                        "    out = []\n"
                        "    skipping = False\n"
                        "    for p in track:\n"
                        "        if any(haversine(p, z.center) < z.radius for z in owner_zones):\n"
                        "            skipping = True\n"
                        "            continue\n"
                        "        if skipping:\n"
                        "            out.append(GAP_MARKER)   # leaves a visible gap on map\n"
                        "            skipping = False\n"
                        "        out.append(p)\n"
                        "    return out"
                    ),
                },
                {"type": "h3", "text": "HIPAA-adjacent vs HIPAA"},
                {
                    "type": "bullets",
                    "items": [
                        "By default this is <strong>not</strong> HIPAA — fitness data from consumer devices is not PHI on its own",
                        "If we partner with a healthcare provider (clinical trial, employer wellness, EHR write-back), the integrated subset becomes PHI",
                        "We isolate that subset behind a separate VPC, BAA-bound vendors, and stricter audit logging",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Encrypt GPS at rest, audit access",
                    "body": (
                        "GPS samples are encrypted at rest with a per-user data key (envelope "
                        "encryption via KMS). All internal access to GPS data is logged to an "
                        "append-only audit table; analytics queries that touch raw lat/lon must "
                        "go through a privileged service account."
                    ),
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
                        ["Phone offline for days", "Backlog of samples on device",
                         "Server-side stale last-sync alert", "Phone backfills in chronological order; aggregator marks days dirty and recomputes"],
                        ["Clock skew on device", "Out-of-order or future-dated samples",
                         "Compare timestamps to server clock at ingest", "Snap to server time on ingest if drift &gt; 60s; preserve original in <code>raw_ts</code>"],
                        ["Duplicate samples (multi-source)", "Triple-counted steps",
                         "Reconciliation diff vs canonical view", "Source-priority dedup; rebuild canonical view per day"],
                        ["Kafka backlog", "Aggregations lag",
                         "Consumer lag metric", "Auto-scale stream consumers; back-pressure on ingest only after Kafka itself is at risk"],
                        ["Cassandra hot partition", "Latency spike for one user",
                         "Per-partition latency monitor", "Day-bucket partitioning already caps; shard further by metric if a user is a torture-test case"],
                        ["S3 GPX write fails", "Workout missing route",
                         "Workout finalisation retry counter", "Retry with backoff; mark workout 'route pending' so the feed still shows summary"],
                        ["HealthKit sends garbage", "Implausible aggregates",
                         "Sanity bounds on totals", "Reject samples failing bounds; flag user for support if persistent"],
                        ["Region failure", "Users in region cannot sync",
                         "Synthetic probe failures", "Phone retries with exponential backoff; route to next region; ingest is offline-tolerant"],
                    ],
                },
                {"type": "h3", "text": "Recovery posture"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>RPO ≈ 0</strong> for samples once cloud has acked — Kafka replicates 3×",
                        "<strong>RPO ≈ minutes</strong> for derived state (summaries, leaderboards) — they can be rebuilt from raw",
                        "<strong>RTO &lt; 30 min</strong> for ingest path; the rest of the system can lag",
                        "Phone is the disaster shock absorber: it can buffer ~1 GB locally, so a 6-hour cloud outage is invisible to the user",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Never lose a sample after ack",
                    "body": (
                        "The phone treats a 200 from Ingest as a durable commit and frees its "
                        "buffer. Therefore Ingest must write to Kafka (3× replicated) "
                        "<em>before</em> returning 200 — never just an in-memory queue. Losing "
                        "samples after ack is the worst-class bug for a fitness platform: users "
                        "see their PRs evaporate."
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
                        ["Sample granularity", "HR 5s, steps 1s, GPS only in workouts",
                         "Higher fidelity costs storage and battery; chosen rates match what users perceive."],
                        ["Sync model", "Batched HTTP from phone",
                         "Up to 15 min ingest lag; vastly cheaper and battery-friendlier than streaming."],
                        ["TSDB choice", "Cassandra (with per-row TTL)",
                         "Operationally heavier than Influx but predictable at PB scale."],
                        ["Aggregation timing", "Real-time daily + nightly weekly/monthly",
                         "Live numbers users see today; cheap batch for longer windows."],
                        ["Feed fan-out", "Hybrid: write for normals, read for celebrities",
                         "Two code paths, but caps memory blowup for high-fan-out users."],
                        ["GPS sharing", "Simplified track + privacy zone clip",
                         "Tiny payload, safer; loses some fidelity for public viewers."],
                        ["Leaderboards", "Real-time Redis ZSET (sharded)",
                         "Memory cost; necessary for the gamification UX."],
                        ["Conflict resolution", "Server-side reconciliation per (user, day)",
                         "Extra compute; the only reliable path given multi-source duplicates."],
                        ["Privacy default", "<em>friends</em> for new accounts",
                         "Slightly less viral; meaningfully safer."],
                        ["Hot retention", "30 days online",
                         "Most product needs are within 30 days; older data warm/cold is fine."],
                    ],
                },
            ],
        },
        # ---- 15 ------------------------------------------------------
        {
            "num": "15",
            "title": "Interview Playbook",
            "subtitle": "How to present this in 45 minutes",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "This system is broad — keep the narrative on a leash. The interviewer "
                        "wants to see you handle bursty time-series ingest, retention tiers, "
                        "multi-source dedup, and privacy. The social layer and integrations are "
                        "supporting acts."
                    ),
                },
                {"type": "h3", "text": "45-minute outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (3 min):</strong> 500M users / 50M DAU / ~14 MB/user/day / ~25 GB/s peak ingest",
                        "<strong>Sync model (5 min):</strong> device → phone → cloud, batched, offline-tolerant — explain why not streaming",
                        "<strong>High-level arch (5 min):</strong> Ingest → Kafka → TSDB / Aggregator / Workouts / Social / Integrations",
                        "<strong>Time-series store (8 min):</strong> Cassandra vs Influx vs Timescale; partition by (user, day, metric); per-row TTL",
                        "<strong>Aggregations (5 min):</strong> live daily summary + nightly weekly/monthly; dirty-day recomputation",
                        "<strong>Workouts & GPX (5 min):</strong> structured doc, RDP simplification, full vs simple track",
                        "<strong>Social + leaderboards (5 min):</strong> hybrid fan-out, sharded Redis ZSET",
                        "<strong>HealthKit/Fit + privacy (6 min):</strong> source-priority dedup, privacy zones, HIPAA boundary",
                        "<strong>Failure modes (3 min):</strong> phone offline backfill, clock skew, duplicate samples",
                    ],
                },
                {"type": "h3", "text": "Numbers to memorise"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>~25 GB/s</strong> peak aggregate ingest",
                        "<strong>~14 MB/user/day</strong> after compression incl. workouts",
                        "<strong>30 days hot · 1 year warm · lifetime cold</strong>",
                        "HR 5s · steps 1s · GPS only in workouts",
                        "Fan-out threshold ~<strong>50K followers</strong> (write-fan-out below, read-fan-out above)",
                    ],
                },
                {"type": "h3", "text": "Common follow-ups"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why not a streaming WebSocket?</strong> A: Battery and connectivity. Devices are offline often; batched HTTP with retries is cheaper, more reliable, and gets the same effective freshness once you accept a 5-15 minute lag.",
                        "<strong>Q: How do you handle a 5-day backlog after a vacation?</strong> A: Phone buffers locally, uploads chronologically with throttling on reconnect; aggregator marks each affected day dirty and recomputes the daily summary.",
                        "<strong>Q: How do you stop someone gaming step counts?</strong> A: Server-side tally only, plausibility caps per minute, source-tagged samples, drop unverified sources for prize-tier challenges.",
                        "<strong>Q: A user lives next to a gym they hate — how do they hide it?</strong> A: Privacy zone — a circle around the address. Server clips the track segment inside that circle for any non-self viewer; the user's totals stay correct.",
                        "<strong>Q: Strava-famous athlete with 3M followers posts a workout — how does it scale?</strong> A: Cross the fan-out threshold, switch to read-time pull. Their post sits in a per-user posts list; followers' feed builders fetch and merge at read time.",
                        "<strong>Q: What if Apple HealthKit and our watch disagree on step count?</strong> A: Source-priority rules — watch wins for HR and steps when worn. Reconciliation runs per (user, day) and rebuilds a canonical view; raw samples are never deleted.",
                        "<strong>Q: Is this HIPAA?</strong> A: Not by default. The moment we integrate with a healthcare provider for clinical data exchange, the integrated subset becomes PHI and lives in an isolated, BAA-bound environment.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Headline Numbers",
                    "body": (
                        "500M users · 50M DAU · ~14 MB/user/day · ~25 GB/s peak ingest · "
                        "30d hot / 1y warm / lifetime cold · HR 5s / steps 1s / GPS in workouts only · "
                        "Fan-out flips at ~50K followers."
                    ),
                },
            ],
        },
    ],
}
