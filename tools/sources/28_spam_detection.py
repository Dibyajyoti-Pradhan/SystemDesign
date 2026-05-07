"""Source for `28 - Spam Detection.pdf`."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Spam Detection",
    "subtitle": "real-time spam and abuse classification at planet scale (email, comments, posts, listings)",
    "read_time": "~ 45 minute read",
    "short_title": "Design Spam Detection",
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
                        "Design a <strong>spam and abuse detection</strong> system that scores every "
                        "incoming message in real time and decides whether it lands in the inbox, "
                        "the spam folder, or is dropped outright. The same pipeline must extend to "
                        "comments, social-media posts and marketplace listings. The threat model "
                        "is <strong>adversarial</strong>: spammers actively probe and mutate to "
                        "evade detection."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Surfaces?", "Email primarily; reuse pipeline for comments / posts / listings"],
                        ["Volume?", "~300 B emails/day globally; 3.5 M/sec at peak"],
                        ["Latency budget?", "Inline scoring p99 &lt; 50 ms (must not delay delivery)"],
                        ["Action set?", "ALLOW / SPAM-FOLDER / QUARANTINE / DROP / CHALLENGE"],
                        ["Feedback?", "Users mark ‘Report spam’ / ‘Not spam’; bounces; engagement"],
                        ["Adversarial?", "Yes — content mutation, image-only spam, URL shorteners"],
                        ["Privacy?", "Body never leaves region; features hashed before storage"],
                        ["Multi-tenant?", "Yes, per-tenant rules + global model"],
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
                        ["Inline scoring", "Synchronous score on every message; verdict before delivery"],
                        ["Layered defence", "Pre-filters → rules → ML classifier → deep model (borderline only)"],
                        ["Sender reputation", "Per-IP, per-domain, per-ASN scores updated continuously"],
                        ["Content fingerprint", "SimHash + LSH for near-duplicate spam waves"],
                        ["Feedback loop", "Capture user reports; nightly retrain; champion / challenger"],
                        ["Audit & explain", "Persist verdict + features for every message (90-day TTL)"],
                        ["Appeals", "Users / senders can request review of decisions"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Throughput", "3.5 M messages/sec at peak; 300 B/day"],
                        ["Latency", "Pre-filter p99 &lt; 5 ms; full pipeline p99 &lt; 50 ms"],
                        ["Availability", "99.99% — fail-open to ‘ALLOW with low confidence’ on outage"],
                        ["False positive", "&lt; 0.1% (legit mail in spam folder is the worst error)"],
                        ["False negative", "&lt; 1% catch rate floor on bulk spam"],
                        ["Model freshness", "Hot blocklists in &lt; 60 s; full model nightly"],
                        ["Storage", "~ 1.5 PB raw events / day; 90-day verdict log"],
                    ],
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "Math for planet-scale email",
            "blocks": [
                {"type": "h3", "text": "Traffic"},
                {
                    "type": "bullets",
                    "items": [
                        "Global email: <strong>~300 B/day</strong> (industry estimate, all senders)",
                        "Average rate: 300 B / 86,400 s ≈ <strong>3.47 M/sec</strong>",
                        "Peak factor 1.0× (always-on traffic) → call it <strong>3.5 M/sec at peak</strong>",
                        "Comments / posts / listings reuse the same path at ~10% of email volume",
                        "<strong>~95% of mail is rejected before bytes hit the model</strong> (RBL, SPF, rate)",
                    ],
                },
                {"type": "h3", "text": "Layered Funnel"},
                {
                    "type": "table",
                    "headers": ["Stage", "QPS in", "QPS out", "Reject rate"],
                    "rows": [
                        ["L0 IP / RBL pre-filter", "3.5 M/sec", "350 K/sec", "~ 90%"],
                        ["L1 SPF/DKIM/DMARC + reputation", "350 K/sec", "70 K/sec", "~ 80%"],
                        ["L2 Hand-crafted rules", "70 K/sec", "30 K/sec", "~ 60%"],
                        ["L3 GBDT classifier (LightGBM)", "30 K/sec", "3 K/sec", "~ 90% scored, 10% borderline"],
                        ["L4 Deep model (BERT) on borderline", "3 K/sec", "n/a", "final adjudication"],
                    ],
                },
                {"type": "h3", "text": "Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "Verdict log: 300 B/day × 500 B per row ≈ <strong>150 TB/day raw → ~ 50 TB compressed</strong>",
                        "90-day retention: 90 × 50 TB ≈ <strong>4.5 PB</strong> compressed (Parquet on S3)",
                        "Sender reputation hot store: 100 M IPs × 200 B ≈ <strong>20 GB Redis</strong>",
                        "Sender reputation warm: 5 B (IP, domain, ASN) × 200 B ≈ <strong>1 TB RocksDB</strong>",
                        "Fingerprint index (SimHash): 30 d × 1 B fingerprints × 24 B ≈ <strong>720 GB</strong>",
                    ],
                },
                {"type": "h3", "text": "Compute"},
                {
                    "type": "bullets",
                    "items": [
                        "L3 LightGBM @ 30 K/sec, 1 ms / score → ~ 30 cores. Replicate 5× for HA → <strong>150 cores</strong>",
                        "L4 BERT-small @ 3 K/sec, 8 ms on T4 → ~ 24 GPU-seconds/sec → <strong>~30 T4 GPUs</strong>",
                        "Feature store reads: ~ 200 K/sec (10 features × L1 funnel) → 5-node Redis cluster",
                        "Training: 30 days of labels × 1 B labels/day ≈ <strong>30 B examples</strong>; nightly Spark/Ray job",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "<strong>3.5 M/sec</strong> peak &nbsp;·&nbsp; "
                        "<strong>p99 &lt; 50 ms</strong> &nbsp;·&nbsp; "
                        "<strong>FP &lt; 0.1%</strong> / FN &lt; 1% &nbsp;·&nbsp; "
                        "<strong>5 layers</strong>, each rejects ~10× &nbsp;·&nbsp; "
                        "<strong>~30 GPUs</strong> for borderline BERT &nbsp;·&nbsp; "
                        "<strong>4.5 PB</strong> verdict log / 90 d."
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level Architecture",
            "subtitle": "Online scoring + offline learning",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Two loops cooperate. The <strong>online (synchronous) path</strong> sits in "
                        "the SMTP / posting hot path: pre-filter, feature extractor, model server, "
                        "decision. The <strong>offline (training) path</strong> tails verdict events "
                        "and user feedback into Kafka, builds features, trains models, and pushes "
                        "new artefacts back into the model server through a model registry."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Online scoring path (top, blue) and offline learning loop (bottom, purple). The model server reads features from the online feature store; the training pipeline tails Kafka and writes back to the registry.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_ingress {
        label="Ingress"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        SMTP [label="SMTP / Post API\n3.5 M/sec", fillcolor="#dbe6fb"];
    }
    subgraph cluster_online {
        label="Online Scoring"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        PRE  [label="Pre-Filter\n(IP RBL, SPF/DKIM)", fillcolor="#cbeedf"];
        FE   [label="Feature\nExtractor", fillcolor="#cbeedf"];
        MS   [label="Model Server\n(GBDT + BERT)", fillcolor="#cbeedf"];
        DEC  [label="Decision\nALLOW / SPAM / DROP", fillcolor="#cbeedf"];
    }
    subgraph cluster_storage {
        label="Online Stores"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        REP  [label="Reputation\nRedis (hot)", fillcolor="#fff2c9"];
        FS   [label="Feature Store\n(low-latency)", fillcolor="#fff2c9"];
        FP   [label="SimHash Index\n(LSH)", fillcolor="#fff2c9"];
    }
    subgraph cluster_delivery {
        label="Delivery"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        INBOX [label="Inbox", fillcolor="#dbe6fb"];
        SPAM  [label="Spam Folder", fillcolor="#fbd7c5"];
    }
    subgraph cluster_offline {
        label="Offline Learning"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        K     [label="Kafka\nverdicts + feedback", fillcolor="#ead7fb"];
        FP2   [label="Feature\nPipeline (Spark)", fillcolor="#ead7fb"];
        LBL   [label="Label Store\n(user reports)", fillcolor="#ead7fb"];
        TRN   [label="Training\n(Ray / Spark)", fillcolor="#ead7fb"];
        REG   [label="Model Registry\n(MLflow)", fillcolor="#ead7fb"];
    }

    SMTP -> PRE -> FE -> MS -> DEC;
    DEC -> INBOX [label="ALLOW"];
    DEC -> SPAM  [label="SPAM / QUARANTINE"];
    PRE -> REP   [label="lookup", style=dashed];
    FE  -> FS    [label="read", style=dashed];
    FE  -> FP    [label="near-dup", style=dashed];

    DEC -> K     [label="emit verdict", style=dashed, color="#7a3eb8"];
    INBOX -> LBL [label="user report", style=dashed, color="#7a3eb8"];
    SPAM  -> LBL [label="not spam", style=dashed, color="#7a3eb8"];
    K   -> FP2 -> TRN;
    LBL -> TRN;
    TRN -> REG -> MS [label="deploy", style=dashed, color="#7a3eb8"];
    FP2 -> REP   [label="update reputation", style=dashed, color="#7a3eb8"];
    FP2 -> FP    [label="update fingerprints", style=dashed, color="#7a3eb8"];
}
""",
                },
                {"type": "h3", "text": "Component Responsibilities"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Pre-Filter:</strong> O(µs) lookups in IP / domain / ASN blocklists; SPF / DKIM / DMARC verification; rate limits",
                        "<strong>Feature Extractor:</strong> tokenises body, computes SimHash, joins with reputation + recent-history features",
                        "<strong>Model Server:</strong> shadow-aware ensemble; GBDT for routine traffic, BERT only for borderline scores",
                        "<strong>Decision:</strong> applies thresholds; produces audit row; emits Kafka event",
                        "<strong>Feature Pipeline:</strong> hourly (warm) and nightly (cold) jobs that update reputation + label store",
                        "<strong>Training:</strong> nightly retrain using last-30-day labels; canary in shadow mode before promotion",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Layered Defence",
            "subtitle": "Why five layers beat one big model",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "A single neural network at 3.5 M/sec is operationally and economically "
                        "untenable. Stacking <strong>cheap → expensive</strong> filters lets each "
                        "layer reject ~10× of remaining traffic, so the heaviest model only sees "
                        "0.1% of inputs. Each layer has different blast radius, latency and "
                        "false-positive cost."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Volume halves by an order of magnitude per layer. Cost-per-evaluation rises in the opposite direction: O(1) Redis lookup at L0, O(N) BERT inference at L4.",
                    "dot": r"""
digraph L {
    rankdir=TB;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=9, color="#586278"];

    L0 [label="L0  IP / RBL Blocklist\n3.5 M/sec  ·  ~5 µs/req\nrejects ~90%", fillcolor="#cbeedf"];
    L1 [label="L1  SPF / DKIM / DMARC + Reputation\n350 K/sec  ·  ~200 µs/req\nrejects ~80%", fillcolor="#fff2c9"];
    L2 [label="L2  Hand-crafted Rules\n70 K/sec  ·  ~500 µs/req\nrejects ~60%", fillcolor="#fff2c9"];
    L3 [label="L3  LightGBM Classifier\n30 K/sec  ·  ~1 ms/req\nresolves ~90% confidently", fillcolor="#ead7fb"];
    L4 [label="L4  Fine-tuned BERT (borderline)\n3 K/sec  ·  ~8 ms/req on T4\nfinal adjudication", fillcolor="#fbd7c5"];
    OUT [label="Verdict\nALLOW / SPAM / QUARANTINE / DROP", fillcolor="#dbe6fb"];

    L0 -> L1 [label="not in blocklist"];
    L1 -> L2 [label="auth pass + rep ok"];
    L2 -> L3 [label="no rule fires"];
    L3 -> L4 [label="0.4 ≤ score ≤ 0.7"];
    L3 -> OUT [label="confident"];
    L4 -> OUT;
}
""",
                },
                {"type": "h3", "text": "Why Each Layer Earns Its Keep"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>L0 IP / RBL:</strong> 90% of spam comes from a <em>tiny</em> set of compromised hosts. Catching them in a 5 µs Redis call frees the entire fleet.",
                        "<strong>L1 Auth + reputation:</strong> SPF/DKIM/DMARC + per-domain history shields against header spoofing; cheap, deterministic, explainable",
                        "<strong>L2 Rules:</strong> human-readable, fast to ship for an emerging campaign (hours vs. nightly retrain). Trade specificity for recall",
                        "<strong>L3 LightGBM:</strong> dense numerical + categorical features (reputation, time-of-day, link-count). Sub-ms latency, well-calibrated",
                        "<strong>L4 BERT:</strong> only borderline cases (~10% of L3 traffic). Reads body text; expensive but high precision on novel phishing",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Cost-per-decision discipline",
                    "body": (
                        "If a layer cannot reject ~10× of remaining traffic at less than 10× the "
                        "cost of the previous layer, fold it back into the previous layer. The "
                        "five-layer cascade only works when each step pulls its weight."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Sender Reputation",
            "subtitle": "Per-IP / per-domain / per-ASN scores",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Reputation is the single highest-signal feature. We track it at three "
                        "granularities so a campaign cannot trivially hop IPs to escape: "
                        "<strong>IP, domain, ASN</strong>. Hot lookups land in Redis; the warm tier "
                        "lives in RocksDB, fed by the offline feature pipeline."
                    ),
                },
                {"type": "h3", "text": "Reputation Schema"},
                {
                    "type": "code",
                    "text": (
                        "-- Warm tier (RocksDB key-value, key = entity_type:entity_id)\n"
                        "TABLE sender_reputation (\n"
                        "  entity_type    ENUM('IP','DOMAIN','ASN'),\n"
                        "  entity_id      VARCHAR(64),       -- IPv6 or FQDN or AS#####\n"
                        "  msg_total_30d  BIGINT,\n"
                        "  msg_spam_30d   BIGINT,\n"
                        "  spam_rate_30d  FLOAT,             -- spam_30d / total_30d\n"
                        "  user_reports   BIGINT,\n"
                        "  bounce_rate    FLOAT,\n"
                        "  engagement     FLOAT,             -- opens / clicks / replies\n"
                        "  age_days       INT,               -- how long we have seen this entity\n"
                        "  first_seen     TIMESTAMP,\n"
                        "  last_updated   TIMESTAMP,\n"
                        "  reputation     FLOAT,             -- bounded [-1.0 .. +1.0]\n"
                        "  PRIMARY KEY (entity_type, entity_id),\n"
                        "  INDEX idx_rep   (reputation),\n"
                        "  INDEX idx_seen  (last_updated)\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "Score Update Rule"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Bayesian smoothing:</strong> rep = (spam + α·m) / (total + α), m = global prior, α = smoothing strength",
                        "<strong>Decay:</strong> 30-day exponential half-life so old behaviour fades",
                        "<strong>Cold-start penalty:</strong> entities with age &lt; 24 h get a damped score (treat as ‘unknown’ ≈ slight negative)",
                        "<strong>Three tiers blended:</strong> 0.5×IP + 0.3×domain + 0.2×ASN, then clipped to [-1, +1]",
                        "<strong>Update cadence:</strong> hot increments on each verdict (Redis INCRBY); full recompute hourly in Spark",
                    ],
                },
                {"type": "h3", "text": "Hot Path Lookup"},
                {
                    "type": "code",
                    "text": (
                        "# Pre-filter looks up all three keys in a single Redis MGET\n"
                        "ip, dom, asn = parse_envelope(msg)\n"
                        "rep_ip, rep_dom, rep_asn = redis.mget(\n"
                        "    f'rep:IP:{ip}', f'rep:DOMAIN:{dom}', f'rep:ASN:{asn}'\n"
                        ")\n"
                        "reputation = (\n"
                        "    0.5 * float(rep_ip  or 0.0) +\n"
                        "    0.3 * float(rep_dom or 0.0) +\n"
                        "    0.2 * float(rep_asn or 0.0)\n"
                        ")\n"
                        "if reputation < -0.8:\n"
                        "    return DROP  # known bad sender, never reaches model\n"
                        "if reputation >  0.6:\n"
                        "    bypass_l4 = True  # high-reputation senders skip BERT"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "ASN matters",
                    "body": (
                        "Snowshoe spammers rotate IPs cheaply but ASNs are economically expensive "
                        "to change. A bad ASN reputation is one of the most stable adversarial "
                        "signals available."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Content Fingerprinting",
            "subtitle": "SimHash + LSH for near-duplicate spam waves",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Spam campaigns blast the same payload (with cosmetic mutations) to "
                        "millions of recipients in a short window. Detecting <strong>near-duplicate"
                        "</strong> bodies in O(1) is therefore one of the highest-leverage signals "
                        "in the pipeline. We use 64-bit <strong>SimHash</strong> over weighted "
                        "shingles, indexed by <strong>Locality-Sensitive Hashing</strong>."
                    ),
                },
                {"type": "h3", "text": "SimHash + LSH (Algorithm)"},
                {
                    "type": "code",
                    "text": (
                        "# 1) Shingle the normalised body into k-grams (k=4 words)\n"
                        "shingles = ngrams(normalize(body), n=4)\n"
                        "\n"
                        "# 2) SimHash: weighted sum of shingle-hash bits\n"
                        "v = [0]*64\n"
                        "for sh in shingles:\n"
                        "    h = murmur64(sh)                 # 64-bit hash\n"
                        "    w = idf(sh)                      # rare shingles weigh more\n"
                        "    for i in range(64):\n"
                        "        v[i] += w if (h >> i) & 1 else -w\n"
                        "fp = 0\n"
                        "for i in range(64):\n"
                        "    if v[i] > 0: fp |= (1 << i)\n"
                        "\n"
                        "# 3) LSH: split fingerprint into 4 × 16-bit bands.\n"
                        "#    Two messages within Hamming-3 differ in at most one band\n"
                        "#    (pigeonhole), so candidates are found in O(1).\n"
                        "bands = [(fp >> (16*i)) & 0xFFFF for i in range(4)]\n"
                        "for i, b in enumerate(bands):\n"
                        "    candidates |= redis.smembers(f'lsh:{i}:{b}')\n"
                        "\n"
                        "# 4) Verify Hamming distance on the candidate set\n"
                        "near_dups = [c for c in candidates if popcount(fp ^ c) <= 3]\n"
                        "\n"
                        "# 5) Index for future probes (TTL = 24h sliding window)\n"
                        "for i, b in enumerate(bands):\n"
                        "    redis.sadd(f'lsh:{i}:{b}', fp)\n"
                        "    redis.expire(f'lsh:{i}:{b}', 86400)"
                    ),
                },
                {"type": "h3", "text": "Why It Works"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Robust to small mutations:</strong> reordered words, swapped synonyms, padded whitespace",
                        "<strong>Cheap:</strong> O(shingles) hashing per message; index probe is O(1) Redis set lookup",
                        "<strong>Wave detection:</strong> if a fingerprint appears &gt; N times in 5 minutes across &gt; M senders → instant block",
                        "<strong>Bounded recall by design:</strong> LSH with b bands, r bits/band approximates Hamming threshold via 1 − (1 − s^r)^b",
                        "<strong>Privacy:</strong> we only ever store 64-bit fingerprints, never plaintext",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "MinHash is not the right tool here",
                    "body": (
                        "MinHash estimates Jaccard on sets — great for document retrieval. "
                        "SimHash measures cosine on weighted vectors and is more robust to small "
                        "edits, which is exactly the spammer’s tactic. Pick the hash that matches "
                        "the adversary’s edit budget."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Feature Extraction",
            "subtitle": "What goes into the model",
            "blocks": [
                {"type": "h3", "text": "Feature Vector Layout"},
                {
                    "type": "code",
                    "text": (
                        "# Wire format consumed by L3 (LightGBM) and L4 (BERT)\n"
                        "FeatureVector {\n"
                        "  // ----- envelope (numeric / categorical) -----\n"
                        "  ip_reputation        : float32  // [-1.0 .. 1.0]\n"
                        "  domain_reputation    : float32\n"
                        "  asn_reputation       : float32\n"
                        "  domain_age_days      : int32\n"
                        "  spf_pass             : bool\n"
                        "  dkim_pass            : bool\n"
                        "  dmarc_pass           : bool\n"
                        "  tls_used             : bool\n"
                        "\n"
                        "  // ----- behavioural -----\n"
                        "  msgs_from_ip_5m      : int32    // velocity\n"
                        "  unique_recips_5m     : int32    // fan-out\n"
                        "  avg_recip_open_rate  : float32  // 7d\n"
                        "\n"
                        "  // ----- content -----\n"
                        "  body_len_bytes       : int32\n"
                        "  link_count           : int16\n"
                        "  shortener_link_count : int16\n"
                        "  attachment_count     : int8\n"
                        "  image_to_text_ratio  : float32  // OCR-derived\n"
                        "  language             : enum32\n"
                        "  simhash              : uint64\n"
                        "  near_dup_count_24h   : int32    // LSH probe result\n"
                        "\n"
                        "  // ----- TF-IDF (sparse, for L3 baseline) -----\n"
                        "  tfidf_topk           : list<(uint32 token_id, float32 weight)>  // top-128\n"
                        "\n"
                        "  // ----- text (for L4 only when borderline) -----\n"
                        "  body_tokens          : list<int32>   // BPE ids, max 512\n"
                        "}"
                    ),
                },
                {"type": "h3", "text": "Counter-Adversarial Features"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>OCR on images:</strong> spammers hide text inside JPEGs to dodge TF-IDF — Tesseract / on-device OCR adds it back",
                        "<strong>URL shortener resolution:</strong> follow bit.ly / t.co at extraction time; classify the destination, not the disguise",
                        "<strong>Server-side render:</strong> for HTML mail, render with headless Chromium and re-extract visible text",
                        "<strong>Punycode / homoglyph normalisation:</strong> аpple.com (Cyrillic а) becomes apple.com",
                        "<strong>Zero-width / RTL-override stripping:</strong> remove invisible Unicode that confuses tokenisers",
                    ],
                },
                {"type": "h3", "text": "Online Feature Store"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Velocity counters</strong> (msgs_from_ip_5m, unique_recips_5m) live in Redis Streams + sliding-window structures",
                        "<strong>Reputation</strong> hits the Redis layer described in §06",
                        "<strong>Recipient-side features</strong> (avg_recip_open_rate) are joined from Cassandra by user-id",
                        "<strong>Single round trip:</strong> Feature Extractor issues one MGET / pipelined call &lt; 5 ms p99",
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Model Stack",
            "subtitle": "Naive Bayes → LightGBM → BERT",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "We deliberately ship a portfolio of models with very different "
                        "complexity / latency / accuracy trade-offs. The portfolio also limits "
                        "blast radius: if BERT regresses we can route 100% to LightGBM in seconds."
                    ),
                },
                {"type": "h3", "text": "Model Comparison"},
                {
                    "type": "table",
                    "headers": ["Model", "Latency", "AUC (typical)", "Strength", "Weakness"],
                    "rows": [
                        ["TF-IDF + Naive Bayes", "~ 100 µs", "0.92",
                         "Trivial to train & explain; great baseline",
                         "Brittle to obfuscation; ignores envelope"],
                        ["LightGBM (GBDT)", "~ 1 ms", "0.97",
                         "Mixes dense & sparse features well; calibrated",
                         "Doesn’t read raw text; needs feature engineering"],
                        ["Fine-tuned BERT-small", "~ 8 ms (T4)", "0.985",
                         "Reads body; catches novel phishing wording",
                         "Costly; needs GPUs; harder to explain"],
                        ["DistilBERT distilled", "~ 3 ms", "0.98",
                         "BERT quality at GBDT-ish cost",
                         "Still needs GPUs; complex deploy"],
                    ],
                },
                {"type": "h3", "text": "Routing Logic"},
                {
                    "type": "code",
                    "text": (
                        "score_gbdt = lightgbm.predict(features)\n"
                        "if score_gbdt < 0.05:        return ALLOW\n"
                        "if score_gbdt > 0.95:        return SPAM\n"
                        "if reputation < -0.5:        return SPAM       # cheap precision boost\n"
                        "if 0.4 <= score_gbdt <= 0.7: # borderline → call deep model\n"
                        "    score_bert = bert.predict(features.body_tokens)\n"
                        "    final = 0.4 * score_gbdt + 0.6 * score_bert\n"
                        "    return SPAM if final > 0.6 else ALLOW\n"
                        "return SPAM if score_gbdt > 0.5 else ALLOW"
                    ),
                },
                {"type": "h3", "text": "Why a Per-Message Model and Not Just Per-Sender"},
                {
                    "type": "table",
                    "headers": ["Granularity", "Pros", "Cons"],
                    "rows": [
                        ["Per-sender", "Cheap; one decision per IP",
                         "Punishes shared infrastructure (Gmail, Outlook IPs); zero-day blind"],
                        ["Per-message", "Catches novel content even from clean senders",
                         "Higher compute; per-row latency budget"],
                        ["Hybrid (ours)", "Sender reputation gates first, content model second",
                         "More moving parts; needs careful threshold calibration"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Champion / Challenger",
                    "body": (
                        "Run two models simultaneously: <strong>champion</strong> serves traffic, "
                        "<strong>challenger</strong> shadow-scores. Promote the challenger only "
                        "after 7 days of better precision-at-fixed-recall on a held-out, daily-"
                        "refreshed slice — never on training-set metrics."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Decision & Audit Log",
            "subtitle": "Every verdict is explainable",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Every message that reaches L1 produces an audit row. The row is the "
                        "single source of truth for analytics, appeals, training labels and "
                        "regulatory disclosure. We persist it for 90 days hot (BigQuery / "
                        "Snowflake) and 7 years cold (S3 Glacier with hashed message-ids only)."
                    ),
                },
                {"type": "h3", "text": "Spam Decision Audit Schema"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE spam_decision (\n"
                        "  message_id        UUID PRIMARY KEY,\n"
                        "  tenant_id         BIGINT,\n"
                        "  ts                TIMESTAMP,\n"
                        "  envelope_from     VARCHAR(254),\n"
                        "  ip                INET,\n"
                        "  asn               INT,\n"
                        "  simhash           BIGINT,\n"
                        "  ip_reputation     FLOAT,\n"
                        "  domain_reputation FLOAT,\n"
                        "  rule_hits         TEXT[],         -- which L2 rules fired\n"
                        "  score_gbdt        FLOAT,\n"
                        "  score_bert        FLOAT,          -- nullable; only on borderline\n"
                        "  final_score       FLOAT,\n"
                        "  verdict           ENUM('ALLOW','SPAM','QUARANTINE','DROP'),\n"
                        "  reason_code       VARCHAR(32),    -- 'L0_RBL','L3_HIGH','L4_BORDER'…\n"
                        "  model_version     VARCHAR(32),\n"
                        "  feedback_label    ENUM('NONE','SPAM','HAM') DEFAULT 'NONE',\n"
                        "  feedback_ts       TIMESTAMP NULL,\n"
                        "  INDEX idx_tenant_ts   (tenant_id, ts),\n"
                        "  INDEX idx_verdict_ts  (verdict, ts),\n"
                        "  INDEX idx_ip_ts       (ip, ts)\n"
                        ") PARTITION BY RANGE (ts);   -- daily partitions"
                    ),
                },
                {"type": "h3", "text": "Reason Codes"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>L0_RBL:</strong> sender IP on real-time blocklist; rejected at SMTP HELO",
                        "<strong>L1_AUTH_FAIL:</strong> SPF / DKIM failed AND DMARC = reject",
                        "<strong>L2_RULE_&lt;id&gt;:</strong> a specific operator-defined rule fired",
                        "<strong>L3_HIGH / L3_LOW:</strong> GBDT confident enough alone",
                        "<strong>L4_BORDER:</strong> blended GBDT + BERT score crossed threshold",
                        "<strong>FINGERPRINT_WAVE:</strong> SimHash matched &gt; 1 K messages in last 5 min",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Reason codes are a product feature",
                    "body": (
                        "When a user opens an appeals ticket, the support agent reads the reason "
                        "code, not the raw score. Make the codes few, stable and human-readable."
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Feedback Loop",
            "subtitle": "Closing the learning circle",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The model is only as good as its labels. We harvest implicit and explicit "
                        "signals continuously and close the loop nightly."
                    ),
                },
                {"type": "h3", "text": "Label Sources"},
                {
                    "type": "table",
                    "headers": ["Signal", "Quality", "Volume", "Latency"],
                    "rows": [
                        ["User ‘Report spam’", "High (positive)", "Millions/day", "Seconds"],
                        ["User ‘Not spam’", "High (negative)", "100 K/day", "Seconds"],
                        ["Honeypot inboxes", "Very high", "Tens of K/day", "Seconds"],
                        ["Bounce / NDR", "Medium", "Billions", "Minutes"],
                        ["Engagement (open / reply)", "Weak negative", "Hundreds of B", "Minutes"],
                        ["Hand-curated ground truth", "Gold", "Thousands", "Days"],
                    ],
                },
                {"type": "h3", "text": "Pipeline"},
                {
                    "type": "numbered",
                    "items": [
                        "User clicks <em>Report spam</em> → client emits event to Kafka (<code>spam_feedback</code>) within seconds",
                        "Stream processor joins on <code>message_id</code> with the existing <code>spam_decision</code> row",
                        "Hot loop: increment per-IP / per-domain spam counters in Redis (effective in &lt; 60 s)",
                        "Warm loop: write label to a daily Parquet partition in S3",
                        "Nightly Spark job builds the training set, weights labels by source quality, holds out 7-day rolling slice",
                        "Train challenger (LightGBM + DistilBERT) on Ray cluster, push artefact to model registry",
                        "Model server canaries the challenger to 1% of traffic, ramps to 10% / 50% / 100% over 24 h gated on regressions",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Beware label leakage",
                    "body": (
                        "Users only mark messages they actually saw — i.e., that we already let "
                        "through. Train naïvely on these and the model collapses to ‘predict your "
                        "own past decisions’. Counter with: honeypot accounts, stratified sampling "
                        "across verdict buckets, and counter-factual reweighting by inverse "
                        "propensity (1 / P(seen)) to undo the selection bias."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Adversarial ML",
            "subtitle": "The arms race never ends",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Spammers have economic incentive to probe. Treat the system like a "
                        "security product, not a one-shot ML model."
                    ),
                },
                {"type": "h3", "text": "Common Evasions and Counter-Measures"},
                {
                    "type": "table",
                    "headers": ["Evasion", "How it works", "Counter-measure"],
                    "rows": [
                        ["Image-only spam", "Body is a single JPEG of text",
                         "Tesseract OCR; treat OCR text as body input"],
                        ["URL shortener chain", "bit.ly → t.co → goo.gl → bad.example",
                         "Resolve at extraction time, score the destination"],
                        ["Homoglyph domains", "аpple.com with Cyrillic ‘а’",
                         "Punycode normalise; flag mixed-script domains"],
                        ["Zero-width chars", "fr&zwj;ee m&zwnj;oney",
                         "Strip C0 / RTL / ZW characters before tokenising"],
                        ["Snowshoe (low-volume per IP)", "Spread across 10 K cheap IPs",
                         "ASN reputation; per-tenant fan-out features"],
                        ["Hashbusting", "Append random words to break SimHash",
                         "Weight shingles by IDF; ignore long random tails"],
                        ["Reply-chain hijack", "Inject reply into legit thread",
                         "Verify In-Reply-To DKIM continuity"],
                        ["Adversarial text perturbation", "Replace ‘viagra’ → ‘v1agra’",
                         "Character-level model; subword BPE; OCR-style normalisation"],
                        ["Compromised legit account", "Real Gmail account turns bad",
                         "Behavioural anomaly: sudden fan-out / unusual hours"],
                    ],
                },
                {"type": "h3", "text": "Defensive Posture"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Rate-limit feedback:</strong> attackers submit fake ‘not spam’ reports — cap weight per account & require account age",
                        "<strong>Don’t leak scores:</strong> never expose raw model probabilities to senders; round verdicts coarsely",
                        "<strong>Diversity of models:</strong> ensembles are harder to gradient-attack than a single deep net",
                        "<strong>Honeypots:</strong> seeded inboxes that should never receive mail; anything landing there is gold-label spam",
                        "<strong>Shadow traffic:</strong> tee 1% of inputs to a paranoid challenger model to detect drift early",
                    ],
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Scalability & Distribution",
            "subtitle": "Sharding, replication, multi-region",
            "blocks": [
                {"type": "h3", "text": "Horizontal Scaling"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Pre-Filter / Feature Extractor:</strong> stateless, scaled by QPS",
                        "<strong>Model Server (LightGBM):</strong> stateless, model loaded at startup; rolling restart on new model",
                        "<strong>Model Server (BERT GPU):</strong> autoscaled by GPU utilisation; right-sized to ~10% of LightGBM QPS",
                        "<strong>Reputation Redis:</strong> sharded by entity-id hash; 16 shards × 3 replicas",
                        "<strong>RocksDB warm tier:</strong> sharded same scheme; daily Spark recompute writes new SSTables",
                    ],
                },
                {"type": "h3", "text": "Multi-Region Topology"},
                {
                    "type": "bullets",
                    "items": [
                        "Inline scoring is <strong>region-local</strong>: never wait on a cross-region call",
                        "Reputation is replicated <strong>active-active</strong> via CRDT counters (PN-counters per IP)",
                        "Model registry is <strong>global, single-writer</strong>: training cluster pushes artefact, regions pull on rollout",
                        "Verdict log is <strong>region-local first</strong>, async-replicated to a global lake for training",
                        "Privacy: bodies never leave region; only 64-bit fingerprints + features cross",
                    ],
                },
                {"type": "h3", "text": "Capacity Math Recap"},
                {
                    "type": "bullets",
                    "items": [
                        "L0 hosts: 3.5 M/sec ÷ 50 K/sec/host ≈ <strong>70 pre-filter hosts</strong>",
                        "Feature extractor: 350 K/sec ÷ 5 K/sec/host ≈ <strong>70 hosts</strong>",
                        "LightGBM serving: 30 K/sec, ~ 1 ms/req ≈ <strong>30 cores + 5× HA = 150 cores</strong>",
                        "BERT serving: 3 K/sec, 8 ms on T4 ≈ <strong>~ 30 T4 GPUs</strong>",
                        "Reputation Redis: 200 K reads/sec → comfortable on 16-node cluster",
                    ],
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Failure Modes & Recovery",
            "subtitle": "What can go wrong",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["Reputation Redis down", "Cold-start everyone; precision drops",
                         "Latency / error spike", "Fail-open to neutral score; serve from RocksDB warm tier"],
                        ["BERT GPU outage", "Borderline cases mis-routed",
                         "GPU health check", "Fall back to LightGBM with widened threshold; alert"],
                        ["Model artefact corrupted", "All scores become 0.5",
                         "Score histogram drift alarm", "Auto-rollback to previous model in registry"],
                        ["Kafka outage (verdicts)", "Audit + training data lost",
                         "Broker dead alert", "Local disk buffer + replay; never block the inline path"],
                        ["LSH index lag", "Wave detection delayed",
                         "Wave-detect SLO breach", "Increase shingle weight; secondary in-process Bloom filter"],
                        ["Feedback flood (attack)", "Skewed labels poison training",
                         "Anomalous /spam clicks/sec", "Cap per-account weight; require account age + 2FA"],
                        ["Training pipeline silent failure", "Stale model for days",
                         "Model-age SLO &gt; 24 h", "Page on-call; freeze rules in place; promote last-good"],
                        ["Threshold mis-calibration", "FP rate &gt; 0.1%",
                         "Real-time FP probe", "Auto-revert thresholds; canary halts further rollout"],
                    ],
                },
                {"type": "h3", "text": "Disaster Recovery"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>RTO:</strong> &lt; 5 min to fail-open per region; &lt; 30 min to redeploy a good model",
                        "<strong>RPO:</strong> &lt; 1 min for verdict log; never block delivery on storage failure",
                        "<strong>Backups:</strong> model registry replicated 3× regions; warm reputation snapshot daily",
                        "<strong>Game days:</strong> quarterly chaos drill — kill BERT pool, kill Redis primary, replay yesterday’s spam wave",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Fail-open, not fail-closed",
                    "body": (
                        "If the spam pipeline crashes, it is far better to deliver a few extra "
                        "spammy messages than to drop legitimate mail. Default to ALLOW with a "
                        "low-confidence flag and rely on layer-0 (RBL) to keep the floor."
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
                        ["FP vs FN", "Asymmetric: FP &lt; 0.1% is sacred",
                         "A legit email in spam is far worse than a spam in inbox; tune thresholds accordingly"],
                        ["Latency vs accuracy", "Cascade with 50 ms p99 budget",
                         "Cheap layers get most decisions; deep model only for borderline (~0.1% of traffic)"],
                        ["Rules vs ML", "Hybrid",
                         "Rules ship in hours but rot fast; ML adapts but has cold-start; we keep both"],
                        ["Per-msg vs per-sender", "Hybrid",
                         "Reputation gates first (cheap), content model decides borderline"],
                        ["Deep model vs GBDT", "GBDT champion, BERT challenger on borderline",
                         "GBDT is faster, more explainable; BERT shines on novel phishing wording"],
                        ["Sync vs async scoring", "Sync inline",
                         "Email cannot be ‘un-delivered’ cheaply; spam folder requires the verdict at write time"],
                        ["Global vs per-tenant model", "Global base + per-tenant rule overlays",
                         "Captures shared patterns, lets enterprises encode their own policy"],
                        ["Storage of bodies", "Never persisted across borders",
                         "Strong privacy posture; loses some debug power"],
                        ["Threshold tuning", "Per-tenant ROC-curve picker, monthly",
                         "Some tenants accept higher FN for lower FP (consumer) and vice-versa (B2B alerts)"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Asymmetric error costs",
                    "body": (
                        "Internal SLO: 1 false-positive = 100 false-negatives in cost. The pipeline "
                        "is engineered around that ratio — every threshold, every routing rule, "
                        "every model promotion gate is calibrated for it."
                    ),
                },
            ],
        },
        # ---- 16 ------------------------------------------------------
        {
            "num": "16",
            "title": "Interview Playbook",
            "subtitle": "How to present this",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Spam detection is one of the few interview questions where "
                        "<strong>ML</strong> and <strong>systems</strong> meet at full force. "
                        "Most candidates over-index on the model and forget the 3.5 M/sec "
                        "constraint. Lead with the cascade."
                    ),
                },
                {"type": "h3", "text": "45-Minute Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (2 min):</strong> clarify volume, latency, FP/FN asymmetry, adversarial setting",
                        "<strong>Capacity (3 min):</strong> 300 B/day → 3.5 M/sec; p99 50 ms; explain why a single big model is impossible",
                        "<strong>Layered defence (8 min):</strong> draw the 5-layer funnel; argue 10× rejection per layer",
                        "<strong>Reputation (5 min):</strong> per-IP / per-domain / per-ASN; Bayesian smoothing; ASN as anti-snowshoe lever",
                        "<strong>Fingerprinting (5 min):</strong> SimHash + LSH; explain why MinHash is the wrong tool",
                        "<strong>Model stack (6 min):</strong> NB → LightGBM → BERT; routing rule with explicit thresholds",
                        "<strong>Feedback loop (5 min):</strong> Kafka → Spark → registry; mention selection bias and propensity weighting",
                        "<strong>Adversarial (5 min):</strong> name 3 concrete evasions and counter-measures",
                        "<strong>Failures & trade-offs (4 min):</strong> fail-open; FP &lt; FN cost; champion / challenger",
                        "<strong>Wrap (2 min):</strong> what you would build first, what you would defer",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "“3.5 M/sec at 50 ms p99 — that’s why a cascade exists, not because we love complexity”",
                        "“Each layer rejects an order of magnitude; BERT only sees 0.1% of inputs”",
                        "“Reputation at three granularities — IP, domain, ASN — to defeat snowshoe spam”",
                        "“SimHash + LSH catches near-duplicate waves in O(1)”",
                        "“FP costs 100× FN; the entire pipeline is calibrated to that ratio”",
                        "“Champion / challenger with shadow traffic, never trust offline metrics alone”",
                        "“Fail-open — never delay legitimate email because the ML stack hiccupped”",
                        "“Selection bias is the silent killer of every spam model”",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why not one big neural net?</strong> A: 3.5 M/sec × 8 ms BERT = 28 K GPU-seconds/sec ≈ 28 K T4s. Cascade trims that by 1000×.",
                        "<strong>Q: How do you bootstrap a brand-new sender?</strong> A: ASN reputation + domain-age penalty + content model. Cold senders get a damped neutral score, not a free pass.",
                        "<strong>Q: How do you avoid label leakage?</strong> A: Honeypots + stratified sampling across verdict buckets + inverse-propensity weighting in the loss.",
                        "<strong>Q: What if a spammer flips a model with adversarial perturbations?</strong> A: Ensemble of NB + GBDT + BERT; subword tokenisation; never expose raw scores.",
                        "<strong>Q: How fast can you react to a new wave?</strong> A: SimHash detects within minutes; rules ship within hours; full retrain nightly.",
                        "<strong>Q: How do you handle ‘this is spam’ vs ‘this is not spam’ class imbalance?</strong> A: Class-weighted loss + focal loss for BERT; precision-at-fixed-recall as the headline metric.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "3.5 M/sec &nbsp;·&nbsp; p99 &lt; 50 ms &nbsp;·&nbsp; "
                        "5 layers, 10× reject each &nbsp;·&nbsp; "
                        "FP &lt; 0.1% &nbsp;·&nbsp; FN &lt; 1% &nbsp;·&nbsp; "
                        "FP cost = 100 × FN cost &nbsp;·&nbsp; "
                        "BERT sees 0.1% of traffic &nbsp;·&nbsp; "
                        "Nightly retrain, 1% canary."
                    ),
                },
            ],
        },
    ],
}
