"""Source for `22 - Calendar.pdf` — Google/Outlook-style calendar service."""

DOC = {
    "category": "SYSTEM DESIGN INTERVIEW",
    "title": "Design a Calendar Service",
    "subtitle": "Google/Outlook-style scheduling — events, recurrences, sharing, free-busy",
    "read_time": "~ 45 minute read",
    "short_title": "Design a Calendar",
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
                        "Design a calendar service like <strong>Google Calendar</strong> or "
                        "<strong>Microsoft Outlook</strong>. Users create events with optional "
                        "recurrence, share calendars, schedule meetings against attendees' "
                        "free-busy, and receive reminders. The service must handle complex "
                        "recurrence rules, time zones, and read-heavy access patterns at "
                        "global scale."
                    ),
                },
                {"type": "h3", "text": "Clarifying Questions"},
                {
                    "type": "table",
                    "headers": ["Question", "Answer"],
                    "rows": [
                        ["Active users?", "~500M monthly; ~100M concurrent at peak"],
                        ["Events/user/week?", "~10 (mix of one-off and recurring masters)"],
                        ["Recurrence?", "Yes — RFC 5545 RRULE (FREQ, INTERVAL, BYDAY, COUNT, UNTIL)"],
                        ["Sharing?", "Per-calendar ACL + per-event override; delegate calendars"],
                        ["Free-busy?", "Yes — meeting picker queries union of busy intervals"],
                        ["Notifications?", "Per-event reminders (5 min, 1 day, custom); email + push"],
                        ["Interop?", "iCalendar (.ics) export/import; CalDAV for IMAP/Mac/Thunderbird"],
                        ["Time zones?", "Full IANA TZ DB; correct around DST transitions"],
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
                        ["Create / edit / delete event", "Title, time range, location, attendees, RRULE, reminders"],
                        ["Recurrence", "RFC 5545 RRULE; per-instance exceptions (move/cancel one occurrence)"],
                        ["List view", "Day / week / month query: events overlapping window [t1, t2]"],
                        ["Sharing", "Per-calendar ACL roles: free-busy / see-all / edit / owner"],
                        ["Meeting scheduling", "Free-busy union over N attendees → pick available slot"],
                        ["Notifications", "Reminders 5 min / 1 day / custom; email + push; idempotent"],
                        ["Interop", "iCalendar export/import; CalDAV PROPFIND/REPORT"],
                    ],
                },
                {"type": "h3", "text": "Non-Functional Requirements"},
                {
                    "type": "table",
                    "headers": ["Requirement", "Target"],
                    "rows": [
                        ["Availability", "99.95% — calendars are mission-critical for enterprise"],
                        ["Latency", "&lt;150 ms event lookup; &lt;500 ms free-busy over 10 attendees"],
                        ["Consistency", "Strong within a calendar; eventual across free-busy aggregation"],
                        ["Read:Write ratio", "~50:1 (people glance at calendars constantly)"],
                        ["Throughput", "~500K event lookups/sec at peak; ~10K writes/sec"],
                        ["Storage", "~1B active events; ~5 TB hot + attachments in object store"],
                        ["Time-zone correctness", "All IANA TZs; DST-safe recurrence expansion"],
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
                        "Active users: <strong>500M</strong>",
                        "Avg events created: <strong>10/user/week</strong> → ~700M events/week → ~100M/day",
                        "Total active events (window of ~10 weeks): <strong>~1B events</strong>",
                        "Write throughput: 100M / 86,400 = <strong>~1.2K writes/sec</strong> avg; <strong>~10K/sec at peak</strong>",
                        "Read throughput (50:1 ratio): <strong>~500K event lookups/sec at peak</strong>",
                        "Free-busy queries (meeting picker): ~5K/sec, each fanning out to ~10 calendars",
                    ],
                },
                {"type": "h3", "text": "Storage Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        "Per event row: ~2 KB (title, body, attendees JSON, RRULE, ACL refs)",
                        "1B events × 2 KB ≈ <strong>2 TB</strong> primary; replicas + indexes ≈ <strong>5 TB</strong>",
                        "Exceptions table (modified single instances of recurrences): ~10% of recurring masters",
                        "Attachments: object store (S3/GCS); avg 200 KB × 5% events ≈ <strong>10 TB attachments</strong>",
                    ],
                },
                {"type": "h3", "text": "Cache Estimation"},
                {
                    "type": "bullets",
                    "items": [
                        "Hot working set: events overlapping the next 4 weeks for active users",
                        "~100M concurrent users × ~30 events visible ≈ <strong>3B event references</strong>",
                        "Compressed expanded-occurrence cache: ~150 GB Redis cluster (TTL = 1 h)",
                        "Free-busy intervals are far smaller (just busy spans): ~20 GB Redis",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Key Numbers",
                    "body": (
                        "500M users &nbsp;·&nbsp; ~10 events/user/week &nbsp;·&nbsp; "
                        "~1B active events &nbsp;·&nbsp; <strong>500K reads/sec</strong> peak &nbsp;·&nbsp; "
                        "10K writes/sec peak &nbsp;·&nbsp; ~5 TB hot + 10 TB attachments &nbsp;·&nbsp; "
                        "~150 GB occurrence cache."
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
                        "The system splits into <strong>API Gateway</strong>, four core services "
                        "(<strong>Calendar</strong>, <strong>Recurrence Expander</strong>, "
                        "<strong>Free/Busy</strong>, <strong>Notification Scheduler</strong>), "
                        "and a data tier of Postgres (events), Redis (hot ranges), Kafka "
                        "(notification triggers and audit), and an object store (attachments). "
                        "Reads dominate; the Recurrence Expander is the hottest internal service."
                    ),
                },
                {
                    "type": "diagram",
                    "caption": "Clients hit API; lookups expand recurrences lazily. Free-busy aggregates over attendees. Notifications fan out via Kafka.",
                    "dot": r"""
digraph G {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    subgraph cluster_client {
        label="Clients"; style="rounded,dashed"; color="#586278"; fontcolor="#586278";
        Web    [label="Web App",          fillcolor="#dbe6fb"];
        Mobile [label="Mobile App",       fillcolor="#dbe6fb"];
        IMAP   [label="IMAP / CalDAV\n(Mac, Thunderbird)", fillcolor="#dbe6fb"];
    }
    subgraph cluster_edge {
        label="Edge"; style="rounded,dashed"; color="#1f8359"; fontcolor="#1f8359";
        API [label="API Gateway\n(REST + CalDAV)", fillcolor="#cbeedf"];
    }
    subgraph cluster_svc {
        label="Services"; style="rounded,dashed"; color="#b8862e"; fontcolor="#b8862e";
        CAL [label="Calendar\nService",          fillcolor="#fff2c9"];
        REX [label="Recurrence\nExpander",       fillcolor="#fff2c9"];
        FB  [label="Free/Busy\nService",         fillcolor="#fff2c9"];
        NS  [label="Notification\nScheduler",    fillcolor="#fff2c9"];
    }
    subgraph cluster_data {
        label="Data Tier"; style="rounded,dashed"; color="#7a3eb8"; fontcolor="#7a3eb8";
        PG     [label="Postgres\n(events, ACL,\nexceptions)", fillcolor="#ead7fb"];
        Redis  [label="Redis\n(hot range cache,\nfree-busy)",  fillcolor="#ead7fb"];
        KQ     [label="Kafka\n(notif + audit)",                 fillcolor="#fbd7c5"];
        OBJ    [label="Object Store\n(attachments)",            fillcolor="#ead7fb"];
    }

    Web    -> API;
    Mobile -> API;
    IMAP   -> API [label="CalDAV"];
    API -> CAL;
    API -> FB  [label="meeting picker"];
    CAL -> REX [label="expand RRULE"];
    CAL -> PG;
    CAL -> Redis [label="cache hot ranges", style=dashed];
    CAL -> OBJ   [label="attach", style=dashed];
    REX -> PG    [label="read master + exceptions"];
    REX -> Redis [label="memoize", style=dashed];
    FB  -> REX   [label="expand each calendar"];
    FB  -> Redis [label="busy intervals", style=dashed];
    CAL -> KQ    [label="reminder triggers"];
    NS  -> KQ    [label="consume", style=dashed];
    NS  -> API   [label="email/push out", style=dashed];
}
""",
                },
                {"type": "h3", "text": "Architecture Highlights"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>API Gateway:</strong> REST for web/mobile; CalDAV (PROPFIND/REPORT) for IMAP-style clients",
                        "<strong>Calendar Service:</strong> CRUD on events; enforces ACL; emits reminder triggers",
                        "<strong>Recurrence Expander:</strong> takes RRULE master + window [t1,t2] → list of occurrences",
                        "<strong>Free/Busy Service:</strong> fans out to N attendee calendars; returns interval union",
                        "<strong>Notification Scheduler:</strong> consumes Kafka; fires email/push at the right time",
                        "<strong>Postgres:</strong> partitioned by user_id; recurrence master + exceptions overlay",
                        "<strong>Redis:</strong> caches expanded ranges and busy intervals (1 h TTL)",
                        "<strong>Kafka:</strong> reminder trigger stream and audit log; dedup by (event_id, occurrence_ts)",
                        "<strong>Object store:</strong> S3/GCS for attachments referenced by event row",
                    ],
                },
            ],
        },
        # ---- 05 ------------------------------------------------------
        {
            "num": "05",
            "title": "Data Model & Schema",
            "subtitle": "events, exceptions, ACL",
            "blocks": [
                {"type": "h3", "text": "Core Tables"},
                {
                    "type": "code",
                    "text": (
                        "-- Calendar (one user may own many: primary, work, family)\n"
                        "CREATE TABLE calendars (\n"
                        "  calendar_id   UUID PRIMARY KEY,\n"
                        "  owner_user_id BIGINT NOT NULL,\n"
                        "  name          TEXT NOT NULL,\n"
                        "  default_tz    TEXT NOT NULL,           -- IANA, e.g. 'America/Los_Angeles'\n"
                        "  is_secret     BOOLEAN DEFAULT FALSE,    -- delegate-only calendars\n"
                        "  created_at    TIMESTAMPTZ DEFAULT NOW()\n"
                        ");\n\n"
                        "-- Recurrence master OR a single one-off event\n"
                        "CREATE TABLE events (\n"
                        "  event_id      UUID PRIMARY KEY,\n"
                        "  calendar_id   UUID NOT NULL REFERENCES calendars,\n"
                        "  user_id       BIGINT NOT NULL,           -- partition key\n"
                        "  title         TEXT NOT NULL,\n"
                        "  body          TEXT,\n"
                        "  location      TEXT,\n"
                        "  start_utc     TIMESTAMPTZ NOT NULL,\n"
                        "  end_utc       TIMESTAMPTZ NOT NULL,\n"
                        "  origin_tz     TEXT NOT NULL,             -- IANA TZ for RRULE expansion\n"
                        "  rrule         TEXT,                      -- RFC 5545 RRULE; NULL = one-off\n"
                        "  rdate         TEXT[],                    -- extra explicit dates\n"
                        "  exdate        TEXT[],                    -- excluded occurrences\n"
                        "  attendees     JSONB,                     -- [{user_id, response}]\n"
                        "  reminders     JSONB,                     -- [{minutes_before, channel}]\n"
                        "  attachments   JSONB,                     -- [{key, name, size}]\n"
                        "  updated_at    TIMESTAMPTZ DEFAULT NOW(),\n"
                        "  INDEX (user_id, start_utc),\n"
                        "  INDEX (calendar_id, start_utc)\n"
                        ") PARTITION BY HASH (user_id);\n\n"
                        "-- Per-instance exception (modified or cancelled occurrence)\n"
                        "CREATE TABLE event_exceptions (\n"
                        "  event_id        UUID NOT NULL REFERENCES events,\n"
                        "  occurrence_utc  TIMESTAMPTZ NOT NULL,    -- original start of the occurrence\n"
                        "  is_cancelled    BOOLEAN DEFAULT FALSE,\n"
                        "  override        JSONB,                    -- new {start, end, title, ...}\n"
                        "  PRIMARY KEY (event_id, occurrence_utc)\n"
                        ");\n\n"
                        "-- Per-calendar ACL with per-event override\n"
                        "CREATE TABLE calendar_acl (\n"
                        "  calendar_id  UUID NOT NULL REFERENCES calendars,\n"
                        "  grantee_id   BIGINT NOT NULL,\n"
                        "  role         TEXT NOT NULL,              -- free_busy | see_all | edit | owner\n"
                        "  PRIMARY KEY (calendar_id, grantee_id)\n"
                        ");\n\n"
                        "CREATE TABLE event_acl_override (\n"
                        "  event_id    UUID NOT NULL REFERENCES events,\n"
                        "  grantee_id  BIGINT NOT NULL,\n"
                        "  role        TEXT NOT NULL,\n"
                        "  PRIMARY KEY (event_id, grantee_id)\n"
                        ");"
                    ),
                },
                {"type": "h3", "text": "Why Partition by user_id"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Locality:</strong> day/week/month queries always filter by user → single shard",
                        "<strong>Even spread:</strong> hash partition avoids hotspots from celebrity calendars",
                        "<strong>Free-busy fan-out:</strong> N attendees → N parallel single-shard reads (cheap)",
                        "<strong>Re-sharding:</strong> add partitions; Postgres native HASH partitioning handles it",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "Master + Exceptions Pattern",
                    "body": (
                        "A weekly meeting for 5 years is <strong>one row</strong> in <code>events</code> "
                        "with an RRULE — not 260 rows. If one occurrence moves an hour, we add one "
                        "row in <code>event_exceptions</code>. Storage stays bounded; reads expand the "
                        "master and overlay exceptions on demand."
                    ),
                },
            ],
        },
        # ---- 06 ------------------------------------------------------
        {
            "num": "06",
            "title": "Recurrence: RFC 5545 RRULE",
            "subtitle": "FREQ, INTERVAL, BYDAY, COUNT, UNTIL",
            "blocks": [
                {"type": "h3", "text": "What an RRULE Looks Like"},
                {
                    "type": "code",
                    "text": (
                        "# Every Monday and Wednesday at 10:00 in America/Los_Angeles, until end of 2026\n"
                        "DTSTART;TZID=America/Los_Angeles:20260105T100000\n"
                        "RRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE;UNTIL=20261231T235959Z\n\n"
                        "# Last Friday of every month, 12 occurrences\n"
                        "RRULE:FREQ=MONTHLY;BYDAY=-1FR;COUNT=12\n\n"
                        "# Every 2 years on Feb 29 (leap years only) — RFC 5545 silently drops invalid dates\n"
                        "RRULE:FREQ=YEARLY;INTERVAL=2;BYMONTH=2;BYMONTHDAY=29"
                    ),
                },
                {"type": "h3", "text": "RRULE Parts We Support"},
                {
                    "type": "table",
                    "headers": ["Part", "Meaning", "Example"],
                    "rows": [
                        ["FREQ", "Frequency: SECONDLY..YEARLY", "WEEKLY"],
                        ["INTERVAL", "Step between intervals", "INTERVAL=2 → every other week"],
                        ["BYDAY", "Day-of-week filter", "BYDAY=MO,WE,FR; -1FR = last Friday"],
                        ["BYMONTHDAY", "Day-of-month filter", "BYMONTHDAY=15"],
                        ["BYMONTH", "Month filter", "BYMONTH=2 → February only"],
                        ["BYSETPOS", "Pick the n-th match in interval", "-1 → last; 1 → first"],
                        ["COUNT", "Stop after N occurrences", "COUNT=12"],
                        ["UNTIL", "Stop after a specific UTC instant", "UNTIL=20261231T235959Z"],
                    ],
                },
                {"type": "h3", "text": "Lazy vs Eager Expansion — the Right Default"},
                {
                    "type": "table",
                    "headers": ["Strategy", "Pros", "Cons"],
                    "rows": [
                        ["Eager (materialise every occurrence)",
                         "Trivial range scan; no expansion at read",
                         "1 row × 5 yrs weekly = 260 rows; storage blows up; updating an RRULE means rewriting hundreds of rows; <strong>century-spanning rules unbounded</strong>"],
                        ["Lazy (expand on read for window [t1,t2])",
                         "1 row per master; cheap edits; bounded by query window; matches calendar UX",
                         "CPU cost on read; cache the result; needs a robust RRULE iterator library"],
                        ["Hybrid (lazy + materialise popular ranges)",
                         "Lazy default; pre-materialise next-30-days for frequent rules into Redis",
                         "Two-tier cache to keep coherent on edit"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Default = Lazy + Cache",
                    "body": (
                        "Store the recurrence as <strong>one master row</strong>; expand on read for the "
                        "requested window; memoize results in Redis with a 1 h TTL keyed on "
                        "<code>(event_id, t1, t2, version)</code>. Pre-materialise only the next 30 "
                        "days for hot calendars (heuristic: viewed &gt; 100×/day)."
                    ),
                },
            ],
        },
        # ---- 07 ------------------------------------------------------
        {
            "num": "07",
            "title": "Recurrence Expansion Algorithm",
            "subtitle": "DST-safe iteration",
            "blocks": [
                {
                    "type": "diagram",
                    "caption": "Expansion is master-expand → exception-overlay. Cancellations remove; modifications replace.",
                    "dot": r"""
digraph R {
    rankdir=LR;
    bgcolor="white";
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#2e57b8"];
    edge [fontname="Helvetica", fontsize=8, color="#586278"];

    M     [label="RRULE master\n(start, FREQ, BYDAY, ...)", fillcolor="#dbe6fb"];
    W     [label="Query window\n[t1, t2]",                    fillcolor="#cbeedf"];
    ITER  [label="Iterate occurrences\nin origin TZ\n(DST-safe)",  fillcolor="#fff2c9"];
    EX    [label="Exceptions table\n(cancel / override)",     fillcolor="#fbd7c5"];
    OUT   [label="Final occurrence list\n(start_utc, end_utc, ...)", fillcolor="#cbeedf"];

    M -> ITER;
    W -> ITER [label="bound"];
    ITER -> OUT [label="raw occurrences"];
    EX  -> OUT  [label="overlay"];
}
""",
                },
                {"type": "h3", "text": "Pseudo-code"},
                {
                    "type": "code",
                    "text": (
                        "from zoneinfo import ZoneInfo\n"
                        "from dateutil.rrule import rrulestr\n\n"
                        "def expand(master, t1_utc, t2_utc, exceptions):\n"
                        "    \"\"\"Expand an RRULE master in window [t1_utc, t2_utc].\n\n"
                        "    Iterate in the originating TZ so DST shifts don't drift the wall-clock\n"
                        "    time of weekly meetings (10am stays 10am even after a DST flip).\n"
                        "    \"\"\"\n"
                        "    tz = ZoneInfo(master.origin_tz)\n"
                        "    dtstart_local = master.start_utc.astimezone(tz)\n\n"
                        "    rule = rrulestr(master.rrule, dtstart=dtstart_local)\n"
                        "    duration = master.end_utc - master.start_utc\n\n"
                        "    # rrule yields LOCAL datetimes (DST-aware). Convert each back to UTC.\n"
                        "    occurrences = []\n"
                        "    for local_start in rule.between(\n"
                        "            t1_utc.astimezone(tz), t2_utc.astimezone(tz), inc=True):\n"
                        "        start_utc = local_start.astimezone(ZoneInfo('UTC'))\n"
                        "        end_utc   = start_utc + duration\n"
                        "        occurrences.append({\n"
                        "            'event_id': master.event_id,\n"
                        "            'occurrence_utc': start_utc,\n"
                        "            'start_utc': start_utc, 'end_utc': end_utc,\n"
                        "            'title': master.title,\n"
                        "        })\n\n"
                        "    # Overlay exceptions: cancel removes; override replaces in place.\n"
                        "    by_key = {o['occurrence_utc']: o for o in occurrences}\n"
                        "    for ex in exceptions:\n"
                        "        if ex.is_cancelled:\n"
                        "            by_key.pop(ex.occurrence_utc, None)\n"
                        "        else:\n"
                        "            slot = by_key.get(ex.occurrence_utc)\n"
                        "            if slot:\n"
                        "                slot.update(ex.override)\n\n"
                        "    return sorted(by_key.values(), key=lambda o: o['start_utc'])"
                    ),
                },
                {"type": "h3", "text": "Why Iterate in the Originating TZ"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>DST drift:</strong> a 10am Los Angeles meeting set in February is 18:00 UTC; "
                        "after the March DST flip the same wall-clock 10am is 17:00 UTC. Iterating in UTC "
                        "would silently shift the meeting an hour twice a year.",
                        "<strong>RFC 5545 mandates</strong> RRULE recurrence be computed against DTSTART's local TZ.",
                        "<strong>Render in viewer's TZ:</strong> after expansion, present in the viewing "
                        "user's TZ (which may differ from the originating TZ).",
                        "<strong>All-day events</strong> are TZ-floating (a date, not an instant) — store as "
                        "DATE not TIMESTAMPTZ; expand without TZ conversion.",
                    ],
                },
            ],
        },
        # ---- 08 ------------------------------------------------------
        {
            "num": "08",
            "title": "Time-Zone Correctness",
            "subtitle": "UTC + IANA TZ + DST-safe",
            "blocks": [
                {"type": "h3", "text": "Storage Convention"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Wire format:</strong> all timestamps stored as <code>TIMESTAMPTZ</code> in UTC",
                        "<strong>Originating TZ:</strong> stored alongside as IANA string (e.g. "
                        "<code>'America/Los_Angeles'</code>) — never as a fixed offset like <code>-08:00</code>",
                        "<strong>RRULE expansion</strong> uses the originating TZ to handle DST",
                        "<strong>Render</strong> in the viewing user's preference (their TZ, locale, 12/24 h)",
                    ],
                },
                {"type": "h3", "text": "Why Not a Fixed Offset"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Offsets change:</strong> Pacific is UTC-8 in winter, UTC-7 in summer — "
                        "the IANA name encodes the rule, the offset is a snapshot",
                        "<strong>Governments change rules:</strong> the IANA TZ DB is updated several times "
                        "a year; you ship updates to all servers",
                        "<strong>Out-of-date TZ DB</strong> = silently wrong meeting times for users in "
                        "regions that changed DST policy (a recurring outage class)",
                    ],
                },
                {"type": "h3", "text": "Worked Example: DST Spring-Forward"},
                {
                    "type": "table",
                    "headers": ["Date", "Local 10:00 AM (LA)", "UTC", "Notes"],
                    "rows": [
                        ["Mar 7 (PST = UTC-8)", "10:00 AM", "18:00 UTC", "Pre-DST"],
                        ["Mar 14 (PDT = UTC-7)", "10:00 AM", "17:00 UTC", "DST forward"],
                        ["Mar 21 (PDT = UTC-7)", "10:00 AM", "17:00 UTC", "Stable"],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "DST Edge Cases",
                    "body": (
                        "<strong>Spring forward:</strong> 2:30 AM doesn't exist on the DST day — clients "
                        "must reject or re-prompt. <strong>Fall back:</strong> 1:30 AM happens twice — "
                        "ambiguous; we pick the first occurrence (pre-transition) by convention. "
                        "Same applies to <strong>government policy changes:</strong> when a country "
                        "abolishes DST, recurring events from before the change shift unless we re-anchor."
                    ),
                },
            ],
        },
        # ---- 09 ------------------------------------------------------
        {
            "num": "09",
            "title": "Sharing & ACL",
            "subtitle": "Per-calendar + per-event override",
            "blocks": [
                {"type": "h3", "text": "ACL Roles"},
                {
                    "type": "table",
                    "headers": ["Role", "Capabilities"],
                    "rows": [
                        ["free_busy", "See only busy/free intervals; no titles, no attendees"],
                        ["see_all", "Read all event details (title, location, body) — no edits"],
                        ["edit", "Create / modify / delete events on the calendar"],
                        ["owner", "All edit rights + manage ACL + delete calendar"],
                    ],
                },
                {"type": "h3", "text": "Two-Layer Resolution"},
                {
                    "type": "numbered",
                    "items": [
                        "Resolve <strong>calendar-level role</strong> for the requesting user (or 'none')",
                        "If the event has an entry in <code>event_acl_override</code> for the user, that role wins",
                        "If both are 'none', the event is invisible (404, not 403, to avoid leaking existence)",
                        "<strong>free-busy</strong> + override = 'see_all' is the typical 'I let my boss see this private event'",
                    ],
                },
                {"type": "h3", "text": "Secret / Delegate Calendars"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Secret calendar:</strong> <code>is_secret=true</code>; never appears in "
                        "directory search; access only via direct ACL grant",
                        "<strong>Delegate access:</strong> assistants schedule on behalf of executives — "
                        "stored as a calendar-level <code>edit</code> grant with <code>delegate=true</code> flag",
                        "<strong>Audit log:</strong> every ACL change emits a Kafka audit event; retained 2 yr",
                        "<strong>Acceptance flow:</strong> share invite is a notification; recipient must "
                        "accept before grant becomes active (prevents harassment via auto-share)",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "insight",
                    "title": "ACL Granularity Trade-off",
                    "body": (
                        "Per-event ACL is powerful but expensive: every event read needs an ACL lookup. "
                        "Cache the calendar-level role aggressively; only consult per-event override on a "
                        "miss flag (<code>has_event_overrides</code> bit on the event row)."
                    ),
                },
            ],
        },
        # ---- 10 ------------------------------------------------------
        {
            "num": "10",
            "title": "Free-Busy & Meeting Picker",
            "subtitle": "Union of busy intervals across N attendees",
            "blocks": [
                {"type": "h3", "text": "What the Picker Needs"},
                {
                    "type": "para",
                    "text": (
                        "Given a set of attendee user_ids and a target window (e.g. 'next Monday 9–5, "
                        "1 hour duration'), return the candidate slots when <strong>everyone is free</strong>. "
                        "Output should be the inverse of the union of all attendees' busy intervals, "
                        "filtered to slots ≥ duration."
                    ),
                },
                {"type": "h3", "text": "Algorithm"},
                {
                    "type": "code",
                    "text": (
                        "def free_slots(attendees, t1, t2, duration_min):\n"
                        "    \"\"\"Find common free slots ≥ duration_min within [t1, t2].\"\"\"\n"
                        "    # 1. Fan out: pull busy intervals from each attendee's calendar\n"
                        "    busy_per_user = parallel_map(\n"
                        "        lambda u: list_busy_intervals(u, t1, t2),  # uses ACL=free_busy\n"
                        "        attendees,\n"
                        "    )\n\n"
                        "    # 2. Flatten and merge overlapping intervals (sweep line)\n"
                        "    intervals = sorted([iv for ivs in busy_per_user for iv in ivs])\n"
                        "    merged = []\n"
                        "    for s, e in intervals:\n"
                        "        if merged and s <= merged[-1][1]:\n"
                        "            merged[-1] = (merged[-1][0], max(merged[-1][1], e))\n"
                        "        else:\n"
                        "            merged.append((s, e))\n\n"
                        "    # 3. Invert to free intervals within [t1, t2]\n"
                        "    free, cursor = [], t1\n"
                        "    for s, e in merged:\n"
                        "        if s > cursor: free.append((cursor, s))\n"
                        "        cursor = max(cursor, e)\n"
                        "    if cursor < t2: free.append((cursor, t2))\n\n"
                        "    # 4. Filter to slots big enough for the meeting\n"
                        "    return [(s, e) for (s, e) in free if (e - s).total_seconds() >= duration_min*60]"
                    ),
                },
                {"type": "h3", "text": "Optimisations"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Cache busy intervals</strong> per (user_id, day) in Redis with 5 min TTL — "
                        "viewing-window picker reads are bursty",
                        "<strong>Bitset trick:</strong> bucket the day into 5 min slots → 288 bits → 36 bytes; "
                        "AND across attendees finds free slots in O(N) per day",
                        "<strong>ACL-aware:</strong> Free/Busy service strips titles — even "
                        "<code>see_all</code> users see only busy spans here, by design",
                        "<strong>Eventual consistency OK:</strong> a 5 min stale view is fine for the picker; "
                        "we re-validate on the actual booking write",
                    ],
                },
            ],
        },
        # ---- 11 ------------------------------------------------------
        {
            "num": "11",
            "title": "Notifications & Reminders",
            "subtitle": "Kafka fan-out, idempotent dedup",
            "blocks": [
                {"type": "h3", "text": "Reminder Spec"},
                {
                    "type": "bullets",
                    "items": [
                        "Per-event reminder list: <code>[{minutes_before: 5, channel: 'push'}, "
                        "{minutes_before: 1440, channel: 'email'}]</code>",
                        "<strong>Default:</strong> 10 min push (configurable per calendar)",
                        "<strong>Custom:</strong> user can add up to 5 reminders per event",
                        "<strong>Snooze:</strong> client-side; backend sends once per occurrence",
                    ],
                },
                {"type": "h3", "text": "Pipeline"},
                {
                    "type": "numbered",
                    "items": [
                        "On event create/edit, Calendar Service emits a <code>reminder_trigger</code> "
                        "Kafka record per (event_id, occurrence_utc, channel) for the next 30 days",
                        "Notification Scheduler is a delayed-queue consumer (e.g. Kafka + RocksDB timer) "
                        "that holds messages until <code>fire_at = occurrence_utc - minutes_before</code>",
                        "At fire time, dispatcher calls Email/Push services with idempotency key "
                        "<code>(event_id, occurrence_utc, channel, reminder_id)</code>",
                        "Email/Push services dedup on the idempotency key (24 h window) so retries don't double-send",
                        "Recurring events: each occurrence within the 30 day horizon gets its own trigger; "
                        "a daily refresh job extends the horizon",
                    ],
                },
                {"type": "h3", "text": "Idempotency & Dedup"},
                {
                    "type": "code",
                    "text": (
                        "# Idempotency key for a reminder dispatch\n"
                        "key = sha1(f\"{event_id}:{occurrence_utc.isoformat()}:{channel}:{reminder_id}\")\n\n"
                        "# Dispatcher checks Redis SET-IF-NOT-EXISTS (NX)\n"
                        "if redis.set(f'rem:{key}', 1, nx=True, ex=86400):\n"
                        "    send_email_or_push(...)\n"
                        "else:\n"
                        "    # already sent within the last 24 h — drop silently\n"
                        "    metrics.incr('reminder.deduped')"
                    ),
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Why a Horizon Window",
                    "body": (
                        "Materialising every reminder for a 5-year weekly meeting is wasteful. We "
                        "schedule only the next 30 days and run a nightly job that walks recurrence "
                        "masters with <code>last_horizon_extended &lt; today</code> and emits the "
                        "next batch. Edits invalidate the horizon and re-emit."
                    ),
                },
            ],
        },
        # ---- 12 ------------------------------------------------------
        {
            "num": "12",
            "title": "iCalendar & CalDAV Interop",
            "subtitle": ".ics export/import; PROPFIND/REPORT",
            "blocks": [
                {"type": "h3", "text": "iCalendar (.ics)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>RFC 5545 file format:</strong> text-based VCALENDAR / VEVENT records",
                        "<strong>Export:</strong> any event or calendar can be downloaded as .ics — same "
                        "RRULE we already store, plus DTSTART/DTEND/SUMMARY/LOCATION/ATTENDEE",
                        "<strong>Import:</strong> parse with a vendored library (icalendar4j / ical.py); "
                        "validate; reject events with unknown extensions; map to our schema",
                        "<strong>Email invitations</strong> are .ics attachments with METHOD=REQUEST",
                    ],
                },
                {"type": "h3", "text": "Sample VEVENT"},
                {
                    "type": "code",
                    "text": (
                        "BEGIN:VCALENDAR\n"
                        "VERSION:2.0\n"
                        "PRODID:-//Example//Calendar 1.0//EN\n"
                        "BEGIN:VEVENT\n"
                        "UID:550e8400-e29b-41d4-a716-446655440000@example.com\n"
                        "DTSTAMP:20260506T120000Z\n"
                        "DTSTART;TZID=America/Los_Angeles:20260511T100000\n"
                        "DTEND;TZID=America/Los_Angeles:20260511T103000\n"
                        "RRULE:FREQ=WEEKLY;BYDAY=MO,WE;UNTIL=20261231T235959Z\n"
                        "SUMMARY:Standup\n"
                        "LOCATION:Zoom\n"
                        "ATTENDEE;CN=Alice;PARTSTAT=ACCEPTED:mailto:alice@example.com\n"
                        "ATTENDEE;CN=Bob;PARTSTAT=NEEDS-ACTION:mailto:bob@example.com\n"
                        "END:VEVENT\n"
                        "END:VCALENDAR"
                    ),
                },
                {"type": "h3", "text": "CalDAV (RFC 4791)"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>HTTP-based</strong> protocol on top of WebDAV: <code>PROPFIND</code>, "
                        "<code>REPORT</code>, <code>PUT</code>, <code>DELETE</code>",
                        "<strong>Discovery:</strong> client does PROPFIND on principal URL → finds calendar collection URL",
                        "<strong>Time-range REPORT:</strong> client asks 'give me events in [t1, t2]' → "
                        "we expand recurrences and return matching VEVENTs",
                        "<strong>ETag</strong> on each event for optimistic concurrency on writes",
                        "<strong>Sync token (RFC 6578):</strong> incremental sync — client says 'give me "
                        "everything that changed since token X'",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "tip",
                    "title": "Apple Mail / Thunderbird Just Work",
                    "body": (
                        "Implementing CalDAV correctly means every IMAP-style desktop client works "
                        "out of the box. The hard part is faithful <strong>VTIMEZONE</strong> handling "
                        "for cross-vendor recurrence."
                    ),
                },
            ],
        },
        # ---- 13 ------------------------------------------------------
        {
            "num": "13",
            "title": "Storage & Sharding Strategies",
            "subtitle": "Comparison and rationale",
            "blocks": [
                {"type": "h3", "text": "Comparison of Storage Approaches"},
                {
                    "type": "table",
                    "headers": ["Strategy", "Pros", "Cons"],
                    "rows": [
                        ["Single SQL, no shard",
                         "Simple; full ACID; joins for ACL",
                         "Doesn't scale past one box; 5 TB hot is too much for one instance"],
                        ["Postgres partition by user_id (chosen)",
                         "Range queries hit one shard; ACL joins local; native HASH partitioning",
                         "Cross-user free-busy = N parallel reads (fine, bounded N)"],
                        ["NoSQL key-value (DynamoDB)",
                         "Trivially scales; cheap reads",
                         "No joins (denormalize ACL); harder for time-range scans"],
                        ["Time-series DB (Cassandra)",
                         "Great for append-only event log",
                         "Updates and per-row ACL are awkward"],
                        ["Wide-column with partition by (user_id, month)",
                         "Time-bucketed scans; old months age out cheaply",
                         "Recurring events crossing months duplicate metadata"],
                    ],
                },
                {"type": "h3", "text": "Hot vs Cold"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Hot:</strong> events with <code>start_utc</code> in the next 90 days OR last 14 days — Postgres",
                        "<strong>Cold:</strong> older events archived to a read-only Postgres replica or S3+Parquet "
                        "(occasional access, no edits)",
                        "<strong>Recurrence masters never go cold</strong> — they generate occurrences forever",
                        "<strong>Attachments</strong> always in object store; events store only S3 keys + size + mime",
                    ],
                },
                {"type": "h3", "text": "Read Path Optimisations"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Range cache:</strong> Redis key = <code>(user_id, week_start) → [event_ids]</code>; TTL 1 h",
                        "<strong>Expansion cache:</strong> per-master keyed on <code>(event_id, week_start, version)</code>; "
                        "version invalidates on edit",
                        "<strong>Bulk RRULE expand:</strong> for a week view, expand all of a user's recurring masters "
                        "in one batch; helps L1 cache locality",
                        "<strong>Read replicas</strong> for free-busy fan-out (eventual consistency is fine)",
                    ],
                },
            ],
        },
        # ---- 14 ------------------------------------------------------
        {
            "num": "14",
            "title": "Failure Modes & Trade-offs",
            "subtitle": "What can go wrong",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Failure", "Impact", "Detection", "Mitigation"],
                    "rows": [
                        ["TZ DB out of date",
                         "Recurring events shift silently after a country's DST policy change",
                         "Drift alarms; user reports",
                         "Auto-deploy IANA tzdata 2× / month; canary one region first; emit warning when DTSTART falls in a DST gap"],
                        ["Recurrence rule with no UNTIL/COUNT",
                         "Expansion can iterate forever; CPU exhaustion",
                         "Per-request occurrence cap (e.g. 1000)",
                         "Validate on write: reject &gt; century span without COUNT/UNTIL; cap iterations"],
                        ["Leap second / leap year edge cases",
                         "Feb 29 yearly rules; 23:59:60 UTC second",
                         "Unit tests; date math review",
                         "RFC 5545 specifies dropping invalid dates (Feb 29 in non-leap years); store UTC, ignore leap seconds for scheduling"],
                        ["Postgres partition hot-spot",
                         "One celebrity calendar overwhelms a partition",
                         "Per-partition QPS metrics",
                         "Move calendar to dedicated partition; cache aggressively at edge"],
                        ["Notification dispatcher lag",
                         "Reminders fire late",
                         "End-to-end fire latency SLO",
                         "Auto-scale on Kafka lag; tier critical reminders (&lt; 15 min) on a separate fast lane"],
                        ["Free-busy stale",
                         "Picker shows free, but slot just got booked",
                         "Re-validate on write",
                         "Optimistic write: if conflict, return 409 + alternate slots"],
                        ["Object store outage",
                         "Attachments inaccessible",
                         "Health check",
                         "Event itself remains usable; UI shows 'attachment unavailable'"],
                    ],
                },
                {"type": "h3", "text": "Trade-offs"},
                {
                    "type": "table",
                    "headers": ["Decision", "Choice", "Trade-off"],
                    "rows": [
                        ["Recurrence storage",
                         "Lazy expand from master + exceptions",
                         "Storage tiny; CPU cost on read (mitigated by Redis cache). Eager would blow up storage and edit cost."],
                        ["ACL granularity",
                         "Per-calendar default + per-event override",
                         "Two lookups per event in worst case. Per-event-only would be fully expressive but every read paid the override cost."],
                        ["Free-busy consistency",
                         "Eventual (5 min stale)",
                         "Picker is fast and cacheable; rare double-book caught by optimistic write."],
                        ["Time storage",
                         "UTC + IANA TZ name",
                         "Two columns instead of one offset; correct across DST + policy changes."],
                        ["Notification horizon",
                         "30 days, refreshed nightly",
                         "Bounded queue size; recurring events past 30 days need the refresh job to be healthy."],
                        ["Partition key",
                         "user_id (hash)",
                         "Ranges hit one shard; cross-user free-busy is N parallel reads (bounded by attendees)."],
                    ],
                },
                {
                    "type": "callout",
                    "kind": "warn",
                    "title": "Graceful Degradation",
                    "body": (
                        "Calendar reads are the critical path. If Recurrence Expander is down, serve "
                        "non-recurring events directly from Postgres so users still see today's "
                        "agenda — better than a blank page. If Notifications are down, log and drop; "
                        "users complain about late reminders less than a 500-page calendar."
                    ),
                },
            ],
        },
        # ---- 15 ------------------------------------------------------
        {
            "num": "15",
            "title": "Interview Playbook",
            "subtitle": "How to present this",
            "blocks": [
                {
                    "type": "para",
                    "text": (
                        "Calendar is a deceptively deep system: most candidates breeze through CRUD "
                        "and stumble on recurrence + time zones. Lead with the data model, then "
                        "RRULE expansion, then free-busy. Save sharing/notifications for the deep dive."
                    ),
                },
                {"type": "h3", "text": "45-Minute Outline"},
                {
                    "type": "numbered",
                    "items": [
                        "<strong>Intro (2 min):</strong> 500M users, ~1B events, 500K reads/sec, 10K writes/sec, recurrences + TZs",
                        "<strong>Capacity (4 min):</strong> ~5 TB hot + 10 TB attachments; 50:1 read:write",
                        "<strong>High-level arch (4 min):</strong> API → Calendar / Expander / Free-Busy / Notifier → Postgres / Redis / Kafka / S3",
                        "<strong>Schema (5 min):</strong> events (with rrule), exceptions, calendar_acl; partition by user_id",
                        "<strong>Recurrence (10 min):</strong> RFC 5545; lazy vs eager debate; DST-safe iteration in originating TZ",
                        "<strong>Free-busy (6 min):</strong> fan-out across attendees; sweep-line interval merge; Redis cache",
                        "<strong>Sharing (4 min):</strong> 4 ACL roles; per-event override; secret/delegate calendars",
                        "<strong>Notifications (4 min):</strong> Kafka + delayed dispatcher; idempotency key; 30-day horizon",
                        "<strong>Failures (3 min):</strong> TZ DB stale, runaway recurrence, partition hotspot",
                        "<strong>Wrap (3 min):</strong> trade-offs and what you'd build next (search, AI scheduling)",
                    ],
                },
                {"type": "h3", "text": "Key Talking Points"},
                {
                    "type": "bullets",
                    "items": [
                        "“Lazy expansion is the default” — defend with storage cost + edit cost arguments",
                        "“Iterate in the originating TZ, store UTC” — DST-safe by construction",
                        "“UTC + IANA name, never a fixed offset” — survives policy changes",
                        "“Master row + exceptions overlay” — bounded storage for 5-year weekly meetings",
                        "“Per-calendar ACL + per-event override” — covers 99% of cases at low read cost",
                        "“Free-busy is the inverse of the union of busy intervals” — sweep-line, O(N log N)",
                        "“30-day reminder horizon, refreshed nightly” — bounds Kafka queue size",
                        "“Idempotency key (event_id, occurrence_utc, channel)” — exactly-once-ish dispatch",
                    ],
                },
                {"type": "h3", "text": "Common Follow-ups & Answers"},
                {
                    "type": "bullets",
                    "items": [
                        "<strong>Q: Why not materialise recurrences?</strong> A: A 5-year weekly meeting is "
                        "260 rows instead of 1; editing the RRULE rewrites all of them; storage and write "
                        "amplification are both bad. We materialise only the 30-day notification horizon.",
                        "<strong>Q: How do you handle DST?</strong> A: Store UTC + IANA name; expand RRULE "
                        "in the originating TZ so 10 AM stays 10 AM through DST flips. Keep tzdata fresh.",
                        "<strong>Q: Can you scale free-busy to 100 attendees?</strong> A: Fan out in parallel; "
                        "each is a single-shard read. Bitset-AND across attendees per day for O(N) merge. "
                        "Cap meeting picker at ~50 attendees for sane UX.",
                        "<strong>Q: What if two people book the same slot?</strong> A: Picker is eventually "
                        "consistent; the actual write re-checks busy intervals and returns 409 + alternates.",
                        "<strong>Q: How do you sync to iPhone?</strong> A: Implement CalDAV — PROPFIND for "
                        "discovery, REPORT for time-range queries, sync tokens (RFC 6578) for incremental updates.",
                        "<strong>Q: A recurring rule has no UNTIL/COUNT, what now?</strong> A: We cap at 1000 "
                        "occurrences per request and reject century-spanning rules at write time.",
                    ],
                },
                {
                    "type": "callout",
                    "kind": "key",
                    "title": "Memorize These Numbers",
                    "body": (
                        "500M users &nbsp;·&nbsp; ~1B active events &nbsp;·&nbsp; 500K reads/sec &nbsp;·&nbsp; "
                        "10K writes/sec &nbsp;·&nbsp; ~5 TB hot &nbsp;·&nbsp; ~150 GB Redis &nbsp;·&nbsp; "
                        "30-day reminder horizon &nbsp;·&nbsp; 4 ACL roles."
                    ),
                },
            ],
        },
    ],
}
