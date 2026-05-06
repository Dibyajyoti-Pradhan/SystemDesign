"""Source for `19 - Uber.pdf`."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Uber (Ride Hailing)",
    "subtitle": "real-time matching of riders and drivers, geo-indexed dispatch, trip lifecycle, surge pricing",
    "read_time": "~ 45 minute read",
    "short_title": "Design Uber",
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
                        "Design a global ride-hailing service like <strong>Uber</strong> or "
                        "<strong>Lyft</strong>. The system must match millions of riders with "
                        "nearby drivers in real time, dispatch trips with low latency, track the "
                        "trip lifecycle from request to payment, and dynamically price rides "
                        "based on supply and demand."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Scale?", "150M MAU; 25M trips/day; 6M concurrent online drivers at peak"],
                        ["Geography?", "Global; partition operations by city / metro region"],
                        ["Match latency?", "Driver offer within 2s of rider request; p99 &lt; 5s"],
                        ["Pricing?", "Real-time surge multiplier per region, shown pre-request"],
                        ["Routing?", "Custom routing engine (OSRM-like); ETAs from live telemetry"],
                        ["Payments?", "Charged after trip; multiple methods; tipping post-trip"],
                        ["Offline driver app?", "Buffer location pings; graceful timeout on dispatch"],
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
                        ["Driver location", "Driver app pings location every 4 sec; geo-indexed"],
                        ["Rider request", "Rider taps 'request' → server matches a nearby driver"],
                        ["Dispatch", "Offer trip to top-scored driver; 15s timeout; fall through"],
                        ["Trip lifecycle", "States: requested → accepted → en_route → at_pickup → in_progress → completed"],
                        ["Surge pricing", "Multiplier per H3 cell, computed from supply / demand"],
                        ["ETA", "Live ETA to pickup and to destination from routing engine"],
                        ["Payments", "Auto-charge after trip end; receipts; tipping window"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Match latency", "p50 &lt; 1s, p99 &lt; 5s from request to driver offer"],
                        ["Availability", "99.99% for trip lifecycle; 99.9% for analytics"],
                        ["Geo-index freshness", "Driver location TTL ≤ 10s; query freshness &lt; 5s"],
                        ["Throughput", "1.5M location updates/sec at peak; ~300 trips/sec global"],
                        ["Consistency", "Strong for trip state machine; eventual for pricing"],
                        ["Scale", "Horizontally scalable per city/region shard"],
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
                        "MAU: <strong>150M</strong>; DAU ≈ 30–40M",
                        "Trips/day: <strong>25M</strong> globally → 25M / 86,400s ≈ <strong>290 trips/sec</strong> avg",
                        "Peak factor 3–4× → <strong>~1,000–1,200 trip requests/sec</strong> at peak",
                        "Concurrent online drivers at peak: <strong>6M</strong>",
                        "Driver location ping every <strong>4 sec</strong> → 6M / 4 = <strong>1.5M location updates/sec</strong>",
                    ],
                },
                {"type": "h3", "text": "Storage Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        "Location ping payload: driver_id (8B) + lat/lng (16B) + h3_cell (8B) + ts (8B) + bearing/speed (8B) ≈ 50–80 B",
                        "Hot location store: only the <strong>latest</strong> ping per driver in Redis (6M × ~200B ≈ <strong>1.2 GB</strong>)",
                        "Trip record: ~2 KB; 25M/day × 2 KB = <strong>50 GB/day</strong> trip data",
                        "Trip events to Kafka: ~10 events/trip × 25M = 250M events/day, ~500 GB/day raw",
                        "Annual trip storage (compressed in OLAP): ~<strong>5–10 TB/year</strong>",
                    ],
                },
                {"type": "h3", "text": "Geo-index Working Set"},
                {
                    "type": "bullets",
                    "items": [
                        "H3 res 9 cell ≈ 0.1 km²; a busy metro has ~10K active cells",
                        "Per cell, store list of driver_ids currently in the cell (avg 5–50)",
                        "Total geo-index entries: <strong>6M drivers</strong>, lookup by H3 cell key",
                        "Memory for indexed structures: ~<strong>3–5 GB Redis</strong> (latest pos + cell membership)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "150M MAU &nbsp;·&nbsp; 25M trips/day &nbsp;·&nbsp; 6M concurrent drivers &nbsp;·&nbsp; "
                        "<strong>1.5M location updates/sec</strong> at peak &nbsp;·&nbsp; "
                        "~1,000 trip requests/sec at peak &nbsp;·&nbsp; ~1.2 GB hot driver-location set."
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
                        "The platform splits into <strong>mobile clients</strong> (rider and driver "
                        "apps), an <strong>API gateway</strong> for ingress, a set of <strong>matching "
                        "and trip services</strong> (Uber's <em>Disco</em> dispatch, Geo-index, "
                        "Trip, Pricing), and a <strong>data tier</strong> (Redis geo, MySQL/Postgres "
                        "sharded by city, Kafka for events, and the routing engine). Each city/metro "
                        "is a sharding unit; cross-region traffic is rare."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Rider/Driver mobile apps → API gateway → Disco (matching) coordinates Geo-index, Trip, Pricing, Payments, Notifications. Data tier: Redis geo, MySQL trips, Kafka events, Routing engine.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_mobile {
        label="Mobile"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Rider  [label="Rider App",  fillcolor="#dbe6fb"];
        Driver [label="Driver App", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        GW [label="API Gateway\n(WebSocket + REST)", fillcolor="#cbeedf"];
    }
    subgraph cluster_svc {
        label="Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        Disco   [label="Disco\n(Matching/Dispatch)", fillcolor="#fff2c9"];
        Geo     [label="Geo-index\nService (H3)",    fillcolor="#fff2c9"];
        Trip    [label="Trip Service\n(state machine)", fillcolor="#fff2c9"];
        Price   [label="Pricing\n(Surge)",            fillcolor="#fff2c9"];
        Pay     [label="Payment",                     fillcolor="#fff2c9"];
        Notify  [label="Notifications\n(push, SMS)",  fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        Redis  [label="Redis Geo\n(driver loc, H3 sets)", fillcolor="#ead7fb"];
        DB     [label="MySQL/Postgres\n(trips, sharded by city)", fillcolor="#ead7fb"];
        Kafka  [label="Kafka\n(trip + ping events)", fillcolor="#fbd7c5"];
        Route  [label="Routing Engine\n(OSRM-like, ETA)", fillcolor="#ead7fb"];
    }

    Rider  -> GW [label="request, status"];
    Driver -> GW [label="ping every 4s\noffer / accept"];
    GW -> Disco [label="rider request"];
    GW -> Geo   [label="driver ping"];
    Disco -> Geo   [label="query nearby"];
    Disco -> Price [label="get multiplier"];
    Disco -> Trip  [label="create trip"];
    Disco -> Notify [label="offer push"];
    Trip  -> DB    [label="persist state"];
    Trip  -> Kafka [label="events"];
    Geo   -> Redis [label="GEOADD / nearby"];
    Price -> Kafka [label="cell stats"];
    Price -> Redis [label="multiplier cache"];
    Disco -> Route [label="ETA"];
    Trip  -> Pay   [label="charge on complete"];
}
""",
                },
                {"type": "h3", "text": "Architecture Highlights"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>API Gateway:</strong> long-lived WebSocket per app for low-latency push (offers, status) and REST for control",
                        "<strong>Disco:</strong> matching brain — turns rider request + nearby drivers into a sequence of offers",
                        "<strong>Geo-index:</strong> stateful service over Redis; converts (lat,lng) ↔ H3 cell; answers 'who is near?'",
                        "<strong>Trip Service:</strong> owns the state machine; durable in MySQL; saga across pricing, payment, notify",
                        "<strong>Pricing:</strong> consumes supply/demand stats per H3 cell; emits surge multiplier",
                        "<strong>Routing Engine:</strong> custom graph routing over OpenStreetMap; updated by driver telemetry",
                        "<strong>Kafka:</strong> backbone for ping/trip/payment events feeding analytics, ML, fraud, surge",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Geo-Indexing with H3",
            "subtitle": "Hex grid over the planet",
            "blocks": [
                {"type": "h3", "text": "Why a Hex Grid?"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Equidistant neighbors:</strong> a hexagon has 6 neighbors all the same distance apart; squares have 4 close + 4 diagonal (different distances)",
                        "<strong>Uniform area:</strong> H3 cells of a given resolution have nearly the same area, regardless of latitude",
                        "<strong>Hierarchical:</strong> each cell has parent/children at different resolutions for zoom",
                        "<strong>Simple ring queries:</strong> 'k-ring' returns all cells within k steps — natural for radius search",
                    ],
                },
                {"type": "h3", "text": "Resolution Choice"},
                {
                    "type": "table",
                    "headers": ["H3 res", "Avg cell area", "Use"],
                    "rows": [
                        ["res 6", "~36 km²", "Surge zones, regional supply/demand views"],
                        ["res 7", "~5 km²", "Default surge zone size; metro regions"],
                        ["res 8", "~0.7 km²", "Mid-zoom dispatch context"],
                        ["res 9", "~0.1 km²", "Driver-location bucket; primary dispatch index"],
                        ["res 10", "~0.015 km²", "Pickup-precise; used for pickup snapping"],
                    ],
                },
                {"type": "h3", "text": "H3 vs S2 vs Quadtree"},
                {
                    "type": "table",
                    "headers": ["Property", "H3 (hex)", "S2 (sphere cells)", "Quadtree"],
                    "rows": [
                        ["Cell shape", "Hexagon", "Quadrilateral on sphere", "Square (axis-aligned)"],
                        ["Neighbor distance", "Uniform (6 neighbors)", "Approx uniform (8 neighbors)", "Non-uniform (4+4 diag)"],
                        ["Area uniformity", "High (hierarchical)", "High (Hilbert-curve)", "Distorted near poles, equator OK"],
                        ["Parent / child", "Aperture-7 (not exact partition)", "Exact 4-way subdivision", "Exact 4-way subdivision"],
                        ["Library", "Uber H3", "Google S2", "Many implementations"],
                        ["Best for", "Mobility, surge, dispatch", "Spatial joins, indexing", "Simple range queries"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why H3 Wins for Dispatch",
                    "body": (
                        "Equidistant neighbors mean a 'k-ring' lookup gives a true radius, not a "
                        "stretched square. Uniform area makes per-cell supply/demand metrics fair "
                        "across a city. Aperture-7 hierarchy is good enough for analytics with "
                        "small overlap correction."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Driver Location Pipeline",
            "subtitle": "Ingesting 1.5M pings/sec",
            "blocks": [
                {"type": "h3", "text": "End-to-end Flow"},
                {
                    "type": "numbered",
                    "items": [
                        "Driver app sends <code>POST /ping</code> over WebSocket every 4 sec with (lat, lng, bearing, speed)",
                        "API Gateway forwards ping to Geo-index Service partition for that driver's region",
                        "Geo-index computes <code>h3_cell = h3.geo_to_h3(lat, lng, res=9)</code>",
                        "Update Redis: <code>GEOADD drivers:active &lt;lng&gt; &lt;lat&gt; &lt;driver_id&gt;</code> and <code>SADD cell:&lt;h3_cell&gt; &lt;driver_id&gt;</code>",
                        "Set TTL on driver key (10 sec); stale drivers fall out automatically",
                        "Async: emit ping to Kafka topic <code>driver_pings</code> for surge, fraud, ETA telemetry",
                    ],
                },
                {"type": "h3", "text": "Storage: driver_location Schema"},
                {
                    "type": "code",
                    "text": (
                        "-- Redis (hot, primary)\n"
                        "GEOADD drivers:active <lng> <lat> <driver_id>\n"
                        "HSET   driver:<driver_id> h3 <h3_cell> ts <epoch_ms> status 'available'\n"
                        "EXPIRE driver:<driver_id> 10\n"
                        "SADD   cell:<h3_cell> <driver_id>\n\n"
                        "-- MySQL (cold, append-only history; partition by day, sharded by city)\n"
                        "CREATE TABLE driver_location (\n"
                        "  driver_id   BIGINT     NOT NULL,\n"
                        "  city_id     INT        NOT NULL,\n"
                        "  lat         DOUBLE     NOT NULL,\n"
                        "  lng         DOUBLE     NOT NULL,\n"
                        "  h3_res9     BIGINT     NOT NULL,   -- H3 cell ID\n"
                        "  bearing     SMALLINT,\n"
                        "  speed_kph   SMALLINT,\n"
                        "  ts          TIMESTAMP(3) NOT NULL,\n"
                        "  PRIMARY KEY (driver_id, ts),\n"
                        "  KEY idx_h3 (h3_res9, ts)\n"
                        ") PARTITION BY RANGE (TO_DAYS(ts));"
                    ),
                },
                {"type": "h3", "text": "Why Redis (and not MySQL) for the Hot Index"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>1.5M writes/sec:</strong> Redis handles 100K+ ops/sec per node; 16-node cluster sharded by region absorbs load",
                        "<strong>Sub-ms reads:</strong> nearby-driver queries must return in &lt; 5 ms for sub-second match latency",
                        "<strong>TTL primitives:</strong> stale drivers expire automatically; no scrubbing job",
                        "<strong>Native geo ops:</strong> GEOADD / GEOSEARCH; we combine with H3 sets for hex-aware lookup",
                    ],
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Disco: Matching & Dispatch",
            "subtitle": "Rider request to driver offer",
            "blocks": [
                {"type": "h3", "text": "End-to-end Flow"},
                {
                    "type": "numbered",
                    "items": [
                        "Rider taps 'request' → <code>POST /trip/request</code> with (pickup_lat, pickup_lng, dest)",
                        "Trip Service creates trip in state <code>requested</code>; emits <code>trip.requested</code>",
                        "Disco computes <code>pickup_h3 = h3.geo_to_h3(lat, lng, 9)</code> and queries Geo-index for rings 1, 2, 3",
                        "Filter candidates: online + available + service-tier match + not currently on a trip",
                        "Score each candidate by ETA + driver rating + acceptance rate (see pseudocode below)",
                        "Send offer to top driver via push (WebSocket); start <strong>15 s timeout</strong> timer",
                        "If accepted → trip transitions to <code>accepted</code>; if declined / timeout → fall through to next candidate",
                        "On accept: notify rider, lock driver, push ETA to pickup",
                    ],
                },
                {"type": "h3", "text": "Matching Pseudocode"},
                {
                    "type": "code",
                    "text": (
                        "def match(rider_request):\n"
                        "    pickup_h3 = h3.geo_to_h3(rider_request.lat,\n"
                        "                              rider_request.lng, res=9)\n"
                        "\n"
                        "    # Expand outward until we have enough candidates\n"
                        "    candidates = []\n"
                        "    for ring in range(0, 4):                 # rings 0..3\n"
                        "        cells = h3.k_ring(pickup_h3, ring)\n"
                        "        for cell in cells:\n"
                        "            for driver_id in redis.smembers(f'cell:{cell}'):\n"
                        "                d = driver_state(driver_id)\n"
                        "                if d.online and d.available \\\n"
                        "                   and d.tier == rider_request.tier:\n"
                        "                    candidates.append(d)\n"
                        "        if len(candidates) >= 20:\n"
                        "            break\n"
                        "\n"
                        "    # Score: lower ETA, higher rating, higher accept rate\n"
                        "    def score(d):\n"
                        "        eta = routing.eta(d.location, rider_request.pickup)\n"
                        "        return (-eta * 1.0\n"
                        "                + d.rating       * 30\n"
                        "                + d.accept_rate  * 20)\n"
                        "\n"
                        "    candidates.sort(key=score, reverse=True)\n"
                        "\n"
                        "    # Sequential offer with 15s timeout each\n"
                        "    for d in candidates[:5]:\n"
                        "        if offer_with_timeout(d, rider_request, t=15):\n"
                        "            return d                     # accepted\n"
                        "    raise NoDriverAvailable()"
                    ),
                },
                {"type": "h3", "text": "Sync Dispatch vs Batch Dispatch"},
                {
                    "type": "table",
                    "headers": ["Aspect", "Synchronous (immediate)", "Batched (every 1–2s)"],
                    "rows": [
                        ["Latency to first offer", "Lowest (≈ 1 s)", "Adds the batch window (1–2 s)"],
                        ["Match quality", "Greedy: first decent driver wins", "Globally optimal — uses Hungarian/min-cost flow"],
                        ["Best for", "Sparse demand, off-peak", "Dense urban areas during surge"],
                        ["Failure mode", "Locally suboptimal pairings", "Rider feels app is 'thinking'"],
                        ["Uber's choice", "Default greedy with score", "Batch when supply &gt; demand and cell is hot"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Why Sequential Offers (not 'broadcast')?",
                    "body": (
                        "Broadcasting to many drivers at once causes contention (multiple accepts) "
                        "and unfair allocation. Sequential offers with a 15 s timeout give a fair, "
                        "deterministic flow and let drivers self-select."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Trip Lifecycle & State Machine",
            "subtitle": "Idempotent transitions across services",
            "blocks": [
                {"type": "h3", "text": "States"},
                {
                    "type": "diagram",
                    "caption": "Trip state machine. Transitions are idempotent; each is recorded as an event in Kafka and a row in trip_events.",
                    "dot": r"""
digraph trip {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8", fillcolor="#fff2c9"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    requested  [label="requested"];
    accepted   [label="accepted"];
    enroute    [label="driver_en_route"];
    pickup     [label="at_pickup"];
    inprog     [label="in_progress"];
    completed  [label="completed", fillcolor="#cbeedf"];
    canceled   [label="canceled",  fillcolor="#f7c4c4"];

    requested -> accepted   [label="driver accepts"];
    requested -> canceled   [label="rider cancels / no driver"];
    accepted  -> enroute    [label="driver moves"];
    accepted  -> canceled   [label="cancel"];
    enroute   -> pickup     [label="arrive at pickup"];
    enroute   -> canceled   [label="cancel"];
    pickup    -> inprog     [label="rider on board"];
    pickup    -> canceled   [label="rider no-show"];
    inprog    -> completed  [label="dropoff"];
}
""",
                },
                {"type": "h3", "text": "Trips Table Schema"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE trips (\n"
                        "  trip_id        BIGINT       PRIMARY KEY,\n"
                        "  city_id        INT          NOT NULL,       -- shard key\n"
                        "  rider_id       BIGINT       NOT NULL,\n"
                        "  driver_id      BIGINT,\n"
                        "  state          ENUM('requested','accepted','driver_en_route',\n"
                        "                       'at_pickup','in_progress','completed',\n"
                        "                       'canceled') NOT NULL,\n"
                        "  pickup_lat     DOUBLE,\n"
                        "  pickup_lng     DOUBLE,\n"
                        "  pickup_h3_r9   BIGINT,\n"
                        "  dest_lat       DOUBLE,\n"
                        "  dest_lng       DOUBLE,\n"
                        "  base_fare      DECIMAL(10,2),\n"
                        "  surge_mult     DECIMAL(4,2),\n"
                        "  total_fare     DECIMAL(10,2),\n"
                        "  requested_at   TIMESTAMP(3) NOT NULL,\n"
                        "  accepted_at    TIMESTAMP(3),\n"
                        "  completed_at   TIMESTAMP(3),\n"
                        "  state_version  INT          NOT NULL,       -- optimistic concurrency\n"
                        "  KEY idx_driver (driver_id, requested_at),\n"
                        "  KEY idx_rider  (rider_id,  requested_at)\n"
                        ");\n\n"
                        "CREATE TABLE trip_events (\n"
                        "  trip_id        BIGINT,\n"
                        "  event_seq      INT,\n"
                        "  event_type     VARCHAR(32),\n"
                        "  payload        JSON,\n"
                        "  ts             TIMESTAMP(3),\n"
                        "  PRIMARY KEY (trip_id, event_seq)\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "Idempotency"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>state_version:</strong> guarded transition <code>UPDATE ... WHERE state_version = ?</code> rejects double-apply",
                        "<strong>idempotency_key:</strong> client-supplied UUID on POSTs (request, accept, complete) — server dedups",
                        "<strong>Outbox pattern:</strong> trip_events row written in same Tx as trips update; relay publishes to Kafka",
                        "<strong>Saga:</strong> trip completion fans out to Pricing → Payment → Notify; compensating actions on failure",
                    ],
                },
                {"type": "h3", "text": "Trip Saga Across Services"},
                {
                    "type": "table",
                    "headers": ["Step", "Service", "Compensation if it fails"],
                    "rows": [
                        ["1. Reserve driver", "Disco", "Release lock; offer next driver"],
                        ["2. Create trip row", "Trip", "Mark canceled with reason"],
                        ["3. Compute fare (surge × distance)", "Pricing", "Use last-known multiplier"],
                        ["4. Charge payment", "Payment", "Retry; fall back to deferred billing"],
                        ["5. Push receipt", "Notify", "Best-effort; log if undelivered"],
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Surge Pricing",
            "subtitle": "Real-time supply/demand balance",
            "blocks": [
                {"type": "para", "text": (
                    "Surge multiplies the base fare in zones where rider requests outpace "
                    "available drivers. The multiplier is broadcast to rider apps "
                    "<strong>before</strong> a request, so the rider sees the price up front and the "
                    "system can shape demand."
                )},
                {"type": "h3", "text": "Per-Cell Computation (H3 res 7 ≈ 5 km²)"},
                {
                    "type": "numbered",
                    "items": [
                        "Aggregate per cell, per minute: <code>requests = count(rider.requested)</code>, <code>supply = count(distinct online available drivers)</code>",
                        "Compute imbalance ratio <code>r = max(1, requests / max(supply, 1))</code>",
                        "Smooth with EWMA: <code>multiplier = α · clamp(r, 1.0, 5.0) + (1−α) · prev</code> (α=0.3)",
                        "Publish to Redis <code>surge:cell:&lt;h3&gt; = multiplier</code> with TTL 90 s",
                        "Rider app polls or receives push when entering a new cell",
                    ],
                },
                {"type": "h3", "text": "Pricing Formula"},
                {
                    "type": "code",
                    "text": (
                        "fare = base_fare\n"
                        "     + per_minute  * trip_minutes\n"
                        "     + per_km      * trip_km\n"
                        "     + booking_fee\n\n"
                        "fare *= surge_multiplier(pickup_h3_res7)   # capped at 5.0\n"
                        "fare  = max(fare, min_fare)"
                    ),
                },
                {"type": "h3", "text": "Surge Stream"},
                {
                    "type": "diagram",
                    "caption": "Pricing service consumes Kafka topics (rider requests, driver pings) windowed by H3 cell, emits surge multiplier to Redis, broadcast to rider apps.",
                    "dot": r"""
digraph surge {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Pings   [label="Kafka:\ndriver_pings",  fillcolor="#fbd7c5"];
    Reqs    [label="Kafka:\nrider_requests", fillcolor="#fbd7c5"];
    Flink   [label="Flink / Kafka Streams\n(window=60s, key=H3 res7)", fillcolor="#fff2c9"];
    Pricing [label="Pricing Service\n(EWMA + cap)", fillcolor="#fff2c9"];
    Redis   [label="Redis\nsurge:cell:<h3>", fillcolor="#ead7fb"];
    Apps    [label="Rider Apps\n(WebSocket push)", fillcolor="#dbe6fb"];

    Pings -> Flink;
    Reqs  -> Flink;
    Flink -> Pricing [label="supply, demand"];
    Pricing -> Redis [label="multiplier"];
    Redis -> Apps    [label="push on enter cell"];
}
""",
                },
                {"type": "h3", "text": "Safeguards"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Hard cap:</strong> multiplier ≤ 5.0; emergencies (storms, disasters) → cap at 1.0 manually",
                        "<strong>Smoothing:</strong> EWMA prevents oscillation; minimum dwell of 60 s before raising",
                        "<strong>Show before tap:</strong> rider sees price pre-request; reduces complaints and surprises",
                        "<strong>Driver-side:</strong> heatmap of high-surge cells nudges supply to where it's needed",
                    ],
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "ETA & Routing Engine",
            "subtitle": "Graph routing with live traffic",
            "blocks": [
                {"type": "h3", "text": "Routing Engine"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Graph:</strong> road network from OpenStreetMap; nodes = intersections, edges = road segments with travel-time weights",
                        "<strong>Algorithm:</strong> contraction hierarchies (CH) or A* with landmarks; ETAs in &lt; 10 ms per query",
                        "<strong>Custom build:</strong> Uber's in-house engine (similar to OSRM / Valhalla) tuned for batch ETA at dispatch time",
                        "<strong>Two ETA queries per trip:</strong> driver → pickup, pickup → destination",
                    ],
                },
                {"type": "h3", "text": "Real-Time Traffic Updates"},
                {
                    "type": "numbered",
                    "items": [
                        "Driver pings include speed and bearing every 4 sec",
                        "Stream (Kafka → Flink) bins pings to OSM edges; computes p50 / p85 speed per edge per 5-min window",
                        "Routing engine reloads edge weights every 1–5 minutes",
                        "Historical patterns (time-of-day, day-of-week) are blended for cold edges with no recent telemetry",
                    ],
                },
                {"type": "h3", "text": "ETA Accuracy"},
                {
                    "type": "table",
                    "headers": ["Layer", "Source", "Update freq"],
                    "rows": [
                        ["Static graph", "OSM nightly build", "Daily"],
                        ["Historical speed", "Past 90 days, by hour-of-week", "Weekly"],
                        ["Live speed", "Driver telemetry, last 5 min", "Every 1–5 min"],
                        ["ML correction", "Gradient-boosted residual on top", "Per-trip inference"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why Custom Routing?",
                    "body": (
                        "Off-the-shelf routers are tuned for human navigation (turn-by-turn). "
                        "Dispatch needs <em>millions of ETA queries per minute</em> for matching, "
                        "with low p99 latency. A purpose-built engine with pre-contracted graphs "
                        "and bulk-query APIs hits sub-10 ms per ETA at scale."
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Storage & Sharding",
            "subtitle": "Hot Redis, sharded SQL, Kafka events",
            "blocks": [
                {"type": "h3", "text": "Storage Tiers"},
                {
                    "type": "table",
                    "headers": ["Data", "Store", "Reason"],
                    "rows": [
                        ["Latest driver location", "Redis (geo + hash)", "Sub-ms reads, native geo, TTL"],
                        ["H3 cell membership", "Redis sets", "O(1) add/remove; quick k-ring lookup"],
                        ["Trip records (truth)", "MySQL/Postgres sharded by city", "ACID for state machine; relational queries"],
                        ["Trip / ping events", "Kafka", "Immutable log; fans out to surge, ML, fraud, analytics"],
                        ["Trip history (cold)", "Cassandra / S3 + Parquet", "Cheap, append-only; OLAP queries"],
                        ["Surge multiplier", "Redis (90 s TTL)", "Hot read path; tolerates short staleness"],
                    ],
                },
                {"type": "h3", "text": "Sharding by City"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Shard key:</strong> <code>city_id</code> (San Francisco, NYC, London ...) — most queries are local",
                        "<strong>Hot cities split:</strong> NYC, SF, London get their own dedicated MySQL clusters",
                        "<strong>Cold cities pooled:</strong> dozens of small markets share a cluster",
                        "<strong>Cross-city trip:</strong> rare (airport runs); handled by writing to origin city, mirroring to destination",
                        "<strong>Per-region datacenters:</strong> US-East, US-West, EU, APAC; matching is always intra-DC",
                    ],
                },
                {"type": "h3", "text": "Replication & Consistency"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Trip table:</strong> primary + 2 sync replicas per shard; failover via Orchestrator",
                        "<strong>Read-after-write:</strong> trip mutations always read from primary (low volume)",
                        "<strong>Redis geo:</strong> primary + replica per region; data is rebuildable from pings within 10 sec",
                        "<strong>Kafka:</strong> RF=3, min ISR=2; cross-region mirroring for analytics",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Cell Hashing Across Redis Nodes",
                    "body": (
                        "Shard the geo-index by H3 parent cell (res 4 or 5) using consistent "
                        "hashing. A k-ring query at res 9 stays within one or two Redis nodes. "
                        "Adding capacity moves only 1/N of cells."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Failure Modes & Recovery",
            "subtitle": "What can go wrong",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["Driver app loses connectivity",
                         "Pings stop; driver disappears from cell",
                         "TTL expiry on driver:<id> key",
                         "Graceful timeout (10 s); offer fall-through to next candidate; re-add on reconnect"],
                        ["Rider app loses connectivity mid-trip",
                         "Status updates not received",
                         "WebSocket disconnect",
                         "Trip continues server-side; reconcile state on reconnect via /trip/&lt;id&gt;"],
                        ["Surge runaway (oscillation / spike)",
                         "Multiplier flapping; rider trust hit",
                         "Multiplier change rate alert",
                         "Hard cap 5.0; EWMA smoothing; manual emergency cap to 1.0"],
                        ["Payment failure post-trip",
                         "Trip completed but unpaid",
                         "Payment async error",
                         "Saga retry with backoff; mark trip 'unpaid' and recover via batch settlement"],
                        ["Redis geo node down",
                         "Some cells lose drivers; partial blackouts",
                         "Health check, miss-rate spike",
                         "Failover to replica; data rebuilds from pings within 10 s"],
                        ["MySQL shard down",
                         "Trips in that city stall",
                         "Connection timeout",
                         "Auto-promote replica; block new requests; queue updates"],
                        ["Disco region overload",
                         "Match latency spikes",
                         "p99 alert &gt; 5 s",
                         "Shed load: queue requests; raise surge to throttle demand"],
                        ["Kafka cluster lag",
                         "Surge stale; analytics lag",
                         "Consumer-lag alert",
                         "Use last-known surge in Redis; backfill events on recovery"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful Degradation",
                    "body": (
                        "If the matching engine is degraded, prioritize active trips: never break "
                        "an in-progress trip's state machine. New requests can be delayed or shown "
                        "'no drivers available' — that's recoverable. A lost in-progress trip is not."
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
                        ["Geo grid", "H3 hex (Uber)",
                         "Equidistant neighbors and uniform area beat S2 / quadtrees for radius search; aperture-7 hierarchy is approximate."],
                        ["Hot location store", "Redis (in-memory)",
                         "Sub-ms reads; loses 10 s of data on node death (rebuilds from pings). MySQL / SQL would be too slow at 1.5M writes/sec."],
                        ["Dispatch model", "Sequential offers, score-ranked",
                         "Lower latency to first offer; locally suboptimal pairings. Batch dispatch optimizes globally but adds 1–2 s."],
                        ["Match latency vs quality", "Greedy with score (rating, accept_rate, ETA)",
                         "Fast and fair. Pure ETA-min would worsen driver fairness; pure rating-max would hurt latency."],
                        ["Sharding", "By city_id",
                         "Local queries dominate; trivially scales out per market. Cross-city trips need extra wiring."],
                        ["Surge cap", "Multiplier capped at 5.0",
                         "Limits gouging and runaway spikes; on real shortages, demand exceeds supply (some riders unhappy)."],
                        ["Trip state", "Strong consistency in MySQL",
                         "Prevents double-acceptance and lost trips; lower throughput than Cassandra for the same row."],
                        ["Routing", "Custom OSRM-like engine",
                         "10 ms ETAs at scale; engineering investment vs using Google Maps API (cost + rate-limit pain)."],
                        ["Driver ping frequency", "4 sec",
                         "Smooth tracking and accurate ETAs; 1 sec would 4× backend load. 30 sec would degrade dispatch."],
                        ["Regional dispatch", "Intra-DC matching only",
                         "Sub-second p99; cross-region rider/driver pairs are rare."],
                    ],
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Scalability & Distribution",
            "subtitle": "Going from one city to a planet",
            "blocks": [
                {"type": "h3", "text": "Horizontal Scaling"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>API Gateway:</strong> stateless; sticky WebSocket sessions per device, scale on connection count",
                        "<strong>Geo-index:</strong> partition by H3 parent cell (res 4); each partition owned by one node",
                        "<strong>Disco:</strong> stateless; sharded by pickup city; horizontally scaled by request rate",
                        "<strong>Trip Service:</strong> sharded by city_id; co-located with MySQL primary for that city",
                        "<strong>Pricing:</strong> Flink job sharded by H3 res-7 key; output to Redis surge:cell:<h3>",
                    ],
                },
                {"type": "h3", "text": "Multi-Region Layout"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Region per continent:</strong> US-East, US-West, EU, APAC, LATAM",
                        "<strong>Local primaries:</strong> matching, trip, pricing all run intra-DC for sub-second p99",
                        "<strong>Driver and rider stickiness:</strong> their session lives in the region serving their city",
                        "<strong>Cross-region async:</strong> only analytics (Kafka mirror) + cross-city tracking",
                    ],
                },
                {"type": "h3", "text": "Capacity Headroom"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Peak driver pings:</strong> 1.5M/sec → ~16 Redis primaries × 100K ops/sec each",
                        "<strong>Peak trip requests:</strong> ~1,200/sec → 50–100 Disco workers handle easily",
                        "<strong>Trip writes:</strong> ~3,000/sec MySQL inserts globally (multi-event per trip) → comfortably within sharded MySQL",
                        "<strong>Headroom:</strong> design for 3× peak; New Year's Eve hits ~2.5× a typical Friday",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "City-as-a-Shard",
                    "body": (
                        "Treating each city as an independent shard gives near-linear scalability "
                        "and clean blast radius. A bug or outage in one city doesn't impact others, "
                        "and onboarding a new city is a configuration step, not an architectural one."
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
                        "Designing Uber is a flagship system-design interview. The key is to "
                        "lead with the geo-indexing decision, drive cleanly through dispatch, "
                        "and finish with surge + the trip state machine. Don't drown in payments."
                    ),
                },
                {"type": "h3", "text": "45-Minute Interview Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (2 min):</strong> 150M MAU, 25M trips/day, 6M concurrent drivers, ping every 4 s → 1.5M updates/sec",
                        "<strong>Capacity (4 min):</strong> 1.5M location writes/sec, ~1,200 trip req/sec at peak, ~50 GB/day trip data",
                        "<strong>Geo-index (6 min):</strong> H3 hex, res 9 dispatch + res 7 surge; hex vs square vs quadtree",
                        "<strong>Architecture (3 min):</strong> Mobile → Gateway → Disco / Geo / Trip / Pricing / Payment / Notify → Redis / MySQL / Kafka / Routing",
                        "<strong>Dispatch deep dive (8 min):</strong> k-ring query, score by ETA + rating + accept rate, sequential offers with 15 s timeout",
                        "<strong>Trip lifecycle (6 min):</strong> state machine, idempotent transitions, saga across services, outbox + Kafka",
                        "<strong>Surge (5 min):</strong> per-cell supply/demand, EWMA, cap at 5×, broadcast pre-request",
                        "<strong>Storage & sharding (4 min):</strong> Redis hot, MySQL by city, Kafka events; H3-aware Redis sharding",
                        "<strong>Failures & trade-offs (5 min):</strong> driver disconnect, surge runaway, payment retry; sync vs batch dispatch",
                        "<strong>Wrap (2 min):</strong> what you'd build first, what you'd defer (international payments, fraud)",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "“1.5M location updates/sec” — drives Redis geo + city sharding decision",
                        "“H3 hex grid: equidistant neighbors, uniform area” — explicit reason over S2 / quadtree",
                        "“k-ring 1, 2, 3 + score by ETA + rating + accept rate” — concrete dispatch algorithm",
                        "“15 s offer timeout, sequential fall-through” — fairness + low contention",
                        "“Trip state machine with idempotent transitions, outbox + Kafka” — distributed correctness",
                        "“Surge per H3 res 7 cell, EWMA-smoothed, capped at 5×, broadcast pre-request” — economics + UX",
                        "“City as a shard” — clean blast radius, near-linear scalability",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why H3 over S2?</strong> A: Hex cells have equidistant neighbors and uniform area, which makes 'k-ring' a true radius search and per-cell metrics fair. S2 is great for indexing but uneven for radius queries.",
                        "<strong>Q: What if two riders request the same driver?</strong> A: Disco locks the driver in Redis on offer (SETNX with TTL). The second match query skips locked drivers; on accept, the lock is committed.",
                        "<strong>Q: How do you avoid surge runaway?</strong> A: Hard cap (5×), EWMA smoothing, minimum dwell time. In emergencies, manual override caps at 1×.",
                        "<strong>Q: How do you handle driver app loss-of-connection?</strong> A: TTL on driver key in Redis (10 s); driver falls out of cell after one missed ping interval. On reconnect they re-register.",
                        "<strong>Q: How do payments not block trip completion?</strong> A: Trip completion is a saga: state goes to <code>completed</code> first, payment is async with retries, and unpaid trips are settled in batch.",
                        "<strong>Q: Sync vs batch dispatch?</strong> A: Default sync (greedy, lowest latency). Switch to batch (1–2 s window, min-cost flow) in dense, high-supply cells where global optimality wins.",
                        "<strong>Q: Why not just GEOADD without H3?</strong> A: GEOSEARCH alone gives a circle, but per-cell metrics (surge, supply heatmaps) need a stable, area-uniform tessellation. H3 + Redis sets is the combo.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "150M MAU &nbsp;·&nbsp; 25M trips/day &nbsp;·&nbsp; 6M concurrent drivers &nbsp;·&nbsp; "
                        "ping every 4 s → <strong>1.5M location writes/sec</strong> &nbsp;·&nbsp; "
                        "~1,200 trip req/sec at peak &nbsp;·&nbsp; H3 res 9 ≈ 0.1 km² (dispatch), res 7 ≈ 5 km² (surge) &nbsp;·&nbsp; "
                        "15 s offer timeout &nbsp;·&nbsp; surge cap 5×."
                    ),
                },
            ],
        },
    ],
}
