"""Source for `25 - Google Image Search.pdf` (reverse image search system)."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Google Image (Reverse Image Search)",
    "subtitle": "given an image, return visually similar / duplicate images from ~100B web images",
    "read_time": "~ 45 minute read",
    "short_title": "Design Google Image Search",
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
                        "Design a <strong>reverse image search</strong> system like "
                        "<strong>Google Images</strong> or <strong>TinEye</strong>. Given a query "
                        "image (uploaded bytes or URL), return visually similar and near-duplicate "
                        "images from a corpus of <strong>~100 billion</strong> web images, "
                        "ranked by similarity, with sub-200&nbsp;ms tail latency."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Corpus size?", "~100 billion images crawled from the web"],
                        ["Query type?", "Image upload, image URL, or drag-drop in browser"],
                        ["Result type?", "Ranked list of visually similar / near-duplicate images"],
                        ["Latency target?", "p50 &lt; 80 ms, p99 &lt; 200 ms end-to-end"],
                        ["Query volume?", "~1B queries/day (~12K QPS sustained, ~50K peak)"],
                        ["Crawl rate?", "~500M new images ingested per day"],
                        ["Recall vs precision?", "Top-100 recall &gt; 0.9 vs brute-force ground truth"],
                        ["Languages / OCR?", "Out of scope: text-in-image search handled separately"],
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
                        ["Search by image", "POST /search with image bytes or URL → ranked results"],
                        ["Near-duplicate", "Find exact / cropped / rescaled copies (perceptual hash)"],
                        ["Semantic similarity", "Find visually-similar (same object class, scene, style)"],
                        ["Result page", "Thumbnail, source URL, page title, dimensions"],
                        ["Crawl & ingest", "Continuously index new images discovered by web crawler"],
                        ["Re-index", "Re-embed corpus when a better model ships (~quarterly)"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Scale", "100B images indexed; 1B queries/day"],
                        ["Latency", "p99 query latency &lt; 200 ms"],
                        ["Recall", "Top-100 recall &gt; 0.9 (vs exact brute force)"],
                        ["Availability", "99.95%; degrade with fewer shards rather than fail"],
                        ["Freshness", "New crawled image searchable within ~1 hour"],
                        ["Durability", "Index sharded + 3-way replicated; rebuildable from raw images"],
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
                {"type": "h3", "text": "Traffic"},
                {
                    "type": "bullets",
                    "items": [
                        "Queries/day: <strong>1 billion</strong> → 1e9 / 86,400 ≈ <strong>11.6K QPS</strong> sustained",
                        "Peak factor 4× → <strong>~46K QPS peak</strong>",
                        "Crawl ingestion: <strong>500M images/day</strong> → ~5,800 inserts/sec",
                        "Ratio: query : insert ≈ 2 : 1 (read-mostly but ingest is non-trivial)",
                    ],
                },
                {"type": "h3", "text": "Per-Image Footprint"},
                {
                    "type": "bullets",
                    "items": [
                        "Perceptual hash (pHash + dHash + wHash): <strong>~24 bytes</strong> total",
                        "Deep embedding (512-D float32): 512 × 4 = <strong>2,048 bytes (2 KB)</strong>",
                        "PQ-compressed embedding (64 sub-vectors × 1 byte each): <strong>64 bytes</strong>",
                        "Metadata row (URL, title, dims, crawl time): <strong>~512 bytes</strong>",
                        "Thumbnail (128×128 JPEG): <strong>~8 KB</strong>",
                    ],
                },
                {"type": "h3", "text": "Storage (100B images)"},
                {
                    "type": "bullets",
                    "items": [
                        "Raw embeddings (2 KB): 100B × 2 KB = <strong>200 TB</strong> (RAM-prohibitive)",
                        "PQ-compressed (64 B): 100B × 64 B = <strong>6.4 TB</strong> (fits in cluster RAM)",
                        "Perceptual hash table: 100B × 24 B = <strong>2.4 TB</strong>",
                        "Metadata in Bigtable: 100B × 512 B = <strong>~51 TB</strong>",
                        "Thumbnails in object store: 100B × 8 KB = <strong>~800 TB</strong>",
                    ],
                },
                {"type": "h3", "text": "Sharding"},
                {
                    "type": "bullets",
                    "items": [
                        "Shard at ~<strong>100M vectors per shard</strong> → <strong>1,000 shards</strong>",
                        "Per-shard PQ index: 100M × 64 B = <strong>6.4 GB</strong> (fits in RAM on a 32 GB node)",
                        "3× replication for HA → <strong>~3,000 index replicas</strong>",
                        "Coordinator fan-out: 1,000 shards behind a single query coordinator",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "<strong>100B</strong> images indexed &nbsp;·&nbsp; "
                        "<strong>1B</strong> queries/day (~46K QPS peak) &nbsp;·&nbsp; "
                        "<strong>2 KB</strong> raw → <strong>64 B</strong> PQ embedding &nbsp;·&nbsp; "
                        "<strong>1,000 shards</strong> × 6.4 GB &nbsp;·&nbsp; "
                        "p99 &lt; <strong>200 ms</strong>."
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level Architecture",
            "subtitle": "Query and ingestion paths",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Two independent pipelines share one vector index. The <strong>query path</strong> "
                        "accepts an image, extracts a feature vector on a GPU, fans out to all shards "
                        "of the ANN index, merges top-K, and re-ranks before returning the result page. "
                        "The <strong>ingestion path</strong> consumes URLs from the web crawler, "
                        "deduplicates by perceptual hash, embeds new images, and writes to the vector DB."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Query path (top): image upload → GPU feature extractor → ANN coordinator fan-out → top-K merge → re-rank. Ingestion path (bottom): crawler → pHash dedup → feature extractor → vector DB write.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_query {
        label="Query Path"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        Q  [label="User\n(upload / URL)", fillcolor="#dbe6fb"];
        FE [label="Feature Extractor\n(GPU, ~10 ms)", fillcolor="#cbeedf"];
        QC [label="ANN Query\nCoordinator",          fillcolor="#cbeedf"];
        S1 [label="Shard 1\n(IVF+PQ)",  fillcolor="#fff2c9"];
        S2 [label="Shard 2\n(IVF+PQ)",  fillcolor="#fff2c9"];
        SN [label="... Shard N\n(IVF+PQ)", fillcolor="#fff2c9"];
        MR [label="Top-K Merge\n+ Re-rank", fillcolor="#cbeedf"];
        R  [label="Result Page",     fillcolor="#dbe6fb"];
    }
    subgraph cluster_ing {
        label="Ingestion Path"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        CR [label="Web Crawler",       fillcolor="#fbd7c5"];
        PH [label="pHash Dedup\n(Bigtable lookup)", fillcolor="#fbd7c5"];
        FE2[label="Feature Extractor\n(GPU batch)",  fillcolor="#fbd7c5"];
        VW [label="Vector DB\nWriter", fillcolor="#fbd7c5"];
    }
    subgraph cluster_data {
        label="Storage"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        BT [label="Bigtable\n(metadata + pHash)", fillcolor="#ead7fb"];
        OS [label="Object Store\n(thumbnails)",  fillcolor="#ead7fb"];
        VI [label="Vector Index\n(FAISS / ScaNN)", fillcolor="#ead7fb"];
    }

    Q  -> FE -> QC;
    QC -> S1 [label="fan-out"];
    QC -> S2;
    QC -> SN;
    S1 -> MR;
    S2 -> MR;
    SN -> MR;
    MR -> R;
    MR -> BT [label="metadata\nlookup", style=dashed];
    MR -> OS [label="thumbnail", style=dashed];

    CR -> PH -> FE2 -> VW;
    PH -> BT [label="phash check", style=dashed];
    VW -> VI;
    VW -> BT [label="metadata", style=dashed];
    VW -> OS [label="thumbnail", style=dashed];
    S1 -> VI [style=invis];
}
""",
                },
                {"type": "h3", "text": "Component Highlights"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Feature Extractor:</strong> GPU service running CNN/ViT (e.g., EfficientNet, CLIP) → 512-D float32",
                        "<strong>ANN Coordinator:</strong> stateless; broadcasts query vector to N shards, gathers top-K each",
                        "<strong>Shard:</strong> IVF+PQ FAISS index in RAM; ~100M vectors per shard",
                        "<strong>Re-rank:</strong> exact L2 / cosine on top-1000 with full-precision (or PQ-decoded) vectors",
                        "<strong>Bigtable:</strong> row key = image_id; columns = url, phash, embedding_offset, metadata",
                        "<strong>Object store:</strong> thumbnails for the result page (GCS / S3 with CDN)",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Two Complementary Signals",
            "subtitle": "Perceptual hashes vs deep embeddings",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "A reverse image search needs <strong>two distinct similarity notions</strong>: "
                        "exact / near-duplicate detection (the same JPEG re-saved, cropped, or "
                        "watermarked) and semantic similarity (different photos of the same object). "
                        "Perceptual hashes serve the first cheaply; deep embeddings serve the second."
                    ),
                },
                {"type": "h3", "text": "Perceptual Hashes"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>pHash:</strong> 32×32 grayscale → DCT → low-frequency 8×8 → median bit → 64-bit hash",
                        "<strong>dHash:</strong> 9×8 grayscale → adjacent-pixel difference → 64-bit hash",
                        "<strong>wHash:</strong> wavelet-based; robust to compression and resize",
                        "<strong>Distance:</strong> Hamming distance &lt; 5 ⇒ near-duplicate (very high precision)",
                        "<strong>Cost:</strong> ~64 bits per image; fits in Bigtable column; lookups in microseconds",
                    ],
                },
                {"type": "h3", "text": "Deep Embeddings"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Backbone:</strong> CNN (EfficientNet, ResNet) or ViT (CLIP, DINO) penultimate layer",
                        "<strong>Output:</strong> 512-D float32 vector (2 KB raw); L2-normalized for cosine",
                        "<strong>Distance:</strong> cosine similarity &gt; 0.85 ⇒ visually similar",
                        "<strong>Captures:</strong> object class, scene, color palette, composition",
                        "<strong>Cost:</strong> GPU forward pass ~10 ms (batch 32), 2 KB / image at full precision",
                    ],
                },
                {"type": "h3", "text": "Comparison"},
                {
                    "type": "table",
                    "headers": ["Aspect", "Perceptual Hash", "Deep Embedding"],
                    "rows": [
                        ["Captures", "Pixel-level near-duplicates", "Semantic / visual similarity"],
                        ["Size", "~8–24 bytes", "2 KB raw / 64 B PQ"],
                        ["Compute", "~1 ms CPU", "~10 ms GPU"],
                        ["Distance", "Hamming (XOR + popcount)", "Cosine / L2"],
                        ["Failure mode", "Misses recolored / re-shot images", "Returns false positives at boundary"],
                        ["Use case", "Dedup, copyright, exact-match", "Visual search, recommendations"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why Both",
                    "body": (
                        "On query, run pHash lookup first (cheap; resolves duplicates with high "
                        "precision). If the user wanted near-duplicates they get them in &lt; 10 ms. "
                        "In parallel run the deep-embedding ANN search to surface semantically "
                        "similar images. Merge both lists with pHash hits ranked first."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "ANN Search at 100B Scale",
            "subtitle": "IVF, PQ, HNSW",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Brute-force scanning 100 billion 2 KB vectors per query would require "
                        "200 TB of bandwidth per query — impossible. We need <strong>approximate "
                        "nearest neighbour (ANN)</strong> structures that prune the candidate set "
                        "dramatically while preserving recall."
                    ),
                },
                {"type": "h3", "text": "Inverted File (IVF) Index"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Coarse quantizer:</strong> k-means with K centroids (e.g., K = 65,536) trained on a sample",
                        "<strong>Posting list:</strong> each centroid owns the IDs of vectors closest to it",
                        "<strong>Query:</strong> compare query to all K centroids; visit nprobe (e.g., 32) closest lists",
                        "<strong>Speedup:</strong> visits ~nprobe/K of the corpus → 32/65,536 ≈ 0.05% of vectors",
                    ],
                },
                {"type": "h3", "text": "Product Quantization (PQ)"},
                {
                    "type": "bullets",
                    "items": [
                        "Split 512-D vector into <strong>M = 64</strong> sub-vectors of 8 dims each",
                        "Train 256 centroids per sub-space → each sub-vector = 1 byte (256 = 2^8)",
                        "Storage: 64 bytes per vector instead of 2,048 bytes (<strong>32× compression</strong>)",
                        "Distance: precompute query-to-centroid table, look up + sum for each candidate",
                        "Loss: ~3–5 percentage points of recall@100 vs full-precision vectors",
                    ],
                },
                {"type": "h3", "text": "HNSW (Hierarchical Navigable Small World)"},
                {
                    "type": "bullets",
                    "items": [
                        "Multi-layer graph; each node has ~M neighbours (M=16–48)",
                        "Search: greedy descent from top layer to bottom; logarithmic candidates touched",
                        "<strong>Faster than IVF per shard</strong> (~5×) but uses more RAM (~200 B/vector)",
                        "Best for shards ≤ 50M vectors; combine with PQ as 'HNSW-PQ' if RAM-bound",
                    ],
                },
                {"type": "h3", "text": "Comparison: IVF-PQ vs HNSW vs HNSW-PQ"},
                {
                    "type": "table",
                    "headers": ["Approach", "Memory / vec", "Latency", "Recall@100"],
                    "rows": [
                        ["Brute force", "2,048 B", "minutes", "1.00 (ground truth)"],
                        ["IVF-PQ (M=64)", "~80 B", "5–10 ms / shard", "0.90–0.93"],
                        ["HNSW (M=32)", "~200 B + 2,048 B", "1–3 ms / shard", "0.97"],
                        ["HNSW-PQ", "~200 B + 80 B", "2–4 ms / shard", "0.93"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Production Choice",
                    "body": (
                        "Use <strong>IVF-PQ</strong> for the 100B-scale main index — only this "
                        "fits in RAM cluster-wide (6.4 TB total). Reserve <strong>HNSW</strong> "
                        "for smaller hot indexes (e.g., last-30-days fresh tier or VIP customer "
                        "datasets) where its lower latency and higher recall justify the RAM cost."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Index Sharding & Replication",
            "subtitle": "1,000 shards × 100M vectors",
            "blocks": [
                {"type": "h3", "text": "Sharding Scheme"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Shard key:</strong> hash(image_id) mod 1,000 (random distribution)",
                        "<strong>Why random:</strong> any neighbour can live on any shard → must fan-out to all",
                        "<strong>Why not by feature:</strong> learned-shard routing (SPANN, DiskANN) is complex; random is simpler at this scale",
                        "<strong>Per-shard footprint:</strong> 100M × 64 B = 6.4 GB (fits in 32 GB RAM with overhead)",
                        "<strong>Replicas:</strong> 3× per shard for HA + load balancing",
                    ],
                },
                {
                    "type": "diagram",
                    "caption": "Vector index layout per shard: coarse-cluster centroid table → posting list of image IDs → PQ-compressed vectors stored sequentially.",
                    "dot": r"""
digraph V {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_q {
        label="Query"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        QV [label="Query Vector\n(512-D float32)", fillcolor="#dbe6fb"];
    }
    subgraph cluster_ivf {
        label="Coarse Quantizer (IVF)"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        CT [label="Centroid Table\n(K=65,536)", fillcolor="#fff2c9"];
        L1 [label="Posting List\ncentroid c1\n[id, id, id, ...]", fillcolor="#fff2c9"];
        L2 [label="Posting List\ncentroid c2\n[id, id, id, ...]", fillcolor="#fff2c9"];
        Lk [label="... centroid cK", fillcolor="#fff2c9"];
    }
    subgraph cluster_pq {
        label="PQ-Compressed Vectors"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        PQ [label="64-byte codes\n(M=64 sub-spaces × 8-bit each)", fillcolor="#ead7fb"];
        DT [label="Distance Table\n(query precomputed)", fillcolor="#ead7fb"];
    }

    QV -> CT [label="find nprobe=32\nclosest centroids"];
    CT -> L1 [label="visit", style=dashed];
    CT -> L2 [label="visit", style=dashed];
    CT -> Lk [style=dotted];
    L1 -> PQ [label="lookup codes"];
    L2 -> PQ;
    QV -> DT [label="precompute"];
    DT -> PQ [label="sum 64 partial\ndistances per candidate"];
}
""",
                },
                {"type": "h3", "text": "Replication & Placement"},
                {
                    "type": "bullets",
                    "items": [
                        "Each shard placed in 3 different racks (and 2 regions for top-tier indexes)",
                        "Coordinator picks healthiest replica per shard at query time (load + latency)",
                        "Hedged requests: if a replica's response &gt; p95, fire a second to another replica",
                        "Failed shard: degrade to N-1 = 999 shards rather than fail the query (see §13)",
                    ],
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Query Path Deep Dive",
            "subtitle": "From upload to ranked results",
            "blocks": [
                {"type": "h3", "text": "End-to-End Steps"},
                {
                    "type": "numbered",
                    "items": [
                        "Client uploads image (or URL): <code>POST /search</code>; max 10 MB; resize server-side to 224×224",
                        "<strong>pHash compute</strong> (CPU, ~1 ms) → look up in Bigtable; if Hamming &lt; 5, mark as duplicate hit",
                        "<strong>Feature extraction</strong> (GPU, ~10 ms): batch with other in-flight queries; produce 512-D vector",
                        "<strong>Coordinator</strong> broadcasts vector to all 1,000 shards (one healthy replica each)",
                        "<strong>Each shard</strong> runs IVF-PQ search with nprobe=32, returns top-100 (id, approx_distance)",
                        "<strong>Merge:</strong> coordinator collects 1,000 × 100 = 100K candidates; heap-merge to top-1,000",
                        "<strong>Re-rank:</strong> fetch full-precision (or PQ-decoded) vectors for the 1,000; compute exact cosine; keep top-100",
                        "<strong>Hydrate:</strong> Bigtable scan for image_id → metadata; object store for thumbnails (parallel)",
                        "Return ranked JSON with phash hits first, then semantic neighbours",
                    ],
                },
                {"type": "h3", "text": "Latency Budget (p99)"},
                {
                    "type": "table",
                    "headers": ["Stage", "Budget", "Notes"],
                    "rows": [
                        ["Network in / decode / resize", "20 ms", "TCP + JPEG decode"],
                        ["pHash compute + Bigtable", "5 ms", "CPU + cache lookup"],
                        ["GPU feature extract", "15 ms", "Batched dynamically"],
                        ["Shard fan-out + slowest", "60 ms", "1,000 RPCs in parallel; tail-tolerant"],
                        ["Top-K merge", "10 ms", "Heap of 100K candidates"],
                        ["Re-rank exact distances", "30 ms", "1,000 vectors from cache / shard"],
                        ["Metadata + thumbnail hydrate", "40 ms", "Parallel Bigtable + object store"],
                        ["Response serialization", "20 ms", "JSON + network out"],
                        ["<strong>Total</strong>", "<strong>~200 ms</strong>", "Within p99 SLA"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Tail Latency",
                    "body": (
                        "With 1,000 shard RPCs, the slowest one dominates. Use <strong>request "
                        "hedging</strong> (fire to a second replica if the first hasn't replied "
                        "by p95) and a <strong>backup-on-timeout</strong> policy. This keeps the "
                        "fan-out tail near p95 of a single shard, not p99.9 of 1 in 1,000."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Storage & Schema",
            "subtitle": "Bigtable, vector DB, object store",
            "blocks": [
                {"type": "h3", "text": "Image Metadata (Bigtable)"},
                {
                    "type": "code",
                    "text": (
                        "# Bigtable: image_metadata\n"
                        "# Row key: image_id (16-byte SHA-256 prefix of canonical URL)\n"
                        "#\n"
                        "# Column family 'm' (metadata)\n"
                        "#   m:url           STRING       canonical source URL\n"
                        "#   m:page_url      STRING       page that hosted the image\n"
                        "#   m:title         STRING       page title / alt text\n"
                        "#   m:width         INT64        pixels\n"
                        "#   m:height        INT64        pixels\n"
                        "#   m:mime          STRING       image/jpeg, image/png, ...\n"
                        "#   m:crawled_at    TIMESTAMP    last crawl time\n"
                        "#   m:license       STRING       creative commons, copyright, etc.\n"
                        "#\n"
                        "# Column family 'h' (hashes)\n"
                        "#   h:phash         BYTES(8)     pHash 64-bit\n"
                        "#   h:dhash         BYTES(8)     dHash 64-bit\n"
                        "#   h:whash         BYTES(8)     wHash 64-bit\n"
                        "#\n"
                        "# Column family 'e' (embedding pointer)\n"
                        "#   e:shard_id      INT16        which vector-index shard owns it\n"
                        "#   e:offset        INT64        byte offset of PQ code within shard file\n"
                        "#   e:model_ver     STRING       embedding model version (e.g., v7)"
                    ),
                },
                {"type": "h3", "text": "Vector Index Storage Layout"},
                {
                    "type": "code",
                    "text": (
                        "# Per-shard FAISS index file (memory-mapped)\n"
                        "# Layout (binary):\n"
                        "#\n"
                        "#   header (128 B)        : magic, version, num_vectors, d, M, nlist\n"
                        "#   centroids (K * d * 4) : K=65,536 coarse centroids (float32)\n"
                        "#   pq_codebooks          : M=64 codebooks of 256 centroids each\n"
                        "#   inverted_lists        : posting list per centroid\n"
                        "#       list_id, num_entries, [image_id (8 B), pq_code (64 B)] * N\n"
                        "#\n"
                        "# Per shard: ~100M vectors × (8 B id + 64 B code) = 7.2 GB\n"
                        "# + centroids (16 MB) + codebooks (~512 KB) ≈ 7.2 GB total\n"
                        "# Loaded into RAM at startup; mmap from local SSD on cold start"
                    ),
                },
                {"type": "h3", "text": "Storage Tiers"},
                {
                    "type": "table",
                    "headers": ["Tier", "Stores", "Tech", "Why"],
                    "rows": [
                        ["Hot index", "PQ codes + IVF lists", "FAISS in RAM (1,000 shards)", "Sub-ms vector ops"],
                        ["Warm full vectors", "512-D float32", "ScaNN on local SSD", "Re-rank top-1,000"],
                        ["Metadata", "Image attributes + hashes", "Bigtable", "Petabyte scale, 10 ms reads"],
                        ["Thumbnails", "128×128 JPEGs", "GCS / S3 + CDN", "Cheap blob, geo-cached"],
                        ["Cold full images", "Original bytes", "GCS Coldline", "Re-embedding on model upgrade"],
                    ],
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "ANN Search Algorithms",
            "subtitle": "Pseudocode for IVF-PQ and HNSW",
            "blocks": [
                {"type": "h3", "text": "IVF + PQ Search (per shard)"},
                {
                    "type": "code",
                    "text": (
                        "def ivf_pq_search(query, index, nprobe=32, top_k=100):\n"
                        "    # 1. Find nprobe closest coarse centroids\n"
                        "    centroid_dists = l2(query, index.centroids)        # K dot products\n"
                        "    probe_lists = argpartition(centroid_dists, nprobe)[:nprobe]\n"
                        "\n"
                        "    # 2. Precompute query-to-subspace distance tables\n"
                        "    #    For each of M=64 sub-vectors of the query,\n"
                        "    #    distance to each of 256 sub-centroids.\n"
                        "    dist_table = []  # shape (M, 256)\n"
                        "    for m in range(M):                                  # M=64\n"
                        "        sub_q = query[m*8:(m+1)*8]\n"
                        "        dist_table.append(l2(sub_q, index.codebooks[m]))\n"
                        "\n"
                        "    # 3. Scan posting lists, accumulate approximate distance\n"
                        "    heap = MinHeap(top_k)\n"
                        "    for list_id in probe_lists:\n"
                        "        for image_id, pq_code in index.lists[list_id]:\n"
                        "            d = 0.0\n"
                        "            for m in range(M):\n"
                        "                d += dist_table[m][pq_code[m]]          # 1 byte index\n"
                        "            heap.push((d, image_id))\n"
                        "\n"
                        "    return heap.top_k()                                  # (dist, id) list"
                    ),
                },
                {"type": "h3", "text": "HNSW Search (per shard, smaller indexes)"},
                {
                    "type": "code",
                    "text": (
                        "def hnsw_search(query, graph, ef=64, top_k=100):\n"
                        "    entry = graph.entry_point\n"
                        "    # Greedy descent from top layer to layer 1\n"
                        "    for layer in range(graph.max_level, 0, -1):\n"
                        "        entry = greedy_search(query, entry, layer, ef=1)\n"
                        "    # Beam search at layer 0 with ef candidates\n"
                        "    return beam_search(query, entry, layer=0, ef=ef, top_k=top_k)\n"
                        "\n"
                        "def beam_search(query, entry, layer, ef, top_k):\n"
                        "    visited = {entry}\n"
                        "    candidates = MinHeap([(dist(query, entry), entry)])\n"
                        "    results   = MaxHeap([(dist(query, entry), entry)])\n"
                        "    while candidates:\n"
                        "        d, node = candidates.pop()\n"
                        "        if d > results.top()[0] and len(results) >= ef: break\n"
                        "        for nb in graph.neighbours(node, layer):\n"
                        "            if nb in visited: continue\n"
                        "            visited.add(nb)\n"
                        "            dn = dist(query, nb)\n"
                        "            if dn < results.top()[0] or len(results) < ef:\n"
                        "                candidates.push((dn, nb))\n"
                        "                results.push((dn, nb))\n"
                        "                if len(results) > ef: results.pop()\n"
                        "    return results.top_k(top_k)"
                    ),
                },
                {"type": "h3", "text": "Tunable Parameters"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>nprobe (IVF):</strong> higher = better recall, more compute. 32 is a good starting point",
                        "<strong>M, K (PQ):</strong> M=64, K=256 → 64 B / vector at &gt;0.9 recall@100",
                        "<strong>ef (HNSW):</strong> search beam width; 64–128 typical; higher = better recall",
                        "<strong>top_k:</strong> per-shard top-K returned; coordinator merges and re-ranks",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Crawl & Ingestion Pipeline",
            "subtitle": "From web image to indexed vector",
            "blocks": [
                {"type": "h3", "text": "Pipeline Stages"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Web crawler</strong> discovers image URLs (HTML &lt;img&gt;, sitemaps); writes to Pub/Sub topic <code>image_urls</code>",
                        "<strong>Fetcher</strong> downloads bytes, validates MIME, rejects &gt; 20 MB or animated GIF frames &gt; 50",
                        "<strong>pHash dedup:</strong> compute pHash; Bigtable lookup with Hamming-friendly LSH; if duplicate, skip embedding (just add page reference)",
                        "<strong>Embedding batcher:</strong> queue images for GPU; batch size 64; ~10 ms per batch",
                        "<strong>PQ encode:</strong> use trained codebooks to compress 2 KB → 64 B",
                        "<strong>Vector DB writer:</strong> append to shard's posting list (atomic with Bigtable metadata write)",
                        "<strong>Searchable:</strong> shard reloads its mmap or accepts a write-through delta within ~1 hour",
                    ],
                },
                {"type": "h3", "text": "Throughput Math"},
                {
                    "type": "bullets",
                    "items": [
                        "Target: <strong>500M images/day</strong> = ~5,800/sec",
                        "After pHash dedup (~30% duplicates): ~4,000 unique embeddings/sec",
                        "GPU throughput: 1,000 imgs/sec/GPU at batch 64 → <strong>~4 GPUs steady state</strong>",
                        "10× headroom for re-embedding sweeps and bursts → <strong>~40 GPUs reserved</strong>",
                        "PQ training: re-fit codebooks quarterly on a 10M-sample reservoir",
                    ],
                },
                {"type": "h3", "text": "Delta vs Full Rebuild"},
                {
                    "type": "table",
                    "headers": ["Strategy", "When", "Cost"],
                    "rows": [
                        ["Online write-through", "Every minute", "Cheap; small per-shard append"],
                        ["Hourly compaction", "Per shard", "Rewrite mmap; <1 GB churn"],
                        ["Quarterly full rebuild", "New embedding model", "100B × 10 ms = ~1.2 GPU-years"],
                        ["Codebook retraining", "Quarterly", "10M sample × 1 ms ≈ minutes"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Model-Version Drift",
                    "body": (
                        "Vectors from different embedding versions are <strong>not comparable</strong>. "
                        "Tag every vector with model_ver. During a model upgrade, run both indexes "
                        "in parallel and shadow-test recall before flipping the read traffic. A full "
                        "100B re-embedding takes weeks even with 1,000 GPUs."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Vector Database Choices",
            "subtitle": "FAISS vs ScaNN vs Milvus",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["System", "Origin", "Strengths", "Weaknesses"],
                    "rows": [
                        ["FAISS", "Meta",
                         "Mature C++ kernels, IVF/PQ/HNSW, GPU support",
                         "Library only; you build serving + sharding"],
                        ["ScaNN", "Google",
                         "State-of-the-art recall/latency Pareto; SIMD-tuned",
                         "TF integration heavy; less HNSW support"],
                        ["Milvus", "Zilliz",
                         "Distributed service out of the box; Kubernetes native",
                         "Operational overhead; FAISS under the hood"],
                        ["Vespa", "Yahoo",
                         "Combined text + vector ranking; multi-tenant",
                         "Steeper learning curve; complex DSL"],
                        ["pgvector", "Postgres ext.",
                         "SQL-native; easy to start",
                         "Not suitable beyond ~100M vectors"],
                    ],
                },
                {"type": "h3", "text": "Recommendation"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Use FAISS or ScaNN</strong> as the per-shard library; build a thin gRPC server around it",
                        "Build the <strong>coordinator</strong> in-house: it's where business logic lives (hedging, multi-tenant routing, re-rank)",
                        "Reserve <strong>Milvus / Vespa</strong> for greenfield projects without a serving infra team",
                        "Avoid <strong>pgvector</strong> at this scale — it can't shard a 100B-vector index",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Build vs Buy",
                    "body": (
                        "At Google-scale (100B vectors, 1B QPD), no off-the-shelf vector DB is "
                        "production-ready. Use FAISS / ScaNN as the algorithm, build the serving "
                        "stack on your own infra (Borg / k8s + Bigtable + Spanner). Mid-scale "
                        "products (≤ 1B vectors) can succeed with Milvus or Vespa."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Failure Modes & Recovery",
            "subtitle": "Graceful degradation",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["Shard replica down",
                         "1/3 of replicas for that shard",
                         "Health check; gRPC errors",
                         "Coordinator picks healthy replica; auto-rebalance"],
                        ["Whole shard offline",
                         "Recall drops ~0.1% (1/1000)",
                         "All replicas dead; alert",
                         "Degrade to N-1 shards; flag in response"],
                        ["GPU feature extractor down",
                         "All queries fail",
                         "Inference latency / error rate",
                         "Fallback CPU model (lower quality); auto-scale GPU pool"],
                        ["Bigtable hot row",
                         "Slow metadata hydrate",
                         "p99 hydrate latency spike",
                         "Cache hot image_ids in Redis; rebalance tablets"],
                        ["New images unindexed",
                         "Recent crawl invisible",
                         "Ingestion lag &gt; 1 h",
                         "Surface 'fresh tier' separate index; merge top-K"],
                        ["Adversarial near-dup spam",
                         "Index pollution; bad results",
                         "Cluster-density anomaly",
                         "Per-domain rate-limit; pHash bucket caps"],
                        ["Embedding model drift",
                         "Recall degrades over time",
                         "Offline eval suite",
                         "Quarterly re-train + shadow rollout"],
                        ["Coordinator crash",
                         "5xx for in-flight queries",
                         "Process supervisor",
                         "Stateless; restart in seconds; retry idempotent"],
                    ],
                },
                {"type": "h3", "text": "Graceful Degradation"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Partial fan-out:</strong> if X% shards slow, return early with what you have; mark response 'partial'",
                        "<strong>Cached top results:</strong> for repeated queries (image_id known) serve from result cache",
                        "<strong>Read-only mode:</strong> stop ingestion if Bigtable degraded; queries continue from prior snapshot",
                        "<strong>Tier fallback:</strong> if deep embedding extractor unhealthy, return pHash-only results with banner",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Adversarial Inputs",
                    "body": (
                        "Spammers flood the index with near-duplicates of doorway pages to "
                        "manipulate ranking. Mitigate with <strong>per-domain quotas</strong>, "
                        "pHash-cluster size caps (collapse near-dups within a cluster to one "
                        "canonical), and offline anomaly detection that quarantines suspicious "
                        "ingestion bursts before they reach the live index."
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
                        ["Index algorithm",
                         "IVF + PQ at 100B; HNSW for hot tiers",
                         "IVF-PQ saves 32× RAM but loses ~5pt recall vs HNSW. Required for fit."],
                        ["Sharding",
                         "Random by image_id, fan-out to all",
                         "Simple and balanced; every query touches all shards. Learned routing is complex."],
                        ["Two signals",
                         "pHash + deep embedding",
                         "More compute, but covers both duplicate and semantic search well."],
                        ["Embedding dim",
                         "512-D float32",
                         "Higher-D (1024+) costs 2× memory and ~1pt recall gain. Not worth it."],
                        ["Re-rank pool",
                         "Top-1,000 from approximate search",
                         "Bigger pool = better quality, more latency. 1,000 hits the knee."],
                        ["Freshness",
                         "1-hour delta + nightly compaction",
                         "Lower freshness = bigger compactions, smoother latency. 1 h is humanly fast."],
                        ["Model upgrade",
                         "Quarterly full re-embed",
                         "Cost: ~weeks of GPU time. Faster cadence = constant churn; slower = stale."],
                        ["Result cache",
                         "By image_id, 1-day TTL",
                         "Saves repeat work for popular queries; some staleness when corpus updates."],
                    ],
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
                        "Reverse image search is a <strong>vector retrieval</strong> problem dressed "
                        "up as a search engine. The interview reward comes from articulating the "
                        "two-signal design and the IVF+PQ math; everything else is standard "
                        "service plumbing."
                    ),
                },
                {"type": "h3", "text": "45-Minute Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (3 min):</strong> 100B images, 1B QPD, p99 200 ms, recall &gt; 0.9",
                        "<strong>Capacity (5 min):</strong> 2 KB / 64 B vectors, 6.4 TB cluster RAM, 1,000 shards",
                        "<strong>Two signals (5 min):</strong> pHash (cheap dup) + deep embedding (semantic)",
                        "<strong>ANN deep dive (10 min):</strong> IVF coarse + PQ compression; nprobe trade-off",
                        "<strong>Sharding (5 min):</strong> random hash, fan-out, replication, hedged requests",
                        "<strong>Query path (7 min):</strong> latency budget; tail-latency mitigation",
                        "<strong>Ingestion (5 min):</strong> crawler → pHash dedup → GPU batch → vector DB",
                        "<strong>Failures + trade-offs (5 min):</strong> shard down, model drift, adversarial",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "“100B × 2 KB = 200 TB raw → PQ to 64 B → 6.4 TB fits in cluster RAM” (size justifies algorithm)",
                        "“Two signals: pHash for duplicates, embeddings for semantics” (covers product surface)",
                        "“Random sharding forces fan-out to 1,000 shards; hedged requests tame the tail”",
                        "“nprobe = 32 of K = 65,536 → visit 0.05% of corpus per shard”",
                        "“Top-1,000 re-rank with full-precision vectors recovers most PQ recall loss”",
                        "“GPU batch size 64 keeps feature extraction at ~10 ms p99”",
                        "“Quarterly re-embed; tag vectors with model_ver to avoid mixing”",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why fan-out to all shards?</strong> A: With random sharding, neighbours can be on any shard; learned shard routing (SPANN) reduces fan-out but adds a coarse-shard quantizer that's hard to keep recall on at this scale.",
                        "<strong>Q: How do you handle a new image?</strong> A: Crawler → pHash dedup → GPU batch → PQ encode → append to a delta segment in the matching shard; periodic compaction merges into the main mmap.",
                        "<strong>Q: How do you upgrade the embedding model?</strong> A: Re-embed corpus offline (~weeks on 1,000 GPUs), build a parallel index, shadow-test recall, then flip read traffic. Old vectors stay live until cutover.",
                        "<strong>Q: How do you keep p99 &lt; 200 ms with 1,000 RPCs?</strong> A: Hedged requests against replicas after p95; backup-on-timeout; dynamic batching for GPU; result caching by image_id.",
                        "<strong>Q: What if user uploads adversarial near-dup?</strong> A: pHash-cluster caps and per-domain quotas at ingestion; re-rank scoring penalizes identical pHash clusters dominating the result.",
                        "<strong>Q: Why not HNSW everywhere?</strong> A: HNSW needs the full 2 KB vector + ~200 B graph metadata per vector. At 100B that's 220 TB — won't fit. IVF-PQ trades a few recall points for 30× memory savings.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "<strong>100B</strong> images &nbsp;·&nbsp; "
                        "<strong>1B</strong> queries/day &nbsp;·&nbsp; "
                        "<strong>2 KB → 64 B</strong> via PQ (M=64) &nbsp;·&nbsp; "
                        "<strong>1,000</strong> shards × 6.4 GB &nbsp;·&nbsp; "
                        "<strong>nprobe=32</strong> of K=65,536 &nbsp;·&nbsp; "
                        "<strong>p99 &lt; 200 ms</strong> &nbsp;·&nbsp; "
                        "recall@100 &gt; <strong>0.9</strong>."
                    ),
                },
            ],
        },
    ],
}
