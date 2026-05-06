"""Source for `20 - Swiggy Deliveroo.pdf` — three-sided food-delivery marketplace."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design Swiggy / Deliveroo",
    "subtitle": "three-sided food-delivery marketplace: customers, restaurants, riders",
    "read_time": "~ 45 minute read",
    "short_title": "Design Swiggy / Deliveroo (Food Delivery)",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Statement",
            "subtitle": "Three-sided marketplace, not just rideshare",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Design a food-delivery platform like <strong>Swiggy</strong>, "
                        "<strong>Deliveroo</strong>, <strong>DoorDash</strong>, or "
                        "<strong>Uber Eats</strong>. Unlike Uber rideshare (two-sided: "
                        "rider + driver), this is a <strong>three-sided marketplace</strong>: "
                        "<em>customer</em> places an order, <em>restaurant</em> prepares the "
                        "food, and <em>rider</em> delivers it. All three lifecycles must stay "
                        "synchronized on a single <code>order_id</code> state machine while "
                        "an ML stack predicts prep-time and ETA, and the dispatcher batches "
                        "deliveries for unit economics."
                    ),
                },
                {"type": "h3", "text": "Why This Differs from Uber Rideshare"},
                {
                    "type": "table",
                    "headers": ["Dimension", "Uber Rideshare", "Food Delivery"],
                    "rows": [
                        ["Sides", "2 (rider, driver)", "3 (customer, restaurant, rider)"],
                        ["Service time", "Known once trip starts", "Variable prep_time (5–25 min, ML estimate)"],
                        ["Inventory", "Driver capacity = 1 trip", "Restaurant menu, in-stock flags, kitchen load"],
                        ["Batching", "UberPool: shared mid-trip", "Stack 2–3 orders from same restaurant cluster"],
                        ["Cancellation", "Either side, low cost", "Food already cooking → restaurant absorbs cost"],
                        ["Dispatch trigger", "Rider request immediately", "Wait for prep-time minus rider arrival"],
                        ["Search", "Pickup location only", "Restaurant catalog, dish, cuisine, price, rating"],
                    ],
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Order volume?", "~5M orders/day globally"],
                        ["Cities & restaurants?", "~500K active restaurants across major metros"],
                        ["Rider fleet?", "~500K riders concurrently online at peak"],
                        ["Search load?", "~50K QPS (catalog browsing dominates)"],
                        ["Order placement peak?", "~60 orders/sec (lunch + dinner spikes 5–8× baseline)"],
                        ["Geography?", "Hyperlocal: most deliveries within 4 km / 30 min"],
                        ["Payments?", "Card, UPI, wallets, cash-on-delivery"],
                        ["Batching allowed?", "Yes: 2–3 orders if same direction & overlapping prep"],
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
                        ["Browse / Search", "Customer searches restaurants by location, cuisine, dish, rating, price"],
                        ["Cart & Checkout", "Add items; re-validate prices & stock at checkout (menu may have changed)"],
                        ["Place Order", "Atomic order creation: payment hold + restaurant confirmation"],
                        ["Restaurant App", "Tablet at restaurant accepts/rejects, marks prep_started / food_ready"],
                        ["Dispatch", "Match order to rider considering prep-time, distance, and batch potential"],
                        ["Live Tracking", "Customer sees rider location; ETA recomputed continuously"],
                        ["Payments", "Pre-auth at order, capture on delivery; refunds for cancellations"],
                        ["Surge Pricing", "Busy-area delivery fee multiplier when demand &gt;&gt; supply"],
                        ["Notifications", "Push/SMS at each state transition"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Availability", "99.95% for order/dispatch; 99.9% for search"],
                        ["Latency (search)", "&lt;200ms p95 from edge"],
                        ["Latency (place order)", "&lt;1s p95 (payment hold + restaurant push)"],
                        ["Dispatch decision", "&lt;3s from food_ready to rider_assigned"],
                        ["Menu propagation", "Restaurant edits visible in search index in &lt;60s"],
                        ["ETA accuracy", "MAE &lt;3 minutes; p90 within 5 min"],
                        ["Consistency", "Strong on order state &amp; payment; eventual on search index"],
                        ["Geo coverage", "Multi-region active-active per metro"],
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
                {"type": "h3", "text": "Traffic & Concurrency"},
                {
                    "type": "bullets",
                    "items": [
                        "Active users (MAU): <strong>~200M</strong>; DAU ~30M",
                        "Orders/day: <strong>~5M</strong> globally",
                        "Average orders/sec: 5M / 86,400 ≈ <strong>58/sec</strong> baseline",
                        "Lunch + dinner peak: 5–8× baseline ≈ <strong>~60 orders/sec sustained at peak</strong> (with bursts to ~300/sec)",
                        "Search QPS: customers browse 8–10 screens before ordering → <strong>~50K search QPS</strong> at peak",
                        "Active riders online: <strong>~500K</strong>; GPS pings every 4s → <strong>~125K pings/sec</strong>",
                        "Active restaurants: <strong>~500K</strong>; tablet poll/long-poll every 5s → <strong>~100K conn</strong>",
                    ],
                },
                {"type": "h3", "text": "Storage Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        "Per order: header (~2 KB) + items (~3 KB) + state log (~1 KB) ≈ <strong>~6 KB</strong>",
                        "Daily order data: 5M × 6 KB = <strong>~30 GB/day</strong>",
                        "5-year retention (hot 90d, warm 1y, cold archive): ~<strong>55 TB</strong>",
                        "Restaurant menus: 500K × ~50 KB = <strong>~25 GB</strong> (small, fits in cache)",
                        "Rider GPS history (90 days): 500K riders × 1 ping/4s × 86,400/4 × 90 ≈ <strong>~1B pings/day</strong> → ~<strong>120 GB/day</strong> compressed",
                        "Search index (Elasticsearch): denormalised restaurant + dish docs ≈ <strong>~80 GB</strong> per region",
                    ],
                },
                {"type": "h3", "text": "Cache & Bandwidth"},
                {
                    "type": "bullets",
                    "items": [
                        "Hot menus (top 10% of restaurants drive 80% of orders) → <strong>~5 GB Redis</strong> per region",
                        "Geo-index of riders (H3 hex cells) → ~<strong>200 MB</strong> in memory per metro",
                        "Customer cart sessions (Redis, TTL 30 min) → ~<strong>2 GB</strong>",
                        "Bandwidth: rider pings 100B × 125K/sec = <strong>~12 MB/sec</strong> ingress",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "5M orders/day &nbsp;·&nbsp; ~60 orders/sec peak &nbsp;·&nbsp; "
                        "50K search QPS &nbsp;·&nbsp; 500K riders &nbsp;·&nbsp; "
                        "500K restaurants &nbsp;·&nbsp; 30 GB orders/day &nbsp;·&nbsp; "
                        "MAE ETA &lt;3 min."
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "High-Level Architecture",
            "subtitle": "Three sides into one platform",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Three client surfaces — <strong>customer app</strong>, "
                        "<strong>restaurant tablet</strong>, and <strong>rider app</strong> — "
                        "all enter through an API gateway and converge on a set of services that "
                        "share an <code>order_id</code> state machine. Search and Cart are read-heavy "
                        "and run off Elasticsearch + Redis; Order and Dispatch are write-heavy and "
                        "run off Postgres + Kafka with Redis geo-sets for live rider locations."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Three clients converge on a shared API gateway, fan out to domain services, and persist to a heterogeneous data tier (Postgres for transactions, Redis for hot state, Elasticsearch for catalog, Kafka for events).",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_clients {
        label="Clients"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Cust [label="Customer App", fillcolor="#dbe6fb"];
        Tab  [label="Restaurant\nTablet",      fillcolor="#dbe6fb"];
        Rid  [label="Rider App",   fillcolor="#dbe6fb"];
    }
    GW [label="API Gateway\n+ Auth + RL", fillcolor="#cbeedf", color="#1f8359"];

    subgraph cluster_svc {
        label="Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        Search   [label="Search\n(Catalog)",     fillcolor="#fff2c9"];
        Cart     [label="Cart /\nCheckout",      fillcolor="#fff2c9"];
        Order    [label="Order\n(state machine)",fillcolor="#fff2c9"];
        Dispatch [label="Dispatch\n+ Batching",  fillcolor="#fff2c9"];
        Pay      [label="Payment",               fillcolor="#fff2c9"];
        Pricing  [label="Pricing\n+ Surge",      fillcolor="#fff2c9"];
        Notif    [label="Notifications",         fillcolor="#fff2c9"];
        ETA      [label="ETA / ML",              fillcolor="#fff2c9"];
    }

    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        PG  [label="Postgres\n(orders, menus)", fillcolor="#ead7fb"];
        RD  [label="Redis\n(cart, rider geo)",  fillcolor="#ead7fb"];
        ES  [label="Elasticsearch\n(catalog)",  fillcolor="#ead7fb"];
        KF  [label="Kafka\n(events)",           fillcolor="#fbd7c5"];
        RT  [label="Routing\n(OSRM/Valhalla)",  fillcolor="#ead7fb"];
    }

    Cust -> GW;
    Tab  -> GW;
    Rid  -> GW;

    GW -> Search;
    GW -> Cart;
    GW -> Order;
    GW -> Pay;
    GW -> Notif;

    Search -> ES;
    Cart   -> RD;
    Cart   -> PG  [label="re-validate"];
    Order  -> PG;
    Order  -> KF  [label="state events"];
    Order  -> Pricing;
    Pay    -> PG;
    Pricing-> RD  [label="surge map"];
    Notif  -> KF;

    KF -> Dispatch;
    Dispatch -> RD [label="rider geo"];
    Dispatch -> RT [label="ETA / route"];
    Dispatch -> Order [label="rider_assigned"];
    Dispatch -> ETA;
    ETA -> RT;
}
""",
                },
                {"type": "h3", "text": "Service Responsibilities"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>API Gateway:</strong> auth (JWT), rate limit, route to the correct service per client kind",
                        "<strong>Search:</strong> Elasticsearch over denormalised restaurant+dish docs, geo-filtered",
                        "<strong>Cart:</strong> Redis-backed session; re-validates price &amp; stock against Postgres at checkout",
                        "<strong>Order:</strong> owns the <code>order_id</code> state machine; only writer to <code>orders</code> table",
                        "<strong>Dispatch:</strong> consumes <code>food_ready_soon</code> events; assigns &amp; batches riders",
                        "<strong>Payment:</strong> pre-auth at place_order; capture on delivered; refund on cancel",
                        "<strong>Pricing/Surge:</strong> publishes per-hex multiplier; Cart &amp; Search read it",
                        "<strong>ETA / ML:</strong> separate predictors for prep, arrival, cooking_buffer, delivery",
                        "<strong>Notifications:</strong> Kafka consumer → push/SMS/email per state transition",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "The Three Lifecycles",
            "subtitle": "Customer order, restaurant prep, rider dispatch — one state machine",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The defining property of food delivery is that three independent actors "
                        "drive state transitions on the <em>same</em> <code>order_id</code>. The "
                        "Order service is the single source of truth; every other service "
                        "subscribes to the event stream and reacts. State changes go through "
                        "Postgres with a row-level lock so concurrent updates from rider, "
                        "restaurant, and customer cannot corrupt the order."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Order state machine. CREATED → CONFIRMED is the commit point (payment held + restaurant accepted). DELIVERED is terminal-success; CANCELLED is terminal-failure.",
                    "dot": r"""
digraph SM {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10,
          color="#2e57b8", fillcolor="#dbe6fb"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    CREATED      [label="CREATED\n(cart submitted)"];
    PAYMENT_HELD [label="PAYMENT_HELD"];
    CONFIRMED    [label="CONFIRMED\n(restaurant accepts)"];
    PREPARING    [label="PREPARING"];
    READY_SOON   [label="READY_SOON\n(prep_time - 4 min)"];
    RIDER_ASSIGNED [label="RIDER_ASSIGNED"];
    PICKED_UP    [label="PICKED_UP"];
    EN_ROUTE     [label="EN_ROUTE"];
    DELIVERED    [label="DELIVERED", fillcolor="#cbeedf", color="#1f8359"];
    CANCELLED    [label="CANCELLED", fillcolor="#fbd7c5", color="#c45a3b"];

    CREATED      -> PAYMENT_HELD [label="auth ok"];
    PAYMENT_HELD -> CONFIRMED    [label="restaurant accept"];
    PAYMENT_HELD -> CANCELLED    [label="restaurant reject\nrefund"];
    CONFIRMED    -> PREPARING    [label="prep_started"];
    PREPARING    -> READY_SOON   [label="ETA trigger"];
    READY_SOON   -> RIDER_ASSIGNED [label="dispatch"];
    RIDER_ASSIGNED -> PICKED_UP  [label="rider tap"];
    PICKED_UP    -> EN_ROUTE;
    EN_ROUTE     -> DELIVERED    [label="rider tap\ncapture payment"];
    CONFIRMED    -> CANCELLED    [label="customer cancel\n(grace 60s)"];
    PREPARING    -> CANCELLED    [label="restaurant fail\nfull refund"];
}
""",
                },
                {"type": "h3", "text": "Synchronization Rules"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Single writer:</strong> only Order service writes to <code>orders</code>; everyone else publishes intent via Kafka",
                        "<strong>Row lock:</strong> <code>SELECT ... FOR UPDATE</code> on the order row before transition; reject illegal transitions in SQL <code>CHECK</code>",
                        "<strong>Idempotency:</strong> every event carries <code>(order_id, transition, occurred_at)</code>; duplicates are no-ops",
                        "<strong>Forward-only:</strong> states form a DAG; no rollbacks (failed pickup → CANCELLED, not back to CONFIRMED)",
                        "<strong>Customer cancel grace:</strong> allowed for 60s after CONFIRMED; after that, only restaurant or system can cancel",
                    ],
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Database Schema",
            "subtitle": "Orders, items, and state transitions",
            "blocks": [
                {"type": "h3", "text": "Core Tables"},
                {
                    "type": "code",
                    "text": (
                        "-- Postgres: order header (one row per order)\n"
                        "CREATE TABLE orders (\n"
                        "  order_id        UUID PRIMARY KEY,\n"
                        "  customer_id     BIGINT NOT NULL,\n"
                        "  restaurant_id   BIGINT NOT NULL,\n"
                        "  rider_id        BIGINT NULL,                  -- assigned later\n"
                        "  status          VARCHAR(20) NOT NULL,         -- enum: CREATED..DELIVERED\n"
                        "  subtotal_cents  INT NOT NULL,\n"
                        "  delivery_fee    INT NOT NULL,\n"
                        "  surge_mult      NUMERIC(4,2) DEFAULT 1.00,\n"
                        "  payment_id      UUID,\n"
                        "  prep_eta_sec    INT,                          -- ML estimate at order time\n"
                        "  delivery_eta_sec INT,\n"
                        "  pickup_h3       BIGINT,                       -- H3 hex of restaurant\n"
                        "  drop_h3         BIGINT,                       -- H3 hex of customer\n"
                        "  created_at      TIMESTAMP DEFAULT NOW(),\n"
                        "  updated_at      TIMESTAMP DEFAULT NOW(),\n"
                        "  CHECK (status IN ('CREATED','PAYMENT_HELD','CONFIRMED',\n"
                        "                    'PREPARING','READY_SOON','RIDER_ASSIGNED',\n"
                        "                    'PICKED_UP','EN_ROUTE','DELIVERED','CANCELLED'))\n"
                        ");\n"
                        "CREATE INDEX idx_orders_rider     ON orders(rider_id, status);\n"
                        "CREATE INDEX idx_orders_rest_open ON orders(restaurant_id, status)\n"
                        "  WHERE status NOT IN ('DELIVERED','CANCELLED');\n\n"
                        "-- Items (line items per order)\n"
                        "CREATE TABLE order_items (\n"
                        "  order_id    UUID REFERENCES orders(order_id),\n"
                        "  line_no     INT,\n"
                        "  dish_id     BIGINT NOT NULL,\n"
                        "  name_snap   TEXT NOT NULL,            -- snapshot of name at order time\n"
                        "  price_snap  INT  NOT NULL,            -- snapshot of price at order time\n"
                        "  qty         INT  NOT NULL,\n"
                        "  options     JSONB,                    -- size, addons, no-onion, etc.\n"
                        "  PRIMARY KEY (order_id, line_no)\n"
                        ");\n\n"
                        "-- Append-only state transition log (audit + event sourcing)\n"
                        "CREATE TABLE order_events (\n"
                        "  event_id     BIGSERIAL PRIMARY KEY,\n"
                        "  order_id     UUID NOT NULL,\n"
                        "  from_status  VARCHAR(20),\n"
                        "  to_status    VARCHAR(20) NOT NULL,\n"
                        "  actor        VARCHAR(20),             -- customer|restaurant|rider|system\n"
                        "  reason       TEXT,\n"
                        "  occurred_at  TIMESTAMP DEFAULT NOW()\n"
                        ");\n"
                        "CREATE INDEX idx_oe_order ON order_events(order_id, occurred_at);"
                    ),
                },
                {"type": "h3", "text": "Atomic State Transition"},
                {
                    "type": "code",
                    "text": (
                        "-- Single transaction: lock + check + write + emit event\n"
                        "BEGIN;\n"
                        "  SELECT status FROM orders WHERE order_id = :id FOR UPDATE;\n"
                        "  -- application asserts allowed_transition(current, :next)\n"
                        "  UPDATE orders\n"
                        "     SET status = :next, updated_at = NOW()\n"
                        "   WHERE order_id = :id\n"
                        "     AND status = :expected_current;     -- optimistic guard\n"
                        "  INSERT INTO order_events(order_id, from_status, to_status, actor, reason)\n"
                        "  VALUES (:id, :expected_current, :next, :actor, :reason);\n"
                        "COMMIT;\n"
                        "-- Outbox row picked up by Debezium → Kafka topic `order.events`."
                    ),
                },
                {"type": "h3", "text": "Sharding & Partitioning"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Partition <code>orders</code></strong> by <code>created_at</code> (monthly) — old months drop fast, hot month is small",
                        "<strong>Shard by <code>customer_id</code> hash</strong> across 16 Postgres shards (Citus or app-level) for write scale",
                        "<strong>Co-locate <code>order_items</code></strong> on the same shard as <code>orders</code> via the same shard key",
                        "<strong>Read replicas</strong> for analytics &amp; restaurant dashboards (eventual consistency OK)",
                    ],
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Restaurant Menu Sync",
            "subtitle": "Inventory and price freshness",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The catalog is read &gt;&gt; write but writes are <em>operationally critical</em>: "
                        "a restaurant turning off an item must propagate everywhere within seconds, "
                        "or customers will order food the kitchen cannot make. This is the equivalent "
                        "of inventory in e-commerce, but with much lower SKU count and much higher "
                        "edit rate (in/out of stock toggles all day)."
                    ),
                },
                {"type": "h3", "text": "Write Path: Menu Edit"},
                {
                    "type": "numbered",
                    "items": [
                        "Restaurant edits item on tablet: <code>PATCH /menu/items/:id</code>",
                        "Menu service writes Postgres (source of truth); commits a row in the outbox",
                        "Debezium / outbox poller publishes to Kafka topic <code>menu.changes</code>",
                        "<strong>Search indexer</strong> consumes &amp; upserts the dish doc into Elasticsearch (target &lt;60s)",
                        "<strong>Cache invalidator</strong> deletes Redis keys <code>menu:rest:{id}</code> and per-dish keys",
                        "<strong>Cart re-validator</strong> scans active carts that contain that dish; flags them stale",
                    ],
                },
                {"type": "h3", "text": "Read Path: Menu Browse"},
                {
                    "type": "bullets",
                    "items": [
                        "Search: ES query with geo filter (<code>distance &lt;= 6 km</code>) + cuisine + open_now",
                        "Restaurant detail: Redis <code>menu:rest:{id}</code> (TTL 5 min); miss → Postgres + warm",
                        "Dish image &amp; static assets: served from CDN, cache-busted by version hash",
                        "<strong>Stale-while-revalidate</strong> in the customer app: render last menu instantly, then patch on response",
                    ],
                },
                {"type": "h3", "text": "Cart Re-validation at Checkout"},
                {
                    "type": "code",
                    "text": (
                        "# Pseudocode: revalidate before locking payment\n"
                        "def checkout(cart):\n"
                        "    fresh = db.fetch_dishes([li.dish_id for li in cart.items])\n"
                        "    issues = []\n"
                        "    for li in cart.items:\n"
                        "        d = fresh[li.dish_id]\n"
                        "        if not d.in_stock:\n"
                        "            issues.append(('OUT_OF_STOCK', li.dish_id))\n"
                        "        elif d.price_cents != li.price_snap:\n"
                        "            issues.append(('PRICE_CHANGED', li.dish_id,\n"
                        "                            li.price_snap, d.price_cents))\n"
                        "    if issues:\n"
                        "        return CartReview(issues)        # show user, require ACK\n"
                        "    return place_order(cart)             # snapshot prices into order_items"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Why snapshot prices",
                    "body": (
                        "Once an order is placed we copy <code>name</code> and <code>price</code> "
                        "into <code>order_items</code> as snapshots. The dish row is mutable; the "
                        "order is immutable. This is the same pattern Amazon uses: a price change "
                        "after checkout must never affect a placed order."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "ETA Composition",
            "subtitle": "Four ML models, not one",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "What the customer sees as a single \"35 min\" ETA is actually the sum of "
                        "four independent estimates, each with its own model and feature set. "
                        "Decomposing them lets us debug accuracy per stage and recompute only the "
                        "stale piece."
                    ),
                },
                {"type": "h3", "text": "The Four Components"},
                {
                    "type": "table",
                    "headers": ["Component", "What it estimates", "Key features"],
                    "rows": [
                        ["prep_time", "Restaurant cook + plate time",
                         "dish complexity, kitchen load, hour-of-day, restaurant historical p50/p90"],
                        ["rider_arrival", "Time for assigned rider to reach restaurant",
                         "rider current loc, traffic, mode (bike/scooter), batch leg"],
                        ["cooking_buffer", "Slack so rider doesn't wait at restaurant",
                         "prep variance, rider on-time risk; usually 1–3 min"],
                        ["delivery_time", "Restaurant → customer drop",
                         "OSRM route, traffic, building entry penalty, batch order"],
                    ],
                },
                {"type": "h3", "text": "Composition Formula"},
                {
                    "type": "code",
                    "text": (
                        "ETA_total = max(prep_time, rider_arrival + cooking_buffer)\n"
                        "          + delivery_time\n\n"
                        "# We display ETA_total to the customer.\n"
                        "# Internally we track each piece so we can recompute lazily:\n"
                        "#   - prep_time updates on PREPARING event\n"
                        "#   - rider_arrival updates on each rider GPS ping\n"
                        "#   - delivery_time updates when rider picks up\n"
                        "#\n"
                        "# Why max(): the rider must wait if they arrive before food is ready;\n"
                        "# the food must wait if it's ready before the rider arrives.\n"
                        "# cooking_buffer biases toward food-waiting (cold-food risk &lt; rider-idle)."
                    ),
                },
                {"type": "h3", "text": "Dispatch Trigger"},
                {
                    "type": "bullets",
                    "items": [
                        "Naive: assign rider at CONFIRMED → rider sits idle 10 min at busy restaurant",
                        "Better: assign at <code>READY_SOON = prep_time - rider_arrival - 1 min</code>",
                        "Trigger fires when <code>now &gt;= confirmed_at + (prep_time - predicted_rider_arrival - buffer)</code>",
                        "Implementation: scheduled task per order in Redis sorted set keyed by trigger_at",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why a separate ETA service",
                    "body": (
                        "The ETA service is consulted by Search (\"30–35 min delivery\"), Cart "
                        "(\"order before 7:45 to get it by 8:15\"), Dispatch (when to assign), and "
                        "the customer tracking screen (live updates). Centralising the model lets "
                        "us A/B test new estimators in one place."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Rider Dispatch & Batching",
            "subtitle": "Greedy nearest-neighbour with prep-time and same-direction constraints",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Dispatch is the hardest service. Like Uber it must match supply &amp; demand "
                        "in a hex grid in real time, but unlike Uber it has two extra constraints: "
                        "<strong>prep-time</strong> (don't assign too early) and <strong>batching</strong> "
                        "(stack up to 3 orders to lift rider earnings &amp; platform margin)."
                    ),
                },
                {"type": "h3", "text": "Candidate Selection"},
                {
                    "type": "numbered",
                    "items": [
                        "Compute <code>pickup_h3</code> (H3 res 9, ~150m hex) and search rings 0..3 around it",
                        "Pull online riders in those hexes from Redis <code>GEORADIUS</code> / H3 set",
                        "Filter: rider <code>state IN (FREE, BATCH_OPEN)</code>, capacity left, vehicle type matches",
                        "Score each candidate: <code>cost = ETA_to_restaurant + α * detour + β * (1/rider_acceptance)</code>",
                        "Pick top-5; offer to #1 with a 12-second timeout; on decline, fall through",
                    ],
                },
                {"type": "h3", "text": "Greedy Batching Algorithm"},
                {
                    "type": "code",
                    "text": (
                        "# Greedy nearest-neighbour batching with same-direction constraint.\n"
                        "# Called when a new order_O reaches READY_SOON.\n"
                        "#\n"
                        "# Goal: either (a) start a new solo trip, or (b) graft order_O onto\n"
                        "# an existing rider's route if it doesn't blow either ETA.\n"
                        "\n"
                        "MAX_BATCH        = 3                  # never stack more than 3\n"
                        "MAX_DETOUR_SEC   = 6 * 60             # 6 min per added stop\n"
                        "BEARING_TOL_DEG  = 35                 # 'same direction' window\n"
                        "ETA_BREACH_SEC   = 4 * 60             # don't make any order &gt; 4min late\n"
                        "\n"
                        "def assign(order_O):\n"
                        "    cands = nearby_riders(order_O.pickup_h3, rings=3)\n"
                        "    best, best_cost = None, INF\n"
                        "\n"
                        "    for r in cands:\n"
                        "        if r.state == 'FREE':\n"
                        "            cost = solo_cost(r, order_O)\n"
                        "            if cost &lt; best_cost:\n"
                        "                best, best_cost = ('SOLO', r, None), cost\n"
                        "            continue\n"
                        "\n"
                        "        if r.state == 'BATCH_OPEN' and len(r.legs) &lt; MAX_BATCH:\n"
                        "            # Same-direction check on bearings\n"
                        "            if bearing_diff(r.next_drop, order_O.drop) &gt; BEARING_TOL_DEG:\n"
                        "                continue\n"
                        "            # Insert order_O at best position; recompute legs\n"
                        "            new_legs, detour = best_insertion(r.legs, order_O)\n"
                        "            if detour &gt; MAX_DETOUR_SEC:\n"
                        "                continue\n"
                        "            if any(eta_breach(l) &gt; ETA_BREACH_SEC for l in new_legs):\n"
                        "                continue\n"
                        "            cost = batch_cost(r, new_legs, detour)\n"
                        "            if cost &lt; best_cost:\n"
                        "                best, best_cost = ('BATCH', r, new_legs), cost\n"
                        "\n"
                        "    if not best:\n"
                        "        return queue_for_retry(order_O)   # back-off, surge area\n"
                        "    return offer(best)                    # 12s accept window"
                    ),
                },
                {"type": "h3", "text": "Batch Eligibility"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Same restaurant cluster:</strong> pickups within 200m and prep windows overlap",
                        "<strong>Same direction:</strong> drop bearings within 35° of each other",
                        "<strong>Detour budget:</strong> additional stop adds ≤ 6 minutes per existing leg",
                        "<strong>No ETA breach:</strong> no customer's promised time slips by more than 4 minutes",
                        "<strong>Cap:</strong> max 3 orders per rider; cold-food risk grows non-linearly",
                    ],
                },
                {"type": "h3", "text": "Dynamic Re-routing"},
                {
                    "type": "bullets",
                    "items": [
                        "Re-evaluate the leg order on every rider GPS ping (4s interval)",
                        "If traffic recomputes leg ordering and it doesn't breach ETA, swap silently",
                        "If a leg <em>will</em> breach: notify customer + suppress further insertions on that rider",
                        "Mid-trip cancel: drop the leg, refund, recompute remaining route",
                    ],
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Surge & Busy-Area Pricing",
            "subtitle": "Closing the supply gap",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "When demand outstrips rider supply in a hex, ETAs blow up and orders "
                        "stall. Surge does two things at once: it <strong>damps demand</strong> "
                        "(higher fee filters out price-sensitive orders) and "
                        "<strong>summons supply</strong> (riders see a heatmap and self-relocate)."
                    ),
                },
                {"type": "h3", "text": "Surge Computation"},
                {
                    "type": "code",
                    "text": (
                        "# Per H3 hex, every 60 seconds:\n"
                        "open_orders   = count(orders waiting for rider in hex over last 5 min)\n"
                        "free_riders   = count(riders idle/free in hex)\n"
                        "p90_wait_sec  = percentile90(time-to-rider_assigned in hex)\n"
                        "\n"
                        "demand_pressure = open_orders / max(free_riders, 1)\n"
                        "wait_pressure   = clamp(p90_wait_sec / 180.0, 0, 3)   # 3min target\n"
                        "\n"
                        "surge = round(1.0 + 0.4*max(0, demand_pressure-1)\n"
                        "                  + 0.3*max(0, wait_pressure-1), 1)\n"
                        "surge = clamp(surge, 1.0, 2.5)                        # cap"
                    ),
                },
                {"type": "h3", "text": "How It Surfaces"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Customer:</strong> delivery fee × surge_mult shown <em>before</em> they tap Place Order",
                        "<strong>Rider:</strong> heatmap colours hexes by surge; rider self-relocates to earn more",
                        "<strong>Restaurant:</strong> unaffected — restaurant takes their normal cut",
                        "<strong>Storage:</strong> 60s-resolution surge_map kept in Redis, hex → multiplier",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Surge gotchas",
                    "body": (
                        "Cap surge (here 2.5×) to avoid PR disasters during emergencies (cap to 1.0× "
                        "during declared natural disasters). Snapshot surge_mult onto the order at "
                        "checkout so the price the user saw is the price they're charged."
                    ),
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Search & Discovery",
            "subtitle": "Catalog at 50K QPS",
            "blocks": [
                {"type": "h3", "text": "Index Structure"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>One Elasticsearch index per metro;</strong> reduces shard count and keeps geo queries local",
                        "<strong>Document = restaurant</strong> with nested dish list (denormalised)",
                        "<strong>Geo field</strong> on restaurant location; <code>geo_distance</code> filter at query time",
                        "<strong>Computed fields:</strong> <code>open_now</code>, <code>avg_prep_time</code>, <code>delivery_eta</code>, <code>rating</code>, <code>price_band</code>",
                    ],
                },
                {"type": "h3", "text": "Ranking Signals"},
                {
                    "type": "table",
                    "headers": ["Signal", "Why"],
                    "rows": [
                        ["Distance + ETA", "Closer = faster &amp; cheaper to deliver"],
                        ["Rating × order count", "Bayesian average; avoids one-review outliers"],
                        ["Personalisation", "User's past cuisines, repeat orders"],
                        ["Operational health", "Cancellation rate &amp; on-time rate downweight bad actors"],
                        ["Sponsored", "Paid placement, capped &amp; labelled"],
                    ],
                },
                {"type": "h3", "text": "Indexing Pipeline"},
                {
                    "type": "bullets",
                    "items": [
                        "Postgres (truth) → outbox → Kafka <code>menu.changes</code>",
                        "Indexer service consumes, builds doc, upserts to ES &amp; CDN-cached static menu",
                        "Hot path edits (in_stock toggle): high-priority partition, target latency &lt;30s",
                        "Cold path edits (dish photo, description): low-priority, &lt;5 min OK",
                    ],
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "Comparison: Swiggy vs Uber vs DoorDash",
            "subtitle": "And batch-1 vs batch-2 economics",
            "blocks": [
                {"type": "h3", "text": "Platform Comparison"},
                {
                    "type": "table",
                    "headers": ["Aspect", "Uber Rideshare", "Swiggy / Deliveroo", "DoorDash"],
                    "rows": [
                        ["Sides", "2", "3 (customer/restaurant/rider)", "3 (same)"],
                        ["Trip time predictability", "Known after pickup", "Variable prep_time + traffic", "Same as Swiggy"],
                        ["Batching strategy", "UberPool: shared mid-route", "Stack 2–3 orders, same-direction", "DoubleDash: 2 orders/trip"],
                        ["Surge unit", "Per hex, immediate", "Per hex, demand+wait pressure", "Peak Pay (per zone, scheduled)"],
                        ["Avg delivery radius", "5–25 km", "&lt;4 km hyperlocal", "~4 km"],
                        ["Restaurant integration", "n/a", "Tablet POS push", "Mostly tablet; some POS"],
                        ["Rider mode", "Car", "Bike/scooter dominant", "Car &amp; bike"],
                        ["Order size", "1 person", "1–4 people, multi-item", "Same"],
                    ],
                },
                {"type": "h3", "text": "Batch-1 vs Batch-2 Unit Economics"},
                {
                    "type": "table",
                    "headers": ["Metric", "Solo (batch=1)", "Stacked (batch=2)"],
                    "rows": [
                        ["Avg trip time", "26 min", "32 min"],
                        ["Trips/hour", "2.3", "1.9 (but 3.8 deliveries)"],
                        ["Deliveries/hour", "2.3", "3.8"],
                        ["Rider revenue/hour", "$15", "$22 (+47%)"],
                        ["Platform CoG/order", "$5.20", "$3.40 (-35%)"],
                        ["Customer ETA delta", "0", "+4 min on second drop"],
                        ["Cold-food risk", "Low", "Medium (food sits during 1st drop)"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Why batching matters",
                    "body": (
                        "Batching is the single biggest lever on food-delivery margin. Going from "
                        "100% solo to 30% stacked drops cost-per-order by ~10%, which is the "
                        "difference between a profitable and unprofitable city. The constraint is "
                        "customer trust — push batching too hard and ETAs slip, NPS craters."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Failure Modes",
            "subtitle": "What goes wrong, and how to recover",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["Restaurant tablet offline",
                         "Orders queue without acceptance",
                         "Heartbeat &gt; 30s lost",
                         "SMS fallback to manager; auto-cancel + refund after 90s"],
                        ["Rider GPS gap",
                         "Stale dispatch decisions; bad ETA",
                         "No ping &gt; 30s",
                         "Dead-reckon from last vector; freeze rider state; re-dispatch if &gt; 2 min"],
                        ["Payment provider down",
                         "Cannot pre-auth → orders fail at checkout",
                         "Provider error rate &gt; 5%",
                         "Failover to secondary PSP; allow COD as fallback"],
                        ["Postgres primary down",
                         "Order writes block",
                         "Replication lag spike, write timeout",
                         "Auto-promote replica (Patroni); 30–60s blackout"],
                        ["Elasticsearch lag",
                         "Stale catalog, in-stock toggles invisible",
                         "Indexer lag &gt; 60s",
                         "Reduce concurrency on cold edits, scale indexer; show 'temp unavailable' on stale items"],
                        ["Routing service (OSRM) slow",
                         "ETA inaccuracy, dispatch delays",
                         "p99 latency &gt; 1s",
                         "Fall back to haversine × city factor; degrade ETA precision"],
                        ["Surge runaway",
                         "Customer outrage, PR risk",
                         "Surge &gt; 2.5× sustained",
                         "Hard cap; manual kill-switch per metro"],
                        ["Rider mass cancel",
                         "Orders pile up, prep waste",
                         "Acceptance rate drops &gt; 30%",
                         "Trigger surge + ops bonus; throttle new orders in hex"],
                        ["Kafka lag",
                         "Notifications &amp; dispatch delayed",
                         "Consumer lag &gt; 30s",
                         "Add partitions; spill to dead-letter; replay"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Cooking-cost asymmetry",
                    "body": (
                        "Once an order is CONFIRMED, the restaurant has spent ingredients and "
                        "labour. Any cancel after CONFIRMED has a real cash cost. Design the "
                        "cancel path so it's cheap to cancel <em>before</em> CONFIRMED (60s "
                        "customer grace) and expensive after (only restaurant or system, with "
                        "compensation policy)."
                    ),
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Design Trade-offs",
            "subtitle": "What we picked and why",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Decision", "Choice", "Trade-off"],
                    "rows": [
                        ["Order state authority", "Single Order service",
                         "Bottleneck risk; but eliminates split-brain across rider/restaurant/customer"],
                        ["Menu freshness", "Eventual (&lt;60s) in search; strong at checkout",
                         "Customers may see stale availability briefly; cart re-validation catches it"],
                        ["Price snapshot", "Snapshot at order_items write",
                         "Price changes can't affect placed orders; menu edits are safe"],
                        ["Dispatch trigger", "READY_SOON (prep_time - rider_arrival)",
                         "Rider doesn't sit idle; risks late dispatch if prep prediction is wrong"],
                        ["Batching cap", "3 orders max",
                         "Bigger batches earn more but cold-food &amp; ETA-breach risk grows non-linearly"],
                        ["Same-direction window", "35° bearing tolerance",
                         "Tighter = fewer batches; looser = bigger detours"],
                        ["ETA model", "4 separate predictors",
                         "More moving parts; but each component is debuggable + replaceable"],
                        ["Surge cap", "2.5×",
                         "Lost revenue at extreme demand; protects brand &amp; regulator scrutiny"],
                        ["Datastore mix", "Postgres + Redis + ES + Kafka",
                         "Operational complexity; but each tool fits one read pattern"],
                        ["Geo index", "H3 (Uber's lib)",
                         "Hex cells distort less than lat/lon grid; ring queries cheap"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Pick your hill",
                    "body": (
                        "The two design hills you should die on in an interview: "
                        "(1) <strong>order state machine is single-writer</strong>, all sides "
                        "publish intents; (2) <strong>batching is the margin lever</strong>, "
                        "everything in dispatch (geo, ETA, surge) exists to make safe batching "
                        "possible."
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
                        "If you've already discussed Uber rideshare, the interviewer almost "
                        "always asks for food delivery as a follow-up. They want to see you "
                        "<em>not</em> reuse the rideshare answer wholesale. Anchor on the three "
                        "differences: third side (restaurant), variable service time (prep), and "
                        "batching."
                    ),
                },
                {"type": "h3", "text": "45-Minute Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (3 min):</strong> three sides, ~5M orders/day, ~60 orders/sec peak, ~50K search QPS",
                        "<strong>Lifecycle (5 min):</strong> draw the order state machine; emphasise single-writer Order service",
                        "<strong>High-level arch (5 min):</strong> three clients → API GW → 8 services → Postgres + Redis + ES + Kafka",
                        "<strong>Schema (5 min):</strong> orders, order_items (price snapshot!), order_events (audit log)",
                        "<strong>Menu sync (5 min):</strong> &lt;60s search index lag, cart re-validation at checkout",
                        "<strong>ETA composition (5 min):</strong> four separate models; <code>max(prep, rider_arr+buffer) + delivery</code>",
                        "<strong>Dispatch + batching (8 min):</strong> H3 hex → candidates → score → greedy batch insertion",
                        "<strong>Surge (3 min):</strong> per-hex multiplier, capped, snapshotted on order",
                        "<strong>Failures + trade-offs (5 min):</strong> tablet offline, payment outage, batching cap"
                    ],
                },
                {"type": "h3", "text": "Talking Points That Score"},
                {
                    "type": "bullets",
                    "items": [
                        "“Three sides, one order_id state machine, single writer.” — shows you understand consistency boundary",
                        "“Snapshot price into order_items.” — shows you've thought about menu mutability",
                        "“ETA = max(prep, rider_arrival + buffer) + delivery.” — shows you understand the synchronisation",
                        "“Dispatch fires on READY_SOON, not CONFIRMED.” — shows you know rider-idle is a real cost",
                        "“Batch cap 3, bearing tolerance 35°, detour ≤ 6 min.” — concrete numbers beat hand-waving",
                        "“Surge capped at 2.5×, snapshot on order.” — shows you've thought about brand &amp; legal risk",
                        "“H3 hex grid for geo.” — same vocabulary as Uber Eng",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Restaurant rejects after CONFIRMED — what happens?</strong> A: System cancel + full refund + chargeback to restaurant; reliability score drops; repeat offenders auto-paused.",
                        "<strong>Q: Customer wants to add an item after placing the order.</strong> A: Treat as new mini-order to same restaurant; new payment, new dispatch decision (often piggybacks on same rider).",
                        "<strong>Q: How do you stop riders from gaming surge?</strong> A: Detect cluster of accept-then-cancel; require min on-time rate; pay surge as bonus on completion, not on accept.",
                        "<strong>Q: Cold food complaints?</strong> A: Track temperature-proxy = elapsed since food_ready; cap batches when proxy &gt; 8 min; refund automatically.",
                        "<strong>Q: How is this different from Uber?</strong> A: Three sides not two; variable service time (prep); batching across pickups; restaurant inventory acts as a third consistency boundary.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize these numbers",
                    "body": (
                        "5M orders/day &nbsp;·&nbsp; ~60 orders/sec peak &nbsp;·&nbsp; "
                        "50K search QPS &nbsp;·&nbsp; 500K riders &nbsp;·&nbsp; "
                        "500K restaurants &nbsp;·&nbsp; ETA MAE &lt;3 min &nbsp;·&nbsp; "
                        "menu propagation &lt;60s &nbsp;·&nbsp; batch cap 3 &nbsp;·&nbsp; "
                        "surge cap 2.5×."
                    ),
                },
            ],
        },
    ],
}
