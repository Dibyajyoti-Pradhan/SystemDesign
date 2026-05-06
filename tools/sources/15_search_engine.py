"""Source for `15 - Search Engine.pdf` (web search engine: indexing + serving)."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design a Web Search Engine",
    "subtitle": "Google/Bing-scale indexing, ranking, and query serving",
    "read_time": "~ 45 minute read",
    "short_title": "Design a Web Search Engine",
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
                        "Design a web-scale search engine like <strong>Google</strong> or "
                        "<strong>Bing</strong>. The system must index ~100B web pages, answer "
                        "free-text queries with sub-200 ms latency at ~100K QPS sustained, and "
                        "rank results so the most relevant documents surface in the top 10. "
                        "Crawling itself is out of scope (covered in <strong>14 - Web Crawler</strong>); "
                        "we focus on the <strong>indexing pipeline</strong> and the "
                        "<strong>online serving stack</strong>."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Corpus size?", "~100B web pages indexed (English-dominant)"],
                        ["Query volume?", "~100K QPS sustained, ~500K QPS peak"],
                        ["Latency target?", "p99 &lt; 200 ms end-to-end (search box → 10 blue links)"],
                        ["Freshness?", "Daily full rebuild + minute-level real-time inserts for trending"],
                        ["Languages?", "Multi-lingual; per-language analyzers; assume English here"],
                        ["Personalisation?", "Light: locale, recent history; full personalisation out of scope"],
                        ["Crawler?", "Assumed solved — focus on index + serve"],
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
                        ["Query", "GET /search?q=... → ranked list of 10 results + snippets"],
                        ["Spell correct", "Auto-suggest correction; “did you mean…”"],
                        ["Synonyms", "Expand query terms (car ↔ automobile)"],
                        ["Snippets", "Highlight matched terms with surrounding context"],
                        ["Freshness", "Trending content searchable within minutes"],
                        ["Filters", "Site:, filetype:, date range; advanced operators"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Availability", "99.99% — search is the front door"],
                        ["Query latency", "p50 &lt; 80 ms · p99 &lt; 200 ms"],
                        ["Throughput", "100K QPS sustained · 500K QPS peak"],
                        ["Index size", "~100 TB compressed inverted index (across replicas)"],
                        ["Freshness", "Daily batch rebuild + real-time insert path (≤ 5 min)"],
                        ["Recall vs precision", "Recall ≥ 90% in candidate gen; top-10 precision is the metric"],
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
                {"type": "h3", "text": "Corpus & Index Size"},
                {
                    "type": "bullets",
                    "items": [
                        "Pages indexed: <strong>100 billion</strong>",
                        "Avg indexed bytes per page (terms + positions + tf): <strong>~5 KB</strong> uncompressed",
                        "Raw inverted-index size: 100B × 5 KB = <strong>500 TB</strong>",
                        "After block compression (PForDelta + Roaring): <strong>~5×</strong> ratio → <strong>~100 TB</strong>",
                        "Doc store (titles, URLs, snippet text): ~2 KB / page × 100B = <strong>~200 TB</strong>",
                        "Total per replica: ~300 TB; with 3-way replication ≈ <strong>~1 PB online</strong>",
                    ],
                },
                {"type": "h3", "text": "Query Throughput"},
                {
                    "type": "bullets",
                    "items": [
                        "Sustained: <strong>100,000 QPS</strong>",
                        "Peak (event-driven): <strong>~500,000 QPS</strong> (≈ 5×)",
                        "p99 latency budget: <strong>&lt; 200 ms</strong> from edge to rendered SERP",
                        "Internal budget: 20 ms parse/rewrite + 80 ms shard fan-out + 30 ms rerank + 30 ms snippets + 40 ms slack",
                    ],
                },
                {"type": "h3", "text": "Sharding Math"},
                {
                    "type": "bullets",
                    "items": [
                        "Per-shard index size target: <strong>~50 GB</strong> in RAM (fits NVMe-backed page cache too)",
                        "Shards per replica: 100 TB / 50 GB = <strong>~2,000 shards</strong>",
                        "Replicas per shard: 3 (HA + read parallelism) → <strong>6,000 index servers</strong>",
                        "Fan-out per query: 1 → 2,000 shards (scatter-gather); coordinator merges top-K",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "100B pages &nbsp;·&nbsp; 100K QPS sustained / 500K peak &nbsp;·&nbsp; "
                        "p99 &lt; 200 ms &nbsp;·&nbsp; 100 TB compressed index &nbsp;·&nbsp; "
                        "~2,000 shards × 3 replicas &nbsp;·&nbsp; ~5 KB indexed/page."
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level Architecture",
            "subtitle": "Online serving + offline indexing",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Two halves: an <strong>online serving stack</strong> that fans queries "
                        "out across thousands of index shards and reranks the merged candidates, "
                        "and an <strong>offline indexing pipeline</strong> that turns crawled "
                        "pages into immutable index segments and pushes them to serving."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Online path (top): Frontend → Coordinator → Index Servers (sharded) + Doc Servers → Ranker → SERP. Offline path (bottom): Crawl → Parse → Index Build → Index Push.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Client"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Client [label="Browser / App", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge & Frontend"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        FE   [label="Frontend\n(spell + rewrite)", fillcolor="#cbeedf"];
        QC   [label="Query Coordinator\n(scatter-gather)", fillcolor="#cbeedf"];
        QCache [label="Query Result\nCache", fillcolor="#cbeedf"];
    }
    subgraph cluster_serve {
        label="Index Tier (sharded × replicated)"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        IS1 [label="Index Shard 1\n(BM25 top-K)", fillcolor="#fff2c9"];
        IS2 [label="Index Shard 2", fillcolor="#fff2c9"];
        ISN [label="… Index Shard N", fillcolor="#fff2c9"];
    }
    subgraph cluster_rank {
        label="Rerank & Snippet"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        Rerank [label="Learned Reranker\n(LambdaMART / DNN)", fillcolor="#ead7fb"];
        DocSrv [label="Doc Server\n(snippet store)", fillcolor="#ead7fb"];
    }
    subgraph cluster_offline {
        label="Offline Indexing Pipeline"; style="rounded,dashed"; color="#c0392b"; fontcolor="#c0392b";
        Crawl [label="Crawl\n(see file 14)", fillcolor="#fbd7c5"];
        Parse [label="Parse + Tokenize\n+ link graph", fillcolor="#fbd7c5"];
        Build [label="Index Builder\n(Spark / MR)", fillcolor="#fbd7c5"];
        Push  [label="Segment Push\n(immutable shards)", fillcolor="#fbd7c5"];
        RT    [label="Real-time\nIndex (NRT)", fillcolor="#fbd7c5"];
    }

    Client -> FE [label="q=..."];
    FE -> QCache [label="lookup", style=dashed];
    FE -> QC;
    QC -> IS1 [label="fan-out"];
    QC -> IS2;
    QC -> ISN;
    IS1 -> QC [label="top-K", style=dashed];
    IS2 -> QC [style=dashed];
    ISN -> QC [style=dashed];
    QC -> Rerank;
    Rerank -> DocSrv [label="snippet"];
    Rerank -> FE [label="SERP"];
    FE -> Client;

    Crawl -> Parse -> Build -> Push;
    Push  -> IS1 [style=dashed, color="#c0392b"];
    Push  -> IS2 [style=dashed, color="#c0392b"];
    Push  -> ISN [style=dashed, color="#c0392b"];
    Parse -> RT  [style=dashed];
    RT    -> IS1 [style=dashed, color="#c0392b", label="NRT delta"];
}
""",
                },
                {"type": "h3", "text": "Online Path"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Frontend:</strong> auth, spell-correction, query rewrite (synonyms, stemming), result-cache lookup",
                        "<strong>Query Coordinator:</strong> fans the parsed query out to every index shard (root + leaf model)",
                        "<strong>Index Servers:</strong> each shard scores its local docs via BM25 and returns local top-K (e.g., K=1,000)",
                        "<strong>Reranker:</strong> merges shard top-Ks, applies LambdaMART / neural model on top ~200 candidates",
                        "<strong>Doc Server:</strong> separate KV store keyed by doc_id; supplies titles + raw text for snippet generation",
                    ],
                },
                {"type": "h3", "text": "Offline Path"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Crawler frontier:</strong> upstream (file 14) drops raw HTML into object storage",
                        "<strong>Parser:</strong> extract text, language, links → emit (term, doc_id, tf, positions) tuples",
                        "<strong>Index Builder:</strong> Spark / MapReduce sorts by term, builds posting lists, writes immutable segments",
                        "<strong>Segment Push:</strong> rsync new segments to index servers; hot-reload behind a barrier",
                        "<strong>Real-time index:</strong> small in-memory inverted index for breaking news; merged into base nightly",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "The Inverted Index",
            "subtitle": "Term → posting list",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The inverted index is the backbone. For each term in the vocabulary "
                        "we store a <strong>posting list</strong>: the document IDs that contain "
                        "the term, plus per-document term frequency and (optionally) positions "
                        "for phrase queries. Posting lists are sorted by doc_id and "
                        "block-compressed."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Inverted-index physical layout: term dictionary points into a posting-list file; each list is a sequence of compressed blocks holding doc_ids, term frequencies, and positions.",
                    "dot": r"""
digraph II {
    rankdir=LR;
    bgcolor="white";
    node [shape=record, style="rounded,filled", fontname="Helvetica", fontsize=9, color="#2e57b8", fillcolor="#fff2c9"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Dict [label="{Term Dictionary (FST / B-tree)|{ apple | bread | cat | … | zebra }}"];

    PL_apple [label="{Posting list: apple|{block 0 | block 1 | block 2 | …}|{(d=12, tf=3, pos=[4,7,99])|(d=88, tf=1, pos=[2])|…}}", fillcolor="#cbeedf"];
    PL_cat   [label="{Posting list: cat|{block 0 | block 1 | …}|{(d=3, tf=2, pos=[1,8])|(d=44, tf=1, pos=[12])|…}}", fillcolor="#cbeedf"];

    DocStore [label="{Doc Store (KV)|{doc_id → title, url, body}|{12 → 'Apple pie recipe'|88 → 'iPhone review'|3  → 'Cat behaviour'}}", fillcolor="#ead7fb"];

    Dict -> PL_apple [label="apple"];
    Dict -> PL_cat   [label="cat"];
    PL_apple -> DocStore [style=dashed, label="doc_id lookup"];
    PL_cat   -> DocStore [style=dashed];
}
""",
                },
                {"type": "h3", "text": "Posting-List Encoding"},
                {
                    "type": "code",
                    "text": (
                        "// Logical record:\n"
                        "//   term: \"apple\"\n"
                        "//   df:   42_318_004        // documents containing the term\n"
                        "//   postings: [(doc_id, tf, [positions...]), ...]   // sorted by doc_id\n"
                        "//\n"
                        "// Physical layout (per posting list):\n"
                        "//   header { df, doc_id_min, doc_id_max, num_blocks }\n"
                        "//   for each block of 128 postings:\n"
                        "//       doc_ids   : delta-encoded then PForDelta-packed\n"
                        "//       tfs       : variable-byte (most tfs are tiny)\n"
                        "//       positions : delta-encoded + PForDelta (skipped for non-phrase queries)\n"
                        "//   skip_pointers[] -> { doc_id, file_offset }  // every 1,024 docs\n"
                        "//\n"
                        "// Compression ratio: ~5x vs raw int32 doc_ids; ~10x with positions skipped.\n"
                        "// Hot heads (small df_inverse, i.e. common terms) live in RAM; tails on SSD."
                    ),
                },
                {"type": "h3", "text": "Tiered Storage"},
                {
                    "type": "table",
                    "headers": ["Tier", "Resident", "Latency", "What lives here"],
                    "rows": [
                        ["RAM", "~10% of index", "&lt; 1 ms", "Heads of common terms, term dict, skip pointers"],
                        ["NVMe SSD", "~70% of index", "~100 µs", "Bulk posting lists, doc store hot shard"],
                        ["HDD / object store", "~20% (cold)", "~10 ms", "Long-tail postings, archive doc bodies"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why immutable segments?",
                    "body": (
                        "Posting lists are append-mostly and read-heavy. Immutable segments + "
                        "background merges (LSM-style) let us keep posting lists densely packed, "
                        "memory-map them, and avoid per-document write amplification. "
                        "Lucene/Elasticsearch use exactly this pattern."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Sharding Strategy",
            "subtitle": "Document-partition vs term-partition",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Two ways to slice a 100 TB index across 2,000 machines: by "
                        "<strong>document</strong> (every shard owns ~50M docs and holds the "
                        "full vocabulary for those docs) or by <strong>term</strong> (every "
                        "shard owns a slice of the vocabulary and holds the global posting list "
                        "for those terms). The trade-off shapes the entire serving stack."
                    ),
                },
                {
                    "type": "table",
                    "headers": ["Aspect", "Doc-partition (recommended)", "Term-partition"],
                    "rows": [
                        ["Query fan-out", "All shards (scatter-gather)", "Only shards owning query terms (1–5 typical)"],
                        ["Network", "High: O(N_shards) RPCs / query", "Low: O(query_terms) RPCs"],
                        ["Hotspot risk", "Even (random doc_id placement)", "Severe — common terms (“the”) hammer one shard"],
                        ["Indexing", "Embarrassingly parallel by doc", "Requires global sort by term; cross-machine shuffle"],
                        ["Adding docs", "Append to one shard", "Touches every shard owning a term in the doc"],
                        ["Replica granularity", "Per shard (simple)", "Per term range (uneven sizes)"],
                        ["Recovery", "Lose 1/N of corpus per shard down → degrade", "Lose entire term ranges → wrong answers"],
                        ["Used by", "Google, Bing, Elasticsearch, Solr", "Mostly academic / specialised IR systems"],
                    ],
                },
                {"type": "h3", "text": "Why Doc-Partition Wins at Web Scale"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Hotspot resistance:</strong> hash(doc_id) spreads load uniformly; query 'the' hits all shards equally",
                        "<strong>Fault tolerance:</strong> a dead shard means missing 1/N of candidates, not missing a whole term",
                        "<strong>Throughput:</strong> 2,000 shards × 3 replicas = 6,000 cores doing scoring in parallel",
                        "<strong>Indexing speed:</strong> each builder writes its own segments, no cross-cluster shuffle",
                    ],
                },
                {"type": "h3", "text": "Cost of Scatter-Gather"},
                {
                    "type": "bullets",
                    "items": [
                        "Every query talks to every shard → tail-latency amplification (slowest shard wins)",
                        "Mitigation: <strong>request hedging</strong> — re-issue to a replica when p95 elapses",
                        "Mitigation: <strong>tiered serving</strong> — high-quality shard tier handles 90% of queries; full corpus only when shallow tier returns &lt; threshold candidates",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Recommendation",
                    "body": (
                        "Doc-partition with hash(doc_id) sharding and 3-way replication. Pair "
                        "with a hot/cold tier so most queries are answered by a smaller, faster "
                        "subset of the corpus, falling back to full fan-out only when needed."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Query Pipeline",
            "subtitle": "From query string to SERP",
            "blocks": [
                {"type": "h3", "text": "End-to-End Steps"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Receive</strong> query at Frontend; record query_id, user locale, session",
                        "<strong>Normalize</strong>: lowercase, Unicode NFKC, strip punctuation",
                        "<strong>Spell-correct</strong>: noisy-channel model + click-log priors → 'did you mean'",
                        "<strong>Tokenize</strong> with the same analyzer used at index time",
                        "<strong>Rewrite</strong>: stem, expand synonyms, drop stopwords (or downweight)",
                        "<strong>Cache check</strong>: hash(rewritten_query, locale) → query result cache",
                        "<strong>Coordinator fan-out</strong>: send to all index shards (or hot tier first)",
                        "<strong>Per-shard scoring</strong>: BM25 over posting lists; emit local top-K (K≈1,000)",
                        "<strong>Merge</strong> at coordinator: priority queue keyed by score → global top-N (N≈200)",
                        "<strong>Rerank</strong>: learned-to-rank model with rich features (PageRank, freshness, click-through)",
                        "<strong>Snippet</strong>: re-fetch doc bodies, highlight matched terms",
                        "<strong>Render SERP</strong>: 10 results + ads + features (KG card, images)",
                        "<strong>Log</strong>: query, results, click position → feedback loop for ranking model",
                    ],
                },
                {"type": "h3", "text": "Latency Budget"},
                {
                    "type": "table",
                    "headers": ["Stage", "Budget", "Notes"],
                    "rows": [
                        ["Edge + Frontend", "20 ms", "TLS, parse, spell-correct, cache lookup"],
                        ["Coordinator fan-out", "80 ms", "Slowest-shard latency; hedged requests"],
                        ["Per-shard scoring", "50 ms (parallel)", "Decompress postings + BM25 + heap top-K"],
                        ["Merge top-K", "5 ms", "Priority queue across N shards"],
                        ["Rerank", "30 ms", "LambdaMART or small DNN over ~200 docs"],
                        ["Snippet generation", "30 ms", "Doc-server fetch + highlight"],
                        ["Render + return", "20 ms", "HTML / JSON response"],
                        ["<strong>Total p99</strong>", "<strong>&lt; 200 ms</strong>", "Overlapping where possible"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Tail latency hedging",
                    "body": (
                        "At 2,000 shards a query is only as fast as its slowest shard. If each "
                        "shard has p99 = 50 ms, the fan-out p99 is much worse. Mitigation: send "
                        "the request to one replica, and after 30 ms fire a tied request to a "
                        "second replica; take whichever returns first. Recovers most of the tail."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Ranking",
            "subtitle": "BM25, link signals, learned-to-rank",
            "blocks": [
                {"type": "h3", "text": "Two-Stage Ranking"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Candidate generation (recall):</strong> BM25 per shard, top 1,000 each",
                        "<strong>Reranking (precision):</strong> learned model over top ~200 globally with rich features",
                        "Why two stages? BM25 is cheap (millions of docs/sec/core); LambdaMART is expensive but only runs on hundreds",
                    ],
                },
                {"type": "h3", "text": "BM25 Scoring"},
                {
                    "type": "code",
                    "text": (
                        "# BM25 score for query Q against document D\n"
                        "# Constants: k1 ≈ 1.2, b ≈ 0.75\n"
                        "#   tf(t,D)  = term frequency of t in D\n"
                        "#   df(t)    = number of docs containing t\n"
                        "#   |D|      = length of D in tokens\n"
                        "#   avgdl    = mean doc length in the corpus\n"
                        "#   N        = total docs in the corpus\n"
                        "\n"
                        "def bm25(Q, D, stats, k1=1.2, b=0.75):\n"
                        "    score = 0.0\n"
                        "    for t in Q:\n"
                        "        if t not in D: continue\n"
                        "        idf = log((stats.N - stats.df[t] + 0.5) /\n"
                        "                  (stats.df[t] + 0.5) + 1)\n"
                        "        tf  = D.tf[t]\n"
                        "        norm = 1 - b + b * (D.length / stats.avgdl)\n"
                        "        score += idf * (tf * (k1 + 1)) / (tf + k1 * norm)\n"
                        "    return score"
                    ),
                },
                {"type": "h3", "text": "Top-K Heap Merge Across Shards"},
                {
                    "type": "code",
                    "text": (
                        "# Coordinator merges per-shard top-K into a global top-N (N ≤ K)\n"
                        "import heapq\n"
                        "\n"
                        "def merge_topk(shard_results, N=200):\n"
                        "    # shard_results: list[ list[(score, doc_id, shard_id)] ]  per-shard sorted desc\n"
                        "    heap = []   # min-heap of size N\n"
                        "    for shard in shard_results:\n"
                        "        for score, doc_id, sid in shard:\n"
                        "            if len(heap) < N:\n"
                        "                heapq.heappush(heap, (score, doc_id, sid))\n"
                        "            elif score > heap[0][0]:\n"
                        "                heapq.heapreplace(heap, (score, doc_id, sid))\n"
                        "            else:\n"
                        "                break  # shard list is sorted; safe to stop\n"
                        "    return sorted(heap, key=lambda x: -x[0])"
                    ),
                },
                {"type": "h3", "text": "Ranking Signal Categories"},
                {
                    "type": "table",
                    "headers": ["Category", "Examples", "Signal type"],
                    "rows": [
                        ["Text relevance", "BM25, term proximity, exact-phrase match", "Per-query × per-doc"],
                        ["Document quality", "PageRank, link graph, spam score, content length", "Per-doc (offline)"],
                        ["Freshness", "doc_age, last-modified, crawl frequency", "Per-doc (offline) + RT"],
                        ["User behaviour", "Click-through rate, dwell time, query reformulation", "Aggregated from logs"],
                        ["Personalisation", "Locale, language, recent queries, location", "Per-query × per-user"],
                        ["Authority", "Domain trust, HTTPS, author signals", "Per-doc (offline)"],
                        ["Intent", "Navigational vs informational classifier", "Per-query"],
                    ],
                },
                {"type": "h3", "text": "Learned-to-Rank Reranker"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Model:</strong> LambdaMART (gradient-boosted trees) — workhorse since ~2010; or a small Transformer cross-encoder for top-50",
                        "<strong>Training:</strong> pairwise loss on labelled (query, doc, relevance) judgements + click logs",
                        "<strong>Features per (q, d):</strong> ~hundreds (BM25 of body/title/anchor, PageRank, freshness, click features, language match)",
                        "<strong>Inference:</strong> ~30 ms for 200 candidates × 500 trees on a single CPU; SIMD-friendly",
                        "<strong>A/B:</strong> every model change rolled out behind interleaved experiments measured by NDCG@10 + click-through",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "PageRank in 2026",
                    "body": (
                        "Link graph signals (PageRank-style eigenvector centrality) are still "
                        "computed offline over a graph of ~1T edges. They survive as one feature "
                        "among hundreds in the LTR model — not the dominant signal Brin and Page "
                        "started with, but still a strong prior for authority."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Indexing Pipeline",
            "subtitle": "Crawl → segments → serving",
            "blocks": [
                {"type": "h3", "text": "Daily Batch Build"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Input:</strong> raw crawl corpus in object storage (Parquet of [url, html, fetched_at])",
                        "<strong>Parse stage:</strong> Spark job extracts text, language, links, metadata",
                        "<strong>Tokenize:</strong> per-language analyzer; emit (doc_id, term, tf, positions)",
                        "<strong>Sort + group:</strong> shuffle by (shard_id, term); each shard sees its slice",
                        "<strong>Build segments:</strong> per shard, write immutable Lucene-style segment files",
                        "<strong>Push:</strong> upload to per-shard staging area; index server downloads",
                        "<strong>Atomic swap:</strong> behind a barrier, all replicas of a shard cut over to new generation",
                    ],
                },
                {"type": "h3", "text": "Real-Time Insert Path"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Why?</strong> News, sports, social trends — must be searchable in minutes, not 24 hours",
                        "<strong>Write path:</strong> Parser → Kafka topic <code>doc_updates</code> (key = doc_id)",
                        "<strong>NRT indexer:</strong> consumes Kafka, builds an in-memory mini-index per shard (~GB)",
                        "<strong>Merge:</strong> nightly batch absorbs the NRT delta into the main segment",
                        "<strong>Serving:</strong> queries hit BOTH the main index and the NRT delta; scores combined",
                    ],
                },
                {"type": "h3", "text": "Freshness vs Build Cost"},
                {
                    "type": "table",
                    "headers": ["Strategy", "Freshness", "Build cost", "Where used"],
                    "rows": [
                        ["Full daily rebuild", "24 h", "Highest (re-process 100B docs)", "Long-tail content"],
                        ["Incremental segments + nightly merge", "Hours", "Medium", "Most content"],
                        ["Real-time mini-index (NRT)", "Minutes", "Low (in-memory only)", "News, trending"],
                        ["Push-on-publish", "Seconds", "Per-doc network cost", "Featured publishers, AMP"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Three-tier freshness model",
                    "body": (
                        "Run all three: nightly full rebuild for the long tail, incremental "
                        "merges for hourly updates, and an NRT in-memory index for trending "
                        "content. Queries hit all tiers; scores combined. Keeps cost bounded "
                        "while staying fresh on what users actually care about right now."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Caching Layers",
            "subtitle": "Result, posting-list, and document caches",
            "blocks": [
                {"type": "h3", "text": "Why caching matters here"},
                {
                    "type": "bullets",
                    "items": [
                        "Query distribution is heavily Zipfian: top ~1% of queries cover ~50% of volume",
                        "Recomputing the SERP for 'weather' or 'youtube' 100K times/sec is wasteful",
                        "Posting lists for common terms ('the', 'and') are huge and accessed by every query",
                    ],
                },
                {
                    "type": "table",
                    "headers": ["Layer", "Key", "Value", "Size", "Hit rate", "TTL"],
                    "rows": [
                        ["Query result cache", "hash(query, locale)", "Rendered SERP (top-10)", "~100 GB", "30–50%", "1–10 min"],
                        ["Posting-list cache", "term_id", "Decompressed posting head", "~5 GB / shard", "~80% on heads", "Until segment swap"],
                        ["Doc fragment cache", "doc_id", "Title + snippet body", "~50 GB / region", "~60%", "Hours"],
                        ["Spell / rewrite cache", "raw query", "Rewritten query", "~10 GB", "~70%", "1 day"],
                    ],
                },
                {"type": "h3", "text": "Query Result Cache Details"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Eligibility:</strong> only non-personalised, non-localised slices cached; logged-in users still benefit from sub-feature caches",
                        "<strong>Invalidation:</strong> short TTL + explicit purge on big news events (e.g., 'super bowl 2026' result needs refreshing live)",
                        "<strong>Storage:</strong> Memcached / Redis cluster geographically replicated; ~200 nodes",
                        "<strong>Win:</strong> a 30% hit rate at 100K QPS removes 30K QPS from the index tier — saves billions in serving cost",
                    ],
                },
                {"type": "h3", "text": "Posting-List Cache Details"},
                {
                    "type": "bullets",
                    "items": [
                        "Each index server keeps decompressed posting-list <strong>heads</strong> (first few blocks) for the most-used terms",
                        "Eviction: LFU; resets after segment swap",
                        "Saves the per-query decompression cost on common terms — biggest CPU win in the index server",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Personalisation vs cache hit",
                    "body": (
                        "Every personal feature you add (location, recent history, account "
                        "preferences) shrinks the cache key space and tanks the result-cache "
                        "hit rate. Keep personalisation as a final reranking step over cached "
                        "candidates, not a first-class cache key."
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Doc Store & Snippet Generation",
            "subtitle": "Showing why a result matters",
            "blocks": [
                {"type": "h3", "text": "Doc Store"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Purpose:</strong> serve the data needed to render a result row — title, URL, body excerpt",
                        "<strong>Schema:</strong> <code>doc_id → { url, title, body_text, lang, last_modified }</code>",
                        "<strong>Backing store:</strong> Bigtable / RocksDB / custom SSTable; sharded by doc_id",
                        "<strong>Size:</strong> ~2 KB / doc × 100B = ~200 TB; replicated 3×",
                        "<strong>Access pattern:</strong> 200 random doc_id reads per query (one per candidate)",
                    ],
                },
                {"type": "h3", "text": "Snippet Algorithm"},
                {
                    "type": "numbered",
                    "items": [
                        "Fetch doc body for top-10 reranked results (parallelised across doc-store shards)",
                        "Slide a fixed-width window (≈ 30 tokens) over the body",
                        "Score each window by sum of query-term occurrences + IDF weight",
                        "Pick the highest-scoring window; truncate at sentence boundary",
                        "Bold the matched query terms; HTML-escape; return ~160-char snippet",
                    ],
                },
                {"type": "h3", "text": "Snippet Cache"},
                {
                    "type": "bullets",
                    "items": [
                        "Cache key: <code>(doc_id, query_terms_hash)</code>",
                        "TTL: 1 day; invalidated when doc body changes",
                        "Hit rate: ~60% (popular doc + popular query combos)",
                        "Without this cache, snippet generation can dominate the latency budget",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why a separate doc store?",
                    "body": (
                        "We never store the full doc body inside posting-list shards — it would "
                        "balloon the inverted index for no scoring benefit. Splitting the index "
                        "server (scoring, latency-critical, RAM-bound) from the doc server "
                        "(snippet, throughput-bound, SSD-bound) lets each scale independently."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Failure Modes & Recovery",
            "subtitle": "What can go wrong",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["1 of 3 shard replicas down", "Query still served by remaining 2",
                         "Health-check / heartbeat", "Auto-promote spare replica; rebuild from segments in object storage"],
                        ["Entire shard (all replicas) down", "Missing 1/N of candidates → degraded recall",
                         "Coordinator timeout %", "Serve from N-1 shards; flag SERP as 'partial'; alert SREs"],
                        ["Coordinator overloaded", "Tail latency blows past 200 ms",
                         "p99 alarm", "Shed load (drop low-priority queries); auto-scale coordinator pool"],
                        ["Index push corrupt segment", "Wrong / missing results",
                         "Checksum + canary query suite", "Refuse swap; revert to previous generation"],
                        ["Reranker model OOM / crash", "BM25-only ranking → noticeable quality drop",
                         "Model-server health", "Fall back to BM25 ordering; alert; roll model back"],
                        ["Doc store shard down", "Cannot generate snippets for some results",
                         "Doc-server timeout", "Show title + URL only; fall back to cached snippet"],
                        ["NRT pipeline lag", "Trending content stale",
                         "Kafka lag metric", "Alert; scale NRT consumers; queries see slightly older content"],
                        ["Datacenter loss", "Region offline",
                         "Edge health checks", "Geo-failover to surviving DC; serve from cached SERPs first"],
                    ],
                },
                {"type": "h3", "text": "Graceful Degradation Ladder"},
                {
                    "type": "numbered",
                    "items": [
                        "Healthy: full fan-out + LTR rerank + personalisation + snippets",
                        "Mild: skip personalisation reranker; keep core LTR",
                        "Worse: skip LTR; sort merged results by BM25",
                        "Severe: serve from query result cache only",
                        "Critical: return cached SERPs from CDN edge with 'service degraded' banner",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Recall degrades silently",
                    "body": (
                        "When a shard is down, the SERP looks normal — it's just missing some "
                        "good candidates. Always emit a per-query metric for the number of "
                        "shards that responded; alert when it drops below the configured floor."
                    ),
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
                        ["Sharding axis", "Document-partition",
                         "Scatter-gather every query but no hotspots and easy HA. Term-partition is cheaper per query but suffers severe load skew on common terms."],
                        ["Index format", "Immutable segments + LSM merges",
                         "Background merge cost; simpler reads, dense compression, mmap-friendly. In-place updates would write-amplify badly."],
                        ["Compression", "PForDelta / Roaring + var-byte tf",
                         "Slightly more CPU on read, ~5× smaller index. Pure raw int32 would explode RAM cost."],
                        ["Two-stage ranking", "BM25 → LTR rerank top-200",
                         "BM25 is recall-imperfect but cheap; LTR is precise but expensive — only run it on the shortlist."],
                        ["Freshness", "Daily batch + NRT delta",
                         "Trending content fresh in minutes; long tail rebuilt nightly. Per-doc push-on-publish is fresher but unaffordable for 100B docs."],
                        ["Personalisation", "Final rerank only",
                         "Preserves cache hit rate. Personalising candidate gen would shrink shareable cache to near-zero."],
                        ["Cache TTL", "Short (1–10 min) on results",
                         "Slight staleness during news events; very high freshness elsewhere. Long TTL serves stale SERPs in fast-moving topics."],
                        ["Replication", "3× per shard",
                         "Lose any 2 nodes per shard → still serving. 2× would be cheaper but cuts safety margin in half."],
                        ["Tail-latency hedging", "Tied requests at p95",
                         "~5–10% extra fan-out load; recovers most of the long tail. Without it, p99 dominated by slowest replica."],
                    ],
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Scalability & Operations",
            "subtitle": "Running the fleet",
            "blocks": [
                {"type": "h3", "text": "Capacity Planning"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Index tier:</strong> ~6,000 servers (2,000 shards × 3 replicas); ~50 GB index each, 256 GB RAM, NVMe",
                        "<strong>Doc tier:</strong> ~3,000 servers; SSD-heavy; ~100 TB / replica × 3",
                        "<strong>Coordinators:</strong> ~500 stateless boxes; auto-scale on QPS",
                        "<strong>Reranker:</strong> ~1,000 GPU/CPU servers; model held entirely in RAM",
                        "<strong>Cache tier:</strong> ~500 Redis/Memcached nodes per region",
                    ],
                },
                {"type": "h3", "text": "Deployment Cadence"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Index segments:</strong> pushed continuously; replicas rolled one at a time per shard",
                        "<strong>Coordinator / frontend:</strong> blue-green deploys behind LB; canary 1% → 10% → 100%",
                        "<strong>Ranking model:</strong> shadow traffic → interleaved A/B → full rollout if NDCG@10 wins",
                        "<strong>Schema changes:</strong> double-write old + new posting list format until full reindex done",
                    ],
                },
                {"type": "h3", "text": "Observability"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Per-query metrics:</strong> latency p50/p99, shards responded, cache hit, ranker stage timings",
                        "<strong>Quality metrics:</strong> NDCG@10 on a labelled probe set, CTR@1, query reformulation rate",
                        "<strong>Index health:</strong> segment count, merge backlog, NRT lag, push success rate",
                        "<strong>Capacity:</strong> RAM headroom per shard, SSD IOPS, coordinator CPU",
                    ],
                },
                {"type": "h3", "text": "Cost Levers"},
                {
                    "type": "table",
                    "headers": ["Lever", "Effect", "Risk"],
                    "rows": [
                        ["Shrink ranker top-200 → top-100", "~40% reranker cost", "Slight NDCG loss"],
                        ["Cold-tier more long-tail postings to disk", "Less RAM per shard", "Higher tail latency"],
                        ["Tighter result-cache eligibility", "Higher hit rate", "Less personalisation"],
                        ["Fewer replicas (3 → 2)", "33% fewer servers", "No rolling deploy + repair simultaneously"],
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
                        "Web search is a depth-of-knowledge interview: the surface area is huge "
                        "(crawl, index, rank, serve, ML, ops), so signal which area you want to "
                        "go deep on early. The strongest candidates pick <strong>one</strong> "
                        "of (a) inverted-index internals, (b) sharding/serving, or (c) ranking, "
                        "and own it convincingly while keeping the others at the right altitude."
                    ),
                },
                {"type": "h3", "text": "45-Minute Interview Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Clarify (3 min):</strong> 100B pages, 100K QPS, p99 &lt; 200 ms, daily + NRT freshness, crawl is solved",
                        "<strong>Capacity (5 min):</strong> 5 KB/page → 500 TB raw → 100 TB compressed; 2,000 shards × 3 replicas",
                        "<strong>High-level arch (5 min):</strong> two halves — online serve + offline build; draw the diagram",
                        "<strong>Inverted index (8 min):</strong> term → posting list (doc_id, tf, positions); block compression; tiered storage",
                        "<strong>Sharding (5 min):</strong> doc-partition vs term-partition; pick doc; explain hotspot argument",
                        "<strong>Query path (5 min):</strong> rewrite → fan-out → BM25 top-K → merge → LTR rerank → snippet",
                        "<strong>Ranking (8 min):</strong> two stages, BM25 formula, LTR features, PageRank as one signal",
                        "<strong>Caching + freshness (3 min):</strong> result cache, NRT path, three-tier freshness model",
                        "<strong>Failures + trade-offs (3 min):</strong> shard down → degrade, hedging, doc-partition rationale",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "“100B pages, ~100 TB compressed inverted index across 2,000 shards × 3 replicas” — sets scale",
                        "“Doc-partition because hash(doc_id) avoids the 'the' hotspot” — answers the obvious follow-up",
                        "“Two-stage ranking: BM25 for recall, LambdaMART for precision” — shows ML literacy",
                        "“Hedged requests at p95 to tame scatter-gather tail latency” — distributed-systems depth",
                        "“Three-tier freshness: nightly + incremental + NRT” — handles 'how do you index breaking news?'",
                        "“Snippet generation is a separate doc-store hop” — shows you've thought past ranking",
                        "“Personalisation is final rerank, not candidate gen, to preserve cache hit rate” — non-obvious",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why not term-partition?</strong> A: Severe hotspots on common terms; one shard handling every 'the' query melts. Doc-partition spreads load uniformly via hash(doc_id), at the cost of fanning out every query.",
                        "<strong>Q: How do you handle phrase queries?</strong> A: Posting lists store positions; intersect doc_id sets and check position adjacency. Expensive, so we keep positions cached separately and skip them when not needed.",
                        "<strong>Q: How fresh can you be?</strong> A: NRT mini-index in RAM consumes Kafka of new docs and serves alongside the main index — fresh in minutes. Nightly batch absorbs the delta into base segments.",
                        "<strong>Q: How do you control p99 with 2,000 shards?</strong> A: Tied / hedged requests after p95, tiered serving (hot tier covers 90% of queries), per-shard request budgets with shed-on-overload.",
                        "<strong>Q: How do you measure ranking quality?</strong> A: NDCG@10 on a labelled probe set + interleaved live experiments measuring CTR and query-reformulation rate. Every model rollout is A/B'd.",
                        "<strong>Q: How do you handle a shard going down?</strong> A: Two replicas keep serving. If all three die, coordinator returns N-1 results and flags the SERP partial; SREs page; rebuild from object-storage segments.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "100B pages &nbsp;·&nbsp; 100K QPS sustained / 500K peak &nbsp;·&nbsp; "
                        "p99 &lt; 200 ms &nbsp;·&nbsp; 5 KB indexed / page &nbsp;·&nbsp; "
                        "500 TB raw → 100 TB compressed &nbsp;·&nbsp; 2,000 shards × 3 replicas &nbsp;·&nbsp; "
                        "BM25 (k1=1.2, b=0.75) &nbsp;·&nbsp; rerank top-200 with LambdaMART &nbsp;·&nbsp; "
                        "30–50% query-cache hit rate."
                    ),
                },
            ],
        },
    ],
}
