# Design Questions — Errata & Corrections

This file lists every known error in the `design-questions/` PDFs, together with drop-in replacement text. Until the PDFs are regenerated, treat the corrected text below as authoritative.

**Coverage:** PDFs 02, 04, 05, 06, 07, 08, 09. PDFs 01 and 03 had no material issues.

**How to use:** Each entry quotes the original wording verbatim, explains the issue, and gives a corrected paragraph that fits the same length budget as the original so it can be pasted into a regenerated PDF without reflowing the page.

---

## 02 - URL Shortener

### Erratum 1: Pareto principle stated backwards
**Section / page:** Section 03, Capacity Estimation — Cache Estimation
**Original text:**
> • Hot URLs: 20% of reads hit 80% of URLs (Pareto principle)

**Issue:** The two ratios are inverted; the Pareto principle says 80% of reads concentrate on 20% of URLs, not the other way around.

**Corrected text:**
> • Hot URLs: 80% of reads hit 20% of URLs (Pareto principle)

### Erratum 2: Cache size contradiction
**Section / page:** Section 03, Capacity Estimation — Cache Estimation
**Original text:**
> • Hot set size: (115K reads/sec) × 0.8 × (24 hours) = 7.9B requests to 1.6B unique URLs
> • Cache size needed: 1.6B URLs × 500B = 800 GB (or deduplicate to top 23M: 23M × 500B = 11.5 GB)

**Issue:** The 1.6B-URL figure assumes every read in 24 hours is a distinct URL, ignoring reuse, so the 800 GB number contradicts the 11.5 GB summary. Cache the 24-hour hot set, not the 5-year hot set.

**Corrected text:**
> • Hot set size: 80% of reads target ~20% of recently-active URLs; over 24 hours that is the working set, not the 5-year corpus
> • Cache sizing: 24h reads = 115K/sec × 86,400 ≈ 9.9B; 80% (~7.9B) hit ~20% of recently-active URLs ≈ 20–30M keys
> • Cache size needed: ~25M URLs × 500B ≈ 12 GB (round to ~11.5 GB Redis cluster with TTL = 24h)

---

## 04 - YouTube

### Erratum 1: Concurrent viewer math
**Section / page:** 03 · Capacity Estimation & Metrics — Streaming (Watch) Volume & Bandwidth
**Original text:**
> Estimated daily watch hours: ~1 billion hours/day
> Concurrent streams at peak:
> 1B hours/day ÷ 86,400 sec = 11.6 million concurrent viewers
> Bandwidth requirement (at 2 Mbps average adaptive bitrate):
> 11.6M streams × 2 Mbps = 23.2 Tbps (Terabits/sec) peak
> CDN needs to handle ≈2.3 Pbps global bandwidth
> Accounting for PoP peering, this is ≈ 500-1000 Tbps to origin.

**Issue:** The derivation divides hours by seconds, mixing units; the correct conversion is hours-watched per day ÷ hours per day, which yields a much larger concurrent figure and changes every downstream bandwidth number.

**Corrected text:**
> Estimated daily watch hours: ~1 billion hours/day
> Concurrent streams (uniform across the day):
> 1B hours/day ÷ 24 h/day ≈ 41.7 million concurrent viewers
> Bandwidth requirement (at 2 Mbps average adaptive bitrate):
> 41.7M streams × 2 Mbps ≈ 83 Tbps (Terabits/sec) average egress
> Peak ≈ 2× average (diurnal/regional skew) → ~170 Tbps CDN egress
> With 95% edge cache hit rate, origin pull ≈ 5% × 83 Tbps ≈ 4 Tbps.

### Erratum 2: Upload-volume math
**Section / page:** 03 · Capacity Estimation & Metrics — Daily Upload Volume
**Original text:**
> 500 hours/minute × 60 minutes = 30,000 hours/day
> Assuming avg video is 10 minutes:
> 30,000 hours = 30,000 × 60 min = 1,800,000 videos/day

