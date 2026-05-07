"""Source for `21 - Movie Ticket Booking.pdf`."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Movie Ticket Booking",
    "subtitle": "BookMyShow / Fandango: venues, showtimes, and double-booking-proof seat reservation",
    "read_time": "~ 45 minute read",
    "short_title": "Design Movie Ticket Booking",
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
                        "Design a movie ticket booking platform like <strong>BookMyShow</strong> or "
                        "<strong>Fandango</strong>. Users browse cities, theatres, movies, and showtimes; "
                        "select specific seats on a screen layout; hold them during checkout; and pay. "
                        "The hardest sub-problem is <strong>preventing double-booking</strong> when "
                        "tens of thousands of users hammer a single show simultaneously — an Avengers "
                        "premiere, a Coldplay concert, an IPL final."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Scope?", "Movies first; concerts/sports later (same primitives)"],
                        ["Geography?", "Multi-country; per-city catalog and currency"],
                        ["Seat selection?", "Yes — visual seat map; not just count of tickets"],
                        ["Hold during checkout?", "Yes — 5-minute hold while user pays"],
                        ["Payments?", "Card, UPI, wallets via 3rd-party PSP (idempotent)"],
                        ["Refunds & cancellations?", "Up to 2 hours before showtime; partial fee"],
                        ["Flash crowds?", "Marvel premieres: 50K reservation attempts/sec on one show"],
                        ["Consistency?", "Strong on seats; eventual on search/recommendations"],
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
                        ["Browse catalog", "City → cinema → movie → showtime; filters (language, format)"],
                        ["Seat map", "Render screen layout with AVAILABLE / HELD / BOOKED state"],
                        ["Hold seat", "Place 5-minute hold; reject if seat already HELD/BOOKED"],
                        ["Checkout & pay", "Idempotent charge via PSP; convert hold → booking on success"],
                        ["Cancel / refund", "Pre-show cancellation; release inventory back to AVAILABLE"],
                        ["Notifications", "Email/SMS/push for booking confirmation & reminders"],
                        ["Search", "Full-text by movie title, genre, language, location"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Correctness", "<strong>Zero double-bookings</strong> — invariant, not best-effort"],
                        ["Latency", "&lt;200ms seat map; &lt;500ms hold; &lt;3s end-to-end checkout"],
                        ["Availability", "99.95% on booking path; 99.9% on search/discovery"],
                        ["Throughput", "~1M bookings/day; 50K seat-reservations/sec on a hot show"],
                        ["Scalability", "Multi-region; isolate hot shows so they don't starve cold ones"],
                        ["Fairness", "Reasonable FIFO under contention; no permanent loser problem"],
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
                {"type": "h3", "text": "Users and Bookings"},
                {
                    "type": "bullets",
                    "items": [
                        "Registered users: <strong>10M</strong>; DAU on weekends: ~2M",
                        "Bookings per day: <strong>1M</strong> (avg 2.4 seats/booking ≈ 2.4M tickets/day)",
                        "Average sustained bookings/sec: 1M / 86,400 ≈ <strong>12 bookings/sec</strong>",
                        "Friday/weekend peak: <strong>10×</strong> sustained → ~120 bookings/sec average",
                        "Read:write ratio (browse vs book): ~<strong>50:1</strong> → ~6K browse QPS sustained, 60K at peak",
                    ],
                },
                {"type": "h3", "text": "The Hot-Show Problem"},
                {
                    "type": "bullets",
                    "items": [
                        "Marvel premiere goes on sale at 10:00 IST: tickets vanish in &lt; 60 seconds",
                        "One show = ~250 seats; 50K users hit <em>that single show</em> in the first second",
                        "<strong>Peak QPS on one show: 50K seat-reservation attempts/sec</strong>",
                        "Of those, only ~250 will succeed; the rest must fail fast and cleanly",
                        "Implication: hot-show traffic is <strong>1000× the average booking rate</strong>; cannot be handled by the same path",
                    ],
                },
                {"type": "h3", "text": "Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "Cinemas: ~10K worldwide × ~10 screens each = <strong>100K screens</strong>",
                        "Showtimes: 5 shows/screen/day × 100K × 365 = <strong>180M showtimes/year</strong>",
                        "Seat inventory rows: 180M shows × ~200 seats avg = <strong>36B rows/year</strong>",
                        "Booking record: ~500B; 1M/day × 365 = <strong>~180 GB/year</strong> bookings table",
                        "Total transactional store with indexes & 5y retention: <strong>~10–15 TB</strong>",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "10M users &nbsp;·&nbsp; 1M bookings/day &nbsp;·&nbsp; 10× Friday peak &nbsp;·&nbsp; "
                        "<strong>50K reservations/sec on a single hot show</strong> &nbsp;·&nbsp; "
                        "100K screens &nbsp;·&nbsp; 36B seat rows/year &nbsp;·&nbsp; "
                        "zero double-bookings tolerated."
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "Domain Model",
            "subtitle": "Entities and relationships",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Booking systems live or die on a clean domain model. The hierarchy is "
                        "<strong>chains → cities → cinemas → screens → seats</strong>, with "
                        "<strong>movies</strong> orthogonal to venues and connected through "
                        "<strong>showtimes</strong>. <strong>Bookings</strong> are the leaf "
                        "transactional record."
                    ),
                },
                {"type": "h3", "text": "Entity Hierarchy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Chain</strong> — operator (PVR, AMC, INOX); owns many cinemas",
                        "<strong>City</strong> — geographic & timezone bucket; cinemas live in cities",
                        "<strong>Cinema</strong> — physical venue; has 1..N screens",
                        "<strong>Screen</strong> — auditorium; fixed seat layout (rows × cols, format: 2D, 3D, IMAX)",
                        "<strong>Seat</strong> — physical seat in a screen; identified by (screen_id, row, col); has class (recliner, premium, standard)",
                        "<strong>Movie</strong> — title, language(s), runtime, certification, posters",
                        "<strong>Showtime</strong> — (screen_id, movie_id, start_time); the unit you sell",
                        "<strong>Seat Inventory</strong> — per-(showtime, seat) row tracking AVAILABLE/HELD/BOOKED",
                        "<strong>Booking</strong> — user_id + showtime_id + N seats + payment_id + status",
                    ],
                },
                {"type": "h3", "text": "Why Seat Inventory is Per-Showtime"},
                {
                    "type": "bullets",
                    "items": [
                        "The same physical seat is sold many times across different showtimes",
                        "State (AVAILABLE/HELD/BOOKED) is a property of <em>seat × showtime</em>, not seat alone",
                        "This is the table that experiences flash-crowd contention, so it deserves its own design",
                        "Pre-allocating one row per (showtime, seat) at showtime-creation simplifies UPDATE-only writes (no INSERT race)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Pre-allocate or Just-in-Time?",
                    "body": (
                        "Pre-allocating seat_inventory rows when a showtime is created (~200 rows per show) "
                        "lets the booking path do <code>UPDATE ... WHERE status='AVAILABLE'</code> with no "
                        "insert path. JIT inserting on first hold avoids rows for never-booked shows but "
                        "introduces an INSERT-vs-UPDATE race. <strong>Pre-allocation wins</strong>: 36B "
                        "rows/year is cheap, contention-safety is priceless."
                    ),
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
                        "The platform decomposes into a discovery side (Search, Catalog) optimized "
                        "for read scale and an inventory side (Booking, Payment) optimized for "
                        "correctness. A Notifications service is asynchronous off Kafka."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Figure 5.1: Mobile/Web → API Gateway fans out to Search (Elasticsearch), Catalog (Postgres), Booking (Postgres + Redis), Payment (PSP), Notifications. Kafka is the event spine.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Clients"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Mob [label="Mobile App", fillcolor="#dbe6fb"];
        Web [label="Web App",    fillcolor="#dbe6fb"];
    }

    GW [label="API Gateway\n(authn, rate-limit)", fillcolor="#fff2c9", color="#b8862e"];

    subgraph cluster_svc {
        label="Services"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        SR [label="Search\nService",        fillcolor="#cbeedf"];
        CA [label="Catalog\nService",       fillcolor="#cbeedf"];
        BK [label="Booking\nService",       fillcolor="#cbeedf"];
        PA [label="Payment\nService",       fillcolor="#cbeedf"];
        NO [label="Notifications\nService", fillcolor="#cbeedf"];
    }

    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        ES [label="Elasticsearch\n(movies, theatres)", fillcolor="#ead7fb"];
        PG [label="Postgres\n(catalog,\nseat_inventory,\nbookings)", fillcolor="#ead7fb"];
        RD [label="Redis\n(hot-show seat state,\nholds, rate limits)", fillcolor="#ead7fb"];
        KQ [label="Kafka\n(booking events)",        fillcolor="#fbd7c5"];
        PSP[label="3rd-party\nPayment Gateway",     fillcolor="#fbd7c5"];
    }

    Mob -> GW;
    Web -> GW;
    GW -> SR; GW -> CA; GW -> BK; GW -> PA;
    SR -> ES;
    CA -> PG;
    BK -> PG  [label="UPDATE\nseat_inventory"];
    BK -> RD  [label="hot-show\ncache"];
    BK -> KQ  [label="booking events"];
    PA -> PSP [label="charge"];
    PA -> PG  [label="payment record"];
    NO -> KQ  [style=dashed, label="consume"];
    KQ -> NO  [style=invis];
}
""",
                },
                {"type": "h3", "text": "Service Responsibilities"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>API Gateway:</strong> authn (JWT), rate-limit per user/IP, route to services, terminate TLS",
                        "<strong>Search Service:</strong> Elasticsearch query for movie/theatre/showtime; read-heavy, cacheable",
                        "<strong>Catalog Service:</strong> CRUD for cinemas, screens, seats, movies, showtimes; partner-facing admin APIs",
                        "<strong>Booking Service:</strong> seat hold + confirm; the correctness-critical path",
                        "<strong>Payment Service:</strong> idempotent PSP integration; wraps the booking saga",
                        "<strong>Notifications Service:</strong> Kafka consumer; sends email/SMS/push asynchronously",
                    ],
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Database Schema",
            "subtitle": "Tables for catalog, inventory, bookings",
            "blocks": [
                {"type": "h3", "text": "Showtime"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE showtimes (\n"
                        "  showtime_id    BIGINT PRIMARY KEY,\n"
                        "  screen_id      BIGINT NOT NULL REFERENCES screens(screen_id),\n"
                        "  movie_id       BIGINT NOT NULL REFERENCES movies(movie_id),\n"
                        "  start_time     TIMESTAMPTZ NOT NULL,\n"
                        "  end_time       TIMESTAMPTZ NOT NULL,\n"
                        "  language       VARCHAR(16) NOT NULL,\n"
                        "  format         VARCHAR(16) NOT NULL,   -- 2D, 3D, IMAX, 4DX\n"
                        "  base_price     INT          NOT NULL,  -- cents\n"
                        "  currency       CHAR(3)      NOT NULL,\n"
                        "  status         VARCHAR(16)  NOT NULL,  -- SCHEDULED, OPEN, SOLD_OUT, CANCELLED\n"
                        "  created_at     TIMESTAMPTZ DEFAULT NOW(),\n"
                        "  UNIQUE (screen_id, start_time)\n"
                        ");\n"
                        "CREATE INDEX idx_show_movie_time ON showtimes (movie_id, start_time);\n"
                        "CREATE INDEX idx_show_screen_time ON showtimes (screen_id, start_time);"
                    ),
                },
                {"type": "h3", "text": "Seat Inventory (the contended table)"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE seat_inventory (\n"
                        "  showtime_id    BIGINT      NOT NULL,\n"
                        "  seat_id        BIGINT      NOT NULL,    -- (screen_id, row, col)\n"
                        "  status         VARCHAR(16) NOT NULL,    -- AVAILABLE, HELD, BOOKED\n"
                        "  hold_id        UUID        NULL,        -- set when HELD\n"
                        "  user_id        BIGINT      NULL,        -- holder/buyer\n"
                        "  expires_at     TIMESTAMPTZ NULL,        -- hold expiry\n"
                        "  version        INT         NOT NULL DEFAULT 0,  -- optimistic lock\n"
                        "  price          INT         NOT NULL,    -- frozen at allocation\n"
                        "  PRIMARY KEY (showtime_id, seat_id)\n"
                        ");\n"
                        "CREATE INDEX idx_holds_expiry\n"
                        "  ON seat_inventory (expires_at)\n"
                        "  WHERE status = 'HELD';"
                    ),
                },
                {"type": "h3", "text": "Booking"},
                {
                    "type": "code",
                    "text": (
                        "CREATE TABLE bookings (\n"
                        "  booking_id     UUID         PRIMARY KEY,\n"
                        "  user_id        BIGINT       NOT NULL,\n"
                        "  showtime_id    BIGINT       NOT NULL,\n"
                        "  seat_ids       BIGINT[]     NOT NULL,\n"
                        "  hold_id        UUID         NOT NULL,\n"
                        "  amount         INT          NOT NULL,\n"
                        "  currency       CHAR(3)      NOT NULL,\n"
                        "  status         VARCHAR(16)  NOT NULL,  -- PENDING, CONFIRMED, FAILED, CANCELLED\n"
                        "  payment_id     UUID         NULL,\n"
                        "  idempotency_key VARCHAR(64) NOT NULL UNIQUE,\n"
                        "  created_at     TIMESTAMPTZ  DEFAULT NOW(),\n"
                        "  confirmed_at   TIMESTAMPTZ  NULL\n"
                        ");\n"
                        "CREATE INDEX idx_bk_user ON bookings (user_id, created_at DESC);\n"
                        "CREATE INDEX idx_bk_showtime ON bookings (showtime_id);"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Why a version column on seat_inventory",
                    "body": (
                        "The <code>version</code> column enables <strong>optimistic locking</strong>: "
                        "a hold attempt reads (status, version) and then writes only if version still "
                        "matches. Under contention, losers retry instead of blocking — far better than "
                        "row-level lock queues at 50K QPS."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Seat Reservation: Three Approaches",
            "subtitle": "Pessimistic vs Optimistic vs Distributed Lock",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The single most important interview question for this design: "
                        "<strong>how do you guarantee that a seat is booked by exactly one user?</strong> "
                        "There are three industry-standard primitives, each with different "
                        "consistency, latency, and operational characteristics."
                    ),
                },
                {"type": "h3", "text": "(a) Pessimistic — SELECT FOR UPDATE per seat"},
                {
                    "type": "code",
                    "text": (
                        "BEGIN;\n"
                        "SELECT status FROM seat_inventory\n"
                        " WHERE showtime_id = $1 AND seat_id = ANY($2)\n"
                        " FOR UPDATE;                        -- row lock until COMMIT\n"
                        "-- if any row is not AVAILABLE: ROLLBACK and fail\n"
                        "UPDATE seat_inventory\n"
                        "   SET status='HELD', hold_id=$3, user_id=$4, expires_at=NOW()+INTERVAL '5 min'\n"
                        " WHERE showtime_id=$1 AND seat_id=ANY($2);\n"
                        "COMMIT;"
                    ),
                },
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Pros:</strong> bulletproof correctness; serializes contenders cleanly",
                        "<strong>Cons:</strong> row locks held for the duration of the txn; on a hot show, 50K writers serialize through Postgres → seconds-long queues, connection exhaustion",
                        "<strong>When to use:</strong> normal-traffic shows; <em>and</em> as the inner safety net inside the checkout transaction even on hot shows",
                    ],
                },
                {"type": "h3", "text": "(b) Optimistic — version column + conditional UPDATE"},
                {
                    "type": "code",
                    "text": (
                        "-- read current state (may be served from a replica)\n"
                        "SELECT status, version FROM seat_inventory\n"
                        " WHERE showtime_id=$1 AND seat_id=$2;\n\n"
                        "-- write only if no one has touched the row since\n"
                        "UPDATE seat_inventory\n"
                        "   SET status='HELD', hold_id=$3, user_id=$4,\n"
                        "       expires_at=NOW()+INTERVAL '5 min',\n"
                        "       version = version + 1\n"
                        " WHERE showtime_id=$1 AND seat_id=$2\n"
                        "   AND status='AVAILABLE'\n"
                        "   AND version=$5;\n"
                        "-- rowcount = 1 → won; 0 → lost, retry or pick another seat"
                    ),
                },
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Pros:</strong> no locks held across the request; loser sees rowcount=0 and retries; scales horizontally",
                        "<strong>Cons:</strong> requires explicit retry handling and a UX path (\"this seat was just taken — pick another\"); more complex client",
                        "<strong>When to use:</strong> the <strong>default</strong> for everyday traffic — most hold attempts will be uncontended single-row writes",
                    ],
                },
                {"type": "h3", "text": "(c) Distributed Lock in Redis (RedLock)"},
                {
                    "type": "code",
                    "text": (
                        "# pseudocode: try to acquire a per-seat lock for ~6s\n"
                        "key   = f\"seat:{showtime_id}:{seat_id}\"\n"
                        "token = uuid4().hex\n"
                        "ok    = redis.set(key, token, nx=True, px=6000)   # SET NX PX\n"
                        "if not ok:\n"
                        "    return SeatTaken\n"
                        "try:\n"
                        "    # inside the lock: do the DB hold (still verify status!)\n"
                        "    rowcount = db.execute(OPTIMISTIC_HOLD_SQL, ...)\n"
                        "    if rowcount == 0: return SeatTaken\n"
                        "finally:\n"
                        "    # release only if we still own the lock (Lua CAS)\n"
                        "    redis.eval(RELEASE_LUA, keys=[key], args=[token])"
                    ),
                },
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Pros:</strong> sub-millisecond lock acquisition; absorbs the 50K-QPS thundering herd before it hits Postgres; trivial to put in front of any DB",
                        "<strong>Cons:</strong> RedLock has well-known partition-tolerance edge cases (Kleppmann's critique); a Redis failover can briefly grant the same lock twice",
                        "<strong>Mitigation:</strong> always do the DB conditional UPDATE inside the lock — Redis is the funnel, Postgres is the source of truth",
                    ],
                },
                {"type": "h3", "text": "Comparison"},
                {
                    "type": "table",
                    "headers": ["Aspect", "Pessimistic (SELECT FOR UPDATE)", "Optimistic (version)", "Redis Distributed Lock"],
                    "rows": [
                        ["Correctness", "Strongest (DB serializes)", "Strong (CAS in DB)", "Strong only if DB still validates"],
                        ["Latency under contention", "High (lock waits)", "Low (fail-fast retry)", "Lowest (fail at Redis)"],
                        ["Throughput on hot row", "Bottlenecked by lock queue", "Many losers, but all fast", "Funnels traffic; DB sees 1 winner"],
                        ["Failure modes", "Long-running txn → deadlock", "Retry storms if naive", "RedLock partition edge cases"],
                        ["Complexity", "Lowest", "Medium (retry logic)", "Highest (lock + CAS + lease)"],
                        ["Best for", "Inside checkout txn always", "Default everyday hold path", "Hot-show admission control"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Recommended Composition",
                    "body": (
                        "Use <strong>(b) optimistic locking</strong> as the default seat-hold primitive — it scales linearly "
                        "and fails fast. For known hot shows, put a <strong>(c) Redis lock</strong> in front to absorb the "
                        "thundering herd. Inside the eventual checkout transaction, always upgrade to <strong>(a) "
                        "SELECT FOR UPDATE</strong> on the held rows so the final commit is bulletproof. All three layers "
                        "are correct; the composition gives correctness <em>and</em> throughput."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Hold State Machine",
            "subtitle": "AVAILABLE → HELD → BOOKED, with TTL",
            "blocks": [
                {"type": "h3", "text": "Status Transitions"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>AVAILABLE → HELD:</strong> on successful hold; sets hold_id, user_id, expires_at = now + 5 min",
                        "<strong>HELD → BOOKED:</strong> on payment success; clears expires_at, links to booking_id",
                        "<strong>HELD → AVAILABLE:</strong> on payment failure, user cancel, or expiry sweep",
                        "<strong>BOOKED → AVAILABLE:</strong> only on cancellation/refund; logged for audit",
                        "<strong>Invariant:</strong> a row can be transitioned only by the owner of the current hold_id (or admin/sweeper)",
                    ],
                },
                {"type": "h3", "text": "Expiring Holds"},
                {
                    "type": "para",
                    "text": (
                        "If a user opens checkout and walks away, the seats must be released. Two "
                        "mechanisms work in concert:"
                    ),
                },
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Background sweeper</strong> — every 10 sec: <code>UPDATE seat_inventory SET status='AVAILABLE', hold_id=NULL, expires_at=NULL WHERE status='HELD' AND expires_at &lt; NOW()</code>; uses the partial index",
                        "<strong>Lazy release on read</strong> — when seat map is fetched, treat HELD-with-expired-expires_at as AVAILABLE in the API response (UX fast path), then enqueue the sweep",
                        "<strong>Per-hold TTL in Redis</strong> — for hot shows, a Redis key <code>hold:{hold_id}</code> with PX=300s; on expiry, a key-expiry listener kicks the DB sweep",
                    ],
                },
                {"type": "h3", "text": "Optimistic Hold with Retry (algorithm)"},
                {
                    "type": "code",
                    "text": (
                        "def hold_seats(showtime_id, seat_ids, user_id, max_retries=3):\n"
                        "    hold_id = uuid4()\n"
                        "    expires = now() + timedelta(minutes=5)\n"
                        "    for attempt in range(max_retries):\n"
                        "        # 1. read current versions (one round-trip)\n"
                        "        rows = db.fetchall('''\n"
                        "            SELECT seat_id, status, version FROM seat_inventory\n"
                        "             WHERE showtime_id=%s AND seat_id = ANY(%s)\n"
                        "        ''', (showtime_id, seat_ids))\n"
                        "        if any(r.status != 'AVAILABLE' for r in rows):\n"
                        "            return Failure('SEAT_TAKEN', conflicting=[r.seat_id\n"
                        "                                       for r in rows if r.status != 'AVAILABLE'])\n"
                        "\n"
                        "        # 2. CAS update — all-or-nothing in one txn\n"
                        "        with db.transaction():\n"
                        "            updated = 0\n"
                        "            for r in rows:\n"
                        "                updated += db.execute('''\n"
                        "                    UPDATE seat_inventory\n"
                        "                       SET status='HELD', hold_id=%s, user_id=%s,\n"
                        "                           expires_at=%s, version=version+1\n"
                        "                     WHERE showtime_id=%s AND seat_id=%s\n"
                        "                       AND status='AVAILABLE' AND version=%s\n"
                        "                ''', (hold_id, user_id, expires,\n"
                        "                      showtime_id, r.seat_id, r.version)).rowcount\n"
                        "            if updated == len(rows):\n"
                        "                return Success(hold_id, expires)\n"
                        "            db.rollback()  # partial → all-or-nothing\n"
                        "        # 3. someone moved a row; loop and re-read\n"
                        "    return Failure('SEAT_TAKEN_RETRIES_EXHAUSTED')"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "All-or-Nothing Group Holds",
                    "body": (
                        "A user picking 4 seats expects <strong>all 4 or none</strong>. Run all "
                        "per-seat CAS updates inside a single transaction; if any one fails, "
                        "rollback the whole transaction and retry. Never confirm a partial group — "
                        "that's a UX disaster (\"you got 3 of 4\")."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Seat Reservation Sequence",
            "subtitle": "End-to-end flow, click to confirmation",
            "blocks": [
                {
                    "type": "diagram",
                    "caption": "Figure 9.1: User clicks seats → Booking Service tries Redis admission lock → Postgres optimistic CAS hold → checkout → idempotent payment → confirm booking → release Redis lock. Failures at any step trigger compensating actions.",
                    "dot": r"""
digraph S {
    rankdir=TB;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    U   [label="1. User clicks seats\nPOST /hold {showtime, [seats]}", fillcolor="#dbe6fb"];
    LCK [label="2. Booking svc:\nacquire Redis lock per seat\n(SET NX PX 6000)", fillcolor="#cbeedf", color="#1f8359"];
    CAS [label="3. Postgres CAS UPDATE\nstatus=HELD WHERE\nstatus=AVAILABLE AND version=v", fillcolor="#cbeedf", color="#1f8359"];
    OK  [label="4. hold_id, expires_at\nreturned to client (5-min timer)", fillcolor="#fff2c9", color="#b8862e"];
    CHK [label="5. User clicks pay\nPOST /checkout {hold_id, payment}", fillcolor="#dbe6fb"];
    PAY [label="6. Payment svc charges PSP\nidempotency_key = hold_id", fillcolor="#fff2c9", color="#b8862e"];
    CFM [label="7. SELECT FOR UPDATE held rows\nstatus HELD→BOOKED\nINSERT booking + payment", fillcolor="#cbeedf", color="#1f8359"];
    REL [label="8. release Redis lock\nemit booking_confirmed → Kafka", fillcolor="#ead7fb", color="#7a3eb8"];
    NOT [label="9. Notifications svc\nemail/SMS/push ticket", fillcolor="#fbd7c5"];

    FCAS[label="3a. CAS rowcount=0\n→ SEAT_TAKEN; release lock; suggest alternates",
         fillcolor="#f8d7d7", color="#a03030"];
    FPAY[label="6a. payment fails/timeout\n→ saga: release seats + lock,\nbooking=FAILED",
         fillcolor="#f8d7d7", color="#a03030"];
    EXP [label="(timer) hold expires after 5 min\n→ sweeper releases seats",
         fillcolor="#f8d7d7", color="#a03030"];

    U -> LCK -> CAS -> OK -> CHK -> PAY -> CFM -> REL -> NOT;
    CAS -> FCAS [style=dashed, label="conflict"];
    PAY -> FPAY [style=dashed, label="fail"];
    OK  -> EXP  [style=dashed, label="user idle"];
}
""",
                },
                {"type": "h3", "text": "Step-by-Step"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Hold attempt:</strong> client sends seat ids; Booking acquires per-seat Redis locks (admission control)",
                        "<strong>DB CAS:</strong> within the locks, run optimistic UPDATE; require all rows updated or rollback",
                        "<strong>Hold confirmed:</strong> return <code>hold_id</code> + <code>expires_at</code>; client starts a 5-min countdown",
                        "<strong>Checkout:</strong> client posts payment details with <code>idempotency_key = hold_id</code>",
                        "<strong>PSP charge:</strong> Payment Service issues idempotent charge; retries on network errors are safe",
                        "<strong>Confirm:</strong> on success, transaction does SELECT FOR UPDATE on the HELD rows, transitions to BOOKED, inserts booking + payment record",
                        "<strong>Release lock & emit:</strong> drop Redis lock; publish <code>booking_confirmed</code> to Kafka",
                        "<strong>Notify:</strong> Notifications consumer emails/SMSs the ticket; Search service may evict cached seat-map",
                    ],
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Payment Integration",
            "subtitle": "Idempotency and the seat-release saga",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Payment is where money meets seats; it's also the noisiest part of the "
                        "system (PSP timeouts, network drops, user back-button). The two design "
                        "goals are <strong>idempotency</strong> (so retries don't double-charge) "
                        "and a <strong>compensating transaction</strong> (so a failed payment "
                        "cleanly returns seats to inventory)."
                    ),
                },
                {"type": "h3", "text": "Idempotent Charge"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Idempotency key:</strong> use <code>hold_id</code> (UUID) as the key sent to the PSP",
                        "<strong>PSP guarantee:</strong> Stripe/Razorpay/Adyen dedupe by key for 24h; same key returns the same charge result",
                        "<strong>Local table:</strong> <code>payments(payment_id, idempotency_key UNIQUE, status, psp_ref, ...)</code>; INSERT-or-fetch on the unique key",
                        "<strong>Client retries:</strong> always allowed; the same hold_id always converges to the same booking",
                    ],
                },
                {"type": "h3", "text": "Compensating Saga on Failure"},
                {
                    "type": "code",
                    "text": (
                        "def checkout(hold_id, payment_method):\n"
                        "    booking = create_booking_pending(hold_id)         # status=PENDING\n"
                        "    try:\n"
                        "        result = psp.charge(amount, payment_method,\n"
                        "                            idempotency_key=hold_id,\n"
                        "                            timeout=20s)\n"
                        "    except (PspTimeout, PspNetworkError):\n"
                        "        # don't know yet — schedule reconciler\n"
                        "        kafka.emit('payment_unknown', booking.id, hold_id)\n"
                        "        return Pending(booking.id)\n"
                        "    if result.status == 'SUCCESS':\n"
                        "        confirm_booking(booking.id, hold_id, result.payment_id)\n"
                        "        return Confirmed(booking.id)\n"
                        "    else:\n"
                        "        # COMPENSATING TRANSACTION: release the seats\n"
                        "        release_hold(hold_id)\n"
                        "        mark_booking_failed(booking.id, result.error)\n"
                        "        return Failed(result.error)"
                    ),
                },
                {"type": "h3", "text": "Reconciler for Unknown States"},
                {
                    "type": "bullets",
                    "items": [
                        "PSP timeouts leave the charge in a <strong>UNKNOWN</strong> state — could be charged or not",
                        "Reconciler job polls the PSP every 30s on the idempotency_key until terminal",
                        "On terminal SUCCESS: confirm booking; on FAIL: release hold (idempotent if already released)",
                        "Hold TTL (5 min) is the safety net: even if reconciler is down, seats free themselves",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Never confirm before charge succeeds",
                    "body": (
                        "Tempting optimization: \"emit booking_confirmed eagerly to keep the UI snappy.\" "
                        "Don't. If the charge later fails, you've already sent an email with a ticket "
                        "QR code that doesn't exist — and the seat is double-bookable. "
                        "<strong>Confirmation must follow successful capture.</strong>"
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Search & Discovery",
            "subtitle": "Finding the right show",
            "blocks": [
                {"type": "h3", "text": "Query Surface"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>By location:</strong> city → list of cinemas with shows today; default user-detected city",
                        "<strong>By movie:</strong> showtimes across cinemas in user's city, grouped by venue",
                        "<strong>By language / format:</strong> Hindi, Tamil, …; 2D, 3D, IMAX, 4DX",
                        "<strong>By time window:</strong> tonight, weekend, this week",
                        "<strong>Full-text:</strong> movie title, cast, theatre name (typo-tolerant)",
                    ],
                },
                {"type": "h3", "text": "Storage & Indexing"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Postgres</strong> is source of truth for catalog (movies, theatres, showtimes)",
                        "<strong>Elasticsearch</strong> is the read-side projection for search; indexed via CDC (Debezium → Kafka → ES sink)",
                        "<strong>Per-city sharding</strong> in ES: index alias <code>showtimes-{city}</code>; query routes by user city",
                        "<strong>TTL on documents:</strong> showtimes in the past auto-delete from ES (ILM policy, 7-day retention)",
                    ],
                },
                {"type": "h3", "text": "Caching Discovery"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Edge cache (CDN):</strong> movie list per city, posters, trailers — TTL 5 min",
                        "<strong>App cache (Redis):</strong> showtimes-by-(city,date) keyed lookups, TTL 60s",
                        "<strong>Seat map snapshot:</strong> AVAILABLE/HELD/BOOKED state cached for 2s — fresh enough for browsing, but never trust for booking",
                        "<strong>Stale-while-revalidate:</strong> serve last-good while async refresh runs",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Read state is advisory; write state is authoritative",
                    "body": (
                        "Seat maps shown during browsing can be a few seconds stale — that's fine, "
                        "users still pick a seat. The <em>hold attempt</em> is the only place where "
                        "freshness matters, and it always re-reads from the DB. Decoupling display "
                        "freshness from correctness freshness is the unlock for browsing throughput."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Hot-Show Special Path",
            "subtitle": "Surviving 50K reservations/sec on one show",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "An Avengers premiere on sale at 10:00 IST is a fundamentally different "
                        "workload from the average booking. We pre-classify shows as "
                        "<strong>hot</strong> and route them through a dedicated path."
                    ),
                },
                {"type": "h3", "text": "Identifying Hot Shows"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Manual flag</strong> — partner ops mark known blockbuster premieres as hot at showtime creation",
                        "<strong>Auto-detect</strong> — if seat-map QPS for a showtime crosses, e.g., 1K/sec, promote to hot",
                        "<strong>Hot path activates:</strong> Redis-fronted admission, dedicated Postgres connection pool, separate rate limiter, queueing UI",
                    ],
                },
                {"type": "h3", "text": "Admission Control"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Virtual waiting room:</strong> users entering the show page join a token queue (Redis sorted set); only N=2× capacity admitted concurrently",
                        "<strong>Seat-level locks:</strong> Redis SET NX PX serializes contenders for each seat — only one reaches Postgres per seat",
                        "<strong>Per-user rate limit:</strong> max 1 outstanding hold attempt per user per show (prevents bot floods)",
                        "<strong>Connection isolation:</strong> hot-show booking pool ≠ general pool, so the rest of the system stays healthy",
                    ],
                },
                {"type": "h3", "text": "Caching Seat State for Hot Shows"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Per-seat status cached in Redis:</strong> hash <code>show:{id}:seats</code>, fields = seat_id → status",
                        "<strong>Updated on every transition:</strong> Booking writes both DB and Redis; on conflict, DB wins (CDC repairs cache)",
                        "<strong>Seat-map reads bypass Postgres entirely</strong> during hot windows → 99% browse load on Redis",
                        "<strong>Fallback:</strong> if Redis is unhealthy, seat map falls back to DB (slower, but correct); booking still works because DB is source of truth",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Three-Layer Funnel",
                    "body": (
                        "1) <strong>Waiting room</strong> rate-limits how many users can attempt holds at all. "
                        "2) <strong>Redis lock</strong> serializes the survivors per seat. "
                        "3) <strong>Postgres CAS</strong> is the final source-of-truth gate. "
                        "Each layer drops ~10–100× of the load. The 50K/sec storm becomes ~250 successful "
                        "writes/sec at the DB — well within normal capacity."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Failure Modes & Recovery",
            "subtitle": "What breaks and how we degrade",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["Payment timeout after hold",
                         "Money may or may not be charged",
                         "PSP HTTP timeout (&gt;20s)",
                         "Reconciler polls PSP on idempotency_key; release saga frees seats; hold TTL is safety net"],
                        ["Redis cluster down",
                         "Hot-show admission lost; cache miss storm",
                         "Redis health check, latency alarm",
                         "Fall back to DB-only path; degrade hot-show throughput; reject new attempts at 429"],
                        ["Postgres primary down",
                         "All booking writes fail",
                         "Conn errors, replication lag alarm",
                         "Auto-promote replica (Patroni); booking returns 503 with retry-after; reads served from replica"],
                        ["Long-running SELECT FOR UPDATE",
                         "Lock queue, conn exhaustion",
                         "pg_locks monitoring",
                         "Statement_timeout=2s; circuit breaker; switch hot show to optimistic+Redis path"],
                        ["Sweeper lag",
                         "Expired holds linger; seats look unavailable",
                         "Holds older than expires_at metric",
                         "Multi-instance sweeper; lazy release on read; alert if backlog &gt; 1 min"],
                        ["Kafka down",
                         "Notifications delayed; analytics lag",
                         "Broker dead alert",
                         "Booking core path still works; events buffered locally and replayed"],
                        ["PSP webhook lost",
                         "Booking stuck PENDING",
                         "Booking-aging metric",
                         "Reconciler polls; webhook retry; user-facing \"check status\" endpoint"],
                        ["Showtime cancelled by cinema",
                         "Bookings invalid",
                         "Partner admin event",
                         "Bulk refund saga; emit notifications; release inventory"],
                    ],
                },
                {"type": "h3", "text": "Degradation Order"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Tier 1 (must work):</strong> seat hold + payment + booking confirmation",
                        "<strong>Tier 2 (degrade gracefully):</strong> hot-show waiting room, seat-map cache, search relevance",
                        "<strong>Tier 3 (delay OK):</strong> notifications, analytics, recommendations",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Saga, not 2PC",
                    "body": (
                        "Payment + Inventory live in different systems (PSP + Postgres). 2PC across them is "
                        "neither possible nor desirable — the PSP is a 3rd party. Use a saga: forward steps "
                        "(create booking → charge → confirm) each have a compensating reverse (release hold → "
                        "void/refund). Every state transition is durable and replayable."
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
                        ["Concurrency primitive (default)",
                         "Optimistic locking (version)",
                         "Fast under low contention; needs retry UX. Pessimistic would queue everyone and starve at 50K QPS."],
                        ["Concurrency primitive (hot show)",
                         "Redis admission + DB CAS + checkout SELECT FOR UPDATE",
                         "Three layers add complexity; without them a single hot show DDoSes the booking DB."],
                        ["Seat inventory rows",
                         "Pre-allocate at showtime creation",
                         "36B rows/yr storage; eliminates INSERT race and allows pure UPDATE-only path."],
                        ["Source of truth",
                         "Postgres",
                         "ACID gives us correctness; sharding & ops overhead. NoSQL would be cheaper to scale but weaker on multi-row transactional holds."],
                        ["Hold TTL",
                         "5 minutes",
                         "Long enough for users to pay; short enough that abandoned holds free quickly. Shorter = friction; longer = inventory hoarding."],
                        ["Search store",
                         "Elasticsearch projection from Postgres",
                         "Eventual consistency on browse data is OK; ES lets us scale read QPS independently of catalog writes."],
                        ["Payment confirmation",
                         "Synchronous within checkout txn",
                         "Slower checkout; never overbooks. Async confirmation would be faster but lets you ship a ticket whose payment later fails."],
                        ["Notifications",
                         "Async via Kafka",
                         "User sees confirmation page instantly; email may take a few seconds. Sync would couple booking latency to email infra."],
                        ["Hot-show detection",
                         "Hybrid (manual flag + auto-detect)",
                         "Manual catches premieres; auto catches surprises. Pure auto reacts late; pure manual misses unexpected hits."],
                    ],
                },
            ],
        },
        # ---- 15 ------------------------------------------------------
        {
            "num": "15",
            "title": "Scalability & Multi-Region",
            "subtitle": "Growing the platform",
            "blocks": [
                {"type": "h3", "text": "Horizontal Scaling"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Stateless services</strong> — Booking, Search, Payment scale behind load balancers",
                        "<strong>Postgres sharded by city_id</strong> — bookings rarely cross cities; 32–128 shards depending on country",
                        "<strong>Read replicas per shard</strong> — serve seat-map browsing and analytics; primary handles holds/bookings",
                        "<strong>Redis cluster</strong> — slot-based; one slot per show key so all that show's locks colocate",
                    ],
                },
                {"type": "h3", "text": "Sharding by City"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Why city:</strong> a booking is always against one cinema in one city → no cross-shard txns on the hot path",
                        "<strong>Hot-city overflow:</strong> Mumbai is bigger than 10× a small city — sub-shard popular cities by cinema_id",
                        "<strong>Catalog reference data</strong> — movies, languages — globally replicated read-only tables",
                    ],
                },
                {"type": "h3", "text": "Multi-Region"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Region per country</strong> — IN, US, EU isolated; latency and data-residency benefits",
                        "<strong>No cross-region writes on hot path</strong> — a Mumbai booking never touches the EU primary",
                        "<strong>Global services:</strong> identity (users), payment routing, fraud, recommendations — replicated read views",
                        "<strong>Disaster recovery:</strong> per-region warm standby; RPO &lt; 1 min via streaming replication",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why City is the Natural Shard Key",
                    "body": (
                        "Movie ticket booking is fundamentally local: users pick a cinema in their city, "
                        "showtimes belong to one screen in one venue, holds touch one row per (showtime, seat). "
                        "There is no realistic transaction that spans cities. That makes city_id the right "
                        "shard key, gives us geo-locality for free, and isolates hot-city blast radius."
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
                        "Movie ticket booking is the canonical <strong>contended-inventory</strong> "
                        "interview question. Hotel rooms, flight seats, concert tickets, restaurant "
                        "reservations all share the same core. If you can defend the seat-reservation "
                        "design under flash-crowd pressure, you have answered 80% of the question."
                    ),
                },
                {"type": "h3", "text": "45-Minute Interview Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (3 min):</strong> 10M users, 1M bookings/day, 10× Friday peak, <strong>50K/sec on one hot show</strong>; zero double-bookings",
                        "<strong>Domain model (5 min):</strong> chains → cinemas → screens → seats → showtimes → seat_inventory → bookings; pre-allocate inventory rows",
                        "<strong>High-level arch (3 min):</strong> API GW → {Search, Catalog, Booking, Payment, Notifications} → {Postgres, Redis, ES, Kafka, PSP}",
                        "<strong>Seat reservation (15 min — the centerpiece):</strong> walk through (a) pessimistic, (b) optimistic, (c) Redis lock; recommend (b) default, (a) inside checkout txn, (c) for hot shows",
                        "<strong>State machine + saga (5 min):</strong> AVAILABLE → HELD → BOOKED; 5-min TTL; sweeper; payment failure → release saga",
                        "<strong>Hot-show path (5 min):</strong> waiting room + Redis admission + connection isolation",
                        "<strong>Failures (5 min):</strong> payment timeout, Redis down, sweeper lag, PSP webhook loss",
                        "<strong>Trade-offs & wrap (4 min):</strong> consistency vs throughput, pre-allocate vs JIT, sync confirm vs async",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "\"50K reservation attempts/sec on one show\" — frames the entire concurrency discussion",
                        "\"AVAILABLE → HELD → BOOKED with hold_id and expires_at\" — concrete state machine",
                        "\"Optimistic CAS with version column\" — default; \"SELECT FOR UPDATE inside checkout txn\" — final safety net",
                        "\"Redis lock funnels 50K/sec into 250 DB writes\" — quantifies the hot-show admission",
                        "\"hold_id as PSP idempotency key\" — payment retries cannot double-charge or double-book",
                        "\"Compensating saga, not 2PC\" — release seats on payment failure",
                        "\"Pre-allocate seat_inventory rows\" — UPDATE-only path; no INSERT race",
                        "\"City as shard key\" — bookings never cross cities; clean horizontal scale",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: How do you guarantee no double-booking?</strong> A: Postgres UPDATE … WHERE status='AVAILABLE' AND version=v is atomic; rowcount=1 means we won, 0 means lost. Inside the checkout txn, SELECT FOR UPDATE the held rows for an extra serialization barrier. Redis is only a funnel, never the source of truth.",
                        "<strong>Q: What if payment succeeds but booking confirm fails?</strong> A: Retry the confirm; idempotent on hold_id. Reconciler reads payment status; if charged but no booking after N retries, refund and release seats. Hold TTL is the backstop.",
                        "<strong>Q: What if 50K users want the same seat?</strong> A: Redis SET NX serializes them; only one reaches the DB; the other 49,999 see SEAT_TAKEN within milliseconds. UI suggests next-best alternates.",
                        "<strong>Q: Why not just SELECT FOR UPDATE everywhere?</strong> A: At 50K QPS the lock queue and connection count blow up Postgres. Optimistic + Redis admission keeps lock duration to a single fast UPDATE.",
                        "<strong>Q: How do you handle the user closing the tab?</strong> A: 5-min TTL; background sweeper releases; lazy release on read returns seat as AVAILABLE if expires_at &lt; now.",
                        "<strong>Q: Refunds and cancellations?</strong> A: Cancellation flips BOOKED → AVAILABLE in the same txn that issues the refund; emit cancellation event; partial-fee policy lives in the booking rules engine.",
                        "<strong>Q: How do you scale beyond one DB?</strong> A: Shard by city_id; bookings are local-by-construction. Hot cities sub-shard by cinema_id.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "10M users &nbsp;·&nbsp; 1M bookings/day &nbsp;·&nbsp; 10× Friday peak &nbsp;·&nbsp; "
                        "<strong>50K reservation attempts/sec on a hot show</strong> &nbsp;·&nbsp; "
                        "5-min hold TTL &nbsp;·&nbsp; ~250 seats/show &nbsp;·&nbsp; 100K screens &nbsp;·&nbsp; "
                        "AVAILABLE → HELD → BOOKED &nbsp;·&nbsp; zero double-bookings."
                    ),
                },
            ],
        },
    ],
}
