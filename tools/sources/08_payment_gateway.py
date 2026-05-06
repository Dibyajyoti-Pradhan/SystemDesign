"""Source for `08 - Payment Gateway.pdf` (regenerated with errata applied)."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design a Payment Gateway",
    "subtitle": "Stripe/PayPal-style transaction flow, idempotency, PCI compliance, and fraud detection",
    "read_time": "~ 45 minute read",
    "short_title": "Design a Payment Gateway",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Overview",
            "subtitle": "Stripe/PayPal at scale",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Design a payment gateway in the spirit of <strong>Stripe</strong>, "
                        "<strong>Adyen</strong>, or <strong>PayPal</strong>. The system must "
                        "accept charges from merchants, tokenize cards, run fraud and risk "
                        "checks, route to a card network, persist a double-entry ledger, and "
                        "emit reliable webhooks — all while never losing or duplicating a "
                        "single cent and surviving the network outages of third parties we do "
                        "not control."
                    ),
                },
                {"type": "h3", "text": "Scale & Requirements"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Volume:</strong> ~250M transactions/day; ~2.9K TPS daily average; ~10K TPS sustained at peak hour",
                        "<strong>Burst:</strong> Black Friday / Cyber Monday peaks to ~100K TPS globally for short flash windows",
                        "<strong>Uptime:</strong> 99.999% (5 nines); money cannot be lost or duplicated under any failure mode",
                        "<strong>Latency:</strong> gateway processing p99 &lt; 500 ms; end-to-end (incl. card network) p99 ≤ 8–10 s",
                        "<strong>Compliance:</strong> PCI DSS Level 1; never store raw PAN; tamper-evident audit trail",
                        "<strong>Fraud:</strong> real-time ML scoring &lt; 50 ms; 3DS authentication; velocity / device checks",
                        "<strong>Settlement:</strong> daily batch reconciliation against card-network files; double-entry accounting",
                    ],
                },
                {"type": "h3", "text": "Core Challenges"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Idempotency:</strong> networks time out and merchants retry — must dedup without duplicating charges",
                        "<strong>Double-spend:</strong> user clicks <em>Pay</em> twice; prevent the second hitting the bank",
                        "<strong>Distributed transactions:</strong> atomically update merchant balance, ledger, and fraud log across regions without 2PC",
                        "<strong>External dependency:</strong> issuing banks take 1.5–8 s; need async fallback and timeout handling",
                        "<strong>Fraud arms race:</strong> ML models retrain daily; balance false positives (lost revenue) vs. false negatives (chargebacks)",
                        "<strong>Compliance:</strong> PCI DSS, PSD2, SOX, regional regs; a single breach is a $5–25M event",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "The Headline Tension",
                    "body": (
                        "Payments has two competing obsessions: <strong>correctness</strong> "
                        "(no double-charge, no lost money, audit on demand) and "
                        "<strong>availability</strong> (5 nines despite a card network you do "
                        "not own). Almost every architectural choice picks correctness for "
                        "the money path and availability for everything else."
                    ),
                },
            ],
        },
        # ---- 02 ------------------------------------------------------
        {
            "num": "02",
            "title": "Clarifying Questions",
            "subtitle": "Scope refinement",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Spend the first three minutes pinning scope. Payments has more "
                        "branching than almost any other interview question — clarify what "
                        "is in and out before drawing a single box."
                    ),
                },
                {
                    "type": "table",
                    "headers": ["Question", "Options", "Assumption"],
                    "rows": [
                        ["Payment types?", "Cards, ACH, wallets, crypto", "Credit/debit cards (extend later)"],
                        ["Multi-currency?", "Single (USD) or global", "Multi-currency (100+); FX at capture"],
                        ["Regions?", "US-only or global", "Global; regional regs differ (PSD2, etc.)"],
                        ["Merchants?", "Small / large / platforms", "Mix; platforms (e.g. Shopify) need sub-accounts"],
                        ["PCI Level?", "1, 2, or 3", "Level 1 (strictest; &gt; 6M txn/yr)"],
                        ["Retry logic?", "Auto-retry? Cached fallback?", "3 retries w/ backoff; soft decline ≠ retry"],
                        ["Refunds?", "Full / partial? Chargebacks?", "Full + partial; full chargeback flow"],
                        ["Latency budget?", "Sync vs async charge?", "Sync auth; async capture & webhook"],
                        ["Tokenization?", "In-house vault or PSP?", "In-house HSM-backed vault (PCI scope)"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "What the Interviewer Is Listening For",
                    "body": (
                        "The strongest signal in the first five minutes is whether you "
                        "<em>separate</em> the things you can control (your code, your DBs, "
                        "your fraud model) from the things you cannot (card networks, "
                        "issuing banks). That separation drives every SLO, retry, and "
                        "fallback decision later in the design."
                    ),
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        # NEW EXPANDED CAPACITY ESTIMATION (replaces original §03)
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "Math for scale",
            "blocks": [
                {"type": "h3", "text": "Traffic Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        "Daily transactions: <strong>~250M baseline</strong> → ~10K TPS sustained at peak hour (Stripe-scale), ~2.9K TPS daily average",
                        "Black Friday / Cyber Monday peak: bursts to <strong>~100K TPS</strong> globally for short windows; design headroom to 2× peak (~200K TPS) so we do not shed load during the 30-second flash window when every checkout in the world fires at once",
                        "Read:Write profile: roughly <strong>4:1</strong> — every charge generates lookups (idempotency check, fraud features, merchant config, ledger reads for refunds/chargebacks) on top of the write",
                        "Webhook fan-out: 1 charge → ~3 outbound events (authorized, captured, settled) → <strong>~30K webhook deliveries/sec</strong> at peak; size Kafka and the retry tier for that, not for the raw charge rate",
                    ],
                },
                {"type": "h3", "text": "Storage Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        "Per payment record: ~2 KB hot (UUIDs, amounts, status, auth_code, fraud_score, timestamps) + ~3 KB extended (addresses, device fingerprint, 3DS metadata) → budget <strong>~5 KB/record</strong> including indexes",
                        "Daily payments storage: 250M × 2 KB = <strong>~500 GB/day hot</strong>; ~1.25 TB/day if extended fields and per-row indexes are co-located",
                        "Ledger entries: 3–4 per charge → ~1B rows/day × ~300 B = <strong>~300 GB/day</strong>",
                        "Retention: <strong>7 years minimum</strong> (PCI DSS, SOX, most national tax regimes; some EU regimes require 10)",
                        "Payments hot (1 year online): <strong>~180 TB</strong>",
                        "Payments warm/archive (years 2–7): ~1.1 PB in object storage / Glacier",
                        "Ledger hot (1 year): <strong>~110 TB</strong>; archive (years 2–7): ~660 TB",
                        "Idempotency cache (Redis): 250M keys/day × 24 h TTL × ~10 KB cached response = <strong>~2.5 TB</strong>; cluster sized at 4 TB to leave headroom",
                    ],
                },
                {"type": "h3", "text": "Bandwidth Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        "Inbound API: 10K TPS × ~2 KB request body ≈ <strong>20 MB/s sustained</strong>, 200 MB/s at Black Friday peak",
                        "Card-network egress: 10K TPS × ~1 KB ISO 8583 frame ≈ <strong>10 MB/s</strong>; replicated across regional acquirers",
                        "Webhook egress: 30K events/sec × ~1 KB ≈ <strong>30 MB/s sustained</strong>, ~300 MB/s peak",
                        "Kafka inter-broker: ~3× replication factor on a ~50 MB/s topic mix → <strong>~150 MB/s</strong> on the cluster backbone",
                    ],
                },
                {"type": "h3", "text": "Latency Targets (separated budgets)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Gateway processing</strong> (everything we own: API gateway → fraud → risk → ledger write, <em>excluding</em> card-network round-trip): p99 &lt; 500 ms, p50 &lt; 150 ms",
                        "<strong>Card-network + issuing-bank round-trip</strong> (out of our control): typically 1.5–3 s p50, 5–8 s p99 over ISO 8583 / network APIs",
                        "<strong>End-to-end authorization</strong> (gateway + network + bank): p99 ≤ 8–10 s, p50 ≈ 2 s. SLOs are defined separately so a slow issuer cannot blow our processing SLO",
                        "<strong>Fraud scoring:</strong> p99 &lt; 50 ms (in-process model server)",
                        "<strong>Primary DB write</strong> (ledger insert + idempotency upsert): p99 &lt; 20 ms",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "Sustained TPS: <strong>~10K</strong> &nbsp;·&nbsp; "
                        "Peak TPS (Black Friday): <strong>~100K</strong> &nbsp;·&nbsp; "
                        "Hot payments storage (1 yr): <strong>~180 TB</strong> &nbsp;·&nbsp; "
                        "Hot ledger storage (1 yr): <strong>~110 TB</strong> &nbsp;·&nbsp; "
                        "Idempotency cache: <strong>~2.5 TB</strong> Redis (24 h TTL) &nbsp;·&nbsp; "
                        "Retention: <strong>7 years</strong> (PCI / SOX)"
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level Architecture",
            "subtitle": "System components and data flow",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Merchants submit charges via REST to the <strong>API Gateway</strong> "
                        "(TLS, idempotency, rate-limiting). The <strong>Payment Processor</strong> "
                        "orchestrates fraud detection, risk checks, tokenization, and card-network "
                        "authorization. Data is persisted to <strong>PostgreSQL</strong> (payments + "
                        "double-entry ledger), <strong>Redis</strong> (idempotency cache, 24h TTL), "
                        "and <strong>Kafka</strong> (async events feeding webhooks, analytics, "
                        "settlement). Separate <strong>Settlement</strong> and <strong>Refund</strong> "
                        "services handle batch reconciliation and reversals."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "High-level architecture: merchant → API gateway → payment processor → {auth, fraud, risk, vault, charge, ledger} → card network → issuing bank. Ledger writes hit PostgreSQL synchronously; downstream events flow through Kafka to webhook delivery.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Merchant"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Merchant [label="Merchant\n(server / SDK)", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        APIGW [label="API Gateway\n(TLS, HMAC,\nrate limit, idem)", fillcolor="#cbeedf"];
    }
    subgraph cluster_svc {
        label="Payment Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        Auth   [label="Auth /\nMerchant Cfg",  fillcolor="#fff2c9"];
        Fraud  [label="Fraud Service\n(LightGBM)",  fillcolor="#fff2c9"];
        Risk   [label="Risk Engine\n(AVS, CVV, 3DS)", fillcolor="#fff2c9"];
        Vault  [label="Tokenizer / Vault\n(HSM)",     fillcolor="#fff2c9"];
        Charge [label="Charge\nOrchestrator",         fillcolor="#fff2c9"];
        Ledger [label="Ledger Service\n(double-entry)", fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        PG    [label="PostgreSQL\n(payments + ledger)", fillcolor="#ead7fb"];
        Redis [label="Redis\n(idempotency, 24h)",       fillcolor="#ead7fb"];
        Kafka [label="Kafka\n(events)",                  fillcolor="#fbd7c5"];
    }
    subgraph cluster_ext {
        label="External"; style="rounded,dashed"; color="#a32e2e"; fontcolor="#a32e2e";
        Net  [label="Card Network\n(Visa/MC/Amex)", fillcolor="#fbd5d5"];
        Bank [label="Issuing Bank",                  fillcolor="#fbd5d5"];
    }
    subgraph cluster_out {
        label="Delivery"; style="rounded,dashed"; color="#1f6e8c"; fontcolor="#1f6e8c";
        Web [label="Webhook\nDelivery",  fillcolor="#cfe6f1"];
    }

    Merchant -> APIGW [label="POST /charges"];
    APIGW -> Auth     [label="verify"];
    APIGW -> Charge   [label="orchestrate"];
    Charge -> Fraud   [label="score < 50ms"];
    Charge -> Risk    [label="AVS/CVV/3DS"];
    Charge -> Vault   [label="tokenize PAN"];
    Charge -> Net     [label="ISO 8583 auth"];
    Net -> Bank       [label="approve / decline"];
    Charge -> Ledger  [label="debit/credit"];
    Ledger -> PG      [label="WAL fsync"];
    APIGW -> Redis    [label="SETNX idem"];
    Charge -> Kafka   [label="payment.authorized\n.captured / .settled", style=dashed];
    Kafka -> Web      [label="fan-out", style=dashed];
    Web -> Merchant   [label="callback", style=dashed];
}
""",
                },
                {"type": "h3", "text": "Tier 1: API Gateway"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Clients:</strong> REST API, mobile SDKs, server-to-server webhooks",
                        "<strong>Rate limiting:</strong> token bucket per merchant key (per-second + per-day)",
                        "<strong>Auth:</strong> TLS 1.3 + HMAC-SHA256 signature verification on every request",
                        "<strong>Routing:</strong> Route53 latency-based; multi-region active-active",
                        "<strong>Idempotency:</strong> first stop for the <code>Idempotency-Key</code> header (see §05)",
                    ],
                },
                {"type": "h3", "text": "Tier 2: Payment Services"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Charge Orchestrator:</strong> drives the saga; calls fraud, risk, vault, network in order",
                        "<strong>Fraud:</strong> LightGBM model server; real-time scoring p99 &lt; 50 ms; score 0–100",
                        "<strong>Risk:</strong> AVS, CVV, 3DS, velocity checks; deterministic rule engine",
                        "<strong>Tokenizer / Vault:</strong> HSM-backed; raw PAN never leaves this tier",
                        "<strong>Ledger:</strong> double-entry, append-only; 3–4 entries per charge",
                        "<strong>Reconciliation:</strong> daily batch matching against card-network files; discrepancy alerts",
                    ],
                },
                {"type": "h3", "text": "Tier 3: Data Layer"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>PostgreSQL:</strong> ACID; synchronous WAL; multi-region primary/replica with controlled failover",
                        "<strong>Redis:</strong> idempotency cache, 24 h TTL; cluster mode + AOF for durability",
                        "<strong>Kafka:</strong> async events (<code>payment.authorized</code>, <code>.captured</code>, <code>.refunded</code>, <code>.settled</code>); consumers: webhooks, analytics, settlement",
                        "<strong>Object store:</strong> S3 / Glacier for warm + cold ledger and audit archives (years 2–7)",
                    ],
                },
                {"type": "h3", "text": "Tier 4: External & Compliance"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Card Networks:</strong> Visa, Mastercard, Amex; ISO 8583 + REST APIs",
                        "<strong>Acquirers:</strong> banks processing on the merchant's behalf",
                        "<strong>Issuing Banks:</strong> consumer banks; approve/decline based on funds + fraud rules",
                        "<strong>PCI DSS Vault:</strong> HSM tokenizes raw cards at the edge; PAN never enters app code or primary DB",
                        "<strong>Audit logs:</strong> immutable append-only; every transaction, every action; PCI requirement",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Core Design Decisions",
            "subtitle": "Idempotency, at-least-once, double-spend",
            "blocks": [
                {"type": "h3", "text": "Decision 1: Idempotency Keys"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Problem:</strong> merchant clicks <em>Pay</em>; network times out; merchant retries — duplicate charge?",
                        "<strong>Solution:</strong> client supplies <code>Idempotency-Key</code> (UUID); server stores <code>key → response</code> in Redis for 24 h",
                        "<strong>Mechanism:</strong> first request processes and stores; retry returns the cached response immediately",
                        "<strong>Guarantee:</strong> exactly-once semantics at the API layer; no double charges",
                        "<strong>Durability:</strong> Redis row mirrored to a durable <code>idempotency_keys</code> table so cache loss does not collapse the guarantee",
                    ],
                },
                # NEW SECTION: Idempotency Key Handling reference implementation
                {"type": "h3", "text": "Idempotency Key Handling — Reference Implementation"},
                {
                    "type": "para",
                    "text": (
                        "Every <code>POST /charges</code> requires the merchant to supply an "
                        "<code>Idempotency-Key</code> header (a client-generated UUID). The "
                        "gateway treats <code>(merchant_id, idempotency_key)</code> as the "
                        "deduplication tuple. Replays are answered from cache; replays with a "
                        "different body for the same key are rejected with <code>409</code>."
                    ),
                },
                {
                    "type": "code",
                    "text": (
                        "import hashlib, json, redis\n\n"
                        "r = redis.Redis()\n"
                        "TTL_SECONDS = 24 * 60 * 60  # 24h, matches Redis key retention\n\n"
                        "def handle_charge(merchant_id, idempotency_key, request_body):\n"
                        "    cache_key = f\"idem:{merchant_id}:{idempotency_key}\"\n"
                        "    body_hash = hashlib.sha256(\n"
                        "        json.dumps(request_body, sort_keys=True).encode()\n"
                        "    ).hexdigest()\n\n"
                        "    # SETNX = atomic 'claim this key if nobody else has'.\n"
                        "    # Value initially holds the request fingerprint + a PENDING marker.\n"
                        "    claimed = r.set(\n"
                        "        cache_key,\n"
                        "        json.dumps({\"status\": \"PENDING\", \"body_hash\": body_hash}),\n"
                        "        nx=True, ex=TTL_SECONDS,\n"
                        "    )\n\n"
                        "    if not claimed:\n"
                        "        existing = json.loads(r.get(cache_key))\n"
                        "        if existing[\"body_hash\"] != body_hash:\n"
                        "            # Same key, different payload -> client bug or replay attack.\n"
                        "            return 409, {\"error\": \"idempotency_key_reuse_with_different_payload\"}\n"
                        "        if existing[\"status\"] == \"PENDING\":\n"
                        "            # Original request still in-flight -> tell client to retry.\n"
                        "            return 409, {\"error\": \"request_in_progress\"}\n"
                        "        # Completed: replay the cached response verbatim.\n"
                        "        return existing[\"status_code\"], existing[\"response\"]\n\n"
                        "    # First time we have seen this key -- actually run the charge.\n"
                        "    try:\n"
                        "        status_code, response = process_payment(merchant_id, request_body)\n"
                        "    except Exception:\n"
                        "        # Release the slot so the merchant's retry can proceed.\n"
                        "        r.delete(cache_key)\n"
                        "        raise\n\n"
                        "    r.set(\n"
                        "        cache_key,\n"
                        "        json.dumps({\n"
                        "            \"status\": \"DONE\",\n"
                        "            \"body_hash\": body_hash,\n"
                        "            \"status_code\": status_code,\n"
                        "            \"response\": response,\n"
                        "        }),\n"
                        "        ex=TTL_SECONDS,\n"
                        "    )\n"
                        "    return status_code, response"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why This Shape",
                    "body": (
                        "<code>SET ... NX EX</code> is the atomic claim primitive (single "
                        "round-trip; survives concurrent retries from the same merchant). The "
                        "<strong>PENDING</strong> marker lets us distinguish &lsquo;in-flight&rsquo; "
                        "from &lsquo;already finished&rsquo; so a fast retry returns <code>409</code> "
                        "instead of double-charging. The body fingerprint protects against keys "
                        "being reused by a buggy client for a different amount/currency/customer. "
                        "The Redis row is mirrored to the durable <code>idempotency_keys</code> "
                        "table (see §06) so cache loss does not collapse the guarantee — on Redis "
                        "miss, the API falls back to the DB row."
                    ),
                },
                {"type": "h3", "text": "Decision 2: At-Least-Once Webhooks (Kafka)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Problem:</strong> payment completes; webhook to merchant fails; merchant never learns",
                        "<strong>Solution:</strong> publish event to Kafka; retry queue with exponential backoff (1 s, 10 s, 100 s, 1000 s); max 5 retries then DLQ",
                        "<strong>Guarantee:</strong> at-least-once delivery; merchant <em>may</em> see duplicates and must dedup by <code>event_id</code>",
                        "<strong>Why not exactly-once?</strong> exactly-once is unimplementable across an arbitrary merchant network — pushing dedup to the merchant is industry standard",
                    ],
                },
                {"type": "h3", "text": "Decision 3: Double-Spend Prevention"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Race condition:</strong> two retries arrive simultaneously and both pass the Redis check before SETNX completes (rare but possible across clusters)",
                        "<strong>Defence in depth:</strong> Redis SETNX is the fast path; PostgreSQL <code>UNIQUE (merchant_id, idempotency_key)</code> is the durable backstop",
                        "<strong>Advisory locks:</strong> <code>pg_advisory_xact_lock(hashtext(idempotency_key))</code> serializes any sliver that escapes the cache",
                        "<strong>Heuristic backstop:</strong> flag charges &lt; 1 s apart with overlapping amounts as suspicious for manual review",
                    ],
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Data Models",
            "subtitle": "Schema and storage",
            "blocks": [
                {"type": "h3", "text": "Payments Table (PostgreSQL)"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE payments (\n"
                        "  id              UUID PRIMARY KEY,\n"
                        "  merchant_id     UUID NOT NULL,\n"
                        "  idempotency_key UUID,\n"
                        "  amount_cents    BIGINT NOT NULL,\n"
                        "  currency        CHAR(3),                -- USD, EUR, GBP, ...\n"
                        "  status          payment_status,         -- pending|authorized|captured|declined|refunded\n"
                        "  card_token      VARCHAR(255),           -- tokenized; never raw PAN\n"
                        "  fraud_score     DECIMAL(5,2),           -- 0-100; >80 = manual review\n"
                        "  auth_code       VARCHAR(10),            -- from card network\n"
                        "  created_at      TIMESTAMPTZ DEFAULT NOW(),\n"
                        "  captured_at     TIMESTAMPTZ,\n"
                        "  settled_at      TIMESTAMPTZ,\n"
                        "  UNIQUE (merchant_id, idempotency_key),\n"
                        "  INDEX (merchant_id, created_at),\n"
                        "  INDEX (status, created_at)\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "Ledger Entries (Double-Entry Accounting)"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE ledger_entries (\n"
                        "  id             UUID PRIMARY KEY,\n"
                        "  transaction_id UUID NOT NULL,           -- groups 3-4 entries\n"
                        "  account_id     UUID NOT NULL,\n"
                        "  debit_cents    BIGINT NOT NULL DEFAULT 0,\n"
                        "  credit_cents   BIGINT NOT NULL DEFAULT 0,\n"
                        "  currency       CHAR(3),\n"
                        "  description    VARCHAR(255),            -- 'Charge', 'Fee', 'Reversal', ...\n"
                        "  created_at     TIMESTAMPTZ DEFAULT NOW(),\n"
                        "  settled_at     TIMESTAMPTZ,\n"
                        "  INDEX (account_id, created_at),\n"
                        "  INDEX (transaction_id)\n"
                        ");\n\n"
                        "-- Invariant (verified nightly): SUM(debit_cents) = SUM(credit_cents)\n"
                        "-- across the whole table, and per-transaction inside one transaction_id.\n"
                        "-- The table is APPEND-ONLY: corrections are new rows, not UPDATEs."
                    ),
                },
                {"type": "h3", "text": "Idempotency Keys (durable mirror)"},
                {
                    "type": "code",
                    "text": (
                        "-- Redis (fast path):\n"
                        "Key:   'idem:{merchant_id}:{idempotency_key}'\n"
                        "Value: {status, body_hash, status_code, response}\n"
                        "TTL:   86,400 seconds (24h)\n\n"
                        "-- PostgreSQL (durable backstop):\n"
                        "CREATE TABLE idempotency_keys (\n"
                        "  key           UUID,\n"
                        "  merchant_id   UUID,\n"
                        "  body_hash     CHAR(64),\n"
                        "  response_body JSONB,\n"
                        "  status_code   SMALLINT,\n"
                        "  created_at    TIMESTAMPTZ DEFAULT NOW(),\n"
                        "  expires_at    TIMESTAMPTZ,\n"
                        "  PRIMARY KEY (merchant_id, key)\n"
                        ");"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Why Append-Only Ledger",
                    "body": (
                        "Auditable by construction (<code>SUM(debits) = SUM(credits)</code> is "
                        "a one-line invariant). No destructive updates means no corruption "
                        "from a buggy migration. Easy to replay forward from any timestamp. "
                        "Trade-off: storage growth (every correction is a new row) and that "
                        "&lsquo;current balance&rsquo; requires a materialized view."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Payment Transaction Flow",
            "subtitle": "Complete lifecycle as a saga",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "A charge is a <strong>saga</strong>: a sequence of local transactions, "
                        "each with a compensating action. We never use 2PC across services — it "
                        "blocks on the coordinator, does not survive cross-region partitions, and "
                        "is incompatible with five-nines targets that depend on third-party banks."
                    ),
                },
                {"type": "h3", "text": "Step-by-Step (happy path)"},
                {
                    "type": "numbered",
                    "items": [
                        "Merchant <code>POST /charges</code> with <code>Idempotency-Key</code> header",
                        "API Gateway: TLS, HMAC verify, rate-limit, dedup via Redis SETNX (returns cached response on retry)",
                        "Charge Orchestrator: insert <code>payments</code> row in <code>pending</code> state (single SQL txn)",
                        "Fraud Service: ML scoring (LightGBM, p99 &lt; 50 ms); if score &gt; threshold, decline or trigger 3DS",
                        "Risk Engine: AVS, CVV, 3DS, velocity checks (deterministic rules)",
                        "Tokenizer/Vault: turn raw PAN (if present) into a vault token; PAN never reaches app code or DB",
                        "Card Network: ISO 8583 / REST authorization; await issuing-bank approval (1.5–3 s p50)",
                        "Ledger Service: write 3–4 double-entry rows in one PG transaction with synchronous WAL",
                        "Status: flip <code>payments.status</code> from <code>pending</code> → <code>authorized</code>",
                        "Publish <code>payment.authorized</code> to Kafka (async fan-out to webhook, analytics, settlement)",
                        "Cache the final response under the idempotency key (PENDING → DONE)",
                        "Return <code>200 OK</code> to the merchant",
                    ],
                },
                {
                    "type": "diagram",
                    "caption": "Charge as a saga: each forward step has an explicit compensating action. Authorize and Capture are the synchronous money-path; Settle and Reconcile are the daily T+1 batch tail.",
                    "dot": r"""
digraph Saga {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Start [label="Charge\nrequested", shape=ellipse, fillcolor="#dbe6fb"];

    subgraph cluster_fwd {
        label="Forward path (saga)"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        Authorize [label="1. Authorize\n(reserve funds)", fillcolor="#cbeedf"];
        Capture   [label="2. Capture\n(claim funds)",     fillcolor="#cbeedf"];
        Settle    [label="3. Settle\n(T+1 batch)",        fillcolor="#cbeedf"];
        Reconcile [label="4. Reconcile\n(match files)",   fillcolor="#cbeedf"];
    }

    subgraph cluster_comp {
        label="Compensations"; style="rounded,dashed"; color="#a32e2e"; fontcolor="#a32e2e";
        Void      [label="Void\n(cancel auth)",     fillcolor="#fbd5d5"];
        Refund    [label="Refund\n(reverse capture)", fillcolor="#fbd5d5"];
        Adjust    [label="Adjustment entry\n(ledger correction)", fillcolor="#fbd5d5"];
        Dispute   [label="Chargeback /\nDispute",    fillcolor="#fbd5d5"];
    }

    Done [label="Settled +\nReconciled", shape=ellipse, fillcolor="#cbeedf"];

    Start -> Authorize;
    Authorize -> Capture   [label="approved"];
    Capture   -> Settle    [label="batch nightly"];
    Settle    -> Reconcile [label="match"];
    Reconcile -> Done;

    Authorize -> Void    [label="fraud / merchant abort", style=dashed, color="#a32e2e"];
    Capture   -> Refund  [label="merchant refund", style=dashed, color="#a32e2e"];
    Settle    -> Adjust  [label="reconciliation diff", style=dashed, color="#a32e2e"];
    Reconcile -> Dispute [label="chargeback", style=dashed, color="#a32e2e"];
}
""",
                },
                {"type": "h3", "text": "Compensations (the unhappy paths)"},
                {
                    "type": "table",
                    "headers": ["Forward action", "Compensation", "When it fires"],
                    "rows": [
                        ["Authorize", "Void", "Fraud verdict flips post-auth, or merchant aborts before capture"],
                        ["Capture", "Refund", "Merchant-initiated refund; reverses ledger entries with new rows"],
                        ["Settle", "Adjustment entry", "Reconciliation finds a discrepancy vs the network file"],
                        ["Reconcile", "Chargeback / dispute", "Cardholder disputes; funds reverse, evidence package built"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Every Step Must Be Idempotent",
                    "body": (
                        "Sagas only work if every forward action and every compensation can "
                        "be replayed without side effects. Authorize uses the merchant&rsquo;s "
                        "<code>Idempotency-Key</code>; capture and refund use the "
                        "<code>payment_id</code> as the dedup key; ledger writes are guarded "
                        "by <code>UNIQUE (transaction_id, account_id, side)</code>."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Fraud Detection & Prevention",
            "subtitle": "ML + rules + 3DS",
            "blocks": [
                {"type": "h3", "text": "Real-Time ML Model"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Algorithm:</strong> LightGBM (gradient boosted trees); retrained daily on the last 30 days",
                        "<strong>Features:</strong> merchant (MCC, chargeback ratio), card (BIN age, country), user (device, IP, geo, velocity), transaction (amount, currency, MCC)",
                        "<strong>Output:</strong> <code>fraud_score</code> 0–100; merchant sets thresholds (e.g. 70 = decline, 85 = manual review)",
                        "<strong>Latency:</strong> p99 &lt; 50 ms; served via Seldon / KServe / in-process",
                        "<strong>Monitoring:</strong> precision, recall, AUC-ROC daily; rebalance for class imbalance (fraud ~0.5%)",
                        "<strong>Model server:</strong> shadow + A/B traffic; kill-switch back to last-good model",
                    ],
                },
                {"type": "h3", "text": "Deterministic Rules + 3DS"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Velocity:</strong> same card 5× in 5 min → decline; 3× different merchants in 1 min → review",
                        "<strong>Geo anomalies:</strong> card issued US, txn from RU 1 h ago, now UK → impossible-travel risk",
                        "<strong>3DS:</strong> cardholder SMS OTP or biometric; 30–120 s latency; <em>liability shift</em> to issuer if authenticated",
                        "<strong>Device fingerprinting:</strong> client-side JS collects user-agent, screen, timezone, IP; detects stolen-creds fingerprints",
                        "<strong>Allow / deny lists:</strong> per-merchant overrides for known good/bad customers",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why ML + Rules Together",
                    "body": (
                        "Pure rules are explainable but bleed against adaptive fraud rings. "
                        "Pure ML catches novel patterns but is a black box that regulators "
                        "and risk teams hate. The combination — ML for the score, rules for "
                        "hard guardrails (velocity, BIN bans, AML lists) — is the industry "
                        "standard."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Settlement & Reconciliation",
            "subtitle": "Daily accounting cycle",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Authorization promises money. <strong>Settlement</strong> moves it. "
                        "Card networks send daily settlement files (typically T+1 to T+3); we "
                        "match each line to a <code>payments</code> row and to its ledger "
                        "entries. Discrepancies are the highest-priority alert in the system — "
                        "they mean either the network or our ledger is wrong, and one of them "
                        "is going to cost real money."
                    ),
                },
                {"type": "h3", "text": "Daily Batch Job (2 AM UTC)"},
                {
                    "type": "numbered",
                    "items": [
                        "Pull settlement file from each card network (Visa, Mastercard, Amex)",
                        "Parse rows into a staging table: <code>(network_txn_id, payment_id, amount, fee, status)</code>",
                        "Match against <code>payments</code> by <code>payment_id</code> + <code>amount_cents</code> within tolerance",
                        "Matched rows: insert ledger <strong>settlement entries</strong> (debit clearing account, credit merchant balance, debit fee)",
                        "Mark <code>payments.settled_at</code>; emit <code>payment.settled</code> to Kafka",
                        "Unmatched rows: write to <code>reconciliation_discrepancies</code>; page on-call",
                        "Nightly invariant check: <code>SUM(debits) = SUM(credits)</code> per account and globally",
                    ],
                },
                {"type": "h3", "text": "Refund Path"},
                {
                    "type": "bullets",
                    "items": [
                        "Merchant calls <code>POST /refunds</code> with <code>payment_id</code> + (optional) <code>amount</code>",
                        "Validate: payment is captured, refund &lt;= captured amount, idempotency key supplied",
                        "Reverse authorization on the card network; await ack",
                        "Append ledger entries: debit merchant balance, credit cardholder clearing account",
                        "Emit <code>payment.refunded</code>; cardholder sees funds in 3–5 business days",
                    ],
                },
                {"type": "h3", "text": "Discrepancy Categories"},
                {
                    "type": "table",
                    "headers": ["Category", "Likely cause", "Action"],
                    "rows": [
                        ["Network has, we don't", "Lost write; double-charge risk", "Manual review; insert payment + ledger or refund"],
                        ["We have, network doesn't", "Auth never settled; expired hold", "Mark expired; reverse ledger; notify merchant"],
                        ["Amount mismatch", "FX rounding; partial capture", "Adjustment entry; root-cause within 24 h"],
                        ["Fee mismatch", "Tariff change or pricing bug", "Reprice; adjustment entry; finance review"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "The Invariant",
                    "body": (
                        "<code>SUM(debit_cents) = SUM(credit_cents)</code>. Verified per "
                        "transaction, per account, per day, and globally. If this number is "
                        "ever non-zero, every senior engineer in the company gets paged. The "
                        "ledger is the source of truth — not the database, not the network "
                        "file, the ledger."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Failure Modes & Recovery",
            "subtitle": "What breaks and how we survive it",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Cause", "Impact", "Mitigation"],
                    "rows": [
                        ["Bank Timeout", "Issuing bank API &gt; 5 s",
                         "Auth hangs; client retries; potential duplicate",
                         "Hard 5 s timeout; soft decline; idempotency prevents duplicate"],
                        ["Network Partition", "ISP / CDN routing down",
                         "Merchants can't reach API",
                         "Multi-region active-active; Route53 failover &lt; 30 s"],
                        ["Duplicate Charge", "Retry same idempotency key",
                         "Same charge twice (would be)",
                         "Redis SETNX + DB UNIQUE; cached response replay"],
                        ["Fraud False Positive", "ML model too strict",
                         "Good customer declined; lost revenue",
                         "A/B threshold tests; FP rate dashboard; merchant-tunable thresholds"],
                        ["PCI DSS Breach", "DB hacked; card data exposed",
                         "Regulatory fine $5–25M; brand damage",
                         "Tokenize at edge; PAN never in app code; HSM vault; PCI audit"],
                        ["Card Network Outage", "Visa/MC APIs down (rare)",
                         "Cannot authorize any txns",
                         "Cached pre-approved BIN list; local fallback rules; route to backup network"],
                        ["Redis Eviction", "Memory full; old keys evicted prematurely",
                         "Idem key expired; duplicate charge possible",
                         "Size cluster at 4 TB (1.6× working set); fall back to durable PG row"],
                        ["Kafka Down", "Broker cluster unavailable",
                         "Webhooks stop; settlement delayed",
                         "Local outbox table; replay on recovery; PG remains source of truth"],
                        ["Ledger Drift", "Reconciliation mismatch vs network",
                         "Money in flight; audit risk",
                         "Page on-call; freeze affected merchant; manual reconcile within 24 h"],
                    ],
                },
                {"type": "h3", "text": "Disaster Recovery"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>RTO:</strong> &lt; 60 s for a regional API outage (Route53 failover); &lt; 5 min for a primary DB failover",
                        "<strong>RPO:</strong> 0 for ledger writes (synchronous WAL replication); &lt; 1 min for analytics",
                        "<strong>Backups:</strong> continuous WAL archiving + nightly snapshot; 30-day retention online, 7 yr in Glacier",
                        "<strong>Failover drills:</strong> monthly chaos exercises; quarterly full-region failover; tested pgmrgr scripts",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful Degradation Order",
                    "body": (
                        "Under load shedding, drop in this order: (1) analytics enrichment, "
                        "(2) webhook delivery (deliver later), (3) recommendations / nice-to-haves, "
                        "(4) <em>never</em> the money path. Authorization, ledger write, and "
                        "idempotency are the last things to break."
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        # NEW SECTION: Design Trade-offs
        {
            "num": "11",
            "title": "Design Trade-offs",
            "subtitle": "Decisions and rationale",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Decision", "Choice", "Trade-off"],
                    "rows": [
                        [
                            "Distributed transaction model",
                            "Saga (event-driven compensation across processor → fraud → card network → ledger)",
                            "Survives partial outages, each step idempotent, scales horizontally; trade-off is transient inconsistency windows (\"authorized but not yet captured\") and the requirement to design every compensation explicitly. Alternative 2PC gives atomicity across services but blocks on the coordinator and is incompatible with 5-nines targets that depend on external third-party banks.",
                        ],
                        [
                            "Settlement",
                            "Async, daily batch (T+1) reconciliation against card-network files",
                            "Matches how Visa/Mastercard actually settle, batches I/O cheaply, allows nightly invariant checks (sum debits = sum credits); trade-off is that money is \"in flight\" for 24–72 h and discrepancies are not detected in real time. Alternative real-time settlement requires direct network membership and offers limited benefit for typical PSP-style integrations.",
                        ],
                        [
                            "Card-network integration",
                            "Integrate with PSPs / acquirers (Stripe-style) rather than direct network membership",
                            "Faster to launch, no PCI Level 1 acquirer compliance from day one, fewer bank contracts; trade-off is per-transaction fees, dependence on the PSP's uptime, and the PSP's own rate limits. Direct membership is cheaper at very high volume but takes 12–24 months and a Level-1 audit.",
                        ],
                        [
                            "Idempotency mechanism",
                            "Client-supplied <code>Idempotency-Key</code> (UUID), dedup via Redis SETNX with TTL + durable mirror in PostgreSQL",
                            "Constant-time check, exact replay of original response, easy for merchants to reason about; trade-off is that merchants must generate stable keys (a real implementation problem) and Redis must be sized to never evict before TTL. Alternative request-content hashing dedups even when the merchant forgets the header but cannot tell a \"legitimate retry of an identical charge\" from a \"two real charges that happen to look the same\".",
                        ],
                        [
                            "Ledger model",
                            "Append-only, immutable, double-entry",
                            "Auditable by construction (<code>SUM(debits) = SUM(credits)</code> is a 1-line invariant), no destructive updates means no corruption from a buggy migration, easy to replay; trade-off is storage growth (every correction is a new row) and that \"current balance\" requires a materialized view. Alternative mutable ledger is cheaper to query but loses the audit guarantees regulators require.",
                        ],
                        [
                            "Webhook delivery",
                            "At-least-once with exponential backoff (1s, 10s, 100s, 1000s, …); merchants must dedup by event_id",
                            "Delivery survives merchant outages up to ~hours, no central coordinator needed; trade-off is that merchants will see duplicates and must keep their own dedup table. Alternative exactly-once delivery is unimplementable across an arbitrary merchant network — pushing dedup to the merchant is the industry standard.",
                        ],
                        [
                            "PCI scope",
                            "Tokenize at the edge; raw PAN never enters application code or the primary DB",
                            "Shrinks the PCI DSS audit boundary from \"everything\" to just the HSM/vault tier, which materially reduces audit cost and breach surface; trade-off is one extra hop on every charge and a hard dependency on the vault's uptime. Alternative storing raw PAN simplifies some flows but pulls the entire stack into PCI scope and turns every breach into a $5–25M event.",
                        ],
                        [
                            "Fraud scoring",
                            "Real-time inline ML (LightGBM, p99 &lt; 50 ms) + offline daily retraining",
                            "Catches novel fraud patterns within 24 h, latency stays inside the auth budget; trade-off is concept drift between retrains and the operational cost of a model server in the auth path. Alternative pure rules engine is cheaper and explainable but bleeds against adaptive fraud rings.",
                        ],
                        [
                            "Consistency for ledger writes",
                            "Strong (single-writer Postgres primary, synchronous WAL, multi-AZ replicas)",
                            "Money never disappears or duplicates; trade-off is that the write path is bounded by primary throughput and a regional outage requires a controlled failover (RTO seconds, RPO 0). Alternative multi-master / eventually-consistent ledger is faster to write but cannot guarantee the double-entry invariant under partition.",
                        ],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Headline Tension",
                    "body": (
                        "Payments has two competing obsessions: <strong>correctness</strong> "
                        "(no double-charge, no lost money, audit on demand) and "
                        "<strong>availability</strong> (5 nines despite a card network you do "
                        "not own). Almost every choice in the table picks <em>correctness</em> "
                        "for the money path (strong consistency, append-only ledger, "
                        "idempotency, tokenization) and <em>availability</em> for everything "
                        "else (sagas, async webhooks, batch settlement, regional active-active)."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Interview Playbook",
            "subtitle": "45-minute presentation",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "This guide distils a 45-minute payment-gateway interview into a "
                        "structured narrative. Use it to practice clarifying scope, framing "
                        "the correctness/availability tension, and defending trade-offs with "
                        "specific numbers."
                    ),
                },
                {"type": "h3", "text": "Timeline: 5 + 3 + 10 + 20 + 7 minutes"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Opening (5 min):</strong> clarifying questions (payment types? regions? PCI level?) → state assumptions",
                        "<strong>Problem framing (3 min):</strong> 250M txn/day → ~10K TPS sustained, ~100K peak; card network is 1.5–8 s; everything we own must be sub-second",
                        "<strong>Architecture (10 min):</strong> show Diagram 1; explain 4 tiers; solid arrows = sync money path, dashed = async events",
                        "<strong>Deep dives (20 min):</strong> pick 2–3: idempotency keys (with code), saga + compensations (Diagram 2), fraud ML, ledger invariant, reconciliation",
                        "<strong>Wrap-up (7 min):</strong> trade-offs (at-least-once vs exactly-once; batch vs real-time settlement); compliance complexity; closing on the headline tension",
                    ],
                },
                {"type": "h3", "text": "Key Numbers to Memorize"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Volume:</strong> 250M txn/day; ~10K TPS sustained; ~100K TPS Black Friday peak",
                        "<strong>Latency:</strong> gateway p99 &lt; 500 ms; fraud &lt; 50 ms; DB write &lt; 20 ms; end-to-end p99 8–10 s",
                        "<strong>Card-network round-trip:</strong> 1.5–3 s p50, 5–8 s p99 (out of our control)",
                        "<strong>Uptime:</strong> 99.999% ≈ <strong>5 min 16 sec/year</strong> (≈ 315 sec; ≈ 26 sec/month). Six nines would be ~31 sec/year — out of reach for any system that depends on third-party card networks",
                        "<strong>Idempotency cache:</strong> ~2.5 TB Redis (24 h TTL); cluster sized at 4 TB",
                        "<strong>Storage:</strong> ~180 TB hot payments (1 yr); ~110 TB hot ledger; 7-year retention (PCI/SOX)",
                        "<strong>Ledger:</strong> 3–4 entries/charge; ~1B rows/day; invariant <code>SUM(debits)=SUM(credits)</code>",
                        "<strong>Settlement:</strong> daily batch; T+1 to T+3 latency",
                    ],
                },
                {"type": "h3", "text": "Common Probe Questions & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: How do you prevent double-charges?</strong> A: Client-supplied <code>Idempotency-Key</code> + Redis SETNX with PENDING/DONE marker + body-hash 409; durable backstop in PG <code>UNIQUE</code>.",
                        "<strong>Q: Card-network timeout — what do you do?</strong> A: Hard 5 s timeout, soft decline (do <em>not</em> retry on the customer's behalf), idempotency makes the merchant's retry safe.",
                        "<strong>Q: Why double-entry accounting?</strong> A: <code>SUM(debits)=SUM(credits)</code> is a one-line audit invariant; append-only means no destructive corruption; mandatory for SOX.",
                        "<strong>Q: How does 3DS work?</strong> A: Cardholder authenticates (OTP / biometric); on success, liability shifts from merchant to issuer.",
                        "<strong>Q: Multi-region or single?</strong> A: Active-active across regions for the API and read path; primary-replica with controlled failover for the ledger (correctness over availability for money).",
                        "<strong>Q: 2PC or saga?</strong> A: Saga every time. 2PC blocks on the coordinator and cannot survive a card-network partition; we&rsquo;d miss our 5-nines target on the first bad day.",
                        "<strong>Q: What about exactly-once webhooks?</strong> A: Unimplementable across an arbitrary merchant network — we deliver at-least-once and the merchant dedups by <code>event_id</code>.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "10K TPS sustained &nbsp;·&nbsp; 100K TPS peak &nbsp;·&nbsp; "
                        "p99 gateway 500 ms &nbsp;·&nbsp; p99 end-to-end 8–10 s &nbsp;·&nbsp; "
                        "99.999% ≈ 5 min 16 sec/year &nbsp;·&nbsp; "
                        "2.5 TB idem cache &nbsp;·&nbsp; 180 TB hot payments &nbsp;·&nbsp; "
                        "3–4 ledger entries/charge &nbsp;·&nbsp; T+1 settlement"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Closing Line",
                    "body": (
                        "<em>&ldquo;Payment systems demand obsessive correctness and "
                        "resilience. Idempotency is the single most important contract in "
                        "the API. Test failure modes relentlessly: mock timeouts, simulate "
                        "database failures, verify the ledger invariant nightly. Everything "
                        "else is in service of: never lose a cent, never charge twice, prove "
                        "it on demand.&rdquo;</em>"
                    ),
                },
            ],
        },
    ],
}