**Issue:** The line multiplies hours by minutes-per-hour and labels the result as videos, omitting the divide-by-video-length step; the correct figure is 10× smaller.

**Corrected text:**
> 500 hours/minute × 60 minutes = 30,000 hours/day
> Assuming avg video is 10 minutes:
> 30,000 h/day × 60 min/h ÷ 10 min/video = 180,000 videos/day

---

## 05 - Netflix

### Erratum 1: Replace Hystrix reference
**Section / page:** Section 08, Microservices & Resilience — Hystrix Circuit Breaker (Resilience Pattern)
**Original text:**
> Hystrix Circuit Breaker (Resilience Pattern)

**Issue:** Netflix moved Hystrix to maintenance mode in 2018; the current recommendation is resilience4j (or Spring Cloud Circuit Breaker), with Netflix internally adopting adaptive concurrency limits.

**Corrected text:**
> Circuit Breaker (Resilience Pattern — resilience4j / concurrency-limits)
>
>    • Note: Netflix put Hystrix into maintenance mode in 2018; new services use resilience4j (or Spring Cloud Circuit Breaker), and Netflix internally adopted adaptive concurrency limits via the concurrency-limits library.

### Erratum 2: Recommendation funnel phrasing
**Section / page:** Section 10, Three-Stage Ranking Pipeline — Why Three Stages?
**Original text:**
> • Speed: Each stage reduces candidate set; Stage 3 ranking only runs on 2K titles, not 5K+

**Issue:** "2K titles, not 5K+" muddles the funnel: the doc states ~10K candidates from Stage 1, ~1–2K after Stage 2 filtering, and ~100 displayed after Stage 3 ranking. The comparison should reflect the monotonic narrowing.

**Corrected text:**
> • Speed: Each stage narrows the set monotonically — ~5K-title catalog → ~10K user-specific candidates (Stage 1 ALS) → ~1–2K after filtering (Stage 2) → ~100 ranked titles displayed (Stage 3); LightGBM only scores the ~1–2K survivors, not the full catalog

---

## 06 - Google Drive / Dropbox

### Erratum 1: Peak upload bandwidth
**Section / page:** 03 · Capacity Estimation — Sync Activity
**Original text:**
> Peak bandwidth (uploads): During business hours, 100K concurrent users × 1Mbps = 100 Tbps

**Issue:** 100,000 × 1 Mbps equals 100 Gbps, not 100 Tbps; the result is off by a factor of 1000.

**Corrected text:**
> Peak bandwidth (uploads): During business hours, 100K concurrent users × 1Mbps = 100 Gbps

### Erratum 2: Total storage figure (10 PB vs 5 EB contradiction)
**Section / page:** 02 · Non-Functional Requirements and 03 · Capacity Estimation — User & Storage
**Original text:**
> Scale: 1B+ users; 10PB+ storage; 100K+ concurrent active syncs; 1M+ RPS
> ...
> Avg storage per user: ~10GB (Google Drive); ranging 100MB–2TB
> Total storage: 500M users × 10GB = 5EB (exabytes) = 5,000 petabytes
> Deduplication factor: ~40% (duplicate files, backups, shared folders reduce net storage)
> Net storage after dedup: 5EB × 0.6 = 3EB physical storage on S3

**Issue:** The "10 PB+" requirement contradicts the later derivation of multi-exabyte storage; the 10 GB/user assumption also overstates real average usage, since most accounts are free-tier with far less data.

**Corrected text:**
> Scale: 1B+ users; 1EB+ storage; 100K+ concurrent active syncs; 1M+ RPS
> ...
> Avg storage per user: ~2GB (blended free + paid; paid tiers average ~10GB, free tiers <1GB)
> Total storage: 500M users × 2GB ≈ 1EB (exabyte) logical
> Deduplication factor: ~40% (duplicate files, backups, shared folders reduce net storage)
> Net storage after dedup: 1EB × 0.6 ≈ 600PB physical storage on S3

