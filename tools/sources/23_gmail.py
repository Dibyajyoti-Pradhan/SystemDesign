"""Source for `23 - Gmail.pdf` — designing a Gmail-scale email service."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Gmail",
    "subtitle": "large-scale email service: SMTP ingest, IMAP/web delivery, threading, search, spam, labels",
    "read_time": "~ 45 minute read",
    "short_title": "Design Gmail",
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
                        "Design an email service like <strong>Gmail</strong>. The system must "
                        "ingest mail over SMTP, deliver via IMAP / POP / web / mobile, group "
                        "messages into <strong>conversations</strong>, support full-text search, "
                        "filter spam at scale, and keep ~25 GB per user reliably for billions of "
                        "users."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Users?", "~2 billion active mailboxes; global"],
                        ["Volume?", "~300 billion emails/day inbound (most non-human)"],
                        ["Storage/user?", "~25 GB free tier; petabyte-scale aggregate"],
                        ["Protocols?", "SMTP in/out, IMAP, POP3, JMAP, web, mobile push"],
                        ["Threading?", "Conversation view by Subject + In-Reply-To/References"],
                        ["Search?", "Full-text, near-real-time, per-user partition"],
                        ["Spam?", "ML-scored at SMTP edge; user feedback loop"],
                        ["Attachments?", "Up to 25 MB; deduped via content hash"],
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
                        ["Receive mail", "Accept SMTP on MX; verify DKIM/SPF/DMARC; spam-score; deliver"],
                        ["Send mail", "Compose, queue, retry, DSN handling; outbound SMTP relay"],
                        ["Read mail", "IMAP/POP/web/mobile; folders/labels; mark-read state"],
                        ["Threading", "Group messages by conversation (canonical thread_id)"],
                        ["Labels", "Tag messages with M:N labels; system + user labels"],
                        ["Search", "Full-text query: from/to/subject/body/has:attachment/label:"],
                        ["Spam", "Auto-classify; user can mark spam / not-spam"],
                        ["Attachments", "Store, dedup by content-hash, virus-scan"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Availability", "99.99% mailbox; 99.9% search index"],
                        ["Durability", "11 nines; 3+ replicas; cross-region for hot data"],
                        ["Latency", "&lt;200 ms inbox load; &lt;500 ms search"],
                        ["Ingest", "~3.5 M msgs/sec peak; 99% within 30 s end-to-end"],
                        ["Storage", "~25 GB/user; multi-EB aggregate"],
                        ["Consistency", "Strong per-mailbox; eventual for search index"],
                        ["Spam recall", "≥99.9% caught; &lt;0.1% false positive"],
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
                        "Active users: <strong>~2 billion</strong>",
                        "Emails inbound: <strong>~300 billion / day</strong> (Gmail-public-figure ballpark)",
                        "Average rate: 300B / 86,400 s ≈ <strong>3.47 M msgs/sec</strong>",
                        "Peak rate: ~2× average ≈ <strong>~7 M msgs/sec</strong>",
                        "Composition: ~85% bulk/automated/spam, ~15% human-to-human",
                        "Outbound: ~10% of inbound (most users read more than they send)",
                    ],
                },
                {"type": "h3", "text": "Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "Average kept message: ~75 KB body + ~50 KB headers/metadata + occasional attachment",
                        "Per user: ~25 GB usable (free tier; paid tiers up to 2 TB)",
                        "Aggregate: 2B × 25 GB = <strong>~50 EB</strong> raw",
                        "After dedup, compression, tiering: <strong>~10–15 EB</strong> live + cold archive",
                        "Daily growth: 300B msgs × 100 KB avg = <strong>~30 PB / day</strong> raw",
                        "After spam filtering (~85% dropped or kept compactly): ~3–5 PB/day stored",
                    ],
                },
                {"type": "h3", "text": "Search Index"},
                {
                    "type": "bullets",
                    "items": [
                        "~15% of messages searched per day → ~45 B query-relevant docs touched",
                        "Index size: ~30% of raw text size with posting lists ≈ <strong>multi-PB</strong>",
                        "Refresh latency target: <strong>&lt;30 seconds</strong> from delivery to searchable",
                        "QPS: ~1–2 M searches/sec peak (auto-complete + manual queries)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "<strong>2 B</strong> users &nbsp;·&nbsp; "
                        "<strong>300 B</strong> msgs/day &nbsp;·&nbsp; "
                        "<strong>3.5 M/sec</strong> ingest &nbsp;·&nbsp; "
                        "<strong>25 GB</strong>/user &nbsp;·&nbsp; "
                        "<strong>~10 EB</strong> live storage &nbsp;·&nbsp; "
                        "<strong>&lt;30 s</strong> search freshness."
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
                        "The architecture has three planes: an <strong>ingest plane</strong> that "
                        "accepts SMTP and runs reputation, authentication, anti-virus, and spam "
                        "scoring; a <strong>storage plane</strong> built on Bigtable/Spanner plus "
                        "a content-addressed object store for attachments; and a "
                        "<strong>delivery plane</strong> that exposes IMAP, POP, JMAP, web, and "
                        "mobile push. Search runs as a separate per-user inverted-index service "
                        "fed by a Kafka event stream."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Inbound SMTP runs through reputation/auth/AV/spam, then writes to the per-user mailbox; delivery and search read from that store.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_in {
        label="Inbound (SMTP)"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        MX  [label="MX / SMTP\nReceiver", fillcolor="#cbeedf"];
        Rep [label="Reputation\n(IP/domain)", fillcolor="#cbeedf"];
        Auth[label="DKIM / SPF\nDMARC verify", fillcolor="#cbeedf"];
        AV  [label="Anti-virus\nscan", fillcolor="#cbeedf"];
        Spam[label="Spam ML\nscorer", fillcolor="#cbeedf"];
        Rt  [label="Routing\n(addr → user_id)", fillcolor="#cbeedf"];
    }
    subgraph cluster_core {
        label="Mailbox Service"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        MB [label="Mailbox\nService", fillcolor="#fff2c9"];
        Th [label="Thread\nResolver", fillcolor="#fff2c9"];
        Lb [label="Label\nService", fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        BT [label="Bigtable / Spanner\n(messages, threads, labels)", fillcolor="#ead7fb"];
        OS [label="Object Store\n(attachments, dedup)", fillcolor="#ead7fb"];
        IX [label="Search Index\n(per-user Lucene)", fillcolor="#ead7fb"];
        KQ [label="Kafka\n(mail events)", fillcolor="#fbd7c5"];
    }
    subgraph cluster_out {
        label="Delivery"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        IMAP [label="IMAP / POP /\nJMAP gateway", fillcolor="#dbe6fb"];
        Web  [label="Web / Mobile\nAPI", fillcolor="#dbe6fb"];
        Push [label="Mobile push\n(APNs/FCM)",  fillcolor="#dbe6fb"];
        Out  [label="Outbound SMTP\nrelay", fillcolor="#dbe6fb"];
    }

    MX -> Rep -> Auth -> AV -> Spam -> Rt -> MB;
    MB -> Th -> BT;
    MB -> Lb -> BT;
    MB -> OS [label="attachments"];
    MB -> KQ [label="event"];
    KQ -> IX [label="index"];
    IMAP -> MB;
    Web  -> MB;
    Web  -> IX [label="search"];
    MB -> Push;
    Web -> Out;
}
""",
                },
                {"type": "h3", "text": "Architecture Highlights"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>MX / SMTP receivers:</strong> globally distributed; accept on port 25; speak ESMTP, STARTTLS",
                        "<strong>Reputation:</strong> IP/domain block-lists, greylisting, RBL checks; reject before parsing body",
                        "<strong>DKIM/SPF/DMARC:</strong> cryptographic and policy auth — <em>essential for spam decisions</em>",
                        "<strong>Anti-virus:</strong> ClamAV-class scanners on attachments and embedded scripts",
                        "<strong>Spam scorer:</strong> LightGBM/DNN model returning [0..1]; threshold splits inbox vs spam",
                        "<strong>Mailbox Service:</strong> the source of truth API for read/write; routes by user_id",
                        "<strong>Bigtable/Spanner:</strong> primary store; row key (user_id, thread_id, msg_id)",
                        "<strong>Object Store:</strong> attachments by content-hash; dedup across all users",
                        "<strong>Search Index:</strong> per-user Lucene shard, updated via Kafka events",
                        "<strong>Delivery:</strong> IMAP/POP/JMAP gateways, web/mobile API, FCM/APNs push, outbound SMTP",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "SMTP Ingest Pipeline",
            "subtitle": "From MX to mailbox",
            "blocks": [
                {"type": "h3", "text": "End-to-End Pipeline"},
                {
                    "type": "numbered",
                    "items": [
                        "Sender's MTA opens TCP/25 to our MX, advertises EHLO, STARTTLS",
                        "<strong>Reputation check:</strong> source IP / sending-domain reputation (IP4R, RBLs); reject 5xx for known-bad",
                        "<strong>Greylisting (light):</strong> defer first delivery from unknown sender; legitimate MTAs retry",
                        "<strong>SPF:</strong> verify SMTP MAIL FROM domain authorizes the source IP",
                        "<strong>DKIM:</strong> verify body+selected-headers signature against the sender's published public key",
                        "<strong>DMARC:</strong> apply alignment policy; quarantine/reject on policy failure",
                        "<strong>Anti-virus scan:</strong> attachments and inline scripts; quarantine if positive",
                        "<strong>Content extraction:</strong> parse MIME tree; extract headers, text, attachments",
                        "<strong>Spam scoring:</strong> ML model returns score; ≥0.5 → Spam label, ≥0.95 → silent drop",
                        "<strong>Routing:</strong> resolve to_addr → user_id (account directory); handle aliases, +tags, mailing-lists",
                        "<strong>Thread resolution:</strong> compute thread_id from In-Reply-To / References / Subject",
                        "<strong>Persist:</strong> write row to Bigtable; attachments to object store keyed by SHA-256",
                        "<strong>Emit event:</strong> publish to Kafka for indexing, push notification, audit log",
                        "<strong>Acknowledge:</strong> 250 OK to sender — only after durable persistence",
                    ],
                },
                {"type": "h3", "text": "Authentication Decision Matrix"},
                {
                    "type": "table",
                    "headers": ["SPF", "DKIM", "DMARC", "Action"],
                    "rows": [
                        ["pass", "pass", "pass", "Inbox (subject to spam score)"],
                        ["fail", "pass", "pass (DKIM aligns)", "Inbox; lower trust"],
                        ["pass", "fail", "pass (SPF aligns)", "Inbox; lower trust"],
                        ["fail", "fail", "p=quarantine", "Spam folder"],
                        ["fail", "fail", "p=reject", "Reject 550 at SMTP"],
                        ["—", "—", "no record", "Treat as suspicious; weight on spam model"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Reject Early, Save Money",
                    "body": (
                        "Most inbound is junk. Rejecting at the SMTP envelope (before DATA) on "
                        "reputation alone discards the majority of bytes — saving bandwidth, AV "
                        "cycles, and storage. Anti-virus and ML scoring run only after the "
                        "envelope passes."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Storage Model",
            "subtitle": "Bigtable, Spanner, and dedup",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "We store messages in a wide-column store such as <strong>Bigtable</strong> "
                        "(or Spanner where strong cross-row consistency is needed). The row key "
                        "embeds <code>(user_id, thread_id, msg_id)</code> so all messages in a "
                        "conversation live next to each other on disk — a single range scan "
                        "loads the entire thread."
                    ),
                },
                {"type": "h3", "text": "Bigtable Row Layout"},
                {
                    "type": "code",
                    "text": (
                        "# Row key: <user_id>/<thread_id>/<msg_id>\n"
                        "#   user_id is a 64-bit hash → balanced regions\n"
                        "#   thread_id sorts within user → conversation locality\n"
                        "#   msg_id is monotonic (timestamp-derived)\n"
                        "\n"
                        "row_key = f\"{user_id:016x}/{thread_id:016x}/{msg_id:016x}\"\n"
                        "\n"
                        "# Column families:\n"
                        "#   meta:    headers, dates, sender, subject, snippet\n"
                        "#   body:    text/plain, text/html (compressed)\n"
                        "#   labels:  one column per label_id, value=timestamp\n"
                        "#   attach:  one column per attachment, value=content_hash\n"
                        "#   flags:   read/unread, starred, important, draft\n"
                        "\n"
                        "# Example cells:\n"
                        "#   meta:from        \"alice@x.com\"\n"
                        "#   meta:subject     \"Re: Q3 plans\"\n"
                        "#   labels:INBOX     1714972800\n"
                        "#   labels:STARRED   1714972900\n"
                        "#   attach:f4ab12..  \"deck.pdf|application/pdf|2.4MB\"\n"
                        "#   body:html        <gzipped html>"
                    ),
                },
                {"type": "h3", "text": "Why This Row Key"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>user_id prefix:</strong> all of a user's data is one contiguous range — easy GDPR delete",
                        "<strong>thread_id next:</strong> conversation messages co-locate; one scan loads the full thread",
                        "<strong>msg_id last:</strong> within a thread, ordered by arrival; cursor pagination is trivial",
                        "<strong>Hash user_id first:</strong> avoids hot regions when popular tenants ramp",
                        "<strong>Tablet split:</strong> Bigtable auto-splits ranges; very large mailboxes fan across tablets",
                    ],
                },
                {"type": "h3", "text": "Attachment Deduplication"},
                {
                    "type": "bullets",
                    "items": [
                        "Compute <strong>SHA-256</strong> of the attachment bytes during MIME parse",
                        "Object-store key = content hash; PUT is idempotent (same hash → same blob)",
                        "Reference count tracked separately (or rely on lifecycle rules for cleanup)",
                        "<strong>Win:</strong> a viral PDF emailed to 1 M users stores <em>once</em>, ~1 M tiny references",
                        "<strong>Caveat:</strong> per-user encryption breaks dedup — solved with envelope encryption (per-blob key wrapped per-user)",
                        "Estimated savings: <strong>30–40%</strong> of attachment bytes on real-world workloads",
                    ],
                },
                {"type": "h3", "text": "Bigtable vs Spanner"},
                {
                    "type": "table",
                    "headers": ["Aspect", "Bigtable", "Spanner"],
                    "rows": [
                        ["Consistency", "Single-row atomic; eventual across rows", "External consistency, multi-row TX"],
                        ["Throughput", "Massive (sequential row writes)", "Lower; TX coordination cost"],
                        ["Use", "Message rows, label cells", "Account directory, billing, quota"],
                        ["Cost", "$ per node + storage", "$$ — pricier per QPS"],
                        ["Schema", "Schemaless cells", "Strong schema with secondary indexes"],
                    ],
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Threading (Conversation View)",
            "subtitle": "Grouping messages",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Gmail's signature feature is the <strong>conversation view</strong>: a "
                        "back-and-forth thread shown as one expandable card. Threading is "
                        "computed at delivery time and stored as a canonical "
                        "<code>thread_id</code> per user. Clients never re-thread."
                    ),
                },
                {"type": "h3", "text": "Threading Algorithm (RFC 5322 + Gmail tweaks)"},
                {
                    "type": "code",
                    "text": (
                        "def resolve_thread_id(user_id, msg):\n"
                        "    # 1. Prefer the chain referenced by the message itself.\n"
                        "    candidates = []\n"
                        "    if msg.in_reply_to:\n"
                        "        candidates.append(msg.in_reply_to)\n"
                        "    candidates.extend(reversed(msg.references or []))  # newest-first\n"
                        "\n"
                        "    for ref in candidates:\n"
                        "        existing = lookup_by_message_id(user_id, ref)\n"
                        "        if existing:\n"
                        "            return existing.thread_id\n"
                        "\n"
                        "    # 2. Fallback: subject normalisation + sliding window.\n"
                        "    norm = normalise_subject(msg.subject)\n"
                        "    #   strip 'Re:', 'Fwd:', '[list]', trailing whitespace, case\n"
                        "    if norm:\n"
                        "        recent = recent_threads_with_subject(user_id, norm,\n"
                        "                                             window=timedelta(days=14))\n"
                        "        # require at least one shared participant for safety\n"
                        "        for t in recent:\n"
                        "            if msg.participants & t.participants:\n"
                        "                return t.thread_id\n"
                        "\n"
                        "    # 3. New thread.\n"
                        "    return new_thread_id()\n"
                        "\n"
                        "def normalise_subject(s):\n"
                        "    s = re.sub(r'^(re|fwd|fw|aw)\\s*:\\s*', '', s, flags=re.I)\n"
                        "    s = re.sub(r'^\\[.*?\\]\\s*', '', s)  # strip mailing-list tags\n"
                        "    return s.strip().lower()"
                    ),
                },
                {"type": "h3", "text": "Why Per-User Thread IDs"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Privacy:</strong> Alice's view of a thread shouldn't leak Bob's participation",
                        "<strong>Asymmetric membership:</strong> Bob may be added later; his thread starts mid-conversation",
                        "<strong>BCC handling:</strong> hidden recipients shouldn't change the visible thread for others",
                        "<strong>Message-ID is global, but threading is local</strong> — dual lookup tables: by msg-id, by thread-id",
                    ],
                },
                {"type": "h3", "text": "Edge Cases"},
                {
                    "type": "table",
                    "headers": ["Case", "Behaviour"],
                    "rows": [
                        ["Missing References header", "Fall back to subject + participants window"],
                        ["Subject changed mid-thread", "References still chain; thread persists"],
                        ["Common subject (\"hi\")", "Subject heuristic disabled below a length/uniqueness floor"],
                        ["Mailing list bounces", "Strip [list-tag] and re-evaluate"],
                        ["Forwarded standalone", "User explicitly forwarded → start new thread"],
                        ["Self-reply (sent + received)", "Same thread on both sides via cross-ref index"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why Subject Alone Is Not Enough",
                    "body": (
                        "Two unrelated people can both email Alice with subject "
                        "<code>Lunch?</code>. Subject matching without participant overlap or a "
                        "References chain produces incorrect merges. Always require a "
                        "corroborating signal."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Labels vs Folders",
            "subtitle": "Gmail's tag model on top of IMAP",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Traditional mail clients organise mail in <strong>folders</strong>: a "
                        "tree where each message lives in exactly one node (1:N). Gmail uses "
                        "<strong>labels</strong>: a tag set where each message can carry many "
                        "labels (M:N). The IMAP protocol only knows about folders, so Gmail "
                        "<em>projects</em> labels onto folders for IMAP clients."
                    ),
                },
                {"type": "h3", "text": "Labels vs Folders"},
                {
                    "type": "table",
                    "headers": ["Property", "Folders (IMAP)", "Labels (Gmail)"],
                    "rows": [
                        ["Cardinality", "1 message → 1 folder", "1 message → many labels"],
                        ["Structure", "Hierarchical tree", "Flat or nested namespace"],
                        ["Storage", "Move = copy + delete", "Add/remove a column cell"],
                        ["Queries", "List by folder", "Intersect/union of labels"],
                        ["Archive", "Move to Archive folder", "Remove INBOX label"],
                        ["Trash", "Move to Trash folder", "Add TRASH label, remove others"],
                        ["IMAP fidelity", "Native", "Each label appears as a virtual folder"],
                    ],
                },
                {"type": "h3", "text": "Schema for Labels"},
                {
                    "type": "code",
                    "text": (
                        "-- Logical model (the real impl is Bigtable cells, but this captures it)\n"
                        "CREATE TABLE labels (\n"
                        "    user_id     BIGINT,\n"
                        "    label_id    BIGINT,\n"
                        "    name        VARCHAR(120),\n"
                        "    parent_id   BIGINT,        -- nested labels\n"
                        "    color       VARCHAR(16),\n"
                        "    is_system   BOOLEAN,       -- INBOX, SENT, SPAM, TRASH, STARRED, IMPORTANT\n"
                        "    PRIMARY KEY (user_id, label_id)\n"
                        ");\n"
                        "\n"
                        "CREATE TABLE message_labels (\n"
                        "    user_id     BIGINT,\n"
                        "    msg_id      BIGINT,\n"
                        "    label_id    BIGINT,\n"
                        "    applied_at  TIMESTAMP,\n"
                        "    PRIMARY KEY (user_id, msg_id, label_id),\n"
                        "    INDEX (user_id, label_id, applied_at DESC)  -- list a label\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "Mapping Labels Onto IMAP"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Each label = one IMAP folder</strong> (e.g., <code>[Gmail]/All Mail</code>, <code>[Gmail]/Sent</code>)",
                        "A message with N labels appears in N IMAP folders — same UID across them",
                        "IMAP <em>MOVE</em> from <code>INBOX</code> → <code>Receipts</code> = remove INBOX label, add Receipts label",
                        "IMAP <em>COPY</em> = add a label",
                        "<code>[Gmail]/All Mail</code> is the universe; deleting from a label folder doesn't remove from All Mail",
                        "Gmail-specific extensions (<code>X-GM-LABELS</code>, <code>X-GM-THRID</code>) expose native model to IMAP-aware clients",
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Search",
            "subtitle": "Per-user inverted index",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Search must return results in &lt;500 ms across a 25 GB mailbox, with "
                        "&lt;30 s freshness from delivery. The natural partition key is "
                        "<code>user_id</code>: queries always run against a single user's "
                        "corpus."
                    ),
                },
                {"type": "h3", "text": "Index Architecture"},
                {
                    "type": "bullets",
                    "items": [
                        "Per-user <strong>Lucene</strong>-style inverted index, sharded by user_id",
                        "Many users per shard (small users co-tenant); whales get dedicated shards",
                        "Fields: <code>from</code>, <code>to</code>, <code>cc</code>, <code>subject</code>, <code>body</code>, <code>label</code>, <code>has:attachment</code>, <code>filename</code>, <code>before:</code>, <code>after:</code>",
                        "Tokenise body with language detection; ICU analyser for CJK / RTL",
                        "Store snippets in the index for instant preview without a Bigtable round-trip",
                        "Replicate index 3-way; queries hit any replica (read-any-quorum)",
                    ],
                },
                {"type": "h3", "text": "Near-Real-Time Refresh"},
                {
                    "type": "numbered",
                    "items": [
                        "Mailbox Service publishes a delivery event to Kafka topic <code>mail.events</code>",
                        "Indexer consumer (per shard) reads events partitioned by user_id",
                        "Builds in-memory segment; flushes to disk every 5 seconds (or 10 MB)",
                        "Searcher opens new segment via Lucene's <code>SearcherManager.maybeRefresh()</code>",
                        "Net visibility: typically <strong>5–15 seconds</strong>; SLO &lt;30 s",
                        "Background merger compacts small segments hourly; major merge nightly",
                    ],
                },
                {"type": "h3", "text": "Inverted Index vs Bigtable Scan"},
                {
                    "type": "table",
                    "headers": ["Approach", "Pros", "Cons"],
                    "rows": [
                        ["Bigtable scan + filter", "No second store; consistent with mailbox",
                         "Slow on large mailboxes; reads every byte of body; no relevance ranking"],
                        ["Dedicated Lucene index", "Sub-second queries; scoring; phrase/wildcard",
                         "Extra storage (~30%); index lag; rebuild cost on schema change"],
                        ["Hybrid: index for text, BT for fields", "Best of both; cheap header filters",
                         "Two query paths; merge complexity"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Always Pin to user_id",
                    "body": (
                        "Every query carries the authenticated user_id as the first filter. The "
                        "index is partitioned by user_id, so a query touches exactly one shard. "
                        "This is what makes &lt;500 ms feasible across a 25 GB mailbox."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Spam Filtering",
            "subtitle": "ML at SMTP edge with feedback loop",
            "blocks": [
                {"type": "h3", "text": "Multi-Layer Defence"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>L1 — IP/domain reputation:</strong> reject at SMTP envelope; cheapest layer",
                        "<strong>L2 — Authentication:</strong> SPF/DKIM/DMARC; failures mark suspicious",
                        "<strong>L3 — Content fingerprints:</strong> known-bad URL/hash blocklists",
                        "<strong>L4 — ML model:</strong> LightGBM / DNN scoring full message",
                        "<strong>L5 — User feedback:</strong> 'Mark as spam' / 'Not spam' close the loop",
                    ],
                },
                {"type": "h3", "text": "ML Features"},
                {
                    "type": "bullets",
                    "items": [
                        "Sender reputation history (per IP / per domain / per ASN)",
                        "Header anomalies (date skew, malformed Message-ID, mismatched From/Reply-To)",
                        "Body features: TF-IDF, URL count, image-only ratio, language match",
                        "Recipient features: how the user has historically treated this sender",
                        "Content embeddings (transformer-based) for novel-spam generalisation",
                        "Engagement signal: how often this sender's mail gets opened / replied to",
                    ],
                },
                {"type": "h3", "text": "Decision Thresholds"},
                {
                    "type": "table",
                    "headers": ["Score", "Action"],
                    "rows": [
                        ["&lt; 0.10", "Inbox; high-confidence ham"],
                        ["0.10 – 0.50", "Inbox; light category sort (Promotions / Updates / Social)"],
                        ["0.50 – 0.95", "Spam folder; user can recover"],
                        ["≥ 0.95", "Silent drop / 5xx reject (clear malware/phish)"],
                    ],
                },
                {"type": "h3", "text": "Feedback Loop"},
                {
                    "type": "numbered",
                    "items": [
                        "User marks a message as spam (or not-spam)",
                        "Event written to <code>spam.feedback</code> Kafka topic",
                        "Online learner updates per-user weights immediately (personalisation)",
                        "Aggregated daily into the global model retraining set",
                        "Promote new model after offline AUC + canary traffic ≥ baseline",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Model Drift",
                    "body": (
                        "Spammers retool weekly. Without continuous retraining and drift "
                        "monitoring, recall drops within days. Track per-day false-positive and "
                        "false-negative rates; alert on &gt;0.1% FP for human-to-human mail."
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Email Lifecycle",
            "subtitle": "From sender to notification",
            "blocks": [
                {
                    "type": "diagram",
                    "caption": "End-to-end lifecycle: SMTP receive → ingest pipeline → mailbox write → search index update → mobile push.",
                    "dot": r"""
digraph L {
    rankdir=TB;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    S  [label="Sender MTA", fillcolor="#dbe6fb"];
    MX [label="MX Receiver\n(TLS, ESMTP)", fillcolor="#cbeedf"];
    R  [label="Reputation\n+ Greylist", fillcolor="#cbeedf"];
    A  [label="DKIM / SPF / DMARC", fillcolor="#cbeedf"];
    V  [label="Anti-virus", fillcolor="#cbeedf"];
    SP [label="Spam ML\nscorer", fillcolor="#cbeedf"];
    RT [label="Routing\n(addr → user_id)", fillcolor="#cbeedf"];
    TH [label="Thread\nresolver", fillcolor="#fff2c9"];
    MB [label="Mailbox write\n(Bigtable + Object Store)", fillcolor="#fff2c9"];
    K  [label="Kafka\nmail.events", fillcolor="#fbd7c5"];
    IX [label="Search index\nrefresh (5–15 s)", fillcolor="#ead7fb"];
    P  [label="Mobile push\n(APNs / FCM)", fillcolor="#ead7fb"];
    W  [label="Web / IMAP\nclient delivery", fillcolor="#ead7fb"];

    S -> MX -> R -> A -> V -> SP -> RT -> TH -> MB -> K;
    K -> IX;
    K -> P;
    MB -> W [label="long-poll / IDLE"];
}
""",
                },
                {"type": "h3", "text": "Latency Budget (target: &lt;30 s end-to-end)"},
                {
                    "type": "table",
                    "headers": ["Stage", "Typical", "P99"],
                    "rows": [
                        ["MX accept + TLS", "30 ms", "150 ms"],
                        ["Reputation + auth", "20 ms", "200 ms"],
                        ["Anti-virus scan", "100 ms", "1 s"],
                        ["Spam ML score", "50 ms", "300 ms"],
                        ["Thread resolve", "20 ms", "200 ms"],
                        ["Mailbox persist", "50 ms", "500 ms"],
                        ["Kafka publish", "10 ms", "100 ms"],
                        ["Indexer flush", "5 s", "30 s"],
                        ["Push to device", "1 s", "10 s"],
                        ["<strong>Total visible</strong>", "<strong>&lt; 7 s</strong>", "<strong>&lt; 30 s</strong>"],
                    ],
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Outbound Send Path",
            "subtitle": "Compose to remote MX",
            "blocks": [
                {"type": "h3", "text": "Send Steps"},
                {
                    "type": "numbered",
                    "items": [
                        "Web/mobile composer POSTs to API: <code>POST /v1/messages</code>",
                        "Server validates auth, quota, recipient list size",
                        "Persist as <code>DRAFT</code> in user's mailbox first (so a crash doesn't lose it)",
                        "On Send: write <code>SENT</code> label, enqueue to outbound queue",
                        "Outbound MTA looks up MX records for each recipient domain",
                        "DKIM-sign the outgoing message with our domain's selector",
                        "Connect to remote MX over TLS; deliver via SMTP",
                        "On 5xx: bounce → DSN to sender; on 4xx: retry with backoff (15 min, 1 h, 4 h, 24 h)",
                        "Final result (delivered or bounced) updates the SENT message status",
                    ],
                },
                {"type": "h3", "text": "Outbound Reputation Hygiene"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Per-IP warm-up</strong> for new sending IPs to avoid block-listing",
                        "<strong>Bounce-rate monitoring:</strong> auto-disable accounts &gt;5% hard-bounce",
                        "<strong>Spam-trap detection:</strong> if user's outbound triggers RBL, suspend",
                        "<strong>Rate-limit per user:</strong> ~500 recipients/day for free accounts",
                        "<strong>Feedback loops:</strong> ARF reports from large providers feed user-account abuse model",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Persist Drafts Before Send",
                    "body": (
                        "Mobile networks drop. Persist drafts on every keystroke (debounced) so "
                        "Send is just a flag flip. The Sent message and the Inbox copy at the "
                        "recipient should appear within 5 seconds of clicking Send."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Protocols & Comparison",
            "subtitle": "IMAP, POP, JMAP, SMTP",
            "blocks": [
                {"type": "h3", "text": "Protocol Roles"},
                {
                    "type": "table",
                    "headers": ["Protocol", "Direction", "Role"],
                    "rows": [
                        ["SMTP", "in / out", "Server-to-server transport (port 25, 587 submit)"],
                        ["IMAP", "client read", "Stateful sync; folders; flags; partial fetch"],
                        ["POP3", "client read", "Download-and-delete; minimal state on server"],
                        ["JMAP", "client read", "Modern JSON-over-HTTPS; push, batch, rich queries"],
                        ["HTTPS API", "client read/write", "First-party web/mobile; richest features"],
                        ["DKIM/SPF/DMARC", "auth", "Domain-level message authentication"],
                    ],
                },
                {"type": "h3", "text": "SMTP vs JMAP"},
                {
                    "type": "table",
                    "headers": ["Aspect", "SMTP / IMAP", "JMAP"],
                    "rows": [
                        ["Transport", "Stateful TCP, multi-port", "HTTPS, single port"],
                        ["Encoding", "RFC 5322 / MIME", "JSON"],
                        ["Push", "IMAP IDLE (poll-ish)", "Native push channel"],
                        ["Batching", "Round-trip per command", "Single batched call"],
                        ["Search", "Server-side, limited", "Rich filter + sort"],
                        ["Mobile fit", "Battery-hostile", "HTTP-friendly"],
                    ],
                },
                {"type": "h3", "text": "Provider Comparison"},
                {
                    "type": "table",
                    "headers": ["Provider", "Org Model", "Search", "E2E Encryption", "Notable"],
                    "rows": [
                        ["Gmail", "Labels (M:N) on IMAP folder façade", "Per-user Lucene; conversations", "Optional S/MIME, no E2E by default", "ML spam, conversation view, AI features"],
                        ["Outlook (M365)", "Folders + Categories", "Exchange Search (Lucene-based)", "S/MIME, optional Purview encryption", "Tight Office/Teams integration"],
                        ["ProtonMail", "Folders + Labels", "Client-side encrypted index", "Native E2E (PGP)", "Privacy-first; smaller scale"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why Gmail Keeps IMAP",
                    "body": (
                        "JMAP is technically nicer, but two decades of MUAs, scripts, and devices "
                        "speak IMAP. The value of an interoperable inbox dominates the cost of "
                        "translating labels to folders. Gmail-native clients use the HTTPS API."
                    ),
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Failure Modes",
            "subtitle": "What can go wrong",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["Bigtable hot tablet (whale user)",
                         "Mailbox slow; queue backs up",
                         "Tablet QPS / latency dashboard",
                         "Salt user_id; shard whale to dedicated cluster"],
                        ["DKIM verification slow / DNS flaky",
                         "Ingest latency spikes",
                         "P99 verify time alarm",
                         "Async DKIM: provisionally accept, re-verify offline; cache pubkeys"],
                        ["Spam model drift",
                         "Recall drops; complaints rise",
                         "Daily FP/FN metric, user-mark-spam rate",
                         "Continuous retraining; canary rollout; per-user personalisation"],
                        ["MX overload (mail storm)",
                         "Senders see 4xx; queue grows",
                         "Conn-rate, queue-depth alarm",
                         "Per-source rate limit; tarpit; auto-scale receivers"],
                        ["Index lag &gt; 30 s",
                         "Search misses recent mail",
                         "Refresh-lag SLO breach",
                         "Add indexer consumers; flush more often; degrade to BT scan"],
                        ["Object store unavailable",
                         "Attachments fail to load",
                         "PUT/GET error rate",
                         "Multi-region replication; serve stale via CDN; degrade attachment-only"],
                        ["Outbound IP blocklisted",
                         "Mail to that domain bounces",
                         "Bounce-rate per IP",
                         "Reputation pool: rotate sending IP; submit delisting"],
                        ["AV scanner crash loop",
                         "Ingest stalls (fail-closed)",
                         "Worker liveness",
                         "Bypass with quarantine label and async re-scan"],
                        ["Cross-region partition",
                         "Cannot replicate",
                         "Replication lag alarm",
                         "Continue local writes; reconcile on heal"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Fail-Closed on Auth, Fail-Open on Convenience",
                    "body": (
                        "If anti-virus is down, hold mail (fail closed) — a malware delivery is "
                        "worse than a delay. If the search index is lagging, allow inbox load "
                        "(fail open) — search can be stale, but mail must arrive."
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
                        ["Search freshness vs cost",
                         "5–15 s typical; ≤30 s SLO",
                         "Tighter freshness multiplies indexer cost (more flushes, more replicas). 30 s is the user-perceptible sweet spot."],
                        ["Dedup at storage vs query time",
                         "Storage-time content-hash",
                         "Hash work on ingest is a fixed cost; saves 30–40% of attachment bytes forever. Query-time dedup wastes storage and complicates retention."],
                        ["IMAP fidelity vs Gmail-native model",
                         "Both: labels-as-folders + X-GM extensions",
                         "Native model is richer; IMAP keeps two decades of clients working. Worth the translation cost."],
                        ["Threading at delivery vs at read",
                         "At delivery (canonical thread_id)",
                         "Heavier write path; constant-time read. Re-threading on read would double inbox-load cost."],
                        ["Spam: silent drop vs spam folder",
                         "Drop only at ≥0.95; otherwise spam folder",
                         "Silent drop hides false positives forever. Spam folder lets users recover at the cost of clutter."],
                        ["Bigtable vs Spanner",
                         "Bigtable for messages, Spanner for accounts",
                         "Bigtable is cheaper at scale; Spanner gives ACID where it matters (billing, quota, login)."],
                        ["Per-user index shard vs global",
                         "Per-user partitioned (many users / shard)",
                         "Per-user keeps query latency tight; global index would dominate compute and complicate ACLs."],
                        ["E2E encryption",
                         "Off by default",
                         "E2E breaks search, spam scoring, and dedup. Provider-side encryption + audit is the practical compromise."],
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
                        "Gmail is a deceptively deep prompt: SMTP ingest, threading, labels, "
                        "search, and spam are each a system in themselves. Drive the discussion; "
                        "do not let the interviewer pull you into a single rabbit-hole until the "
                        "skeleton is up."
                    ),
                },
                {"type": "h3", "text": "45-Minute Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Clarify (3 min):</strong> 2 B users, 300 B msgs/day, 25 GB/user; protocols (SMTP/IMAP/web)",
                        "<strong>Capacity (4 min):</strong> 3.5 M/sec ingest, ~10 EB live, ~30 PB/day raw, search lag &lt;30 s",
                        "<strong>Architecture (5 min):</strong> SMTP MX → reputation/auth/AV/spam → mailbox → BT/object/index/Kafka → IMAP/web/push",
                        "<strong>Ingest deep dive (8 min):</strong> SPF/DKIM/DMARC matrix, threading, 250-OK only after persist",
                        "<strong>Storage (6 min):</strong> Bigtable row key (user, thread, msg); attachment dedup by SHA-256",
                        "<strong>Threading (5 min):</strong> References chain → subject + participant fallback; per-user thread_id",
                        "<strong>Search (5 min):</strong> per-user Lucene shard, Kafka-driven NRT refresh, 5–15 s freshness",
                        "<strong>Spam (4 min):</strong> 5-layer defence, ML at scoring, user feedback closes the loop",
                        "<strong>Failures (3 min):</strong> hot user, model drift, index lag, fail-closed on AV",
                        "<strong>Trade-offs (2 min):</strong> Bigtable/Spanner split; labels-as-folders for IMAP",
                    ],
                },
                {"type": "h3", "text": "Numbers To Memorise"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>2 B</strong> users · <strong>300 B</strong> msgs/day · <strong>3.5 M</strong> msgs/sec",
                        "<strong>25 GB</strong>/user · <strong>~10 EB</strong> live · <strong>~30 PB/day</strong> raw inbound",
                        "Search freshness <strong>&lt; 30 s</strong>, query <strong>&lt; 500 ms</strong>",
                        "Inbox load <strong>&lt; 200 ms</strong>; total visible delivery <strong>&lt; 7 s</strong>",
                        "Spam: ≥<strong>99.9%</strong> recall, &lt;<strong>0.1%</strong> false positive on human mail",
                        "Attachment dedup saves <strong>30–40%</strong> of bytes",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: How do you scale a 'whale' mailbox?</strong> A: Hash user_id into row key; Bigtable auto-splits tablets; very large mailboxes get a dedicated cluster and a sharded index.",
                        "<strong>Q: How does conversation view stay consistent across IMAP and web?</strong> A: thread_id is computed once at delivery and stored on each message; IMAP exposes via <code>X-GM-THRID</code>; web reads the same column.",
                        "<strong>Q: How do you keep search fresh?</strong> A: Mailbox publishes to Kafka; per-user-shard indexer flushes 5–10 s segments; Lucene <code>maybeRefresh</code> opens them. SLO &lt;30 s.",
                        "<strong>Q: Why labels and not folders?</strong> A: Real workflows are M:N (a receipt is also Travel and also Important). Labels are cheap cell adds in Bigtable; moves between folders would be a copy + delete.",
                        "<strong>Q: How do you stop spam loops?</strong> A: SPF/DKIM/DMARC at the door, per-IP/domain reputation, ML score, user feedback into per-user weights, daily global retrain with canary.",
                        "<strong>Q: GDPR delete?</strong> A: All of a user's rows share the user_id prefix; one range delete in Bigtable plus an attachment-refcount sweep handles it.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "One-Sentence Pitch",
                    "body": (
                        "Receive over SMTP with reputation + DKIM/SPF/DMARC + AV + ML spam → "
                        "persist to a Bigtable row keyed by <code>(user_id, thread_id, msg_id)</code> "
                        "with attachments deduped in object storage → fan a Kafka event to a "
                        "per-user Lucene index → serve to IMAP/JMAP/web with conversation view "
                        "computed at delivery."
                    ),
                },
            ],
        },
    ],
}
