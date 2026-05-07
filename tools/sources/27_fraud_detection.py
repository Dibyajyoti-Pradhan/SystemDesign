"""Source for `27 - Fraud Detection.pdf` — fraud detection deep-dive."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design a Fraud Detection System",
    "subtitle": "real-time risk scoring for cards, ACH, and account-to-account transfers at issuer scale",
    "read_time": "~ 45 minute read",
    "short_title": "Design a Fraud Detection System",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Statement",
            "subtitle": "Real-time fraud scoring on the auth path",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Design a real-time fraud detection system for a global card issuer / "
                        "payments platform. Every card swipe, ACH origination, and "
                        "account-to-account transfer must be scored <strong>in-line on the "
                        "authorization path</strong> in under 50 ms p99, with a verdict of "
                        "<code>ALLOW</code>, <code>REVIEW</code>, or <code>DECLINE</code>. The "
                        "system blends a deterministic rules engine (velocity caps, blocked "
                        "geographies, BIN blocklists) with a gradient-boosted ML model fed by "
                        "a streaming feature store, and feeds confirmed-fraud labels back into "
                        "a nightly retraining loop."
                    ),
                },
                {
                    "type": "para",
                    "text": (
                        "The companion <em>Payment Gateway</em> guide covers the auth/capture/"
                        "ledger path end to end; this document zooms into the <strong>risk "
                        "service, feature store, model server, and feedback loop</strong> that "
                        "the gateway calls during the &lsquo;fraud check&rsquo; step. Treat the "
                        "gateway as a fixed upstream caller — our SLO is everything between "
                        "<code>POST /score</code> and the verdict response."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Assumption"],
                    "rows": [
                        ["Transaction types?", "Cards (issuer side), ACH originations, real-time A2A transfers"],
                        ["Scoring mode?", "Synchronous in-line on auth (must respond before the network does)"],
                        ["Inline latency?", "p99 &lt; 50 ms end-to-end including feature lookup + model inference"],
                        ["Throughput?", "~12K TPS sustained, ~50K TPS Black Friday peak"],
                        ["Decisions?", "ALLOW (auto-approve) / REVIEW (queue) / DECLINE (block)"],
                        ["Fraud rate?", "~30 bps (0.3%) of transactions are confirmed fraud"],
                        ["Labels?", "Chargebacks (T+30–120 d) + customer fraud reports + manual-review outcomes"],
                        ["Explainability?", "Required for declines (regulator + dispute evidence)"],
                        ["Retraining?", "Nightly offline; champion/challenger A/B for promotion"],
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
                        ["Score transaction", "POST /score → returns {decision, score, reason_codes} on the auth path"],
                        ["Rules pre-filter", "Hard-block known-bad (sanctioned countries, BIN blocklist, velocity caps)"],
                        ["ML scoring", "Gradient-boosted model on aggregated features; score 0–1000"],
                        ["Manual review queue", "Mid-band scores route to analyst console with case context"],
                        ["Feedback ingestion", "Chargebacks, customer reports, analyst dispositions become labels"],
                        ["Nightly retraining", "Train on last 90 days; promote via shadow + champion/challenger"],
                        ["Audit trail", "Every decision (score, features, model version, rule hits) persisted 7 yr"],
                        ["Explainability", "SHAP-style top-3 reason codes returned with every decision"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Inline latency", "p99 &lt; 50 ms (feature lookup + inference); p50 &lt; 12 ms"],
                        ["Availability", "99.99% on the scoring path; degrade to rules-only on model failure"],
                        ["Throughput", "~12K TPS sustained, ~50K TPS peak; design headroom 2× peak"],
                        ["Freshness", "Streaming features visible &lt; 1 s after the upstream txn"],
                        ["Retraining", "Nightly offline; full retrain in &lt; 4 h on the warehouse"],
                        ["Drift detection", "PSI/KS on features daily; AUC-ROC on labels weekly"],
                        ["Audit retention", "7 years (PCI / SOX / chargeback dispute window)"],
                    ],
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "Math for issuer scale",
            "blocks": [
                {"type": "h3", "text": "Traffic"},
                {
                    "type": "bullets",
                    "items": [
                        "Daily transactions: <strong>~1B</strong> (issuer-scale; cards + ACH + A2A combined)",
                        "Sustained TPS: 1B / 86,400 ≈ <strong>~12K TPS</strong> daily average; ~25K TPS at peak hour",
                        "Black Friday / Cyber Monday peak: bursts to <strong>~50K TPS</strong>; design headroom to 2× peak (~100K TPS) so we never shed load on the auth path",
                        "Read amplification per scored txn: ~30 feature lookups (multi-window aggregates per user/card/device/merchant) → <strong>~360K Redis GETs/sec sustained, ~1.5M/sec peak</strong>",
                        "Confirmed-fraud rate: ~30 bps → <strong>~3M fraud events/day</strong>, the labelled tail of the funnel",
                    ],
                },
                {"type": "h3", "text": "Latency Budget (50 ms p99 inline)"},
                {
                    "type": "table",
                    "headers": ["Stage", "Budget (p99)", "Notes"],
                    "rows": [
                        ["Network in (gateway → risk)", "3 ms", "Same-AZ gRPC; mTLS; pooled connections"],
                        ["Rules engine pre-filter", "5 ms", "In-process; deterministic; short-circuits on hard-block"],
                        ["Feature lookup (Redis)", "12 ms", "~30 keys; pipelined MGET; hot store in same AZ"],
                        ["Model inference", "20 ms", "LightGBM / DNN; co-located server; warm process"],
                        ["Score → decision", "2 ms", "Threshold lookup + reason codes"],
                        ["Audit log write (async)", "0 ms inline", "Fire-and-forget to Kafka; not on critical path"],
                        ["Network out", "3 ms", "Reply gRPC"],
                        ["Headroom", "5 ms", "Sums to 50 ms with slack for tail spikes"],
                    ],
                },
                {"type": "h3", "text": "Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Transaction events (Kafka):</strong> 1B/day × ~1.5 KB ≈ <strong>1.5 TB/day raw</strong>; 7-day retention on hot tier ≈ ~10 TB; replicated 3× ≈ ~30 TB cluster",
                        "<strong>Feature store hot (Redis):</strong> ~500M active entities × ~200 features × ~16 B ≈ <strong>~1.6 TB hot working set</strong>; cluster sized at 2.5 TB to leave headroom",
                        "<strong>Feature store warm (Cassandra / Bigtable):</strong> 12 months of windowed aggregates ≈ <strong>~120 TB</strong> across all entities and windows",
                        "<strong>Decision audit log (Postgres + S3):</strong> 1B/day × ~2 KB ≈ <strong>~2 TB/day</strong>; 90 days online (~180 TB), 7 yr in object storage (~5 PB Glacier)",
                        "<strong>Training warehouse:</strong> last 90 days of features + labels ≈ <strong>~10 TB</strong> in Snowflake / BigQuery",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "1B txns/day &nbsp;·&nbsp; ~12K TPS sustained &nbsp;·&nbsp; "
                        "~50K TPS Black Friday peak &nbsp;·&nbsp; p99 inline &lt; 50 ms &nbsp;·&nbsp; "
                        "~30 feature lookups per scored txn &nbsp;·&nbsp; "
                        "~1.6 TB hot Redis feature store &nbsp;·&nbsp; "
                        "~30 bps fraud rate &nbsp;·&nbsp; nightly retrain on 90 d window."
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level Architecture",
            "subtitle": "Online auth path + offline training",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The system has two clearly separated planes: an <strong>online "
                        "scoring path</strong> (gateway → risk service → feature store + rules "
                        "+ model server → decision) bound by a 50 ms budget, and an "
                        "<strong>offline training path</strong> (transaction events → "
                        "warehouse → daily training → model registry) that updates the model "
                        "the online path serves. A streaming feature pipeline (Flink) bridges "
                        "the two: it consumes the same transaction events that flow through "
                        "the online path and continually updates the feature store so that the "
                        "next inference sees the very latest aggregates."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Online scoring path (solid) and offline training path (dashed). The risk service calls feature store + rules engine + model server in parallel where possible; transactions also fan out to Kafka for streaming feature updates and warehouse landing for nightly retraining.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_online {
        label="Online auth path  (p99 < 50 ms)"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        GW    [label="Payment Gateway\n(upstream)",        fillcolor="#dbe6fb"];
        Risk  [label="Risk Service\n(orchestrator)",       fillcolor="#cbeedf"];
        Rules [label="Rules Engine\n(in-process)",         fillcolor="#fff2c9"];
        FS    [label="Feature Store\n(Redis hot)",         fillcolor="#fff2c9"];
        MS    [label="Model Server\n(LightGBM / DNN)",     fillcolor="#fff2c9"];
        Dec   [label="Decision\nALLOW/REVIEW/DECLINE",     fillcolor="#cbeedf"];
    }

    subgraph cluster_stream {
        label="Streaming feature pipeline"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        K     [label="Kafka\n(transactions)",              fillcolor="#fbd7c5"];
        Flink [label="Flink / Spark Streaming\n(windowed aggregates)", fillcolor="#fff2c9"];
        Cass  [label="Cassandra / Bigtable\n(warm features)", fillcolor="#ead7fb"];
    }

    subgraph cluster_offline {
        label="Offline training path  (nightly)"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        WH    [label="Warehouse\n(Snowflake / BQ)",        fillcolor="#ead7fb"];
        Train [label="Training Job\n(LightGBM / DNN)",     fillcolor="#fff2c9"];
        Reg   [label="Model Registry\n(versioned)",        fillcolor="#ead7fb"];
        Lbl   [label="Labels\n(chargebacks + reports)",    fillcolor="#fbd5d5"];
    }

    subgraph cluster_audit {
        label="Audit + Review"; style="rounded,dashed"; color="#1f6e8c"; fontcolor="#1f6e8c";
        Audit [label="Decision Audit\n(Postgres + S3)",    fillcolor="#cfe6f1"];
        Queue [label="Manual Review\nQueue",               fillcolor="#cfe6f1"];
    }

    GW    -> Risk  [label="POST /score"];
    Risk  -> Rules [label="hard rules"];
    Risk  -> FS    [label="MGET ~30 keys"];
    Risk  -> MS    [label="features"];
    MS    -> Risk  [label="score + SHAP"];
    Risk  -> Dec;
    Dec   -> GW    [label="verdict"];
    Dec   -> Queue [label="REVIEW", style=dashed];
    Dec   -> Audit [label="async log", style=dashed];

    GW    -> K     [label="txn event", style=dashed];
    K     -> Flink [style=dashed];
    Flink -> FS    [label="upsert hot",  style=dashed];
    Flink -> Cass  [label="upsert warm", style=dashed];
    K     -> WH    [label="land daily",  style=dashed];

    Lbl   -> WH    [style=dashed];
    WH    -> Train [label="90 d window", style=dashed];
    Train -> Reg   [label="publish",     style=dashed];
    Reg   -> MS    [label="deploy / A/B", style=dashed];
}
""",
                },
                {"type": "h3", "text": "Component Roles"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Risk Service:</strong> stateless orchestrator that owns the 50 ms budget; fans out to feature store + rules + model server, combines into a verdict",
                        "<strong>Rules Engine:</strong> in-process deterministic short-circuit (hard-block sanctioned countries, BIN blocklist, velocity caps); explainable and auditable",
                        "<strong>Feature Store:</strong> Redis hot (last 24 h aggregates) + Cassandra warm (30 d / 12 mo aggregates); served by feature retrieval API",
                        "<strong>Model Server:</strong> co-located process (Triton / TF-Serving / custom); warm model in memory; supports shadow + champion/challenger A/B",
                        "<strong>Streaming pipeline:</strong> Flink job consumes the txn event stream and continually updates feature store; bounded delay &lt; 1 s",
                        "<strong>Offline trainer:</strong> nightly Spark / Ray job pulls 90 d of features + labels from the warehouse, trains, evaluates, and publishes to the model registry",
                        "<strong>Manual review queue:</strong> mid-band scores routed here; analyst dispositions feed back as labels",
                        "<strong>Decision audit log:</strong> every verdict (score, features used, model version, rule hits) → Postgres (90 d hot) + S3 (7 yr cold) for chargeback dispute evidence",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Layered Defence",
            "subtitle": "Rules + ML + manual review",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Fraud is an adversarial game: rules are explainable but bleed against "
                        "novel patterns; ML catches novel patterns but is opaque to regulators "
                        "and risk teams. Mature systems combine all three layers, each "
                        "responsible for a different type of error."
                    ),
                },
                {"type": "h3", "text": "Layer 1: Rules Engine (Pre-Filter)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Velocity caps:</strong> same card &gt; 5 auths in 60 s → hard decline; same device &gt; 10 cards in 24 h → review",
                        "<strong>Geo / sanctions:</strong> issuing country in OFAC SDN list → hard decline; impossible-travel (US auth then RU auth 30 min later) → review",
                        "<strong>BIN blocklist:</strong> known-compromised BINs from card-network bulletins → hard decline",
                        "<strong>Allow / deny lists:</strong> per-merchant overrides for known good (whitelist) and known bad (blacklist) cards / customers",
                        "<strong>Properties:</strong> deterministic, explainable, ~1–2 ms in-process, ships hourly via config push",
                    ],
                },
                {"type": "h3", "text": "Layer 2: ML Model"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Algorithm:</strong> LightGBM / XGBoost (gradient-boosted trees) for tabular features; optional DNN for sequence / embedding features",
                        "<strong>Inputs:</strong> ~200 features pulled from the feature store at multiple windows (1m / 1h / 1d / 30d) per (user, card, device, merchant)",
                        "<strong>Output:</strong> calibrated risk score 0–1000; SHAP top-3 reason codes returned with the score",
                        "<strong>Latency:</strong> p99 &lt; 20 ms in-process; warm model; no GPU on the auth path",
                        "<strong>Class imbalance:</strong> ~30 bps fraud → undersample non-fraud, oversample fraud, or use focal loss; track precision/recall, not raw accuracy",
                    ],
                },
                {"type": "h3", "text": "Layer 3: Manual Review Queue"},
                {
                    "type": "bullets",
                    "items": [
                        "Mid-band scores (e.g. 600–800) route to a human analyst console with full case context: txn details, recent activity, device fingerprint, geo, model reason codes",
                        "Analyst SLA: typical 2–5 min for high-value txns; auto-approve with timeout for low-value reviews to keep the merchant happy",
                        "Analyst disposition (CONFIRMED_FRAUD / LEGITIMATE / UNCLEAR) feeds back as a high-quality label for retraining",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why All Three",
                    "body": (
                        "Rules carry the regulatory and explainability load (you can show a "
                        "regulator a flowchart). The ML model carries the adaptability load "
                        "(catches patterns no analyst has written a rule for yet). The review "
                        "queue carries the high-value-edge-case load (a human eyeballs the "
                        "$50K wire transfer that scored 0.72). Removing any one layer makes "
                        "the other two demonstrably worse."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Feature Store",
            "subtitle": "Multi-window aggregates per entity",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The feature store is the single most important system in fraud "
                        "detection — fraud signal lives in <em>aggregates over time</em>, not "
                        "in the raw txn. We maintain pre-computed counters and sums per "
                        "<strong>(entity, window)</strong> across four entity classes and four "
                        "window sizes."
                    ),
                },
                {"type": "h3", "text": "Entities × Windows"},
                {
                    "type": "table",
                    "headers": ["Entity", "Examples of features", "Why it matters"],
                    "rows": [
                        ["User", "Auths/min, $/h, distinct merchants/d, distinct countries/30d",
                         "Account-takeover patterns; ATO bursts within minutes of credential theft"],
                        ["Card / PAN", "Failed CVV/h, declines/d, MCC entropy/30d",
                         "Card-testing rings cycle through stolen PANs at high velocity"],
                        ["Device", "Cards used/d, IPs/d, accounts touched/30d",
                         "One device hammering many cards is a near-certain sign of fraud"],
                        ["Merchant", "Chargeback rate/30d, fraud_score histogram, MCC",
                         "Merchant base rate: a high-CB merchant adjusts the prior on every txn"],
                    ],
                },
                {"type": "h3", "text": "Window Sizes"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>1 minute:</strong> burst detection (card-testing, credential-stuffing)",
                        "<strong>1 hour:</strong> session-level patterns (legit checkout vs. spree)",
                        "<strong>1 day:</strong> daily limits, normal customer behaviour",
                        "<strong>30 days:</strong> long-term baseline, tenure, chargeback history",
                    ],
                },
                {"type": "h3", "text": "Hot vs Warm Storage"},
                {
                    "type": "table",
                    "headers": ["Tier", "Store", "Holds", "Latency", "Why"],
                    "rows": [
                        ["Hot",  "Redis (cluster)",   "1 m / 1 h / 1 d aggregates", "&lt; 1 ms / key", "Auth path; 30 keys per scored txn; pipelined MGET"],
                        ["Warm", "Cassandra / Bigtable", "30 d / 12 mo aggregates", "5–10 ms / key", "Less hot; tolerable for scoring; cheaper at petabyte"],
                        ["Cold", "S3 (parquet)",      "Raw events for retraining",  "Minutes (batch)", "Warehouse landing for nightly training"],
                    ],
                },
                {"type": "h3", "text": "Feature Aggregate Row (Redis hot)"},
                {
                    "type": "code",
                    "text": (
                        "# Redis key layout (one key per (entity, window))\n"
                        "Key:   feat:{entity_type}:{entity_id}:{window}\n"
                        "       e.g. feat:user:u_92f1:1m\n"
                        "Value: hash {\n"
                        "    n              : 17,           # txn count in window\n"
                        "    sum_amount_cts : 4_823_00,     # sum of cents\n"
                        "    distinct_mcc   : 4,            # distinct merchant categories\n"
                        "    distinct_geo   : 2,            # distinct countries\n"
                        "    n_decline      : 1,            # declines in window\n"
                        "    last_ts        : 1746537812,   # epoch sec; for window slide\n"
                        "    fraud_label_30d: 0             # any confirmed fraud in last 30 d?\n"
                        "}\n"
                        "TTL:   2 × window length (so a 1m window persists 2 m as a safety margin)\n\n"
                        "# At score time, the risk service builds the feature vector by\n"
                        "# pipelining MGET across ~30 keys (4 entities × multiple windows + scalars)."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Train/Serve Skew is the Killer",
                    "body": (
                        "The single most painful bug in production ML for fraud is "
                        "<em>train/serve skew</em>: features computed differently offline (in "
                        "Spark) vs online (in Flink/Redis). Mitigate with a single feature "
                        "definition library (e.g. Feast) that emits both the streaming and "
                        "batch implementations from the same source, plus daily PSI checks "
                        "comparing online and offline distributions."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Online Feature Aggregation",
            "subtitle": "Streaming windowed counters",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The streaming pipeline is what keeps Redis fresh. A Flink job consumes "
                        "the <code>transactions</code> Kafka topic, partitioned by entity ID, "
                        "and continuously updates per-(entity, window) aggregates. The hot "
                        "path of this update needs to be lock-free, so we use a sliding-window "
                        "counter pattern and atomic Redis HINCRBY."
                    ),
                },
                {"type": "h3", "text": "Sliding-Window Counter"},
                {
                    "type": "code",
                    "text": (
                        "# Flink operator pseudo-code: per-(entity, window) sliding aggregate.\n"
                        "# Each Kafka record represents one transaction; we update counters\n"
                        "# for *every* window the txn belongs to (1m, 1h, 1d).\n\n"
                        "def on_transaction(txn, redis, now_ts):\n"
                        "    for entity_type, entity_id in (\n"
                        "        ('user',     txn.user_id),\n"
                        "        ('card',     txn.card_token),\n"
                        "        ('device',   txn.device_fp),\n"
                        "        ('merchant', txn.merchant_id),\n"
                        "    ):\n"
                        "        for window, length in (('1m', 60), ('1h', 3600), ('1d', 86400)):\n"
                        "            key = f'feat:{entity_type}:{entity_id}:{window}'\n"
                        "            # HINCRBY is atomic; pipelined for batch efficiency.\n"
                        "            pipe = redis.pipeline()\n"
                        "            pipe.hincrby(key, 'n', 1)\n"
                        "            pipe.hincrby(key, 'sum_amount_cts', txn.amount_cts)\n"
                        "            if txn.status == 'DECLINED':\n"
                        "                pipe.hincrby(key, 'n_decline', 1)\n"
                        "            pipe.hset(key, 'last_ts', now_ts)\n"
                        "            pipe.expire(key, 2 * length)  # auto-evict stale windows\n"
                        "            pipe.execute()\n\n"
                        "# Distinct counts (distinct_mcc, distinct_geo) use HyperLogLog\n"
                        "# (PFADD) to keep the per-key memory bounded at ~12 KB regardless of\n"
                        "# cardinality, with ~1% error -- accuracy we can live with for fraud.\n\n"
                        "# Champion/challenger traffic split for safe model rollouts:\n"
                        "def route(txn, hash_seed='fraud_v1'):\n"
                        "    bucket = mmh3.hash(f'{hash_seed}:{txn.id}') % 100\n"
                        "    return 'challenger' if bucket < 5 else 'champion'  # 5% to challenger"
                    ),
                },
                {"type": "h3", "text": "Why TTL = 2 × window"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>1× window:</strong> race-prone — a window can expire mid-update and lose the increment that just fired",
                        "<strong>2× window:</strong> safety margin; the next read will see the freshly slid value",
                        "<strong>Trade-off:</strong> doubles Redis memory for short windows, but short windows are the cheapest to store anyway",
                    ],
                },
                {"type": "h3", "text": "Late / Out-of-Order Events"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Watermarking:</strong> Flink emits per-key watermarks; events older than 30 s are routed to a side output and reconciled offline (rare)",
                        "<strong>Idempotency:</strong> txn_id deduped at the source; same Kafka offset is processed at-most-once per Flink checkpoint",
                        "<strong>Replay:</strong> on Flink restart, replay from the last checkpoint; aggregates are deterministic given the input stream",
                    ],
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Model Serving",
            "subtitle": "Triton / TF-Serving on the auth path",
            "blocks": [
                {"type": "h3", "text": "Co-Located Model Server"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Pattern:</strong> model server runs as a sidecar / in-process library next to the risk service to avoid an extra network hop on the auth path",
                        "<strong>Engines:</strong> NVIDIA Triton (multi-framework, ONNX), TF-Serving (TF / Keras), or a thin custom runner over LightGBM's C API for the fastest path",
                        "<strong>Warmup:</strong> on deploy, run 1,000 synthetic requests through the model before taking traffic — first-request JIT cost is real and shows up on tail",
                        "<strong>No GPU:</strong> tabular gradient-boosted trees are CPU-bound and dominated by feature lookup; GPU adds variance without throughput",
                    ],
                },
                {"type": "h3", "text": "Champion / Challenger A/B"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Champion:</strong> the model currently in production; takes 95% of traffic by default",
                        "<strong>Challenger:</strong> a candidate model trained on newer data or a new architecture; takes 5% to start",
                        "<strong>Split:</strong> deterministic by hash(txn_id) so the same txn always lands in the same bucket — required for clean comparison",
                        "<strong>Promotion:</strong> nightly evaluation on offline-relabelled traffic; promote when challenger AUC ≥ champion AUC at fixed FP rate",
                        "<strong>Kill switch:</strong> single config flip reverts to last-good model in &lt; 60 s; dashboards on score distribution PSI catch silent regressions",
                    ],
                },
                {"type": "h3", "text": "Shadow Mode"},
                {
                    "type": "bullets",
                    "items": [
                        "Net-new models go to <strong>shadow mode</strong> first: they score every transaction but their verdict is logged, not used",
                        "Lets you compare distribution, latency, and downstream impact before any user sees the new model's decision",
                        "Typical bake time: 7–14 days of full-traffic shadow before any A/B starts taking real decisions",
                    ],
                },
                {"type": "h3", "text": "Model Registry"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Versioning:</strong> every trained model gets <code>model_v{semver}+{git_sha}+{train_date}</code>; the registry tracks training data range, feature schema, eval metrics",
                        "<strong>Provenance:</strong> a decision audit row stores the model version that produced it, so when a chargeback comes in 90 days later we can re-explain that exact decision",
                        "<strong>Rollback:</strong> deploys are atomic flag flips backed by the registry — no copying weights around",
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Decision Flow",
            "subtitle": "Score + rules → ALLOW / REVIEW / DECLINE",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The verdict combines (1) a hard rules pre-filter that can short-circuit "
                        "to DECLINE, (2) a model score, (3) a per-merchant + per-customer-tier "
                        "threshold, and (4) post-rules that escalate edge cases to manual "
                        "review. The thresholds are <em>tunable per merchant and per customer "
                        "tier</em> — a luxury merchant on a premium customer might tolerate "
                        "more false positives than a low-margin merchant on a new customer."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Decision flow: rules pre-filter short-circuits known-bad; ML score buckets the rest by per-merchant threshold; mid-band cases escalate to manual review.",
                    "dot": r"""
digraph DecisionFlow {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Start [label="POST /score\n(txn from gateway)", shape=ellipse, fillcolor="#dbe6fb"];

    Rules [label="Rules pre-filter\n(velocity, BIN, OFAC,\nallow/deny list)", fillcolor="#fff2c9"];
    HardBlock [label="Hard rule hit?\n(yes -> DECLINE)", shape=diamond, fillcolor="#fbd5d5"];
    HardAllow [label="Allow-list hit?\n(yes -> ALLOW)",  shape=diamond, fillcolor="#cbeedf"];

    Feat [label="Feature lookup\n(Redis MGET ~30 keys)", fillcolor="#fff2c9"];
    ML   [label="ML score\n(LightGBM)\n0..1000 + SHAP",  fillcolor="#fff2c9"];
    Thresh [label="Per-merchant\nthresholds\n(low/mid/high)", shape=diamond, fillcolor="#ead7fb"];

    Allow   [label="ALLOW\n(auto-approve)",          fillcolor="#cbeedf"];
    Review  [label="REVIEW\n(manual queue)",         fillcolor="#fff2c9"];
    Decline [label="DECLINE\n(block + reason code)", fillcolor="#fbd5d5"];

    Audit [label="Decision audit log\n(Postgres + S3, 7y)", fillcolor="#cfe6f1"];

    Start -> Rules;
    Rules -> HardBlock;
    HardBlock -> Decline [label="yes",   color="#a32e2e"];
    HardBlock -> HardAllow [label="no"];
    HardAllow -> Allow   [label="yes",   color="#1f8359"];
    HardAllow -> Feat    [label="no"];
    Feat   -> ML;
    ML     -> Thresh;
    Thresh -> Allow   [label="score < low (e.g. < 400)",    color="#1f8359"];
    Thresh -> Review  [label="low <= score < high (400-800)"];
    Thresh -> Decline [label="score >= high (>= 800)",      color="#a32e2e"];

    Allow   -> Audit [style=dashed];
    Review  -> Audit [style=dashed];
    Decline -> Audit [style=dashed];
}
""",
                },
                {"type": "h3", "text": "Threshold Tuning"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Per merchant:</strong> a high-CB merchant gets a lower DECLINE threshold (more aggressive); a luxury merchant on premium customers gets a higher one",
                        "<strong>Per customer tier:</strong> long-tenured customers with no fraud history get a generous threshold; new accounts get a tighter one",
                        "<strong>Per channel:</strong> card-not-present is more aggressive than card-present; A2A transfers stricter than card swipes (because reversal is harder)",
                        "<strong>Per amount band:</strong> $50,000 wire transfers always go to manual review regardless of score",
                    ],
                },
                {"type": "h3", "text": "Decision Audit Log"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE fraud_decisions (\n"
                        "  decision_id      UUID PRIMARY KEY,\n"
                        "  txn_id           UUID NOT NULL,\n"
                        "  merchant_id      UUID NOT NULL,\n"
                        "  card_token       VARCHAR(255),\n"
                        "  user_id          UUID,\n"
                        "  amount_cents     BIGINT NOT NULL,\n"
                        "  currency         CHAR(3),\n"
                        "  decision         decision_enum,        -- ALLOW|REVIEW|DECLINE\n"
                        "  score            DECIMAL(6,2),         -- 0-1000\n"
                        "  model_version    VARCHAR(64) NOT NULL,\n"
                        "  rule_hits        TEXT[],               -- e.g. {'velocity_card_1m','bin_blocklist'}\n"
                        "  reason_codes     TEXT[],               -- top-3 SHAP features\n"
                        "  features_snapshot JSONB,               -- the ~200-feature vector at decision time\n"
                        "  threshold_low    DECIMAL(6,2),\n"
                        "  threshold_high   DECIMAL(6,2),\n"
                        "  latency_ms       INT,\n"
                        "  created_at       TIMESTAMPTZ DEFAULT NOW(),\n"
                        "  INDEX (txn_id),\n"
                        "  INDEX (card_token, created_at),\n"
                        "  INDEX (merchant_id, created_at)\n"
                        ");\n\n"
                        "-- Hot in Postgres for 90 d (chargeback dispute window).\n"
                        "-- Archived to S3 (parquet) for the remaining 7 yr.\n"
                        "-- Append-only: if a decision is later overturned, write a new\n"
                        "-- correction row; never UPDATE in place. Audit trail is sacred."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Feedback Loop",
            "subtitle": "Labels, retraining, drift",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Fraud is a moving target: rings retool weekly, merchants change their "
                        "mix, customer behaviour shifts seasonally. A model frozen for a month "
                        "is already losing to the adversary. The feedback loop is what keeps "
                        "the model honest."
                    ),
                },
                {"type": "h3", "text": "Label Sources"},
                {
                    "type": "table",
                    "headers": ["Source", "Latency", "Quality"],
                    "rows": [
                        ["Chargeback files (issuer)",  "T+30 to T+120 d", "High; cardholder-disputed; reason-coded"],
                        ["Customer fraud reports",     "Hours to days",   "Medium; some self-reported false alarms"],
                        ["Manual review dispositions", "Minutes",         "High; analyst-judged; explicit label"],
                        ["3DS challenge outcomes",     "Seconds",         "Low; only proxies fraud risk, not actual fraud"],
                        ["Network fraud bulletins",    "Days",            "Medium; broad-stroke (e.g. 'BIN compromise')"],
                    ],
                },
                {"type": "h3", "text": "Nightly Retraining"},
                {
                    "type": "numbered",
                    "items": [
                        "Land all txn events of the day into the warehouse (S3 / Snowflake / BigQuery)",
                        "Join with labels: chargebacks come in late, so today's training set sees labels for transactions up to ~30 days ago",
                        "Recompute training features <em>using the same definitions</em> as the streaming pipeline (single source of truth library)",
                        "Train champion-arch model on last 90 d; train challenger arch in parallel",
                        "Evaluate offline: AUC-ROC, precision @ fixed recall, KS statistic; check for regression vs current champion",
                        "Publish to model registry with full metadata; <strong>do not auto-promote</strong> — promotion is gated on shadow + A/B",
                    ],
                },
                {"type": "h3", "text": "Concept Drift"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Feature drift:</strong> input distribution moves (e.g. mobile share rises, IP-geo skew shifts); detect with daily PSI / KS on each feature",
                        "<strong>Label drift:</strong> base rate of fraud changes; check daily fraud rate vs trailing 30 d",
                        "<strong>Concept drift:</strong> the relationship between features and fraud changes (e.g. fraud rings adopt a new technique); detect with rolling AUC on labelled traffic",
                        "<strong>Mitigation:</strong> shadow models always running on current traffic; champion/challenger keeps a fresh candidate ready; emergency hot-fix path is a config flip to revert to last-good",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Survivor Bias",
                    "body": (
                        "Your training set only contains decisions you <em>didn't block</em> — "
                        "you can never know what would have happened on the txns you declined. "
                        "Mitigations: (1) reserve 1–2% of high-score traffic to <em>let through</em> "
                        "as exploration so you can observe the outcome; (2) use the manual "
                        "review queue to generate labels on borderline txns. Failing to do "
                        "this means your model gets progressively more confident on its own "
                        "decisions and progressively blinder to its own errors."
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Storage Plan",
            "subtitle": "Where everything lives",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Data", "Store", "Retention", "Why"],
                    "rows": [
                        ["Transaction event stream", "Kafka", "7 d hot, 30 d compacted",
                         "Source of truth for the streaming pipeline; replayable on Flink restart"],
                        ["Hot features (1m / 1h / 1d aggregates)", "Redis cluster", "TTL = 2 × window",
                         "Sub-ms reads on the auth path"],
                        ["Warm features (30 d / 12 mo aggregates)", "Cassandra / Bigtable", "12 months",
                         "Cheaper at petabyte; 5–10 ms reads acceptable for the long-tail features"],
                        ["Decision audit log (hot)", "Postgres", "90 d",
                         "Chargeback dispute window; queryable from the analyst console"],
                        ["Decision audit log (cold)", "S3 (parquet)", "7 yr",
                         "PCI / SOX / regulator + dispute evidence beyond 90 d"],
                        ["Training data + labels", "Snowflake / BigQuery", "90 d active, 2 yr archive",
                         "Nightly retrain + ad-hoc analysis"],
                        ["Model registry", "S3 + Postgres metadata", "Forever",
                         "Provenance: every decision row references a model version that must exist forever"],
                        ["Manual review queue", "Postgres", "30 d active",
                         "Open cases live here; closed cases flow to the audit log"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Why Postgres for Audit",
                    "body": (
                        "The decision audit log is mostly written and rarely read — but when "
                        "it <em>is</em> read it is during a chargeback dispute and the answer "
                        "had better be correct. Postgres gives us strong consistency on the "
                        "write path (no &lsquo;eventually durable&rsquo; surprises), familiar "
                        "indexes for the analyst console, and easy export to S3 for the cold "
                        "tail. Cassandra for audit would tempt us into eventual consistency "
                        "and trade away the one property we cannot trade."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Comparisons",
            "subtitle": "Choices and trade-offs",
            "blocks": [
                {"type": "h3", "text": "Rules vs ML vs Hybrid"},
                {
                    "type": "table",
                    "headers": ["Approach", "Strengths", "Weaknesses"],
                    "rows": [
                        ["Rules only",   "Explainable, fast, regulator-friendly, easy to ship hotfix",
                         "Bleeds against novel fraud; brittle; rule explosion (10K+ rules unmaintainable)"],
                        ["ML only",      "Catches novel patterns; adapts; high recall for the precision",
                         "Opaque to regulators; hard to hotfix; vulnerable to concept drift; survivor bias"],
                        ["Hybrid (rules + ML)", "Rules carry the regulatory and known-bad load; ML carries adaptability; both layers explainable",
                         "Operational complexity; two systems to maintain; need shared feature definitions"],
                    ],
                },
                {"type": "h3", "text": "Gradient Boosting vs DNN vs Graph Models"},
                {
                    "type": "table",
                    "headers": ["Family", "Best at", "Cost", "Verdict"],
                    "rows": [
                        ["LightGBM / XGBoost (GBT)", "Tabular features; quick to train; CPU-fast inference (&lt; 5 ms)",
                         "Low — single CPU; trains nightly on a beefy box",
                         "Default choice for tabular fraud; what most issuers actually run"],
                        ["DNN (tabular)", "Sequence / embedding features; higher capacity",
                         "Higher — GPU train, careful inference; harder to debug",
                         "Use as a complement (e.g. on session sequences) feeding into the GBT"],
                        ["Graph neural nets", "Ring detection (mule networks, device sharing)",
                         "Highest — graph compute infra; offline only",
                         "Run offline as a feature pipeline (graph embedding becomes a feature for the inline GBT)"],
                    ],
                },
                {"type": "h3", "text": "Sync Inline vs Async Post-Auth"},
                {
                    "type": "table",
                    "headers": ["Mode", "When", "Trade-off"],
                    "rows": [
                        ["Sync inline (this design)", "Card auth, A2A transfer, anything with a real-time decision point",
                         "Hard 50 ms budget; can DECLINE in real time; richer customer experience for legit txns; cost: tail-latency engineering is brutal"],
                        ["Async post-auth", "ACH originations with a 1–3 day clearing window; offline batch reviews",
                         "No latency budget; can use richer (slower) features and ensemble models; cost: any decline is a reversal not a block — money has already moved"],
                        ["Two-tier (sync fast + async deep)", "Best of both: a cheap inline model gates the auth, a deeper async model re-scores within minutes",
                         "Most operationally complex; inconsistency window (allowed inline, declined async) requires reversal flow"],
                    ],
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Failure Modes & Recovery",
            "subtitle": "What breaks and how we survive it",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Cause", "Impact", "Mitigation"],
                    "rows": [
                        ["Model server timeout", "Inference &gt; 30 ms; warmup not done; bad release",
                         "Risk service can't get a score in budget",
                         "Hard timeout; <strong>fall back to rules-only</strong>; emit metric; auto-revert deploy after N timeouts"],
                        ["Feature store down (Redis)", "Cluster failover, AZ outage",
                         "No fresh aggregates; ML score is uninformed",
                         "<strong>Degrade to per-transaction-only features</strong> (no history); rules engine still runs; tighten thresholds; alert on-call"],
                        ["Streaming pipeline (Flink) lag", "Kafka consumer lag; bad job",
                         "Features stale by minutes; ML score uses old data",
                         "Monitor lag; pause challenger promotion when lag &gt; 60 s; auto-scale Flink; stale-feature score gets a confidence penalty"],
                        ["Concept drift (silent)", "Fraud ring changes tactics; model unaware",
                         "Recall drops without warning; chargebacks rise weeks later",
                         "PSI/KS daily on features; rolling AUC weekly on labels; shadow model always running; champion/challenger keeps fresh candidate"],
                        ["Bad model deployed", "Training bug; data leak; wrong feature schema",
                         "Score distribution shifts; FP or FN spikes",
                         "Shadow + A/B catches before full rollout; PSI on score distribution as canary; one-flag kill-switch revert in &lt; 60 s"],
                        ["Label leakage", "Future info leaked into features",
                         "Offline AUC looks great; production AUC collapses",
                         "Train/serve skew tests; out-of-time validation; shadow comparison vs current champion"],
                        ["Manual review backlog", "Volume spike; analyst staff out",
                         "REVIEW txns time out; merchants angry",
                         "SLA-based auto-approve for low-amount REVIEW after N min; auto-decline for high-amount after escalation"],
                        ["Audit log write fails", "Postgres outage",
                         "Decision happened but no row; chargeback evidence gap",
                         "Async write to Kafka first (fire-and-forget); Postgres consumer is replayable; never block the auth path on audit"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful Degradation Order",
                    "body": (
                        "Under partial outage, drop in this order: (1) shadow model logging, "
                        "(2) feature freshness (serve last-known features beyond TTL), (3) ML "
                        "score (degrade to rules-only with tighter thresholds), (4) "
                        "<em>never</em> the rules engine. The auth path must always return a "
                        "deterministic verdict in &lt; 50 ms; rules-only is acceptable, no "
                        "verdict is not."
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
                        [
                            "False-positive vs missed-fraud cost",
                            "Per-merchant tunable thresholds; default biased toward letting borderline cases through to manual review",
                            "Each FP is a lost legitimate sale (~$80 average ticket); each FN is a chargeback (~$120 + ~$25 fee + reputation). Aggressive thresholds optimise short-term loss but burn customers and merchants. We let merchants tune their own ALLOW/DECLINE bands and absorb the calibration in REVIEW.",
                        ],
                        [
                            "Latency vs feature richness",
                            "30 features inline (1m/1h/1d aggregates), ~170 more available offline for re-scoring",
                            "Every feature added to the inline path is one more Redis GET in the 50 ms budget. We pre-materialise multi-window aggregates so each one is a single HMGET, not a stream computation; richer features (graph embeddings, sequence models) live in async post-auth re-scoring.",
                        ],
                        [
                            "Explainability vs accuracy",
                            "LightGBM with SHAP top-3 reason codes (good explainability, near-DNN accuracy on tabular)",
                            "DNNs squeeze ~1–3% more AUC on rich features but are opaque; regulators require declined-customer explanations; SHAP on GBT is the practical sweet spot. Reserve DNN for offline ensembles whose output is a feature for the inline GBT.",
                        ],
                        [
                            "Model freshness vs stability",
                            "Nightly retrain → shadow → 5% A/B → promote; never auto-promote without human gate",
                            "Daily retraining catches drift but every promotion is a risk of regression. The shadow + A/B + human-gated registry promotion gives drift-responsiveness without hot-deploying a regression to 100% of traffic.",
                        ],
                        [
                            "Sync inline vs async post-auth",
                            "Inline for cards / A2A (real-time decision); async post-auth re-scoring for ACH and reversible flows",
                            "Inline catches fraud before money moves but locks us into a 50 ms budget. Async has unlimited budget but can only reverse, not block — we use both and pick by transaction type.",
                        ],
                        [
                            "Rules engine vs ML model",
                            "Hybrid: rules carry hard-blocks and regulatory load, ML carries adaptive scoring",
                            "Pure rules bleed against new patterns; pure ML is opaque and brittle on hotfix. The combination is operationally heavier (two systems) but every layer is explainable, hot-fixable, and reviewable.",
                        ],
                        [
                            "Strong vs eventual consistency for features",
                            "Eventual on the feature store (Redis lag &lt; 1 s under normal load)",
                            "Strong consistency on every feature update would gate the entire txn stream behind a single writer. Eventual is fine because <em>every</em> aggregate is approximate by definition (a windowed counter is always &lsquo;at-least-but-maybe-1-late&rsquo;).",
                        ],
                        [
                            "Audit log durability",
                            "Append-only Postgres (90 d hot) + S3 parquet (7 yr cold)",
                            "Mutable audit would let a buggy migration corrupt evidence; append-only with a model_version reference means every old decision is replayable. Cost is storage growth — accepted for the regulatory guarantee.",
                        ],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Headline Tension",
                    "body": (
                        "Fraud detection has two competing obsessions: <strong>recall</strong> "
                        "(don't miss fraud — every miss is a chargeback and a regulator note) "
                        "and <strong>precision</strong> (don't block legit customers — every "
                        "false positive is a lost sale and a furious merchant). Almost every "
                        "design choice tunes the operating point on this curve, and the right "
                        "operating point is per-merchant, per-customer-tier, and per-channel."
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
                        "This guide distils a 45-minute fraud-detection interview into a "
                        "structured narrative. The trick is to keep the online and offline "
                        "planes separate in your head — interviewers test whether you mix them "
                        "up, because confused candidates always do."
                    ),
                },
                {"type": "h3", "text": "Timeline: 5 + 5 + 10 + 20 + 5 minutes"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Opening (5 min):</strong> clarify scope — sync inline scoring on auth path; cards + ACH + A2A; ~12K TPS sustained, ~50K Black Friday peak; p99 &lt; 50 ms",
                        "<strong>Capacity (5 min):</strong> 1B txns/day, ~30 feature lookups per scored txn, ~1.6 TB hot Redis, nightly retrain on 90 d window",
                        "<strong>Architecture (10 min):</strong> Diagram 1 — split online (solid) and offline (dashed) planes; explain risk service as the orchestrator that owns the 50 ms budget",
                        "<strong>Deep dives (20 min):</strong> pick 2–3: feature store (multi-window aggregates), streaming aggregation (Flink + sliding window), decision flow (rules + ML thresholds), feedback loop (labels → retrain → A/B)",
                        "<strong>Wrap-up (5 min):</strong> trade-offs (FP vs FN cost, explainability vs accuracy); failure modes (model timeout → rules-only); closing on the recall/precision tension",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "&ldquo;Layered defence — rules + ML + manual review&rdquo; — every layer carries a different error type",
                        "&ldquo;Feature store is the core system&rdquo; — fraud signal lives in aggregates over time; raw txn alone is useless",
                        "&ldquo;Streaming pipeline keeps the hot store fresh in &lt; 1 s&rdquo; — Flink on Kafka with sliding-window counters",
                        "&ldquo;Champion/challenger A/B with shadow bake&rdquo; — model promotion never auto, always gated",
                        "&ldquo;Concept drift is what kills you, not bugs&rdquo; — daily PSI/KS, weekly rolling AUC, ever-running shadow",
                        "&ldquo;Train/serve skew is the silent killer&rdquo; — single feature definition library for both planes",
                        "&ldquo;Model timeout → fall back to rules-only&rdquo; — never block the auth path on the model",
                    ],
                },
                {"type": "h3", "text": "Common Probe Questions & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why not just rules?</strong> A: They bleed against novel patterns; you'd need 10K+ rules within a year and they become unmaintainable. ML adapts to shifts that no analyst has written a rule for yet.",
                        "<strong>Q: Why not just ML?</strong> A: Regulators require explanations for declines; rules are explainable by construction. And when a fraud ring suddenly hits, you need a hot-fix path that doesn't wait for a retrain.",
                        "<strong>Q: How do you handle class imbalance?</strong> A: ~30 bps fraud → undersample non-fraud (10–50× ratio), use focal loss or class weights, optimise for AUC-PR not accuracy.",
                        "<strong>Q: What if the model server times out?</strong> A: 30 ms hard timeout, fall back to rules-only with tighter thresholds, emit a metric, auto-revert the deploy after N timeouts in 5 min.",
                        "<strong>Q: How do you avoid train/serve skew?</strong> A: Single feature library (e.g. Feast) emits both Spark batch and Flink streaming implementations from one source. PSI checks daily.",
                        "<strong>Q: How do you detect concept drift?</strong> A: Daily PSI/KS on each feature, weekly rolling AUC on labelled traffic, an always-running shadow model, and customer-fraud-report spikes as a leading indicator.",
                        "<strong>Q: What about adversarial attacks?</strong> A: Card-testing attacks pop the velocity rules; credential-stuffing pops the device aggregates; the rules engine is hot-fixable in minutes via config push so you can react faster than retraining.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "1B txns/day &nbsp;·&nbsp; ~12K TPS sustained &nbsp;·&nbsp; "
                        "~50K TPS Black Friday peak &nbsp;·&nbsp; p99 inline &lt; 50 ms &nbsp;·&nbsp; "
                        "~30 feature lookups / scored txn &nbsp;·&nbsp; ~1.6 TB hot Redis &nbsp;·&nbsp; "
                        "~30 bps fraud rate &nbsp;·&nbsp; nightly retrain on 90 d &nbsp;·&nbsp; "
                        "5% challenger A/B &nbsp;·&nbsp; 7 yr audit retention."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Closing Line",
                    "body": (
                        "<em>&ldquo;Fraud detection is about being &lsquo;right enough, fast "
                        "enough&rsquo; — never perfectly right, never instantaneous, but always "
                        "deterministic, always explainable, and always a tiny bit ahead of the "
                        "adversary. The architecture is rules + ML + humans, the operational "
                        "spine is the feature store and the feedback loop, and the discipline "
                        "is to keep the online and offline planes ruthlessly separate.&rdquo;</em>"
                    ),
                },
            ],
        },
    ],
}