### Erratum 3: S3 cost per GB
**Section / page:** 13 · Trade-offs & Alternatives
**Original text:**
> S3 storage             Custom object store               Cost: S3 11¢/GB vs. custom ~1¢/GB; but custom
>                                                          requires operational overhead

**Issue:** S3 Standard list price is ~$0.023/GB-month, not 11¢; the 11¢ figure overstates S3 cost roughly 5×.

**Corrected text:**
> S3 storage             Custom object store               Cost: S3 Standard ~2.3¢/GB-mo (Glacier ~0.4¢)
>                                                          vs. custom ~1¢/GB-mo; custom requires ops overhead

---

## 07 - Amazon E-commerce

### Erratum 1: Order-volume scale figures are off by ~16x average / ~26x peak
**Section / page:** 01 Problem Overview ("The Scale Problem"); echoed in 03 Capacity Estimation ("Order Volume") and 12 Interview Playbook ("Capacity Estimation", "Key Numbers to Memorize").
**Original text:**
> Amazon handles 500M products, 1B users, and processes 100K+ orders per day at peak.

> Peak traffic: 100K+ orders/day; 10K concurrent users during sales/holidays

> 100K orders/day peak (~1.2 orders/sec average)
> Peak burst (Cyber Monday): 500K orders/day (~6 orders/sec)

**Issue:** Public figures put Amazon's worldwide order volume near ~1.6M orders/day on an average day and ~13M+ orders/day on Prime Day / peak holiday events (Amazon disclosed ~13M items shipped on a record day, and analyst estimates of ~1.6M parcels/day are widely cited). "100K+ orders/day at peak" understates by more than an order of magnitude, and the derived "1.2 orders/sec" QPS is therefore wrong. Anyone using these numbers in an interview will under-provision every downstream component (Order Service capacity, Inventory write throughput, Kafka partitioning, ledger storage).

**Corrected text:**
> Amazon handles ~500M products, ~1B registered users (~300M MAU), and processes on the order of 1.6M orders/day on an average day, with peaks of 10–13M+ orders/day during Prime Day and Cyber Week.

> Average traffic: ~1.6M orders/day → ~18 orders/sec average
> Peak burst (Prime Day / Cyber Monday): ~13M orders/day → ~150 orders/sec, with intra-day spikes of 500–1,000 orders/sec in the first hour of a major sale

### Erratum 2: Order-storage math drops three zeros and is inconsistent with the headline scale
**Section / page:** 03 Capacity Estimation, "Order Volume" bullet.
**Original text:**
> Order storage: 100 orders/day × 365 × 10 years = 365M orders; ~5KB each = ~1.8TB

**Issue:** Two compounding bugs. (a) The line uses "100 orders/day" rather than the "100K orders/day" stated two bullets above — three zeros silently dropped. (b) Even if you use 100K/day, the result (365M orders / 1.8TB) understates the system. Once Erratum 1 is applied (1.6M/day average), the 10-year corpus is roughly 5.84B orders, not 365M.

**Corrected text:**
> Order storage: 1.6M orders/day × 365 × 10 years ≈ 5.84B orders
> Order record size: ~5 KB (header + items + addresses + status history) → ~29 TB hot in PostgreSQL
> With peaks at ~13M/day, sustained write rate is ~150 orders/sec average and ~1K/sec at the start of a flash sale; size shards (and Kafka partitions for OrderCreated) accordingly.
> Fulfillment queue: Kafka topic; ~1.6M events/day average, ~13M/day peak; 7-day retention ≈ 0.4–0.6 TB.

(Propagate the same correction to Section 12 "Key Numbers to Memorize" — replace "100K orders/day (1.2 ops/sec avg); 500K orders/day peak (6 ops/sec)" with "~1.6M orders/day (~18 ops/sec avg); ~13M orders/day peak (~150 ops/sec)".)

