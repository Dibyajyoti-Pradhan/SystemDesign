"""Source for `30 - ChatGPT.pdf` — Designing an LLM-powered chatbot at scale."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design ChatGPT",
    "subtitle": "LLM serving at scale: GPU pooling, KV-cache, streaming, safety, tiered routing",
    "read_time": "~ 45 minute read",
    "short_title": "Design ChatGPT",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Statement",
            "subtitle": "What we are building",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Design a chatbot service powered by a large language model "
                        "(<strong>ChatGPT-style</strong>) that answers user prompts in "
                        "real-time, streams tokens back as they are generated, remembers "
                        "the conversation, enforces safety, and serves hundreds of millions "
                        "of users on a fleet of GPUs whose capex is measured in hundreds of "
                        "millions of dollars."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Scale?", "~200M monthly active users; ~1B prompts/day"],
                        ["Latency target?", "&lt;500ms time-to-first-token; ~50 tokens/sec stream"],
                        ["Models served?", "Free (small), Paid flagship, Auto-route to thinking"],
                        ["Multi-turn?", "Yes, conversations are stateful and durable"],
                        ["Streaming?", "Yes, token-by-token via SSE / chunked HTTP"],
                        ["Safety?", "Pre-filter input, post-filter output, separate classifier"],
                        ["Rate limits?", "Token-bucket per user, org and tier"],
                        ["Tools/RAG?", "Out of scope here; focus on raw chat serving"],
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
                        ["Send message", "POST /v1/chat — accepts thread_id, prompt; returns SSE stream"],
                        ["List threads", "GET /v1/threads — paginated user history"],
                        ["Resume thread", "GET /v1/threads/:id — full message log"],
                        ["Stream tokens", "Server-Sent Events; one event per token chunk"],
                        ["Cancel", "DELETE /v1/chat/:request_id — abort decode mid-stream"],
                        ["Tier routing", "Free → 8B model; Pro → 70B; Auto → thinking model"],
                        ["Safety", "Refuse disallowed content; hide chain-of-thought"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["TTFT (time-to-first-token)", "p50 &lt; 300ms, p99 &lt; 1.5s"],
                        ["Throughput", "12K queries/sec avg, ~50K/sec peak"],
                        ["Stream rate", "~50 tok/sec/req for 70B model"],
                        ["Availability", "99.9%; degrade to smaller model on overload"],
                        ["Durability", "Conversation log retained 30 days hot, archive 1 year"],
                        ["GPU utilisation", "&gt; 70% sustained on flagship cluster"],
                        ["Cost ceiling", "Free tier: ~$0.005/query; Paid: ~$0.05/query"],
                    ],
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "Math for serving an LLM at planet scale",
            "blocks": [
                {"type": "h3", "text": "Traffic"},
                {
                    "type": "bullets",
                    "items": [
                        "MAU: <strong>200M</strong>; ~5 prompts/active-day → <strong>~1B prompts/day</strong>",
                        "Average QPS: 1B / 86,400 ≈ <strong>~12K QPS</strong>",
                        "Peak QPS (4× avg, US-EU overlap): <strong>~50K QPS</strong>",
                        "Concurrent in-flight decodes (avg 10 sec/req): 12K × 10 ≈ <strong>120K concurrent</strong>",
                    ],
                },
                {"type": "h3", "text": "Token Economics"},
                {
                    "type": "bullets",
                    "items": [
                        "Avg context (system + history + prompt): <strong>~200 tokens</strong>",
                        "Avg response: <strong>~500 tokens</strong>",
                        "Total tokens generated/day: 1B × 500 = <strong>500B output tokens/day</strong>",
                        "Total prefill tokens/day: 1B × 200 = <strong>200B input tokens/day</strong>",
                    ],
                },
                {"type": "h3", "text": "GPU Fleet"},
                {
                    "type": "bullets",
                    "items": [
                        "Per-request decode rate (70B flagship): <strong>~50 tokens/sec</strong>",
                        "Per-GPU concurrent batch (paged attention, 8K ctx): <strong>~8–32 reqs</strong>",
                        "Throughput per H100 ≈ 16 reqs × 50 tok/s = <strong>~800 tok/sec/GPU</strong>",
                        "Output capacity needed: 500B / 86,400 ≈ <strong>5.8M tok/sec</strong>",
                        "Required GPUs (output-bound): 5.8M / 800 ≈ <strong>~7,250</strong> + headroom → <strong>~10K GPUs</strong>",
                        "H100 capex ~$30K each → <strong>~$300M capex</strong> for the flagship cluster",
                    ],
                },
                {"type": "h3", "text": "KV-Cache Memory"},
                {
                    "type": "bullets",
                    "items": [
                        "Per-token KV (70B, fp16, 80 layers, GQA): <strong>~2 MB / token / request</strong>",
                        "Per-request at 8K context: 8,192 × 2 MB ≈ <strong>16 GB</strong>",
                        "H100 has 80 GB HBM; weights ~140 GB sharded across 2 GPUs (TP=2)",
                        "Free HBM per GPU after weights ≈ 80 - 70 = <strong>~10 GB for KV</strong>",
                        "Paged attention packs many partial sequences into shared 16-token blocks",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "200M MAU &nbsp;·&nbsp; 1B prompts/day &nbsp;·&nbsp; "
                        "12K QPS avg / 50K peak &nbsp;·&nbsp; 500 tok response &nbsp;·&nbsp; "
                        "200 tok context &nbsp;·&nbsp; 50 tok/sec/req &nbsp;·&nbsp; "
                        "2 MB KV/tok/req &nbsp;·&nbsp; 16 GB KV @ 8K &nbsp;·&nbsp; "
                        "10K H100 cluster ≈ $300M capex"
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level Architecture",
            "subtitle": "From client tap to GPU and back",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "User traffic enters the <strong>API Gateway</strong> "
                        "(authentication, rate-limiting, tier resolution), is handled by the "
                        "<strong>Conversation Service</strong> which loads thread state, runs "
                        "<strong>safety pre-filtering</strong> and selects a model via the "
                        "<strong>Model Router</strong>. The request then joins a continuous "
                        "batch on a <strong>Model Server</strong>; tokens stream back through "
                        "an <strong>SSE</strong> connection while a <strong>safety post-"
                        "filter</strong> watches the output stream. Conversation state lives in "
                        "Redis (hot) and Postgres (durable); usage events flow to Kafka for "
                        "billing."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Request flow: gateway → conversation service → safety pre-filter → router → model server (continuous batching on GPU) → safety post-filter → SSE stream. Side path: Redis + Postgres for thread state; Kafka for usage and billing.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Client"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Client [label="Web / Mobile / API\n(SSE consumer)", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        GW [label="API Gateway\n(auth, rate-limit,\ntier resolve)", fillcolor="#cbeedf"];
    }
    subgraph cluster_app {
        label="App Tier"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        CS  [label="Conversation\nService",      fillcolor="#fff2c9"];
        SafePre  [label="Safety\nPre-filter",    fillcolor="#fff2c9"];
        Router   [label="Model Router\n(tier→model)", fillcolor="#fff2c9"];
        SafePost [label="Safety\nPost-filter",   fillcolor="#fff2c9"];
    }
    subgraph cluster_gpu {
        label="GPU Cluster"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        Sched [label="Continuous-batch\nScheduler", fillcolor="#ead7fb"];
        Small [label="8B Model Pool\n(free tier)",  fillcolor="#ead7fb"];
        Big   [label="70B Model Pool\n(paid)",      fillcolor="#ead7fb"];
        Think [label="Thinking Model\n(auto-route)", fillcolor="#ead7fb"];
    }
    subgraph cluster_state {
        label="State + Telemetry"; style="rounded,dashed"; color="#963f23"; fontcolor="#963f23";
        Redis [label="Redis\n(hot threads,\nKV-cache index)", fillcolor="#fbd7c5"];
        PG    [label="Postgres\n(durable threads,\nusage)",   fillcolor="#fbd7c5"];
        Kafka [label="Kafka\n(usage events)", fillcolor="#fbd7c5"];
        Bill  [label="Billing /\nAnalytics",  fillcolor="#fbd7c5"];
    }

    Client -> GW [label="POST /chat (SSE)"];
    GW -> CS;
    CS -> Redis [label="load thread"];
    CS -> SafePre;
    SafePre -> Router;
    Router -> Sched;
    Sched -> Small [style=dashed];
    Sched -> Big   [style=dashed];
    Sched -> Think [style=dashed];
    Sched -> SafePost [label="token stream"];
    SafePost -> Client [label="SSE chunks", color="#1f8359"];
    CS -> PG    [label="append messages"];
    CS -> Kafka [label="usage event"];
    Kafka -> Bill;
}
""",
                },
                {"type": "h3", "text": "Architecture Highlights"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>API Gateway:</strong> JWT auth, token-bucket rate-limit, resolves user tier",
                        "<strong>Conversation Service:</strong> stateful coordinator; loads thread, owns SSE socket",
                        "<strong>Safety pre-filter:</strong> blocks prompt-injection / disallowed content before GPU",
                        "<strong>Model Router:</strong> picks 8B / 70B / thinking model; degrades on overload",
                        "<strong>Continuous-batch scheduler:</strong> joins new requests into in-flight batch each step",
                        "<strong>Safety post-filter:</strong> classifies streaming output; can interrupt + apologise",
                        "<strong>Redis:</strong> hot conversation state; KV-cache locality hints",
                        "<strong>Postgres:</strong> durable message log + usage; sharded by user_id",
                        "<strong>Kafka:</strong> async usage + billing pipeline; never blocks the chat path",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "GPU Pooling & Model Placement",
            "subtitle": "Sharing $300M of silicon",
            "blocks": [
                {"type": "h3", "text": "Cluster Layout"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Pods:</strong> 8 H100 GPUs per node (NVLink); racks of 8 nodes (64 GPUs)",
                        "<strong>Tensor parallelism:</strong> 70B fp16 weights → 140 GB; TP=2 fits on 2× H100",
                        "<strong>Pipeline parallelism:</strong> across nodes for thinking model (200B+)",
                        "<strong>Replica:</strong> a model deployment = TP-group; many replicas behind router",
                        "<strong>Pool sizing:</strong> 8B pool ~30% of GPUs, 70B pool ~60%, thinking ~10%",
                    ],
                },
                {"type": "h3", "text": "Why Pools, Not Per-User Allocation"},
                {
                    "type": "bullets",
                    "items": [
                        "Per-user GPU is wasteful: each H100 must run at &gt;70% util to amortise capex",
                        "Continuous batching mixes requests from different users on the same GPU step",
                        "Pool model: route a request to the least-loaded replica that hosts the right model",
                        "Affinity hint: send follow-up messages to the same replica to reuse prefix KV-cache",
                    ],
                },
                {"type": "h3", "text": "GPU Economics Cheat-Sheet"},
                {
                    "type": "table",
                    "headers": ["Resource", "Number"],
                    "rows": [
                        ["H100 capex (street)", "~$30,000 per GPU"],
                        ["10K-GPU cluster capex", "~$300M (excludes networking, power, DC)"],
                        ["DGX H100 server (8 GPUs)", "~$300K"],
                        ["Power", "~700W per H100; ~10 MW for 10K-GPU cluster"],
                        ["Useful life", "3–4 years before next-gen replacement"],
                        ["Effective $ / 1M tokens (70B)", "~$1–3 amortised at 70% util"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why Utilisation Is Everything",
                    "body": (
                        "A 10K-GPU cluster sitting at 30% utilisation costs the same as one at "
                        "90% utilisation. Continuous batching, prompt caching and KV-cache reuse "
                        "exist to push that number up. A 10-point utilisation gain on a $300M "
                        "cluster is roughly $30M of effective capacity."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Continuous Batching",
            "subtitle": "vLLM / TensorRT-LLM style scheduling",
            "blocks": [
                {"type": "h3", "text": "Static vs Continuous"},
                {
                    "type": "table",
                    "headers": ["Aspect", "Static batching", "Continuous batching"],
                    "rows": [
                        ["Batch composition", "Fixed at start, decodes together",
                         "Dynamic; new reqs join each decode step"],
                        ["Tail latency", "Bad — fast reqs wait for slowest in batch",
                         "Good — finished slots free immediately"],
                        ["GPU utilisation", "Drops as sequences finish",
                         "Stays high; padding minimal"],
                        ["Implementation", "Simple",
                         "Requires paged KV-cache + iteration-level scheduler"],
                        ["Used by", "Naive HF pipeline",
                         "vLLM, TensorRT-LLM, TGI, Triton"],
                    ],
                },
                {"type": "h3", "text": "Continuous Batching Loop (pseudocode)"},
                {
                    "type": "code",
                    "text": (
                        "# Iteration-level scheduler that runs forever on each replica.\n"
                        "active = []                # in-flight requests\n"
                        "wait_q = priority_queue()  # admitted but not yet started\n\n"
                        "while True:\n"
                        "    # 1. Admit new requests until KV-cache budget is full.\n"
                        "    while wait_q and kv_pool.has_room_for(wait_q.peek()):\n"
                        "        req = wait_q.pop()\n"
                        "        kv_pool.allocate_blocks(req, prefill_len=len(req.prompt))\n"
                        "        prefill(req)              # one big GEMM, fills KV for prompt\n"
                        "        active.append(req)\n\n"
                        "    if not active:\n"
                        "        sleep(small); continue\n\n"
                        "    # 2. One decode step for the whole active batch.\n"
                        "    logits = model.decode_step(active)   # batched matmul on GPU\n"
                        "    for req, tok in zip(active, sample(logits)):\n"
                        "        req.append(tok)\n"
                        "        sse_send(req.client, tok)\n"
                        "        if tok == EOS or req.len >= req.max_tokens:\n"
                        "            kv_pool.free(req)\n"
                        "            active.remove(req)\n"
                        "            sse_close(req.client)\n"
                        "    # 3. KV-cache may now have room → loop back to admission.\n"
                    ),
                },
                {"type": "h3", "text": "Engine Comparison"},
                {
                    "type": "table",
                    "headers": ["Engine", "Strengths", "Weaknesses"],
                    "rows": [
                        ["vLLM",
                         "Open-source; PagedAttention; great throughput; easy ops",
                         "Slightly behind on cutting-edge kernels; Python overhead"],
                        ["TensorRT-LLM",
                         "Fastest single-stream latency; FP8 / fused kernels; NVIDIA tuned",
                         "Closed-source kernels; per-model build step; harder to operate"],
                        ["Triton Inference Server",
                         "Multi-framework; mature ops; ensembles",
                         "Not LLM-aware on its own; needs vLLM/TRT-LLM backend for batching"],
                    ],
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "KV-Cache Management",
            "subtitle": "Paged attention and reuse",
            "blocks": [
                {"type": "h3", "text": "What the KV-Cache Is"},
                {
                    "type": "bullets",
                    "items": [
                        "Each transformer layer caches <strong>K</strong> and <strong>V</strong> projections of every prior token so decode is O(1) per token, not O(n²)",
                        "Per-token size (70B, fp16, 80 layers, GQA 8 heads): <strong>~2 MB / token / request</strong>",
                        "At 8K context: 8,192 × 2 MB = <strong>~16 GB</strong> per request",
                        "Without paging this is allocated as one giant slab → fragmentation and OOM",
                    ],
                },
                {"type": "h3", "text": "Paged Attention"},
                {
                    "type": "bullets",
                    "items": [
                        "Borrow OS virtual-memory idea: split KV into fixed <strong>16-token blocks</strong>",
                        "Each request owns a <strong>page table</strong> mapping logical positions → physical blocks",
                        "Blocks live in a shared GPU pool; allocate on demand as the sequence grows",
                        "Different requests can <strong>share</strong> blocks for an identical prefix (e.g. system prompt)",
                        "Eviction policy: least-recently-used full sequence; never mid-decode",
                    ],
                },
                {"type": "h3", "text": "Logical Layout"},
                {
                    "type": "code",
                    "text": (
                        "# KV-cache page table for one request.\n"
                        "{\n"
                        "  \"request_id\": \"req_98ab\",\n"
                        "  \"model\":      \"flagship-70b\",\n"
                        "  \"block_size\": 16,                 # tokens per block\n"
                        "  \"page_table\": [\n"
                        "    {\"logical\": 0,  \"physical\": 12048, \"shared\": true },\n"
                        "    {\"logical\": 1,  \"physical\": 12049, \"shared\": true },\n"
                        "    {\"logical\": 2,  \"physical\": 30771, \"shared\": false},\n"
                        "    ...\n"
                        "  ],\n"
                        "  \"prefix_hash\": \"sha256(system+history)\",  # for sharing\n"
                        "  \"ref_count\":  1\n"
                        "}\n"
                        "# Shared blocks: ref_count > 1; copy-on-write if a divergent token is sampled."
                    ),
                },
                {"type": "h3", "text": "Reuse Wins"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Multi-turn reuse:</strong> follow-up message keeps prior turns in cache → skip prefill for them",
                        "<strong>System prompt cache:</strong> a 2K-token system prompt shared across millions of users — prefill it <em>once</em>",
                        "<strong>Beam / parallel sampling:</strong> multiple candidates share the prompt blocks",
                        "<strong>Hash-keyed:</strong> hash(model + tokens) → physical block id; lookup before allocate",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Why Paging Beats Slabs",
                    "body": (
                        "Slab allocation reserves max_context_len up front for every request. "
                        "If the request finishes at 200 tokens but reserved 8,192, you wasted "
                        "~16 GB. Paging only allocates blocks you actually fill, so a busy "
                        "replica can serve 4-8× more concurrent requests on the same HBM."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Streaming Responses (SSE)",
            "subtitle": "Token-by-token to the browser",
            "blocks": [
                {"type": "h3", "text": "Why Stream"},
                {
                    "type": "bullets",
                    "items": [
                        "A 500-token reply at 50 tok/sec is a 10-second wait if buffered; unacceptable UX",
                        "Streaming hides latency: user starts reading after &lt;500ms TTFT",
                        "Lets users <strong>cancel</strong> mid-generation and free GPU time",
                    ],
                },
                {"type": "h3", "text": "SSE vs WebSocket vs gRPC"},
                {
                    "type": "table",
                    "headers": ["Transport", "Pros", "Cons"],
                    "rows": [
                        ["SSE (chunked HTTP)",
                         "One-way; works through proxies; auto-reconnect; trivial in browser",
                         "HTTP/1.1 6-conn limit per host; no native binary"],
                        ["WebSocket",
                         "Bidirectional; binary; lower per-msg overhead",
                         "Harder through corporate proxies; manual reconnect"],
                        ["gRPC server-streaming",
                         "Strong typing; HTTP/2 multiplex; great server-to-server",
                         "Browser support requires gRPC-Web shim"],
                    ],
                },
                {"type": "h3", "text": "SSE Wire Format"},
                {
                    "type": "code",
                    "text": (
                        "HTTP/1.1 200 OK\n"
                        "Content-Type: text/event-stream\n"
                        "Cache-Control: no-cache\n"
                        "Connection: keep-alive\n\n"
                        "event: token\n"
                        "data: {\"t\":\"Hello\",\"i\":0}\n\n"
                        "event: token\n"
                        "data: {\"t\":\" world\",\"i\":1}\n\n"
                        "event: usage\n"
                        "data: {\"prompt_tok\":42,\"completion_tok\":18}\n\n"
                        "event: done\n"
                        "data: [DONE]\n\n"
                    ),
                },
                {"type": "h3", "text": "Server-Side Plumbing"},
                {
                    "type": "bullets",
                    "items": [
                        "Conversation Service holds the SSE socket; subscribes to a Redis channel keyed by request_id",
                        "Model Server publishes each generated token chunk to that channel",
                        "Cancel: client closes SSE → Conversation Service publishes <code>cancel</code> → scheduler removes request, frees KV blocks",
                        "<strong>Mid-stream migration is hard</strong> — if the GPU pod dies, surface a clear error and let the client retry; do not try to resume",
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Conversation Memory",
            "subtitle": "Threads in Redis + Postgres",
            "blocks": [
                {"type": "h3", "text": "Storage Tiers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Redis (hot):</strong> active threads in last 24h; full message log; ~1ms reads",
                        "<strong>Postgres (durable):</strong> all threads; sharded by user_id; source of truth",
                        "<strong>Object storage (cold):</strong> threads &gt; 30 days old → S3/GCS for compliance"
                    ],
                },
                {"type": "h3", "text": "Thread Schema"},
                {
                    "type": "code",
                    "text": (
                        "-- Postgres, sharded by user_id\n"
                        "CREATE TABLE threads (\n"
                        "  thread_id     UUID PRIMARY KEY,\n"
                        "  user_id       BIGINT NOT NULL,\n"
                        "  title         TEXT,\n"
                        "  model         TEXT,           -- last model used\n"
                        "  created_at    TIMESTAMPTZ DEFAULT NOW(),\n"
                        "  updated_at    TIMESTAMPTZ,\n"
                        "  msg_count     INT DEFAULT 0,\n"
                        "  total_tokens  BIGINT DEFAULT 0\n"
                        ");\n\n"
                        "CREATE TABLE messages (\n"
                        "  msg_id        BIGSERIAL PRIMARY KEY,\n"
                        "  thread_id     UUID REFERENCES threads,\n"
                        "  role          TEXT,           -- 'system' | 'user' | 'assistant'\n"
                        "  content       TEXT,\n"
                        "  prompt_tok    INT,\n"
                        "  completion_tok INT,\n"
                        "  model         TEXT,\n"
                        "  created_at    TIMESTAMPTZ DEFAULT NOW(),\n"
                        "  INDEX idx_thread_time (thread_id, created_at)\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "Read / Write Path"},
                {
                    "type": "numbered",
                    "items": [
                        "Conversation Service receives <code>POST /v1/chat</code>",
                        "<code>GET</code> thread from Redis; if miss, load from Postgres and warm Redis",
                        "Append user message to thread (write-through to both stores)",
                        "Compose prompt: system prompt + last N turns (token-budgeted)",
                        "Stream assistant response; buffer the full response",
                        "On <code>done</code> event: append assistant message; <code>UPDATE threads SET ...</code>; emit usage event to Kafka",
                    ],
                },
                {"type": "h3", "text": "Context Window Budgeting"},
                {
                    "type": "bullets",
                    "items": [
                        "Reserve ~25% of model context for the response (e.g. 32K total → 8K reserved)",
                        "Walk history newest-first; include while running token total ≤ budget",
                        "Drop oldest turns; never split a single message in half",
                        "For very long threads: produce a <strong>running summary</strong> with the cheaper model and prepend it",
                    ],
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Tiered Routing",
            "subtitle": "Free, Paid, Auto-thinking",
            "blocks": [
                {"type": "h3", "text": "Tiers"},
                {
                    "type": "table",
                    "headers": ["Tier", "Default model", "Limits", "Cost target"],
                    "rows": [
                        ["Free", "8B fast model", "40 msgs / 3 hours", "&lt; $0.005 / query"],
                        ["Plus", "70B flagship", "80 msgs / 3 hours", "~$0.05 / query"],
                        ["Pro", "70B + thinking", "Effectively unlimited; soft cap", "~$0.20 / query"],
                        ["Enterprise", "Dedicated capacity", "SLA + custom RPS", "Negotiated"],
                    ],
                },
                {"type": "h3", "text": "Routing Logic"},
                {
                    "type": "bullets",
                    "items": [
                        "Gateway resolves <code>tier = user.plan</code>; passes through to Router",
                        "Router has a static map: tier → eligible model pools",
                        "<strong>Auto-route</strong> (Pro): a small classifier inspects the prompt; complex/STEM/multi-step → thinking model, simple chat → flagship",
                        "<strong>Overload degradation:</strong> if 70B pool queue depth &gt; threshold, downgrade non-Plus traffic to 8B with a note",
                        "Sticky routing on follow-up: send to a replica that already has the prior turns' KV-cache",
                    ],
                },
                {"type": "h3", "text": "Thinking Model"},
                {
                    "type": "bullets",
                    "items": [
                        "Generates a hidden chain-of-thought, then a final answer",
                        "Latency budget: 10–60 seconds; GPU-cost ~5–10× of flagship",
                        "Hide the chain-of-thought in API responses; show a UI <em>“thinking…”</em> indicator",
                        "Use only when classifier confidence × user tier justifies it",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Rate Limiting",
            "subtitle": "Token-bucket per user, org and tier",
            "blocks": [
                {"type": "h3", "text": "Why Token-Bucket"},
                {
                    "type": "bullets",
                    "items": [
                        "Smooth bursts (a power user firing 10 messages in 30 sec) without permanent over-allocation",
                        "Stateless to clients; tiny state in Redis (one counter + timestamp)",
                        "Two buckets per request: <strong>requests/min</strong> and <strong>tokens/min</strong>",
                    ],
                },
                {"type": "h3", "text": "Bucket Config"},
                {
                    "type": "table",
                    "headers": ["Tier", "Req/min", "Input tok/min", "Output tok/min"],
                    "rows": [
                        ["Free", "20", "20K", "10K"],
                        ["Plus", "60", "120K", "60K"],
                        ["Pro", "200", "500K", "250K"],
                        ["Enterprise", "Negotiated", "Negotiated", "Negotiated"],
                    ],
                },
                {"type": "h3", "text": "Implementation Sketch"},
                {
                    "type": "code",
                    "text": (
                        "# Atomic refill+decrement using a Redis Lua script.\n"
                        "# KEYS[1] = bucket key   ARGV = capacity, refill_rate, now, cost\n"
                        "LUA = '''\n"
                        "local data    = redis.call('HMGET', KEYS[1], 'tokens', 'ts')\n"
                        "local tokens  = tonumber(data[1]) or tonumber(ARGV[1])\n"
                        "local last_ts = tonumber(data[2]) or tonumber(ARGV[3])\n"
                        "local now     = tonumber(ARGV[3])\n"
                        "tokens = math.min(tonumber(ARGV[1]),\n"
                        "                  tokens + (now - last_ts) * tonumber(ARGV[2]))\n"
                        "if tokens < tonumber(ARGV[4]) then\n"
                        "  return {0, tokens}                         -- 429\n"
                        "end\n"
                        "tokens = tokens - tonumber(ARGV[4])\n"
                        "redis.call('HMSET', KEYS[1], 'tokens', tokens, 'ts', now)\n"
                        "redis.call('EXPIRE', KEYS[1], 600)\n"
                        "return {1, tokens}                            -- OK\n"
                        "'''\n\n"
                        "# Two checks per request: rl:user:<id>:req and rl:user:<id>:tok\n"
                        "# org bucket also checked when present"
                    ),
                },
                {"type": "h3", "text": "Where It Lives"},
                {
                    "type": "bullets",
                    "items": [
                        "Front-line check at API Gateway → fast reject, no GPU touched",
                        "Second check inside Conversation Service against <em>actual</em> token usage post-decode",
                        "Output-token bucket is debited as the SSE stream progresses; can stop mid-stream and 429",
                    ],
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Safety Pipeline",
            "subtitle": "Pre-filter → model → post-filter",
            "blocks": [
                {"type": "h3", "text": "Three Layers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Input filter:</strong> prompt-injection, jailbreak patterns, disallowed content (CSAM, weapons, etc.)",
                        "<strong>Model alignment:</strong> RLHF-trained refusal behaviour for in-policy edges",
                        "<strong>Output filter:</strong> classifier on streaming tokens; also a final policy check on the full response",
                    ],
                },
                {"type": "h3", "text": "Why a Separate Classifier"},
                {
                    "type": "bullets",
                    "items": [
                        "Faster: a 1B-param classifier runs in &lt;20ms on a tiny GPU",
                        "Independently versioned: safety teams ship updates without touching the flagship",
                        "Defence in depth: catches model failures (the model said yes; classifier says no)",
                    ],
                },
                {"type": "h3", "text": "Streaming Post-Filter"},
                {
                    "type": "numbered",
                    "items": [
                        "Tokens flow from Model Server to Safety Post-filter via Redis Pub/Sub",
                        "Post-filter buffers ~32 tokens at a time and runs the classifier",
                        "If a chunk scores above threshold: stop the stream, send <code>event: blocked</code> to client, cancel the underlying decode",
                        "Otherwise forward the chunk to SSE — adds &lt;30ms p50 to TTFT",
                    ],
                },
                {"type": "h3", "text": "Prompt-Injection Defences"},
                {
                    "type": "bullets",
                    "items": [
                        "Strip HTML / role markers (e.g. <code>&lt;/im_start&gt;</code>) from user content",
                        "Ignore instructions embedded inside tool outputs (mark them as data, not instructions)",
                        "Run the input filter against both the new turn <em>and</em> any retrieved/pasted context",
                        "Audit log: store {user_id, hash(prompt), classifier scores, decision} for review",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Strictness vs Helpfulness",
                    "body": (
                        "Setting the classifier threshold too low blocks benign questions and "
                        "users churn. Too high and policy violations leak. Calibrate per "
                        "category (e.g. tighter on medical advice, looser on programming) and "
                        "track false-positive rate as a first-class SLO."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Cost Optimisations",
            "subtitle": "Squeezing more tokens per dollar",
            "blocks": [
                {"type": "h3", "text": "KV-Cache Reuse (Multi-Turn)"},
                {
                    "type": "bullets",
                    "items": [
                        "Reuse the prior turns' KV blocks if they are still in HBM on the same replica",
                        "Saves the prefill GEMM for everything except the new user message — typical multi-turn save: <strong>30–60% of prefill cost</strong>",
                        "Requires sticky routing: <code>thread_id → replica</code> via consistent hash",
                    ],
                },
                {"type": "h3", "text": "Prompt Caching"},
                {
                    "type": "bullets",
                    "items": [
                        "System prompts and few-shot exemplars are identical across millions of requests",
                        "Hash the prefix; if hash already maps to allocated KV blocks, point the new request at them",
                        "<strong>10× reduction</strong> in prefill cost for boilerplate-heavy assistants",
                    ],
                },
                {"type": "h3", "text": "Speculative Decoding"},
                {
                    "type": "bullets",
                    "items": [
                        "Use a small <strong>draft model</strong> (e.g. 1B) to propose <em>k</em> tokens at a time",
                        "Big model verifies all <em>k</em> in one forward pass; accepts the longest matching prefix",
                        "Speed-up: 2–3× on natural text where draft is usually right",
                    ],
                },
                {"type": "h3", "text": "Speculative Decoding Sketch"},
                {
                    "type": "code",
                    "text": (
                        "# Speculative decoding outer loop.\n"
                        "while not done:\n"
                        "    # 1. Draft model proposes k=4 cheap tokens.\n"
                        "    draft = small_model.generate_k(state, k=4)\n\n"
                        "    # 2. Big model evaluates them in ONE forward pass.\n"
                        "    big_logits = big_model.forward(state + draft)\n\n"
                        "    # 3. Accept the longest prefix where big agrees with draft.\n"
                        "    accepted = []\n"
                        "    for i, tok in enumerate(draft):\n"
                        "        if argmax(big_logits[i]) == tok:\n"
                        "            accepted.append(tok)\n"
                        "        else:\n"
                        "            accepted.append(argmax(big_logits[i]))   # correction\n"
                        "            break\n"
                        "    state += accepted\n"
                        "    sse_send(client, accepted)\n"
                        "# Net effect: 1 big-model call yielded ~2.5 tokens on average."
                    ),
                },
                {"type": "h3", "text": "MoE Routing"},
                {
                    "type": "bullets",
                    "items": [
                        "Mixture-of-Experts: 200B params total, only ~20B active per token",
                        "Router gates each token to top-2 experts; effective FLOPs ≈ a 20B dense model",
                        "Memory-bound, not compute-bound: needs lots of HBM but few FLOPs",
                        "Pairs well with continuous batching; expert imbalance is the main risk",
                    ],
                },
                {"type": "h3", "text": "Other Levers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Quantisation:</strong> fp16 → fp8 / int4 on weights; ~2× throughput, small quality hit",
                        "<strong>FlashAttention-2/3:</strong> kernel-level memory + compute wins (free)",
                        "<strong>Heterogeneous fleet:</strong> route free-tier to older A100s; flagship to H100/B200",
                        "<strong>Off-peak batch jobs:</strong> evals, fine-tunes run at night when chat QPS dips",
                    ],
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Inference Batching Diagram",
            "subtitle": "How a request lives and dies on a GPU",
            "blocks": [
                {
                    "type": "diagram",
                    "caption": "Continuous-batching scheduler: incoming requests join the in-flight batch each decode step. When a sequence emits EOS its KV blocks are freed and the slot is reused. Tokens stream out as SSE.",
                    "dot": r"""
digraph B {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Incoming [label="Incoming\nrequests", fillcolor="#dbe6fb"];

    subgraph cluster_sched {
        label="Continuous-Batch Scheduler"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        Admit [label="Admission\n(KV-budget check)", fillcolor="#fff2c9"];
        Prefill [label="Prefill\n(prompt → KV)", fillcolor="#fff2c9"];
        Active [label="Active batch\n(in-flight reqs)", fillcolor="#fff2c9"];
    }

    subgraph cluster_gpu {
        label="GPU"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        Step    [label="Decode step\n(1 token / req)", fillcolor="#ead7fb"];
        KV      [label="Paged KV-cache\n(shared blocks)", fillcolor="#ead7fb"];
    }

    Done [label="Sequence done\n(EOS / max_tok)", fillcolor="#cbeedf"];
    SSE  [label="SSE stream\nto client", fillcolor="#cbeedf"];
    Free [label="Free KV blocks\n→ slot reused", fillcolor="#cbeedf"];

    Incoming -> Admit;
    Admit -> Prefill -> Active;
    Active -> Step [label="batched"];
    Step -> KV [dir=both, label="read/write\n2 MB/tok"];
    Step -> Active [label="next iter"];
    Step -> SSE [label="token chunk", color="#1f8359"];
    Step -> Done [label="EOS"];
    Done -> Free;
    Free -> Admit [label="capacity\nrestored", style=dashed];
}
""",
                },
                {"type": "h3", "text": "What This Buys You"},
                {
                    "type": "bullets",
                    "items": [
                        "Decode step is a single batched matmul over <em>all</em> active requests — GPU stays busy",
                        "Sequences finish independently; free slot is filled within one iteration",
                        "Admission control on KV-budget prevents OOM-induced full-replica crashes",
                        "Prefill and decode share the same engine; new arrivals don't stall ongoing streams",
                    ],
                },
            ],
        },
        # ---- 15 ------------------------------------------------------
        {
            "num": "15",
            "title": "Failure Modes & Trade-offs",
            "subtitle": "Things that break and decisions to defend",
            "blocks": [
                {"type": "h3", "text": "Failure Modes"},
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["KV-cache OOM on long context",
                         "Active reqs killed; replica thrash",
                         "HBM &gt; 95% gauge",
                         "Admission control on KV budget; spillover to swap is a no-go"],
                        ["GPU pod crash mid-stream",
                         "All in-flight streams die; SSE closes",
                         "Health check; missing heartbeats",
                         "Surface clear error to user; client retries new turn — <strong>do not try to migrate</strong>"],
                        ["Prompt-injection attack",
                         "Model leaks system prompt or PII",
                         "Output classifier; red-team probes",
                         "Pre-filter; treat retrieved/pasted context as data, not instructions"],
                        ["Thinking model latency spike",
                         "p99 blows through 60s SLA",
                         "Latency histogram alert",
                         "Fall back to flagship + apology; cap thinking budget"],
                        ["Hot replica (sticky routing)",
                         "One replica saturates while others idle",
                         "Per-replica QPS skew",
                         "Bound stickiness; fall back to least-loaded after threshold"],
                        ["Postgres shard down",
                         "Cannot persist new messages",
                         "Conn errors",
                         "Buffer in Redis; replay; serve in read-only degraded mode"],
                        ["Safety classifier false positive spike",
                         "Benign answers blocked; user churn",
                         "Block rate + complaint rate",
                         "Roll back classifier version; tune thresholds per category"],
                    ],
                },
                {"type": "h3", "text": "Trade-offs"},
                {
                    "type": "table",
                    "headers": ["Decision", "Choice", "Trade-off"],
                    "rows": [
                        ["Latency vs throughput",
                         "Continuous batching at moderate batch size",
                         "Larger batches → higher throughput but higher TTFT; tune per pool"],
                        ["KV-cache eviction",
                         "Never evict an active sequence; reject new admits instead",
                         "Better tail latency for in-flight; new requests queue under load"],
                        ["Safety strictness vs helpfulness",
                         "Per-category thresholds + RLHF",
                         "Stricter loses users; looser leaks policy violations"],
                        ["Paid model cost vs free experience",
                         "Free → 8B; Pro → 70B + thinking",
                         "Free quality must be good enough to convert; paid must be worth $20/mo"],
                        ["Streaming protocol",
                         "SSE",
                         "Trivial in browser; tiny per-token overhead vs WebSocket binary"],
                        ["State storage",
                         "Redis hot + Postgres durable",
                         "Two systems to operate; double-write race rare and reconcilable"],
                        ["Mid-stream resume",
                         "Not supported",
                         "Simpler design; one bad pod = one bad turn, not a cluster-wide bug"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful Degradation Hierarchy",
                    "body": (
                        "Under overload: (1) shorten max_tokens, (2) downgrade Auto/thinking → "
                        "flagship, (3) downgrade flagship → 8B for free tier with a banner, "
                        "(4) shed traffic with 429. Never deliver a hung connection — fail fast "
                        "with a typed error so the client can retry."
                    ),
                },
            ],
        },
        # ---- 16 ------------------------------------------------------
        {
            "num": "16",
            "title": "Interview Playbook",
            "subtitle": "How to present this in 45 minutes",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "LLM serving questions reward candidates who can do GPU economics in "
                        "their head, name the right systems primitives (paged attention, "
                        "continuous batching, SSE), and remember that this is fundamentally "
                        "a constrained-resource scheduling problem on a $300M cluster."
                    ),
                },
                {"type": "h3", "text": "45-Minute Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (2 min):</strong> 200M MAU, ~1B prompts/day, multi-turn, streaming, safety",
                        "<strong>Capacity (6 min):</strong> 12K QPS, 50 tok/s/req, 2 MB KV/tok, ~10K H100s, ~$300M capex",
                        "<strong>High-level arch (4 min):</strong> Gateway → Conversation Svc → Safety → Router → GPU pool → SSE",
                        "<strong>Continuous batching (8 min):</strong> static vs continuous; iteration-level scheduling pseudocode",
                        "<strong>KV-cache (6 min):</strong> paged attention, prefix sharing, prompt caching",
                        "<strong>Streaming + memory (5 min):</strong> SSE, Redis hot + Postgres durable",
                        "<strong>Routing + rate limit (4 min):</strong> tier map, token-bucket, auto-route to thinking",
                        "<strong>Safety (4 min):</strong> pre/post filters, separate classifier, prompt injection",
                        "<strong>Cost levers (4 min):</strong> KV reuse, prompt cache, speculative decoding, MoE",
                        "<strong>Failures (2 min):</strong> KV OOM, GPU crash mid-stream, sticky-replica skew",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: How big is the KV-cache?</strong> A: ~2 MB per token per request for a 70B model; 16 GB at 8K context. Paged attention packs partial sequences into 16-token blocks.",
                        "<strong>Q: Why continuous over static batching?</strong> A: Static makes fast requests wait for the slowest; GPU util drops as sequences finish. Continuous fills slots every step → 2–4× throughput at the same latency.",
                        "<strong>Q: How do you stream?</strong> A: SSE over chunked HTTP. Conversation Service holds the socket; Model Server publishes tokens via Redis Pub/Sub; Safety post-filter sits between them.",
                        "<strong>Q: What happens if a GPU pod dies mid-response?</strong> A: We surface a typed error and let the client retry. Mid-stream migration is intractable because KV-cache is GPU-resident and context-specific.",
                        "<strong>Q: How do you protect against prompt injection?</strong> A: Pre-filter classifier on input + retrieved context, treat tool outputs as data, hide chain-of-thought, post-filter on output.",
                        "<strong>Q: How do you make the free tier cheap?</strong> A: Smaller model (8B), aggressive prompt caching, lower rate limits, off-peak capacity sharing, quantisation to int4 weights.",
                        "<strong>Q: Speculative decoding — when is it a loss?</strong> A: When the draft and big model disagree often (code with tricky tokens, low-temperature precise outputs); the verification pass is wasted.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "200M MAU &nbsp;·&nbsp; 1B prompts/day &nbsp;·&nbsp; 12K QPS avg / 50K peak "
                        "&nbsp;·&nbsp; 200 tok context / 500 tok response &nbsp;·&nbsp; "
                        "50 tok/sec/req on 70B &nbsp;·&nbsp; 8–32 concurrent reqs/GPU "
                        "&nbsp;·&nbsp; 2 MB KV / token / request &nbsp;·&nbsp; 16 GB KV @ 8K ctx "
                        "&nbsp;·&nbsp; H100 ~$30K &nbsp;·&nbsp; 10K-GPU cluster ~$300M capex."
                    ),
                },
            ],
        },
    ],
}
