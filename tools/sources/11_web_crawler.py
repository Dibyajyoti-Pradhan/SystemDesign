"""Source for `11 - Web Crawler.pdf`."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design a Web Crawler",
    "subtitle": "Distributed crawler at Common Crawl / Googlebot scale",
    "read_time": "~ 45 minute read",
    "short_title": "Design a Web Crawler",
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
                        "Design a <strong>distributed web crawler</strong> like "
                        "<strong>Googlebot</strong> or <strong>Common Crawl</strong>. The "
                        "crawler discovers and downloads web pages, extracts links to feed "
                        "back into the frontier, deduplicates content, respects "
                        "<code>robots.txt</code> and per-host politeness, and stores the "
                        "harvested HTML for downstream search-indexing and knowledge-extraction "
                        "pipelines."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Pages to crawl?", "10 billion unique URLs (web-scale corpus)"],
                        ["Refresh cycle?", "30 days end-to-end (high-priority pages: 1 day)"],
                        ["Content types?", "HTML primarily; sniff non-HTML and skip binaries"],
                        ["Politeness?", "Obey robots.txt; max 1 req/sec per host"],
                        ["Output?", "Raw HTML (S3) + extracted links + content fingerprints"],
                        ["Languages?", "All; UTF-8 detection per page"],
                        ["JS rendering?", "Phase 2: headless Chrome for SPA-heavy hosts"],
                        ["Duplicate handling?", "URL dedup + near-dup content (SimHash)"],
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
                        ["Seed", "Accept seed URLs; bootstrap the frontier"],
                        ["Fetch", "Download HTML over HTTP(S); follow redirects"],
                        ["Parse", "Extract links + metadata + canonical tags"],
                        ["Enqueue", "Push new URLs back into the frontier"],
                        ["Dedup", "URL canonicalization + content near-dup detection"],
                        ["Politeness", "Obey robots.txt; per-host rate limit"],
                        ["Store", "Persist raw HTML and metadata for downstream pipelines"],
                        ["Refresh", "Re-crawl pages on TTL; prioritise by importance"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Throughput", "~3,860 fetches/sec sustained, ~8K peak"],
                        ["Storage", "~750 TB/year compressed deduped"],
                        ["Freshness", "30-day full refresh; 1-day for top-1% URLs"],
                        ["Politeness", "&le; 1 req/sec/host; honour Crawl-Delay"],
                        ["Robustness", "Survive zone outages; idempotent retries"],
                        ["Scalability", "Linear scale-out: add fetcher pods for more QPS"],
                        ["Extensibility", "Pluggable parsers (HTML, PDF, JSON-LD)"],
                    ],
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "The math",
            "blocks": [
                {"type": "h3", "text": "Throughput"},
                {
                    "type": "bullets",
                    "items": [
                        "Pages to crawl: <strong>10 billion</strong>",
                        "Refresh cycle: <strong>30 days</strong> &rArr; 333M pages/day",
                        "Sustained: 333M / 86,400 sec &asymp; <strong>3,860 fetches/sec</strong>",
                        "Peak (2&times; sustained): <strong>~8K fetches/sec</strong>",
                        "Each fetcher worker: ~10 concurrent fetches @ ~2 sec each &rarr; ~5 fetches/sec/worker &rArr; <strong>~1,600 workers</strong> sustained",
                    ],
                },
                {"type": "h3", "text": "Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "Avg page size: <strong>100 KB</strong> raw HTML",
                        "Daily raw: 333M &times; 100 KB &asymp; <strong>33 TB/day</strong>",
                        "Annual raw: 33 TB &times; 365 &asymp; <strong>12 PB/year</strong>",
                        "Dedup (~30% identical content removed) &rArr; ~8.4 PB/year",
                        "gzip compression (~5&times;) &rArr; <strong>~750 TB/year stored</strong>",
                        "URL set: 10B keys; Bloom filter @ ~10 bits/key &rArr; <strong>~12 GB</strong>",
                        "Content fingerprint set: 10B SimHashes &times; 8 B &rArr; <strong>~80 GB</strong>",
                    ],
                },
                {"type": "h3", "text": "DNS Pressure"},
                {
                    "type": "bullets",
                    "items": [
                        "Without cache: ~8K fetches/sec &asymp; <strong>~10K DNS qps</strong> at peak",
                        "With aggressive caching (TTL = host avg fetch interval): <strong>~50 qps</strong>",
                        "Cache hit rate: &gt; 99% (we re-hit the same hosts repeatedly)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "10B URLs &nbsp;&middot;&nbsp; 30-day refresh &rArr; "
                        "<strong>3,860 fetches/sec</strong> sustained, "
                        "<strong>~8K peak</strong> &nbsp;&middot;&nbsp; "
                        "33 TB/day raw &rArr; <strong>~750 TB/year</strong> after dedup &amp; gzip "
                        "&nbsp;&middot;&nbsp; URL Bloom filter <strong>~12 GB</strong>."
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
                        "The crawler is a feedback loop: the <strong>URL Frontier</strong> "
                        "feeds the <strong>Fetcher Pool</strong>, which downloads HTML; the "
                        "<strong>Content Parser</strong> extracts links and emits them back "
                        "into the frontier while the raw bytes flow into the "
                        "<strong>Content Store</strong> and the indexing pipeline. Three "
                        "out-of-band services keep the loop honest: <strong>DNS</strong>, "
                        "<strong>robots.txt cache</strong>, and the <strong>URL/Content "
                        "Dedup</strong> layer."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Core pipeline: frontier &rarr; DNS &rarr; fetch &rarr; parse, then a fan-out to link extraction (loop) and content storage / indexing (sink).",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_frontier {
        label="Scheduling"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        Seed [label="Seed URLs", fillcolor="#ead7fb"];
        Frontier [label="URL Frontier\n(priority + per-host)", fillcolor="#ead7fb"];
    }
    subgraph cluster_fetch {
        label="Fetch"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        DNS [label="DNS Resolver\n(cached)", fillcolor="#cbeedf"];
        Robots [label="robots.txt\nCache", fillcolor="#cbeedf"];
        Fetcher [label="Fetcher Pool\n(~1,600 workers)", fillcolor="#cbeedf"];
    }
    subgraph cluster_parse {
        label="Parse"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        Parser [label="Content Parser\n(HTML, charset)", fillcolor="#fff2c9"];
        LinkX  [label="Link Extractor\n+ canonicalize", fillcolor="#fff2c9"];
    }
    subgraph cluster_dedup {
        label="Dedup"; style="rounded,dashed"; color="#b8362e"; fontcolor="#b8362e";
        URLSet  [label="URL Set\n(Bloom + RocksDB)", fillcolor="#fbd7c5"];
        SimHash [label="Content Fingerprint\n(SimHash / MinHash)", fillcolor="#fbd7c5"];
    }
    subgraph cluster_store {
        label="Store + Index"; style="rounded,dashed"; color="#2e57b8"; fontcolor="#2e57b8";
        S3   [label="Raw HTML\n(S3 / WARC)", fillcolor="#dbe6fb"];
        HBase[label="Page Metadata\n(HBase)",     fillcolor="#dbe6fb"];
        Index[label="Index Pipeline\n(inverted idx, KG)", fillcolor="#dbe6fb"];
    }

    Seed -> Frontier;
    Frontier -> DNS [label="dequeue"];
    DNS -> Robots;
    Robots -> Fetcher [label="allow?"];
    Fetcher -> Parser [label="HTML bytes"];
    Parser  -> LinkX;
    Parser  -> S3    [label="raw"];
    Parser  -> SimHash [label="near-dup?"];
    SimHash -> HBase;
    LinkX   -> URLSet [label="seen?"];
    URLSet  -> Frontier [label="new URL"];
    HBase   -> Index;
    S3      -> Index;
}
""",
                },
                {"type": "h3", "text": "Component Responsibilities"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>URL Frontier:</strong> prioritised, per-host queue feeding fetchers; the heart of the crawler",
                        "<strong>DNS Resolver:</strong> async resolver with massive cache; ~99% hit rate",
                        "<strong>robots.txt Cache:</strong> per-host fetched once per 24h; enforces Disallow + Crawl-Delay",
                        "<strong>Fetcher Pool:</strong> stateless async HTTP workers; ~1,600 pods sustained",
                        "<strong>Content Parser:</strong> charset detection, HTML &rarr; DOM, extract links + canonical tag",
                        "<strong>Dedup:</strong> Bloom filter for URL membership; SimHash for near-dup content",
                        "<strong>Content Store:</strong> S3 / WARC files for raw HTML; HBase for metadata index",
                        "<strong>Index Pipeline:</strong> downstream MapReduce / Spark builds inverted index + KG",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "URL Frontier (Mercator)",
            "subtitle": "Priority + politeness queue",
            "blocks": [
                {"type": "h3", "text": "Two-Level Queue"},
                {
                    "type": "para",
                    "text": (
                        "The frontier follows the <strong>Mercator</strong> design: "
                        "<strong>front queues</strong> hold URLs sorted by priority (importance, "
                        "freshness, refresh policy); <strong>back queues</strong> hold URLs grouped "
                        "by host and feed the fetchers. A back-queue selector enforces politeness "
                        "by ensuring each fetcher worker only ever pulls from one host at a time."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Mercator-style frontier: priority front queues feed per-host back queues; a heap-driven router picks the next host whose politeness window has elapsed.",
                    "dot": r"""
digraph F {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_front {
        label="Front Queues (priority)"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        F1 [label="P1: hourly\n(news, top-1%)", fillcolor="#cbeedf"];
        F2 [label="P2: daily\n(top-10%)",       fillcolor="#cbeedf"];
        F3 [label="P3: weekly\n(rest)",         fillcolor="#cbeedf"];
        F4 [label="P4: 30-day\n(tail)",         fillcolor="#cbeedf"];
    }
    Router [label="Back-Queue\nRouter\n(host -> queue)", shape=hexagon, fillcolor="#fff2c9", color="#b8862e"];
    subgraph cluster_back {
        label="Back Queues (one per host)"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        B1 [label="back: nyt.com",   fillcolor="#ead7fb"];
        B2 [label="back: github.com", fillcolor="#ead7fb"];
        B3 [label="back: reddit.com", fillcolor="#ead7fb"];
        Bn [label="...thousands more", fillcolor="#ead7fb"];
    }
    Heap [label="Min-Heap\n(host, next_fetch_at)", shape=hexagon, fillcolor="#fbd7c5", color="#b8362e"];
    Pool [label="Fetcher\nWorker Pool", fillcolor="#dbe6fb"];

    F1 -> Router;
    F2 -> Router;
    F3 -> Router;
    F4 -> Router;
    Router -> B1;
    Router -> B2;
    Router -> B3;
    Router -> Bn;
    B1 -> Heap;
    B2 -> Heap;
    B3 -> Heap;
    Bn -> Heap;
    Heap -> Pool [label="next ready host"];
}
""",
                },
                {"type": "h3", "text": "Politeness Scheduler (pseudocode)"},
                {
                    "type": "code",
                    "text": (
                        "# Per-host min-heap keyed by next_fetch_at\n"
                        "# Invariant: a host is in the heap iff its back-queue is non-empty\n"
                        "\n"
                        "def next_url():\n"
                        "    host, ready_at = heap.peek()\n"
                        "    if now() < ready_at:\n"
                        "        sleep(ready_at - now())\n"
                        "    heap.pop()\n"
                        "    url = back_queue[host].pop_front()\n"
                        "    crawl_delay = robots[host].crawl_delay or 1.0  # &gt;=1 sec/host\n"
                        "    if back_queue[host]:\n"
                        "        heap.push((host, now() + crawl_delay))\n"
                        "    return url\n"
                        "\n"
                        "def enqueue(url):\n"
                        "    host = canonical_host(url)\n"
                        "    was_empty = not back_queue[host]\n"
                        "    back_queue[host].push_back(url)\n"
                        "    if was_empty:\n"
                        "        heap.push((host, now()))  # immediately ready"
                    ),
                },
                {"type": "h3", "text": "Frontier Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>In-memory:</strong> hot back-queues fit in RAM (recent + active hosts)",
                        "<strong>On-disk overflow:</strong> RocksDB / Kafka per partition for cold tail",
                        "<strong>Sharding:</strong> partition by host hash so each frontier shard owns disjoint hosts",
                        "<strong>Persistence:</strong> WAL on every dequeue/enqueue; recover state on crash",
                    ],
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "DNS & Politeness",
            "subtitle": "Resolving and respecting hosts",
            "blocks": [
                {"type": "h3", "text": "DNS Resolver"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Async resolver:</strong> non-blocking (c-ares, getdns); thousands of in-flight lookups",
                        "<strong>Local cache:</strong> per-fetcher LRU keyed by host; honour TTL but cap at 1 day",
                        "<strong>Shared cache:</strong> Redis-backed cluster cache: ~10K hosts &times; ~64 B = trivial",
                        "<strong>Negative cache:</strong> cache NXDOMAIN for 60 sec to avoid hammering bad hosts",
                        "<strong>Effect:</strong> ~10K qps &rarr; <strong>~50 qps</strong> with cache (hit rate &gt;99%)",
                    ],
                },
                {"type": "h3", "text": "robots.txt"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Fetch once per host per 24 h;</strong> store parsed allow/disallow + Crawl-Delay",
                        "<strong>Match user-agent:</strong> identify ourselves (e.g. <code>MyCrawler/1.0</code>) and obey wildcard fallbacks",
                        "<strong>Apply before fetch:</strong> if disallowed, drop URL and emit a metric",
                        "<strong>Crawl-Delay:</strong> overrides our default of 1 req/sec when host requests slower",
                    ],
                },
                {"type": "h3", "text": "Per-Host vs Per-IP Politeness"},
                {
                    "type": "table",
                    "headers": ["Strategy", "Pros", "Cons"],
                    "rows": [
                        ["Per-host", "Simple; matches robots.txt scope",
                         "Co-hosted sites on same IP get hammered (e.g. shared hosting)"],
                        ["Per-IP", "Friendly to shared hosting and CDNs",
                         "Need reverse-DNS; one big IP (Cloudflare) blocks unrelated sites"],
                        ["Hybrid", "Default per-host; per-IP cap as upper bound",
                         "More state; reconcile when DNS changes; complexity"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Recommendation",
                    "body": (
                        "Start with <strong>per-host</strong> politeness (1 req/sec or Crawl-Delay). "
                        "Layer on a <strong>per-IP cap</strong> (e.g., 10 req/sec/IP) only after you "
                        "see complaints from shared-hosting providers."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Fetcher Pool",
            "subtitle": "Async HTTP workers",
            "blocks": [
                {"type": "h3", "text": "Worker Design"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Async I/O:</strong> Python asyncio + aiohttp, or Go net/http with goroutines",
                        "<strong>Concurrency:</strong> ~10 in-flight fetches per worker; bound by mem + per-host limit",
                        "<strong>Timeouts:</strong> 5 sec connect, 30 sec total; abandon stragglers fast",
                        "<strong>Retry:</strong> exponential backoff for 5xx / network errors; max 3 retries",
                        "<strong>Body size cap:</strong> 10 MB; truncate larger pages",
                        "<strong>HTTPS:</strong> reuse TLS sessions; ALPN HTTP/2 where supported",
                    ],
                },
                {"type": "h3", "text": "Sizing Math"},
                {
                    "type": "bullets",
                    "items": [
                        "Average fetch wall time: ~2 sec (TCP + TLS + first-byte + read)",
                        "Per-worker QPS: 10 concurrent / 2 sec = 5 fetches/sec",
                        "Sustained workers: 3,860 / 5 = <strong>~770</strong>",
                        "Headroom (HA + retry + tail): 2&times; &rArr; <strong>~1,600 workers</strong>",
                        "Each worker pod ~256 MB &rArr; <strong>~400 GB</strong> total fetcher memory",
                    ],
                },
                {"type": "h3", "text": "Fetch Loop (pseudocode)"},
                {
                    "type": "code",
                    "text": (
                        "async def fetch_loop():\n"
                        "    while True:\n"
                        "        url = await frontier.next_url()\n"
                        "        host = canonical_host(url)\n"
                        "        ip   = await dns.resolve(host)\n"
                        "        if not robots[host].allows(url):\n"
                        "            metrics.inc('robots_disallow')\n"
                        "            continue\n"
                        "        try:\n"
                        "            resp = await http.get(url, host_ip=ip,\n"
                        "                                  timeout=30, max_bytes=10_000_000)\n"
                        "        except (Timeout, ConnError) as e:\n"
                        "            await retry_or_drop(url, e)\n"
                        "            continue\n"
                        "        if resp.status in (301, 302):\n"
                        "            await frontier.enqueue(canonicalize(resp.location))\n"
                        "            continue\n"
                        "        if resp.status == 200 and is_html(resp):\n"
                        "            await parser_queue.put((url, resp.body))"
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Content Parser & Link Extraction",
            "subtitle": "From bytes to URLs",
            "blocks": [
                {"type": "h3", "text": "Parsing Stages"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Charset detection:</strong> sniff UTF-8 / Latin-1 / declared meta",
                        "<strong>HTML &rarr; DOM:</strong> lxml or Cheerio; tolerant of malformed markup",
                        "<strong>Canonical tag:</strong> if <code>&lt;link rel=canonical&gt;</code>, prefer that URL",
                        "<strong>Extract links:</strong> all <code>&lt;a href&gt;</code>, plus <code>src</code> attrs as configured",
                        "<strong>Normalize:</strong> strip fragments, lowercase host, sort query params, drop session IDs",
                        "<strong>Filter:</strong> reject schemes other than http(s); reject blacklisted TLDs",
                        "<strong>Emit:</strong> push (url, source_url, anchor_text) tuples to the dedup layer",
                    ],
                },
                {"type": "h3", "text": "URL Canonicalization"},
                {
                    "type": "code",
                    "text": (
                        "def canonicalize(url):\n"
                        "    u = urlparse(url)\n"
                        "    scheme = u.scheme.lower()\n"
                        "    host   = u.hostname.lower().rstrip('.')\n"
                        "    if (scheme, u.port) in [('http', 80), ('https', 443)]:\n"
                        "        netloc = host\n"
                        "    else:\n"
                        "        netloc = f'{host}:{u.port}' if u.port else host\n"
                        "    path = re.sub(r'/+', '/', u.path) or '/'\n"
                        "    # remove tracking params; sort the rest\n"
                        "    params = [(k, v) for k, v in parse_qsl(u.query)\n"
                        "              if k not in TRACKING_PARAMS]\n"
                        "    query = urlencode(sorted(params))\n"
                        "    # drop fragment entirely\n"
                        "    return urlunparse((scheme, netloc, path, '', query, ''))"
                    ),
                },
                {"type": "h3", "text": "Anchor-text Signal"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Save anchor text:</strong> downstream PageRank-style scoring uses it",
                        "<strong>Source &rarr; target graph:</strong> store (src_url, dst_url, anchor) triples",
                        "<strong>Fan-out cap:</strong> &le; 1,000 outgoing links per page (defend against link bombs)",
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "URL Deduplication",
            "subtitle": "Have we seen this URL?",
            "blocks": [
                {"type": "h3", "text": "Two-Layer Approach"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Bloom filter (in-memory):</strong> fast probabilistic 'definitely-new' test",
                        "<strong>RocksDB (on-disk):</strong> exact set; lookup on Bloom-positive to confirm",
                        "<strong>Why both:</strong> Bloom lets us skip 99% of disk reads; RocksDB resolves the 1%",
                    ],
                },
                {"type": "h3", "text": "Bloom Filter Sizing"},
                {
                    "type": "bullets",
                    "items": [
                        "Keys: <strong>10 billion</strong> URLs (target capacity)",
                        "Bits/key: <strong>~10</strong> &rArr; false-positive rate ~1%",
                        "Total bits: 10B &times; 10 = 100 Gbit &rArr; <strong>~12 GB</strong>",
                        "Hash functions: <strong>k = 7</strong> (optimal for ~10 bits/key)",
                        "Sharded: 64 partitions of ~190 MB each across the dedup tier",
                    ],
                },
                {
                    "type": "code",
                    "text": (
                        "# URL membership check (probabilistic + exact backstop)\n"
                        "def is_new_url(url):\n"
                        "    h = url_canonical(url)\n"
                        "    if not bloom.might_contain(h):\n"
                        "        bloom.add(h)\n"
                        "        rocks.put(h, 1)\n"
                        "        return True   # definitely new\n"
                        "    # Bloom hit: could be false positive (~1%)\n"
                        "    if rocks.get(h) is None:\n"
                        "        rocks.put(h, 1)\n"
                        "        return True\n"
                        "    return False      # already seen"
                    ),
                },
                {"type": "h3", "text": "Tunings"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Counting Bloom:</strong> if you ever need to remove URLs (e.g., re-crawl invalidation)",
                        "<strong>Cuckoo filter:</strong> better fp rate at the same memory; supports deletion",
                        "<strong>Partition by host hash:</strong> co-locates URLs from the same host for cache locality",
                    ],
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Content Deduplication",
            "subtitle": "SimHash & near-duplicates",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "URL dedup catches obvious repeats. <strong>Content dedup</strong> catches "
                        "the long tail of mirror sites, syndication, boilerplate, and tracker-only "
                        "differences. Use a <strong>locality-sensitive hash</strong> "
                        "(SimHash for text, MinHash for sets) so that near-identical pages collapse "
                        "into the same bucket."
                    ),
                },
                {"type": "h3", "text": "SimHash Algorithm"},
                {
                    "type": "code",
                    "text": (
                        "# 64-bit SimHash over n-gram shingles of the page body\n"
                        "def simhash(tokens, bits=64):\n"
                        "    v = [0] * bits\n"
                        "    for tok in tokens:\n"
                        "        h = hash64(tok)\n"
                        "        for i in range(bits):\n"
                        "            v[i] += 1 if (h &gt;&gt; i) &amp; 1 else -1\n"
                        "    fingerprint = 0\n"
                        "    for i in range(bits):\n"
                        "        if v[i] &gt; 0:\n"
                        "            fingerprint |= (1 &lt;&lt; i)\n"
                        "    return fingerprint\n"
                        "\n"
                        "def is_near_duplicate(fp, store, hamming_thresh=3):\n"
                        "    # Index fp into 4 banded tables of 16 bits each\n"
                        "    for band in band_keys(fp):\n"
                        "        for cand in store.lookup(band):\n"
                        "            if popcount(fp ^ cand) &lt;= hamming_thresh:\n"
                        "                return True\n"
                        "    store.insert(fp)\n"
                        "    return False"
                    ),
                },
                {"type": "h3", "text": "SimHash vs Exact Hash"},
                {
                    "type": "table",
                    "headers": ["Property", "Exact (SHA-256)", "SimHash"],
                    "rows": [
                        ["Catches near-dups", "No (1-bit change &rarr; new hash)",
                         "Yes (Hamming distance &le; 3)"],
                        ["Index size", "32 B / page",
                         "8 B / page"],
                        ["Lookup", "O(1) hash map",
                         "Banded LSH; O(1) per band"],
                        ["False positives", "Effectively 0",
                         "~ small; tunable by Hamming threshold"],
                        ["Use case", "Byte-identical detection",
                         "Boilerplate / mirror / syndication"],
                    ],
                },
                {"type": "h3", "text": "Pipeline Placement"},
                {
                    "type": "bullets",
                    "items": [
                        "Compute fingerprint after parsing &amp; boilerplate stripping",
                        "Skip storage write if near-dup found (saves ~30% of bytes)",
                        "Still record the URL &rarr; canonical-page mapping for reverse lookups",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Storage Tiers",
            "subtitle": "Hot / warm / cold",
            "blocks": [
                {"type": "h3", "text": "Tiered Architecture"},
                {
                    "type": "table",
                    "headers": ["Tier", "Backend", "Contents", "Latency", "Cost"],
                    "rows": [
                        ["Hot", "HBase / Cassandra",
                         "Page metadata, last 7 days raw HTML for active pages",
                         "ms",
                         "~$0.10 / GB-mo"],
                        ["Warm", "S3 Standard (WARC files)",
                         "Compressed raw HTML, 90-day window",
                         "10-100 ms",
                         "~$0.023 / GB-mo"],
                        ["Cold", "S3 Glacier",
                         "Older WARC archives, 1-7 yr",
                         "min-hours (restore)",
                         "~$0.004 / GB-mo"],
                    ],
                },
                {"type": "h3", "text": "Page Metadata Schema (HBase)"},
                {
                    "type": "code",
                    "text": (
                        "-- Logical schema for page metadata\n"
                        "CREATE TABLE page_metadata (\n"
                        "  url_hash       BINARY(16) PRIMARY KEY,   -- md5(canonical_url)\n"
                        "  canonical_url  TEXT NOT NULL,\n"
                        "  host           VARCHAR(253) NOT NULL,\n"
                        "  http_status    SMALLINT,\n"
                        "  content_type   VARCHAR(64),\n"
                        "  content_len    INT,\n"
                        "  simhash        BIGINT,                   -- 64-bit fingerprint\n"
                        "  s3_warc_key    VARCHAR(255),             -- pointer to raw bytes\n"
                        "  s3_warc_offset BIGINT,\n"
                        "  fetched_at     TIMESTAMP,\n"
                        "  next_refresh   TIMESTAMP,                -- frontier picks this up\n"
                        "  priority       TINYINT,                  -- 1=hourly..4=monthly\n"
                        "  outlink_count  INT,\n"
                        "  INDEX idx_host         (host),\n"
                        "  INDEX idx_next_refresh (next_refresh),\n"
                        "  INDEX idx_simhash      (simhash)\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "WARC Files"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Format:</strong> Web ARChive (ISO 28500); standard for crawl dumps",
                        "<strong>Roll-over:</strong> 1 GB per WARC file; ~33K files/day",
                        "<strong>Compression:</strong> per-record gzip; ~5&times; compression on HTML",
                        "<strong>Index:</strong> CDX index file maps url_hash &rarr; (warc_key, offset)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why HBase + S3?",
                    "body": (
                        "HBase gives random access by url_hash with mutable metadata "
                        "(refresh times, priority, fingerprints). S3 stores the bulky immutable "
                        "raw HTML cheaply. Splitting hot metadata from cold body bytes is the "
                        "key cost lever at petabyte scale."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Refresh & Recrawl Policy",
            "subtitle": "Keeping the index fresh",
            "blocks": [
                {"type": "h3", "text": "Priority Tiers"},
                {
                    "type": "table",
                    "headers": ["Tier", "Examples", "Refresh"],
                    "rows": [
                        ["P1: hourly", "News homepages, twitter trending, status pages",
                         "1 hour"],
                        ["P2: daily", "Top-10% by inlinks; popular blogs",
                         "1 day"],
                        ["P3: weekly", "Mid-tail content sites",
                         "7 days"],
                        ["P4: monthly", "Long tail (&gt;90% of corpus)",
                         "30 days"],
                    ],
                },
                {"type": "h3", "text": "Adaptive Refresh"},
                {
                    "type": "bullets",
                    "items": [
                        "Track <strong>change rate</strong> per URL: did the simhash differ on last refetch?",
                        "If unchanged for k consecutive cycles &rArr; <strong>downgrade</strong> priority tier",
                        "If changed every cycle &rArr; <strong>upgrade</strong> tier",
                        "Use ETag / Last-Modified / If-None-Match to skip unchanged pages cheaply",
                    ],
                },
                {"type": "h3", "text": "Sitemaps & Pings"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>sitemap.xml:</strong> trust hosts that publish one; seed frontier with it",
                        "<strong>RSS / Atom:</strong> high-signal change notification for blogs",
                        "<strong>PubSubHubbub / WebSub:</strong> push-based; instant notification of changes",
                        "<strong>Effect:</strong> reduces wasted refetches by ~40% for cooperating hosts",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "BFS vs DFS",
                    "body": (
                        "Crawl breadth-first. BFS keeps the frontier diverse and politeness-friendly "
                        "(many hosts, never deep on one). DFS would hammer a single host and miss "
                        "broad coverage. Add priority on top of BFS: high-importance pages jump "
                        "the queue but BFS is the default ordering."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Scalability & Distribution",
            "subtitle": "Sharding the crawler",
            "blocks": [
                {"type": "h3", "text": "Partitioning"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Shard by host hash:</strong> a single host always lands on the same frontier shard",
                        "<strong>Why host, not URL:</strong> politeness state (rate, robots) is per-host",
                        "<strong>Re-sharding:</strong> consistent hashing &rArr; only 1/N of hosts move on scale change",
                        "<strong>Cross-shard links:</strong> emit to a Kafka topic partitioned by host hash",
                    ],
                },
                {"type": "h3", "text": "Topology"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Frontier shards:</strong> ~64 partitions; each owns ~150K hosts",
                        "<strong>Fetcher pool:</strong> stateless; any pod can fetch from any shard",
                        "<strong>Parser pool:</strong> stateless; consumes from per-shard Kafka topic",
                        "<strong>Dedup tier:</strong> sharded Bloom + RocksDB by url_hash prefix",
                        "<strong>Object storage:</strong> S3 is region-global; HBase is geo-replicated",
                    ],
                },
                {"type": "h3", "text": "Backpressure"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Kafka between stages:</strong> absorb fetcher / parser rate mismatches",
                        "<strong>Frontier soft cap:</strong> if back-queues exceed M URLs/host, stop accepting",
                        "<strong>Drop priority tail:</strong> under sustained overload, drop P4 enqueues first",
                        "<strong>Auto-scale fetchers</strong> on queue depth and per-pod CPU",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Stateless workers, stateful queues",
                    "body": (
                        "Push <em>all</em> stateful concerns into the frontier and dedup layers. "
                        "Keep fetchers and parsers stateless so they can be scaled, replaced, or "
                        "restarted at any time. This is the same pattern as MapReduce: stateless "
                        "compute, durable shuffle."
                    ),
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
                        ["Fetcher pod crash",
                         "In-flight URLs lost",
                         "Pod liveness; missed heartbeat",
                         "K8s reschedules; URLs re-emerge from frontier WAL"],
                        ["Frontier shard down",
                         "Hosts on that shard pause",
                         "Replica lag alert",
                         "Promote standby; replay WAL; resume"],
                        ["DNS outage",
                         "Most fetches fail",
                         "DNS error rate",
                         "Failover to secondary resolver; serve from cache"],
                        ["Slow host (tarpit)",
                         "Workers stuck on it",
                         "Per-host p99 latency",
                         "Per-host timeout; circuit-break for 1 h"],
                        ["Bloom corruption",
                         "Re-fetch already-seen URLs",
                         "Disk checksum mismatch",
                         "Rebuild from RocksDB snapshot; takes hours"],
                        ["S3 region outage",
                         "Cannot persist new HTML",
                         "PUT error rate",
                         "Buffer in local disk; replay when S3 recovers"],
                        ["Spider trap (infinite URLs)",
                         "Frontier pollution",
                         "Per-host URL growth",
                         "Cap URLs/host; depth limit; pattern detection"],
                        ["Robots violation",
                         "Host complaints; IP ban",
                         "Webmaster contact; abuse@",
                         "Revalidate robots cache; honor Retry-After"],
                    ],
                },
                {"type": "h3", "text": "Idempotency"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Frontier dequeue:</strong> at-least-once; URLs may be fetched twice on crash",
                        "<strong>Storage writes:</strong> idempotent on (url_hash, fetched_at)",
                        "<strong>Dedup checks:</strong> safe under retry; Bloom + RocksDB are monotonic",
                        "<strong>Effect:</strong> end-to-end at-least-once; duplicates collapsed by url_hash key",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Spider Traps",
                    "body": (
                        "Calendars, faceted-search pages, session IDs in URLs, and infinite "
                        "redirect chains can generate unbounded URLs from a single host. "
                        "Defend with <strong>per-host URL caps</strong>, <strong>depth limits</strong>, "
                        "<strong>query-param fingerprinting</strong>, and <strong>refresh "
                        "demotion</strong> on near-duplicate detection."
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
                        ["Traversal order", "BFS + priority",
                         "Diverse coverage, polite. DFS would hammer hosts and miss breadth."],
                        ["Politeness scope", "Per-host (with per-IP cap)",
                         "Matches robots.txt scope. Pure per-IP is friendlier to shared hosting but loses cleanliness."],
                        ["URL dedup", "Bloom + RocksDB",
                         "Fast in-memory check, exact backstop. Pure RocksDB is too slow; pure Bloom has false positives."],
                        ["Content dedup", "SimHash (LSH)",
                         "Catches near-duplicates at 8 B/page. Exact hash misses 30%+ of mirror content."],
                        ["Frontier", "Mercator two-level queue",
                         "Decouples priority from politeness. A single FIFO queue cannot do both."],
                        ["Storage split", "HBase metadata + S3 WARC",
                         "Cheap bulk + fast metadata. All-HBase is too expensive; all-S3 has no random access."],
                        ["Refresh policy", "Adaptive (4 tiers)",
                         "Spend budget on changing pages. Fixed-period wastes ~40% on static content."],
                        ["JS rendering", "Phase 2 only",
                         "Headless Chrome is ~50&times; more expensive per fetch. Worth it only for SPA-heavy hosts."],
                        ["Storage tier", "S3 Glacier for &gt; 90 d",
                         "Cuts cost ~6&times;. Restore latency is hours, but cold archives are rarely queried."],
                        ["Fresh vs polite", "Politeness wins",
                         "Never break robots.txt. Freshness loss recovered with sitemaps and PubSubHubbub."],
                    ],
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
                        "Web crawler is a classic SD interview because it forces you to balance "
                        "five orthogonal concerns: scale, politeness, dedup, freshness, and "
                        "storage cost. Lead with the loop, anchor the math, and defend trade-offs."
                    ),
                },
                {"type": "h3", "text": "45-Minute Interview Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (2 min):</strong> 10B URLs, 30-day refresh, polite, near-dup detection",
                        "<strong>Capacity (5 min):</strong> 3,860 fetches/sec, 33 TB/day raw, 750 TB/yr stored",
                        "<strong>High-level arch (4 min):</strong> frontier &rarr; DNS &rarr; fetch &rarr; parse &rarr; {links, store, index}",
                        "<strong>Frontier deep dive (8 min):</strong> Mercator front+back queues; politeness heap",
                        "<strong>Dedup deep dive (8 min):</strong> Bloom for URLs, SimHash for content",
                        "<strong>Storage (5 min):</strong> HBase metadata + S3 WARC + Glacier cold",
                        "<strong>Refresh (4 min):</strong> 4 priority tiers + adaptive demotion",
                        "<strong>Failures (4 min):</strong> spider traps, slow hosts, robots violations",
                        "<strong>Wrap (5 min):</strong> trade-offs and what you'd build next (JS rendering)",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "&ldquo;3,860 fetches/sec sustained, ~8K peak&rdquo; &mdash; capacity math, not magic",
                        "&ldquo;Mercator two-level queue&rdquo; &mdash; cite the canonical design by name",
                        "&ldquo;Politeness is per-host with per-IP cap&rdquo; &mdash; nuanced, correct",
                        "&ldquo;Bloom filter at 10 bits/key &rarr; 12 GB for 10B URLs&rdquo; &mdash; exact memory math",
                        "&ldquo;SimHash with Hamming threshold 3&rdquo; &mdash; concrete near-dup parameter",
                        "&ldquo;HBase + S3 + Glacier&rdquo; &mdash; cost-aware tiered storage",
                        "&ldquo;Adaptive refresh on simhash drift&rdquo; &mdash; freshness without waste",
                        "&ldquo;Idempotent at-least-once&rdquo; &mdash; recovery story is correct, not hand-wavy",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: How do you avoid hammering one host?</strong> A: Per-host back-queue + min-heap on next_fetch_at; honour robots Crawl-Delay, default 1 req/sec.",
                        "<strong>Q: Why Bloom + RocksDB instead of just one?</strong> A: Bloom skips 99% of disk reads; RocksDB resolves the ~1% Bloom false-positives. Pure Bloom would re-fetch 1% of URLs forever.",
                        "<strong>Q: What about JavaScript-rendered pages?</strong> A: Phase 2: headless Chrome pool, ~50&times; more expensive; reserve for SPA-heavy hosts identified by content signals.",
                        "<strong>Q: How do you detect spider traps?</strong> A: Per-host URL growth metric, depth limits, query-param fingerprint, simhash-driven refresh demotion.",
                        "<strong>Q: What if the frontier shard crashes?</strong> A: WAL on disk; standby promotes and replays. URLs may be fetched twice (at-least-once); idempotent storage by url_hash.",
                        "<strong>Q: Why not Cassandra over HBase?</strong> A: Either works; HBase has stronger consistency on row updates (refresh timestamps), Cassandra wins on multi-region writes. Pick based on existing stack.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "10B URLs &nbsp;&middot;&nbsp; 30-day refresh &nbsp;&middot;&nbsp; "
                        "<strong>3,860 fetches/sec</strong> sustained, <strong>~8K peak</strong> "
                        "&nbsp;&middot;&nbsp; 100 KB avg page &nbsp;&middot;&nbsp; "
                        "<strong>33 TB/day</strong> raw &rArr; <strong>~750 TB/year</strong> stored "
                        "&nbsp;&middot;&nbsp; <strong>~12 GB</strong> Bloom filter "
                        "&nbsp;&middot;&nbsp; <strong>1 req/sec/host</strong> politeness "
                        "&nbsp;&middot;&nbsp; <strong>~1,600 fetcher workers</strong>."
                    ),
                },
            ],
        },
    ],
}