### New Section: Design Trade-offs (proposed)

This chapter is missing from the document. The standard study-guide template (see file 02 §15) carries an explicit "Design Trade-offs" chapter with a Decision / Choice / Trade-off table; in 07 the trade-off discussion is scattered across §05 and §12. Drop the following in as **new section 12, before the Interview Playbook**, and renumber Playbook → 13.

> ## 12 · Design Trade-offs
> ### Decisions and rationale
>
> | Decision | Choice | Trade-off |
> | --- | --- | --- |
> | Orders datastore | PostgreSQL (sharded by user_id, with read replicas) | Strong ACID for the money path and easy joins for fulfillment, but operationally heavier than DynamoDB; alternative NoSQL (DynamoDB / Cassandra) scales writes more cheaply but forces you to roll your own multi-row consistency for order + items + payment status. |
> | Inventory consistency | Eventual within a region (optimistic locking + 15-min reservation TTL); strong only inside the reserve transaction | High throughput, no global locks, occasional retries on contention; alternative strong/global consistency would block hot SKUs during flash sales and cap throughput at a few hundred ops/sec/SKU. |
> | Distributed transaction model | Saga (event-driven compensation via Kafka) across Order → Payment → Inventory | Loose coupling, high availability, each step independently scalable; trade-off is intermediate inconsistency windows ("payment captured but order not yet confirmed") and the requirement that every step be idempotent. Alternative 2PC gives atomicity but couples services, blocks on coordinator failure, and does not survive cross-region partitions. |
> | Concurrency control on stock | Optimistic locking with `version` column | Lock-free, scales horizontally, retries are cheap; alternative pessimistic `SELECT ... FOR UPDATE` serializes hot SKUs and creates lock convoys at peak. |
> | Search index population | Async index from CDC / Kafka into Elasticsearch (eventual, ~30–60s lag) | New products are searchable within a minute, write path stays cheap; alternative synchronous dual-write to Postgres + ES doubles write latency and creates partial-failure modes (in DB but not in index). |
> | Cart storage | Redis (TTL = 30 days), no DB write until checkout | Sub-millisecond reads/writes, cheap, naturally session-scoped; trade-off is that a Redis cluster failure loses in-flight carts (mitigated by AOF + replicas). Alternative DB-backed carts survive failures but inflate write load by ~10–100x and add latency to every "add to cart". |
> | Recommendations freshness | Offline ALS batch (daily) + online filter | Cheap to train, deterministic, A/B-testable; trade-off is staleness for new users / new items. Alternative real-time online learning is more responsive but harder to validate and prone to feedback loops. |
> | Read scaling | CDN + Redis cache for product detail (~95% hit) | Big origin offload, low latency; trade-off is cache invalidation complexity (price/stock changes must purge edge + Redis). |
> | Sharding strategy | Postgres sharded by `user_id` for orders; ES sharded by `product_id` hash | Aligns each query with a single shard; trade-off is that cross-user analytics needs a separate OLAP path (warehouse/Redshift). |
>
> **Headline tension.** The whole architecture is a balancing act between (a) the money-path which wants strong consistency, durability, and audit, and (b) the browsing path which wants global scale, low latency, and cheap reads. Microservice boundaries are drawn so each side can pick its own consistency model.

---

## 08 - Payment Gateway

### Erratum 1: 99.999% downtime budget is wrong by 10x
**Section / page:** 11 Interview Playbook, "Key Numbers to Memorize" bullet.
**Original text:**
> Uptime: 99.999% = 26 seconds downtime/year

**Issue:** 26 seconds/year is the budget for **six** nines (99.9999%). Five nines (99.999%) allows ~5.26 minutes of downtime per year (525,600 min × 0.00001 ≈ 5.256 min ≈ 315.36 seconds). The whole document is built on a 5-nines target (see §01 "Uptime: 99.999% (5 nines)"), so the number to memorise must match.

