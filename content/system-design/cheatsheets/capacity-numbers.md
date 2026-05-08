---
title: Capacity & Throughput Cheat Sheet
description: Rough numbers you can quote in an interview without flinching.
---

## Per-machine throughput (rough)

| Component | Order of magnitude |
|---|---|
| Modern web app server (Node, Go) | 10–50k QPS for simple endpoints |
| Postgres (well-tuned) | 10–30k TPS, falls fast under contention |
| Redis | ~100k ops/sec/node, sub-ms p99 |
| Memcached | ~200k ops/sec/node |
| Kafka broker | ~1 MB/s per partition steady; bursts much higher |
| Cassandra node | ~10k writes/sec/node |
| Elasticsearch (search) | a few hundred QPS for complex queries |

## Common back-of-envelope estimates

- **Daily active users → QPS**: `DAU × actions/user/day / 86400`. 100M DAU × 10 actions/day ≈ 11k QPS average; peak ≈ 3× ≈ 33k QPS.
- **Bytes per row** (typical): id 8B, fk 8B, timestamp 8B, short string 32B, blob/text 1–10KB. Index ≈ 16–32B per entry.
- **Storage from QPS**: `writes/sec × bytes/row × seconds in retention`. 10k writes/sec × 1KB × 1 yr ≈ 315 TB/yr.
- **Replication overhead**: ×3 for 3-replica systems (Cassandra, GFS-style).

## Useful conversions

- 1 day = 86,400 s
- 1 month ≈ 2.6M s
- 1 year ≈ 31.5M s
- 1 KB → 1 MB → 1 GB → 1 TB → 1 PB → 1 EB (each ×1024)
- 1 Gbps line: ~125 MB/s usable
- 1 typical cache page: 64 bytes

## Interview rules of thumb

1. **State your assumptions before estimating** — "1B users, 10% DAU, peak/avg of 3."
2. **Round aggressively** — 86,400 → 100,000. Don't get lost in arithmetic.
3. **Always express both QPS *and* bandwidth** — they hit different bottlenecks.
4. **Re-derive when probed** — interviewers will challenge a number. Show the calculation, not just the answer.
