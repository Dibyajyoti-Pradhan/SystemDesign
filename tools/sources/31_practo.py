"""Source for `31 - Practo.pdf` — doctor appointment + telemedicine platform."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Practo",
    "subtitle": "doctor discovery, appointment scheduling, video consultations, e-prescriptions, and medical records",
    "read_time": "~ 45 minute read",
    "short_title": "Design Practo",
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
                        "Design <strong>Practo</strong>: a healthcare booking + telemedicine "
                        "platform. Patients <strong>discover</strong> doctors by specialty, "
                        "city, language, and fee; <strong>book</strong> in-person or video "
                        "appointments against a doctor's calendar; have a 1-on-1 (occasionally "
                        "3-way) <strong>video consultation</strong>; receive a signed "
                        "<strong>e-prescription</strong>; and store encrypted "
                        "<strong>medical records</strong> they can share with future doctors. "
                        "All of this must comply with HIPAA / India DPDP."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Scale?", "~30M registered users, ~100K verified doctors"],
                        ["Volume?", "~500K appointments/day, ~30K search QPS"],
                        ["Video peak?", "~5K concurrent consultations at evening peak (7–10 PM)"],
                        ["Discovery axes?", "Specialty, city/locality, availability, language, fee, rating"],
                        ["Calendar?", "Doctor exposes slots; sync with their Google/Outlook iCal"],
                        ["Booking model?", "Auto-confirm or doctor-approval; cancellation &amp; no-show flows"],
                        ["Video?", "WebRTC; 1-on-1 normal, 3-way for family; SFU only for group"],
                        ["Recording?", "Optional, consent-gated, encrypted at rest"],
                        ["Prescriptions?", "Signed PDF, integrate with pharmacy networks via FHIR"],
                        ["Records?", "Patient-owned, per-record ACL, encrypted"],
                        ["Payments?", "Hold at booking, capture after consult, saga refunds"],
                        ["Compliance?", "HIPAA (US), DPDP (India), region-pinned data"],
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
                        ["Doctor discovery", "Filter by specialty, city/locality (S2/H3), language, fee, rating; sort by availability"],
                        ["Calendar &amp; slots", "Doctors expose 15-min slots; sync from Google/Outlook iCal; conflict detection"],
                        ["Booking", "Hold slot 5 min, take payment, confirm; auto-confirm or doctor approval"],
                        ["Reminders", "Push/SMS at 24h and 1h before appointment"],
                        ["Video consult", "WebRTC 1-on-1; SFU for 3-way; reconnect on drop within 60s"],
                        ["E-prescriptions", "Signed PDF; push to chosen pharmacy via FHIR/local API"],
                        ["Medical records", "Encrypted at rest; ACL — patient grants doctors read access"],
                        ["Payments", "Hold-then-capture; saga refund for in-policy cancellations"],
                        ["Reviews", "Post-consultation review; visible only after both parties closed"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Search latency", "p95 &lt; 250 ms; geo + full-text combined"],
                        ["Booking latency", "p95 &lt; 800 ms (includes payment auth)"],
                        ["Video setup", "&lt; 3 sec to first frame; &lt; 60 sec auto-reconnect"],
                        ["Availability", "99.95% for booking; 99.9% for video"],
                        ["Consistency", "<strong>Strong</strong> on slot booking; eventual on search index"],
                        ["Compliance", "HIPAA-eligible AWS, DPDP, audit log every PHI read"],
                        ["Encryption", "TLS 1.3 in transit, AES-256-GCM at rest, KMS-managed keys"],
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
                        "Users: <strong>30M</strong> registered, ~3M DAU (10%)",
                        "Doctors: <strong>100K</strong> verified, ~40K active daily",
                        "Appointments: <strong>500K/day</strong> = 5.8/sec avg, ~30/sec peak (factor 5)",
                        "Search QPS: <strong>30K/sec</strong> (discovery dominates traffic)",
                        "Concurrent video: <strong>5K</strong> at evening peak (each ~25 min, ~1.5 Mbps)",
                    ],
                },
                {"type": "h3", "text": "Bandwidth"},
                {
                    "type": "bullets",
                    "items": [
                        "Video: 5K calls × 1.5 Mbps × 2 (both legs, P2P) = <strong>15 Gbps</strong> peer-to-peer",
                        "TURN relay (~20% NAT-failed): 1K × 3 Mbps = <strong>3 Gbps</strong> on TURN",
                        "Recording (10% opt-in): 500 streams × 0.5 Mbps = <strong>250 Mbps</strong> ingest",
                    ],
                },
                {"type": "h3", "text": "Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "Appointment row: ~1 KB → 500K/day × 365 × 1 KB = <strong>180 GB/yr</strong>",
                        "Slots: 100K doctors × 30 slots/day × 365 × 200 B = <strong>220 GB/yr</strong> (TTL'd)",
                        "Prescriptions (PDF avg 50 KB): 500K/day × 50 KB = <strong>25 GB/day = 9 TB/yr</strong>",
                        "Medical records (avg 200 KB encrypted blob): ~5M new/yr × 200 KB = <strong>1 TB/yr</strong>",
                        "Recordings (10% × 25 min × 200 MB): 50K/day × 200 MB = <strong>10 TB/day</strong> if all opt in (rare; budget 1 TB/day)",
                    ],
                },
                {"type": "h3", "text": "Cache"},
                {
                    "type": "bullets",
                    "items": [
                        "Hot calendars (next 7 days for 40K active doctors): ~40K × 7 × 30 slots × 200 B ≈ <strong>1.7 GB Redis</strong>",
                        "Search results LRU (top 5K specialty/city pairs × 50 doctors × 1 KB): <strong>~250 MB</strong>",
                        "Doctor profile cache (100K × 4 KB): <strong>~400 MB</strong>",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "30M users &nbsp;·&nbsp; 100K doctors &nbsp;·&nbsp; "
                        "500K appointments/day &nbsp;·&nbsp; 5K concurrent video "
                        "&nbsp;·&nbsp; 30K search QPS &nbsp;·&nbsp; 15 Gbps P2P "
                        "video &nbsp;·&nbsp; ~1.7 GB hot calendar cache."
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
                        "Three apps (Patient, Doctor, Web) hit a single <strong>API "
                        "Gateway</strong>, which fans out to bounded-context services: "
                        "Search/Discovery, Booking, Calendar Sync, Video, Records, "
                        "Pharmacy, Payment, and Notifications. Each service owns its data; "
                        "Postgres holds bookings, Redis caches hot calendars, Elasticsearch "
                        "powers search, encrypted object storage holds records and "
                        "recordings, and Kafka streams cross-service events."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Patient/Doctor/Web → API GW → bounded-context services → polyglot data tier and external integrations.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=9, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Clients"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Patient [label="Patient app", fillcolor="#dbe6fb"];
        Doctor  [label="Doctor app",  fillcolor="#dbe6fb"];
        Web     [label="Web",         fillcolor="#dbe6fb"];
    }
    GW [label="API Gateway\n(authn, ratelimit)", fillcolor="#cbeedf"];

    subgraph cluster_svc {
        label="Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        Search   [label="Search /\nDiscovery",     fillcolor="#fff2c9"];
        Booking  [label="Booking",                 fillcolor="#fff2c9"];
        CalSync  [label="Calendar\nSync",          fillcolor="#fff2c9"];
        Video    [label="Video\n(WebRTC + SFU)",   fillcolor="#fff2c9"];
        Records  [label="Medical\nRecords",        fillcolor="#fff2c9"];
        Rx       [label="Pharmacy\nIntegration",   fillcolor="#fff2c9"];
        Pay      [label="Payment",                 fillcolor="#fff2c9"];
        Notif    [label="Notifications",           fillcolor="#fff2c9"];
    }

    subgraph cluster_data {
        label="Data tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        PG    [label="Postgres\n(bookings, slots)", fillcolor="#ead7fb"];
        Redis [label="Redis\n(hot calendars)",      fillcolor="#ead7fb"];
        ES    [label="Elasticsearch\n(doctor index)", fillcolor="#ead7fb"];
        Obj   [label="Object store\n(records, Rx, recordings,\nencrypted)", fillcolor="#ead7fb"];
        Kafka [label="Kafka\n(events)",             fillcolor="#fbd7c5"];
    }

    subgraph cluster_ext {
        label="External"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        PG_ext [label="Payment GW\n(Razorpay/Stripe)", fillcolor="#cbeedf"];
        Pharm  [label="Pharmacy\nnetworks (FHIR)",     fillcolor="#cbeedf"];
        ICAL   [label="Google /\nOutlook iCal",        fillcolor="#cbeedf"];
    }

    Patient -> GW; Doctor -> GW; Web -> GW;
    GW -> Search; GW -> Booking; GW -> Video; GW -> Records; GW -> Pay;

    Search  -> ES;
    Booking -> PG; Booking -> Redis; Booking -> Kafka;
    CalSync -> ICAL [dir=both]; CalSync -> PG; CalSync -> Redis;
    Video   -> Obj  [label="recording"];
    Records -> Obj; Records -> Kafka;
    Rx      -> Pharm; Rx -> Obj;
    Pay     -> PG_ext; Pay -> Kafka;
    Notif   -> Kafka [dir=back, label="consume"];
}
""",
                },
                {"type": "h3", "text": "Architecture Highlights"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>API Gateway:</strong> auth (JWT + mTLS for Doctor app), rate limiting, regional routing",
                        "<strong>Search/Discovery:</strong> Elasticsearch + S2/H3 geo cells; cached top queries",
                        "<strong>Booking:</strong> owns Postgres slots/appointments; strong consistency on slot transitions",
                        "<strong>Calendar Sync:</strong> two-way iCal sync; reconciles drift every 5 min",
                        "<strong>Video:</strong> WebRTC P2P with TURN fallback; SFU only for ≥ 3 participants",
                        "<strong>Records:</strong> patient-owned blobs in encrypted object store; ACL in Postgres",
                        "<strong>Pharmacy:</strong> FHIR for international networks, REST shims for local Indian chains",
                        "<strong>Payment:</strong> hold + capture; saga compensation on cancellation",
                        "<strong>Notifications:</strong> Kafka consumer fanning out push/SMS/email",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Doctor Discovery",
            "subtitle": "Search, geo, and ranking",
            "blocks": [
                {"type": "h3", "text": "Index design"},
                {
                    "type": "bullets",
                    "items": [
                        "Elasticsearch index <code>doctors_v3</code>; one doc per doctor",
                        "Fields: name, specialty (keyword), sub_specialties, languages, fee, rating, "
                        "next_available_ts, S2 cell tokens at levels 10/12/14, location (geo_point)",
                        "Tokenization: edge n-gram on name (typeahead) + specialty synonym list",
                        "Updated by Kafka consumer when profile or availability changes (≤ 5s freshness)",
                    ],
                },
                {"type": "h3", "text": "Query path"},
                {
                    "type": "numbered",
                    "items": [
                        "Patient sends <code>{specialty=Cardiologist, city=Bangalore, lang=Hindi, max_fee=800}</code>",
                        "Gateway resolves city → S2 cell at level 10 (≈80 km²)",
                        "ES <code>bool</code>: <code>filter</code> on specialty + cell + languages + fee; "
                        "<code>sort</code> by next_available_ts then rating",
                        "Top 50 doctors → enrich with Redis profile cache → return",
                        "Cache <code>(specialty, city)</code> top 50 in Redis with 60s TTL",
                    ],
                },
                {"type": "h3", "text": "Geo-search: S2 vs H3"},
                {
                    "type": "table",
                    "headers": ["Property", "S2 (Google)", "H3 (Uber)"],
                    "rows": [
                        ["Cell shape", "Square, hierarchical", "Hexagonal, hierarchical"],
                        ["Neighbour distance", "Variable (4 vs 8)", "Uniform (6 neighbours)"],
                        ["Best for", "Range queries, ES filter", "K-nearest, ride matching"],
                        ["Choice here", "S2 — ES already supports geo_cell tokens", "—"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Pre-warm hot queries",
                    "body": (
                        "About 80% of search QPS hits ~5K (specialty, city) pairs. Materialise "
                        "their top-50 lists every 60s into Redis; queries beyond cache fall "
                        "through to ES. Cuts ES QPS from 30K to ~6K."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Doctor Calendar & iCal Sync",
            "subtitle": "Slots, drift, and conflict detection",
            "blocks": [
                {"type": "h3", "text": "Slot model"},
                {
                    "type": "bullets",
                    "items": [
                        "Each doctor exposes <strong>15-min slots</strong> per practice location",
                        "Slot row: <code>(doctor_id, start_ts, mode=in_person|video, state, version)</code>",
                        "State machine: <strong>AVAILABLE → HELD → BOOKED</strong> (or → AVAILABLE on release)",
                        "Pre-generate next 30 days; cron extends rolling window each midnight",
                    ],
                },
                {"type": "h3", "text": "External calendar sync"},
                {
                    "type": "bullets",
                    "items": [
                        "Doctor links Google/Outlook iCal; we hold a <strong>refresh token</strong>",
                        "Inbound: every 5 min, pull events; mark overlapping slots as <strong>BLOCKED</strong> "
                        "(separate state, never bookable)",
                        "Outbound: when slot becomes BOOKED, push event to doctor's external calendar via Calendar API",
                        "Drift detection: ETag mismatch → full re-sync; reconcile any orphan bookings",
                    ],
                },
                {"type": "h3", "text": "Schema"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE doctors (\n"
                        "  doctor_id     BIGINT PRIMARY KEY,\n"
                        "  full_name     TEXT NOT NULL,\n"
                        "  specialty     VARCHAR(64) NOT NULL,\n"
                        "  languages     VARCHAR(128),       -- comma list\n"
                        "  city          VARCHAR(64),\n"
                        "  s2_cell_l10   BIGINT,             -- ~80 km^2\n"
                        "  s2_cell_l12   BIGINT,             -- ~5 km^2\n"
                        "  fee_inr       INT,\n"
                        "  rating_avg    DECIMAL(2,1),\n"
                        "  ical_url      TEXT,               -- external sync\n"
                        "  ical_etag     TEXT,\n"
                        "  verified_at   TIMESTAMP\n"
                        ");\n\n"
                        "CREATE TABLE slots (\n"
                        "  slot_id     BIGINT PRIMARY KEY,\n"
                        "  doctor_id   BIGINT NOT NULL,\n"
                        "  start_ts    TIMESTAMPTZ NOT NULL,\n"
                        "  mode        VARCHAR(16) NOT NULL,         -- in_person|video\n"
                        "  state       VARCHAR(16) NOT NULL,         -- AVAILABLE|HELD|BOOKED|BLOCKED\n"
                        "  version     INT NOT NULL DEFAULT 0,       -- optimistic lock\n"
                        "  held_until  TIMESTAMPTZ,                  -- 5-min hold expiry\n"
                        "  appt_id     BIGINT,                       -- when BOOKED\n"
                        "  UNIQUE (doctor_id, start_ts)\n"
                        ");\n"
                        "CREATE INDEX idx_slot_open ON slots(doctor_id, start_ts)\n"
                        "  WHERE state IN ('AVAILABLE','HELD');\n\n"
                        "CREATE TABLE appointments (\n"
                        "  appt_id      BIGINT PRIMARY KEY,\n"
                        "  patient_id   BIGINT NOT NULL,\n"
                        "  doctor_id    BIGINT NOT NULL,\n"
                        "  slot_id      BIGINT NOT NULL UNIQUE,\n"
                        "  state        VARCHAR(16) NOT NULL,        -- REQUESTED|CONFIRMED|REMINDED|IN_PROGRESS|COMPLETED|CANCELLED|NO_SHOW\n"
                        "  payment_id   BIGINT,\n"
                        "  hold_expiry  TIMESTAMPTZ,\n"
                        "  created_at   TIMESTAMPTZ DEFAULT NOW(),\n"
                        "  updated_at   TIMESTAMPTZ\n"
                        ");"
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Appointment Lifecycle",
            "subtitle": "REQUESTED → COMPLETED",
            "blocks": [
                {"type": "h3", "text": "State machine"},
                {
                    "type": "table",
                    "headers": ["State", "Trigger", "Side-effects"],
                    "rows": [
                        ["REQUESTED", "Patient picks slot &amp; pays", "Slot HELD 5 min; payment hold"],
                        ["CONFIRMED", "Auto or doctor approves", "Payment hold persists; sync push to doctor iCal"],
                        ["REMINDED", "Cron 24h then 1h before", "Push + SMS to patient + doctor"],
                        ["IN_PROGRESS", "Either side joins video / arrives", "Start consultation timer; lock recording session"],
                        ["COMPLETED", "Doctor closes consult", "Capture payment; emit Rx-eligible event; allow review"],
                        ["FOLLOW_UP", "Optional doctor-initiated", "Free 7-day re-consult slot generated"],
                        ["CANCELLED", "Either party within policy", "Release slot; trigger refund saga"],
                        ["NO_SHOW", "Auto after 15 min", "Capture cancellation fee; release slot"],
                    ],
                },
                {"type": "h3", "text": "Cancellation policy"},
                {
                    "type": "bullets",
                    "items": [
                        "&gt; 24h before: 100% refund, slot released",
                        "2–24h before: 50% refund, slot released",
                        "&lt; 2h before: 0% refund (cancellation fee), slot released",
                        "Doctor cancels: 100% refund regardless; doctor's reliability score dinged",
                    ],
                },
                {"type": "h3", "text": "Sequence — booking"},
                {
                    "type": "diagram",
                    "caption": "Booking sequence — patient picks slot, hold + payment auth, confirm, doctor notify, calendar push.",
                    "dot": r"""
digraph G {
    rankdir=TB;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=9, color="#2e57b8", fillcolor="#dbe6fb"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    P  [label="Patient"];
    GW [label="API Gateway"];
    B  [label="Booking svc"];
    PG [label="Postgres\n(slots)"];
    PAY[label="Payment svc"];
    EXT[label="Razorpay/Stripe", fillcolor="#cbeedf"];
    K  [label="Kafka", fillcolor="#fbd7c5"];
    N  [label="Notifications"];
    C  [label="Calendar Sync"];
    EX [label="Doctor iCal", fillcolor="#cbeedf"];

    P  -> GW [label="1. POST /book {slot_id}"];
    GW -> B  [label="2. forward"];
    B  -> PG [label="3. SELECT...FOR UPDATE\n   AVAILABLE → HELD\n   held_until = now+5m"];
    PG -> B  [label="4. ok"];
    B  -> PAY[label="5. authorize hold"];
    PAY-> EXT[label="6. auth"];
    EXT-> PAY[label="7. token"];
    PAY-> B  [label="8. ok"];
    B  -> PG [label="9. HELD → BOOKED\n   create appointment"];
    B  -> K  [label="10. emit appointment.created"];
    K  -> N  [label="11. push doctor"];
    K  -> C  [label="12. push iCal event"];
    C  -> EX [label="13. POST event"];
    B  -> P  [label="14. 201 confirmed"];
}
""",
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Slot Concurrency",
            "subtitle": "Preventing double-booking",
            "blocks": [
                {"type": "h3", "text": "The problem"},
                {
                    "type": "para",
                    "text": (
                        "When two patients click the same slot within the same second, exactly "
                        "one must win. Lose-side must see <code>409 SLOT_TAKEN</code> immediately "
                        "and be offered alternatives. We compare two implementations."
                    ),
                },
                {"type": "h3", "text": "Optimistic vs pessimistic"},
                {
                    "type": "table",
                    "headers": ["Aspect", "Pessimistic (FOR UPDATE)", "Optimistic (version)"],
                    "rows": [
                        ["Lock duration", "Held until txn commits", "None — CAS at update time"],
                        ["Throughput per slot", "Serial; ~1 winner/100 ms", "Parallel attempts; one wins"],
                        ["Tail latency", "Higher under contention", "Lower; loser fast-fails"],
                        ["Deadlock risk", "Yes if multi-row", "No"],
                        ["Code complexity", "Simple", "Retry + rebuild needed"],
                        ["Best for", "Low contention, multi-row txns", "High contention single row"],
                    ],
                },
                {"type": "h3", "text": "Optimistic-lock booking algorithm"},
                {
                    "type": "code",
                    "text": (
                        "def reserve_slot(slot_id: int, patient_id: int) -> str:\n"
                        "    for attempt in range(3):\n"
                        "        # 1. Read current state + version\n"
                        "        row = db.exec(\n"
                        "            \"SELECT state, version, held_until FROM slots WHERE slot_id=%s\",\n"
                        "            slot_id).one()\n"
                        "\n"
                        "        if row.state == 'BOOKED':\n"
                        "            return 'TAKEN'\n"
                        "        if row.state == 'HELD' and row.held_until > now():\n"
                        "            return 'TAKEN'\n"
                        "\n"
                        "        # 2. Compare-and-swap on (slot_id, version)\n"
                        "        n = db.exec(\n"
                        "            \"\"\"UPDATE slots\n"
                        "                 SET state='HELD', held_until=NOW()+INTERVAL '5 min',\n"
                        "                     version=version+1\n"
                        "               WHERE slot_id=%s AND version=%s\n"
                        "                 AND state IN ('AVAILABLE','HELD')\n"
                        "                 AND (held_until IS NULL OR held_until <= NOW())\"\"\",\n"
                        "            slot_id, row.version)\n"
                        "\n"
                        "        if n == 1:\n"
                        "            return 'HELD'        # winner — proceed to payment\n"
                        "        # else: someone else won the CAS; retry\n"
                        "    return 'CONTENTION'\n"
                    ),
                },
                {"type": "h3", "text": "Hold expiry"},
                {
                    "type": "bullets",
                    "items": [
                        "Cron <strong>every 30s</strong>: <code>UPDATE slots SET state='AVAILABLE', appt_id=NULL "
                        "WHERE state='HELD' AND held_until &lt; NOW()</code>",
                        "Backstop only — happy path releases hold via payment-fail saga immediately",
                        "Hold record also TTL'd in Redis hot-calendar cache so search reflects it",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why optimistic wins here",
                    "body": (
                        "Hot doctors see ~50 concurrent attempts on a popular slot. Pessimistic "
                        "locks queue them serially through Postgres; optimistic CAS lets all "
                        "fail-fast except one, and the loser instantly retries with a different "
                        "slot. p95 booking latency drops from ~1.4s to ~600ms in our load tests."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Video Consultation",
            "subtitle": "WebRTC, SFU, and recording",
            "blocks": [
                {"type": "h3", "text": "Topology"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>1-on-1 (default):</strong> WebRTC P2P, TURN fallback for symmetric NAT (~20%)",
                        "<strong>3-way (family member):</strong> route through <strong>SFU</strong> (Selective "
                        "Forwarding Unit, e.g. mediasoup); each participant sends 1 stream, receives 2",
                        "Signalling: WebSockets to Video service; ICE candidate exchange; DTLS-SRTP keys",
                        "STUN: free, NAT discovery; TURN: relayed (egress cost) when P2P fails",
                    ],
                },
                {"type": "h3", "text": "In-house vs Twilio/Agora"},
                {
                    "type": "table",
                    "headers": ["Aspect", "In-house WebRTC + SFU", "Twilio / Agora"],
                    "rows": [
                        ["Cost @ 5K concurrent", "~$8K/mo TURN + SFU compute", "~$30–60K/mo"],
                        ["Engineering effort", "High — SFU ops, codec tuning", "Low — SDK call away"],
                        ["Compliance", "We control PHI residency", "Vendor BAA needed"],
                        ["Time-to-launch", "3–6 months", "Days"],
                        ["Choice", "Phase 2 — start with vendor, migrate hot path later", "—"],
                    ],
                },
                {"type": "h3", "text": "Mid-call network drop"},
                {
                    "type": "bullets",
                    "items": [
                        "Client detects ICE state change → reconnect window <strong>60 sec</strong>",
                        "Same room id resumed; SRTP keys reused if still valid",
                        "If &gt; 60 sec: state moves to <code>SUSPENDED</code>; doctor can reopen the session "
                        "(extends consult timer)",
                        "Bandwidth adaptation: simulcast layers; downshift to audio-only at &lt; 200 Kbps",
                    ],
                },
                {"type": "h3", "text": "Recording (consent-gated)"},
                {
                    "type": "bullets",
                    "items": [
                        "Both parties tap <strong>Consent</strong> before record button is enabled",
                        "Recorder is an extra SFU peer, mixes streams, writes WebM to S3 with <strong>SSE-KMS</strong>",
                        "Encryption key per appointment; audit-logged on every read",
                        "Default retention 90 days; patient can request earlier deletion",
                    ],
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "E-Prescriptions",
            "subtitle": "Signed PDFs and pharmacy delivery",
            "blocks": [
                {"type": "h3", "text": "Prescription flow"},
                {
                    "type": "numbered",
                    "items": [
                        "Doctor finalises Rx during/after consult: drug, dose, duration, instructions",
                        "Service generates <strong>PDF/A</strong> with QR code + Practo Rx ID",
                        "Doctor signs with their <strong>HSM-backed key</strong> (DSC in India)",
                        "PDF stored in object store (encrypted); hash anchored in Postgres for tamper detection",
                        "Patient receives signed link; can forward to chosen pharmacy",
                        "Optional: push directly to pharmacy via FHIR <code>MedicationRequest</code>",
                    ],
                },
                {"type": "h3", "text": "FHIR MedicationRequest sketch"},
                {
                    "type": "code",
                    "text": (
                        "{\n"
                        "  \"resourceType\": \"MedicationRequest\",\n"
                        "  \"id\": \"rx-39281\",\n"
                        "  \"status\": \"active\",\n"
                        "  \"intent\": \"order\",\n"
                        "  \"medicationCodeableConcept\": {\n"
                        "    \"coding\": [{ \"system\": \"http://www.nlm.nih.gov/research/umls/rxnorm\",\n"
                        "                  \"code\": \"310965\", \"display\": \"Amoxicillin 500 mg\" }]\n"
                        "  },\n"
                        "  \"subject\":   { \"reference\": \"Patient/p-12031\" },\n"
                        "  \"requester\": { \"reference\": \"Practitioner/d-9043\" },\n"
                        "  \"authoredOn\": \"2026-05-07T10:14:00Z\",\n"
                        "  \"dispenseRequest\": {\n"
                        "    \"quantity\":  { \"value\": 21, \"unit\": \"capsule\" },\n"
                        "    \"expectedSupplyDuration\": { \"value\": 7, \"unit\": \"d\" }\n"
                        "  },\n"
                        "  \"dosageInstruction\": [{\n"
                        "    \"text\": \"1 capsule three times daily after food\",\n"
                        "    \"timing\": { \"repeat\": { \"frequency\": 3, \"period\": 1, \"periodUnit\": \"d\" } }\n"
                        "  }]\n"
                        "}"
                    ),
                },
                {"type": "h3", "text": "Controlled substances"},
                {
                    "type": "bullets",
                    "items": [
                        "Schedule H/H1/X drugs require explicit doctor 2FA before signing",
                        "Audit trail: <code>(rx_id, doctor_id, patient_id, drug_code, signed_ts, ip, device_attest)</code>",
                        "Append-only log replicated to S3 Object Lock (WORM) for 5 years",
                        "Anomaly detection: same doctor signing identical Rx for &gt; 50 patients/day → flag",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Medical Records",
            "subtitle": "Patient-owned, encrypted, ACL'd",
            "blocks": [
                {"type": "h3", "text": "Storage model"},
                {
                    "type": "bullets",
                    "items": [
                        "Each record (lab report, scan, prior Rx) stored as a blob in S3 with "
                        "<strong>per-object KMS data key</strong> (envelope encryption)",
                        "Metadata in Postgres: owner (always patient), MIME, size, kms_key_id, sha256, created_at",
                        "Doctors get <strong>time-bound</strong> read access, scoped to one appointment",
                    ],
                },
                {"type": "h3", "text": "Schema"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE encrypted_records (\n"
                        "  record_id     BIGINT PRIMARY KEY,\n"
                        "  patient_id    BIGINT NOT NULL,\n"
                        "  s3_key        TEXT NOT NULL,            -- ciphertext blob\n"
                        "  kms_key_id    TEXT NOT NULL,            -- per-record DEK\n"
                        "  iv            BYTEA NOT NULL,           -- 96-bit GCM nonce\n"
                        "  sha256        BYTEA NOT NULL,           -- integrity\n"
                        "  mime          VARCHAR(64),\n"
                        "  size_bytes    BIGINT,\n"
                        "  created_at    TIMESTAMPTZ DEFAULT NOW(),\n"
                        "  redacted_at   TIMESTAMPTZ\n"
                        ");\n\n"
                        "CREATE TABLE record_grants (\n"
                        "  grant_id      BIGINT PRIMARY KEY,\n"
                        "  record_id     BIGINT NOT NULL REFERENCES encrypted_records,\n"
                        "  doctor_id     BIGINT NOT NULL,\n"
                        "  appt_id       BIGINT NOT NULL,\n"
                        "  granted_at    TIMESTAMPTZ DEFAULT NOW(),\n"
                        "  expires_at    TIMESTAMPTZ NOT NULL,     -- usually appt+24h\n"
                        "  revoked_at    TIMESTAMPTZ,\n"
                        "  UNIQUE (record_id, doctor_id, appt_id)\n"
                        ");\n\n"
                        "CREATE TABLE record_access_audit (\n"
                        "  audit_id      BIGINT PRIMARY KEY,\n"
                        "  record_id     BIGINT NOT NULL,\n"
                        "  actor_id      BIGINT NOT NULL,          -- doctor or patient\n"
                        "  actor_role    VARCHAR(16) NOT NULL,\n"
                        "  action        VARCHAR(16) NOT NULL,     -- READ|WRITE|GRANT|REVOKE\n"
                        "  ip_addr       INET,\n"
                        "  occurred_at   TIMESTAMPTZ DEFAULT NOW()\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "Read flow"},
                {
                    "type": "numbered",
                    "items": [
                        "Doctor app requests <code>GET /records/{id}</code>",
                        "Records service joins <code>encrypted_records ⨝ record_grants</code> with valid expiry",
                        "If granted: <code>kms:Decrypt(kms_key_id)</code> → DEK → fetch S3 ciphertext → decrypt → stream",
                        "Audit row written <strong>before</strong> bytes leave the service",
                        "Streamed bytes are never persisted on doctor device (DRM-style overlay)",
                    ],
                },
                {"type": "h3", "text": "Compliance"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>HIPAA:</strong> BAA with AWS, encryption at rest + in transit, audit log every PHI read",
                        "<strong>India DPDP:</strong> data fiduciary role; consent receipts; data principal rights API",
                        "<strong>EU:</strong> EU-region tenant, GDPR right-to-erasure (tombstone + delete blob)",
                        "Region-pin: <code>workspace.region</code> determines DB shard and S3 bucket; never crosses",
                    ],
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Payments & Refund Saga",
            "subtitle": "Hold → capture, compensation flows",
            "blocks": [
                {"type": "h3", "text": "Money flow"},
                {
                    "type": "numbered",
                    "items": [
                        "Booking: payment GW <strong>authorize hold</strong> for fee + platform charge",
                        "Slot booked → hold persists; reminder cron does nothing financial",
                        "Consult <strong>COMPLETED</strong> → <strong>capture</strong> the auth → settle to doctor T+2",
                        "Cancel within policy → release the auth (no money moves)",
                        "Cancel with partial refund → capture + immediate refund of refundable %",
                    ],
                },
                {"type": "h3", "text": "Saga (cancellation)"},
                {
                    "type": "bullets",
                    "items": [
                        "Step 1: <code>appointment.cancelled</code> emitted",
                        "Step 2: Booking releases slot (state → AVAILABLE, version++)",
                        "Step 3: Calendar Sync deletes external iCal event",
                        "Step 4: Payment computes refund % per policy &amp; calls payment GW <code>refund</code>",
                        "Step 5: Notifications fire to patient + doctor",
                        "Each step idempotent on <code>(appt_id, step)</code>; failures retried with backoff",
                    ],
                },
                {"type": "h3", "text": "Idempotency"},
                {
                    "type": "bullets",
                    "items": [
                        "Every external call carries <code>Idempotency-Key = sha256(appt_id + step + attempt)</code>",
                        "Payment GW dedupes for 24h; we dedupe forever via Postgres <code>processed_steps</code>",
                        "Patient retries (double-tap book) protected with client-supplied request id",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Hold-then-no-capture leak",
                    "body": (
                        "If consult never starts and we never explicitly cancel, the auth holds "
                        "the patient's bank funds. A daily reconciliation job inspects "
                        "<code>state IN ('REQUESTED','CONFIRMED')</code> with start_ts &lt; now − 24h, "
                        "auto-cancels them, and triggers the saga."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Comparison: Practo vs Zocdoc vs DocOnline",
            "subtitle": "How others solve it",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Aspect", "Practo (this design)", "Zocdoc", "DocOnline"],
                    "rows": [
                        ["Primary market", "India + SEA", "US", "India tier-2/3 + insurance"],
                        ["Discovery", "ES + S2 geo", "ES + insurance filter", "Phone-first, basic search"],
                        ["Calendar", "iCal 2-way sync", "Pulls from doctor EHR", "Practo-owned only"],
                        ["Slot lock", "Optimistic CAS", "Pessimistic + queue", "Pessimistic"],
                        ["Video stack", "WebRTC + SFU (in-house phase 2)", "Vendor (Twilio)", "Vendor (Agora)"],
                        ["E-prescriptions", "FHIR + DSC sign", "Surescripts (US-specific)", "PDF only"],
                        ["Records", "Patient-owned, ACL'd", "Insurance-tied", "Limited"],
                        ["Compliance", "HIPAA + DPDP", "HIPAA only", "DPDP"],
                        ["Strength", "Ecosystem breadth", "Insurance verification", "Affordability"],
                    ],
                },
                {"type": "h3", "text": "Slot lock: pessimistic vs optimistic — recap"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Pessimistic</strong> (Zocdoc-style): <code>SELECT FOR UPDATE</code>; correct, "
                        "simpler, but contention serialises hot slots",
                        "<strong>Optimistic</strong> (this design): version CAS; better tail latency under "
                        "contention; loser fast-fails without holding row locks",
                        "Hybrid is possible — pessimistic with <code>SKIP LOCKED</code> for the cleanup job, "
                        "optimistic for user-facing booking",
                    ],
                },
                {"type": "h3", "text": "Video: build vs buy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Phase 1:</strong> Twilio Programmable Video — fastest to launch, BAA covers HIPAA",
                        "<strong>Phase 2:</strong> in-house mediasoup SFU when concurrent &gt; 10K (cost crossover)",
                        "<strong>Always:</strong> own signalling and room state — never give vendor your call graph",
                    ],
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Failure Modes & Trade-offs",
            "subtitle": "What goes wrong and what we accept",
            "blocks": [
                {"type": "h3", "text": "Failure modes"},
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["Doctor calendar drift",
                         "External booking we miss → double-book",
                         "ETag mismatch on iCal poll",
                         "5-min reconciliation; conflict resolved in patient's favour with apology + free reschedule"],
                        ["Double-book under contention",
                         "Two HELDs, only one BOOKED",
                         "UNIQUE(slot_id) violation in appointments",
                         "Optimistic CAS + version; loser shown alternatives in &lt; 200 ms"],
                        ["Video drop mid-consult",
                         "Either party loses connection",
                         "ICE state change",
                         "60-sec reconnect window; same room id; SUSPENDED state if longer"],
                        ["Payment fail post-hold",
                         "Slot HELD, no auth → orphan",
                         "Saga step timeout",
                         "Compensating release — slot back to AVAILABLE, hold record TTL'd"],
                        ["Pharmacy API down",
                         "Rx not delivered electronically",
                         "5xx from FHIR endpoint",
                         "Fall back to signed PDF link; queue Rx for retry; SMS to patient"],
                        ["KMS unavailable",
                         "Records cannot be decrypted",
                         "kms:Decrypt 5xx",
                         "Multi-region KMS aliases; cached DEKs for 5 min in-memory only"],
                        ["ES cluster down",
                         "Discovery degrades",
                         "Health probe",
                         "Serve from Redis prewarmed top queries; show 'limited search' banner"],
                    ],
                },
                {"type": "h3", "text": "Trade-offs"},
                {
                    "type": "table",
                    "headers": ["Decision", "Choice", "Why this side"],
                    "rows": [
                        ["Slot consistency",
                         "Strong (CP)",
                         "Double-booking is unacceptable; we'd rather show 503 than confirm a stolen slot"],
                        ["Search consistency",
                         "Eventual (AP)",
                         "5-sec stale availability is fine; the hold check on book is the source of truth"],
                        ["Video transport",
                         "In-app WebRTC, not WhatsApp link",
                         "Compliance + recording control + identity verification"],
                        ["Records depth",
                         "Minimal record store, not full EHR",
                         "EHR is a 5-year project; minimal store ships in 6 months and covers 80% of needs"],
                        ["Calendar source-of-truth",
                         "Practo for booked appts, doctor's iCal for everything else",
                         "Two-way sync gives us authority over our own bookings, respects doctor's existing workflow"],
                        ["Build vs buy video",
                         "Buy first, build hot path later",
                         "Cost crossover at ~10K concurrent; before that, vendor BAA + speed wins"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Patient safety overrides everything",
                    "body": (
                        "If the system is uncertain whether a payment was captured, default to "
                        "letting the consult happen and reconcile money later. Never block a "
                        "scheduled medical interaction on a payment ambiguity."
                    ),
                },
            ],
        },
        # ---- 15 ------------------------------------------------------
        {
            "num": "15",
            "title": "Interview Playbook",
            "subtitle": "How to present this in 45 minutes",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Practo blends three known sub-problems — search, slot booking, and "
                        "real-time video — plus the hard constraint of medical compliance. "
                        "Lead with the slot concurrency story and the video build/buy decision; "
                        "those are where senior signal lives."
                    ),
                },
                {"type": "h3", "text": "45-Minute Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (3 min):</strong> clarify functional set: discovery, booking, video, Rx, records, payments",
                        "<strong>Capacity (4 min):</strong> 30M users, 100K doctors, 500K appts/day, 5K concurrent video, 30K search QPS",
                        "<strong>High-level arch (4 min):</strong> API GW + 8 services + polyglot data tier + 3 externals",
                        "<strong>Discovery (5 min):</strong> ES + S2 cells + Redis hot-query cache",
                        "<strong>Calendar &amp; slots (5 min):</strong> 15-min slots, iCal sync, AVAILABLE/HELD/BOOKED",
                        "<strong>Concurrency deep-dive (8 min):</strong> optimistic CAS, hold expiry, why over pessimistic",
                        "<strong>Video (6 min):</strong> WebRTC P2P, SFU for ≥3, TURN, 60s reconnect, build vs buy",
                        "<strong>Records + Rx + payments (6 min):</strong> envelope encryption, FHIR, refund saga",
                        "<strong>Failures + trade-offs (4 min):</strong> doctor calendar drift, payment leak, patient-safety override",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "“500K appointments/day, 5K concurrent video at peak” — anchors capacity",
                        "“30K search QPS, but 80% on ~5K hot pairs” — justifies Redis prewarm",
                        "“Slot is AVAILABLE → HELD → BOOKED with optimistic CAS” — concurrency story",
                        "“1-on-1 P2P, 3-way SFU” — keeps cost under control",
                        "“Patient owns the record; doctor gets time-bound grant” — compliance posture",
                        "“Hold then capture; saga compensates on cancel” — money-safety story",
                        "“Patient safety overrides money ambiguity” — judgement signal",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why optimistic over pessimistic locks?</strong> "
                        "A: Hot doctors see ~50 concurrent attempts on a popular slot. Pessimistic queues them through Postgres; "
                        "optimistic CAS lets all but one fail-fast and retry with a different slot.",
                        "<strong>Q: How do you stop a doctor from accepting a booking after blocking time on Google Calendar?</strong> "
                        "A: 5-min iCal reconciliation marks slots BLOCKED; if a booking already exists in the conflict window, "
                        "we resolve in the patient's favour and offer the doctor a one-click reschedule of their personal event.",
                        "<strong>Q: Why not E2E-encrypt video?</strong> "
                        "A: We need server-side recording for medical-record purposes (consent-gated). E2EE would block that. "
                        "Trade-off: TLS + DTLS-SRTP between client and SFU, encrypted-at-rest recordings, audit log.",
                        "<strong>Q: What's the data residency story?</strong> "
                        "A: Each workspace pinned to a region (IN, US, EU). DB shard, S3 bucket, KMS keys all "
                        "regional; cross-region access requires an explicit cross-region grant signed by the patient.",
                        "<strong>Q: 5K concurrent video — bandwidth?</strong> "
                        "A: ~15 Gbps P2P + 3 Gbps TURN. SFU only kicks in for ~5% of calls (3-way), bounded.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "30M users &nbsp;·&nbsp; 100K doctors &nbsp;·&nbsp; "
                        "500K appts/day &nbsp;·&nbsp; 5K concurrent video &nbsp;·&nbsp; "
                        "30K search QPS &nbsp;·&nbsp; 15 Gbps P2P + 3 Gbps TURN &nbsp;·&nbsp; "
                        "5-min hold &nbsp;·&nbsp; 60-sec video reconnect &nbsp;·&nbsp; "
                        "p95 booking &lt; 800 ms."
                    ),
                },
            ],
        },
    ],
}