**Corrected text:**
> Uptime: 99.999% ≈ 5 min 16 sec downtime/year (≈ 315 seconds; ≈ 26 sec/month). Six nines would be ~31 sec/year — out of reach for any system that depends on third-party card networks.

### Erratum 2: End-to-end latency target contradicts itself
**Section / page:** 03 Capacity Estimation, "Storage & Latency"; §01 "Scale & Requirements".
**Original text:**
> Latency targets: fraud check <50ms; db write <20ms; end-to-end <2s (includes 3–5s bank latency)

> Latency: <500ms authorization; <2s end-to-end charge

**Issue:** The end-to-end target (<2s) cannot "include" a 3–5s dependency — the budget is smaller than one of its line items. The fix is to separate the two budgets, the way Stripe / Adyen / Braintree publish them: an in-gateway processing budget (everything we control) and a wire-level end-to-end budget (everything including issuing-bank round-trip).

**Corrected text:**
> Latency targets:
>     • Gateway processing (everything we own: API gateway → fraud → risk → ledger write, **excluding** card-network round-trip): p99 < 500 ms, p50 < 150 ms.
>     • Card-network + issuing-bank round-trip (out of our control): typically 1.5–3 s p50, 5–8 s p99 over ISO 8583 / network APIs.
>     • End-to-end authorization (gateway + network + bank): p99 ≤ 8–10 s, p50 ≈ 2 s. SLOs are defined separately so a slow issuer cannot blow our processing SLO.
>     • Fraud scoring: p99 < 50 ms (in-process model server).
>     • Primary DB write (ledger insert + idempotency upsert): p99 < 20 ms.

### New Section: Capacity Estimation (expanded replacement for §03)

The current §03 is a single bullet block. The reference template (file 02 §03) splits Capacity Estimation into clear traffic / storage / bandwidth subsections with a "Key Numbers" callout. Replace §03 with the following.

> ## 03 · Capacity Estimation
> ### Math for scale
>
> #### Traffic Estimation
> - Daily transactions: ~250M baseline → ~10K TPS sustained at peak hour (Stripe-scale), ~2.9K TPS daily average.
> - Black Friday / Cyber Monday peak: bursts to ~100K TPS globally for short windows; design headroom to 2× peak (~200K TPS) so we do not shed load during the 30-second flash window when every checkout in the world fires at once.
> - Read:Write profile: roughly 4:1 — every charge generates lookups (idempotency check, fraud features, merchant config, ledger reads for refunds/chargebacks) on top of the write.
> - Webhook fan-out: 1 charge → ~3 outbound events (authorized, captured, settled) → ~30K webhook deliveries/sec at peak; size Kafka and the retry tier for that, not for the raw charge rate.
>
> #### Storage Estimation
> - Per payment record: ~2 KB hot (UUIDs, amounts, status, auth_code, fraud_score, timestamps) + ~3 KB extended (addresses, device fingerprint, 3DS metadata) → budget ~5 KB/record including indexes.
> - Daily payments storage: 250M × 2 KB = ~500 GB/day hot; ~1.25 TB/day if the extended fields and per-row indexes are co-located.
> - Ledger entries: 3–4 per charge → ~1B rows/day × ~300 B = ~300 GB/day.
> - Retention: 7 years minimum (PCI DSS, SOX, most national tax regimes; some EU regimes require 10).
>     - Payments hot (1 year online): ~180 TB.
>     - Payments warm/archive (years 2–7): ~1.1 PB in object storage / Glacier.
>     - Ledger hot (1 year): ~110 TB; archive (years 2–7): ~660 TB.
> - Idempotency cache (Redis): 250M keys/day × 24 h TTL × ~10 KB cached response = ~2.5 TB; cluster sized at 4 TB to leave headroom.
>
> #### Bandwidth Estimation
> - Inbound API: 10K TPS × ~2 KB request body ≈ 20 MB/s sustained, 200 MB/s at Black Friday peak.
> - Card-network egress: 10K TPS × ~1 KB ISO 8583 frame ≈ 10 MB/s; replicated across regional acquirers.
> - Webhook egress: 30K events/sec × ~1 KB ≈ 30 MB/s sustained, ~300 MB/s peak.
> - Kafka inter-broker: ~3× replication factor on a ~50 MB/s topic mix → ~150 MB/s on the cluster backbone.
>
> > **N KEY NUMBERS**
> >
> > Sustained TPS: ~10K
> > Peak TPS (Black Friday): ~100K
> > Hot payments storage (1 yr): ~180 TB
> > Hot ledger storage (1 yr): ~110 TB
> > Idempotency cache: ~2.5 TB Redis (24 h TTL)
> > Retention: 7 years (PCI / SOX)

