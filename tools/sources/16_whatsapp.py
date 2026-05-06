"""Source for `16 - WhatsApp.pdf`."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design WhatsApp",
    "subtitle": "1:1 + group chat at planet scale, end-to-end encrypted, with presence and attachments",
    "read_time": "~ 45 minute read",
    "short_title": "Design WhatsApp",
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
                        "Design <strong>WhatsApp</strong>: a planet-scale messaging service supporting 1:1 "
                        "and group chats, end-to-end encrypted, with presence (online / last-seen / typing), "
                        "media attachments, and reliable delivery across mobile + desktop. "
                        "<em>Voice and video calling are explicitly out of scope.</em>"
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Users / DAU?", "~2B registered, ~500M DAU"],
                        ["Message volume?", "~100B messages/day across all chats"],
                        ["Media volume?", "~2B media messages/day, ~50KB average"],
                        ["Encryption?", "End-to-end (Signal protocol); server stores ciphertext only"],
                        ["Group size?", "Historically ~256, now up to ~1024 members"],
                        ["Multi-device?", "Yes — phone + up to 4 linked desktop / web devices"],
                        ["Retention?", "Server stores until ack from all recipient devices, then evict"],
                        ["Voice/video?", "Out of scope (separate WebRTC / SFU pipeline)"],
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
                        ["1:1 chat", "Send / receive text + media; ordering preserved per pair"],
                        ["Group chat", "Up to ~1024 members; admin controls; member add/remove"],
                        ["Receipts", "Sent (server ack), Delivered (device ack), Read (user opens chat)"],
                        ["Presence", "Online / offline / last-seen / typing — privacy controlled"],
                        ["Attachments", "Images, video, docs up to ~100MB; thumbnails auto-generated"],
                        ["Multi-device", "Same account on phone + 4 linked devices, ciphertext per device"],
                        ["Offline delivery", "Queue messages until recipient connects; deliver on reconnect"],
                        ["E2E encryption", "Signal protocol (X3DH + Double Ratchet); sender keys for groups"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Availability", "99.99% — messaging is the critical path"],
                        ["Latency (online → online)", "p50 &lt; 200 ms, p99 &lt; 1 s end-to-end"],
                        ["Latency (push to offline)", "p99 &lt; 5 s via APNs / FCM wakeup"],
                        ["Throughput", "~1.16M msgs/sec average, 5–10× peak (~10M/sec)"],
                        ["Durability", "No message loss once server-acked; per-device idempotency"],
                        ["Privacy", "Server sees only ciphertext + minimal envelope metadata"],
                        ["Scale", "~100M concurrent persistent connections globally"],
                    ],
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "Math for planet scale",
            "blocks": [
                {"type": "h3", "text": "Traffic Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        "Registered users: <strong>~2B</strong>; DAU: <strong>~500M</strong>",
                        "Daily messages: <strong>~100B/day</strong> across all chats",
                        "Average msg/sec: 100B / 86,400 ≈ <strong>1.16M msgs/sec</strong>",
                        "Peak factor: <strong>5–10×</strong> (New Year's Eve, World Cup) → <strong>~6–12M msgs/sec peak</strong>",
                        "Concurrent connections: <strong>~100M globally</strong> (subset of DAU online at any moment)",
                    ],
                },
                {"type": "h3", "text": "Storage Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        "Ciphertext envelope: ~1KB per text message average (header + payload + MAC)",
                        "Active queue (in-flight + offline) ≈ 100B × 1KB = <strong>100 TB/day</strong> of inbox writes — but evicted on ack",
                        "Steady-state inbox storage: ~5–10% of users have undelivered queue at any time → <strong>~10–20 TB hot</strong>",
                        "Media: 2B media messages/day × 50KB avg = <strong>~100 PB/day</strong> of media — stored in S3-class object store",
                        "Media is referenced by URL inside the encrypted envelope; bytes themselves are ciphertext",
                    ],
                },
                {"type": "h3", "text": "Connection / Edge Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        "Concurrent persistent TLS sessions: <strong>~100M</strong>",
                        "Per edge server budget: <strong>~50K connections/server</strong> (tuned C10K-style sockets)",
                        "Edge fleet: 100M / 50K = <strong>~2,000 edge servers</strong> globally; round to 3–5K with HA + region overhead",
                        "Heartbeat: <strong>30–60 sec</strong> (presence + NAT keepalive) → ~1.6–3.3M heartbeats/sec",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "100B msgs/day &nbsp;·&nbsp; <strong>1.16M msgs/sec avg</strong> &nbsp;·&nbsp; "
                        "~10M msgs/sec peak &nbsp;·&nbsp; <strong>100M concurrent connections</strong> &nbsp;·&nbsp; "
                        "~50K conn/edge &nbsp;·&nbsp; <strong>100 PB/day media</strong>."
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
                        "Clients open a single persistent TLS connection (XMPP-derived, "
                        "WhatsApp uses a binary variant called Noise Protocol on top of TCP/TLS) to the "
                        "nearest <strong>Edge Connection Server</strong>. The edge server authenticates the "
                        "device, then relays messages to a stateless <strong>Message Router</strong> that "
                        "looks up the recipient's home edge (via a presence / session registry) and pushes "
                        "the ciphertext there. If the recipient is offline, the router writes the envelope "
                        "to the recipient's <strong>Inbox Store</strong> (Cassandra) and triggers a push "
                        "notification (APNs / FCM) to wake the device."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Online → online path goes router-to-router; offline path lands in Cassandra and is fetched on reconnect.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Clients"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Mobile  [label="Mobile App", fillcolor="#dbe6fb"];
        Desktop [label="Desktop / Web", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge (per region)"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        EdgeNode [label="Edge Connection Server\n(persistent TLS / Noise)\n~50K conns each", fillcolor="#cbeedf"];
    }
    subgraph cluster_core {
        label="Core Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        Router   [label="Message Router\n(stateless, sharded)", fillcolor="#fff2c9"];
        Session  [label="Session Registry\n(user → edge mapping)", fillcolor="#fff2c9"];
        Presence [label="Presence Service\n(Redis)",              fillcolor="#fff2c9"];
        Auth     [label="Auth / Key Server\n(prekeys, identity)", fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Storage"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        Inbox [label="Inbox Store\n(Cassandra)\nper-device queue",  fillcolor="#ead7fb"];
        Media [label="Media Store\n(S3-class object)\nencrypted blobs", fillcolor="#ead7fb"];
        Push  [label="Push Notifs\n(APNs / FCM)",                    fillcolor="#fbd7c5"];
    }

    Mobile  -> EdgeNode [label="TLS/Noise"];
    Desktop -> EdgeNode [label="TLS/Noise"];
    EdgeNode -> Router  [label="envelope"];
    Router  -> Session [label="lookup\nrecipient edge", style=dashed];
    Router  -> EdgeNode    [label="deliver if online"];
    Router  -> Inbox   [label="queue if offline"];
    Router  -> Push    [label="wakeup if offline"];
    EdgeNode -> Presence [label="online/typing", style=dashed];
    EdgeNode -> Auth     [label="login / prekeys", style=dashed];
    EdgeNode -> Media    [label="upload/download URL", style=dashed];
}
""",
                },
                {"type": "h3", "text": "Architecture Highlights"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Edge Connection Server:</strong> terminates TLS / Noise, owns the persistent socket, ~50K connections/box",
                        "<strong>Message Router:</strong> stateless; consults Session Registry to find the recipient's edge; falls back to inbox store on miss",
                        "<strong>Session Registry:</strong> in-memory KV (Redis / etcd) mapping <code>user_device → edge_node</code>; updated on connect/disconnect",
                        "<strong>Presence Service:</strong> Redis cluster keyed by user_id; tracks online state, typing, last-seen with TTL",
                        "<strong>Auth / Key Server:</strong> stores user identity keys + bundles of one-time prekeys for X3DH initial handshake",
                        "<strong>Inbox Store:</strong> Cassandra; per-device row of pending envelopes; messages evicted after device ack",
                        "<strong>Media Store:</strong> S3-class object store; client-side encrypted blobs; CDN edges for download",
                        "<strong>Push Notifications:</strong> APNs (iOS) and FCM (Android) wake the app to fetch from inbox when offline",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Connection Model",
            "subtitle": "Persistent TLS, sharded edges, heartbeats",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Every online device holds a single long-lived TCP+TLS connection to its nearest "
                        "edge server. The protocol is binary, framed, and multiplexed: a single connection "
                        "carries chat messages, receipts, presence updates, and key-exchange traffic."
                    ),
                },
                {"type": "h3", "text": "Why Persistent Connections"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Push without polling:</strong> server can deliver instantly without the client asking",
                        "<strong>Battery / data:</strong> single TCP keepalive cheaper than HTTP polling at 1.16M msg/sec scale",
                        "<strong>Ordering:</strong> in-order frames per connection simplify per-pair ordering guarantees",
                        "<strong>NAT traversal:</strong> outbound long-lived TCP punches NAT and stays open via heartbeats",
                    ],
                },
                {"type": "h3", "text": "Heartbeats and Liveness"},
                {
                    "type": "bullets",
                    "items": [
                        "Client sends heartbeat every <strong>30–60 seconds</strong> (NAT timeout windows are typically 90 s+)",
                        "Edge marks connection dead after <strong>2 missed heartbeats</strong> and removes from Session Registry",
                        "Presence is derived from the existence of a healthy connection, not a separate ping",
                        "Mobile radios prefer batched heartbeats — Android jobs / iOS background fetch align with OS schedule",
                    ],
                },
                {"type": "h3", "text": "Sharding the Edge Fleet"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Geographic routing:</strong> client resolves <code>chat.whatsapp.net</code> via GeoDNS to nearest PoP",
                        "<strong>Inside a region:</strong> L4 load balancer hashes by <code>user_id</code> for sticky reconnect",
                        "<strong>~50K connections/server:</strong> tuned with epoll + non-blocking I/O (Erlang/BEAM at WhatsApp historically)",
                        "<strong>~2,000 edge servers</strong> for 100M concurrent connections; ~3–5K with replication / spare capacity",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why Erlang at WhatsApp",
                    "body": (
                        "WhatsApp famously ran on Erlang/BEAM because the runtime is built around millions "
                        "of lightweight processes, preemptive scheduling, and supervision trees — exactly "
                        "the shape of a problem where each connection is an independent state machine that "
                        "must survive partial failures of its neighbours."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Message Protocol & Lifecycle",
            "subtitle": "Send, ack, deliver, read",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "A message walks through four states visible to the user: <strong>sent</strong> "
                        "(server received), <strong>delivered</strong> (recipient device received), "
                        "<strong>read</strong> (recipient opened the chat). Each transition is an explicit "
                        "ack frame; the sender's UI updates the checkmarks accordingly."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Each ack hop is independent. Server ack only proves durability; device ack proves delivery; read receipt is opt-in.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    Sender   [label="Sender\nDevice", fillcolor="#dbe6fb"];
    SEdge    [label="Sender Edge",   fillcolor="#cbeedf"];
    Router   [label="Message Router",fillcolor="#fff2c9"];
    REdge    [label="Recipient Edge",fillcolor="#cbeedf"];
    Recipient[label="Recipient\nDevice", fillcolor="#dbe6fb"];

    Sender   -> SEdge    [label="1. send(envelope)"];
    SEdge    -> Router   [label="2. route"];
    Router   -> REdge    [label="3. push"];
    REdge    -> Recipient[label="4. deliver"];
    Recipient-> REdge    [label="5. ack(deliv)", color="#1f8359"];
    REdge    -> Router   [label="6. ack(deliv)", color="#1f8359"];
    Router   -> SEdge    [label="7. ack(deliv)", color="#1f8359"];
    SEdge    -> Sender   [label="8. ✓✓ delivered", color="#1f8359"];
    Recipient-> REdge    [label="9. ack(read)*", color="#b8862e", style=dashed];
    SEdge    -> Sender   [label="10. ✓✓ blue (read)*", color="#b8862e", style=dashed];

    SEdge    -> Sender   [label="0. ✓ sent (server ack)", color="#586278", constraint=false];
}
""",
                },
                {"type": "h3", "text": "Wire Envelope (server-visible)"},
                {
                    "type": "code",
                    "text": (
                        "// Server only sees this — payload is opaque ciphertext.\n"
                        "Envelope {\n"
                        "  msg_id:        uuid_v4,        // client-generated; idempotency key\n"
                        "  from:          user_device_id, // sender device\n"
                        "  to:            user_device_id, // one envelope PER recipient device\n"
                        "  ts_client:     int64_ms,       // sender clock\n"
                        "  ts_server:     int64_ms,       // assigned at edge ingress\n"
                        "  type:          enum{TEXT,MEDIA,RECEIPT,TYPING,KEY_EXCHANGE},\n"
                        "  ratchet_hdr:   bytes,          // Double Ratchet header (DH key + counters)\n"
                        "  ciphertext:    bytes,          // AES-256-GCM payload (text or media descriptor)\n"
                        "  mac:           bytes,          // HMAC over header + ciphertext\n"
                        "}"
                    ),
                },
                {"type": "h3", "text": "Lifecycle Steps"},
                {
                    "type": "numbered",
                    "items": [
                        "Sender encrypts payload per recipient device (Double Ratchet) and writes envelopes to its outbound queue",
                        "Sender's edge receives envelope, assigns <code>ts_server</code> + <code>msg_id</code> dedup, returns <strong>server ack</strong> (single check)",
                        "Router looks up each recipient device in Session Registry: online → push to recipient edge, offline → write to Cassandra inbox",
                        "Recipient edge delivers envelope, recipient device decrypts, sends <strong>delivered ack</strong> back through the chain (double check)",
                        "When recipient opens the chat (and read receipts are on), device sends a <strong>read ack</strong> (blue ticks)",
                        "After all recipient devices have acked, router evicts the envelope from inbox storage",
                    ],
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Inbox / Outbox Model",
            "subtitle": "Per-device queues in Cassandra",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "WhatsApp does not store your message history on the server. Instead, the server "
                        "is a relay with a transient queue: each <strong>device</strong> has a per-device "
                        "inbox of pending envelopes, and once every recipient device has acked, the server "
                        "evicts the envelope. The authoritative chat history lives on the client (and in "
                        "encrypted backups to iCloud / Google Drive)."
                    ),
                },
                {"type": "h3", "text": "Cassandra Inbox Schema"},
                {
                    "type": "code",
                    "text": (
                        "-- Per-device pending envelopes. One row per (recipient_device, msg).\n"
                        "-- Partition key spreads load; clustering key gives in-order pull.\n"
                        "CREATE TABLE inbox (\n"
                        "  recipient_device_id  uuid,         -- partition key: one device's queue\n"
                        "  enq_ts               timeuuid,     -- clustering key: server enqueue time\n"
                        "  msg_id               uuid,         -- idempotency key\n"
                        "  sender_device_id     uuid,\n"
                        "  envelope             blob,         -- ciphertext + ratchet header\n"
                        "  attempts             int,          -- delivery retry count\n"
                        "  expires_at           timestamp,    -- TTL ~30 days max\n"
                        "  PRIMARY KEY ((recipient_device_id), enq_ts)\n"
                        ") WITH CLUSTERING ORDER BY (enq_ts ASC)\n"
                        "  AND default_time_to_live = 2592000;  -- 30 days hard cap\n\n"
                        "-- Idempotency dedup: avoid double-enqueue if router retries.\n"
                        "CREATE TABLE inbox_dedup (\n"
                        "  recipient_device_id  uuid,\n"
                        "  msg_id               uuid,\n"
                        "  PRIMARY KEY ((recipient_device_id, msg_id))\n"
                        ") WITH default_time_to_live = 604800;  -- 7 days"
                    ),
                },
                {"type": "h3", "text": "Why Cassandra"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Write-heavy:</strong> 1.16M envelope writes/sec ingress is exactly Cassandra's sweet spot",
                        "<strong>Partition by recipient_device_id:</strong> all of one device's pending messages live on one set of replicas — single-partition pull on reconnect",
                        "<strong>TTL native:</strong> Cassandra evicts expired rows automatically; no separate cleanup job",
                        "<strong>Tunable consistency:</strong> QUORUM writes for durability, ONE reads for latency",
                        "<strong>Ring expansion:</strong> add nodes online; consistent hashing redistributes only 1/N keys",
                    ],
                },
                {"type": "h3", "text": "Eviction Policy"},
                {
                    "type": "table",
                    "headers": ["Trigger", "Action"],
                    "rows": [
                        ["Recipient device acks delivery", "DELETE row from inbox immediately"],
                        ["All recipient devices in chat acked", "Sender's outbox row also evicted"],
                        ["TTL = 30 days expired", "Cassandra tombstones row; message lost (rare)"],
                        ["User uninstalls / re-registers", "All inbox rows for that device purged"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Server is a Relay, Not an Archive",
                    "body": (
                        "This design choice is what lets WhatsApp claim it cannot read your messages: even "
                        "if compelled, the server has only the brief transit ciphertext, not the history. "
                        "Long-term chat backups are encrypted client-side with a key the user controls."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "End-to-End Encryption (Signal Protocol)",
            "subtitle": "X3DH, Double Ratchet, Sender Keys",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "WhatsApp uses the <strong>Signal Protocol</strong>: <strong>X3DH</strong> "
                        "(Extended Triple Diffie-Hellman) for the initial key agreement, and the "
                        "<strong>Double Ratchet</strong> for ongoing message keys with forward secrecy "
                        "and post-compromise security. Group chats use a derived construction called "
                        "<strong>Sender Keys</strong> for efficiency."
                    ),
                },
                {"type": "h3", "text": "X3DH — First Contact"},
                {
                    "type": "bullets",
                    "items": [
                        "Each user publishes to the Auth/Key server: <strong>identity key (IK)</strong>, <strong>signed prekey (SPK)</strong>, and a batch of <strong>one-time prekeys (OPK)</strong>",
                        "Alice fetches Bob's bundle (IK_B, SPK_B, one OPK_B) — the OPK is consumed and never reused",
                        "Alice computes 3 (or 4) Diffie-Hellman shared secrets across her keys and Bob's; concatenates → KDF → <strong>shared root key</strong>",
                        "From the root key both sides derive the initial Double Ratchet state — no round-trip needed for Alice's first message",
                    ],
                },
                {"type": "h3", "text": "Double Ratchet — Ongoing Messages"},
                {
                    "type": "para",
                    "text": (
                        "Each message has its own message key, derived by stepping a <strong>symmetric "
                        "ratchet</strong> (KDF chain). When the peer replies, a fresh <strong>DH ratchet</strong> "
                        "step mixes a new ephemeral DH key into the root, giving forward secrecy (past "
                        "messages stay safe if the current key leaks) and post-compromise security "
                        "(future messages recover after key leak)."
                    ),
                },
                {
                    "type": "code",
                    "text": (
                        "# Simplified Double Ratchet send step.\n"
                        "def ratchet_encrypt(state, plaintext, associated_data):\n"
                        "    # 1) Symmetric-ratchet the chain key to get this message's key.\n"
                        "    state.CKs, mk = kdf_ck(state.CKs)         # CKs -> (next CKs, message key)\n"
                        "    header = Header(\n"
                        "        dh   = state.DHs.public,\n"
                        "        pn   = state.PN,                       # prev chain length\n"
                        "        n    = state.Ns,                       # this msg index\n"
                        "    )\n"
                        "    state.Ns += 1\n"
                        "    ciphertext = aead_encrypt(\n"
                        "        key   = mk,\n"
                        "        plain = plaintext,\n"
                        "        ad    = associated_data + serialize(header),\n"
                        "    )\n"
                        "    return header, ciphertext\n\n"
                        "def ratchet_recv(state, header, ciphertext, ad):\n"
                        "    if header.dh != state.DHr:\n"
                        "        # Peer ratcheted forward: do a DH step and reset chains.\n"
                        "        skip_message_keys(state, header.pn)\n"
                        "        state.DHr = header.dh\n"
                        "        state.RK, state.CKr = kdf_rk(state.RK, dh(state.DHs, state.DHr))\n"
                        "        state.DHs           = generate_dh()\n"
                        "        state.RK, state.CKs = kdf_rk(state.RK, dh(state.DHs, state.DHr))\n"
                        "    skip_message_keys(state, header.n)\n"
                        "    state.CKr, mk = kdf_ck(state.CKr)\n"
                        "    return aead_decrypt(mk, ciphertext, ad + serialize(header))"
                    ),
                },
                {"type": "h3", "text": "Group Chat — Sender Keys"},
                {
                    "type": "para",
                    "text": (
                        "Running a separate Double Ratchet to each of 1023 other group members for every "
                        "message is wasteful — the sender would encrypt and the server would store 1023 "
                        "ciphertexts per message. Instead, the sender generates a <strong>sender key</strong> "
                        "(a symmetric chain key) and distributes it once to each member via their pairwise "
                        "Signal session. Subsequent group messages are encrypted <strong>once</strong> with "
                        "the sender key and the server fans out the ciphertext."
                    ),
                },
                {
                    "type": "table",
                    "headers": ["Property", "Pairwise Double Ratchet", "Sender Key (Group)"],
                    "rows": [
                        ["Encrypt cost (sender)", "O(N) per msg", "O(1) per msg, O(N) once at setup"],
                        ["Server storage / msg", "N ciphertexts", "1 ciphertext, fanned out at delivery"],
                        ["Forward secrecy", "Per-message via DH ratchet", "Per-message via symmetric ratchet only"],
                        ["Member added/removed", "Trivial", "Rotate sender key + redistribute"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Server Sees Metadata, Not Content",
                    "body": (
                        "E2E encryption hides payload but not who-talks-to-whom-and-when. The router "
                        "still sees sender id, recipient id, timestamps, and message size. Threat-modelling "
                        "WhatsApp must distinguish content privacy (strong) from metadata privacy (weak)."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Group Chat & Fan-out",
            "subtitle": "Client-side vs server-side fan-out",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "There are two fan-out designs for group chat. <strong>Client-side fan-out</strong>: "
                        "the sender encrypts and uploads N copies, one per recipient device. "
                        "<strong>Server-side fan-out</strong>: the sender uploads one ciphertext + a member "
                        "list and the server duplicates it to N inboxes. WhatsApp uses a <strong>hybrid</strong>: "
                        "the sender encrypts <em>once</em> with the sender key and the server fans out the "
                        "single ciphertext to all member edges / inboxes."
                    ),
                },
                {"type": "h3", "text": "Comparison"},
                {
                    "type": "table",
                    "headers": ["Approach", "Sender cost", "Server cost", "Privacy", "Used for"],
                    "rows": [
                        ["Client-side per-recipient",
                         "Encrypt N times, upload N",
                         "Storage = N",
                         "Server sees ciphertext + recipient list",
                         "Initial sender-key distribution"],
                        ["Server-side fan-out (plain)",
                         "Encrypt once, upload 1",
                         "Multicast to N inboxes",
                         "Server would need plaintext — INCOMPATIBLE WITH E2E",
                         "Not used for content"],
                        ["Sender Key (hybrid, what WhatsApp uses)",
                         "Encrypt once with chain key",
                         "Multicast 1 ciphertext to N recipient inboxes",
                         "Server stays oblivious to content",
                         "All ongoing group messages"],
                    ],
                },
                {"type": "h3", "text": "Sender-Key Fan-out Pseudocode"},
                {
                    "type": "code",
                    "text": (
                        "# Sender side (per group, once group is established):\n"
                        "def send_group_message(group_id, plaintext):\n"
                        "    sk_state = sender_keys[group_id]      # symmetric chain key\n"
                        "    sk_state.chain, mk = kdf_ck(sk_state.chain)\n"
                        "    ciphertext = aead_encrypt(mk, plaintext, ad=group_id || sk_state.idx)\n"
                        "    sk_state.idx += 1\n"
                        "    envelope = {\n"
                        "        'group_id':   group_id,\n"
                        "        'sender':     my_device_id,\n"
                        "        'sk_idx':     sk_state.idx,\n"
                        "        'ciphertext': ciphertext,\n"
                        "    }\n"
                        "    upload_to_edge(envelope)              # ONE upload\n\n"
                        "# Server side (in Message Router):\n"
                        "def route_group(envelope):\n"
                        "    members = group_members(envelope.group_id)   # cached, ~1024 max\n"
                        "    for device_id in members:\n"
                        "        if device_id == envelope.sender:         # don't echo to self\n"
                        "            continue\n"
                        "        edge = session_registry.get(device_id)\n"
                        "        if edge:\n"
                        "            edge.push(device_id, envelope)        # online path\n"
                        "        else:\n"
                        "            inbox.append(device_id, envelope)     # offline path\n"
                        "            push_notif.wake(device_id)"
                    ),
                },
                {"type": "h3", "text": "Membership Changes"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Add member:</strong> existing members each pairwise-encrypt the current sender key for the new member",
                        "<strong>Remove member:</strong> all remaining members <em>rotate</em> sender keys so the removed member can't decrypt future traffic",
                        "<strong>Admin actions</strong> are themselves messages routed through the same protocol — no privileged server path",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why ~1024 is the Practical Cap",
                    "body": (
                        "Each new member triggers O(N) pairwise sender-key distributions; each removed "
                        "member forces O(N) rotation. The cost is bearable up to ~10^3 members; beyond that "
                        "people typically use Channels (broadcast) which has different threat-model and "
                        "drops per-recipient encryption."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Presence & Typing Indicators",
            "subtitle": "Online, last-seen, typing — privacy-aware",
            "blocks": [
                {"type": "h3", "text": "Sources of Presence Truth"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Online:</strong> the user has at least one healthy edge connection (heartbeat fresh)",
                        "<strong>Last-seen:</strong> timestamp of the most recent disconnect or background event",
                        "<strong>Typing:</strong> sender broadcasts a TYPING control frame; recipient edge fans out",
                    ],
                },
                {"type": "h3", "text": "Storage & Propagation"},
                {
                    "type": "bullets",
                    "items": [
                        "Presence Service: <strong>Redis cluster</strong> keyed by user_id, fields = {online, last_seen, typing_in}, TTL ~120 s",
                        "Updates pushed only to <strong>contacts in active conversations</strong> (not globally) — N to a few, not N to millions",
                        "Typing TTL ~10 s so a stale TYPING auto-clears if the sender disconnects mid-keystroke",
                        "Heartbeat refresh extends online TTL; disconnect or missed beats → set last_seen + flip online=false",
                    ],
                },
                {"type": "h3", "text": "Privacy Modes"},
                {
                    "type": "table",
                    "headers": ["Setting", "Visible to", "Server behavior"],
                    "rows": [
                        ["Last-seen: Everyone", "All contacts", "Broadcast last_seen to subscribers"],
                        ["Last-seen: My Contacts", "Contacts only", "Filter subscribers by contact list"],
                        ["Last-seen: Nobody", "No one", "Suppress presence broadcast entirely"],
                        ["Read receipts: off", "Sender sees only ✓✓ (delivered)", "Drop READ ack on the floor at recipient edge"],
                        ["Typing: off (silent typing not exposed in UI)", "—", "Still sent on wire if sender's UI emits"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Don't Broadcast to the World",
                    "body": (
                        "The naive design — push 'Alice is online' to all 500 of Alice's contacts every "
                        "time she opens the app — costs 500M × 100 events/day = 50B presence msgs/day. "
                        "WhatsApp only pushes presence to contacts who currently have Alice's chat open, "
                        "cutting fan-out by 100×."
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Media Attachments",
            "subtitle": "Encrypted blobs in object store",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Sending a 50 KB image through the message envelope path would balloon the inbox "
                        "store and choke the router. Instead, media takes a <strong>side channel</strong>: "
                        "the client encrypts the file with a fresh symmetric key, uploads ciphertext to a "
                        "<strong>Media Store</strong> (S3-class), and the chat envelope carries only the "
                        "URL + the symmetric key. Recipients pull from the CDN edge."
                    ),
                },
                {"type": "h3", "text": "Upload Flow"},
                {
                    "type": "numbered",
                    "items": [
                        "Client generates random <strong>media_key</strong> (32 bytes) and encrypts file with AES-CBC + HMAC",
                        "Client requests <strong>pre-signed PUT URL</strong> from media-upload service (one-shot, expires in minutes)",
                        "Client PUTs ciphertext directly to object store — bytes never touch the message router",
                        "Client computes content hash; checks server-side hash for <strong>dedup</strong> (popular forwards = same blob)",
                        "Client constructs media descriptor <code>{url, media_key, sha256, mime, size, thumbnail}</code>",
                        "Descriptor is <strong>encrypted inside the normal Signal envelope</strong> and sent to recipients",
                    ],
                },
                {"type": "h3", "text": "Download Flow"},
                {
                    "type": "numbered",
                    "items": [
                        "Recipient decrypts envelope with Double Ratchet → recovers media descriptor + media_key",
                        "Recipient GETs the ciphertext blob from CDN (cache hit on viral forwards)",
                        "Recipient verifies HMAC, decrypts with media_key, and renders",
                        "Server never sees plaintext — even though the media bytes are stored on Meta-controlled S3",
                    ],
                },
                {"type": "h3", "text": "Storage Economics"},
                {
                    "type": "table",
                    "headers": ["Tier", "Use", "Notes"],
                    "rows": [
                        ["Hot (S3 Standard / Cassandra inbox)", "Last 30 days", "Heaviest read; CDN-fronted"],
                        ["Warm (S3 IA)", "30–180 days", "Cheaper; access latency tens of ms"],
                        ["Cold (Glacier)", "180 days – years", "Forward chains; rarely re-fetched"],
                        ["Eviction", "Reference count = 0", "All recipient devices acked + downloaded → delete"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "100 PB/day, but Dedup Saves the Day",
                    "body": (
                        "2B media msgs/day × 50KB = ~100 PB/day raw. Forward dedup (same SHA on blob) "
                        "typically reduces unique storage by 3–5× because a fraction of media is heavily "
                        "re-shared. Net steady-state media corpus growth is materially smaller than the "
                        "ingress rate suggests."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Offline Delivery & Multi-Device",
            "subtitle": "Reconnect, replay, retry",
            "blocks": [
                {"type": "h3", "text": "Reconnect Flow"},
                {
                    "type": "numbered",
                    "items": [
                        "Device opens TLS to nearest edge; presents auth token + device fingerprint",
                        "Edge writes <code>(user_device → edge_node)</code> into Session Registry",
                        "Edge issues a single Cassandra query: <code>SELECT * FROM inbox WHERE recipient_device_id = ? ORDER BY enq_ts</code>",
                        "Edge streams pending envelopes to device in order; device acks each",
                        "On ack receipt, edge issues <code>DELETE</code> for the row (or buffers and batches)",
                        "Device is now caught up; subsequent messages flow online via the router",
                    ],
                },
                {"type": "h3", "text": "Offline Retry Policy"},
                {
                    "type": "table",
                    "headers": ["Stage", "Action", "Retry"],
                    "rows": [
                        ["Recipient online", "Edge push", "TCP retransmit; if disconnect → fall through"],
                        ["Recipient offline (recent)", "Inbox write + APNs/FCM wakeup", "Re-wake every 1 min, capped at 3 attempts"],
                        ["Recipient offline (long)", "Inbox holds with TTL = 30 days", "No additional pushes; pulled on reconnect"],
                        ["TTL exceeded (~30 days)", "Cassandra evicts row", "Message lost; sender keeps single check (sent only)"],
                        ["Device permanently gone (uninstall)", "Server detects via key rotation", "Drop pending envelopes; sender notified"],
                    ],
                },
                {"type": "h3", "text": "Multi-Device"},
                {
                    "type": "bullets",
                    "items": [
                        "Each linked device has its own <strong>identity key + Signal session</strong> with every contact",
                        "A single chat to Bob means the sender encrypts <em>once per Bob device</em> (phone + 2 desktops = 3 envelopes)",
                        "Linked desktops historically required the phone to be online; modern WhatsApp uses an independent multi-device protocol",
                        "Device-add: new device fetches the chat history via an authenticated bootstrap from a primary device, not from the server",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Per-Device, Not Per-User",
                    "body": (
                        "Every encryption decision in WhatsApp's modern protocol is keyed on "
                        "device, not user. A user with phone + iPad + 2 desktops is 4 endpoints; "
                        "ack semantics, sender keys, and inbox rows are all per-device."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Scalability & Distribution",
            "subtitle": "Sharding, regions, and the registry",
            "blocks": [
                {"type": "h3", "text": "Horizontal Scaling Cheatsheet"},
                {
                    "type": "table",
                    "headers": ["Tier", "Scaling axis", "Why it works"],
                    "rows": [
                        ["Edge Connection Server", "Add servers, GeoDNS routes new conns", "Stateful per connection but stateless across users"],
                        ["Message Router", "Stateless, scale on CPU", "All state in Session Registry / Cassandra"],
                        ["Session Registry", "Shard by user_id", "O(1) lookup; replicate across AZs"],
                        ["Cassandra Inbox", "Add ring nodes; partition by recipient_device_id", "Hot-key risk minimal — each device has its own queue"],
                        ["Presence (Redis)", "Cluster slots by user_id", "Soft-state, can be rebuilt from heartbeats"],
                        ["Media Store", "Object store auto-scales", "Pay-by-use, CDN absorbs read"],
                    ],
                },
                {"type": "h3", "text": "Geographic Distribution"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Edge PoPs</strong> in every major region; clients connect to nearest via GeoDNS / Anycast",
                        "<strong>Cassandra ring</strong> typically multi-region with local-quorum writes; cross-region replication async",
                        "<strong>Cross-region routing:</strong> if Alice (Europe) messages Bob (Asia), Alice's edge → her region's router → Bob's region's router → Bob's edge",
                        "<strong>Failover:</strong> if a region edge is unhealthy, GeoDNS pulls it out of rotation; client retries to next-nearest PoP",
                    ],
                },
                {"type": "h3", "text": "Hot Spots and Hot Groups"},
                {
                    "type": "bullets",
                    "items": [
                        "Celebrity broadcast → 1024 members all online → 1024 fan-out per message; bounded by group cap",
                        "Trending forward (viral image) → media CDN handles bursts; envelope rate not affected because content is by-reference",
                        "Marketing flood / spam → rate limit at edge by sender, not recipient (cheaper)",
                    ],
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
                        ["Edge server crash",
                         "All ~50K connections drop simultaneously",
                         "Heartbeat loss + LB health",
                         "Clients reconnect to peer edge via GeoDNS; Session Registry updates on reconnect"],
                        ["Session Registry partition",
                         "Router can't find recipient edge — falls through to inbox",
                         "Registry RTT spike",
                         "Treat as 'offline' (write inbox + push); registry self-heals"],
                        ["Cassandra ring partition",
                         "Some inbox writes fail at QUORUM",
                         "Coordinator timeout",
                         "Hinted handoff buffers writes; degrade to LOCAL_ONE if needed; alert"],
                        ["Push (APNs/FCM) outage",
                         "Offline users not woken",
                         "Vendor status page + delivery telemetry",
                         "Retry on schedule; users still get msg on next foreground open"],
                        ["Media Store / CDN outage",
                         "Media downloads fail; text still works",
                         "5xx rate, CDN dashboards",
                         "Fall back to origin region; show 'tap to retry' in UI"],
                        ["Auth/Key Server down",
                         "New conversations blocked (no prekey fetch)",
                         "X3DH error rate",
                         "Existing sessions keep working; degrade gracefully on first-contact only"],
                        ["Sender clock skew",
                         "Out-of-order display, wrong receipts",
                         "ts_client vs ts_server diff",
                         "Order by ts_server; UI displays best-effort ts_client"],
                        ["Replay / duplicate envelope",
                         "User sees same msg twice",
                         "msg_id collision",
                         "Idempotency: inbox_dedup table drops duplicate enqueue"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Degrade Gracefully",
                    "body": (
                        "Order of preservation under stress: (1) text delivery, (2) receipts, (3) presence, "
                        "(4) typing, (5) media. Presence and typing are the first to be silently dropped "
                        "when the system is unhealthy — losing them is invisible to most users."
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
                        ["Connection model",
                         "Persistent TLS per device",
                         "Battery + edge-server cost vs HTTP polling latency. At 1.16M msg/sec, polling is non-viable."],
                        ["E2E encryption",
                         "Signal protocol everywhere",
                         "Compute + key-management cost; server can't help with search, spam ML on content. Privacy is the product."],
                        ["Group fan-out",
                         "Sender-key (1× encrypt, server multicasts)",
                         "Rotation cost on member change vs O(N) per-message encrypt cost. Hybrid wins."],
                        ["Server-side fan-out (plaintext)",
                         "REJECTED — incompatible with E2E",
                         "Would let server batch and dedup in plaintext, but breaks the privacy guarantee."],
                        ["Storage model",
                         "Ephemeral relay (evict on ack)",
                         "Server can't be subpoenaed for history; users must back up themselves. WhatsApp's stance."],
                        ["Inbox DB",
                         "Cassandra",
                         "Write-optimised, TTL native, ring-scalable. SQL would buckle at 1M writes/sec."],
                        ["Media path",
                         "Side-channel object store + CDN",
                         "Two-step send (upload + envelope) vs inline. Inline would 50× the inbox volume."],
                        ["Presence broadcast",
                         "Only to active-conversation contacts",
                         "Slight UI lag for stale chats vs 100× message storm."],
                        ["Read receipts",
                         "Opt-out per user",
                         "Some senders never get the read tick; small ack savings; user trust win."],
                        ["Push notifications",
                         "APNs / FCM (vendor lock)",
                         "Dependency on Apple/Google availability vs reinventing OS-level wakeup. Worth it."],
                        ["Multi-device",
                         "Per-device keys, no server-held history",
                         "Linking a new device requires a primary; complex bootstrap vs trivial server-side sync."],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Headline Tension",
                    "body": (
                        "WhatsApp is a system that aggressively gives up server-side capabilities — content "
                        "search, spam ML on payload, server-side history — in exchange for the "
                        "claim that the operator cannot read users' messages. Almost every architectural "
                        "choice is downstream of that trade-off."
                    ),
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
                        "WhatsApp is a classic 'chat at scale' interview. The interviewer wants to see you "
                        "(a) do the capacity math, (b) reason about persistent connections, (c) understand "
                        "fan-out vs storage trade-offs, and (d) speak intelligently about end-to-end "
                        "encryption without hand-waving."
                    ),
                },
                {"type": "h3", "text": "45-Minute Interview Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (2 min):</strong> clarify scope — 1:1 + group, E2E, presence, attachments; voice/video out",
                        "<strong>Capacity (5 min):</strong> 100B msgs/day, 1.16M/sec avg, 100M concurrent conns, 100 PB/day media",
                        "<strong>Connection model (5 min):</strong> persistent TLS, ~50K/edge, heartbeats, GeoDNS",
                        "<strong>High-level arch (3 min):</strong> Edge → Router → {Inbox, Media, Presence, Push}",
                        "<strong>Message lifecycle (5 min):</strong> sent / delivered / read; envelope schema; ack chain",
                        "<strong>Inbox model (5 min):</strong> Cassandra per-device queue; eviction on ack; 30-day TTL cap",
                        "<strong>E2E encryption (8 min):</strong> X3DH initial handshake; Double Ratchet; sender keys for groups",
                        "<strong>Group fan-out (4 min):</strong> client-side vs server-side; why hybrid (sender key) wins",
                        "<strong>Failures + trade-offs (5 min):</strong> edge crash, Cassandra partition, server-as-relay choice",
                        "<strong>Wrap (3 min):</strong> what would change at 10× scale or with voice in scope",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "“1.16M msgs/sec average, 5–10× peak” — shows you did the math",
                        "“100M concurrent persistent connections, ~50K per edge → ~2K edge servers” — capacity → fleet sizing",
                        "“Server is a relay, not an archive” — frames every other decision",
                        "“X3DH for handshake, Double Ratchet for messages, sender keys for groups” — Signal in three phrases",
                        "“Sender-key fan-out is O(1) per message, O(N) at setup” — quantifies the group trade-off",
                        "“Media is a side-channel: ciphertext to S3, URL+key in the envelope” — explains the 100 PB/day in one sentence",
                        "“Inbox row evicted on device ack” — privacy + storage in one move",
                        "“Presence is broadcast only to active contacts” — avoids 50B presence msgs/day",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why not server-side fan-out for groups?</strong> A: Server would need plaintext to dedup and re-encrypt — incompatible with E2E. Sender key gives O(1) sender cost AND keeps server oblivious.",
                        "<strong>Q: How does WhatsApp claim it can't read messages?</strong> A: Server only ever sees ciphertext + envelope metadata. Inbox row is ciphertext. Backups are encrypted client-side with user key. No keys on server.",
                        "<strong>Q: What if a recipient is offline for a year?</strong> A: 30-day TTL on inbox row; after that, Cassandra evicts. Sender keeps single check. Retention is finite by design.",
                        "<strong>Q: How do you order messages?</strong> A: ts_server assigned at sender-edge ingress is authoritative. ts_client is best-effort for UI. Per-pair monotonicity comes from the persistent TCP order, not a global clock.",
                        "<strong>Q: How do you handle a viral group flood?</strong> A: Per-sender rate limit at the edge (cheap, before Cassandra). Group cap (~1024). Media is by-reference so storage doesn't explode.",
                        "<strong>Q: Why Cassandra instead of Kafka for the inbox?</strong> A: Need point-lookups by recipient_device_id and per-row TTL/delete. Kafka is great for streams but not for selective replay/eviction.",
                        "<strong>Q: How do you scale presence?</strong> A: Redis cluster sharded by user_id; broadcast only to subscribers with the chat open; heartbeat-derived; never persisted long-term.",
                        "<strong>Q: Multi-device — how does a new desktop get history?</strong> A: Bootstrapped from a primary device over an authenticated channel; server doesn't hold the history.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "2B users &nbsp;·&nbsp; 500M DAU &nbsp;·&nbsp; <strong>100B msgs/day</strong> &nbsp;·&nbsp; "
                        "<strong>1.16M msgs/sec avg</strong>, ~10M peak &nbsp;·&nbsp; "
                        "<strong>100M concurrent connections</strong> &nbsp;·&nbsp; ~50K/edge &nbsp;·&nbsp; ~2K edge servers &nbsp;·&nbsp; "
                        "<strong>100 PB/day media</strong> &nbsp;·&nbsp; group cap ~1024 &nbsp;·&nbsp; "
                        "inbox TTL 30 days &nbsp;·&nbsp; heartbeat 30–60 s."
                    ),
                },
            ],
        },
    ],
}
