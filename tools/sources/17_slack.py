"""Source for `17 - Slack.pdf` — workspace messaging with persistent history."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Slack",
    "subtitle": "workspace + channel + DM messaging with persistent history, full-text search, and integrations",
    "read_time": "~ 45 minute read",
    "short_title": "Design Slack",
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
                        "Design <strong>Slack</strong>: a workspace-based team-messaging service. "
                        "Users belong to one or more <strong>workspaces</strong>; each workspace "
                        "contains <strong>channels</strong> (public, private, DMs, group-DMs). "
                        "Messages are delivered in real time over WebSockets, persisted forever, "
                        "and indexed for full-text search. Bots and integrations consume an event "
                        "bus."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Scale?", "~20M DAU, ~1.5B messages/day globally"],
                        ["Topology?", "Workspace → channels → messages; user in N workspaces"],
                        ["Channel types?", "Public, private, 1:1 DM, group-DM (≤9 users), threads"],
                        ["Delivery?", "Real-time fan-out to online clients; push for offline"],
                        ["History?", "Persistent forever (workspace pays for retention tier)"],
                        ["Search?", "Full-text per-workspace; near-real-time (~1–5s freshness)"],
                        ["Encryption?", "TLS in transit, AES at rest; <strong>not E2EE</strong> — server reads to index/search"],
                        ["Integrations?", "Apps, Events API webhooks, slash commands, RTM bots"],
                        ["Multi-region?", "Yes; workspace pinned to home region for compliance"],
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
                        ["Send message", "POST to channel/DM; deliver to all subscribed online clients"],
                        ["Receive in real time", "WebSocket push within 1s end-to-end (p99)"],
                        ["Persistent history", "Forever; scrollback, pagination by ts cursor"],
                        ["Threads", "Sub-conversation rooted at parent_ts; UI merges into channel"],
                        ["Search", "Per-workspace inverted index; user/channel/time/keyword filters"],
                        ["Unread + mentions", "Per-channel unread counter; @mentions and DMs trigger push"],
                        ["Presence", "Online / away / DND status visible per workspace"],
                        ["Integrations", "Events API webhooks, slash commands, RTM bots, file uploads"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Availability", "99.99% — chat outages are highly visible"],
                        ["Latency (send→deliver)", "p50 &lt; 200ms, p99 &lt; 1s within region"],
                        ["Search freshness", "1–5 sec from send to searchable"],
                        ["Durability", "11 nines; never lose a persisted message"],
                        ["Throughput", "~17K msgs/sec avg, ~50K peak; ~5M concurrent WebSockets"],
                        ["Storage", "~1.5 TB/day raw + indexes; multi-year retention"],
                        ["Security", "TLS, AES-256 at rest, SSO/SAML, audit log; not E2EE"],
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
                        "DAU: <strong>20M</strong> (active users sending or reading on a given day)",
                        "Messages/day: <strong>1.5B</strong> (≈ 75 messages per DAU)",
                        "Average write rate: 1.5B / 86,400 ≈ <strong>17,360 msgs/sec ≈ 17K/sec</strong>",
                        "Peak (Mon 9am US/EU overlap): ~3× average ≈ <strong>50K msgs/sec</strong>",
                        "Reads (history scrollback + live delivery fan-out): each message fans out to ~10 subscribers on average → <strong>~170K deliveries/sec avg, ~500K peak</strong>",
                        "Concurrent WebSocket connections: ~25% of DAU online simultaneously → <strong>~5M live sockets</strong>",
                    ],
                },
                {"type": "h3", "text": "Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "Average message size: ~<strong>1 KB</strong> (text + JSON envelope; files are separate)",
                        "Raw daily volume: 1.5B × 1 KB = <strong>1.5 TB/day</strong>",
                        "Search index overhead: ~30% of raw text → <strong>~0.5 TB/day</strong> additional",
                        "Replication factor 3 → <strong>~6 TB/day</strong> physical",
                        "Annual: ~<strong>2.2 PB/year</strong> raw (≈ 6.5 PB replicated). Years of history per workspace.",
                    ],
                },
                {"type": "h3", "text": "Cache & Memory"},
                {
                    "type": "bullets",
                    "items": [
                        "Hot recent window: last 7 days of channels users actively read ≈ <strong>~10 TB</strong> across the fleet",
                        "Presence + unread counters in Redis: 20M users × ~200 bytes = <strong>~4 GB</strong> hot data",
                        "WebSocket session state: ~5M sockets × 1 KB metadata = <strong>~5 GB</strong> across RTM gateways",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "20M DAU &nbsp;·&nbsp; 1.5B msgs/day &nbsp;·&nbsp; "
                        "17K avg / 50K peak msgs/sec &nbsp;·&nbsp; ~5M live WebSockets &nbsp;·&nbsp; "
                        "1.5 TB raw/day &nbsp;·&nbsp; ~2.2 PB/year. Persistent forever."
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "Domain Model",
            "subtitle": "Workspace, channel, user, message",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Slack's mental model is a tree: a <strong>user</strong> belongs to N "
                        "<strong>workspaces</strong>; each workspace contains <strong>channels</strong>; "
                        "each channel contains <strong>messages</strong>; some messages have a "
                        "<strong>thread</strong> of replies. DMs and group-DMs are simply special "
                        "channels with implicit membership."
                    ),
                },
                {"type": "h3", "text": "Entities"},
                {
                    "type": "table",
                    "headers": ["Entity", "Notes"],
                    "rows": [
                        ["Workspace", "Tenant boundary; billing, retention, SSO scoped here"],
                        ["User ↔ Workspace", "Many-to-many via membership; user has one identity per workspace"],
                        ["Channel", "Belongs to exactly one workspace; type ∈ {public, private, dm, mpdm}"],
                        ["Membership", "(workspace_id, channel_id, user_id) → joined_at, last_read_ts"],
                        ["Message", "(workspace_id, channel_id, ts) — ts is server-assigned monotonic"],
                        ["Thread", "Messages with parent_ts != NULL; thread_ts = root parent's ts"],
                        ["Reaction / file / pin", "Side tables keyed on (channel_id, ts)"],
                    ],
                },
                {"type": "h3", "text": "Why workspace_id Is the Shard Key"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Tenant isolation:</strong> all queries are scoped by workspace; cross-workspace queries are rare",
                        "<strong>Compliance:</strong> a workspace can be pinned to a region (EU) for data residency",
                        "<strong>Billing & retention:</strong> applied per workspace; co-locating its data simplifies lifecycle",
                        "<strong>Hot-shard risk:</strong> a giant workspace (50K+ users) may need sub-sharding by channel_id",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "High-Level Architecture",
            "subtitle": "System overview",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Clients hold a long-lived WebSocket to an <strong>RTM gateway</strong>. "
                        "Sends are POSTed over HTTPS (or sent on the WebSocket) to the "
                        "<strong>Message Service</strong>, which persists, then publishes a "
                        "<strong>fan-out event</strong> on Kafka. RTM gateways consume that event "
                        "and push to subscribed sockets. Search, integrations, and notifications "
                        "tap the same Kafka stream."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "High-level architecture: WebSocket gateways front the clients; Kafka decouples persistence from fan-out, search, and integrations.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Clients"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Web    [label="Web", fillcolor="#dbe6fb"];
        Desk   [label="Desktop", fillcolor="#dbe6fb"];
        Mob    [label="Mobile", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        LB  [label="HTTPS LB\n+ TLS", fillcolor="#cbeedf"];
        RTM [label="RTM Gateway\n(WebSocket)", fillcolor="#cbeedf"];
    }
    subgraph cluster_svc {
        label="Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        MS [label="Message Service\n(send/persist)", fillcolor="#fff2c9"];
        SS [label="Search Service",   fillcolor="#fff2c9"];
        NS [label="Notification Svc\n(APNs/FCM)",   fillcolor="#fff2c9"];
        IS [label="Integrations\n(Events API)", fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        MySQL  [label="MySQL\n(hot, sharded\nby workspace)", fillcolor="#ead7fb"];
        Cold   [label="Cassandra / S3\n(cold history)",       fillcolor="#ead7fb"];
        ES     [label="Elasticsearch\n(per-workspace index)", fillcolor="#ead7fb"];
        Redis  [label="Redis\n(presence + unread)",           fillcolor="#ead7fb"];
        Kafka  [label="Kafka\n(events bus)",                  fillcolor="#fbd7c5"];
    }

    Web  -> LB;
    Desk -> LB;
    Mob  -> LB;
    LB   -> RTM   [label="WebSocket upgrade"];
    LB   -> MS    [label="POST /chat.postMessage"];
    RTM  -> MS    [label="send (alt path)", style=dashed];
    MS   -> MySQL [label="INSERT (hot tier)"];
    MS   -> Kafka [label="publish event"];
    Kafka -> RTM  [label="fan-out", color="#1f8359"];
    Kafka -> SS   [label="index"];
    Kafka -> NS   [label="badge / push"];
    Kafka -> IS   [label="webhooks"];
    MySQL -> Cold [label="age-out (90d)", style=dashed];
    SS    -> ES;
    NS    -> Redis [label="counters"];
    RTM   -> Redis [label="presence", style=dashed];
}
""",
                },
                {"type": "h3", "text": "Component Responsibilities"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>RTM Gateway:</strong> terminates WebSockets; tracks per-socket channel subscriptions; pushes events from Kafka to clients",
                        "<strong>Message Service:</strong> validates send, assigns server ts, persists to MySQL, publishes to Kafka",
                        "<strong>Kafka:</strong> single source of truth for the fan-out — keeps the hot send path linear and decouples consumers",
                        "<strong>Search Service:</strong> consumes Kafka and indexes into per-workspace Elasticsearch shards",
                        "<strong>Notification Service:</strong> updates unread/badge counters in Redis; fires APNs/FCM for mentions and DMs",
                        "<strong>Integrations:</strong> Events API delivery, slash command dispatch, bot token management",
                        "<strong>Cold tier:</strong> messages older than ~90 days move to Cassandra/S3; reads served on demand",
                    ],
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Real-Time Delivery (WebSockets + RTM)",
            "subtitle": "Pushing messages to online clients",
            "blocks": [
                {"type": "h3", "text": "Connection Lifecycle"},
                {
                    "type": "numbered",
                    "items": [
                        "Client logs in → calls <code>rtm.connect</code> → receives a WebSocket URL pinned to its workspace's home region",
                        "Client opens WebSocket; gateway authenticates token, loads <strong>channel subscription set</strong> for the user (channels they belong to)",
                        "Gateway registers <code>(socket_id → user_id, workspace_id, channel_set)</code> in its local in-memory map",
                        "Gateway also subscribes (in Redis or via Kafka consumer-group routing) to the relevant channel keys for fan-out",
                        "Heartbeat ping/pong every 10s; idle timeout 30s",
                        "On disconnect, client reconnects with <code>last_event_id</code> so the gateway replays missed events from a short buffer",
                    ],
                },
                {"type": "h3", "text": "Subscription Tracking"},
                {
                    "type": "bullets",
                    "items": [
                        "Server-side per-socket channel set is the source of truth — clients never tell the server what to deliver",
                        "On <code>conversations.join</code>/<code>leave</code>, gateway updates the in-memory map and persists to MySQL",
                        "Cross-gateway events (a user in two devices) → both sockets receive the event independently",
                        "Sticky load balancing keeps a workspace's sockets on a stable set of pods, improving Kafka consumer locality",
                    ],
                },
                {"type": "h3", "text": "Delivery to Online + Offline Users"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Online:</strong> Kafka event → RTM gateway looks up channel_id → all matching sockets get the JSON payload",
                        "<strong>Offline:</strong> persistence already happened at MS; on reconnect the client requests <code>conversations.history?oldest=last_read_ts</code> and replays",
                        "<strong>Push:</strong> if the message is a DM or contains an @mention, Notification Service issues an APNs/FCM push regardless of socket state",
                        "<strong>Backpressure:</strong> if a client's send buffer is full for &gt; 5s, gateway drops the socket; client reconnects with cursor and catches up via REST",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "WebSocket vs Long-Poll",
                    "body": (
                        "WebSockets win for Slack: full-duplex, one TCP connection per session, ~5M "
                        "concurrent at our scale. Long-poll would multiply request volume by ~10× "
                        "and add seconds of latency on every message. The cost is sticky-routing "
                        "and connection-draining complexity during deploys."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Storage Schema",
            "subtitle": "Hot, cold, and indexed tiers",
            "blocks": [
                {"type": "h3", "text": "Hot Messages Table (MySQL, sharded by workspace_id)"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE messages (\n"
                        "  workspace_id   BIGINT      NOT NULL,\n"
                        "  channel_id     BIGINT      NOT NULL,\n"
                        "  ts             DECIMAL(16,6) NOT NULL,  -- '1714931523.000200'\n"
                        "  user_id        BIGINT      NOT NULL,\n"
                        "  text           MEDIUMTEXT  NOT NULL,\n"
                        "  parent_ts      DECIMAL(16,6) NULL,      -- thread root\n"
                        "  thread_ts      DECIMAL(16,6) NULL,      -- denorm root for query\n"
                        "  edited_at      TIMESTAMP   NULL,\n"
                        "  attachments    JSON        NULL,\n"
                        "  reactions      JSON        NULL,        -- summary only\n"
                        "  PRIMARY KEY (workspace_id, channel_id, ts),\n"
                        "  KEY idx_thread (workspace_id, thread_ts, ts),\n"
                        "  KEY idx_user   (workspace_id, user_id,  ts)\n"
                        ") ENGINE=InnoDB\n"
                        "  PARTITION BY RANGE (ts) (...);\n\n"
                        "-- Shard key: workspace_id  →  256 logical shards via Vitess.\n"
                        "-- Composite PK gives O(log n) channel scrollback by ts cursor."
                    ),
                },
                {"type": "h3", "text": "Membership / Last-Read"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE channel_members (\n"
                        "  workspace_id  BIGINT NOT NULL,\n"
                        "  channel_id    BIGINT NOT NULL,\n"
                        "  user_id       BIGINT NOT NULL,\n"
                        "  joined_at     TIMESTAMP NOT NULL,\n"
                        "  last_read_ts  DECIMAL(16,6) NOT NULL,\n"
                        "  notify_pref   ENUM('all','mentions','none') DEFAULT 'all',\n"
                        "  PRIMARY KEY (workspace_id, channel_id, user_id),\n"
                        "  KEY idx_user (workspace_id, user_id)\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "Tiering Policy"},
                {
                    "type": "table",
                    "headers": ["Tier", "Age", "Store", "Latency", "Cost"],
                    "rows": [
                        ["Hot", "0–90 days", "MySQL (sharded, replicated)", "~5 ms point read", "$$$"],
                        ["Warm", "90d–2y", "Cassandra (workspace_id, channel_id, ts)", "~30 ms range scan", "$$"],
                        ["Cold", "2y+", "S3 / Glacier columnar (Parquet by month)", "~1–5 s on demand", "$"],
                        ["Search", "all ages", "Elasticsearch per-workspace index", "~50 ms keyword", "$$"],
                    ],
                },
                {"type": "h3", "text": "Why a Composite PK on (workspace_id, channel_id, ts)"},
                {
                    "type": "bullets",
                    "items": [
                        "Primary access pattern is <em>“give me the next page of messages in channel C”</em> — a range scan on (workspace, channel, ts)",
                        "ts is a monotonic decimal — natural cursor for <code>WHERE ts &lt; ? ORDER BY ts DESC LIMIT 50</code>",
                        "All access is workspace-scoped, so the shard prefix matches the leading column of the PK",
                        "Threads use a secondary index on (workspace_id, thread_ts, ts)",
                    ],
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Message Send & Fan-out",
            "subtitle": "From keystroke to subscribers",
            "blocks": [
                {"type": "h3", "text": "Lifecycle"},
                {
                    "type": "diagram",
                    "caption": "Message lifecycle: persist before fan-out, then Kafka drives RTM, search, notifications, and integrations.",
                    "dot": r"""
digraph L {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Client [label="Client send", fillcolor="#dbe6fb"];
    MS     [label="Message Service\n1. validate\n2. assign ts\n3. INSERT MySQL", fillcolor="#fff2c9"];
    Kafka  [label="Kafka topic\nmessages.<workspace>", fillcolor="#fbd7c5"];
    RTM    [label="RTM Gateway\n(fan-out to sockets)", fillcolor="#cbeedf"];
    ES     [label="Elasticsearch\nindexer (1–5s)",     fillcolor="#ead7fb"];
    Notif  [label="Notification Service\nbadge + push",fillcolor="#ead7fb"];
    Bots   [label="Integrations\n(Events API webhooks)",fillcolor="#ead7fb"];

    Client -> MS    [label="POST /chat.postMessage"];
    MS     -> Kafka [label="publish"];
    Kafka  -> RTM   [label="online subs"];
    Kafka  -> ES;
    Kafka  -> Notif [label="@mention/DM"];
    Kafka  -> Bots;
    RTM    -> Client [label="WebSocket push", color="#1f8359"];
    Notif  -> Client [label="APNs/FCM\n(if offline)", color="#1f8359", style=dashed];
}
""",
                },
                {"type": "h3", "text": "Step-by-Step"},
                {
                    "type": "numbered",
                    "items": [
                        "Client sends <code>POST /chat.postMessage { channel, text, client_msg_id }</code>",
                        "MS authenticates, checks channel membership, validates length, runs anti-abuse",
                        "MS assigns server timestamp <code>ts</code> (monotonic per channel) — this is the message's permanent ID",
                        "MS writes to MySQL (sharded by workspace_id). Synchronous — caller blocks until fsync replicates",
                        "MS publishes to Kafka topic <code>messages.<workspace_id></code>, partitioned by channel_id",
                        "RTM gateways consume → push to all subscribed online sockets within ~100 ms",
                        "Search indexer consumes → bulk-indexes into Elasticsearch (refresh interval 1s)",
                        "Notification Service consumes → bumps unread counters in Redis; fires APNs/FCM if @mention or DM",
                        "Integration Service consumes → posts Events API webhooks to subscribed apps",
                        "MS returns <code>{ ok, ts, channel }</code> to client; client replaces optimistic stub with confirmed message",
                    ],
                },
                {"type": "h3", "text": "Channel Fan-out (pseudocode)"},
                {
                    "type": "code",
                    "text": (
                        "# Runs in every RTM gateway pod, consuming the Kafka partition\n"
                        "# for the workspaces whose sockets this pod hosts.\n"
                        "\n"
                        "def on_kafka_event(evt):\n"
                        "    # evt = { workspace_id, channel_id, ts, user_id, text, ... }\n"
                        "    sockets = local_index.subscribers_for(evt.workspace_id,\n"
                        "                                          evt.channel_id)\n"
                        "    if not sockets:\n"
                        "        return  # nobody from this channel is online here\n"
                        "    payload = serialize(evt)        # JSON, ~1 KB\n"
                        "    for s in sockets:\n"
                        "        if s.user_id == evt.user_id and s.client_msg_id == evt.client_msg_id:\n"
                        "            continue                # don't echo to sender's same tab\n"
                        "        s.send_async(payload)       # non-blocking; drops on backpressure\n"
                        "    metrics.fanout_count.inc(len(sockets))\n"
                        "\n"
                        "# local_index is built from ws-join events (channel_members) on connect.\n"
                        "# Lookup is O(1): { (ws_id, ch_id) -> set[socket] }.\n"
                        "# Average channel size at Slack is ~10 members, so most fan-outs touch ~3 sockets.\n"
                    ),
                },
                {"type": "h3", "text": "Idempotency & Ordering"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>client_msg_id</strong> is a UUID generated by the client; MS dedupes on retry within 5 minutes",
                        "<strong>Per-channel ordering:</strong> Kafka partition = channel_id → strict order on the consumer",
                        "<strong>ts ties:</strong> if two clients send within the same microsecond, MS appends a serial suffix (e.g. <code>1714931523.000200</code>)",
                        "<strong>Sender echo:</strong> client gets the authoritative ts in the HTTP response and reconciles with what arrives over the WebSocket",
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Search",
            "subtitle": "Per-workspace inverted index",
            "blocks": [
                {"type": "h3", "text": "Index Topology"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>One Elasticsearch index per workspace</strong> (or per group of small workspaces, multi-tenant indexed by workspace_id)",
                        "Big workspaces (500K+ messages/day) get dedicated indexes; small workspaces share a multi-tenant index",
                        "<strong>Refresh interval:</strong> 1s — gives near-real-time search; trade some indexing throughput for freshness",
                        "<strong>Replication:</strong> 1 primary + 1 replica per shard; rolling restarts safe",
                        "<strong>Time-based rollover:</strong> roll into <code>messages-YYYY.MM</code> indexes; queries fan out to recent N indexes",
                    ],
                },
                {"type": "h3", "text": "Document Mapping"},
                {
                    "type": "code",
                    "text": (
                        "PUT messages-2026.05/_mapping\n"
                        "{\n"
                        "  \"properties\": {\n"
                        "    \"workspace_id\": { \"type\": \"keyword\" },\n"
                        "    \"channel_id\":   { \"type\": \"keyword\" },\n"
                        "    \"channel_type\": { \"type\": \"keyword\" },\n"
                        "    \"user_id\":      { \"type\": \"keyword\" },\n"
                        "    \"ts\":           { \"type\": \"date\",   \"format\": \"epoch_second\" },\n"
                        "    \"thread_ts\":    { \"type\": \"date\",   \"format\": \"epoch_second\" },\n"
                        "    \"text\":         { \"type\": \"text\",   \"analyzer\": \"slack_std\" },\n"
                        "    \"mentions\":     { \"type\": \"keyword\" },\n"
                        "    \"has_file\":     { \"type\": \"boolean\" },\n"
                        "    \"is_private\":   { \"type\": \"boolean\" }\n"
                        "  }\n"
                        "}\n"
                        "\n"
                        "# Custom analyzer: lowercases, splits on punctuation,\n"
                        "# preserves @mentions and #channels as single tokens,\n"
                        "# applies a unicode-aware stemmer."
                    ),
                },
                {"type": "h3", "text": "Query Path"},
                {
                    "type": "numbered",
                    "items": [
                        "User types in search box → frontend hits <code>search.messages?q=...&channel=...&from=...</code>",
                        "Search Service rewrites the query: filters by <code>workspace_id</code>, by channels the user can read (private/DM ACL), by date range",
                        "Hits the workspace's index (or the time-rolled subset of monthly indexes)",
                        "Highlights matched terms; returns top 50 with <code>(channel, ts)</code> back-references",
                        "UI clicks on a hit → fetches the surrounding messages from MySQL/Cassandra by (channel_id, ts)",
                    ],
                },
                {"type": "h3", "text": "Search Freshness vs Cost"},
                {
                    "type": "table",
                    "headers": ["Refresh", "Freshness", "Indexing CPU", "Notes"],
                    "rows": [
                        ["100ms", "near-instant", "very high", "Slack does not need this; people don't search ms-old text"],
                        ["1s", "1–5s end-to-end", "moderate", "Default; matches Slack's actual UX"],
                        ["30s", "30–60s", "low", "Used for cold archive indexes; saves ~5× CPU"],
                        ["Manual", "minutes+", "very low", "Used during bulk reindex (workspace migration)"],
                    ],
                },
                {"type": "h3", "text": "ACL Enforcement"},
                {
                    "type": "bullets",
                    "items": [
                        "Search Service <em>never</em> trusts the client's claimed channel list",
                        "On query, it fetches the user's <code>channel_set</code> from membership cache and pushes it into the ES query as a filter",
                        "Private channels and DMs the user isn't in are filtered out at query time, not deleted from the index",
                        "This means leaving a private channel does not require re-indexing — only the membership cache changes",
                    ],
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Notifications & Unread Counters",
            "subtitle": "Badges, mentions, and pushes",
            "blocks": [
                {"type": "h3", "text": "Counter Model"},
                {
                    "type": "bullets",
                    "items": [
                        "Per-channel unread for each member: <code>unread:{ws}:{ch}:{user}</code> in Redis",
                        "Per-workspace badge: aggregate of unread channels with notifications enabled",
                        "Per-mention counter: <code>mentions:{ws}:{user}</code> — drives the red badge bubble",
                        "<strong>Source of truth:</strong> <code>last_read_ts</code> in MySQL (channel_members); Redis is a derived hot cache",
                    ],
                },
                {"type": "h3", "text": "Counter Update on New Message"},
                {
                    "type": "code",
                    "text": (
                        "# Notification Service consumer (Kafka → Redis)\n"
                        "def on_new_message(evt):\n"
                        "    members = members_cache.get(evt.workspace_id, evt.channel_id)\n"
                        "    is_dm   = evt.channel_type in (\"dm\", \"mpdm\")\n"
                        "    mentioned = parse_mentions(evt.text)        # @user, @channel, @here\n"
                        "\n"
                        "    pipe = redis.pipeline()\n"
                        "    for u in members:\n"
                        "        if u == evt.user_id:                     # sender's own msg\n"
                        "            continue\n"
                        "        # only bump unread if user hasn't read past this ts\n"
                        "        pipe.incr(f\"unread:{evt.workspace_id}:{evt.channel_id}:{u}\")\n"
                        "        if u in mentioned or evt.channel_type == \"channel_at_channel\":\n"
                        "            pipe.incr(f\"mentions:{evt.workspace_id}:{u}\")\n"
                        "    pipe.execute()\n"
                        "\n"
                        "    # Push only for DMs and explicit mentions to avoid storm\n"
                        "    targets = mentioned if not is_dm else members - {evt.user_id}\n"
                        "    if len(targets) > AT_CHANNEL_PUSH_LIMIT:    # e.g. 500\n"
                        "        targets = throttle(targets)              # rate-limit @channel\n"
                        "    for u in targets:\n"
                        "        if presence_is_offline(u) or user_pref_always_push(u):\n"
                        "            push_apns_fcm(u, evt)\n"
                    ),
                },
                {"type": "h3", "text": "Push Storm Defense"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>@channel in 5K-member channels</strong> would otherwise blast 5K APNs requests in one go",
                        "Mitigation: per-user push rate limit (max ~10 push/min), batched into a single \"new activity\" notification on cooldown",
                        "Workspaces can disable @channel for large rooms or require admin-only @channel",
                        "Notification Service is horizontally scaled; Kafka partition count ≥ pod count ensures no single partition becomes the bottleneck during spikes",
                    ],
                },
                {"type": "h3", "text": "Mark-as-Read Path"},
                {
                    "type": "numbered",
                    "items": [
                        "Client sends <code>conversations.mark { channel, ts }</code>",
                        "Notification Service updates <code>last_read_ts</code> in MySQL and resets the Redis counter",
                        "Publishes a <code>read_state_changed</code> event so other devices of the same user update their badges",
                        "Across-device consistency: the user's other tabs see the badge clear within ~200 ms via their own WebSocket",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Threads",
            "subtitle": "Sub-conversations rooted at a parent",
            "blocks": [
                {"type": "h3", "text": "Data Model"},
                {
                    "type": "bullets",
                    "items": [
                        "A reply has <code>parent_ts != NULL</code>; <code>thread_ts</code> equals the root parent's ts",
                        "Threads are read via the secondary index <code>(workspace_id, thread_ts, ts)</code>",
                        "Reply count + last-3-replies are denormalized onto the parent message for fast feed render",
                        "Threads are first-class citizens in fan-out — a reply still goes to the channel's subscribers (with a <code>thread_ts</code> hint), but the UI only auto-opens it for thread participants",
                    ],
                },
                {"type": "h3", "text": "UI Merge Semantics"},
                {
                    "type": "table",
                    "headers": ["Mode", "Behaviour", "Notes"],
                    "rows": [
                        ["Default channel feed", "Show parent only; \"5 replies\" stub", "Avoid noise from busy threads"],
                        ["\"Also send to channel\"", "Reply rendered inline in feed too", "Sender opt-in per reply"],
                        ["Threads pane", "Right-side pane lists all threads the user follows", "Threads pinned by participation or @mention"],
                        ["All-unreads", "Threads contribute to badge if user is a participant", "Otherwise channel-level only"],
                    ],
                },
                {"type": "h3", "text": "Thread Fan-out"},
                {
                    "type": "bullets",
                    "items": [
                        "Same Kafka topic, same fan-out — all channel subscribers see the reply event",
                        "RTM payload includes <code>thread_ts</code>, so the client routes it to the threads pane vs the main feed",
                        "Notification Service additionally bumps <code>thread_unread:{ws}:{ch}:{thread_ts}:{user}</code> for participants",
                    ],
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Integrations & Bots",
            "subtitle": "Events API, slash commands, RTM bots",
            "blocks": [
                {"type": "h3", "text": "Why a Separate Event Bus"},
                {
                    "type": "bullets",
                    "items": [
                        "Integrations are <strong>untrusted external systems</strong> (third-party apps, customer infra) — they can be slow, flaky, or misbehave",
                        "If they were called inline from the send path, a slow webhook would stall messaging — unacceptable",
                        "Solution: every persisted message is published to Kafka; the Integration Service consumes async with retries and per-app rate limits",
                        "App outage doesn't affect the human chat experience — only delays bot replies"
                    ],
                },
                {"type": "h3", "text": "Integration Surface"},
                {
                    "type": "table",
                    "headers": ["Mechanism", "Use", "Latency"],
                    "rows": [
                        ["Events API webhook", "Server-to-server: \"a message was posted in channel X\"", "1–5s, retried with backoff"],
                        ["Slash command", "Synchronous user-typed command → app HTTP endpoint", "&lt; 3s SLA, app must ack within 3s and use response_url for late replies"],
                        ["Interactive components", "Button click / modal submit → app HTTP endpoint", "&lt; 3s SLA"],
                        ["RTM bots", "Bot opens its own WebSocket; receives events", "&lt; 1s, behaves like a user"],
                        ["Incoming webhooks", "External system POSTs into a channel", "Treated as a regular send"],
                    ],
                },
                {"type": "h3", "text": "Event Subscription"},
                {
                    "type": "bullets",
                    "items": [
                        "Apps subscribe to event types (<code>message.channels</code>, <code>app_mention</code>, <code>reaction_added</code>, …)",
                        "Per-app filter applied at the Integration Service so Kafka can carry the firehose; the service does the projection",
                        "<strong>Delivery guarantees:</strong> at-least-once with up to 3 retries over 1 hour; 4xx → drop with alert; 5xx → exponential backoff",
                        "<strong>Per-app rate limit:</strong> 1 msg/sec/channel/app; bursts to 10 — protects laggy webhooks from queue buildup",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Token Scopes",
                    "body": (
                        "Slack apps use granular OAuth scopes (channels:read, chat:write, files:read). "
                        "Events API verifies the request signing secret + timestamp to prevent replay. "
                        "User tokens act as the user; bot tokens act as the bot identity inside channels it's invited to."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Failure Modes & Recovery",
            "subtitle": "What can go wrong",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["RTM gateway pod down",
                         "~10–50K sockets dropped",
                         "Pod liveness; conn count drop",
                         "Clients reconnect with last_event_id; LB drains pod; replay buffer (last 30s) covers the gap"],
                        ["MySQL primary down",
                         "Writes for that workspace shard stall",
                         "Replication lag spike; IO error",
                         "Orchestrator promotes replica (≤30s); Message Service returns 503; clients retry by client_msg_id"],
                        ["Kafka broker down",
                         "Send path slows; fan-out delayed",
                         "Producer ack timeouts",
                         "Multi-broker replication factor 3; producer retries to alt broker; consumers continue from offset"],
                        ["Elasticsearch shard unhealthy",
                         "Search degraded for that workspace",
                         "Cluster yellow/red",
                         "Replica promoted; queries fall back to neighbouring time-rolled indexes; hot reads continue (search is auxiliary)"],
                        ["Redis down (presence/counters)",
                         "Stale unread badges; presence dots flicker",
                         "Health check; PING fail",
                         "Read-through to MySQL last_read_ts; counters rebuild lazily on next message; presence defaults to \"active\""],
                        ["Push provider (APNs) outage",
                         "No mobile push for some users",
                         "APNs error rate alert",
                         "Queue with TTL 10 min; drop if not delivered (notification is best-effort); WebSocket delivery still works on next foreground"],
                        ["Workspace hot-shard",
                         "One huge tenant saturates a shard",
                         "QPS / conn skew",
                         "Sub-shard by channel_id; pin to a dedicated shard pair; rate-limit @channel in giant rooms"],
                        ["Network partition (region)",
                         "Workspace pinned to region unreachable",
                         "Cross-region health check",
                         "Read-only replica in DR region; failover requires manual promotion to preserve ordering"],
                    ],
                },
                {"type": "h3", "text": "Reconnection Protocol"},
                {
                    "type": "bullets",
                    "items": [
                        "Client persists <code>last_event_id</code> per WebSocket session",
                        "On reconnect: gateway checks if last_event_id is in the replay buffer (last ~30s of events)",
                        "<strong>Hit:</strong> replay missed events directly over the new socket",
                        "<strong>Miss:</strong> client falls back to <code>conversations.history</code> over REST, paginated by ts cursor",
                        "Either way the client converges without dropping messages",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful Degradation Order",
                    "body": (
                        "If something has to give, in order: drop search freshness → drop badge accuracy → "
                        "drop integrations → drop presence → never drop persisted message delivery. "
                        "Sending and receiving real chat is the product; everything else is auxiliary."
                    ),
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Slack vs WhatsApp",
            "subtitle": "Why these systems look different",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Both deliver chat over the internet, but their constraints diverge on "
                        "encryption, retention, and identity. Those choices ripple through the "
                        "entire architecture."
                    ),
                },
                {
                    "type": "table",
                    "headers": ["Dimension", "WhatsApp", "Slack"],
                    "rows": [
                        ["Encryption", "End-to-end (Signal protocol); server can't read", "TLS in transit, AES at rest; <strong>server reads to index/search/audit</strong>"],
                        ["Identity", "Phone number per user", "Email + workspace membership; SSO/SAML"],
                        ["Persistence", "Mostly device-local; server is a transient relay", "Server-side history forever (workspace pays for retention)"],
                        ["Search", "Local on device only", "Server-side full-text (Elasticsearch) per workspace"],
                        ["Group size", "&lt;= 1024 members typical", "Channels can have tens of thousands"],
                        ["Tenant model", "No tenants — every user equal", "Workspace (tenant) is the primary boundary"],
                        ["Compliance", "Limited (E2EE prevents most)", "Audit log, retention policy, eDiscovery, DLP"],
                        ["Push reliance", "Mobile-first; push critical", "Multi-device; WebSocket + push"],
                        ["Schema", "Encrypted blobs; minimal server schema", "Rich relational schema (workspace, channel, member, message, reaction, file…)"],
                        ["Storage tier", "Mostly ephemeral; small server-side queue", "Hot MySQL → warm Cassandra → cold S3; PB scale"],
                        ["Integrations", "Limited (Business API)", "Massive: Apps, Events API, slash commands, RTM bots"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "The single decision that explains everything",
                    "body": (
                        "WhatsApp chose E2EE → server is a relay → no server search → no eDiscovery → "
                        "phone-number identity is enough. Slack chose server-side history → full-text "
                        "search → admin/legal compliance → workspace tenancy → SSO. Once you pick "
                        "encryption posture, the rest of the design is largely determined."
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
                        ["Real-time transport", "WebSocket",
                         "Single duplex connection; ~5M concurrent at our scale. Long-poll multiplies request count by ~10× and adds seconds of latency. Cost: sticky routing during deploys."],
                        ["Fan-out", "Async via Kafka after persistence",
                         "Adds ~50 ms vs in-line fan-out, but isolates slow integrations and search from the send hot path. In-line fan-out couples failures."],
                        ["Shard key", "workspace_id",
                         "Tenant isolation, residency, retention all align. Risk: huge workspaces become hot shards. Mitigation: sub-shard by channel_id when needed."],
                        ["Hot store", "MySQL with composite PK",
                         "Strong consistency, range scans by ts cursor are O(log n). Cost: sharding ops via Vitess. NoSQL would scale easier but lose transactions on read state."],
                        ["Cold tier", "Tiered to Cassandra/S3 after 90 days",
                         "Cuts hot-store cost ~10×; cold reads are slower but rare (most reads are recent). Migration job runs nightly per workspace."],
                        ["Search refresh", "1 second",
                         "Matches user expectation; ~2× the indexing CPU vs 30s. Sub-second would 5× the cost for no UX gain."],
                        ["Search index per workspace", "Yes (or grouped for small ones)",
                         "Tenant isolation, easy archival/migration. Cost: cluster has many indexes; mitigated by pooling small tenants."],
                        ["Persistence model", "Server-side (not E2EE)",
                         "Enables search, eDiscovery, integrations, audit. Cost: blast radius of a server breach is larger; offset with strict access control + per-workspace KMS keys."],
                        ["Notification delivery", "Best-effort APNs/FCM",
                         "Acceptable: WebSocket is the primary path; push is a nudge, not a guarantee. Avoids retry storms."],
                        ["@channel in big rooms", "Throttled / opt-in admin gate",
                         "Prevents push storms on 5K-member channels. Costs a tiny UX surprise; explained in onboarding."],
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
                        "A clean Slack pitch frames the problem as <em>“persistent multi-tenant "
                        "chat with server-side search”</em>, contrasts with WhatsApp early to "
                        "anchor the encryption choice, then walks the send path end-to-end."
                    ),
                },
                {"type": "h3", "text": "45-Minute Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (2 min):</strong> clarify scope — workspaces, channels, DMs, threads, server-side history, full-text search, integrations",
                        "<strong>Anchor vs WhatsApp (2 min):</strong> server-side history → drives entire design",
                        "<strong>Capacity (5 min):</strong> 20M DAU, 1.5B msgs/day, 17K avg / 50K peak, ~5M live WebSockets, 1.5 TB/day raw",
                        "<strong>Domain model (3 min):</strong> workspace → channel → message; PK <code>(workspace_id, channel_id, ts)</code>",
                        "<strong>High-level arch (4 min):</strong> RTM gateway, Message Service, Kafka, MySQL/Cassandra/S3, Elasticsearch, Redis",
                        "<strong>Send + fan-out (8 min):</strong> persist before publish; Kafka per-channel ordering; pseudocode for fan-out",
                        "<strong>Real-time delivery (5 min):</strong> WebSocket lifecycle, reconnection with last_event_id",
                        "<strong>Search (5 min):</strong> per-workspace ES index, 1s refresh, ACL pushed into query",
                        "<strong>Notifications + threads (5 min):</strong> Redis counters, push storm defense, thread sub-conversations",
                        "<strong>Failures + trade-offs (5 min):</strong> hot shard, MySQL failover, graceful degradation order",
                        "<strong>Wrap (1 min):</strong> recite memorized numbers, name the encryption-vs-search tension as the central choice",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "“1.5B messages/day → 17K avg / 50K peak — peak is what we provision for”",
                        "“workspace_id is the natural shard key — tenancy, residency, retention all align”",
                        "“Persist <em>then</em> publish to Kafka — fan-out, search, integrations all become async readers”",
                        "“WebSocket subscriptions are server-tracked, never client-claimed — that's how ACLs stay correct”",
                        "“Search is auxiliary; chat must keep working if Elasticsearch is red”",
                        "“Slack ≠ WhatsApp because of E2EE — that one decision determines tenancy, search, and compliance”",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: How do you guarantee per-channel ordering?</strong> A: Single Kafka partition per channel_id; consumer-group keeps strict order; ts is server-assigned.",
                        "<strong>Q: A workspace has 100K users in #general — won't @channel kill us?</strong> A: Per-user push rate limit, batched notifications, admin-only @channel option in big rooms.",
                        "<strong>Q: How are private channels kept private at search?</strong> A: ACL filter pushed into the ES query; index isn't filtered; leaving a channel only updates the membership cache.",
                        "<strong>Q: An RTM pod dies with 50K sockets — what happens?</strong> A: Clients reconnect with last_event_id; replay from the gateway's 30s buffer; fall back to history REST if older.",
                        "<strong>Q: How do you avoid duplicate sends on retry?</strong> A: Client supplies a UUID client_msg_id; Message Service dedupes within 5 minutes; idempotent INSERT on (workspace, channel, client_msg_id).",
                        "<strong>Q: Why not E2EE like WhatsApp?</strong> A: Slack's value prop includes server-side search and eDiscovery; E2EE would forfeit both. Compensate with strict KMS scoping per workspace.",
                        "<strong>Q: How do threads interact with channel ordering?</strong> A: Replies fan out on the channel topic with thread_ts hint; the UI routes to the thread pane while the underlying log stays linear.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "20M DAU &nbsp;·&nbsp; 1.5B msgs/day &nbsp;·&nbsp; 17K avg / 50K peak msgs/sec &nbsp;·&nbsp; "
                        "~5M live WebSockets &nbsp;·&nbsp; ~1 KB avg msg &nbsp;·&nbsp; 1.5 TB raw/day &nbsp;·&nbsp; "
                        "~2.2 PB/year &nbsp;·&nbsp; 1s search refresh &nbsp;·&nbsp; 90-day hot tier."
                    ),
                },
            ],
        },
    ],
}
