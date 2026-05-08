---
title: Database Picker
description: Which DB for which workload, with the one-line reasoning.
---

## Decision tree

```mermaid
flowchart TD
  A[What's the access pattern?] --> B{Strong consistency<br/>+ relational joins?}
  B -- yes --> P[Postgres / MySQL]
  B -- no --> C{Heavy writes,<br/>partition by key?}
  C -- yes --> D{Time-series?}
  D -- yes --> TS[InfluxDB / TimescaleDB]
  D -- no --> E{Wide row /<br/>append-heavy?}
  E -- yes --> Cas[Cassandra / Scylla]
  E -- no --> KV[DynamoDB / Bigtable]
  C -- no --> F{Document shape?}
  F -- yes --> Mo[MongoDB]
  F -- no --> G{Search / full-text?}
  G -- yes --> ES[Elasticsearch / OpenSearch]
  G -- no --> H{Graph traversals?}
  H -- yes --> Neo[Neo4j / JanusGraph]
  H -- no --> KV
```

## Quick reference

| Need | Pick | Because |
|---|---|---|
| Transactions across rows | **Postgres** | ACID, mature, joins are fine up to 100M rows with good indexes |
| Massive write throughput, low query complexity | **Cassandra / DynamoDB** | LSM trees, no global locks, partition-key driven |
| Sub-ms read of hot keys | **Redis** | In-memory, cluster mode for sharding |
| Full-text search / faceting | **Elasticsearch** | Inverted index, relevance scoring |
| Analytics queries on TBs | **Snowflake / BigQuery / Redshift** | Columnar, MPP |
| Time-series telemetry | **TimescaleDB / InfluxDB** | Compression + downsampling |
| Highly connected data (social graph) | **Neo4j** | Index-free adjacency, fast traversals |
| Strict ordering + replay | **Kafka** (as log, not DB) | Partitioned append-only log |
| Geographically distributed strong-consistency | **Spanner / CockroachDB** | TrueTime / Raft, expensive |

## Don't pick X if…

- **Postgres**, if you need >50k writes/sec sustained — start sharding sooner.
- **MongoDB**, if relationships dominate; you'll rebuild joins in app code.
- **DynamoDB**, if your access patterns aren't fully known up front — schema rework is painful.
- **Elasticsearch**, as your source of truth — it's a search index, not a DB.
- **Cassandra**, for read-modify-write patterns — last-write-wins surprises people.

## Hybrid is normal

Most real systems use 2–3:

- Postgres (source of truth) + Redis (hot cache) + Elasticsearch (search) is the most common stack at small scale.
- DynamoDB + S3 + DAX (cache) at AWS-native scale.
- Always justify the "why each one" — interviewers like seeing the reasoning, not just the menu.
