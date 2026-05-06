"""Source for `06 - Google Drive and Dropbox.pdf` (regenerated with errata applied)."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Google Drive / Dropbox",
    "subtitle": "Cloud storage, block-level sync, and conflict resolution",
    "read_time": "~ 35 minute read",
    "short_title": "Design Google Drive / Dropbox",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Statement & Clarifying Questions",
            "subtitle": "Define the scope of the file sync and cloud storage system",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Design a cloud file storage and synchronization service like "
                        "<strong>Google Drive</strong> or <strong>Dropbox</strong>. The system "
                        "must store user files in the cloud, sync them across multiple devices, "
                        "support sharing and version history, and minimise bandwidth via "
                        "block-level deduplication."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Why It Matters", "Typical Answer"],
                    "rows": [
                        ["Sync only or full storage?",
                         "Determines bandwidth model; sync implies local copies",
                         "Both: cloud storage + device sync"],
                        ["Concurrent users per account?",
                         "Conflict-resolution complexity; shared folders",
                         "Multiple devices per user; shared folders with collaborators"],
                        ["File size limits?",
                         "Drives chunking strategy and upload protocol",
                         "Google: 5 TB/file; Dropbox: 350 GB/file (older 2 GB)"],
                        ["Real-time sync SLA?",
                         "Notification latency, polling frequency, cost",
                         "Within 30 sec to 5 min acceptable"],
                        ["Offline support?",
                         "Local caching; conflict handling",
                         "Yes; sync when reconnected; detect conflicts"],
                        ["Sharing & permissions?",
                         "Metadata schema; access control",
                         "Yes: file/folder sharing, read/write/admin roles"],
                        ["Version history?",
                         "Storage and query complexity",
                         "Yes: keep last 30 versions (configurable)"],
                        ["Geographic distribution?",
                         "CDN, replication, latency",
                         "Global: US, EU, APAC; local edge caching"],
                    ],
                },
                {
                    "type": "para",
                    "text": (
                        "We focus on personal cloud storage with multi-device sync, "
                        "block-level deduplication, and pragmatic conflict resolution. "
                        "Real-time collaborative editing (Docs/Sheets) is out of scope — that "
                        "is a CRDT/OT problem, not a file-sync problem."
                    ),
                },
            ],
        },
        # ---- 02 ------------------------------------------------------
        {
            "num": "02",
            "title": "Functional & Non-Functional Requirements",
            "subtitle": "What the system must do, and how well",
            "blocks": [
                {"type": "h3", "text": "Functional Requirements"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Upload files:</strong> single or chunked multipart (&gt;5 MB); resume on failure",
                        "<strong>Download files:</strong> fetch from cloud or local cache; reconstruct from blocks",
                        "<strong>Sync daemon:</strong> poll server for changes; detect local file changes",
                        "<strong>List files:</strong> metadata API with pagination; folder hierarchy",
                        "<strong>Delete files:</strong> soft delete with retention; hard delete after expiry",
                        "<strong>Share files / folders:</strong> granular permissions (read, write, admin)",
                        "<strong>Version history:</strong> keep previous versions; restore any version",
                        "<strong>Conflict resolution:</strong> detect concurrent edits; LWW or versioning fallback",
                        "<strong>Offline support:</strong> continue editing offline; sync on reconnect",
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Availability", "99.99% uptime SLA; graceful degradation if sync service fails"],
                        ["Latency", "Sync detection &lt;5 min; upload &lt;500ms (metadata); download &lt;1s (metadata)"],
                        # ERRATUM 2 applied: 1EB+ storage instead of 10PB+
                        ["Scale", "1B+ users; <strong>1 EB+ storage</strong>; 100K+ concurrent active syncs; 1M+ RPS"],
                        ["Bandwidth", "Minimise data transfer via block-level deduplication and delta sync"],
                        ["Storage cost", "Tiered (S3 Standard / Glacier); per-user quota enforcement"],
                        ["Security", "AES-256 at rest; TLS in transit; OAuth 2.0; audit logs"],
                        ["Consistency", "Eventual globally; strong for metadata within a datacenter"],
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
                {"type": "h3", "text": "User & Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>1B+ users</strong> worldwide; ~30% active monthly → <strong>~500M MAU</strong>",
                        # ERRATUM 2 applied: blended 2GB/user, ~1EB logical, ~600PB physical
                        "Avg storage per user: <strong>~2 GB blended</strong> (paid tiers ~10 GB, free tiers &lt;1 GB)",
                        "Total logical storage: 500M users × 2 GB ≈ <strong>1 EB</strong> (exabyte)",
                        "Deduplication factor: ~40% (backups, duplicate documents, shared media)",
                        "Net physical storage on S3: 1 EB × 0.6 ≈ <strong>~600 PB</strong>",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Why not 10 GB/user × 500M = 5 EB?",
                    "body": (
                        "An earlier version of this guide assumed every user fills the free quota. "
                        "In reality the distribution is heavily skewed: most accounts are free-tier "
                        "with &lt;1 GB used. A <strong>2 GB blended average</strong> is closer to "
                        "Google/Dropbox public figures and yields ~1 EB logical (not 5 EB)."
                    ),
                },
                {"type": "h3", "text": "Sync Activity"},
                {
                    "type": "bullets",
                    "items": [
                        "Peak concurrent active syncs: <strong>100K–500K</strong> (users actively editing/uploading)",
                        "Sync frequency: ~5 min average; desktop daemon checks every 30 sec when foregrounded",
                        "Files changed per user per day: avg 2–5 → <strong>~100M file ops/day</strong>",
                        "Baseline bandwidth: 500M users × 100 MB/month ÷ 30 days ≈ <strong>1.7 Gbps</strong>",
                        # ERRATUM 1 applied: 100K × 1Mbps = 100 Gbps, NOT 100 Tbps
                        "Peak upload bandwidth: 100K concurrent × 1 Mbps = <strong>100 Gbps</strong> (not Tbps)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Unit-check: Gbps vs Tbps",
                    "body": (
                        "100,000 × 1 Mbps = 100,000 Mbps = <strong>100 Gbps</strong>. "
                        "An earlier version printed 100 Tbps — off by a factor of 1,000. "
                        "100 Gbps is what a single AWS Direct Connect bundle delivers; 100 Tbps "
                        "would be roughly all of Netflix's global egress at peak. Always sanity-check "
                        "bandwidth answers against an anchor you trust."
                    ),
                },
                {"type": "h3", "text": "RPS Estimates"},
                {
                    "type": "bullets",
                    "items": [
                        "Upload RPS: 100K concurrent × 1 req/min = <strong>~1.7K RPS</strong> baseline; <strong>~10K RPS</strong> peak",
                        "Download RPS: ~5K RPS (viewing, sharing downloads)",
                        "Metadata RPS: list / get-versions / permission checks ≈ <strong>~50K RPS</strong>",
                        "Sync delta queries: 100K × 1 query/5 min ≈ ~333 RPS baseline; spike to ~5K RPS",
                        "Total API: <strong>~60K RPS baseline, ~100K RPS peak</strong>",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "1 EB logical &nbsp;·&nbsp; ~600 PB physical &nbsp;·&nbsp; "
                        "~100 Gbps peak upload &nbsp;·&nbsp; 100K concurrent syncs &nbsp;·&nbsp; "
                        "~100K RPS at peak &nbsp;·&nbsp; 4 MB block size &nbsp;·&nbsp; SHA-256 dedup."
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
                        "A distributed system serving files with block-level sync, deduplication, "
                        "and multi-device consistency. Reads are CDN-fronted; writes are chunked, "
                        "hashed, and deduped before they ever touch S3."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "End-to-end architecture: clients hit the CDN/API gateway, which fans out to Block, Metadata, and Notification services backed by S3, MySQL, Redis, and Kafka.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Clients"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Web   [label="Web App", fillcolor="#dbe6fb"];
        Desk  [label="Desktop Daemon\n(inotify/FSEvents)", fillcolor="#dbe6fb"];
        Mob   [label="Mobile App", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        CDN [label="CDN\n(downloads, thumbs)", fillcolor="#cbeedf"];
        GW  [label="API Gateway\n(OAuth, rate-limit)", fillcolor="#cbeedf"];
    }
    subgraph cluster_svc {
        label="Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        BS [label="Block Service\n(upload/download)", fillcolor="#fff2c9"];
        MS [label="Metadata Service\n(files, versions)", fillcolor="#fff2c9"];
        NS [label="Notification Service\n(WebSocket / long-poll)", fillcolor="#fff2c9"];
        SS [label="Sync Service\n(delta detection)", fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        S3   [label="S3 Block Store\n(SHA-256 keyed chunks)", fillcolor="#ead7fb"];
        DB   [label="MySQL/Postgres\n(metadata + blocks index)", fillcolor="#ead7fb"];
        Cache[label="Redis Cache\n(file index, quota, hot blocks)", fillcolor="#ead7fb"];
        KQ   [label="Kafka\n(file.uploaded, file.deleted)", fillcolor="#fbd7c5"];
    }

    Web  -> CDN [label="GET (downloads)", color="#1f8359"];
    Desk -> GW  [label="POST chunks\nGET delta"];
    Mob  -> GW;
    Web  -> GW;

    GW -> BS;
    GW -> MS;
    GW -> SS;
    GW -> NS [label="WS upgrade"];

    BS -> S3   [label="PUT/GET chunk"];
    BS -> DB   [label="dedup lookup"];
    MS -> DB   [label="files / versions"];
    MS -> Cache[label="hot path"];
    SS -> DB   [label="cursor scan"];
    BS -> KQ   [label="file.uploaded"];
    NS -> KQ   [label="subscribe", style=dashed];
}
""",
                },
                {"type": "h3", "text": "Tier Responsibilities"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Client tier:</strong> web (browser), desktop daemon (inotify/FSEvents/USN Journal), mobile (background sync, selective sync)",
                        "<strong>API gateway:</strong> OAuth 2.0, MFA, per-user/IP rate limits, validation, circuit breakers",
                        "<strong>Block Service:</strong> receives chunks, validates SHA-256, dedups against block index, writes new blocks to S3",
                        "<strong>Metadata Service:</strong> file/folder records, permissions, versions; strongly consistent within region",
                        "<strong>Sync Service:</strong> cursor-based delta detection; returns changed file list and block indices",
                        "<strong>Notification Service:</strong> WebSocket push (with long-poll fallback); fans out file.uploaded events",
                        "<strong>S3 Block Store:</strong> 4 MB content-addressed chunks; lifecycle into Glacier for cold blocks",
                        "<strong>MySQL/Postgres:</strong> metadata (files, versions, file_blocks, blocks index)",
                        "<strong>Redis:</strong> path→file_id lookups, quota counters, hot-block cache, session state (~99% hit target)",
                        "<strong>Kafka:</strong> decouples upload from thumbnail generation, dedup verification, audit; topics file.uploaded / file.deleted / file.shared",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Core Design Decisions",
            "subtitle": "Block-level sync, dedup, delta protocol, conflict resolution",
            "blocks": [
                {"type": "h3", "text": "Block-Level Sync vs Full-File Sync"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Chosen:</strong> 4 MB content-addressed blocks; only changed blocks re-uploaded",
                        "<strong>Example:</strong> 1 GB doc, edit one paragraph → upload one 4 MB block, not 1 GB",
                        "<strong>Bandwidth savings:</strong> typically <strong>10–50×</strong> for incremental edits on large files",
                        "<strong>Trade-off:</strong> tracks block versions, manifest reconstruction, dedup logic; worth it for the bandwidth",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why 4 MB?",
                    "body": (
                        "Smaller blocks (e.g. 1 MB) bloat the metadata index — a 1 GB file is "
                        "1,000 manifest entries. Larger blocks (e.g. 64 MB) re-upload too much on "
                        "small edits. <strong>4 MB</strong> is Dropbox's empirical sweet spot: ~250 "
                        "manifest rows per GB, ~6 round-trips for the median 25 MB file at 4 parallel "
                        "uploads, and most office-doc edits land within a single block."
                    ),
                },
                {"type": "h3", "text": "Deduplication Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Content-addressed:</strong> block key = SHA-256(block_data); identical blocks stored once",
                        "<strong>Dedup ratio:</strong> typical <strong>40–50%</strong> (backups, shared documents, common media)",
                        "<strong>Cross-user dedup:</strong> same file uploaded by N users → 1 physical block (privacy-careful: no metadata correlation)",
                        "<strong>Hash collisions:</strong> birthday probability ~10<sup>-29</sup> per 600 PB store — vanishingly small, but verify on read",
                    ],
                },
                {"type": "h3", "text": "Delta Sync Protocol"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Cursor:</strong> client persists a monotonic sequence number (e.g. last-seen version_id)",
                        "<strong>Server query:</strong> returns files modified since cursor (up to 1,000/page)",
                        "<strong>Block-level delta:</strong> for files &gt;10 MB, return only changed block indices, not full contents",
                        "<strong>Latency:</strong> &lt;50 ms metadata round-trip; bandwidth scales with diff, not file size",
                    ],
                },
                {"type": "h3", "text": "Conflict Resolution Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Last-Write-Wins (LWW):</strong> default; newer mtime wins",
                        "<strong>Versioning fallback:</strong> if mtimes equal but content hashes differ, keep server version, rename local as <code>{name}.conflict.{ts}</code>",
                        "<strong>Premium versioning:</strong> all versions retained; restore any version",
                        "<strong>Detection:</strong> server tracks version vector; client reports local mtime + content hash",
                    ],
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Data Models & Schema",
            "subtitle": "Metadata in Postgres, blocks in S3",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Metadata lives in PostgreSQL for ACID guarantees and joins; block data "
                        "lives in S3 keyed by content hash. The <code>file_blocks</code> table is "
                        "the manifest that ties a logical file version to its ordered list of blocks."
                    ),
                },
                {"type": "h3", "text": "PostgreSQL Schema"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE files (\n"
                        "  file_id            UUID PRIMARY KEY,\n"
                        "  owner_id           BIGINT NOT NULL,\n"
                        "  name               VARCHAR(255) NOT NULL,\n"
                        "  path               VARCHAR(2048) NOT NULL,\n"
                        "  mime_type          VARCHAR(100),\n"
                        "  size_bytes         BIGINT,\n"
                        "  created_at         TIMESTAMP,\n"
                        "  modified_at        TIMESTAMP,\n"
                        "  deleted_at         TIMESTAMP,        -- soft delete\n"
                        "  current_version_id UUID,\n"
                        "  UNIQUE (owner_id, path)\n"
                        ");\n\n"
                        "CREATE TABLE blocks (\n"
                        "  block_hash    CHAR(64) PRIMARY KEY,  -- SHA-256 hex\n"
                        "  size_bytes    INT,\n"
                        "  s3_key        VARCHAR(255) NOT NULL,\n"
                        "  created_at    TIMESTAMP,\n"
                        "  last_access_at TIMESTAMP,\n"
                        "  ref_count     INT DEFAULT 1          -- live references for GC\n"
                        ");\n\n"
                        "CREATE TABLE file_blocks (\n"
                        "  file_version_id UUID NOT NULL,\n"
                        "  block_sequence  INT NOT NULL,\n"
                        "  block_hash      CHAR(64) NOT NULL REFERENCES blocks(block_hash),\n"
                        "  PRIMARY KEY (file_version_id, block_sequence)\n"
                        ");\n\n"
                        "CREATE TABLE versions (\n"
                        "  version_id  UUID PRIMARY KEY,\n"
                        "  file_id     UUID NOT NULL REFERENCES files(file_id),\n"
                        "  created_at  TIMESTAMP,\n"
                        "  modified_at TIMESTAMP\n"
                        ");\n\n"
                        "CREATE TABLE user_quota (\n"
                        "  user_id      BIGINT PRIMARY KEY,\n"
                        "  quota_bytes  BIGINT DEFAULT 16106127360, -- 15 GiB\n"
                        "  used_bytes   BIGINT DEFAULT 0\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "Key Design Decisions"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Content addressing (block_hash):</strong> block stored once per unique hash → cross-user dedup for free",
                        "<strong>Version history:</strong> separate <code>versions</code> table; each version points to a manifest in <code>file_blocks</code>",
                        "<strong>Soft delete:</strong> <code>deleted_at</code>; cleanup job hard-deletes after 30-day retention",
                        "<strong>Indexing:</strong> <code>(owner_id, path)</code> unique for path lookups; <code>block_hash</code> PK for dedup probes",
                        "<strong>ref_count on blocks:</strong> drives garbage collection — block is deletable when count drops to 0 for &gt;30 days",
                    ],
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "File Upload Pipeline (Write Path)",
            "subtitle": "Chunked multipart with block dedup and async fan-out",
            "blocks": [
                {
                    "type": "diagram",
                    "caption": "Block-level sync: chunk client-side, hash each chunk, ask the server which hashes it has not seen, upload only the new ones, then commit the manifest.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Chunk    [label="1. Chunk file\n(4 MB blocks)", fillcolor="#dbe6fb"];
    Hash     [label="2. SHA-256\nper block", fillcolor="#dbe6fb"];
    Probe    [label="3. POST /blocks/exists\n[hashes]", fillcolor="#cbeedf"];
    Index    [label="Block Index\n(MySQL)", fillcolor="#ead7fb"];
    Upload   [label="4. PUT only NEW\nchunks (parallel)", fillcolor="#fff2c9"];
    S3       [label="S3\n(content-addressed)", fillcolor="#ead7fb"];
    Manifest [label="5. POST /finalize\n{file_id, [hashes]}", fillcolor="#fff2c9"];
    Meta     [label="Metadata Service\nfile_blocks + versions", fillcolor="#fff2c9"];
    Kafka    [label="Kafka\nfile.uploaded", fillcolor="#fbd7c5"];

    Chunk -> Hash;
    Hash -> Probe;
    Probe -> Index [label="known?"];
    Probe -> Upload [label="missing\nhashes"];
    Upload -> S3 [label="PUT block_hash"];
    Upload -> Manifest;
    Manifest -> Meta [label="commit"];
    Meta -> Index [label="ref_count++"];
    Meta -> Kafka [label="emit event"];
}
""",
                },
                {"type": "h3", "text": "Small File (&lt;5 MB)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Protocol:</strong> single <code>PUT /files/{file_id}</code>",
                        "<strong>Flow:</strong> Client → API Gateway → Block Service → S3 (direct put) → 200 OK",
                        "<strong>Latency:</strong> &lt;100 ms metadata; total time dominated by network upload",
                    ],
                },
                {"type": "h3", "text": "Large File (&gt;5 MB)"},
                {
                    "type": "numbered",
                    "items": [
                        "Client chunks file into <strong>4 MB blocks</strong>",
                        "Client computes <strong>SHA-256</strong> for each block",
                        "Client calls <code>POST /blocks/exists</code> with hash list — server returns the subset it doesn't have",
                        "Client <strong>PUTs only missing chunks</strong>, up to 4 in parallel; ETag per part",
                        "Client calls <code>POST /files/{file_id}/finalize</code> with the ordered hash list (the manifest)",
                        "Server creates a new <code>versions</code> row, writes <code>file_blocks</code>, increments <code>ref_count</code>",
                        "Server publishes <code>file.uploaded</code> to Kafka → notification fan-out",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Round-trip math",
                    "body": (
                        "Median S3 PUT round-trip from a same-region service is ~30–60 ms (TLS + "
                        "request + ack). Cross-region PUT can be 200–400 ms. With 4 parallel uploads "
                        "a 25 MB file (≈7 blocks) needs ~2 round-trips of work — well under the &lt;500 ms "
                        "metadata target. The dedup probe avoids the round-trip entirely for unchanged blocks."
                    ),
                },
                {"type": "h3", "text": "Async Fan-out"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Block Processor:</strong> consumes <code>file.uploaded</code>, verifies SHA-256, optionally compresses text blocks, runs orphan-block GC",
                        "<strong>Thumbnail Generator:</strong> images/PDFs/Office docs → previews into a separate S3 bucket",
                        "<strong>Notification Service:</strong> pushes change to other devices via WebSocket so they wake and fetch the delta",
                    ],
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Storage Architecture & Deduplication",
            "subtitle": "S3, content addressing, and garbage collection",
            "blocks": [
                {"type": "h3", "text": "S3 Layout"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Key:</strong> <code>s3://blocks-prod/{hash[:2]}/{hash[2:]}</code> — 256-way prefix sharding for hot-partition spreading",
                        "<strong>Block size:</strong> 4 MB default; 100 KB for thumbnails; up to 10 MB for video",
                        "<strong>Storage classes:</strong> S3 Standard for hot (&lt;7 days); Intelligent-Tiering / Glacier for cold",
                        "<strong>Encryption:</strong> SSE-S3 server-side; optional client-side (zero-knowledge) for paid tiers",
                        "<strong>Versioning:</strong> S3 versioning <em>off</em> — version semantics live in our metadata DB",
                    ],
                },
                {"type": "h3", "text": "Deduplication Mechanics"},
                {
                    "type": "bullets",
                    "items": [
                        "On upload, Block Service probes <code>blocks</code> table by SHA-256 hash",
                        "Hit → bump <code>ref_count</code>, link new <code>file_blocks</code> row, no S3 write",
                        "Miss → insert <code>blocks</code> row, PUT to S3 keyed by hash",
                        "<strong>Dedup ratio:</strong> 40–50% measured; biggest wins are shared docs, OS backup files, and common media",
                        "<strong>Privacy:</strong> dedup index is keyed by hash only; we never reveal who else has the block (counter increments are not logged per-user)",
                    ],
                },
                {"type": "h3", "text": "Garbage Collection"},
                {
                    "type": "bullets",
                    "items": [
                        "Periodic job sums <code>ref_count</code> across all <code>file_blocks</code> referencing each hash",
                        "If 0 for &gt;30 days, delete S3 object and remove the <code>blocks</code> row",
                        "Grace window prevents deleting a block whose only reference was a file mid-restore",
                    ],
                },
                {"type": "h3", "text": "Quota & Billing"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Per-user quota:</strong> Redis (hot) + Postgres (durable); enforced before upload",
                        "<strong>Billing model:</strong> charge for <em>logical</em> bytes (user-visible), not physical — keeps the dedup win on the provider side and gives users predictable bills",
                        # ERRATUM 3 applied: corrected S3 cost
                        "<strong>Effective cost:</strong> S3 Standard ~<strong>2.3¢/GB-mo</strong>, Glacier ~<strong>0.4¢/GB-mo</strong>; after 40% dedup, blended ~1.4¢/GB-mo of physical storage",
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Sync Protocol & Delta Detection",
            "subtitle": "Cursor-based pull plus WebSocket push",
            "blocks": [
                {"type": "h3", "text": "Client-Side Sync Daemon"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Polling interval:</strong> 30 sec foreground / 5 min background",
                        "<strong>Local change detection:</strong> inotify (Linux), FSEvents (macOS), USN Journal (Windows)",
                        "<strong>State store:</strong> <code>.sync_state.db</code> (SQLite) — file metadata at last sync",
                        "<strong>Offline:</strong> queue local changes; reconcile on reconnect; flag conflicts",
                    ],
                },
                {"type": "h3", "text": "Server Delta Detection"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Cursor:</strong> opaque token, internally a <code>(version_id, modified_at)</code> tuple",
                        "<strong>Query:</strong> <code>SELECT … FROM files WHERE owner_id = ? AND modified_at &gt; cursor ORDER BY modified_at LIMIT 1000</code>",
                        "<strong>Response:</strong> changed file list with <code>file_id</code>, <code>name</code>, <code>size</code>, <code>mtime</code>, <code>current_version_id</code>, deleted flag",
                        "<strong>Block-level delta:</strong> for files &gt;10 MB, also return changed block indices",
                        "<strong>Latency target:</strong> &lt;50 ms server query + network round-trip",
                    ],
                },
                {"type": "h3", "text": "Notification Service"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>WebSocket:</strong> daemon holds a persistent connection; server pushes on file change",
                        "<strong>Fan-out:</strong> Notification Service consumes <code>file.uploaded</code> from Kafka, looks up watching clients, pushes",
                        "<strong>Fallback:</strong> if WebSocket fails, client falls back to HTTP long-polling (30 sec hold)",
                        "<strong>Push latency:</strong> &lt;1 sec end-to-end from upload-finalize to other-device notification",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Consistent hashing for the WebSocket fleet",
                    "body": (
                        "Notification Service nodes hold millions of WebSocket connections. Use "
                        "<strong>consistent hashing</strong> on <code>user_id</code> to route a user's "
                        "devices to the same node, so a fan-out only sends one cross-node hop. Adding "
                        "or draining a node moves only ~1/N of users — critical when each rebalance "
                        "tears down millions of connections."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "File Download & Reconstruction",
            "subtitle": "Manifest → parallel block fetch → stream",
            "blocks": [
                {"type": "h3", "text": "Small Files (single block)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Protocol:</strong> <code>GET /files/{file_id}</code>",
                        "<strong>Flow:</strong> Block Service fetches the single block from S3, streams to client",
                        "<strong>Caching:</strong> Redis caches frequently accessed blocks; ~99% hit rate target on hot blocks",
                    ],
                },
                {"type": "h3", "text": "Large Files (multi-block)"},
                {
                    "type": "numbered",
                    "items": [
                        "Block Service queries <code>file_blocks</code> for the file's current version",
                        "Block Service issues 4–8 parallel S3 GETs against the manifest",
                        "As blocks arrive, stream to client immediately (don't wait for all blocks)",
                        "Supports HTTP <code>Range</code> header for resumable downloads",
                        "Latency: &lt;100 ms metadata; perceived TTFB ≈ first block round-trip (~30–60 ms in-region)",
                    ],
                },
                {"type": "h3", "text": "Selective and Smart Sync"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Selective sync:</strong> user picks folders to materialise on disk; others stay cloud-only",
                        "<strong>Smart sync:</strong> metadata is always synced; file content fetches on access (placeholder file → real file on first read)",
                        "<strong>Conflict guard:</strong> if local file changed mid-download, abort, requeue after conflict resolution",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Conflict Resolution",
            "subtitle": "Concurrent edits across devices",
            "blocks": [
                {"type": "h3", "text": "Detection"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Trigger:</strong> on upload-finalize, server compares client's reported parent version with <code>current_version_id</code>",
                        "<strong>Stale parent:</strong> client edited an old version → conflict",
                        "<strong>Equal mtime, different hash:</strong> two devices saved at the same second with different content → concurrent edit",
                        "<strong>Metadata conflicts:</strong> both sides renamed the same file → resolve by path lineage",
                    ],
                },
                {"type": "h3", "text": "Last-Write-Wins (LWW)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Rule:</strong> compare modification timestamps; newer wins",
                        "<strong>Pros:</strong> simple, deterministic, no UX surprises in the common case",
                        "<strong>Cons:</strong> silent data loss if both versions had real content; unsuitable for collaborative docs",
                    ],
                },
                {"type": "h3", "text": "Versioning Fallback"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Action:</strong> keep server version as authoritative; rename local copy as <code>{name}.conflict.{ts}.{ext}</code>",
                        "<strong>Example:</strong> <code>Plan.docx</code> server v5 vs client v4 (modified) → save <code>Plan.conflict.1715000000.docx</code>, pull server v5",
                        "<strong>User action:</strong> manually merge; delete the conflict copy when done",
                        "<strong>Pros:</strong> no data loss; <strong>Cons:</strong> manual merge effort, especially on shared folders",
                    ],
                },
                {"type": "h3", "text": "When to Use OT / CRDT"},
                {
                    "type": "bullets",
                    "items": [
                        "Real-time collaborative editing (Google Docs / Sheets) uses OT or CRDT, not file sync",
                        "For binary files (images, ZIPs, videos) text-merge approaches don't apply",
                        "Dropbox Smart Sync / Google Drive integrate with the editor app's API for live collaboration",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Pragmatic default",
                    "body": (
                        "Ship LWW with the conflict-rename fallback. It is &lt;200 lines of code, "
                        "covers ~99% of real-world conflicts (different devices, not different humans "
                        "in the same second), and crucially has no data loss path even when it's wrong "
                        "— the loser's content lands on disk as a renamed file."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Failure Modes & Recovery",
            "subtitle": "What can go wrong, how we detect and recover",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Detection", "Recovery"],
                    "rows": [
                        ["S3 outage",
                         "Upload returns 5xx; download falls back to cache",
                         "Exponential backoff; cross-region S3 fallback bucket; retry queue"],
                        ["Metadata DB unavailable",
                         "Connection timeout; circuit breaker opens",
                         "Read replicas serve reads; queue writes locally; reconcile on recovery"],
                        ["Upload interrupted",
                         "Client detects TCP reset / 0 bytes ack",
                         "Resume from last confirmed block via ETag; manifest only commits when all blocks present"],
                        ["Sync daemon crash",
                         "No heartbeat; pending push notifications undelivered",
                         "Daemon auto-restarts; on launch performs full delta sync from cursor"],
                        ["Block hash collision",
                         "Two blocks with same hash but byte-different content (~10<sup>-29</sup> probability)",
                         "Cryptographic re-validation on read; store as separate entries with disambiguating suffix"],
                        ["Quota exceeded",
                         "User hits limit; next upload rejected",
                         "Soft enforcement: block uploads, prompt to upgrade or delete; auto-delete oldest versions if user opts in"],
                        ["Concurrent delete + upload",
                         "File deleted on server while client uploading",
                         "Accept upload as a new file version; on next sync, client surfaces the un-delete"],
                        ["Shared folder permission revoked",
                         "Daemon gets 403 on next sync",
                         "Remove local copy; write audit-log entry; notify user"],
                        ["Notification Service node loss",
                         "WebSockets drop; clients get connection-closed",
                         "Clients reconnect with consistent-hash retry; long-poll fallback bridges the gap"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful degradation order",
                    "body": (
                        "When something is on fire, prioritise <strong>downloads</strong> (users "
                        "must read their files), then <strong>uploads</strong>, then "
                        "<strong>sync notifications</strong>, then <strong>thumbnails / "
                        "audit</strong>. Never block the read path on a non-essential subsystem."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Trade-offs & Alternatives",
            "subtitle": "Decisions and rationale",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Decision", "Alternative", "Why Chosen"],
                    "rows": [
                        ["4 MB block size", "1 MB (more granular) or 64 MB (fewer manifests)",
                         "Balances metadata overhead against re-upload cost; sweet spot for typical edit patterns"],
                        ["SHA-256 hash", "MD5 (faster) or BLAKE3",
                         "Collision-resistant for adversarial inputs; CPU cost negligible with HW acceleration; widely standardised"],
                        ["LWW conflict resolution", "Always-version, or CRDT/OT",
                         "Simplest UX for the 99% case; rename-on-conflict prevents data loss; CRDTs aren't useful for binary files"],
                        ["PostgreSQL metadata", "DynamoDB or Cassandra",
                         "ACID for the file/version invariants; joins useful for sharing/quota queries; sharded by user_id when needed"],
                        # ERRATUM 3 applied: corrected S3 cost figures
                        ["S3 storage", "Custom object store",
                         "Cost: S3 Standard ~2.3¢/GB-mo (Glacier ~0.4¢) vs custom ~1¢/GB-mo; custom requires major ops investment"],
                        ["Eventual consistency", "Strong consistency globally",
                         "Availability and latency dominate; 5-minute sync window is acceptable; metadata is strongly consistent within a region"],
                        ["Kafka async fan-out", "Synchronous fan-out",
                         "Decouples upload from thumbnails / dedup verification / audit; improves perceived upload latency"],
                        ["WebSocket + long-poll", "Polling only (5-min interval)",
                         "Real-time UX matters; WebSocket is cheap once you have it; long-poll is the fallback when intermediaries break WS"],
                        ["Client-side chunking", "Server-side chunking",
                         "Saves the entire file upload before dedup probe; server only sees blocks it doesn't already have"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Headline tension",
                    "body": (
                        "The architecture trades <strong>complexity</strong> (block manifests, "
                        "dedup index, version vectors, push fabric) for <strong>bandwidth and "
                        "storage cost</strong>. At 1 EB logical storage and 100 Gbps peak upload, "
                        "even a 40% reduction is worth a lot of engineering. At 10 GB total it would not be."
                    ),
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Interview Playbook",
            "subtitle": "How to present this design (45 minutes)",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "A 45-minute interview pacing for Drive/Dropbox. Lead with the bandwidth "
                        "story (block-level sync), defend the dedup numbers, and pick one or two "
                        "deep dives — don't try to cover everything."
                    ),
                },
                {"type": "h3", "text": "Opening (5 min): Clarify & Scope"},
                {
                    "type": "bullets",
                    "items": [
                        "Ask 2–3 questions: sync + storage? multi-device? sharing? version history?",
                        "Confirm scale: <strong>1B users, ~1 EB logical, 100K concurrent syncs</strong>",
                        "Set scope: focus on core sync + upload/download; mention but don't deep-dive sharing/collab",
                    ],
                },
                {"type": "h3", "text": "Capacity (3 min)"},
                {
                    "type": "bullets",
                    "items": [
                        "Storage: 500M MAU × 2 GB ≈ <strong>1 EB logical</strong>; 40% dedup → <strong>~600 PB physical</strong>",
                        "Sync: 100K concurrent × 1 query/5 min ≈ ~333 RPS baseline",
                        "Bandwidth: 100K concurrent × 1 Mbps = <strong>100 Gbps</strong> peak (Gbps, not Tbps!)",
                        "Block-level delta: <strong>10–50× bandwidth savings</strong> vs full-file sync",
                    ],
                },
                {"type": "h3", "text": "Architecture (10 min)"},
                {
                    "type": "bullets",
                    "items": [
                        "Client tier (web, daemon, mobile) → API gateway → Block / Metadata / Sync / Notification services",
                        "Storage: S3 content-addressed blocks + Postgres metadata + Redis hot path",
                        "Async: Kafka topics for fan-out (thumbnail, dedup verify, notification)",
                        "Draw the diagram — interviewers care that you can decompose into services",
                    ],
                },
                {"type": "h3", "text": "Deep Dives (20 min): Pick 2"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Upload &amp; dedup:</strong> chunk → hash → probe → upload missing → finalize manifest",
                        "<strong>Delta sync:</strong> cursor-based query, block-level diffs, WebSocket push",
                        "<strong>Conflict resolution:</strong> LWW + rename-fallback; when CRDT/OT applies",
                        "<strong>Storage architecture:</strong> 4 MB blocks, SHA-256 keys, S3 prefix sharding, GC",
                        "<strong>Failure recovery:</strong> resumable uploads, metadata replicas, partition tolerance",
                    ],
                },
                {"type": "h3", "text": "Wrap-up (5 min): Trade-offs"},
                {
                    "type": "bullets",
                    "items": [
                        "Block-level sync vs full-file: complexity worth it for bandwidth at 1 EB scale",
                        "Eventual consistency vs strong: acceptable for file sync; metadata strong within region",
                        "Custom store vs S3: S3 wins on ops cost; ~2.3¢/GB-mo Standard, 0.4¢ Glacier",
                        "Closing line: <em>\"Block-level dedup + delta sync are the differentiators that make this economical at exabyte scale.\"</em>",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Numbers to memorise",
                    "body": (
                        "1 B users / 500M MAU &nbsp;·&nbsp; 2 GB blended avg &nbsp;·&nbsp; "
                        "1 EB logical / ~600 PB physical &nbsp;·&nbsp; 4 MB blocks / SHA-256 &nbsp;·&nbsp; "
                        "40–50% dedup &nbsp;·&nbsp; 100K concurrent syncs &nbsp;·&nbsp; "
                        "100 Gbps peak upload &nbsp;·&nbsp; ~50 ms delta query &nbsp;·&nbsp; "
                        "S3 ~2.3¢/GB-mo Standard, ~0.4¢ Glacier &nbsp;·&nbsp; 99.99% availability."
                    ),
                },
                {"type": "h3", "text": "What Interviewers Probe"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Block-level thinking:</strong> Why 4 MB? How is dedup verified? Reconstruction overhead?",
                        "<strong>Sync protocol:</strong> How are changes detected? Offline devices? Conflicts?",
                        "<strong>Consistency model:</strong> Why eventual? Edge cases for concurrent edits?",
                        "<strong>Scale intuition:</strong> Defend every capacity number; unit-check bandwidth (Gbps vs Tbps)",
                        "<strong>Trade-offs:</strong> Why not S3 versioning? Why custom daemon? Why 4 MB not 1 MB?",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Five takeaways",
                    "body": (
                        "<strong>(1)</strong> Block-level sync is the differentiator — small edits "
                        "trigger 4 MB transfers, not GB transfers, for ~10–50× bandwidth savings. "
                        "<strong>(2)</strong> Content-addressed storage gives 40–50% dedup nearly for free. "
                        "<strong>(3)</strong> Cursor-based delta sync + WebSocket push delivers &lt;1 s "
                        "cross-device propagation. <strong>(4)</strong> LWW with rename-fallback handles "
                        "conflicts pragmatically without data loss. <strong>(5)</strong> Kafka decouples "
                        "the user-facing upload latency from async work (dedup verify, thumbnails, audit)."
                    ),
                },
            ],
        },
    ],
}
