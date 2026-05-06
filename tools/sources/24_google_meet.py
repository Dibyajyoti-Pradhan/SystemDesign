"""Source for `24 - Google Meet.pdf`."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Google Meet",
    "subtitle": "Group video conferencing at scale: WebRTC, SFU topology, adaptive streaming, recording",
    "read_time": "~ 45 minute read",
    "short_title": "Design Google Meet",
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
                        "Design a real-time group video conferencing platform like "
                        "<strong>Google Meet</strong>, <strong>Zoom</strong>, or "
                        "<strong>Microsoft Teams</strong>. The service must support multi-party "
                        "audio/video calls, screen sharing, recording, and live captions, all "
                        "running over the public internet at planetary scale."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Concurrent participants peak?", "~100M global (post-COVID baseline)"],
                        ["Avg call shape?", "4 participants, 30 minutes"],
                        ["Calls/day?", "~10M"],
                        ["Max participants per call?", "500 active video, up to 100K view-only (livestream)"],
                        ["Devices?", "Browser (WebRTC), iOS, Android, native desktop"],
                        ["Recording?", "Yes; cloud recording to GCS, optional captions burn-in"],
                        ["Captions / translation?", "Real-time ASR; live translation to ~30 languages"],
                        ["E2E encryption?", "Optional client-side E2EE for &lt;= 200 participants"],
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
                        ["Join / leave", "Authenticated room join via meeting code or link"],
                        ["Audio + video", "Bidirectional A/V; mute / camera toggle; pin / spotlight"],
                        ["Screen share", "Share window or full screen as additional video track"],
                        ["Adaptive quality", "Auto-adjust resolution/bitrate to match downlink BW"],
                        ["Recording", "Cloud recording with composed layout; upload to GCS"],
                        ["Live captions", "Speech-to-text streamed back via data channel"],
                        ["Chat + reactions", "Text chat sidecar; ephemeral emoji reactions"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["End-to-end latency", "&lt; 150 ms mouth-to-ear at p50; &lt; 300 ms at p99"],
                        ["Availability", "99.99% (4 nines); regional failover within 30 s"],
                        ["Concurrent participants", "100M global peak"],
                        ["Calls / day", "10M; 4 participants × 30 min average"],
                        ["Quality", "VP9 / AV1 video; Opus audio; FEC + RED for loss"],
                        ["Loss tolerance", "Smooth at 5% packet loss; degraded at 20%"],
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
                {"type": "h3", "text": "Traffic Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        "Concurrent participants peak: <strong>100M</strong> globally",
                        "Average call: <strong>4 participants × 30 min</strong>",
                        "Calls/day: <strong>~10M</strong> (each contributes 4 participant-sessions)",
                        "Participant-sessions/day: 10M × 4 = <strong>40M</strong>",
                        "Participant-minutes/day: 40M × 30 min = <strong>1.2B participant-minutes</strong>",
                        "Steady-state concurrent (avg): 1.2B / 1440 min ≈ <strong>833K</strong>; peak amplifies ~120× to 100M",
                    ],
                },
                {"type": "h3", "text": "Bandwidth per Participant"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Uplink:</strong> 1 video stream out at ~1.5 Mbps (720p, simulcast L3) + audio at 40 kbps Opus",
                        "<strong>Downlink (1-on-1):</strong> 1 stream in ≈ 1.5 Mbps",
                        "<strong>Downlink (4-person call):</strong> 3 streams × ~0.5 Mbps (mid layer) ≈ 1.5 Mbps",
                        "<strong>Downlink (25-tile gallery):</strong> 24 streams × ~150 kbps (low layer) ≈ 3.6 Mbps",
                        "<strong>Downlink (100-person webinar, all visible):</strong> up to 25 Mbps; SFU only forwards <strong>top-N by speaker</strong> (N≈9)",
                    ],
                },
                {"type": "h3", "text": "Aggregate SFU Capacity"},
                {
                    "type": "bullets",
                    "items": [
                        "Per participant ingress (1 stream up): ~1.5 Mbps audio+video",
                        "Per participant egress (avg 5 streams down): ~3 Mbps",
                        "Per SFU box (32-core, 100 Gbps NIC): ~5K participants peak",
                        "100M peak / 5K per box = <strong>20,000 SFU boxes</strong> globally",
                        "Distribute across <strong>~30 regions</strong>; each region ≈ 600–800 SFUs",
                    ],
                },
                {"type": "h3", "text": "Storage (Recordings)"},
                {
                    "type": "bullets",
                    "items": [
                        "Recording bitrate: ~2 Mbps composed (1080p layout + audio)",
                        "Per recorded minute: 2 Mbps × 60 / 8 = <strong>15 MB</strong>",
                        "If 5% of calls record (500K/day) avg 30 min: 500K × 30 × 15 MB = <strong>225 TB/day</strong>",
                        "90-day retention default: <strong>~20 PB</strong> in GCS Standard + Coldline",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "Peak concurrent: <strong>100M</strong> &nbsp;·&nbsp; "
                        "Calls/day: <strong>10M</strong> &nbsp;·&nbsp; "
                        "SFU fleet: <strong>~20K boxes</strong> across 30 regions &nbsp;·&nbsp; "
                        "Recordings: <strong>~225 TB/day</strong> &nbsp;·&nbsp; "
                        "Mouth-to-ear p50 &lt; <strong>150 ms</strong>."
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "Topology Choice: Mesh vs MCU vs SFU",
            "subtitle": "Why Google chose SFU + simulcast",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The single largest architectural decision is <strong>how media flows</strong> "
                        "between participants. There are three classical topologies; all real "
                        "products at scale converge on SFU."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Mesh (P2P, full graph) vs MCU (server mixes one stream) vs SFU (server forwards selectively).",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=circle, style="filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_mesh {
        label="Mesh (P2P)\nO(N^2) connections"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        M1 [label="A", fillcolor="#cbeedf"];
        M2 [label="B", fillcolor="#cbeedf"];
        M3 [label="C", fillcolor="#cbeedf"];
        M4 [label="D", fillcolor="#cbeedf"];
        M1 -> M2 [dir=both]; M1 -> M3 [dir=both]; M1 -> M4 [dir=both];
        M2 -> M3 [dir=both]; M2 -> M4 [dir=both]; M3 -> M4 [dir=both];
    }
    subgraph cluster_mcu {
        label="MCU (mixer)\n1 stream out, heavy CPU"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        U1 [label="A", fillcolor="#fff2c9"]; U2 [label="B", fillcolor="#fff2c9"];
        U3 [label="C", fillcolor="#fff2c9"]; U4 [label="D", fillcolor="#fff2c9"];
        MCU [label="MCU\nMix+Encode", shape=box, style="rounded,filled", fillcolor="#ffd9a8"];
        U1 -> MCU [dir=both]; U2 -> MCU [dir=both];
        U3 -> MCU [dir=both]; U4 -> MCU [dir=both];
    }
    subgraph cluster_sfu {
        label="SFU (forwarder)\nN streams in, N-1 out per peer"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        S1 [label="A", fillcolor="#ead7fb"]; S2 [label="B", fillcolor="#ead7fb"];
        S3 [label="C", fillcolor="#ead7fb"]; S4 [label="D", fillcolor="#ead7fb"];
        SFU [label="SFU\nSelective\nForward", shape=box, style="rounded,filled", fillcolor="#dabbf5"];
        S1 -> SFU [dir=both]; S2 -> SFU [dir=both];
        S3 -> SFU [dir=both]; S4 -> SFU [dir=both];
    }
}
""",
                },
                {"type": "h3", "text": "Comparison Table"},
                {
                    "type": "table",
                    "headers": ["Aspect", "Mesh (P2P)", "MCU", "SFU"],
                    "rows": [
                        ["Connections per peer", "N-1", "1", "1"],
                        ["Server CPU", "None", "Very high (decode + mix + encode)", "Low (forward only, no transcode)"],
                        ["Server bandwidth", "0", "N in + N out", "N in + N×(N-1) out"],
                        ["Best for", "&lt; 4 participants", "Legacy / phone bridge", "&gt; 4 participants (general case)"],
                        ["Per-receiver layout", "Client", "Server-fixed", "Client-chosen (flexible)"],
                        ["Cost at 100 ppl", "Infeasible (uplink saturation)", "$$$ GPU encoders", "$ commodity NIC"],
                        ["End-to-end encryption", "Native", "Breaks E2EE (server decrypts)", "Possible via Insertable Streams"],
                    ],
                },
                {"type": "h3", "text": "Why SFU + Simulcast Wins"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Linear uplink:</strong> sender uploads exactly 1 stream regardless of room size",
                        "<strong>No transcode:</strong> SFU is mostly a packet router; CPU stays cheap",
                        "<strong>Per-receiver adaptation:</strong> SFU forwards a different simulcast layer to each subscriber based on their downlink",
                        "<strong>E2EE-compatible:</strong> SFU does not need to decrypt payload; it only inspects RTP headers",
                        "<strong>Mesh fallback:</strong> for 2-person calls, Meet uses pure P2P to bypass the SFU when ICE permits (lowest latency, no server cost)",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "High-Level Architecture",
            "subtitle": "Control plane vs media plane",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Meet cleanly separates the <strong>signaling (control) plane</strong> "
                        "(WebSocket, JSON, room state, ICE) from the <strong>media plane</strong> "
                        "(UDP/SRTP, RTP packets through the SFU). The two run on different "
                        "services with different SLOs and scaling profiles."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Browser/App → Edge SFU and Signaling. Media flows over UDP/SRTP; signaling rides WebSocket; auxiliary services (recording, ASR, identity) attach to both planes.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Client"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Cli [label="Browser / App\n(WebRTC stack)", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        SIG [label="Signaling\n(WebSocket, gRPC)", fillcolor="#cbeedf"];
        SFU [label="Edge SFU\n(UDP/SRTP)", fillcolor="#cbeedf"];
        TURN [label="TURN/STUN\n(NAT traversal)", fillcolor="#cbeedf"];
    }
    subgraph cluster_media {
        label="Media services"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        SFU2 [label="Other-region\nSFU mesh", fillcolor="#ead7fb"];
        REC [label="Recording\nComposer", fillcolor="#ead7fb"];
        ASR [label="ASR /\nCaptions", fillcolor="#ead7fb"];
    }
    subgraph cluster_ctrl {
        label="Control services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        ID [label="Identity\n(OAuth)", fillcolor="#fff2c9"];
        CAL [label="Calendar /\nInvites", fillcolor="#fff2c9"];
        NOT [label="Notifications\n(push, email)", fillcolor="#fff2c9"];
        ROOM [label="Room State\n(Spanner)", fillcolor="#fff2c9"];
    }
    subgraph cluster_store {
        label="Storage"; style="rounded,dashed"; color="#a23939"; fontcolor="#a23939";
        GCS [label="GCS\n(recordings)", fillcolor="#fbd7c5"];
        BQ [label="BigQuery\n(analytics)", fillcolor="#fbd7c5"];
    }

    Cli -> SIG [label="WebSocket\nJSON / SDP"];
    Cli -> TURN [label="ICE", style=dashed];
    Cli -> SFU [label="UDP/SRTP\n(RTP media)", color="#7a3eb8"];
    SIG -> ROOM;
    SIG -> ID;
    SIG -> CAL [style=dashed];
    SIG -> NOT [style=dashed];
    SFU -> SFU2 [label="cascade"];
    SFU -> REC [label="phantom\nsubscriber"];
    SFU -> ASR [label="audio fan-out"];
    ASR -> SIG [label="caption text", style=dashed];
    REC -> GCS;
    SIG -> BQ [style=dashed];
}
""",
                },
                {"type": "h3", "text": "Component Responsibilities"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Signaling Service:</strong> handles room join, SDP offer/answer, ICE candidate exchange, presence, mute state, chat — over WebSocket",
                        "<strong>Edge SFU:</strong> terminates SRTP, forwards selected simulcast layers to each subscriber, runs active-speaker detection",
                        "<strong>STUN/TURN:</strong> NAT traversal; TURN relays media when symmetric NAT blocks direct paths",
                        "<strong>Recording Composer:</strong> joins as a phantom participant, composes layout via FFmpeg, uploads to GCS",
                        "<strong>ASR Service:</strong> subscribes to audio streams, runs streaming speech-to-text, posts captions back via signaling data channel",
                        "<strong>Room State Store:</strong> Spanner — authoritative roster, SFU assignment, recording state",
                        "<strong>Identity / Calendar / Notifications:</strong> standard Google services for auth, invites, push",
                    ],
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Signaling Plane",
            "subtitle": "Joining a room with WebRTC",
            "blocks": [
                {"type": "h3", "text": "Join Sequence"},
                {
                    "type": "numbered",
                    "items": [
                        "Client opens WebSocket: <code>wss://meet.google.com/signal</code> with bearer token",
                        "Client sends <code>JOIN { meeting_code, device_caps }</code>",
                        "Signaling validates auth (Identity), checks roster cap (Spanner), and assigns an Edge SFU near the client (geo+load aware)",
                        "Client creates RTCPeerConnection and crafts an <strong>SDP offer</strong> (codecs, simulcast layers, ICE ufrag)",
                        "Signaling forwards offer to the SFU and returns the <strong>SDP answer</strong> with the SFU's ICE candidates",
                        "ICE candidates trickle: client and SFU exchange host / srflx / relay candidates over WS until a pair connects",
                        "DTLS handshake → SRTP keys established; RTP starts flowing",
                        "Client subscribes to other participants' tracks via <code>SUBSCRIBE { participant_id, prefer_layer }</code> messages",
                    ],
                },
                {"type": "h3", "text": "Room / Participant Schema"},
                {
                    "type": "code",
                    "text": (
                        "// Spanner: rooms\n"
                        "CREATE TABLE rooms (\n"
                        "  room_id        STRING(36) NOT NULL,\n"
                        "  meeting_code   STRING(12) NOT NULL,\n"
                        "  host_user_id   STRING(64) NOT NULL,\n"
                        "  sfu_pod_id     STRING(64),       // primary SFU assignment\n"
                        "  region         STRING(8),\n"
                        "  recording      BOOL,\n"
                        "  e2ee           BOOL,\n"
                        "  created_at     TIMESTAMP,\n"
                        "  ended_at       TIMESTAMP,\n"
                        ") PRIMARY KEY (room_id);\n\n"
                        "CREATE TABLE participants (\n"
                        "  room_id        STRING(36) NOT NULL,\n"
                        "  participant_id STRING(36) NOT NULL,\n"
                        "  user_id        STRING(64),\n"
                        "  display_name   STRING(128),\n"
                        "  role           STRING(16),       // host | cohost | guest\n"
                        "  joined_at      TIMESTAMP,\n"
                        "  left_at        TIMESTAMP,\n"
                        "  edge_sfu       STRING(64),       // which SFU pod they hit\n"
                        "  audio_muted    BOOL,\n"
                        "  video_muted    BOOL,\n"
                        ") PRIMARY KEY (room_id, participant_id),\n"
                        "  INTERLEAVE IN PARENT rooms ON DELETE CASCADE;"
                    ),
                },
                {"type": "h3", "text": "ICE Candidate Exchange (over WS)"},
                {
                    "type": "code",
                    "text": (
                        "// client -> signaling\n"
                        "{\n"
                        "  \"type\": \"ice-candidate\",\n"
                        "  \"room_id\": \"7a3...\",\n"
                        "  \"candidate\": {\n"
                        "    \"foundation\": \"3\",\n"
                        "    \"component\": 1,\n"
                        "    \"protocol\": \"udp\",\n"
                        "    \"priority\": 2122260223,\n"
                        "    \"ip\": \"203.0.113.42\",\n"
                        "    \"port\": 54321,\n"
                        "    \"type\": \"srflx\",            // host | srflx | relay\n"
                        "    \"raddr\": \"10.0.0.5\",\n"
                        "    \"rport\": 54321\n"
                        "  }\n"
                        "}\n\n"
                        "// SFU replies with its own candidates the same way until a pair connects."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Media Plane: SFU + Simulcast",
            "subtitle": "How frames flow through the wire",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Each publisher uploads <strong>three encoded layers</strong> of the same "
                        "video (simulcast). The SFU keeps all three in memory and, for each "
                        "subscriber, forwards exactly one — the one that fits the subscriber's "
                        "downlink, viewport, and CPU budget."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Publisher emits L1/L2/L3 simulcast layers. SFU subscribes each receiver to one layer based on bandwidth + viewport + active-speaker rank.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    PUB [label="Publisher\n(Alice)\nencodes 3 layers", fillcolor="#dbe6fb"];

    subgraph cluster_layers {
        label="Simulcast layers (one publisher)"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        L1 [label="L1 low\n180p, 150 kbps", fillcolor="#ead7fb"];
        L2 [label="L2 mid\n360p, 500 kbps", fillcolor="#ead7fb"];
        L3 [label="L3 high\n720p, 1.5 Mbps", fillcolor="#ead7fb"];
    }

    SFU [label="Edge SFU\n(forwarder +\nlayer selector)", fillcolor="#cbeedf"];

    subgraph cluster_subs {
        label="Subscribers"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        SubA [label="Bob\n(speaker, fullscreen)\n→ L3", fillcolor="#fff2c9"];
        SubB [label="Carol\n(gallery tile)\n→ L1", fillcolor="#fff2c9"];
        SubC [label="Dave\n(mobile, weak BW)\n→ L1", fillcolor="#fff2c9"];
        SubD [label="Eve\n(pinned mid)\n→ L2", fillcolor="#fff2c9"];
    }

    PUB -> L1 [label="RTP ssrc=1"];
    PUB -> L2 [label="RTP ssrc=2"];
    PUB -> L3 [label="RTP ssrc=3"];
    L1 -> SFU; L2 -> SFU; L3 -> SFU;
    SFU -> SubA [label="L3", color="#7a3eb8"];
    SFU -> SubB [label="L1", color="#7a3eb8"];
    SFU -> SubC [label="L1", color="#7a3eb8"];
    SFU -> SubD [label="L2", color="#7a3eb8"];
}
""",
                },
                {"type": "h3", "text": "Why Simulcast Beats Server-Side Transcoding"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Cost:</strong> client-side encoder is free; server transcoding needs GPUs",
                        "<strong>Latency:</strong> SFU just routes packets — adds ~5 ms vs ~150 ms for transcode",
                        "<strong>E2EE-friendly:</strong> SFU sees only encrypted payload + RTP headers; cannot transcode anyway",
                        "<strong>Independent rate control:</strong> client encoder reacts to its own uplink congestion (TWCC) without SFU coordination",
                    ],
                },
                {"type": "h3", "text": "SVC vs Simulcast"},
                {
                    "type": "table",
                    "headers": ["Feature", "Simulcast (VP8/VP9/H.264)", "SVC (VP9-SVC, AV1-SVC)"],
                    "rows": [
                        ["Layers", "3 separate encodes", "1 encode, multiple temporal/spatial layers in 1 stream"],
                        ["Uplink BW", "Sum of all layers (~2 Mbps)", "Single bitstream (~1.5 Mbps)"],
                        ["CPU on sender", "3× encode work", "1× encode (efficient)"],
                        ["SFU forward", "Pick one SSRC", "Pick subset of NAL units per layer ID"],
                        ["Used by", "Older Meet, Chrome default", "Modern Meet (VP9-SVC), Zoom"],
                    ],
                },
                {"type": "h3", "text": "Layer Selection Algorithm"},
                {
                    "type": "code",
                    "text": (
                        "# Per (subscriber, publisher) pair, every ~200 ms:\n"
                        "def select_layer(sub, pub, layers):\n"
                        "    # Inputs:\n"
                        "    #   sub.downlink_kbps  : TWCC estimate from REMB / TWCC\n"
                        "    #   sub.viewport      : 'tile' | 'medium' | 'fullscreen'\n"
                        "    #   sub.cpu_load      : 0..1 from client stats\n"
                        "    #   pub.is_active     : active-speaker flag\n"
                        "\n"
                        "    # 1) Cap by viewport (no point sending 720p to a 90px tile)\n"
                        "    cap = {'tile': 'L1', 'medium': 'L2', 'fullscreen': 'L3'}[sub.viewport]\n"
                        "\n"
                        "    # 2) Boost active speaker by one layer if BW allows\n"
                        "    if pub.is_active and cap != 'L3':\n"
                        "        cap = next_higher(cap)\n"
                        "\n"
                        "    # 3) Fit into remaining downlink budget\n"
                        "    budget = sub.downlink_kbps - sum(s.kbps for s in sub.current_subs)\n"
                        "    chosen = cap\n"
                        "    while layers[chosen].kbps > budget and chosen != 'L1':\n"
                        "        chosen = next_lower(chosen)\n"
                        "\n"
                        "    # 4) CPU pressure: drop one layer if client is hot\n"
                        "    if sub.cpu_load > 0.85 and chosen != 'L1':\n"
                        "        chosen = next_lower(chosen)\n"
                        "\n"
                        "    return chosen  # SFU starts forwarding this SSRC"
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Active Speaker Detection",
            "subtitle": "Who is talking and who gets the spotlight",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The SFU continuously ranks publishers by speaking activity. The "
                        "<strong>top-N</strong> are forwarded at high quality; tail participants "
                        "drop to L1 or are entirely paused. This is the trick that lets a "
                        "100-person webinar fit on a phone."
                    ),
                },
                {"type": "h3", "text": "Pipeline"},
                {
                    "type": "numbered",
                    "items": [
                        "Each Opus audio packet carries an <strong>RTP header extension</strong> with audio level (dBov, 0..127), per RFC 6464",
                        "SFU reads the header without decrypting the payload (E2EE-safe)",
                        "Per publisher, maintain a 200 ms moving-average energy and a 2 s short-term average",
                        "Apply hysteresis: a participant becomes 'active' only after ≥3 consecutive frames above threshold; loses it after ≥10 frames below",
                        "Rank publishers by smoothed energy → emit <code>active_speaker</code> event over signaling",
                        "Layer selector boosts top-N by one simulcast layer; tail beyond top-9 gets L1 only",
                    ],
                },
                {"type": "h3", "text": "VAD / Smoothing Algorithm"},
                {
                    "type": "code",
                    "text": (
                        "# Per publisher, called on every audio RTP packet (every 20 ms):\n"
                        "ALPHA_FAST = 0.3   # 200 ms EMA\n"
                        "ALPHA_SLOW = 0.05  # 2 s EMA\n"
                        "ENTER_DB   = -40   # dBov threshold to enter speaking\n"
                        "EXIT_DB    = -50   # dBov threshold to leave speaking\n"
                        "ENTER_FRAMES = 3\n"
                        "EXIT_FRAMES  = 10\n"
                        "\n"
                        "def on_audio_packet(pub, lvl_dbov):\n"
                        "    pub.fast = ALPHA_FAST * lvl_dbov + (1 - ALPHA_FAST) * pub.fast\n"
                        "    pub.slow = ALPHA_SLOW * lvl_dbov + (1 - ALPHA_SLOW) * pub.slow\n"
                        "\n"
                        "    if not pub.speaking and pub.fast > ENTER_DB:\n"
                        "        pub.streak_in += 1; pub.streak_out = 0\n"
                        "        if pub.streak_in >= ENTER_FRAMES:\n"
                        "            pub.speaking = True\n"
                        "            emit('active_speaker_on', pub.id)\n"
                        "    elif pub.speaking and pub.fast < EXIT_DB:\n"
                        "        pub.streak_out += 1; pub.streak_in = 0\n"
                        "        if pub.streak_out >= EXIT_FRAMES:\n"
                        "            pub.speaking = False\n"
                        "            emit('active_speaker_off', pub.id)\n"
                        "\n"
                        "def rank_top_n(publishers, n=9):\n"
                        "    # Use slow EMA for stable ranking, fast EMA as tiebreaker\n"
                        "    return sorted(publishers,\n"
                        "                  key=lambda p: (p.slow, p.fast),\n"
                        "                  reverse=True)[:n]"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why audio energy and not full ML?",
                    "body": (
                        "The audio-level header extension is delivered without decoding or "
                        "decrypting Opus, so a single SFU core can rank thousands of speakers in "
                        "real time. ML-based VAD adds CPU and breaks E2EE. Energy + hysteresis "
                        "gets &gt; 95% of the benefit at &lt; 1% of the cost."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Recording (Phantom Participant)",
            "subtitle": "Server-side composer to GCS",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Cloud recording is implemented as a <strong>headless WebRTC client</strong> "
                        "that joins the call like any other participant. It subscribes to all "
                        "publishers, composes them into a single 1080p frame using FFmpeg + "
                        "libwebrtc, and writes a fragmented MP4 to GCS in 10-second chunks."
                    ),
                },
                {"type": "h3", "text": "Composer Pipeline"},
                {
                    "type": "numbered",
                    "items": [
                        "Host clicks <strong>Record</strong> → signaling sets <code>recording=true</code> in Spanner and notifies all participants (consent banner)",
                        "Recording orchestrator spawns a <strong>composer pod</strong> in the same region as the SFU",
                        "Composer joins the room as a phantom participant (special role <code>recorder</code>); SFU forwards <strong>all</strong> publishers' L3 layers to it",
                        "Composer decodes each stream, lays them out (gallery / spotlight / sidebar+screenshare) on a 1920×1080 canvas at 30 fps",
                        "Mixes all audio streams (Opus → PCM → mix → AAC)",
                        "Encodes composite to H.264 + AAC; writes <strong>fMP4 segments</strong> (10 s) to GCS via resumable upload",
                        "On call end (or 12 h hard cap): finalizes manifest, transcodes to HLS, generates thumbnails, runs DLP scan, emails owner the share link",
                    ],
                },
                {"type": "h3", "text": "Layout Modes"},
                {
                    "type": "table",
                    "headers": ["Layout", "Trigger", "Composition"],
                    "rows": [
                        ["Active speaker", "Default 1-on-1 / small calls", "Active speaker fullscreen, others as PiP strip"],
                        ["Gallery", "User toggle, &lt;= 25 ppl", "Equal-size grid; pads with avatar tiles for muted video"],
                        ["Spotlight", "Host pins someone", "Fixed pin fullscreen, others ignored"],
                        ["Screenshare", "Anyone shares screen", "Screen at 80%, presenter inset at 20%"],
                    ],
                },
                {"type": "h3", "text": "Storage Layout"},
                {
                    "type": "code",
                    "text": (
                        "gs://meet-recordings/{tenant_id}/{year}/{month}/{day}/\n"
                        "    {meeting_id}/\n"
                        "        manifest.m3u8           # HLS top-level\n"
                        "        video/seg-00000.m4s     # 10 s fMP4 segments\n"
                        "        video/seg-00001.m4s\n"
                        "        captions.vtt            # WebVTT timed text\n"
                        "        chat.jsonl              # chat replay\n"
                        "        thumbnail.jpg\n"
                        "        metadata.json           # roster, duration, host\n\n"
                        "Lifecycle: Standard 30 days -> Nearline 60 days -> Coldline 1 yr -> delete."
                    ),
                },
            ],
        },
        # ---- 10 -----------------------------------------------------
        {
            "num": "10",
            "title": "Live Captions & Translation",
            "subtitle": "Streaming ASR over the data channel",
            "blocks": [
                {"type": "h3", "text": "Architecture"},
                {
                    "type": "bullets",
                    "items": [
                        "ASR service joins as a phantom <strong>audio-only</strong> subscriber per active speaker (top-3)",
                        "Audio fans out from SFU at 16 kHz mono (downsampled from Opus); ~32 kbps per speaker",
                        "Streaming model: chunked 100 ms frames into a Conformer-Transducer; emits partial + final tokens",
                        "Captions posted back to signaling: <code>{ ts, speaker_id, text, is_final }</code>",
                        "Signaling broadcasts captions to participants via <strong>WebRTC data channel</strong> (in-order, reliable)",
                        "Client renders bottom-third overlay; finalized lines are appended to the recording's WebVTT track",
                    ],
                },
                {"type": "h3", "text": "Translation Path"},
                {
                    "type": "bullets",
                    "items": [
                        "Each finalized caption goes through NMT (neural machine translation) for the participant's preferred locale",
                        "Cache by (source_lang, target_lang, text-hash) to avoid redundant translation cost",
                        "Per-participant subscription: <code>preferred_caption_lang = 'es-ES'</code> in JOIN",
                    ],
                },
                {"type": "h3", "text": "Latency Budget"},
                {
                    "type": "table",
                    "headers": ["Stage", "Budget"],
                    "rows": [
                        ["Audio packet → SFU → ASR", "~30 ms"],
                        ["Streaming ASR (partial token)", "~150 ms"],
                        ["NMT (when enabled)", "~80 ms"],
                        ["Data channel back to client", "~30 ms"],
                        ["Total caption-on-screen delay", "&lt; 300 ms partial; &lt; 800 ms final"],
                    ],
                },
            ],
        },
        # ---- 11 -----------------------------------------------------
        {
            "num": "11",
            "title": "Adaptive Streaming & Congestion Control",
            "subtitle": "Surviving the public internet",
            "blocks": [
                {"type": "h3", "text": "TWCC + GCC Loop"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>TWCC (Transport-Wide Congestion Control):</strong> receiver feeds back per-packet arrival times to sender",
                        "<strong>GCC (Google Congestion Control):</strong> sender estimates available bandwidth from one-way-delay gradient + loss",
                        "Update period: ~100 ms; bandwidth estimate fed into encoder rate control and simulcast layer activation",
                        "Probe packets: short bursts of padding to test for headroom without disrupting media",
                    ],
                },
                {"type": "h3", "text": "Loss Recovery"},
                {
                    "type": "table",
                    "headers": ["Mechanism", "Use", "Cost"],
                    "rows": [
                        ["NACK", "Retransmit lost RTP packet", "1 RTT extra latency; cheap if RTT &lt; 50 ms"],
                        ["FEC (ULPFEC, FlexFEC)", "Forward-error-correction parity", "10–30% bandwidth overhead"],
                        ["RED for audio", "Bundle prior frames with current", "Fixed +30% audio BW; instant recovery"],
                        ["PLI / FIR", "Force keyframe after burst loss", "Big spike (~50 KB); use sparingly"],
                        ["Jitter buffer", "Reorder + smooth playout", "Adds 20–80 ms"],
                    ],
                },
                {"type": "h3", "text": "Adaptation Ladder"},
                {
                    "type": "numbered",
                    "items": [
                        "Loss &lt; 2%, BW healthy → keep all 3 simulcast layers; receivers pick freely",
                        "Loss 2–5% → enable FEC on audio; receivers downgrade to L2 if budget tight",
                        "Loss 5–10% → drop L3 layer entirely (sender stops encoding it); receivers max at L2",
                        "Loss &gt; 10% or BW &lt; 200 kbps → audio-only mode; pause video encoder",
                        "BW recovers → walk back up after 5 s of clean stats",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Audio over Video, Always",
                    "body": (
                        "When the link degrades, prioritize audio packets ruthlessly. A frozen "
                        "video tile is acceptable; a chopped-up word is not. SFU marks audio "
                        "with higher DSCP and skips video first under egress pressure."
                    ),
                },
            ],
        },
        # ---- 12 -----------------------------------------------------
        {
            "num": "12",
            "title": "Scalability & Global Distribution",
            "subtitle": "Cascading SFUs across regions",
            "blocks": [
                {"type": "h3", "text": "Edge SFU Selection"},
                {
                    "type": "bullets",
                    "items": [
                        "On JOIN, signaling resolves nearest SFU pod via GeoDNS + RTT probe",
                        "Anycast TURN ensures ICE candidates point at the closest relay",
                        "Pod has soft cap of 5K sessions, hard cap of 7K; signaling rebalances under 80% utilisation",
                    ],
                },
                {"type": "h3", "text": "Cross-Region Cascading"},
                {
                    "type": "para",
                    "text": (
                        "When participants are spread across regions, attaching them all to a "
                        "single SFU forces transatlantic uplinks. Instead, each region runs a "
                        "local edge SFU and the SFUs <strong>cascade</strong> via a private "
                        "backbone. Each publisher's stream traverses any inter-region link "
                        "<strong>at most once</strong>, regardless of how many subscribers in "
                        "that remote region."
                    ),
                },
                {"type": "h3", "text": "Capacity Planning"},
                {
                    "type": "bullets",
                    "items": [
                        "Per SFU pod: ~5K participants peak, ~15 Gbps egress",
                        "Per region: 600–800 pods → ~3M participants",
                        "30 regions → ~100M global concurrent",
                        "Recording composers are a separate pool: ~200 per region (fewer record than view)",
                        "ASR pods autoscale per-language; English dominates ~60%",
                    ],
                },
                {"type": "h3", "text": "Why Spanner for Room State"},
                {
                    "type": "bullets",
                    "items": [
                        "Strong consistency on roster join/leave (host kicks, lobby admit)",
                        "Multi-region writes for follow-the-host migration when host changes region",
                        "Interleaved tables: participants live under their room, single-row read for full roster",
                        "Time-travel reads support post-mortem reconstruction of the join graph",
                    ],
                },
            ],
        },
        # ---- 13 -----------------------------------------------------
        {
            "num": "13",
            "title": "Comparison: Meet vs Zoom vs Teams",
            "subtitle": "Where the products differ",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Aspect", "Google Meet", "Zoom", "Microsoft Teams"],
                    "rows": [
                        ["Topology", "SFU + simulcast (VP9/AV1)", "Hybrid SFU (proprietary)", "SFU (Skype stack roots)"],
                        ["Browser path", "First-class WebRTC", "WebRTC (recent); native preferred", "WebRTC; native preferred"],
                        ["Max participants", "1000 active video", "1000 active; 10K webinar", "1000 active; 20K live event"],
                        ["E2EE", "Optional, &lt;= 200 ppl", "Optional, all sizes (since 2020)", "Optional 1-on-1 only"],
                        ["Recording", "GCS, server composed", "Cloud or local; server composed", "OneDrive/Stream; server composed"],
                        ["Captions", "Streaming Conformer ASR; 30+ langs", "On-device + cloud ASR", "Azure Cognitive Services ASR"],
                        ["Codec preference", "VP9-SVC then AV1", "H.264 SVC then VP8", "H.264 SVC"],
                    ],
                },
                {"type": "h3", "text": "SDP vs JSEP"},
                {
                    "type": "table",
                    "headers": ["Spec", "Role", "Format"],
                    "rows": [
                        ["SDP (RFC 4566)", "Describes a media session: codecs, IPs, ports, ICE", "Plain-text, line-oriented (m=, a=, c=)"],
                        ["JSEP (RFC 8829)", "JS API contract: createOffer / createAnswer / setLocalDescription", "JS objects wrapping SDP strings"],
                        ["Trickle ICE (RFC 8838)", "Stream ICE candidates as discovered", "Per-candidate JSON over signaling"],
                        ["BUNDLE / RTCP-MUX", "Multiplex audio+video on one transport", "SDP attributes a=group:BUNDLE"],
                    ],
                },
            ],
        },
        # ---- 14 -----------------------------------------------------
        {
            "num": "14",
            "title": "Failure Modes & Recovery",
            "subtitle": "What can go wrong and how we cope",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["SFU pod dies",
                         "All sessions on that pod drop",
                         "Health check + RTP heartbeat",
                         "Signaling triggers ICE restart on clients; reassigns to neighbor pod within 5 s"],
                        ["Region outage",
                         "All edge SFUs in region down",
                         "Anycast withdrawal, GCLB alarms",
                         "GeoDNS reroutes to next-nearest region; cascade links absorb traffic"],
                        ["TURN saturation",
                         "Symmetric-NAT clients can't connect",
                         "Allocation failure rate alarm",
                         "Autoscale TURN; downgrade non-essential clients to relay-via-SFU only"],
                        ["Bandwidth drop on receiver",
                         "Frozen video, dropped audio",
                         "TWCC reports, NACK storm",
                         "Layer downgrade L3→L2→L1; eventually audio-only"],
                        ["Encoder CPU pegged on sender",
                         "Sender drops simulcast layers",
                         "client stats getStats()",
                         "Disable L3 layer; reduce framerate to 15 fps"],
                        ["Recording composer crash",
                         "Recording gap",
                         "Heartbeat to orchestrator",
                         "Restart pod; resume from last fMP4 segment boundary"],
                        ["ASR backend slow",
                         "Captions lag",
                         "End-to-end caption latency p99",
                         "Drop to partial-only mode; queue NMT translations"],
                        ["Signaling WS drops",
                         "Roster/control lost; media still flows briefly",
                         "WS heartbeat",
                         "Client reconnects with session token; resumes without re-negotiating SRTP keys"],
                    ],
                },
                {"type": "h3", "text": "Disaster Recovery"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>RTO:</strong> &lt; 30 s for SFU pod failover; &lt; 5 min for region failover",
                        "<strong>RPO:</strong> 0 for live media (calls just continue); &lt; 10 s of recording lost on composer restart",
                        "<strong>Spanner:</strong> multi-region synchronous; survives full region loss with no data loss",
                        "<strong>Recordings:</strong> dual-region GCS bucket; checksums verified before original deletion",
                    ],
                },
            ],
        },
        # ---- 15 -----------------------------------------------------
        {
            "num": "15",
            "title": "Design Trade-offs",
            "subtitle": "Decisions and rationale",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Decision", "Choice", "Trade-off"],
                    "rows": [
                        ["Topology",
                         "SFU (mesh for 2 ppl)",
                         "Server cost vs uplink fairness. P2P preserves privacy + zero server but explodes O(N²); SFU adds a relay but linear uplink."],
                        ["Adaptation",
                         "Simulcast 3 layers",
                         "3× sender CPU vs server transcoding cost. Simulcast wastes ~25% sender CPU; transcoding would cost 100× more in GPUs."],
                        ["E2EE",
                         "Optional, off by default",
                         "Privacy vs feature set. E2EE breaks server-side recording, captions, noise cancellation, dial-in. Off by default keeps the suite usable."],
                        ["Recording quality",
                         "1080p composed",
                         "Storage / compute vs fidelity. 4K would 4× storage with marginal viewer benefit; 720p saves 30% but looks dated for screen-share."],
                        ["Region pinning",
                         "Pin to host region",
                         "Latency vs cost. Pinning to host minimizes inter-region cascade fees; worse for participants on the far side. Cascading limits damage."],
                        ["Active-speaker rank",
                         "Audio energy + hysteresis",
                         "Simplicity vs accuracy. ML VAD is ~3% better but breaks E2EE and 10× more CPU."],
                        ["Captions",
                         "Server-side streaming ASR",
                         "Latency + privacy vs accuracy + translation. On-device works for English-only; server-side needed for translation."],
                        ["Signaling transport",
                         "WebSocket",
                         "Long-lived TCP vs ad-hoc HTTP. WS keeps state, handles trickle ICE; long-poll fallback for restrictive networks."],
                    ],
                },
            ],
        },
        # ---- 16 -----------------------------------------------------
        {
            "num": "16",
            "title": "Interview Playbook",
            "subtitle": "How to present this",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Real-time media is a popular interview because it forces you to talk "
                        "about <strong>networking</strong>, <strong>codecs</strong>, "
                        "<strong>topology</strong>, and <strong>cost</strong> simultaneously. "
                        "Anchor the conversation around the topology choice — that decision "
                        "drives almost every other answer."
                    ),
                },
                {"type": "h3", "text": "45-Minute Interview Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (2 min):</strong> clarify scale (100M concurrent), call shape (4 ppl × 30 min), browser-first, recording, captions, E2EE optional",
                        "<strong>Capacity (5 min):</strong> 10M calls/day, 40M sessions, ~833K avg / 100M peak; 20K SFUs across 30 regions",
                        "<strong>Topology (8 min):</strong> Mesh vs MCU vs SFU; defend SFU + simulcast; mention mesh-for-2",
                        "<strong>Signaling vs media (5 min):</strong> WebSocket SDP/ICE control plane; UDP/SRTP media plane; TURN for NAT",
                        "<strong>Adaptive streaming (8 min):</strong> simulcast L1/L2/L3, layer selection per receiver, TWCC + GCC, FEC under loss",
                        "<strong>Active speaker (5 min):</strong> RTP audio-level extension, EMA + hysteresis, top-N forwarding",
                        "<strong>Recording + captions (5 min):</strong> phantom participant for both; FFmpeg compose to GCS; ASR over data channel",
                        "<strong>Failures + trade-offs (7 min):</strong> SFU pod failover, region cascade, BW drop ladder; E2EE-vs-features call-out",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "“SFU forwards, MCU mixes” — one sentence that locks in the topology choice",
                        "“Simulcast lets each receiver pick its own layer” — explains adaptation",
                        "“Active speaker is just RTP audio-level + hysteresis” — shows you know the protocol",
                        "“Recording is a phantom participant” — elegant reuse of the same subscribe path",
                        "“Cascade SFUs across regions, not single global SFU” — shows global awareness",
                        "“Audio over video, always” — cite DSCP marking and FEC/RED",
                        "“E2EE breaks recording and ASR” — shows you understand product trade-offs",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why not WebTransport / QUIC for media?</strong> A: Coming, but RTP/SRTP over UDP has 20 yrs of NAT/middlebox compatibility and bespoke congestion control (GCC/TWCC). QUIC datagram is a likely future, currently used for some Meet experiments.",
                        "<strong>Q: How do you keep latency &lt; 150 ms with the SFU in the path?</strong> A: SFU adds ~5 ms forwarding; the bulk is encoder/decoder + jitter buffer. Edge SFUs sit in the same metro as users, and the only inter-region hop is a single cascade link.",
                        "<strong>Q: How does mute / camera off propagate?</strong> A: Sender stops the encoder and announces state via signaling; SFU stops forwarding that SSRC and broadcasts a 'video paused' event. Receivers render the avatar tile.",
                        "<strong>Q: How do you handle 10K-person webinars?</strong> A: Cascade through a tree of SFUs; only top-N speakers travel as full streams, the rest are audio+thumbnail; record once at root and stream HLS to view-only audience.",
                        "<strong>Q: ICE keeps failing for some users — what now?</strong> A: Force TURN-relay (UDP 443, then TCP 443, then TLS) so the connection looks like HTTPS to corporate firewalls.",
                        "<strong>Q: What if Spanner hiccups?</strong> A: Live calls don't depend on Spanner per-frame; only join/leave does. We can serve in-progress calls from cached SFU state for several minutes; new joins fail with retry.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "100M concurrent peak &nbsp;·&nbsp; 10M calls/day &nbsp;·&nbsp; "
                        "20K SFU boxes &nbsp;·&nbsp; 30 regions &nbsp;·&nbsp; "
                        "L1 150 kbps / L2 500 kbps / L3 1.5 Mbps &nbsp;·&nbsp; "
                        "Top-9 active speakers &nbsp;·&nbsp; "
                        "p50 mouth-to-ear &lt; 150 ms &nbsp;·&nbsp; "
                        "Recording 15 MB/min."
                    ),
                },
            ],
        },
    ],
}