### New Section: Idempotency Key Handling (new)

The text repeatedly references idempotency keys (§05 Decision 1, §06 schema, §07 step 2) but never shows the actual logic. Add this as a new sub-section under §05 "Core Design Decisions", immediately after Decision 1.

> #### Idempotency Key Handling — Reference Implementation
>
> Every `POST /charges` requires the merchant to supply an `Idempotency-Key` header (a client-generated UUID). The gateway treats `(merchant_id, idempotency_key)` as the deduplication tuple. Replays are answered from cache; replays with a different body for the same key are rejected with `409`.
>
> ```python
> import hashlib, json, redis
>
> r = redis.Redis()
> TTL_SECONDS = 24 * 60 * 60  # 24h, matches Redis key retention
>
> def handle_charge(merchant_id, idempotency_key, request_body):
>     cache_key = f"idem:{merchant_id}:{idempotency_key}"
>     body_hash = hashlib.sha256(
>         json.dumps(request_body, sort_keys=True).encode()
>     ).hexdigest()
>
>     # SETNX = atomic "claim this key if nobody else has".
>     # Value initially holds the request fingerprint + a PENDING marker.
>     claimed = r.set(
>         cache_key,
>         json.dumps({"status": "PENDING", "body_hash": body_hash}),
>         nx=True, ex=TTL_SECONDS,
>     )
>
>     if not claimed:
>         existing = json.loads(r.get(cache_key))
>         if existing["body_hash"] != body_hash:
>             # Same key, different payload -> client bug or replay attack.
>             return 409, {"error": "idempotency_key_reuse_with_different_payload"}
>         if existing["status"] == "PENDING":
>             # Original request still in-flight -> tell client to retry.
>             return 409, {"error": "request_in_progress"}
>         # Completed: replay the cached response verbatim.
>         return existing["status_code"], existing["response"]
>
>     # First time we have seen this key -- actually run the charge.
>     try:
>         status_code, response = process_payment(merchant_id, request_body)
>     except Exception:
>         # Release the slot so the merchant's retry can proceed.
>         r.delete(cache_key)
>         raise
>
>     r.set(
>         cache_key,
>         json.dumps({
>             "status": "DONE",
>             "body_hash": body_hash,
>             "status_code": status_code,
>             "response": response,
>         }),
>         ex=TTL_SECONDS,
>     )
>     return status_code, response
> ```
>
> **Notes.**
> - `SET ... NX EX` is the atomic claim primitive (single round-trip; survives concurrent retries from the same merchant).
> - The PENDING marker lets us distinguish "in-flight" from "already finished" so a fast retry returns 409 instead of double-charging.
> - The body fingerprint protects against keys being reused by a buggy client for a different amount/currency/customer.
> - The Redis row is mirrored to the durable `idempotency_keys` table (see §06) so cache loss does not collapse the guarantee — on Redis miss, the API falls back to the DB row.

### New Section: Design Trade-offs (proposed)

This chapter is missing from the document. Add as new **§11 Design Trade-offs**, immediately before the Interview Playbook (renumber Playbook → 12). Format mirrors file 02 §15.

