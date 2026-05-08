---
title: Latency Numbers Every Engineer Should Know
description: The orders of magnitude. Memorise the rough shape, not the exact values.
---

## The big table

| Operation | Latency | Notes |
|---|---|---|
| L1 cache reference | 1 ns | |
| Branch mispredict | 3 ns | |
| L2 cache reference | 4 ns | |
| Mutex lock/unlock | 17 ns | |
| Main memory reference | 100 ns | 25× slower than L2 |
| Compress 1KB with Snappy | 2 µs | |
| Send 2KB over 1 Gbps network | 20 µs | |
| Read 1 MB sequentially from RAM | 3 µs | |
| SSD random read | 16 µs | |
| Read 1 MB sequentially from SSD | 49 µs | |
| Round-trip in same datacenter | 500 µs | |
| Read 1 MB sequentially from disk (HDD) | 825 µs | |
| Disk seek | 2 ms | |
| Round-trip CA → Netherlands | 150 ms | |

## Order-of-magnitude collapse (memorise these 5)

- **Cache: ~1 ns**
- **Memory: ~100 ns** (100× cache)
- **SSD: ~10 µs** (100× memory)
- **Datacenter network: ~500 µs** (50× SSD)
- **Cross-continent RTT: ~150 ms** (300× datacenter)

## What this implies

- A request that hits memory and stays in-DC is sub-ms easily.
- One disk seek per request caps you at ~500 RPS per spinning disk. Why we like SSDs and we like RAM more.
- Cross-region replication has unavoidable latency; eventual consistency is a physics consequence as much as a design choice.
- N+1 queries inside a single request: each adds a DC round-trip. 20 of them = 10 ms before any work happens.
