"""Source for `07 - Amazon E-commerce.pdf` (regenerated with errata applied)."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design an E-commerce System",
    "subtitle": "Microservices, Inventory Management & Order Orchestration",
    "read_time": "~ 35 minute read",
    "short_title": "Design an E-commerce System",
    "sections": [
        # ---- 01 ------------------------------------------------------
        {
            "num": "01",
            "title": "Problem Overview",
            "subtitle": "Building Amazon-scale e-commerce",
            "blocks": [
                {
                    "type": "lead",
                    "text": (
                        "Designing an e-commerce platform requires balancing availability, "
                        "consistency, and scale. Amazon handles <strong>~500M products</strong>, "
                        "<strong>~1B registered users</strong> (~300M MAU), and processes on the "
                        "order of <strong>1.6M orders/day</strong> on an average day, with peaks of "
                        "<strong>10–13M+ orders/day</strong> during Prime Day and Cyber Week."
                    ),
                },
                {"type": "h3", "text": "The Scale Problem"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Users:</strong> 1 billion registered; ~300M monthly active",
                        "<strong>Catalog:</strong> 500M products across all categories (electronics, clothing, books, groceries, …)",
                        # ERRATUM 1: order volume figures corrected.
                        "<strong>Average traffic:</strong> ~1.6M orders/day → <strong>~18 orders/sec</strong> sustained",
                        "<strong>Peak traffic:</strong> ~13M orders/day on Prime Day → <strong>~150 orders/sec</strong>, with intra-day spikes of <strong>500–1,000 ops/sec</strong> in the first hour of a major sale",
                        "<strong>Search QPS:</strong> ~500K queries/sec globally",
                        "<strong>Read-heavy:</strong> 99% reads (browse, search, reviews) vs. 1% writes (orders, updates)",
                    ],
                },
                {"type": "h3", "text": "Key Challenges"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Inventory consistency:</strong> prevent overselling; real-time reservation conflicts across warehouses",
                        "<strong>Order atomicity:</strong> payment → inventory deduction → fulfillment must look transactional across services",
                        "<strong>Search relevance:</strong> 500M products; millisecond response; personalized by user history",
                        "<strong>Global distribution:</strong> regional warehouses, VAT compliance, currency conversion",
                        "<strong>Recommendations:</strong> personalized homepage; “customers also bought” at scale",
                    ],
                },
            ],
        },
        # ---- 02 ------------------------------------------------------
        {
            "num": "02",
            "title": "Clarifying Questions",
            "subtitle": "Scope and assumptions",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Question", "Answer / Assumption"],
                    "rows": [
                        ["Single product or multi-vendor marketplace?",
                         "Single vendor (Amazon.com); seller accounts optional (Phase 2)"],
                        ["Global or single-region?",
                         "Global (multi-region: US, EU, APAC); local currency &amp; tax"],
                        ["Inventory real-time or eventual consistency ok?",
                         "Real-time for high-velocity SKUs; eventual ok for slow movers"],
                        ["Search: full-text only or faceted?",
                         "Full-text + facets (price, rating, seller, availability)"],
                        ["Return / cancellation handling?",
                         "Out of scope; assume successful orders only"],
                        ["Payment processing (in-house or 3rd party)?",
                         "3rd party (Stripe, PayPal); async webhook confirmation"],
                        ["Seller onboarding (FBA, FBM)?",
                         "FBA only (Fulfillment by Amazon); logistics out of scope"],
                    ],
                },
            ],
        },
        # ---- 03 ------------------------------------------------------
        {
            "num": "03",
            "title": "Capacity Estimation",
            "subtitle": "Numbers to anchor your design",
            "blocks": [
                {"type": "h3", "text": "Product Catalog"},
                {
                    "type": "bullets",
                    "items": [
                        "500M products × 2 KB average metadata = <strong>~1 TB</strong> in product catalog DB",
                        "Storage for images: 5 images/product × 500 KB average = <strong>1.25 PB</strong> in S3, served via CDN",
                        "Indexing overhead: Elasticsearch inverted index ~30% of raw data = <strong>~300 GB</strong> across 50 shards",
                    ],
                },
                {"type": "h3", "text": "Order Volume"},
                {
                    "type": "bullets",
                    "items": [
                        # ERRATUM 1 propagated.
                        "Average: <strong>~1.6M orders/day → ~18 orders/sec</strong>",
                        "Peak (Prime Day / Cyber Monday): <strong>~13M orders/day → ~150 orders/sec</strong>; flash-sale opening spikes hit <strong>500–1,000 ops/sec</strong>",
                        # ERRATUM 2: corrected storage derivation.
                        "Order corpus: 1.6M × 365 × 10 yr ≈ <strong>5.84B orders</strong>",
                        "Order record size: ~5 KB (header + items + addresses + status history) → <strong>~29 TB hot</strong> in PostgreSQL",
                        "Fulfillment queue: Kafka topic; ~1.6M events/day average, ~13M/day peak; 7-day retention ≈ <strong>0.4–0.6 TB</strong>",
                    ],
                },
                {"type": "h3", "text": "Search QPS"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>500K queries/sec</strong> globally",
                        "Elasticsearch latency target: <strong>&lt;100 ms p99</strong>",
                        "Shards needed: ~500K QPS ÷ 1,000 QPS/shard = <strong>500 primary shards</strong>; replicated 3× = <strong>1,500 shard copies</strong>",
                        "Replication factor: <strong>RF = 3</strong> for high availability",
                    ],
                },
                {"type": "h3", "text": "Bandwidth & Storage"},
                {
                    "type": "bullets",
                    "items": [
                        "Product images: 5 × 500 KB × 500M = <strong>1.25 PB</strong>; most served from CloudFront CDN",
                        "Product detail pages: 300M MAU × 10 page views/month ÷ 30 days ≈ <strong>100M req/day ≈ 1,157 req/sec</strong>",
                        "Image bandwidth: ~1,000 req/sec × 500 KB ≈ <strong>500 GB/day = 50 MB/sec</strong> sustained",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "Orders: <strong>~18 ops/sec avg, ~150 ops/sec peak</strong> &nbsp;·&nbsp; "
                        "Order corpus: <strong>5.84B rows / ~29 TB</strong> hot &nbsp;·&nbsp; "
                        "Search QPS: <strong>500K/sec</strong> &nbsp;·&nbsp; "
                        "ES shards: <strong>500 × RF=3</strong> &nbsp;·&nbsp; "
                        "Catalog: <strong>~1 TB</strong> + <strong>1.25 PB</strong> images"
                    ),
                },
            ],
        },
        # ---- 04 ------------------------------------------------------
        {
            "num": "04",
            "title": "System Architecture",
            "subtitle": "Microservices layered design",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "The platform is split into a <strong>client tier</strong>, a "
                        "<strong>service tier</strong> of stateless microservices, and a "
                        "<strong>data tier</strong> sized for each access pattern. The CDN absorbs "
                        "image and static page traffic; the API gateway terminates auth and rate "
                        "limits; each service owns its own datastore."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Client → CDN → API Gateway fans out to stateless microservices; each service owns its datastore. Dashed edges are async (Kafka).",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=9, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Client"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Client [label="Web / Mobile /\nDesktop", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        CDN [label="CDN\n(images, static)", fillcolor="#cbeedf"];
        GW  [label="API Gateway\n(auth, rate-limit)", fillcolor="#cbeedf"];
    }
    subgraph cluster_svc {
        label="Microservices"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        Catalog [label="Product\nCatalog", fillcolor="#fff2c9"];
        Cart    [label="Cart",            fillcolor="#fff2c9"];
        Order   [label="Order",           fillcolor="#fff2c9"];
        Pay     [label="Payment",         fillcolor="#fff2c9"];
        Inv     [label="Inventory",       fillcolor="#fff2c9"];
        Search  [label="Search",          fillcolor="#fff2c9"];
        Rec     [label="Recommendation",  fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        PG    [label="PostgreSQL\n(orders, products)", fillcolor="#ead7fb"];
        DDB   [label="DynamoDB\n(inventory, sessions)", fillcolor="#ead7fb"];
        Redis [label="Redis\n(cart, hot cache)",        fillcolor="#ead7fb"];
        Kafka [label="Kafka\n(events, CDC)",            fillcolor="#fbd7c5"];
        ES    [label="Elasticsearch\n(search index)",   fillcolor="#ead7fb"];
        RS    [label="Redshift\n(analytics)",           fillcolor="#ead7fb"];
    }

    Client -> CDN  [label="static (95%)", color="#1f8359"];
    Client -> GW   [label="API"];
    GW -> Catalog;
    GW -> Cart;
    GW -> Order;
    GW -> Pay;
    GW -> Inv;
    GW -> Search;
    GW -> Rec;

    Catalog -> PG;
    Catalog -> Redis [label="cache",  style=dashed];
    Cart    -> Redis;
    Order   -> PG;
    Pay     -> PG;
    Inv     -> DDB;
    Search  -> ES;
    Rec     -> Redis [label="embeds", style=dashed];

    Order   -> Kafka [label="OrderCreated",      style=dashed];
    Pay     -> Kafka [label="PaymentCaptured",   style=dashed];
    Inv     -> Kafka [label="InventoryReserved", style=dashed];
    Catalog -> Kafka [label="CDC",               style=dashed];
    Kafka   -> ES    [label="index",             style=dashed];
    Kafka   -> RS    [label="ETL",               style=dashed];
}
""",
                },
                {"type": "h3", "text": "Three-Tier Model"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Client layer:</strong> web browser, mobile app, desktop; HTTPS to load balancer",
                        "<strong>Service layer:</strong> stateless microservices (Catalog, Search, Inventory, Order, Payment, Cart, Recommendations, Notifications)",
                        "<strong>Data layer:</strong> PostgreSQL (orders/products), DynamoDB (inventory), Redis (cache/cart), Elasticsearch (search), S3 (images), Kafka (events), Redshift (analytics)",
                    ],
                },
                {"type": "h3", "text": "Load Balancer & API Gateway"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Load balancer:</strong> distributes traffic across API gateway instances (e.g., AWS ALB); 5-second health checks",
                        "<strong>API gateway:</strong> single entry point; rate limiting, request validation, routing to microservices",
                        "<strong>Service discovery:</strong> dynamic registry (Consul, Eureka, or Kubernetes service mesh); resolves DNS to healthy instances",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Core Design Decisions",
            "subtitle": "Why this architecture",
            "blocks": [
                {"type": "h3", "text": "Microservices Decomposition"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Product Catalog:</strong> read-heavy; immutable metadata; caches product details in Redis",
                        "<strong>Search:</strong> Elasticsearch backend; full-text search, faceting, autocomplete",
                        "<strong>Inventory:</strong> single source of truth for stock; enforces invariants via optimistic locking",
                        "<strong>Cart:</strong> user's temporary shopping cart; stored in Redis (session-like); TTL = 30 days",
                        "<strong>Order:</strong> creates orders; coordinates Inventory &amp; Payment; publishes events to Kafka",
                        "<strong>Payment:</strong> PCI-compliant; delegates to Stripe/PayPal; handles retries &amp; idempotency",
                        "<strong>Recommendation:</strong> offline batch + online serving; collaborative filtering + content-based",
                        "<strong>Notification:</strong> sends order confirmation, shipment updates, promotional emails",
                    ],
                },
                {"type": "h3", "text": "Eventual Consistency in Inventory"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Approach:</strong> optimistic locking with version numbers; on conflict, client retries with the fresh inventory state",
                        "<strong>Conflict resolution:</strong> “Sorry, only 2 left” message; offer similar items from Recommendations",
                        "<strong>Saga pattern:</strong> if payment succeeds but inventory reserve fails, compensation marks payment for refund",
                        "<strong>Reservation TTL:</strong> inventory hold expires after 15 min if order isn't confirmed; stock returns to the pool",
                    ],
                },
                {"type": "h3", "text": "Asynchronous Event-Driven Pipeline"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Kafka broker:</strong> central event bus; services publish domain events (<code>OrderCreated</code>, <code>PaymentConfirmed</code>, <code>InventoryReserved</code>)",
                        "<strong>Consumers:</strong> Notification, Fulfillment, Analytics subscribe independently",
                        "<strong>Benefits:</strong> loose coupling; if Notification is down, the order is still created and Kafka retains the event for replay",
                        "<strong>Retention:</strong> 7 days; allows late subscribers to catch up",
                    ],
                },
                {"type": "h3", "text": "Kafka Partitioning"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Topic <code>orders.created</code>:</strong> peak ~150 ops/sec sustained, 1K ops/sec in flash bursts; partition by <code>user_id</code> for ordered per-user history",
                        "<strong>Partition count:</strong> ~64 (≈15 ops/sec/partition at peak; 4× headroom for hot users) with RF = 3",
                        "<strong>Topic <code>inventory.reserved</code>:</strong> partition by <code>sku</code>; ~32 partitions to colocate writes for hot SKUs without excessive fan-out",
                        "<strong>Topic <code>catalog.cdc</code>:</strong> partition by <code>product_id</code> for index ordering into Elasticsearch",
                    ],
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Data Models",
            "subtitle": "Schema design",
            "blocks": [
                {"type": "h3", "text": "Key Tables (PostgreSQL)"},
                {
                    "type": "code",
                    "text": (
                        "-- Product Catalog\n"
                        "CREATE TABLE products (\n"
                        "  product_id    BIGINT PRIMARY KEY,\n"
                        "  title         VARCHAR(255),\n"
                        "  description   TEXT,\n"
                        "  price         DECIMAL(10,2),\n"
                        "  category_id   INT,\n"
                        "  seller_id     BIGINT,\n"
                        "  rating        FLOAT,\n"
                        "  reviews_count INT,\n"
                        "  created_at    TIMESTAMP,\n"
                        "  updated_at    TIMESTAMP,\n"
                        "  INDEX idx_category (category_id)\n"
                        ");\n\n"
                        "-- Inventory (per-warehouse stock; optimistic lock)\n"
                        "CREATE TABLE inventory (\n"
                        "  sku          VARCHAR(50) PRIMARY KEY,\n"
                        "  product_id   BIGINT NOT NULL,\n"
                        "  quantity     INT,\n"
                        "  reserved     INT DEFAULT 0,\n"
                        "  version      INT DEFAULT 0,\n"
                        "  warehouse_id INT,\n"
                        "  updated_at   TIMESTAMP,\n"
                        "  UNIQUE (product_id, warehouse_id),\n"
                        "  INDEX idx_product (product_id)\n"
                        ");\n\n"
                        "-- Orders (sharded by user_id)\n"
                        "CREATE TABLE orders (\n"
                        "  order_id         BIGINT PRIMARY KEY,\n"
                        "  user_id          BIGINT NOT NULL,\n"
                        "  order_date       TIMESTAMP,\n"
                        "  total_amount     DECIMAL(10,2),\n"
                        "  status           ENUM('created','payment_pending',\n"
                        "                        'confirmed','shipped','delivered'),\n"
                        "  shipping_address TEXT,\n"
                        "  INDEX idx_user   (user_id),\n"
                        "  INDEX idx_status (status)\n"
                        ");\n\n"
                        "-- Order line items\n"
                        "CREATE TABLE order_items (\n"
                        "  order_item_id BIGINT PRIMARY KEY,\n"
                        "  order_id      BIGINT NOT NULL,\n"
                        "  product_id    BIGINT,\n"
                        "  sku           VARCHAR(50),\n"
                        "  quantity      INT,\n"
                        "  price         DECIMAL(10,2),\n"
                        "  INDEX idx_order (order_id)\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "Redis Keys (Cache & Sessions)"},
                {
                    "type": "code",
                    "text": (
                        "# Cart (session-scoped)\n"
                        "cart:<user_id>      -> { product_id: quantity, ... }   # TTL = 30d\n\n"
                        "# Session\n"
                        "session:<sid>       -> { user_id, logged_in_at }       # TTL = 24h\n\n"
                        "# Product detail cache\n"
                        "product:<id>        -> JSON(title, price, rating, ...) # TTL = 1h\n\n"
                        "# Inventory cache (read-through)\n"
                        "inventory:<sku>     -> { quantity, reserved, version } # TTL = 5m\n\n"
                        "# Idempotency (per checkout request)\n"
                        "idem:<merchant>:<k> -> { status, body_hash, response } # TTL = 24h"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Why DynamoDB for inventory?",
                    "body": (
                        "Inventory writes hit ~150 ops/sec average and burst to 1K+ ops/sec on a flash "
                        "sale, all on a tiny key space (the SKU). DynamoDB gives single-digit-ms "
                        "single-row writes with conditional updates (the optimistic-lock primitive) "
                        "without us having to shard a relational DB by SKU. Postgres still owns the "
                        "money path (orders + payments) where ACID joins matter."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Order Placement Pipeline",
            "subtitle": "Write path and saga pattern",
            "blocks": [
                {"type": "h3", "text": "Request Flow"},
                {
                    "type": "numbered",
                    "items": [
                        "User adds items to cart (Cart Service stores in Redis)",
                        "User clicks <em>Place Order</em>; Order Service receives the checkout request (with an idempotency key)",
                        "Order Service initiates payment via Payment Service (calls Stripe API)",
                        "Payment Service performs fraud check + card auth; returns success/failure",
                        "On success: Order Service calls Inventory Service to reserve stock (<code>sku, quantity, version</code>)",
                        "Inventory Service validates stock and updates with optimistic locking; returns <code>reservation_id</code>",
                        "Order Service creates the Order record (<code>status='confirmed'</code>); publishes <code>OrderCreated</code> to Kafka",
                        "Kafka triggers Fulfillment Service (async) → updates the warehouse system and starts picking",
                        "Kafka triggers Notification Service → sends the order-confirmation email",
                        "Client receives confirmation; order complete",
                    ],
                },
                {
                    "type": "diagram",
                    "caption": "Saga: each forward step has a compensation. Compensation arrows fire only on the failure of the next forward step.",
                    "dot": r"""
digraph Saga {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=9, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8];

    Start  [label="Checkout\nrequested", fillcolor="#dbe6fb"];
    OC     [label="Order\nCreated\n(status=pending)", fillcolor="#fff2c9"];
    Res    [label="Reserve\nInventory\n(optimistic lock)", fillcolor="#fff2c9"];
    Pay    [label="Capture\nPayment\n(Stripe)", fillcolor="#fff2c9"];
    Conf   [label="Confirm\nOrder\n(status=confirmed)", fillcolor="#cbeedf"];

    Fail   [label="Order\nFailed\n(compensated)", fillcolor="#fbd7c5"];

    Start -> OC   [label="OrderCreated", color="#1f8359"];
    OC    -> Res  [label="reserve",      color="#1f8359"];
    Res   -> Pay  [label="capture",      color="#1f8359"];
    Pay   -> Conf [label="confirm",      color="#1f8359"];

    /* Compensations on failure */
    Res  -> Fail [label="reserve fails →\ncancel order",                style=dashed, color="#c45a3b"];
    Pay  -> Fail [label="payment fails →\nrelease inventory + cancel",  style=dashed, color="#c45a3b"];
    Conf -> Fail [label="confirm fails →\nrefund + release",            style=dashed, color="#c45a3b"];
}
""",
                },
                {"type": "h3", "text": "Saga Pattern for Compensation"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Scenario:</strong> payment succeeds but inventory reserve fails (stock exhausted by a concurrent order)",
                        "<strong>Compensation:</strong> Order Service marks the order <code>failed</code>; publishes <code>PaymentRefund</code>; Payment Service issues the refund",
                        "<strong>Idempotency:</strong> every step is idempotent (same request twice = same result); refund is a no-op if already done",
                        "<strong>Timeouts:</strong> payment timeout 30 s; inventory reserve timeout 10 s; on expiry, compensation fires",
                    ],
                },
                {"type": "h3", "text": "Reservation TTL"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Add to cart:</strong> no reservation yet; just a note in the Redis cart",
                        "<strong>Checkout begins:</strong> Inventory Service reserves stock for 15 minutes",
                        "<strong>Order confirmed:</strong> reservation converted to a permanent deduction (<code>quantity -= qty</code>)",
                        "<strong>Order fails / abandoned:</strong> reservation expires after 15 min; stock returns to <em>available</em>",
                        "<strong>Benefit:</strong> prevents overselling; still allows concurrent checkouts during the 15-minute window",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Saga vs 2PC",
                    "body": (
                        "Two-phase commit gives atomicity but blocks on the coordinator and dies at "
                        "regional partitions — fatal at peak Prime-Day load. Sagas accept transient "
                        "inconsistency windows (“payment captured but order not yet confirmed”) in "
                        "exchange for availability. Idempotency on every step is the price of admission."
                    ),
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Inventory & Concurrency",
            "subtitle": "Preventing overselling",
            "blocks": [
                {"type": "h3", "text": "Optimistic Locking Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Version column:</strong> each inventory row carries a version (starts at 0)",
                        "<strong>Reserve:</strong> conditional update — succeeds only if the version matches",
                        "<strong>Conflict:</strong> if the version doesn't match, the update fails and the client retries with fresh state",
                        "<strong>No locks:</strong> many concurrent reservers race; one wins (increments version), the rest retry",
                        "<strong>Performance:</strong> non-blocking; high throughput; only occasional retries on contention",
                    ],
                },
                {
                    "type": "code",
                    "text": (
                        "-- Optimistic reserve. Returns 0 rows if someone beat us.\n"
                        "UPDATE inventory\n"
                        "   SET quantity = quantity - :qty,\n"
                        "       reserved = reserved + :qty,\n"
                        "       version  = version + 1,\n"
                        "       updated_at = NOW()\n"
                        " WHERE sku = :sku\n"
                        "   AND version = :expected_version\n"
                        "   AND quantity - reserved >= :qty;\n\n"
                        "-- DynamoDB equivalent (single round-trip):\n"
                        "--   ConditionExpression: 'version = :v AND quantity - reserved >= :qty'\n"
                        "--   UpdateExpression:    'SET quantity = quantity - :qty,\n"
                        "--                            reserved = reserved + :qty,\n"
                        "--                            version  = :v + 1'"
                    ),
                },
                {"type": "h3", "text": "Overselling Prevention"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Invariant:</strong> <code>quantity ≥ reserved</code> (available = quantity − reserved)",
                        "<strong>Reserve check:</strong> <code>available ≥ order_qty</code> before attempting the update",
                        "<strong>Double-book handling:</strong> on reserve failure, suggest alternates from the Recommendation Service",
                        "<strong>Flash-sale scenario:</strong> 100 units, 1,000 concurrent checkouts → first 100 succeed, remainder get “out of stock”",
                    ],
                },
                {"type": "h3", "text": "Inventory Write Throughput"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Average:</strong> 1.6M orders/day × ~3 line items = ~5M reserves/day → ~55 ops/sec sustained",
                        "<strong>Peak:</strong> 13M orders/day × 3 ≈ 39M reserves/day → ~450 ops/sec, with hot-SKU spikes of 1–5K ops/sec",
                        "<strong>DynamoDB sizing:</strong> on-demand provisioning, hot-partition mitigation via SKU-suffix sharding for the top 1% of SKUs",
                        "<strong>Retry budget:</strong> at 1% contention rate on hot SKUs, allow 3 retries before falling back to “out of stock”",
                    ],
                },
                {"type": "h3", "text": "Reservation TTL Mechanism"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Background job (every minute):</strong> scan reservations older than 15 minutes",
                        "<strong>Expiry logic:</strong> <code>UPDATE inventory SET reserved = reserved - qty WHERE created_at &lt; NOW() - INTERVAL 15 MIN</code>",
                        "<strong>Notification:</strong> publish <code>ReservationExpired</code> for downstream consumers",
                        "<strong>Idempotency:</strong> the job is idempotent; a second run finds no expired reservations and is a no-op",
                    ],
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Search Architecture",
            "subtitle": "Elasticsearch at scale",
            "blocks": [
                {"type": "h3", "text": "Indexing Strategy"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Index structure:</strong> <code>product_index</code> sharded by hash(product_id) mod 50; replica factor 3",
                        "<strong>Inverted index:</strong> term → document IDs; e.g., <code>samsung → [prod_123, prod_456, …]</code>",
                        "<strong>Vector search:</strong> product embeddings as a <code>dense_vector</code> field; supports semantic queries (e.g., “cozy reading light”)",
                        "<strong>Refresh interval:</strong> 30 s (near real-time); new products searchable within ~1 minute",
                    ],
                },
                {"type": "h3", "text": "Dual-Write to ES via CDC"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Source of truth:</strong> PostgreSQL <code>products</code> table",
                        "<strong>Pipeline:</strong> Debezium / logical decoding → Kafka <code>catalog.cdc</code> → ES indexer consumer",
                        "<strong>Why CDC, not synchronous dual-write:</strong> synchronous writes to PG + ES double the write latency and create partial-failure modes (in DB but not in index, or vice versa). CDC keeps the write path on the DB only and lets the index catch up asynchronously.",
                        "<strong>Lag budget:</strong> 30–60 s end-to-end (DB commit → ES searchable); acceptable for catalog updates",
                        "<strong>Replay:</strong> on indexer failure, replay from the last committed Kafka offset; the index is rebuildable from the CDC stream",
                    ],
                },
                {"type": "h3", "text": "Query Features"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Full-text:</strong> Boolean AND/OR, phrase queries, wildcards, fuzzy match (typo tolerance)",
                        "<strong>Faceting:</strong> aggregations on category, price range, rating, seller; powers the filter UI",
                        "<strong>Autocomplete:</strong> prefix query on title; top 10 suggestions in &lt;50 ms",
                        "<strong>Ranking:</strong> relevance score = TF-IDF + custom signals (rating, reviews_count, sales_velocity)",
                    ],
                },
                {"type": "h3", "text": "Read Path with Caching"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Search latency target:</strong> &lt;100 ms p99 for ES + result assembly",
                        "<strong>Cache layer:</strong> popular searches in Redis (e.g., <code>iphone 15</code> → cached results, TTL 1 h)",
                        "<strong>Product detail:</strong> on result click, fetch product from Redis (HIT expected); on MISS, query Postgres + refill cache",
                        "<strong>Hit rates:</strong> ~80% on searches (long-tail not repeated); ~95% on product detail (hot products checked repeatedly)",
                    ],
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Recommendations",
            "subtitle": "Personalization at scale",
            "blocks": [
                {"type": "h3", "text": "Two-Stage Approach"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Offline (daily batch):</strong> train a collaborative-filtering model on user-product interactions; generate top-100 recommendations per user",
                        "<strong>Online (request time):</strong> fetch cached recommendations; apply real-time filters (already-purchased, out-of-stock); return top-20",
                    ],
                },
                {"type": "h3", "text": "Offline Batch Job"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Input:</strong> user-product interaction matrix (views, purchases, ratings) from Cassandra or Kafka events",
                        "<strong>Algorithm:</strong> Alternating Least Squares (ALS) matrix factorization or deep neural network embeddings (Word2Vec-style)",
                        "<strong>Output:</strong> embedding vectors per user / per product; stored in Redis or Cassandra for &lt;10 ms lookup",
                        "<strong>Latency:</strong> nightly Spark job; 2–4 hours; results deployed by morning",
                    ],
                },
                {"type": "h3", "text": "Online Serving"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Request:</strong> <code>user_id</code> → Recommendation Service → fetch embeddings from cache → compute similarity to hot products",
                        "<strong>Filtering:</strong> remove items in the user's purchase history; remove out-of-stock items",
                        "<strong>Personalization:</strong> rank by predicted rating using extra features (price sensitivity, category preference)",
                        "<strong>A/B testing:</strong> homepage variants on 10% of users; winner (higher CTR / revenue) rolled out to 100%",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Failure Modes",
            "subtitle": "Scenarios and recovery",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Cause", "Impact", "Mitigation"],
                    "rows": [
                        ["Payment Service down",
                         "Stripe API timeout; network",
                         "Checkout blocked; users cannot place orders",
                         "Retry with exponential backoff; circuit-breaker after 10 failures; queue orders for async processing"],
                        ["Inventory Service partition",
                         "DB network split",
                         "Reads fail; product page incorrectly shows “out of stock”",
                         "Read from cache (stale ok); eventual consistency; alert ops to repair partition"],
                        ["Search (Elasticsearch) unavailable",
                         "Cluster failure; node crash",
                         "Search results unavailable; “try again later”; browse by category as fallback",
                         "Replica shard failover (RF=3); add nodes; reindex from CDC stream"],
                        ["Order Service crashes",
                         "Unhandled exception in checkout",
                         "In-flight orders lost; user gets 500; may retry with duplicate payment",
                         "Idempotent request keys (at-most-once); reconciliation job merges duplicates"],
                        ["Kafka broker down",
                         "Hardware failure; network",
                         "Events cannot be published; async pipelines stall; fulfillment delayed",
                         "Kafka replication (RF=3); partition leader election; manual failover to replica broker"],
                        ["Redis cache crash",
                         "Memory exhaustion; hardware",
                         "Cart data lost; users re-add items; sessions expire",
                         "Redis Sentinel replicas; AOF + RDB snapshots; warm cache from DB on restart"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful Degradation",
                    "body": (
                        "Prioritize the money path. Browse and search can degrade to cached / "
                        "stale data; cart can fall back to its DB mirror; recommendations can serve "
                        "a non-personalized fallback. Never block checkout on a non-critical "
                        "dependency — a failed promo banner must not break the order pipeline."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        # NEW SECTION (per ERRATA): Design Trade-offs.
        {
            "num": "12",
            "title": "Design Trade-offs",
            "subtitle": "Decisions and rationale",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Decision", "Choice", "Trade-off"],
                    "rows": [
                        ["Orders datastore",
                         "PostgreSQL (sharded by user_id, with read replicas)",
                         "Strong ACID for the money path and easy joins for fulfillment, but operationally heavier than DynamoDB; alternative NoSQL (DynamoDB / Cassandra) scales writes more cheaply but forces you to roll your own multi-row consistency for order + items + payment status."],
                        ["Inventory consistency",
                         "Eventual within a region (optimistic locking + 15-min reservation TTL); strong only inside the reserve transaction",
                         "High throughput, no global locks, occasional retries on contention; alternative strong/global consistency would block hot SKUs during flash sales and cap throughput at a few hundred ops/sec/SKU."],
                        ["Distributed transaction model",
                         "Saga (event-driven compensation via Kafka) across Order → Payment → Inventory",
                         "Loose coupling, high availability, each step independently scalable; trade-off is intermediate inconsistency windows (“payment captured but order not yet confirmed”) and the requirement that every step be idempotent. Alternative 2PC gives atomicity but couples services, blocks on coordinator failure, and does not survive cross-region partitions."],
                        ["Concurrency control on stock",
                         "Optimistic locking with <code>version</code> column",
                         "Lock-free, scales horizontally, retries are cheap; alternative pessimistic <code>SELECT … FOR UPDATE</code> serializes hot SKUs and creates lock convoys at peak."],
                        ["Search index population",
                         "Async index from CDC / Kafka into Elasticsearch (eventual, ~30–60 s lag)",
                         "New products are searchable within a minute, write path stays cheap; alternative synchronous dual-write to Postgres + ES doubles write latency and creates partial-failure modes (in DB but not in index)."],
                        ["Cart storage",
                         "Redis (TTL = 30 days), no DB write until checkout",
                         "Sub-millisecond reads/writes, cheap, naturally session-scoped; trade-off is that a Redis cluster failure loses in-flight carts (mitigated by AOF + replicas). Alternative DB-backed carts survive failures but inflate write load by ~10–100× and add latency to every “add to cart”."],
                        ["Recommendations freshness",
                         "Offline ALS batch (daily) + online filter",
                         "Cheap to train, deterministic, A/B-testable; trade-off is staleness for new users / new items. Alternative real-time online learning is more responsive but harder to validate and prone to feedback loops."],
                        ["Read scaling",
                         "CDN + Redis cache for product detail (~95% hit)",
                         "Big origin offload, low latency; trade-off is cache invalidation complexity (price/stock changes must purge edge + Redis)."],
                        ["Sharding strategy",
                         "Postgres sharded by <code>user_id</code> for orders; ES sharded by <code>product_id</code> hash",
                         "Aligns each query with a single shard; trade-off is that cross-user analytics needs a separate OLAP path (warehouse / Redshift)."],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Headline tension",
                    "body": (
                        "The whole architecture is a balancing act between (a) the <strong>money path</strong>, "
                        "which wants strong consistency, durability, and audit, and (b) the "
                        "<strong>browsing path</strong>, which wants global scale, low latency, and cheap reads. "
                        "Microservice boundaries are drawn so each side can pick its own consistency model."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        # Renumbered from §12 → §13 per ERRATA.
        {
            "num": "13",
            "title": "Interview Playbook",
            "subtitle": "How to ace this design (45 minutes)",
            "blocks": [
                {"type": "h3", "text": "Opening (5 min): Clarifying Questions"},
                {
                    "type": "bullets",
                    "items": [
                        "Confirm scope: single-vendor Amazon or multi-vendor marketplace? (single-vendor; seller model in Phase 2)",
                        "Scale: <strong>1B users, 500M products, ~1.6M orders/day average, ~13M/day peak</strong>",
                        "Consistency: real-time inventory or eventual ok? (real-time on hot SKUs; eventual on slow movers)",
                        "Geography: single region or global? (global; VAT &amp; local fulfillment complicate the design)",
                    ],
                },
                {"type": "h3", "text": "Capacity Estimation (5 min)"},
                {
                    "type": "bullets",
                    "items": [
                        # ERRATUM 1 propagated.
                        "<strong>~1.6M orders/day → ~18 ops/sec average</strong>; <strong>~13M/day peak → ~150 ops/sec</strong> (flash bursts of 500–1,000 ops/sec)",
                        "500M products × 2 KB = ~1 TB catalog; 500K QPS search ⇒ ~500 ES shards × RF=3",
                        "Bandwidth: 100M page views/day × 5 images × 500 KB = ~50 MB/sec sustained to CDN",
                        "Order corpus: <strong>5.84B rows × 5 KB ≈ 29 TB hot</strong> in PostgreSQL",
                    ],
                },
                {"type": "h3", "text": "Architecture (10 min)"},
                {
                    "type": "bullets",
                    "items": [
                        "Client: web / mobile / desktop → HTTPS to load balancer",
                        "Services: Catalog, Search (ES), Inventory, Cart (Redis), Order, Payment, Recommendations, Notifications",
                        "Data: PostgreSQL (orders, products, users); DynamoDB (inventory); Redis (cache, sessions, cart); ES (search); S3 (images); Kafka (events)",
                        "Draw the diagram with dashed lines for async (Kafka) flows",
                    ],
                },
                {"type": "h3", "text": "Deep Dives (20 min): Pick 2–3"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Inventory &amp; concurrency:</strong> optimistic locking, version columns, reservation TTL, overselling",
                        "<strong>Order pipeline &amp; saga:</strong> transactional flow, compensation on payment failure, idempotency keys",
                        "<strong>Search:</strong> ES sharding, inverted index, faceting, autocomplete, CDC dual-write, caching",
                        "<strong>Recommendations:</strong> offline ALS training, online embedding lookup, filtering, A/B testing",
                        "<strong>Failure recovery:</strong> circuit breakers, fallbacks, replication, Kafka durability",
                    ],
                },
                {"type": "h3", "text": "Wrap-Up (5 min): Trade-offs"},
                {
                    "type": "bullets",
                    "items": [
                        "Eventual vs strong consistency: chose eventual for inventory (reservation TTL) to avoid global locks at peak",
                        "Real-time vs offline recommendations: offline batch is sufficient (daily retraining); online serving adds personalization",
                        "Microservices vs monolith: independent scaling (Search and Order have completely different load shapes)",
                        "End with: “the key insight is inventory management — preventing overselling at <strong>~150 ops/sec peak</strong> requires lock-free concurrency control”",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers to Memorize",
                    "body": (
                        "1B users, 500M products &nbsp;·&nbsp; "
                        # ERRATUM 1 propagated to playbook memorization line.
                        "<strong>~1.6M orders/day (~18 ops/sec avg); ~13M orders/day peak (~150 ops/sec)</strong> &nbsp;·&nbsp; "
                        "500K QPS search; ES 500 shards × RF=3; &lt;100 ms p99 &nbsp;·&nbsp; "
                        "Inventory: optimistic locking, 15-min reservation TTL &nbsp;·&nbsp; "
                        "Order corpus: <strong>5.84B rows / ~29 TB</strong> hot &nbsp;·&nbsp; "
                        "Recs: offline ALS daily + online &lt;10 ms lookup."
                    ),
                },
                {"type": "h3", "text": "What Interviewers Are Testing"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Inventory concurrency:</strong> can you prevent overselling? do you understand optimistic locking?",
                        "<strong>Order atomicity:</strong> how do you make payment + inventory deduction look transactional? what if one fails?",
                        "<strong>Scale intuition:</strong> 500M products → how many shards? 500K QPS → how many ES nodes?",
                        "<strong>Trade-off reasoning:</strong> why eventual consistency for inventory? why offline batch for recommendations?",
                        "<strong>Resilience:</strong> what happens if Payment Service times out? if a Kafka broker crashes?",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Closing line",
                    "body": (
                        "“The hardest part of e-commerce design is preventing overselling while "
                        "sustaining ~150 ops/sec on hot SKUs at peak. Optimistic locking with "
                        "version numbers + reservation TTLs solves this without global locks; the "
                        "saga pattern then ties payment, inventory, and order together with "
                        "compensation rather than 2PC.”"
                    ),
                },
            ],
        },
    ],
}