> ## 11 · Design Trade-offs
> ### Decisions and rationale
>
> | Decision | Choice | Trade-off |
> | --- | --- | --- |
> | Distributed transaction model | Saga (event-driven compensation across processor → fraud → card network → ledger) | Survives partial outages, each step idempotent, scales horizontally; trade-off is transient inconsistency windows ("authorized but not yet captured") and the requirement to design every compensation explicitly. Alternative 2PC gives atomicity across services but blocks on the coordinator and is incompatible with 5-nines targets that depend on external third-party banks. |
> | Settlement | Async, daily batch (T+1) reconciliation against card-network files | Matches how Visa/Mastercard actually settle, batches I/O cheaply, allows nightly invariant checks (sum debits = sum credits); trade-off is that money is "in flight" for 24–72 h and discrepancies are not detected in real time. Alternative real-time settlement requires direct network membership and offers limited benefit for typical PSP-style integrations. |
> | Card-network integration | Integrate with PSPs / acquirers (Stripe-style) rather than direct network membership | Faster to launch, no PCI Level 1 acquirer compliance from day one, fewer bank contracts; trade-off is per-transaction fees, dependence on the PSP's uptime, and the PSP's own rate limits. Direct membership is cheaper at very high volume but takes 12–24 months and a Level-1 audit. |
> | Idempotency mechanism | Client-supplied `Idempotency-Key` (UUID), dedup via Redis SETNX with TTL + durable mirror in PostgreSQL | Constant-time check, exact replay of original response, easy for merchants to reason about; trade-off is that merchants must generate stable keys (a real implementation problem) and Redis must be sized to never evict before TTL. Alternative request-content hashing dedups even when the merchant forgets the header but cannot tell a "legitimate retry of an identical charge" from a "two real charges that happen to look the same". |
> | Ledger model | Append-only, immutable, double-entry | Auditable by construction (`SUM(debits) = SUM(credits)` is a 1-line invariant), no destructive updates means no corruption from a buggy migration, easy to replay; trade-off is storage growth (every correction is a new row) and that "current balance" requires a materialized view. Alternative mutable ledger is cheaper to query but loses the audit guarantees regulators require. |
> | Webhook delivery | At-least-once with exponential backoff (1s, 10s, 100s, 1000s, …); merchants must dedup by event_id | Delivery survives merchant outages up to ~hours, no central coordinator needed; trade-off is that merchants will see duplicates and must keep their own dedup table. Alternative exactly-once delivery is unimplementable across an arbitrary merchant network — pushing dedup to the merchant is the industry standard. |
> | PCI scope | Tokenize at the edge; raw PAN never enters application code or the primary DB | Shrinks the PCI DSS audit boundary from "everything" to just the HSM/vault tier, which materially reduces audit cost and breach surface; trade-off is one extra hop on every charge and a hard dependency on the vault's uptime. Alternative storing raw PAN simplifies some flows but pulls the entire stack into PCI scope and turns every breach into a $5–25M event. |
> | Fraud scoring | Real-time inline ML (LightGBM, p99 < 50ms) + offline daily retraining | Catches novel fraud patterns within 24 h, latency stays inside the auth budget; trade-off is concept drift between retrains and the operational cost of a model server in the auth path. Alternative pure rules engine is cheaper and explainable but bleeds against adaptive fraud rings. |
> | Consistency for ledger writes | Strong (single-writer Postgres primary, synchronous WAL, multi-AZ replicas) | Money never disappears or duplicates; trade-off is that the write path is bounded by primary throughput and a regional outage requires a controlled failover (RTO seconds, RPO 0). Alternative multi-master / eventually-consistent ledger is faster to write but cannot guarantee the double-entry invariant under partition. |
>
> **Headline tension.** Payments has two competing obsessions: **correctness** (no double-charge, no lost money, audit on demand) and **availability** (5 nines despite a card network you do not own). Almost every choice in the table picks correctness for the money path (strong consistency, append-only ledger, idempotency, tokenization) and availability for everything else (sagas, async webhooks, batch settlement, regional active-active).

