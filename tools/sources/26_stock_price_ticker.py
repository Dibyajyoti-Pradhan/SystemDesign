"""Source for `26 - Stock Price Ticker.pdf`."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design a Stock Price Ticker",
    "subtitle": "real-time market data fan-out to millions of clients (Robinhood / Yahoo Finance scale)",
    "read_time": "~ 40 minute read",
    "short_title": "Design a Stock Price Ticker",
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
                        "Design a real-time <strong>stock price ticker</strong> like the "
                        "Robinhood, Yahoo Finance, or TradingView watchlist. The system ingests "
                        "raw exchange feeds (NYSE / NASDAQ over FIX or ITCH), normalises them, "
                        "and pushes per-symbol price updates to <strong>~10 million</strong> "
                        "concurrent clients with sub-100 ms p99 latency. Clients subscribe to "
                        "small watchlists (10–50 symbols) and only need the latest price, not "
                        "every tick."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Who are the clients?", "Mobile and web users watching a personal watchlist (10–50 symbols)"],
                        ["Concurrent clients?", "~10M during US market hours (9:30–16:00 ET)"],
                        ["Symbol universe?", "~10K listed symbols (NYSE + NASDAQ common stock + ETFs)"],
                        ["Tick rate?", "~5/sec/symbol average; ~500/sec on hot symbols (TSLA, AAPL on news)"],
                        ["Aggregate ingress?", "~50,000 ticks/sec from exchange feed handler"],
                        ["Lossy or lossless?", "Lossy — UI only needs latest tick; coalesce intermediate updates"],
                        ["Latency budget?", "&lt;100 ms p99: exchange tick → gateway → broker → client"],
                        ["History needed?", "Intraday chart + 30 d / 1 y candles via separate TSDB path"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why this problem is hard",
                    "body": (
                        "Naïve fan-out is catastrophic. A hot symbol with 5M watchers at 100 "
                        "ticks/sec would generate <strong>500M push events/sec</strong> — three "
                        "orders of magnitude beyond what any broker fleet can serve. The whole "
                        "design hinges on <strong>per-client coalescing</strong> plus careful "
                        "subscription routing."
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
                        ["Subscribe", "Client opens WebSocket and sends SUBSCRIBE [AAPL, MSFT, ...]"],
                        ["Push", "Server pushes price/size/time updates as ticks arrive"],
                        ["Coalesce", "Throttle to ≤1 update/symbol/200 ms per client; drop intermediates"],
                        ["Snapshot", "On subscribe, send last-known-price immediately from Redis"],
                        ["Unsubscribe", "Client may modify watchlist mid-session without reconnect"],
                        ["History", "Separate REST API for intraday and historical candles (TSDB)"],
                        ["Reconnect", "Clients reconnect with last-seen seq; server replays gap or sends snapshot"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Concurrent clients", "10M peak; 95% during market hours"],
                        ["Latency p50 / p99", "20 ms / 100 ms (exchange → screen)"],
                        ["Availability", "99.99% during market hours; market-hour SLO is sacred"],
                        ["Throughput (ingress)", "50K ticks/sec normalised"],
                        ["Throughput (egress)", "≤300M push frames/sec post-coalesce across fleet"],
                        ["Loss tolerance", "Lossy on intermediate ticks; never lose latest price"],
                        ["Data ordering", "Per-symbol monotonic seq; cross-symbol unordered"],
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
                {"type": "h3", "text": "Ingress: Exchange Feed"},
                {
                    "type": "bullets",
                    "items": [
                        "Universe: <strong>~10K symbols</strong> (NYSE + NASDAQ listed)",
                        "Average tick rate: <strong>5 ticks/sec/symbol</strong> over the day",
                        "Hot-symbol tick rate: <strong>up to 500 ticks/sec</strong> on news (TSLA, AAPL, NVDA)",
                        "Aggregate ingress: <strong>~50,000 ticks/sec</strong> normalised",
                        "Tick payload: ~40 B normalised (symbol_id, price, size, ts, seq) → <strong>~2 MB/sec</strong> ingress",
                    ],
                },
                {"type": "h3", "text": "Subscription Distribution"},
                {
                    "type": "bullets",
                    "items": [
                        "Concurrent clients: <strong>10M</strong>",
                        "Symbols per watchlist: <strong>10–50</strong>; assume avg <strong>30</strong>",
                        "Total subscriptions: 10M × 30 = <strong>300M (client, symbol) pairs</strong>",
                        "Average watchers per symbol: 300M / 10K = <strong>30,000 clients/symbol</strong>",
                        "Hot symbol watchers: <strong>5M</strong> (TSLA at peak retail interest)",
                    ],
                },
                {"type": "h3", "text": "Egress: Naïve vs Coalesced"},
                {
                    "type": "bullets",
                    "items": [
                        "Naïve hot path: 5M watchers × 100 ticks/sec = <strong>500M push events/sec</strong> (one symbol!)",
                        "With <strong>200 ms per-client coalesce</strong>: ≤5 updates/sec/symbol/client",
                        "Coalesced hot path: 5M × 5/sec = <strong>25M frames/sec</strong> for a hot symbol",
                        "Fleet aggregate post-coalesce: ~<strong>10M clients × ~30 active updates/sec</strong> = 300M frames/sec across fleet",
                        "Per broker (10K connections each): <strong>~300K frames/sec/broker</strong> — well within a single NIC",
                    ],
                },
                {"type": "h3", "text": "Storage (TSDB Path)"},
                {
                    "type": "bullets",
                    "items": [
                        "Raw ticks: 50K/sec × 86,400 sec ≈ <strong>4.3B ticks/day</strong>",
                        "Per tick on disk (compressed): ~10 B → <strong>43 GB/day raw</strong>",
                        "Downsampled retention: 1 s for 24 h, 1 min for 30 d, 1 d forever",
                        "Steady-state on-disk: ~<strong>1.5 TB/year</strong> after compression",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "Ingress: <strong>50K ticks/sec</strong> &nbsp;·&nbsp; "
                        "Concurrent clients: <strong>10M</strong> &nbsp;·&nbsp; "
                        "Avg subs/client: <strong>30</strong> &nbsp;·&nbsp; "
                        "Coalesce: <strong>1/symbol/200 ms</strong> &nbsp;·&nbsp; "
                        "Latency budget: <strong>100 ms p99</strong>"
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
                        "Two paths leave the <strong>Tick Gateway</strong>: a "
                        "<strong>real-time fan-out path</strong> that pushes coalesced ticks to "
                        "WebSocket brokers, and an <strong>analytics path</strong> through Kafka "
                        "into the time-series database used for charts. Both fork from the "
                        "<strong>Tick Normaliser</strong>, which converts raw FIX/ITCH frames "
                        "into a uniform internal format and assigns a monotonic per-symbol seq."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Tick flow: exchange feeds ingest at the Tick Gateway, fork to a real-time path (Redis + fan-out brokers → WebSocket clients) and an analytics path (Kafka → TSDB → Chart API).",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_ex {
        label="Exchanges"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        NYSE [label="NYSE\n(FIX / Pillar)", fillcolor="#dbe6fb"];
        NASDAQ [label="NASDAQ\n(ITCH 5.0)", fillcolor="#dbe6fb"];
    }
    subgraph cluster_in {
        label="Ingest"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        GW [label="Tick Gateway\n(feed handler)", fillcolor="#cbeedf"];
        NORM [label="Tick Normaliser\n(seq assign)", fillcolor="#cbeedf"];
    }
    subgraph cluster_rt {
        label="Real-time path"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        REDIS [label="Last-known-price\nRedis (per symbol)", fillcolor="#fff2c9"];
        BUS [label="Fan-out Bus\n(NATS / Kafka topic\nper-symbol)", fillcolor="#fff2c9"];
        FAN [label="Fan-out Brokers\n(sticky WebSocket)", fillcolor="#fff2c9"];
    }
    subgraph cluster_an {
        label="Analytics path"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        KQ [label="Kafka\n(raw_ticks)", fillcolor="#ead7fb"];
        TSDB [label="TSDB\n(KDB+ / Influx)", fillcolor="#ead7fb"];
        API [label="Chart API\n(REST)", fillcolor="#ead7fb"];
    }

    Client [label="Client\n(WebSocket / HTTP/3)", fillcolor="#dbe6fb"];

    NYSE -> GW;
    NASDAQ -> GW;
    GW -> NORM;
    NORM -> REDIS [label="SET last_price"];
    NORM -> BUS [label="publish(symbol)"];
    NORM -> KQ [label="async"];
    BUS -> FAN [label="subscribe(symbol)"];
    FAN -> Client [label="WS push\n(coalesced)"];
    Client -> FAN [label="SUBSCRIBE [AAPL,MSFT]"];
    Client -> API [label="GET /chart/AAPL"];
    KQ -> TSDB;
    TSDB -> API;
}
""",
                },
                {"type": "h3", "text": "Component Responsibilities"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Tick Gateway:</strong> receives raw exchange frames; handles ITCH 5.0 / FIX session, sequencing, gap fills",
                        "<strong>Tick Normaliser:</strong> maps exchange-specific message → uniform Tick struct; assigns monotonic <code>seq</code> per symbol",
                        "<strong>Last-known-price Redis:</strong> hash keyed by symbol → latest price + seq; serves snapshots on subscribe",
                        "<strong>Fan-out Bus:</strong> per-symbol topic (NATS subject or Kafka partition by symbol_id) — brokers pull only what their clients need",
                        "<strong>Fan-out Brokers:</strong> stateful WebSocket servers; maintain symbol→client_set; perform per-client coalescing",
                        "<strong>Kafka raw_ticks:</strong> durable lossless stream for the analytics / TSDB path",
                        "<strong>TSDB:</strong> KDB+ or InfluxDB; powers chart API with downsampled bars",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Subscription & Fan-out Model",
            "subtitle": "Routing ticks to the right clients",
            "blocks": [
                {"type": "h3", "text": "The Mapping Problem"},
                {
                    "type": "para",
                    "text": (
                        "On every tick, a fan-out broker must answer: <em>which of my locally "
                        "connected clients care about this symbol?</em> With ~10K connections "
                        "per broker and 30 subs each, that's ~300K (client, symbol) edges per "
                        "broker. We invert the map: <code>symbol → client_set</code>."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Per-broker subscription map: each client connection holds a sparse bitmap of subscribed symbols; broker also maintains the inverted symbol→clients index that drives fan-out on every tick.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=9, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_c {
        label="Client connections"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        C1 [label="conn_001\nbitmap: {AAPL,MSFT}", fillcolor="#cbeedf"];
        C2 [label="conn_002\nbitmap: {AAPL,TSLA}", fillcolor="#cbeedf"];
        C3 [label="conn_003\nbitmap: {MSFT,GOOG}", fillcolor="#cbeedf"];
    }
    subgraph cluster_idx {
        label="Inverted index (symbol → clients)"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        AAPL [label="AAPL\n→ {001, 002}", fillcolor="#fff2c9"];
        MSFT [label="MSFT\n→ {001, 003}", fillcolor="#fff2c9"];
        TSLA [label="TSLA\n→ {002}", fillcolor="#fff2c9"];
        GOOG [label="GOOG\n→ {003}", fillcolor="#fff2c9"];
    }
    Tick [label="Incoming tick\n(symbol=AAPL,\nprice=192.40)", fillcolor="#dbe6fb"];

    Tick -> AAPL [label="lookup"];
    AAPL -> C1 [label="push (after coalesce)", color="#1f8359"];
    AAPL -> C2 [label="push (after coalesce)", color="#1f8359"];
    C1 -> AAPL [style=dashed, label="SUBSCRIBE", color="#586278"];
    C2 -> AAPL [style=dashed, color="#586278"];
    C2 -> TSLA [style=dashed, color="#586278"];
    C3 -> MSFT [style=dashed, color="#586278"];
}
""",
                },
                {"type": "h3", "text": "Per-Connection State (in broker memory)"},
                {
                    "type": "code",
                    "text": (
                        "// One per connected client (resides in broker)\n"
                        "struct Connection {\n"
                        "    conn_id:        u64,\n"
                        "    user_id:        u64,\n"
                        "    socket:         WebSocket,\n"
                        "    // Sparse bitmap: symbol_id → bit. With 10K symbols a 1.25 KB\n"
                        "    // dense bitmap is fine; for 10–50 syms a small RoaringBitmap is\n"
                        "    // ~100 B and faster to iterate.\n"
                        "    subscriptions: RoaringBitmap,\n"
                        "    // Coalesce state (per subscribed symbol)\n"
                        "    last_pushed:   HashMap<symbol_id, (ts_ms, price)>,\n"
                        "    // Backpressure: bounded queue per connection\n"
                        "    out_queue:     RingBuffer<TickFrame, 256>,\n"
                        "    last_seq:      HashMap<symbol_id, u64>,\n"
                        "}"
                    ),
                },
                {"type": "h3", "text": "Broker-Wide Inverted Index"},
                {
                    "type": "code",
                    "text": (
                        "// Updated on every SUBSCRIBE / UNSUBSCRIBE\n"
                        "// Read on every incoming tick — must be lock-free or RW-locked\n"
                        "type SubIndex = ConcurrentHashMap<symbol_id, ConcurrentSet<conn_id>>;\n\n"
                        "fn on_tick(tick: Tick, idx: &SubIndex, conns: &ConnTable) {\n"
                        "    let Some(client_set) = idx.get(tick.symbol_id) else { return };\n"
                        "    for conn_id in client_set.iter() {\n"
                        "        let conn = conns.get(conn_id);\n"
                        "        if conn.should_emit(tick) {        // 200 ms / 0.1% rule\n"
                        "            conn.enqueue(TickFrame::from(&tick));\n"
                        "        }\n"
                        "    }\n"
                        "}"
                    ),
                },
                {"type": "h3", "text": "Why a Fan-out Bus Per Symbol"},
                {
                    "type": "bullets",
                    "items": [
                        "Each broker only needs the symbols its clients subscribe to — typically <strong>~3K of 10K symbols</strong> on a 10K-conn broker",
                        "Use NATS subjects (<code>ticks.AAPL</code>, <code>ticks.MSFT</code>) or Kafka with partition-per-symbol",
                        "Brokers join/leave subjects dynamically as clients sub/unsub: <strong>no broker receives ticks for symbols nobody on it watches</strong>",
                        "Cuts inter-broker bandwidth from 50K msg/sec/broker to ~15K msg/sec/broker",
                    ],
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Coalescing Algorithm",
            "subtitle": "Lossy throttling that preserves the latest price",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "A ticker UI updates a number on a screen — the user can't perceive "
                        "more than ~5 changes/sec. We exploit this: instead of pushing every "
                        "tick, push at most <strong>one update per symbol per 200 ms per "
                        "client</strong>, but always honour a <strong>significant price move "
                        "(≥ 0.1%)</strong> immediately. This is <em>conflated</em> data — a "
                        "standard pattern in market-data distribution."
                    ),
                },
                {"type": "h3", "text": "Per-Client Coalesce Rule"},
                {
                    "type": "code",
                    "text": (
                        "const COALESCE_MS:    u64 = 200;     // throttle window\n"
                        "const PRICE_DELTA_BP: f64 = 10.0;    // 10 bps = 0.1%\n\n"
                        "fn should_emit(conn: &Connection, tick: &Tick) -> bool {\n"
                        "    let now = now_ms();\n"
                        "    match conn.last_pushed.get(&tick.symbol_id) {\n"
                        "        None => true,                          // first tick → push\n"
                        "        Some((last_ts, last_px)) => {\n"
                        "            let age_ok = now - last_ts >= COALESCE_MS;\n"
                        "            let move_bp = ((tick.price - last_px).abs() / last_px)\n"
                        "                          * 10_000.0;\n"
                        "            let big_move = move_bp >= PRICE_DELTA_BP;\n"
                        "            age_ok || big_move\n"
                        "        }\n"
                        "    }\n"
                        "}\n\n"
                        "fn on_emit(conn: &mut Connection, tick: &Tick) {\n"
                        "    conn.last_pushed.insert(tick.symbol_id, (now_ms(), tick.price));\n"
                        "    // Buffer is a fixed ring; if full → drop oldest non-latest entry\n"
                        "    conn.out_queue.push_or_replace(tick.symbol_id, TickFrame::from(tick));\n"
                        "}"
                    ),
                },
                {"type": "h3", "text": "Why This Works"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Bounded egress:</strong> ≤5 updates/sec/symbol/client → 30 syms × 5 = 150 frames/sec/client max",
                        "<strong>Latest-wins semantics:</strong> ring buffer holds at most one entry per symbol — overwrite, don't append",
                        "<strong>Big moves bypass throttle:</strong> a 0.1% jump on AAPL pushes immediately even within the 200 ms window",
                        "<strong>No global lock:</strong> coalesce state lives on the connection — a single thread per shard owns it",
                    ],
                },
                {"type": "h3", "text": "Coalesce vs No-Coalesce Trade-off"},
                {
                    "type": "table",
                    "headers": ["Mode", "Egress", "Latency", "Use Case"],
                    "rows": [
                        ["No coalesce (raw)", "500M frames/sec hot symbol",
                         "Best — 5–10 ms",
                         "HFT / pro traders paying for L2 feed"],
                        ["Coalesce 200 ms", "~5/sec/sym/client",
                         "20–100 ms (bounded)",
                         "Retail ticker (Robinhood, Yahoo)"],
                        ["Coalesce 1 s", "~1/sec/sym/client",
                         "Up to 1 s",
                         "Cheap watchlist, free tier"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Per-tier coalesce windows",
                    "body": (
                        "Make the 200 ms window a per-tier knob. Free users get 1 s, premium "
                        "200 ms, professional 50 ms. Same broker code, just a config field per "
                        "Connection — saves ~5× egress on the long tail."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Tick Message Format",
            "subtitle": "Wire protocol on the WebSocket",
            "blocks": [
                {"type": "h3", "text": "Goals"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Compact:</strong> ticker frames go over mobile data — every byte counts at 150 frames/sec",
                        "<strong>Self-describing seq:</strong> client must detect gaps and request snapshot",
                        "<strong>Multiplexed:</strong> one WebSocket carries many symbols",
                        "<strong>Binary:</strong> Protobuf or FlatBuffers — JSON adds 3–5× overhead",
                    ],
                },
                {"type": "h3", "text": "Protobuf Schema"},
                {
                    "type": "code",
                    "text": (
                        "syntax = \"proto3\";\n\n"
                        "// Server → client\n"
                        "message TickFrame {\n"
                        "    uint32 symbol_id  = 1;   // dictionary lookup; 4 B vs 5–6 B string\n"
                        "    sint64 price_e6   = 2;   // price × 1e6 as int (avoid float)\n"
                        "    uint32 size       = 3;   // last trade size\n"
                        "    fixed64 ts_us     = 4;   // exchange timestamp, microseconds\n"
                        "    uint64 seq        = 5;   // monotonic per symbol\n"
                        "    uint32 flags      = 6;   // bid/ask/trade/halt bits\n"
                        "}\n\n"
                        "// Client → server\n"
                        "message ClientMsg {\n"
                        "    oneof body {\n"
                        "        Subscribe   subscribe   = 1;\n"
                        "        Unsubscribe unsubscribe = 2;\n"
                        "        Resync      resync      = 3;\n"
                        "    }\n"
                        "}\n"
                        "message Subscribe   { repeated uint32 symbol_ids = 1; }\n"
                        "message Unsubscribe { repeated uint32 symbol_ids = 1; }\n"
                        "message Resync      { uint32 symbol_id = 1; uint64 last_seen_seq = 2; }\n\n"
                        "// Multiplexed envelope (one per WS frame)\n"
                        "message ServerMsg {\n"
                        "    repeated TickFrame ticks    = 1;  // batched per flush\n"
                        "    Snapshot           snapshot = 2;  // sent on subscribe / resync\n"
                        "    uint32             error    = 3;\n"
                        "}\n"
                        "message Snapshot { uint32 symbol_id = 1; sint64 price_e6 = 2;\n"
                        "                   uint64 seq = 3; fixed64 ts_us = 4; }"
                    ),
                },
                {"type": "h3", "text": "Symbol Dictionary"},
                {
                    "type": "bullets",
                    "items": [
                        "Client downloads <code>symbol_id ↔ ticker</code> dictionary on app start (≈ 200 KB, gzipped, cached)",
                        "Refreshed once per trading day (new IPOs, delistings)",
                        "Lets us send <strong>4-byte symbol_id</strong> instead of 5–6 B ASCII tickers",
                    ],
                },
                {"type": "h3", "text": "Wire Size"},
                {
                    "type": "bullets",
                    "items": [
                        "Per TickFrame on the wire: <strong>~22–28 B</strong> (varint-packed)",
                        "Batch 8 ticks per WS frame → <strong>~200 B</strong> + 4 B WS header",
                        "10M clients × 30 active syms × 5 Hz × 25 B ÷ 8 = <strong>~470 MB/sec</strong> outbound across the fleet",
                    ],
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Transport: WebSocket vs Alternatives",
            "subtitle": "Why long-lived push, with HTTP/3 fallback",
            "blocks": [
                {"type": "h3", "text": "Comparison"},
                {
                    "type": "table",
                    "headers": ["Transport", "Push?", "Pros", "Cons"],
                    "rows": [
                        ["WebSocket",
                         "Yes (full duplex)",
                         "Binary; low overhead; widely supported; works through proxies",
                         "Sticky session; one TCP per client; can stall under packet loss"],
                        ["SSE (Server-Sent Events)",
                         "Server → client only",
                         "Plain HTTP; auto-reconnect; firewall-friendly",
                         "Text-only; no client→server multiplex; one-way subscribe is awkward"],
                        ["HTTP/3 (QUIC) streams",
                         "Yes (per-stream)",
                         "No head-of-line blocking; better on lossy mobile",
                         "Proxy support uneven; library maturity"],
                        ["Long-poll",
                         "Simulated",
                         "Works anywhere",
                         "30K reqs/sec on 10M clients = unbearable; high latency"],
                    ],
                },
                {"type": "h3", "text": "Recommendation"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Primary:</strong> WebSocket over TLS 1.3, HTTP/2 upgrade",
                        "<strong>Fallback:</strong> HTTP/3 long-poll for clients behind corporate proxies that block WS",
                        "<strong>Heartbeat:</strong> binary <code>PING</code> every 25 s; client ACK or reconnect after 60 s silence",
                        "<strong>Compression:</strong> permessage-deflate <em>off</em> — Protobuf is already compact, deflate adds CPU",
                    ],
                },
                {"type": "h3", "text": "Sticky Sessions"},
                {
                    "type": "para",
                    "text": (
                        "Each WebSocket terminates on a single broker that owns its "
                        "subscription state. The L7 load balancer (Envoy / Nginx) hashes by "
                        "<code>conn_id</code> cookie or by client IP for the initial upgrade "
                        "request. After that, the WS is pinned for the session — moving it "
                        "would require state migration."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Sticky vs stateless",
                    "body": (
                        "Sticky sessions simplify state but couple availability to broker "
                        "uptime. A broker crash drops 10K connections. Mitigate with: fast "
                        "client reconnect (≤2 s), <strong>last-seen seq replay</strong>, and "
                        "<strong>graceful drain</strong> for deploys (50% drain over 30 s)."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Time-Series Storage Path",
            "subtitle": "Charts, candles, history",
            "blocks": [
                {"type": "h3", "text": "Why a Separate Path"},
                {
                    "type": "para",
                    "text": (
                        "The real-time path is lossy and only carries the latest price. The "
                        "TSDB path is <strong>lossless</strong> — every tick is durably "
                        "written to Kafka, then ingested into a time-series database that "
                        "powers chart APIs (1-minute candles, intraday history, daily bars)."
                    ),
                },
                {"type": "h3", "text": "TSDB Comparison"},
                {
                    "type": "table",
                    "headers": ["Database", "Strengths", "Weaknesses", "Use"],
                    "rows": [
                        ["KDB+",
                         "Industry std for tick data; columnar; q-language analytics",
                         "Expensive license; niche skills",
                         "Hedge funds; HFT-grade tick storage"],
                        ["InfluxDB",
                         "Easy to operate; good downsampling (continuous queries); HTTP API",
                         "Cardinality limits; OSS scaling pain",
                         "Mid-scale ticker, dashboards"],
                        ["TimescaleDB",
                         "Postgres compatibility; SQL; hypertables",
                         "Write throughput vs purpose-built TSDBs",
                         "If you already run Postgres"],
                        ["Cassandra",
                         "Massive write throughput; multi-region",
                         "Range scans across symbol+time slow; manual aggregation",
                         "Raw archive only"],
                    ],
                },
                {"type": "h3", "text": "Retention & Downsampling"},
                {
                    "type": "table",
                    "headers": ["Granularity", "Retention", "Bars/day/symbol", "Use"],
                    "rows": [
                        ["1-second", "24 hours", "~23,400", "Intraday high-detail chart"],
                        ["1-minute", "30 days", "390", "Default chart view"],
                        ["1-day OHLCV", "Forever", "1", "Long-term history; analytics"],
                    ],
                },
                {"type": "h3", "text": "Ingestion"},
                {
                    "type": "bullets",
                    "items": [
                        "Tick Normaliser publishes to Kafka topic <code>raw_ticks</code> (partition by symbol_id, RF=3)",
                        "TSDB writer consumes; batches 1000 ticks per flush; <strong>at-least-once</strong> semantics",
                        "Downsampler runs as Kafka Streams or Flink job: tick → 1 s bar → 1 min bar → 1 d bar",
                        "Continuous queries (Influx) or scheduled <code>kdb+ tick</code> rollups (KDB+)",
                    ],
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Latency Budget",
            "subtitle": "100 ms p99 — where does it go?",
            "blocks": [
                {"type": "h3", "text": "Hop-by-hop"},
                {
                    "type": "table",
                    "headers": ["Hop", "Budget", "Notes"],
                    "rows": [
                        ["Exchange → Tick Gateway", "1–3 ms",
                         "Co-located in NYSE / NASDAQ data centres; cross-connect"],
                        ["Gateway → Normaliser", "&lt; 1 ms",
                         "Same host or shared-memory ring buffer"],
                        ["Normaliser → Fan-out Bus", "1–5 ms",
                         "NATS in-memory pub/sub; one DC hop"],
                        ["Bus → Broker", "1–3 ms",
                         "Brokers subscribe to needed subjects; in-region"],
                        ["Broker coalesce buffer", "0–200 ms",
                         "By design: throttling window; bounded"],
                        ["Broker → client (network)", "20–60 ms",
                         "Mobile RTT dominates; TLS established already"],
                        ["Total p99", "&lt; 100 ms",
                         "Budget mostly absorbed by mobile last-mile + coalesce"],
                    ],
                },
                {"type": "h3", "text": "Where Things Go Wrong"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>GC pauses on broker:</strong> use Rust / Go with low-pause GC; budget &lt;5 ms p99",
                        "<strong>NIC saturation:</strong> 100 Gbps NICs; monitor <code>tx_drop</code>",
                        "<strong>Backpressure on client:</strong> slow mobile fills socket buffer → ring drops oldest non-latest",
                        "<strong>Cross-AZ hop:</strong> keep gateway, bus, brokers <em>in the same AZ</em> as the exchange feed",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Co-location matters",
                    "body": (
                        "Even a single trans-continental hop (~70 ms one-way US East ↔ West) "
                        "blows the 100 ms budget. Run a full ingest+fan-out stack <em>per "
                        "region</em> with replicated Kafka for the analytics path only. "
                        "Real-time path is regional, not global."
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Failure Modes & Recovery",
            "subtitle": "What can go wrong",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["Exchange feed gap (seq jump)",
                         "Missing ticks; stale prices",
                         "Sequence-gap monitor in Normaliser",
                         "Backfill from secondary feed (e.g., NASDAQ TotalView ↔ NYSE OpenBook); request retransmit; mark symbol stale until repaired"],
                        ["Primary feed disconnect",
                         "All ticks halted",
                         "Heartbeat from FIX session; 5 s timeout",
                         "Auto-failover to redundant feed; alert; clients keep last-known-price with 'stale' badge"],
                        ["Fan-out broker crash",
                         "10K connections drop",
                         "Health check; LB ejects",
                         "Clients reconnect with <code>resync(symbol, last_seen_seq)</code>; broker fleet auto-scales"],
                        ["Redis last-price down",
                         "New subscribers see no snapshot",
                         "Redis sentinel alert",
                         "Failover to replica; brokers serve stale snapshot from local cache for 30 s"],
                        ["Kafka raw_ticks lag",
                         "TSDB stale; charts behind",
                         "Consumer-lag metric",
                         "Real-time path unaffected; scale TSDB writers; replay from Kafka"],
                        ["Hot-symbol overload",
                         "Broker CPU spike on news",
                         "Per-symbol rate metric",
                         "Per-symbol surge protection: drop coalesce window to 500 ms for that symbol fleet-wide"],
                        ["Network partition",
                         "Cross-AZ unreachable",
                         "Connection error rate",
                         "Each AZ has its own ingest+fan-out; client reconnects to nearest healthy broker via DNS"],
                    ],
                },
                {"type": "h3", "text": "Client Reconnect Protocol"},
                {
                    "type": "numbered",
                    "items": [
                        "Client detects WS close or 60 s silence",
                        "Reconnects with exponential backoff capped at 5 s; resolves DNS to nearest broker",
                        "Sends Subscribe + per-symbol <code>last_seen_seq</code> (resync messages)",
                        "Broker compares against Redis last-price + Kafka tail; sends Snapshot if gap is non-trivial",
                        "Client merges snapshot, resumes streaming",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Market-hour SLO is sacred",
                    "body": (
                        "9:30 am ET (US market open) is the worst time for an outage. Freeze "
                        "deploys 30 min before open through close. Use canary brokers (1% of "
                        "fleet) with auto-rollback if error rate &gt; 0.5%."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Scaling the Broker Fleet",
            "subtitle": "From 1M to 10M concurrent connections",
            "blocks": [
                {"type": "h3", "text": "Broker Capacity Planning"},
                {
                    "type": "bullets",
                    "items": [
                        "Per broker: <strong>10K connections</strong> (limited by ulimit, FDs, kernel buffers)",
                        "Memory: 10K × ~30 KB/conn (sockets + bitmap + coalesce state) = <strong>~300 MB/broker</strong>",
                        "CPU: ~300K frame writes/sec; on 16-core m6i.4xlarge: ~30% CPU at peak",
                        "Fleet size: 10M / 10K = <strong>1,000 brokers</strong>; over-provision to 1,500 for headroom + canaries",
                    ],
                },
                {"type": "h3", "text": "Auto-scaling Triggers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Scale up:</strong> &gt;7K connections per broker for 5 min",
                        "<strong>Scale up:</strong> p99 broker CPU &gt;70% for 5 min",
                        "<strong>Scale down:</strong> &lt;3K connections per broker for 30 min (sticky drains take time)",
                        "<strong>Pre-warm:</strong> 30 min before US open, scale fleet to 120% of yesterday's peak",
                    ],
                },
                {"type": "h3", "text": "Sharding the Subscription Index"},
                {
                    "type": "para",
                    "text": (
                        "The inverted <code>symbol → client_set</code> index is "
                        "<em>per-broker</em> — not global. Each broker only knows its own "
                        "10K clients. Scaling brokers does not scale a shared structure; the "
                        "fan-out bus does the global routing. This is what makes "
                        "<strong>linear horizontal scaling</strong> possible."
                    ),
                },
                {"type": "h3", "text": "Dictionary / Symbol Updates"},
                {
                    "type": "bullets",
                    "items": [
                        "New listings (IPOs) added overnight; brokers reload dictionary at session boundary",
                        "Delistings → mark symbol_id as <em>removed</em> for 30 days; reject new subs",
                        "Corporate actions (splits, dividends) emitted as control frames; client adjusts last_pushed cache",
                    ],
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
                        ["Coalesce ticks?", "Yes (200 ms / 0.1%)",
                         "Bounds egress at 10M-client scale; loses intermediate prints. Acceptable for retail UI; <em>not</em> for HFT."],
                        ["Loss model", "Lossy real-time, lossless analytics",
                         "Two paths add complexity; preserves history while keeping live cheap."],
                        ["Transport", "WebSocket primary, HTTP/3 fallback",
                         "Sticky sessions complicate failover but give 30% lower CPU than long-poll at 10M clients."],
                        ["Sticky vs stateless", "Sticky",
                         "Crashes drop 10K conns at once; clients reconnect in &lt;2 s. Stateless would need a global sub index — much costlier."],
                        ["Bus", "Per-symbol topic (NATS / Kafka)",
                         "Avoids broadcasting all 50K ticks/sec to every broker; adds many topics."],
                        ["Snapshot source", "Redis last-known-price",
                         "Adds a hot-path Redis dep; saves replaying Kafka on every subscribe."],
                        ["TSDB", "KDB+ (or Influx)",
                         "Best-in-class for ticks; license cost. Cassandra alone would need huge custom rollup work."],
                        ["Region model", "Real-time per-region; analytics global",
                         "Latency budget forces it; a NYSE-listed symbol still has ~70 ms RTT to APAC clients no matter what."],
                        ["Symbol IDs", "Numeric dictionary, not strings",
                         "Saves ~30% wire bytes; clients must keep dictionary in sync."],
                        ["Compression", "Off (rely on Protobuf)",
                         "Lower CPU on broker; loses ~10% bandwidth — net win on a 10M-conn fleet."],
                    ],
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Deep Dive: Hot Symbol Storms",
            "subtitle": "The TSLA-on-news problem",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "On news days, a single symbol can spike from 5 ticks/sec to "
                        "<strong>500 ticks/sec</strong> with millions of watchers. Even after "
                        "coalesce, every broker that has TSLA subscribers must process 500 "
                        "incoming ticks/sec for that symbol, fan out to ~5,000 local "
                        "subscribers each, and apply the per-client coalesce check. This is "
                        "the <em>single biggest CPU spike</em> in the system."
                    ),
                },
                {"type": "h3", "text": "Mitigations"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Hot-symbol coalesce at the bus:</strong> fan-out bus pre-coalesces to 50 Hz before delivering to brokers — cuts broker work by 10×",
                        "<strong>Adaptive window:</strong> when broker CPU &gt; 70%, dynamically widen coalesce from 200 ms to 500 ms <em>for that symbol only</em>",
                        "<strong>Frame batching:</strong> brokers flush WS write queue every 50 ms — combine multiple symbols into one frame, amortising syscall cost",
                        "<strong>Drop-oldest ring buffer:</strong> if a slow client can't keep up, drop intermediates — never block the broker",
                        "<strong>Per-symbol broker pinning:</strong> for top-100 symbols, dedicate a broker shard with extra cores",
                    ],
                },
                {"type": "h3", "text": "Adaptive Coalesce Pseudocode"},
                {
                    "type": "code",
                    "text": (
                        "// Runs once per second per broker\n"
                        "fn adapt_coalesce(broker: &mut Broker) {\n"
                        "    let cpu = read_cpu_pct();\n"
                        "    let window = match cpu {\n"
                        "        c if c > 85 => 1000,   // emergency: 1 s\n"
                        "        c if c > 70 =>  500,   // throttle\n"
                        "        c if c > 50 =>  300,\n"
                        "        _           =>  200,   // default\n"
                        "    };\n"
                        "    for sym in broker.hot_symbols() {        // top-N by tick rate\n"
                        "        broker.coalesce_window.insert(sym, window);\n"
                        "    }\n"
                        "    // Long-tail symbols stay at 200 ms regardless\n"
                        "}"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Halt frames bypass everything",
                    "body": (
                        "Trading halts (LULD, news pending) must reach clients in &lt;1 s "
                        "— they are <em>control</em> messages, not price ticks. Mark them "
                        "with a flag bit; brokers bypass coalesce and emit immediately."
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
                        "This is a fan-out problem dressed up as a market-data problem. The "
                        "interview signal is your ability to spot the <strong>multiplicative "
                        "blow-up</strong> (5M × 100 = 500M/sec) and design coalescing as the "
                        "first-order defence. Numbers must be self-consistent."
                    ),
                },
                {"type": "h3", "text": "45-Minute Interview Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (2 min):</strong> clarify scale (10M clients, 30 syms, 50K ticks/sec, 100 ms p99)",
                        "<strong>Capacity (5 min):</strong> compute the 500M/sec naïve fan-out — make the interviewer sweat",
                        "<strong>High-level arch (5 min):</strong> two paths (real-time vs analytics); fan-out bus per symbol",
                        "<strong>Subscription model (8 min):</strong> per-broker inverted index; sticky WebSocket; bitmap per conn",
                        "<strong>Coalesce (8 min):</strong> 200 ms / 0.1% rule; ring buffer with overwrite; per-tier windows",
                        "<strong>Wire format (5 min):</strong> Protobuf, symbol_id dictionary, batching",
                        "<strong>Failures (5 min):</strong> feed gap → backfill; broker crash → resync(seq); hot symbol → adaptive window",
                        "<strong>Trade-offs (4 min):</strong> sticky vs stateless, lossy vs lossless, real-time vs analytics paths",
                        "<strong>Wrap (3 min):</strong> repeat memorize-these-numbers; offer extension (options, L2 book)",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "“Naïve fan-out for one hot symbol = 500M events/sec — coalescing is non-negotiable”",
                        "“Per-symbol fan-out bus means each broker only pulls the ~3K symbols its clients want”",
                        "“200 ms / 0.1% coalesce: bounded egress and bounded staleness simultaneously”",
                        "“Real-time path is lossy by design; lossless TSDB path is the system of record”",
                        "“Sticky WebSocket trades crash blast radius (10K conns) for simpler state”",
                        "“Co-locate gateway, bus, brokers in same AZ as exchange feed — physics, not engineering”",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: How do you handle a client subscribed to TSLA when the broker crashes?</strong> A: WS closes, client reconnects in &lt;2 s, sends <code>resync(TSLA, last_seen_seq)</code>; new broker fetches snapshot from Redis (last-known-price) and resumes streaming.",
                        "<strong>Q: Why not just use a shared Redis pub/sub?</strong> A: Redis pub/sub is broadcast — every subscriber gets every message on the channel. Per-symbol fan-out at scale needs broker-side filtering anyway, plus Redis pub/sub is lossy on disconnect. NATS or Kafka with per-symbol topics + durability for replay is the right tool.",
                        "<strong>Q: How do you bound memory on a slow client?</strong> A: Bounded ring buffer per connection (256 frames). Slow client → ring fills → we overwrite the oldest <em>non-latest</em> entry per symbol. Latest price always survives; intermediates are sacrificed.",
                        "<strong>Q: Do you need ordering?</strong> A: Per-symbol monotonic seq, yes — derived from exchange seq. Cross-symbol ordering is irrelevant (UI doesn't care if MSFT or AAPL updates first).",
                        "<strong>Q: What about pre-market / after-hours?</strong> A: Tick rate is ~10× lower, so capacity is fine. Same code path; flag in tick payload distinguishes session.",
                        "<strong>Q: How do you bill / meter this?</strong> A: Each subscribe goes through an entitlement check (tier → max symbols, coalesce window). Audit via Kafka entitlements topic.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "<strong>50K ticks/sec</strong> ingress &nbsp;·&nbsp; "
                        "<strong>10K symbols</strong> &nbsp;·&nbsp; "
                        "<strong>10M clients</strong> &nbsp;·&nbsp; "
                        "<strong>30 subs/client</strong> avg &nbsp;·&nbsp; "
                        "<strong>30K watchers/symbol</strong> avg, <strong>5M</strong> hot &nbsp;·&nbsp; "
                        "<strong>200 ms / 0.1%</strong> coalesce &nbsp;·&nbsp; "
                        "<strong>100 ms p99</strong> end-to-end &nbsp;·&nbsp; "
                        "<strong>10K conns/broker</strong>, <strong>~1,000 brokers</strong> in fleet."
                    ),
                },
            ],
        },
    ],
}
