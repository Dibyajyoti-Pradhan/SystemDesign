"""Source for `18 - Facebook News Feed.pdf` — personalized, ML-ranked timeline."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Facebook News Feed",
    "subtitle": "personalised, ML-ranked timeline of friends, pages, and groups at planet scale",
    "read_time": "~ 45 minute read",
    "short_title": "Design Facebook News Feed",
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
                        "Design <strong>Facebook News Feed</strong>: the home screen that shows each "
                        "user a personalised stream of posts from <strong>friends, pages, and groups</strong> "
                        "they follow. The feed is <strong>not chronological</strong> — it is "
                        "ML-ranked. The system must ingest ~1B posts/day, serve ~10B feed reads/day, "
                        "rank with ≤300 ms latency, and remain available globally."
                    ),
                },
                {"type": "h3", "text": "Key Features"},
                {
                    "type": "bullets",
                    "items": [
                        "Personalised home feed — posts from friends, followed pages, joined groups",
                        "ML ranking by engagement, affinity, recency, content type, negative signals",
                        "Pull-to-refresh + infinite scroll; pagination with stable cursors",
                        "Mixed content types — text, photo, video, link preview, life events, ads",
                        "Engagement primitives — react, comment, share, save, hide, snooze, unfollow",
                        "Real-time injection of viral / trending posts",
                        "Cross-device sync — last seen position, dismissed posts, see-first lists",
                    ],
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Scope?", "Home News Feed only; profile timelines, Stories, Reels out of scope"],
                        ["Scale?", "3B MAU, 2B DAU, ~1B posts/day, ~10B feed reads/day"],
                        ["Ranking?", "ML personalisation; not chronological; explainable signals"],
                        ["Latency?", "p99 feed load &lt; 1.5s end-to-end; ranking &lt; 300 ms"],
                        ["Freshness?", "&lt; 60 sec for friend posts; viral injection &lt; 5 min"],
                        ["Average friends/follows?", "~350 friends + ~200 pages/groups = ~550 sources"],
                        ["Average post candidates per read?", "~1,500 fresh + ~3,000 unseen = ~5K to rank"],
                        ["Geography?", "Global; multi-region active-active reads, single-region writes per user"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Assumption",
                    "body": (
                        "Design for <strong>2B DAU</strong>, <strong>1B posts/day</strong>, "
                        "<strong>10B feed reads/day</strong>, and <strong>ML ranking under 300 ms</strong>. "
                        "Every architectural choice flows from those four numbers."
                    ),
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
                    "type": "bullets",
                    "items": [
                        "<strong>Post:</strong> create text/photo/video/link post; choose audience",
                        "<strong>Feed read:</strong> GET ranked, personalised feed with cursor pagination",
                        "<strong>Engagement:</strong> react, comment, share, save, hide, snooze",
                        "<strong>Negative feedback:</strong> hide, snooze 30d, unfollow, report",
                        "<strong>See-first / favorites:</strong> users pin sources for promotion",
                        "<strong>Friend / page / group graph:</strong> source of candidate posts",
                        "<strong>Counter sync:</strong> reaction, comment, share counters across devices",
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Availability", "99.99% for read path; 99.9% for write path"],
                        ["Latency", "p50 feed &lt; 400 ms, p99 &lt; 1.5s; ranking &lt; 300 ms"],
                        ["Freshness", "Friend posts visible &lt; 60 s; viral injection &lt; 5 min"],
                        ["Consistency", "Eventual for feed; read-your-writes for the poster's own post"],
                        ["Throughput", "~115K reads/sec avg, ~300K peak; ~12K post writes/sec"],
                        ["Durability", "Posts: 11 nines on BLOB / 5 nines on metadata"],
                        ["Scale", "10× growth without redesign; horizontal everywhere"],
                        ["Cost", "Optimise ranking compute and Memcached fleet — the dominant lines"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Read-Your-Writes",
                    "body": (
                        "When you publish a post you must see it instantly in your own feed even "
                        "before fan-out completes. We solve this with a <strong>self-injection</strong> "
                        "step: the poster's own client receives a synthetic feed entry referencing the "
                        "fresh post_id. Other followers see it after fan-out (push) or on next pull "
                        "(celebrities)."
                    ),
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
                        "MAU: <strong>3B</strong>; DAU: <strong>2B</strong>",
                        "Posts/day: <strong>1B</strong> → 1B / 86,400 ≈ <strong>11,574 ≈ 12K writes/sec</strong>",
                        "Feed opens/user/day: <strong>5</strong> avg → 2B × 5 = <strong>10B feed reads/day</strong>",
                        "Read QPS avg: 10B / 86,400 ≈ <strong>115,740 ≈ 115K reads/sec</strong>",
                        "Peak QPS (2.5× diurnal skew): <strong>~300K reads/sec</strong>",
                        "Engagement events (react+comment+share): ~10× post rate ≈ <strong>120K/sec</strong>",
                    ],
                },
                {"type": "h3", "text": "Ranking Cost"},
                {
                    "type": "bullets",
                    "items": [
                        "Candidates ranked per feed read: <strong>~5,000</strong> (after candidate filtering)",
                        "Total feature evaluations/sec: 115K reads × 5K candidates = <strong>575M scores/sec</strong>",
                        "Per-score budget: 300 ms / 5K = <strong>60 µs per candidate</strong>",
                        "→ pre-compute embeddings; serve via DLRM inference on GPU/TPU pools",
                        "Top-K returned per read: <strong>~30 stories</strong> (page 1) + paginate",
                    ],
                },
                {"type": "h3", "text": "Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "Post metadata: ~1 KB × 1B = <strong>1 TB/day</strong> → ~365 TB/year metadata",
                        "Photo BLOB: ~250 KB × 30% of posts (300M) = <strong>75 TB/day</strong> media",
                        "Video BLOB: ~3 MB × 5% of posts (50M) = <strong>150 TB/day</strong> media",
                        "5-year corpus: ~411 PB media + ~1.8 PB metadata; tiered to cold storage",
                        "Feed timeline (push fan-out): see §05 — ~30B inserts/day, denormalised",
                    ],
                },
                {"type": "h3", "text": "Cache & Bandwidth"},
                {
                    "type": "bullets",
                    "items": [
                        "Active feed working set: ~200M users opening/hour × ~30 stories × 1 KB ≈ <strong>6 TB hot</strong> Memcached",
                        "Photo egress (CDN): ~10B reads × ~100 KB rendered = <strong>~1 EB/day</strong> at the edge",
                        "Origin egress after CDN: assume 95% offload → <strong>~50 PB/day</strong> from origin",
                        "Inbound media: ~225 TB/day ≈ <strong>~21 Gbps avg, ~60 Gbps peak</strong>",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Numbers To Memorise",
                    "body": (
                        "<strong>3B MAU / 2B DAU</strong> &nbsp;·&nbsp; "
                        "<strong>1B posts/day</strong> (12K/sec) &nbsp;·&nbsp; "
                        "<strong>10B feed reads/day</strong> (115K avg, 300K peak) &nbsp;·&nbsp; "
                        "<strong>5K candidates/read, 60 µs/score</strong> &nbsp;·&nbsp; "
                        "<strong>~30 stories</strong> served per page &nbsp;·&nbsp; "
                        "<strong>~6 TB hot</strong> Memcached working set."
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
                        "The architecture has three planes. <strong>Ingest</strong> accepts new posts "
                        "and runs fan-out. <strong>Serve</strong> reads candidates, ranks them, and "
                        "returns the page. <strong>Logging</strong> captures every impression and "
                        "engagement so the next training run can improve relevance. Each plane scales "
                        "independently; Kafka is the only contract between them."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "End-to-end: client to API gateway to Feed Aggregator + Ranking Service + Action Logger; data tier mixes TAO graph, BLOB store, Memcached, the Ranking Model Server, and Kafka.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Clients"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Mobile [label="iOS / Android",  fillcolor="#dbe6fb"];
        Web    [label="Web",            fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        CDN [label="CDN\n(media bytes)", fillcolor="#cbeedf"];
        LB  [label="Global LB",          fillcolor="#cbeedf"];
        GW  [label="API Gateway\n(auth, rate-limit)", fillcolor="#cbeedf"];
    }
    subgraph cluster_svc {
        label="Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        Agg  [label="Feed Aggregator\n(candidate gen + merge)", fillcolor="#fff2c9"];
        Rank [label="Ranking Service\n(score + reorder)",      fillcolor="#fff2c9"];
        Log  [label="Action Logger\n(impressions + clicks)",    fillcolor="#fff2c9"];
        Post [label="Post / Write Svc",                         fillcolor="#fff2c9"];
        FOW  [label="Fan-Out Worker",                           fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        TAO    [label="TAO\n(social graph,\nposts, edges)",  fillcolor="#ead7fb"];
        BLOB   [label="Content / BLOB\nStore (Haystack/f4)",  fillcolor="#ead7fb"];
        MC     [label="Memcached / Redis\n(feed + post cache)", fillcolor="#ead7fb"];
        Model  [label="Ranking Model\nServer (DLRM)",         fillcolor="#ead7fb"];
        Kafka  [label="Kafka / Scribe\n(events)",             fillcolor="#fbd7c5"];
    }

    Mobile -> CDN [label="GET media"];
    Mobile -> LB  [label="API"];
    Web    -> CDN;
    Web    -> LB;
    LB -> GW;

    GW -> Agg  [label="GET /feed"];
    GW -> Post [label="POST /post"];
    GW -> Log  [label="POST /event", style=dashed];

    Post -> TAO   [label="write post + edges"];
    Post -> BLOB  [label="presigned PUT"];
    Post -> Kafka [label="post_created", style=dashed];
    Kafka -> FOW  [style=dashed];
    FOW   -> MC   [label="push timeline"];
    FOW   -> TAO  [label="durable timeline"];

    Agg  -> MC    [label="hot timeline"];
    Agg  -> TAO   [label="celeb pull / hydrate"];
    Agg  -> Rank  [label="candidates"];
    Rank -> Model [label="score 5K/req"];
    Rank -> MC    [label="features", style=dashed];
    Agg  -> BLOB  [label="thumb refs", style=dashed];

    Log  -> Kafka [style=dashed];
    Kafka -> Model [label="training data\n(offline)", style=dashed];
}
""",
                },
                {"type": "h3", "text": "Service Responsibilities"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>API Gateway:</strong> authn, per-user QPS limits, request routing",
                        "<strong>Post Service:</strong> writes post row to TAO, issues presigned BLOB URL, emits <code>post_created</code>",
                        "<strong>Fan-Out Worker:</strong> Kafka consumer; pushes post_id into followers' Memcached timelines (regular users) or skips for celebrities",
                        "<strong>Feed Aggregator:</strong> on read, fetches pre-built timelines + celebrity candidates, merges, dedups, hydrates",
                        "<strong>Ranking Service:</strong> calls the Model Server with feature vectors; returns top-K",
                        "<strong>Action Logger:</strong> async log of every impression, dwell, click, react, hide — feeds offline training",
                        "<strong>Ranking Model Server:</strong> hosts the trained DLRM; ~60 µs/inference on accelerator",
                        "<strong>TAO:</strong> graph store of users, posts, edges (friend/follows/likes); cache-fronted MySQL",
                        "<strong>BLOB store:</strong> Haystack (warm) + f4 (cold) for photos and videos",
                        "<strong>Memcached:</strong> per-user feed lists, post metadata, ranking features",
                        "<strong>Kafka / Scribe:</strong> backbone for events and async work",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Hybrid Push / Pull Fan-Out",
            "subtitle": "The core feed-delivery decision",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Naïve approaches break fast. <strong>Pure push</strong> melts when a page "
                        "with 100M followers posts. <strong>Pure pull</strong> melts when 2B DAU each "
                        "scatter-gather across 550 sources at read time. Facebook uses a <strong>hybrid</strong>: "
                        "push for normal accounts, pull for high-fanout sources, merge on read."
                    ),
                },
                {"type": "h3", "text": "Push vs. Pull vs. Hybrid"},
                {
                    "type": "table",
                    "headers": ["Aspect", "Push (write fan-out)", "Pull (read fan-out)", "Hybrid (recommended)"],
                    "rows": [
                        ["Read latency", "Fast — timeline pre-built", "Slow — scatter-gather across 550 sources",
                         "Fast for both paths"],
                        ["Write cost", "O(followers) per post", "O(1) per post",
                         "O(followers) below threshold; O(1) above"],
                        ["Storage", "N timeline entries per post", "1 row in postDB",
                         "Mostly N copies; 0 for celebs"],
                        ["Worst case", "Page with 100M followers → 100M writes",
                         "Active user open → 550-way fan-in", "Celeb post: O(1); user open: ~20-way fan-in"],
                        ["Freshness", "Eventually consistent (push lag)",
                         "Always fresh on read", "Push lag &lt; 60 s; pull always fresh"],
                        ["Best for", "Low-fanout users", "Very-high-fanout sources",
                         "Realistic distribution (heavy-tail)"],
                    ],
                },
                {
                    "type": "diagram",
                    "caption": "Hybrid fan-out: regular users push into followers' Memcached timelines + TAO; celebrities & big pages skip the push and live in TAO postDB; the read path merges both at request time.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Post   [label="New Post\n(Post Service)",    fillcolor="#dbe6fb"];
    Kafka  [label="Kafka\npost_created topic",   fillcolor="#fbd7c5"];
    FOW    [label="Fan-Out Worker",              fillcolor="#fff2c9"];
    Decide [label="follower_count\n>= T (e.g. 100K)?",
            shape=diamond, fillcolor="#fff2c9", style="filled"];

    subgraph cluster_push {
        label="Push (regular accounts, < T followers)"; style="rounded,dashed";
        color="#1f8359"; fontcolor="#1f8359";
        MC1   [label="Memcached\nper-follower\ntimeline list",     fillcolor="#cbeedf"];
        TAO_T [label="TAO\nuser_timeline\n(durable)",              fillcolor="#cbeedf"];
    }

    subgraph cluster_pull {
        label="Pull (celebs & pages, >= T followers)"; style="rounded,dashed";
        color="#b8862e"; fontcolor="#b8862e";
        TAO_P [label="TAO\nauthor_postlist\n(read on demand)",     fillcolor="#fff2c9"];
    }

    Read  [label="Feed Read\n(GET /feed)",       fillcolor="#dbe6fb"];
    Merge [label="Aggregator:\nuser timeline\n+ celeb posts\n+ dedup",
           fillcolor="#ead7fb"];
    Rank  [label="Ranking\nService\n(top-K)",    fillcolor="#ead7fb"];
    MCM   [label="Memcached\nranked feed cache\n(TTL ~60 s)",      fillcolor="#cbeedf"];

    Post -> Kafka -> FOW -> Decide;
    Decide -> MC1   [label="no\n(push)"];
    Decide -> TAO_T [label="no\n(durable)"];
    Decide -> TAO_P [label="yes\n(skip fan-out)"];

    Read  -> MCM   [label="ranked-cache hit?", style=dashed];
    MCM   -> Merge [label="miss", style=dashed];
    Merge -> MC1   [label="pre-built rows"];
    Merge -> TAO_P [label="celeb posts\non demand"];
    Merge -> Rank;
    Rank  -> MCM   [label="store top-K"];
}
""",
                },
                {"type": "h3", "text": "Fan-Out Worker — Pseudocode"},
                {
                    "type": "code",
                    "text": (
                        "def on_post_created(event):\n"
                        "    post   = event.post\n"
                        "    author = tao.get_user(post.user_id)\n"
                        "    fc     = author.follower_count\n\n"
                        "    # Always durable-write the post once on the author side\n"
                        "    tao.append_author_postlist(author.id, post.id, post.created_at)\n\n"
                        "    if fc >= PUSH_THRESHOLD:                        # celeb / big page\n"
                        "        metrics.incr('fanout.skip_celeb')\n"
                        "        return                                       # readers will pull\n\n"
                        "    # Push path — page through followers in batches\n"
                        "    for batch in tao.followers_paged(author.id, 5000):\n"
                        "        ops = []\n"
                        "        for follower_id in batch:\n"
                        "            if user_pref.is_snoozed(follower_id, author.id):\n"
                        "                continue                              # skip muted\n"
                        "            key = f'tl:{follower_id}'\n"
                        "            ops.append(memcache.lpush(key,\n"
                        "                       (post.id, post.created_at, author.id),\n"
                        "                       maxlen=2000))                  # cap timeline size\n"
                        "        memcache.pipeline(ops)                         # batch RPC\n"
                        "        tao.append_user_timeline_batch(batch, post)    # durable copy\n\n"
                        "    metrics.incr('fanout.push_done', fc)"
                    ),
                },
                {"type": "h3", "text": "Threshold-Tuning Math (push vs. pull break-even)"},
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Where Does The Push/Pull Curve Cross?",
                    "body": (
                        "Let <strong>F</strong> = an author's follower count, "
                        "<strong>R</strong> = average reads per follower per day (assume 5), "
                        "<strong>w_push</strong> = cost of one Memcached LPUSH (~80 µs incl. network), "
                        "<strong>w_pull</strong> = cost of one extra TAO partition read on the read "
                        "path (~600 µs incl. cache miss assumption).<br><br>"
                        "<strong>Push cost per post:</strong> <code>F · w_push</code> = "
                        "F × 80 µs.<br>"
                        "<strong>Pull cost per post:</strong> incurred on every read by every follower = "
                        "<code>F · R · w_pull</code> = F × 5 × 600 µs <em>per day</em>.<br><br>"
                        "Per-post push is paid once; pull is paid R times per follower per day for the "
                        "post's lifetime in feed (call it L = 2 days of decay). Equating cost per post:<br>"
                        "<code>F · w_push  ≈  F · R · L · w_pull</code> simplifies away — the per-post "
                        "cost is linear in F either way. <strong>So the break-even isn't on F directly — "
                        "it's on the <em>read multiplier</em> R·L vs the push multiplier 1.</strong> "
                        "Push wins when R·L · w_pull &gt; w_push, i.e. 5 × 2 × 600 µs = 6,000 µs &gt; "
                        "80 µs — which is always true.<br><br>"
                        "<strong>So why ever pull?</strong> Because push has a <em>burst</em> cost: "
                        "F LPUSHs in seconds. A page with 100M followers triggers 100M LPUSH at one "
                        "instant — saturating the cluster. Pull amortises across the day. The real "
                        "threshold isn't where averages cross — it's where <strong>burst push exceeds "
                        "your cluster's instantaneous capacity</strong>: "
                        "<code>T = capacity_per_sec · max_seconds_to_complete / posts_per_sec_from_class</code>. "
                        "For Facebook's measured cluster, <strong>T ≈ 100K followers</strong> is the "
                        "operational sweet spot."
                    ),
                },
                {"type": "h3", "text": "Hybrid Algorithm — Read Path"},
                {
                    "type": "numbered",
                    "items": [
                        "Look up user's pre-built timeline list in Memcached (push path output)",
                        "Look up the user's <strong>celeb-follow set</strong> (cached); for each, query TAO <code>author_postlist</code> for the last N posts",
                        "Merge by created_at; <strong>dedup</strong> by post_id; cap to ~5K candidates",
                        "Hydrate metadata (author name, counters, BLOB refs) from Memcached + TAO",
                        "Send candidates + user features to Ranking Service",
                        "Persist ranked top-K in Memcached for ~60 s (handles re-pulls during scroll)",
                    ],
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "ML Ranking — Signals & Models",
            "subtitle": "EdgeRank → DLRM",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Chronological ordering buries good content. The ranker assigns each candidate "
                        "a score and returns top-K. The model has evolved: original <strong>EdgeRank</strong> "
                        "was a 3-term linear formula; today's production is a <strong>DLRM</strong> "
                        "(Deep Learning Recommendation Model) with hundreds of features and learned "
                        "embeddings, served on accelerators."
                    ),
                },
                {"type": "h3", "text": "Ranking Signals"},
                {
                    "type": "table",
                    "headers": ["Signal", "What it captures"],
                    "rows": [
                        ["Affinity (u_e)", "How often viewer u interacts with author/source e (likes, comments, profile visits, DMs)"],
                        ["Edge weight (w_e)", "Importance of the edge type — comments &gt; reactions &gt; views; videos &gt; photos &gt; text"],
                        ["Time decay (d_e)", "Exponential decay; freshness boost; half-life ~6 hours for friends, ~3 hours for pages"],
                        ["Negative signals", "Hide, snooze, unfollow, low-dwell, report — strong demotions"],
                        ["Content quality", "Click-bait classifier, integrity filters, NSFW, misinformation flags"],
                        ["Diversity", "Anti-echo: cap stories from one author/page in top-K"],
                        ["Predicted action", "P(react), P(comment), P(share), P(dwell &gt; 3s) — multi-task heads"],
                        ["Personal preferences", "See-first list, snooze list, language, locality"],
                    ],
                },
                {"type": "h3", "text": "EdgeRank (v0)"},
                {
                    "type": "code",
                    "text": (
                        "# Original EdgeRank — sum over edges (u, e_i) for candidate post p\n"
                        "score(u, p) = sum_over_edges(\n"
                        "    affinity(u, e) * weight(e) * decay(e)\n"
                        ")\n\n"
                        "affinity(u, e)  = log(1 + interaction_count_30d(u, author(e))) / 5\n"
                        "weight(e)       = {'comment': 3.0, 'react': 1.0,\n"
                        "                   'share':   2.5, 'view':  0.2}[e.type]\n"
                        "decay(e)        = exp(-ln(2) * age_hours(e) / half_life_hours)\n"
                        "negative_pen(u, p) = -10.0 if hidden_similar(u, p) else 0\n\n"
                        "# Sort candidates by score desc; return top-K"
                    ),
                },
                {"type": "h3", "text": "DLRM (production)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Inputs:</strong> dense user features + dense item features + 100s of categorical IDs (author, page, hashtag, language, device, hour-of-day…)",
                        "<strong>Embedding tables:</strong> 10s of TB of learned vectors; sharded across parameter servers",
                        "<strong>Bottom MLP:</strong> processes dense features; <strong>top MLP:</strong> combines with embedding interactions (dot products / FMs)",
                        "<strong>Multi-task heads:</strong> p_react, p_comment, p_share, p_dwell, p_negative — combined as a weighted utility",
                        "<strong>Training:</strong> daily on impression+engagement logs; ~PB scale; A/B-tested before promotion",
                        "<strong>Serving:</strong> accelerator pool (GPU/TPU); ~60 µs per candidate, 5K candidates per request → ~300 ms total",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Multi-task Utility",
                    "body": (
                        "Don't just predict one engagement type. The serving formula combines several "
                        "predicted probabilities with business-tuned weights:<br>"
                        "<code>U = a·p_react + b·p_comment + c·p_share + d·p_dwell − e·p_negative − "
                        "f·p_clickbait</code><br>"
                        "Tuning <em>a..f</em> is a product decision: heavy comment weight encourages "
                        "discussion; heavy share weight pushes virality; the negative term protects "
                        "long-term retention."
                    ),
                },
                {"type": "h3", "text": "Negative Signals — Why They Matter"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Hide:</strong> demote anything similar (same author, same hashtag) for 30 days",
                        "<strong>Snooze 30d:</strong> hard exclude — never rank from this source for the window",
                        "<strong>Unfollow:</strong> remove from candidate generation entirely",
                        "<strong>Report:</strong> route to integrity pipeline; possibly block author",
                        "<strong>Low-dwell:</strong> implicit signal — &lt; 1 s in viewport = mild demotion",
                        "<strong>Why critical:</strong> negative signals are scarce but high-value; without them the ranker overfits to engagement bait",
                    ],
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Storage — TAO, BLOB, Memcached",
            "subtitle": "Polyglot persistence at planet scale",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "No single store fits feed. Posts and edges (friend, follow, like) live in "
                        "<strong>TAO</strong> — a graph cache layered over sharded MySQL. Photos and "
                        "videos live in the <strong>BLOB store</strong> (Haystack for warm, f4 for "
                        "cold). Hot timeline lists, post metadata, and ranking features are kept in "
                        "<strong>Memcached</strong>. Async work flows on <strong>Kafka/Scribe</strong>."
                    ),
                },
                {"type": "h3", "text": "TAO — Graph Cache"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Objects (nodes):</strong> users, posts, comments, pages, groups",
                        "<strong>Associations (edges):</strong> friend, follow, react, comment_on, share, member_of",
                        "<strong>Layout:</strong> two-level cache (regional follower + per-shard leader) over sharded MySQL",
                        "<strong>Why graph?</strong> Feed candidate gen is fundamentally <em>traverse the social graph</em>",
                        "<strong>Read path:</strong> nearest cache → leader cache → MySQL primary; ~99% hit rate at the edge",
                        "<strong>Write path:</strong> write to MySQL primary, invalidate cache, async replicate cross-region",
                    ],
                },
                {"type": "h3", "text": "Post Schema (TAO object)"},
                {
                    "type": "code",
                    "text": (
                        "# Object record\n"
                        "post {\n"
                        "  id:           bigint (snowflake)\n"
                        "  author_id:    bigint\n"
                        "  type:         enum {text, photo, video, link, life_event}\n"
                        "  text:         varchar(63206)        # FB max post length\n"
                        "  blob_refs:    list<blob_id>         # photos / video manifests\n"
                        "  audience:     enum {public, friends, friends_of_friends, custom}\n"
                        "  custom_acl:   list<user_id|list_id> # nullable\n"
                        "  created_at:   bigint (ms)\n"
                        "  edited_at:    bigint (ms) | null\n"
                        "  geo:          (lat, lng) | null\n"
                        "  lang:         varchar(8)\n"
                        "  integrity:    bitmask (clickbait, lowqual, fake_news, etc.)\n"
                        "  counters_id:  bigint                 # external counter row\n"
                        "}\n\n"
                        "# Association tables (sharded by 1st column)\n"
                        "friend(user_id, friend_id, created_at)\n"
                        "follow(user_id, page_id,   created_at)\n"
                        "member(user_id, group_id,  created_at, role)\n"
                        "react(post_id,  user_id,   reaction_type, created_at)\n"
                        "user_timeline(user_id, created_at DESC, post_id)   # push fan-out output\n"
                        "author_postlist(author_id, created_at DESC, post_id)  # pull-path source"
                    ),
                },
                {"type": "h3", "text": "BLOB Store — Haystack + f4"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Haystack (warm):</strong> append-only log files; needle index in RAM; one disk seek per photo",
                        "<strong>f4 (cold):</strong> Reed-Solomon erasure-coded; ~2.1× storage overhead vs 3× replication",
                        "<strong>Tiering:</strong> photos start in Haystack; if access rate &lt; threshold for 90 days, migrate to f4",
                        "<strong>Upload path:</strong> Post Service issues presigned URL; client PUTs bytes directly",
                        "<strong>Serving:</strong> CDN absorbs ~95% of egress; origin pulls only on edge miss",
                    ],
                },
                {"type": "h3", "text": "Memcached — Hot Caches"},
                {
                    "type": "table",
                    "headers": ["Key", "Contents", "TTL", "Why"],
                    "rows": [
                        ["tl:{user_id}", "List of (post_id, ts, author_id) — push timeline",
                         "24 h sliding", "Read on every feed open"],
                        ["post:{post_id}", "Hydrated post (author name, counters, blob_refs)",
                         "1 h", "Avoid TAO trip on hydration"],
                        ["counters:{post_id}", "Reactions/comments/shares (sharded counters)",
                         "30 s", "Hot updates; freshness matters"],
                        ["feat:user:{user_id}", "Dense user features for ranker",
                         "5 min", "Reused across consecutive feed reads"],
                        ["feat:post:{post_id}", "Dense post features",
                         "1 h", "Mostly static after the first hour"],
                        ["ranked:{user_id}:{cursor}", "Stored top-K page",
                         "60 s", "Idempotent re-pulls during scroll"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Lease Semantics For Counters",
                    "body": (
                        "Memcached has no transactions. To prevent thundering-herd cache stampedes, "
                        "Facebook added <strong>leases</strong>: the first cache miss is given a lease "
                        "token; subsequent misses block briefly. The token-holder fetches from TAO and "
                        "writes back; everyone else reads the freshly-cached value. Saves the DB from "
                        "1000× duplicate fills when a viral post explodes."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Write Path — Post Creation",
            "subtitle": "From compose to fan-out",
            "blocks": [
                {"type": "h3", "text": "Step-by-Step"},
                {
                    "type": "numbered",
                    "items": [
                        "Client composes; if media, requests presigned BLOB URL via <code>POST /upload</code>",
                        "Client PUTs media bytes <strong>directly</strong> to BLOB store (Haystack)",
                        "Client calls <code>POST /post</code> with text, blob_refs, audience",
                        "Post Service validates: text length, audience ACL, integrity classifiers (NSFW, hate, misinformation)",
                        "TAO write: insert post object; insert edges (audience_acl, blob_refs, hashtags, mentions)",
                        "Append to <code>author_postlist(author_id)</code> — durable; supports pull-path reads",
                        "Emit <code>post_created</code> on Kafka; return 201 with post_id (no need to wait for fan-out)",
                        "Self-injection: client cache adds the post to the user's own feed view immediately (read-your-writes)",
                        "Fan-Out Worker (async): pushes to followers per §05 hybrid rules",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Why Async Fan-Out?",
                    "body": (
                        "If we waited for fan-out before responding, a post by a user with 350 friends "
                        "would block the API call for ~30 ms. Worse, a page with 100M followers would "
                        "block for minutes. Async lets the write return in &lt; 100 ms, and the worker "
                        "absorbs the spike at its own pace. Followers see the post within 60 s — "
                        "perceptually instant."
                    ),
                },
                {"type": "h3", "text": "Integrity Pipeline (synchronous)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Hate / harassment:</strong> classifier ensemble; block + appeal queue",
                        "<strong>Misinformation:</strong> 3rd-party fact-check; demote not block",
                        "<strong>NSFW:</strong> nudity classifier on media; age-gate or block",
                        "<strong>Spam:</strong> velocity rules + ML; rate-limit account",
                        "<strong>Latency budget:</strong> 50 ms p99 inline; deeper checks run async post-publish",
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Read Path — Feed Generation",
            "subtitle": "Aggregate, rank, hydrate",
            "blocks": [
                {"type": "h3", "text": "Step-by-Step"},
                {
                    "type": "numbered",
                    "items": [
                        "Client calls <code>GET /feed?cursor=...</code>",
                        "Aggregator: ranked-feed cache check (key <code>ranked:{u}:{cursor}</code>); hit → return; miss → continue",
                        "Candidate gen: read <code>tl:{user_id}</code> from Memcached (push output)",
                        "Celeb pull: read <code>celeb_follows:{u}</code>; for each, fetch last N from <code>author_postlist</code>",
                        "Merge + dedup; cap at ~5,000 candidates by created_at",
                        "Filter: blocked, snoozed, hidden_similar, audience-mismatch, integrity-violations",
                        "Hydrate: feature vectors via <code>feat:user:{u}</code>, <code>feat:post:{p}</code>",
                        "Score: send ~5K candidates to Ranking Service → Model Server (DLRM)",
                        "Re-rank with diversity caps (≤2 per author per top-30); apply ad insertion slots",
                        "Hydrate metadata for top-K; store in <code>ranked:{u}:{cursor}</code> with 60 s TTL",
                        "Return top-30 + next_cursor; client renders; impressions logged async",
                    ],
                },
                {"type": "h3", "text": "Latency Budget (target p99 = 1.5 s end-to-end)"},
                {
                    "type": "table",
                    "headers": ["Stage", "Budget", "Notes"],
                    "rows": [
                        ["Network (client → edge)", "150 ms", "Geo-aware Anycast; TLS resume"],
                        ["Auth + routing", "20 ms", "Cached JWT verify"],
                        ["Aggregator candidate gen", "100 ms", "Memcached + TAO parallel calls"],
                        ["Filter + hydrate features", "80 ms", "Batched cache mget"],
                        ["Ranking inference (5K × 60 µs)", "300 ms", "Accelerator pool; batched"],
                        ["Re-rank + diversity + ads", "30 ms", "CPU"],
                        ["Hydrate top-K", "70 ms", "Parallel TAO/Memcached"],
                        ["Network (edge → client)", "150 ms", "Compressed JSON"],
                        ["Slack / GC / retries", "300 ms", "Headroom"],
                        ["<strong>Total p99</strong>", "<strong>1.20 s</strong>", "Inside 1.5s budget"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Pagination Stability",
                    "body": (
                        "Cursors must be <strong>stable</strong> — the user must not see the same "
                        "post twice on page 2 even though new posts arrived between page loads. The "
                        "cursor encodes the ranked-feed snapshot ID + offset. Server stores the "
                        "snapshot for 5 minutes; subsequent <code>GET /feed?cursor=...</code> reads "
                        "from the same snapshot."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Action Logging & Training",
            "subtitle": "Closing the ML loop",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Ranking quality depends entirely on training data quality. Every impression, "
                        "dwell, scroll, react, comment, share, hide, snooze must be logged with "
                        "context — what was shown, what rank, what the user did. The volume is "
                        "staggering: ~10B reads × 30 stories = <strong>300B impressions/day</strong>, "
                        "before counting engagement events."
                    ),
                },
                {"type": "h3", "text": "Event Schema"},
                {
                    "type": "code",
                    "text": (
                        "{\n"
                        "  \"event_id\":   \"<uuid>\",\n"
                        "  \"viewer_id\":  12345,\n"
                        "  \"post_id\":    67890,\n"
                        "  \"author_id\":  54321,\n"
                        "  \"event_type\": \"impression | dwell | react | comment | share | hide | snooze | unfollow\",\n"
                        "  \"rank\":       7,                        // position in feed\n"
                        "  \"feed_session\": \"<uuid>\",\n"
                        "  \"model_id\":   \"dlrm_v143_2026_05_01\",  // for offline replay\n"
                        "  \"features\":   { ... },                  // hashed feature vector\n"
                        "  \"dwell_ms\":   2400,                     // for impression events\n"
                        "  \"timestamp\":  \"2026-05-07T10:30:45.123Z\",\n"
                        "  \"client\":     { \"app\": \"ios\", \"version\": \"442.1\" }\n"
                        "}"
                    ),
                },
                {"type": "h3", "text": "Pipeline"},
                {
                    "type": "bullets",
                    "items": [
                        "Client batches events; flushes every 5 s or on backgrounding",
                        "API edge writes to Scribe / Kafka topic <code>feed_actions</code> (RF=3)",
                        "Stream processor (Flink) does sessionisation + joins with the served snapshot",
                        "Hourly: dump to <strong>Hive / data warehouse</strong> for offline training",
                        "Daily: train next DLRM checkpoint; A/B test on 1% before global rollout",
                        "Real-time: short-loop feedback (e.g. snooze, hide) updates user-feature cache within 60 s",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Negative Sampling",
                    "body": (
                        "Most impressions are non-engagements. To train, we don't need every "
                        "non-event — we down-sample negatives ~10:1 against positives, then re-weight "
                        "during training. Saves 90% of training compute with negligible AUC loss."
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Caching Strategy",
            "subtitle": "Layered, lease-protected, invalidation-aware",
            "blocks": [
                {"type": "h3", "text": "Cache Layers"},
                {
                    "type": "table",
                    "headers": ["Layer", "What", "TTL", "Hit Rate (target)"],
                    "rows": [
                        ["CDN edge", "Photo / video bytes", "7 days", "≥ 95%"],
                        ["Memcached (regional)", "Push timeline tl:{u}", "24 h slide", "~98%"],
                        ["Memcached (regional)", "Hydrated post post:{p}", "1 h", "~95%"],
                        ["Memcached (regional)", "Counters counters:{p}", "30 s", "~85%"],
                        ["Memcached (regional)", "User / post features", "5 min / 1 h", "~92%"],
                        ["Memcached (regional)", "Ranked-feed snapshot", "60 s", "~70% (during scroll)"],
                        ["TAO leader cache", "Posts, edges", "until invalidate", "~99%"],
                        ["Client SDK", "Pre-rendered top-30 + next 30", "session", "100% on scroll"],
                    ],
                },
                {"type": "h3", "text": "Invalidation"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Write-through invalidation:</strong> writer publishes invalidate event; cache nodes drop the key",
                        "<strong>Lease tokens:</strong> first miss gets a lease; others wait briefly to avoid stampede",
                        "<strong>TTL backstop:</strong> if an invalidate is dropped, key expires anyway",
                        "<strong>Counter sloppiness:</strong> reaction counts shown ±1% acceptable; serves from coarse-grained sharded counters",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Two-Level Cache",
                    "body": (
                        "TAO uses a <strong>region-local follower cache</strong> in front of a "
                        "<strong>per-shard leader cache</strong> in front of MySQL. A miss at the "
                        "follower walks up to the leader, then to MySQL. Writes go to MySQL primary "
                        "and invalidate the leader (and via gossip, the followers). Net effect: "
                        "&gt; 99% hit rate at the regional edge, low cross-DC traffic."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Comparable Systems",
            "subtitle": "News Feed vs Twitter timeline vs Instagram",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "All three are timelines built on hybrid push/pull, but they diverge sharply "
                        "in graph shape, content type, and ranking objective."
                    ),
                },
                {
                    "type": "table",
                    "headers": ["Aspect", "Facebook News Feed", "Twitter Home Timeline", "Instagram Feed"],
                    "rows": [
                        ["Graph", "Bidirectional friends + follows of pages/groups",
                         "Asymmetric follow graph; many-to-many", "Asymmetric follow; typically ≪ friends"],
                        ["Avg sources", "~550 (350 friends + pages/groups)",
                         "~400 follows (heavy-tailed)", "~150 follows"],
                        ["Content", "Mixed: text/photo/video/link/life events/ads",
                         "Mostly short text + media", "Photo + video first"],
                        ["Ranking", "DLRM, multi-task, integrity-aware",
                         "Earlybird → real-time graph + Heavy Ranker", "Two-tower; engagement+recency"],
                        ["Freshness target", "&lt; 60 s for friends",
                         "Near real-time (seconds)", "&lt; 60 s"],
                        ["Push threshold", "~100K followers",
                         "~1M followers (lower w_push)", "~1M followers"],
                        ["Storage primary", "TAO (graph cache + MySQL)",
                         "Manhattan (KV) + Gizzard / Twemcache", "MySQL + Cassandra"],
                        ["Media store", "Haystack + f4",
                         "Blobstore", "S3"],
                        ["Distinct twist", "Pages + groups inflate fanout vs Twitter",
                         "Retweet adds extra fan-out edge", "Stories run on a separate stack"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why The Threshold Differs",
                    "body": (
                        "Twitter's push threshold is higher (~1M) because their write-cost-per-follower "
                        "is lower (smaller payload, simpler timeline rows) and their read freshness "
                        "demand is higher (real-time culture). Facebook's News Feed tolerates 60 s "
                        "lag in exchange for richer hydrated metadata at push time. Different "
                        "constants, same hybrid pattern."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Scalability & Sharding",
            "subtitle": "Horizontal everything",
            "blocks": [
                {"type": "h3", "text": "Sharding Plan"},
                {
                    "type": "table",
                    "headers": ["Data", "Shard Key", "Shards", "Why"],
                    "rows": [
                        ["users", "hash(user_id) % 4096", "4096+",
                         "Even distribution; isolate hot users"],
                        ["posts", "hash(author_id) % 4096", "4096+",
                         "Co-locate author's posts; profile reads stay single-shard"],
                        ["friend / follow edges", "hash(user_id) % 4096", "4096+",
                         "User's outgoing edges all on one shard"],
                        ["user_timeline (push)", "hash(user_id) % 8192", "8192+",
                         "Hottest write target during fan-out"],
                        ["author_postlist (pull)", "hash(author_id) % 4096", "4096+",
                         "Reads concentrated on celebs — pre-warm caches"],
                        ["counters", "hash(post_id) % 16384", "16384+",
                         "Hot reactions on viral posts; sub-shard counters per region"],
                        ["BLOB Haystack", "consistent hash on blob_id", "1000s of volumes",
                         "Append-only logs; rebalance via rolling migration"],
                    ],
                },
                {"type": "h3", "text": "Replication & Multi-Region"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Single-master writes per user:</strong> user is pinned to a primary region (Atlanta, Luleå, Singapore...)",
                        "<strong>Cross-region replication:</strong> async; ~1 s typical lag",
                        "<strong>Read locally:</strong> all read paths satisfied from the nearest region",
                        "<strong>TAO follower cache:</strong> per region; invalidations cross-region via the wormhole stream",
                        "<strong>Failover:</strong> if a primary region drops, secondary promotes after coordination quorum",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Hot Author Mitigation",
                    "body": (
                        "A page with 200M followers posting concurrently with 9 other pages causes "
                        "<strong>2B writes</strong> in seconds if naïvely pushed. Mitigations: "
                        "(1) celeb threshold skips push entirely; "
                        "(2) sharded counters break per-post hotspots; "
                        "(3) rate-limit rapid-fire pages to once per N seconds; "
                        "(4) batch LPUSHes per follower-shard to one RPC."
                    ),
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Failure Modes & Recovery",
            "subtitle": "Graceful degradation order",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["Memcached node down", "Higher TAO load on miss",
                         "Health check + miss rate alarm",
                         "Consistent-hash drop; TAO absorbs; spin replacement; lease tokens limit stampede"],
                        ["TAO leader down", "Reads slower, writes blocked on shard",
                         "Replica-lag + write-error alarm",
                         "Promote replica; reroute; backfill from MySQL primary"],
                        ["MySQL shard down", "That shard's reads/writes fail",
                         "Connection timeout",
                         "Auto-promote replica (Orchestrator); ~30 s RTO; cache absorbs"],
                        ["Ranking Model Server down", "No personalised ranking",
                         "Inference latency / error rate",
                         "Fall back to chronological merge; serve cached ranked feed; banner 'updating'"],
                        ["Fan-Out Worker lag", "Friend posts late to followers",
                         "Kafka consumer-lag metric",
                         "Scale workers; pull-path rescues during outage; freshness SLO breach"],
                        ["Kafka broker partition", "Action logging stalls; training slips a day",
                         "Broker dead alert",
                         "RF=3 brokers; 7-day buffer; consume from the surviving region"],
                        ["BLOB store outage", "New uploads fail; existing media OK from CDN",
                         "PUT error rate",
                         "Queue uploads in client; presigned URL retry; user banner"],
                        ["CDN regional outage", "+200 ms latency in that region",
                         "CDN provider alert",
                         "DNS failover to backup CDN; origin scales"],
                        ["Cache stampede on viral post", "TAO request floods",
                         "Per-key miss rate spike",
                         "Lease tokens; coalesced fills; pre-warm celeb posts"],
                        ["Cross-region partition", "Read-your-writes broken cross-region",
                         "Latency + replication lag",
                         "Pin user to primary region; serve stale until heal"],
                        ["Cascading slowness", "Timeouts propagate up",
                         "p99 explosion",
                         "Circuit breakers around Ranking; fall back to cache; shed traffic"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Degradation Order",
                    "body": (
                        "If we have to drop features to stay up, the order is: "
                        "(1) ML ranking → chronological merge; "
                        "(2) hydration richness → strip side-counters; "
                        "(3) ad insertion → skip; "
                        "(4) celeb pull → skip; "
                        "(5) action logging → buffer locally; "
                        "(6) <strong>feed read of pre-built timeline is never dropped</strong>."
                    ),
                },
                {"type": "h3", "text": "Disaster Recovery"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>RTO:</strong> &lt; 30 s for a single shard; &lt; 5 min for a regional outage",
                        "<strong>RPO:</strong> &lt; 1 s for posts (synchronous WAL); &lt; 1 min for action logs",
                        "<strong>Backups:</strong> MySQL incremental every 30 min; full daily; off-region copies",
                        "<strong>Drills:</strong> quarterly chaos exercises take a region offline for one hour",
                    ],
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
                        ["Fan-out model", "Hybrid push/pull at ~100K threshold",
                         "Push-only melts on big pages; pull-only melts on read scatter-gather. Hybrid pays more storage to serve fast reads for the 99% case and cheap writes for the heavy-tail."],
                        ["Ordering", "ML-ranked, not chronological",
                         "Better engagement and time-spent; opaque to users; risk of filter bubbles. Chronological is honest but burys quality content."],
                        ["Consistency", "Eventual for feed; read-your-writes for poster",
                         "Stale by &lt; 60 s for friends; needs self-injection for the poster. Strong consistency at this scale is impossible across regions."],
                        ["Storage", "TAO over sharded MySQL; Haystack+f4",
                         "Operational complexity vs single store. TAO cache layer is a Facebook-grade investment; smaller orgs use Cassandra+S3."],
                        ["Ranking model", "DLRM with multi-task heads",
                         "PB of training data; 10s of TB of embeddings; serving cost is real. Linear EdgeRank is cheaper but plateaus on quality."],
                        ["Cache TTL", "Counters 30s, posts 1h, timelines 24h slide",
                         "Counters trade freshness for cluster load; long TTLs save fills but risk stale UX."],
                        ["Self-injection (RYW)", "Client-side overlay",
                         "Simple; requires careful dedup when push catches up. Server-side strict RYW would force read-after-write across replicas."],
                        ["Negative signals", "Strong demotion + 30-day exclusion",
                         "Protects retention but reduces candidate diversity; tunable per-account."],
                        ["Push threshold", "~100K (operational sweet spot)",
                         "Higher threshold saves writes but risks read-path scatter-gather; tune per cluster capacity."],
                        ["Action logging", "At-least-once, sampled negatives",
                         "Cheap and accurate enough for ML; exactly-once is unimplementable across systems."],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "The Defining Trade-Off",
                    "body": (
                        "News Feed exists at the intersection of <strong>graph traversal</strong> "
                        "(social), <strong>information retrieval</strong> (relevance ranking), and "
                        "<strong>real-time messaging</strong> (freshness). Every architectural choice "
                        "is the cheapest answer to <em>two of those</em> while paying down the third "
                        "in latency, storage, or staleness."
                    ),
                },
            ],
        },
        # ---- 16 ------------------------------------------------------
        {
            "num": "16",
            "title": "Interview Playbook",
            "subtitle": "45-minute execution",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "News Feed is an everyone-asks-it design. The expected depth: hybrid fan-out "
                        "math, ML ranking layer, integrity, scale numbers. Most candidates hand-wave "
                        "the threshold; the strong ones derive it."
                    ),
                },
                {"type": "h3", "text": "45-Minute Time Budget"},
                {
                    "type": "table",
                    "headers": ["Window", "Phase", "Goal"],
                    "rows": [
                        ["00:00–02:00", "Clarify requirements", "Friends + pages + groups; ML ranked; 2B DAU"],
                        ["02:00–07:00", "Capacity estimation", "1B posts/day, 10B reads/day, 115K avg / 300K peak QPS"],
                        ["07:00–17:00", "High-level architecture", "Aggregator + Ranking + Action Logger + TAO + BLOB + Memcached + Kafka"],
                        ["17:00–32:00", "Hybrid fan-out deep dive", "Push vs pull, threshold math, worker pseudocode"],
                        ["32:00–40:00", "Ranking stack", "EdgeRank → DLRM, signals, multi-task, negative signals, action logging"],
                        ["40:00–45:00", "Trade-offs + failures", "Degradation order, sharding, hot pages"],
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>“2B DAU × 5 feeds / 86,400 = 115K reads/sec; peak ~300K”</strong> — capacity math, recited",
                        "<strong>“1B posts/day → 12K writes/sec; engagement ~10× → 120K/sec”</strong>",
                        "<strong>“Hybrid push/pull; threshold ~100K followers”</strong>",
                        "<strong>“Threshold isn't a magic number — it's where burst push exceeds cluster capacity”</strong>",
                        "<strong>“Self-injection delivers read-your-writes without strict consistency”</strong>",
                        "<strong>“5K candidates × 60 µs per score = 300 ms ranking budget”</strong>",
                        "<strong>“DLRM with multi-task heads (react, comment, share, dwell) − negative signals”</strong>",
                        "<strong>“Action logging closes the loop — 300B impressions/day fuel daily training”</strong>",
                        "<strong>“TAO over MySQL + Haystack/f4 + Memcached — polyglot at planet scale”</strong>",
                        "<strong>“Degrade ranking before dropping the feed itself”</strong>",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Strong Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why hybrid, not pure pull?</strong> A: Pure pull does 550-source scatter-gather per read at 115K reads/sec. The aggregate read load on TAO postlists would be ~63M partition reads/sec — far above cluster capacity. Push pre-builds 99% of the work.",
                        "<strong>Q: Why not pure push?</strong> A: A page with 100M followers posting causes 100M LPUSH in seconds. We'd need an order-of-magnitude bigger Memcached cluster just to absorb the burst. Pull amortises celeb cost across the day.",
                        "<strong>Q: How do you pick the threshold?</strong> A: It's the F where <code>F · w_push</code> exceeds your cluster's burst capacity per author class. We measure: at ~100K followers, a single post saturates one Memcached pod for ~2 s; that's our operational ceiling.",
                        "<strong>Q: How does a poster see their own post instantly?</strong> A: Self-injection — the client overlays the freshly-created post on top of the timeline locally. The async fan-out catches up within 60 s; dedup by post_id on overlap.",
                        "<strong>Q: What if the ranking model is down?</strong> A: Aggregator falls back to chronological merge of candidates and serves cached top-K from before the outage; banner indicates 'feed updating'.",
                        "<strong>Q: How do negative signals work?</strong> A: Hide → 30-day demotion of similar (same author, hashtag); snooze → hard exclusion from candidate gen; unfollow → graph edit. They're scarce but high-value training signals.",
                        "<strong>Q: How do you avoid filter bubbles?</strong> A: Diversity caps in re-rank (max 2 stories per author in top-30); injecting exploration items at low rate; integrity classifiers demote echo-chamber bait.",
                        "<strong>Q: Counter consistency?</strong> A: Sloppy — we use sub-shard counters and accept ±1% on viral posts. Exactness costs latency and almost no user notices.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Numbers to Memorise",
                    "body": (
                        "<strong>3B MAU / 2B DAU</strong> &nbsp;·&nbsp; "
                        "<strong>1B posts/day</strong> (12K/sec) &nbsp;·&nbsp; "
                        "<strong>10B feed reads/day</strong> (115K avg, 300K peak) &nbsp;·&nbsp; "
                        "<strong>5K candidates / 60 µs each / 300 ms total</strong> &nbsp;·&nbsp; "
                        "<strong>~30 stories per page</strong> &nbsp;·&nbsp; "
                        "<strong>~100K push/pull threshold</strong> &nbsp;·&nbsp; "
                        "<strong>~6 TB hot Memcached</strong> &nbsp;·&nbsp; "
                        "<strong>300B impressions/day</strong> for training."
                    ),
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "If You Get Stuck",
                    "body": (
                        "Anchor on the cost model. State the variables: F (followers), R (reads per "
                        "follower per day), w_push, w_pull. Write the inequality. The interviewer "
                        "wants to see you reason about <em>why</em> the threshold exists, not "
                        "memorise that it does."
                    ),
                },
            ],
        },
    ],
}