---

## 09 - Real-Time Collaborative Editor

### Erratum 1: Peak inbound throughput units
**Section / page:** 03 · Capacity Estimation — Bandwidth & Latency
**Original text:**
> Peak inbound: 60M ops/sec × 200 bytes = 12 TB/sec (aggregated across regions)

**Issue:** 60,000,000 × 200 bytes equals 12 GB/s, not 12 TB/s; the figure is off by a factor of 1000.

**Corrected text:**
> Peak inbound: 60M ops/sec × 200 bytes = 12 GB/sec (aggregated across regions)

### Erratum 2: "1000 concurrent docs per server" claim is unsupported
**Section / page:** 05 · Core Design Decisions: OT vs CRDT — Design Decision callout
**Original text:**
> We will use Operational Transform with a central OT engine and sticky sessions per doc. All edits route
> to one server; that server transforms ops and broadcasts results. This trades some scalability (can't
> horizontally scale per doc) for simplicity and correctness. At 50 users per doc, a single modern server (16
> cores, 64GB RAM) can handle ~1000 concurrent docs.

**Issue:** The "~1000 concurrent docs per server" capacity is asserted without back-of-envelope justification.

**Corrected text:**
> We will use Operational Transform with a central OT engine and sticky sessions per doc. All edits route
> to one server; that server transforms ops and broadcasts results. This trades some scalability (can't
> horizontally scale per doc) for simplicity and correctness. As a rough estimate, with ~10MB of in-memory
> state per active doc (snapshot + recent op buffer + presence) and ~100 ops/sec per doc to transform and
> fan out to 50 peers, a 16-core / 64GB server can plausibly host on the order of a few thousand concurrent
> docs before memory or fanout CPU saturates; treat this as an envelope, not a SLA.

### Erratum 3: OT section understates production difficulty
**Section / page:** 08 · OT/CRDT Deep Dive — Operational Transform (OT) Essentials
**Original text:**
> Operational Transform (OT) Essentials
>    • Core idea: Given two concurrent ops, compute a third op that applies both edits correctly
>    • Transform function: op' = T(op_a, op_b) where op' is op_a adjusted for op_b's effects
>    • For insert operations: If op_b inserts before op_a's position, shift op_a's position forward
>    • For delete operations: Delete positions shift based on prior insertions; overlapping deletes handled
>    carefully
>    • String vs tree: Most collaborative editors use string (linear sequence); complex docs use tree (nodes,
>    hierarchy)

**Issue:** The section presents OT as straightforward, but production-grade OT is notoriously hard — most modern collaborative editors picked CRDTs precisely because of this.

**Corrected text:**
> Operational Transform (OT) Essentials
>    • Core idea: Given two concurrent ops, compute a third op that applies both edits correctly
>    • Transform function: op' = T(op_a, op_b) where op' is op_a adjusted for op_b's effects
>    • For insert operations: If op_b inserts before op_a's position, shift op_a's position forward
>    • For delete operations: Delete positions shift based on prior insertions; overlapping deletes handled
>    carefully
>    • String vs tree: Most collaborative editors use string (linear sequence); complex docs use tree (nodes,
>    hierarchy)
>    • Why this is hard in practice: Correct OT requires the transform function to satisfy TP1 (convergence
>    for two concurrent ops) and TP2 (convergence for three or more concurrent ops applied in any order).
>    TP2 is famously difficult to satisfy — multiple published OT algorithms were later shown to violate it
>    under specific edit sequences. OT must also preserve user *intent* (e.g., not splitting a word a user just
>    typed), which adds further case analysis. These pitfalls are why most modern collaborative systems
>    (Figma, Automerge, Yjs) chose CRDTs instead, trading larger payloads for a merge function that is
>    correct by construction.
