## ADDED Requirements

### Requirement: Full-stack architecture reference document exists
The system SHALL have a canonical architecture reference document that describes every layer of the ONYX platform from embedded booking widget to Google Ads conversion upload, including data models, logic rules, and integration contracts.

#### Scenario: Architecture overview is accessible
- **WHEN** a developer or stakeholder needs to understand how the ONYX system works end-to-end
- **THEN** they SHALL find a single document that covers all components, data flows, and key logic decisions without needing to read source files or migration history

---

## Architecture: ONYX Full-Stack Reference

### System Overview

ONYX is a field-service business intelligence platform for a home services company. It connects:

- **HousecallPro (HCP)** — the field CRM where estimates, jobs, schedules, and customers live
- **Booking widget** — a self-contained JS script embedded on client-facing websites that captures attribution and opens an iframe booking form
- **Supabase** — Postgres + Edge Functions serving as the data hub and automation engine
- **CallRail** — call tracking; calls and form fills are received via webhook and synced historically
- **Google Ads** — offline conversion upload (3 stages per lead) and analytics snapshot
- **React Dashboard** — internal app for operations, sales, commissions, and conversion management


---

### Sequence: Booking Flow

```mermaid
sequenceDiagram
    autonumber
    participant W as onyx-widget.js
    participant BW as Booking Wizard (iframe)
    participant FN as Edge: hcp-booking
    participant HCP as HousecallPro API
    participant DB as Supabase DB
    participant Notify as Slack / SMS

    W->>W: Page load — scan URL params<br/>write to sessionStorage (first-touch)
    W->>BW: Open iframe with tagged src<br/>(gclid, utm_*, hsa_*, ref appended)

    Note over BW: Step 1 — Service Selection<br/>Step 2 — Contact Details

    BW->>FN: GET /hcp-booking?show_for_days=N
    FN->>HCP: GET available schedule windows
    HCP-->>FN: [ { start_time, end_time, arrival_window } ]
    FN-->>BW: Available arrival windows

    Note over BW: Step 3 — User selects arrival window

    BW->>FN: POST /hcp-booking<br/>{ customer, notes, start_time, end_time, tags }

    FN->>HCP: POST /customers
    HCP-->>FN: customer_id

    FN->>HCP: POST /estimates
    HCP-->>FN: estimate_id

    FN->>HCP: POST /estimates/:id/schedule
    HCP-->>FN: schedule confirmed

    FN->>HCP: GET /estimates/:id
    HCP-->>FN: Full estimate record

    FN->>FN: resolveChannel()<br/>90-day attribution guard

    FN->>DB: UPSERT customers (lead_source)<br/>UPSERT estimates (is_booking_form=true)<br/>INSERT booking_tags (one row per param)<br/>INSERT estimate_options

    FN->>Notify: POST Slack webhook
    FN->>Notify: POST CallRail SMS API (if enabled)

    FN-->>BW: { success: true, estimate_id }

    Note over BW: Step 4 — Confirmation screen<br/>postMessage BOOKING_SUCCESS → parent
```

---

### Sequence: resolveChannel() — 90-Day Attribution Guard

```mermaid
sequenceDiagram
    autonumber
    participant FN as hcp-booking
    participant DB as Supabase DB

    Note over FN: Incoming booking has a candidate channel<br/>derived from tags (gclid → "Google Ads",<br/>hsa_src → "GLS", utm_source → mapped value, etc.)

    FN->>DB: SELECT id, lead_source, created_at<br/>FROM customers WHERE hcp_id = :id
    DB-->>FN: Customer record (or null)

    alt Customer does not exist
        FN->>FN: Use incoming channel as lead_source
    else Customer exists AND created_at > NOW() - 90 days
        FN->>FN: Preserve original lead_source<br/>(do not overwrite with incoming channel)
        Note over FN: Returning customer within attribution window.<br/>Credit stays with the channel that first acquired them.
    else Customer exists AND created_at <= NOW() - 90 days
        FN->>FN: Use incoming channel as lead_source
        Note over FN: Attribution window expired.<br/>New channel gets credit for this booking.
    end

    FN->>DB: UPSERT customers SET lead_source = resolved_channel
    FN->>DB: UPSERT estimates SET lead_source = resolved_channel
```

---

### Sequence: Conversion Discovery

```mermaid
sequenceDiagram
    autonumber
    participant CRON as pg_cron (every 15 min)
    participant DB as Supabase DB
    participant CFG as gads_conversion_config

    CRON->>DB: discover_pending_conversions()

    Note over DB: Pre-pass — build customer_gclids

    DB->>DB: UPSERT customer_gclids<br/>from booking_tags WHERE key='gclid'<br/>(source = 'booking_form')
    DB->>DB: UPSERT customer_gclids<br/>from callrail_leads WHERE gclid IS NOT NULL<br/>(source = 'callrail')

    Note over DB: Stage 1 — Booking Lead detection

    DB->>CFG: Check booking_lead.enabled
    CFG-->>DB: enabled = true
    DB->>DB: get_pending_booking_lead_conversions()<br/>→ estimates with any source signal<br/>not yet in gads_conversion_uploads
    DB->>DB: INSERT INTO gads_conversion_uploads<br/>(estimate_id, 'booking_lead', 'pending', gclid,<br/>conversion_datetime = estimates.created_at)<br/>ON CONFLICT DO NOTHING

    Note over DB: Stage 2 — Qualified Lead detection

    DB->>CFG: Check qualified_lead.enabled
    CFG-->>DB: enabled = true
    DB->>DB: get_pending_qualified_lead_conversions()<br/>→ approved priced option (approval_status + total_amount > 0)<br/>GCLID from customer_gclids (first_seen_at ASC,<br/>filtered: first_seen_at >= conversion_datetime - 90d)
    DB->>DB: INSERT INTO gads_conversion_uploads<br/>(estimate_id, 'qualified_lead', 'pending', gclid,<br/>value = AVG(options) / 100)<br/>ON CONFLICT DO NOTHING

    Note over DB: Stage 3 — Converted Lead detection

    DB->>CFG: Check converted_lead.enabled
    CFG-->>DB: enabled = true
    DB->>DB: get_pending_converted_lead_conversions()<br/>→ approved estimate_options<br/>GCLID from customer_gclids (first_seen_at ASC,<br/>filtered: first_seen_at >= conversion_datetime - 90d)
    DB->>DB: INSERT INTO gads_conversion_uploads<br/>(estimate_id, 'converted_lead', 'pending', gclid,<br/>value = SUM(approved options) / 100)<br/>ON CONFLICT DO NOTHING
```

---

### Sequence: Conversion Upload

```mermaid
sequenceDiagram
    autonumber
    participant CRON as pg_cron (:05/:20/:35/:50)
    participant FN as Edge: google-ads-conversion-upload
    participant DB as Supabase DB
    participant GA as Google Ads API v23

    CRON->>FN: HTTP POST (service role key)

    FN->>DB: SELECT * FROM gads_pipeline_state
    DB-->>FN: { paused }
    Note over FN: If paused = true → return early

    FN->>DB: SELECT * FROM gads_conversion_uploads<br/>WHERE status = 'pending'
    DB-->>FN: Pending rows (lifecycle queued/sending/retrying)

    FN->>DB: UPDATE lifecycle='expired', status='expired'<br/>WHERE conversion_datetime < NOW() - 90 days

    FN->>DB: SELECT * FROM gads_conversion_config
    DB-->>FN: { conversion_action_id, enabled, dry_run } per type

    loop For each pending row
        FN->>FN: Skip if config.enabled = false
        FN->>FN: Skip (log only) if config.dry_run = true
        FN->>DB: SELECT email, mobile_number<br/>FROM customers WHERE id = customer_id
        DB-->>FN: Customer PII
        FN->>FN: Classify method:<br/>with_gclid / user_data_only / none
        alt method = none
            FN->>DB: UPDATE lifecycle='excluded', status='skipped'
        else
            FN->>FN: Normalize + SHA-256 hash<br/>email and phone (enhanced conversions)
            FN->>FN: Build conversion payload<br/>{ gclid?, conversionDateTime,<br/>conversionValue, userIdentifiers }
            FN->>DB: UPDATE lifecycle='sending', batch_id=<new>
        end
    end

    FN->>DB: INSERT gads_conversion_upload_batches<br/>(sent_at, conversion_type, row_count, request_body)
    FN->>GA: POST customers/{id}/googleAds:uploadClickConversions<br/>Authorization: Bearer {access_token}<br/>developer-token + login-customer-id headers
    GA-->>FN: { results: [ { status, error? } ] }
    FN->>DB: UPDATE gads_conversion_upload_batches<br/>SET http_status, response_body, accepted_count, rejected_count

    loop For each result
        alt Accepted
            FN->>DB: UPDATE lifecycle='sent', status='uploaded',<br/>uploaded_at = NOW()
        else API error
            FN->>DB: Look up disposition for error_code
            DB-->>FN: { disposition, max_attempts, retry_after }
            alt disposition = retry AND attempt_count < max_attempts
                FN->>DB: UPDATE lifecycle='retrying', status='pending',<br/>attempt_count++, last_attempt_at=NOW()
            else disposition = fix-config/data/triage
                FN->>DB: UPDATE lifecycle='needs-attention', status='failed',<br/>error_code, error_namespace, error_detail
            else disposition = drop/deliberate or attempts exhausted
                FN->>DB: UPDATE lifecycle='failed', status='failed'
            end
        end
    end
```

---

### Stage 1: Attribution Capture (Booking Widget)

**Component:** `onyx-widget.js` (embedded on client website)

**What it does:**  
The widget script runs immediately on page load before the user interacts with anything. It scans `window.location.search` for all tracked URL parameters and stores them in `sessionStorage['onyx_attribution']`.

**Tracked parameters:**
| Parameter | Purpose |
|---|---|
| `gclid` | Google Ads click ID |
| `gbraid` / `wbraid` | Google Ads app/web click IDs |
| `gad_source` / `gad_campaignid` | Google Ads source metadata |
| `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` | UTM tracking parameters |
| `hsa_src`, `hsa_cam`, `hsa_grp`, `hsa_ad`, `hsa_net`, `hsa_kw`, etc. | HubSpot/SA360 click params (used to detect GLS: `hsa_src=LocalServicesAds`) |
| `fbclid` | Facebook Ads click ID |
| `ttclid` | TikTok Ads click ID |
| `msclkid` | Microsoft Ads click ID |
| `ref` | Referrer override (or captured from `document.referrer`) |

**First-touch wins semantics:**  
If `sessionStorage['onyx_attribution']` already has a value for a key, it is NOT overwritten. This means the attribution from the user's first landing page visit on this session is preserved even if they navigate around.

**On button click:**  
`buildSrc()` reads the live URL params first, then falls back to sessionStorage for any missing keys. All tracked params are appended to the iframe `src` URL, so the booking form always has the full attribution context.

---

### Stage 2: Booking Form (BookingWizard — iframe)

**Component:** `BookingWizard` React component (inside the iframe at `/booking` or `/booking-page`)

**4-step flow:**

| Step | Component | What happens |
|---|---|---|
| 1 | `ServiceSelection` | User picks service category and size (e.g., "Regular Cleaning — 3BR/2BA") |
| 2 | `ContactDetails` | User enters name, email, phone, service address |
| 3 | `ArrivalWindow` | Widget calls `GET /functions/v1/hcp-booking?show_for_days=N` → HCP API returns available 4-hour arrival windows. User selects one. |
| 4 | `BookingSuccess` | Confirmation screen. Posts `BOOKING_SUCCESS` message to parent (triggers GTM/pixel events). |

**`buildLeadSource()` — client-side channel pre-resolution:**  
Before the form submits, the widget builds an initial `lead_source` string for the `customer` payload. Priority order:
1. `gclid` present → `"Google Ads"`
2. `hsa_src = 'LocalServicesAds'` → `"GLS"`  
3. `utm_source` maps to a known channel
4. Referrer hostname matches known domains
5. Fallback: `"Direct"`

This value is sent in the POST body and later overridden by server-side channel resolution if necessary.

---

### Stage 3: Booking Submission (hcp-booking Edge Function)

**Component:** `supabase/functions/hcp-booking/index.ts`

**POST body:**
```json
{
  "customer": { "first_name", "last_name", "email", "mobile_number", "address", "lead_source" },
  "notes": "Service type + customer notes",
  "start_time": "ISO8601",
  "end_time": "ISO8601",
  "tags": { "gclid": "...", "utm_source": "...", "ref": "...", ... }
}
```

**Execution sequence:**

1. **`createCustomer()`** — POST to HCP API `/customers`. Returns HCP customer ID.
2. **`createEstimate()`** — POST to HCP API `/estimates` with the customer ID and service notes.
3. **`scheduleEstimate()`** — POST to HCP API to attach a 4-hour schedule block to the estimate.
4. **`getFullEstimate()`** — GET from HCP to fetch the created estimate with all fields populated (including the new estimate ID).
5. **`persistBooking()`** — Write to Supabase (see Stage 4).
6. **`notifySlack()`** — POST to configured Slack Incoming Webhook with booking summary.
7. **`notifySms()`** — If `sms_enabled`, POST to CallRail SMS API to send confirmation to customer.

---

### Stage 4: Supabase Persistence & Channel Resolution

**Component:** `supabase-writer.ts` → `channel-resolver.ts` (inside `hcp-booking`)

**`resolveChannel()` — 90-day attribution guard:**

This function decides what value gets written to `customers.lead_source` and `estimates.lead_source`.

```
IF customer already exists in Supabase
  AND customers.created_at > NOW() - 90 days
  THEN preserve the ORIGINAL lead_source (do not overwrite)
  ELSE use the incoming channel from this booking
```

**Rationale:** If the same customer books again within 90 days, the new booking is still attributed to the channel that originally acquired them — preventing re-attribution of a returning customer to a different channel (e.g., direct/organic second visit overwriting a Google Ads first touch).

**Database writes:**
| Table | What is written |
|---|---|
| `customers` | Upserted on HCP customer ID. `lead_source` = resolved channel. |
| `estimates` | Upserted on HCP estimate ID. `is_booking_form = true`, `lead_source` = resolved channel. |
| `addresses` | Upserted service address linked to customer. |
| `estimate_options` | Inserted (one row per option from HCP response). |
| `booking_tags` | One row per tag key/value pair. `UNIQUE(estimate_id, key)` — idempotent re-runs are safe. |

---

### Stage 5: Lead Channel Taxonomy

The system uses a 7-value channel taxonomy applied consistently across both write-time and read-time resolution.

**Channels:**
| Channel | Meaning |
|---|---|
| `Google Ads` | Click from a paid search/display ad; identified by `gclid` |
| `GLS` | Google Local Services Ad; identified by `hsa_src=LocalServicesAds` or ref URL pattern `google.com/localservices` |
| `GMB` | Google My Business profile; identified by `utm_source=gmb` or `lead_source='Reserve with Google'` |
| `Thumbtack` | Thumbtack marketplace; identified by `utm_source=thumbtack` |
| `Organic` | Organic search or known search engine referrer |
| `Direct` | No referrer, no UTM, no click ID |
| `Other` | Any signal not matching above |

**Read-time resolution in `vw_conversion_candidates`:**  
The view applies the following CASE priority chain on every row:

1. `estimates.lead_source` is one of the 7 taxonomy values → use it directly
2. `estimates.lead_source = 'Reserve with Google'` → `'GMB'`
3. `booking_tags.gclid` IS NOT NULL → `'Google Ads'`
4. `booking_tags.hsa_src = 'LocalServicesAds'` → `'GLS'`
5. `booking_tags.utm_source` → mapped to taxonomy
6. `booking_tags.ref` matches `google.com/localservices` → `'GLS'`
7. `callrail_leads.source` string-matched to taxonomy patterns
8. Fallback → `'Other'`

---

### Stage 6: HCP Data Sync (hcp-import-data)

**Component:** `supabase/functions/hcp-import-data/index.ts`

**Purpose:** Keeps Supabase tables in sync with HCP master data (not booking-created records, but the full CRM state including status changes, job completions, invoices, etc.).

**Import types (selected via `importType` POST body param):**
| Type | Source | Target table(s) |
|---|---|---|
| `employees` | HCP `/employees` | `employees` |
| `estimates` | HCP `/estimates` with pagination | `customers`, `estimates`, `estimate_options`, `addresses`, `schedules`, `estimates_settings` |
| `jobs` | HCP `/jobs` | `jobs` |
| `invoices` | HCP `/invoices` | `invoices` |
| `all` | All of the above in sequence | All of the above |

**Key behavior:**  
- Upserts on HCP ID — safe to re-run.  
- Does NOT overwrite `is_booking_form` — this is only set by `hcp-booking` and backfilled by migration.  
- Does NOT overwrite `booking_tags` — those only come from actual booking form submissions.

---

### Stage 7: CallRail Attribution

**Components:** `supabase/functions/callrail-webhook/`, `supabase/functions/callrail-pull/`, `correlate_callrail_estimate()` trigger, `resync_callrail_estimates()` function.

**Real-time webhook path:**
1. CallRail POST → `callrail-webhook` edge function
2. Validate HMAC-SHA1 signature using `CALLRAIL_WEBHOOK_SIGNING_KEY`
3. `detectWebhookType()` → determines if this is a `call` or `form_submission`
4. `mapPayloadToRow()` → maps CallRail fields to `callrail_leads` schema
5. Upsert into `callrail_leads` on `callrail_id` (idempotent)
6. `correlate_callrail_estimate()` trigger fires automatically

**`correlate_callrail_estimate()` trigger logic:**  
Matches the new `callrail_leads` row to an existing customer and estimate:
1. Try to match by `customer_phone` (last 10 digits, strips formatting)
2. If no match, try `customer_email`
3. If no match, try customer name
4. If a customer is found, set `callrail_leads.customer_id`
5. Find the most recent estimate for that customer and set `callrail_leads.estimate_id`

**Multi-estimate attribution caveat:**  
Step 5 uses a strict `ORDER BY created_at DESC LIMIT 1` tiebreak. When a customer has more than one estimate, the call binds to the **newest** one — regardless of which estimate the call actually concerned, and regardless of `work_status` (a canceled or `$0` estimate is an equally valid target). The choice is **sticky**: once `estimate_id` is set, the resync cron (below) only refills rows where `estimate_id IS NULL`, so a correlation is never re-pointed if a newer estimate later appears or the bound estimate is canceled.

This propagates into Booking Lead discovery (Stage 9a): booking-lead eligibility is per-estimate via the correlated call, so the booking conversion lands on whichever estimate won the tiebreak — even a canceled one — while a sibling estimate for the same customer may carry the Qualified/Converted stages. The result is a funnel split across two estimate records for a single customer interaction. Booking Lead carries a NULL value, so Google Ads still receives one booking count either way; the impact is to internal pipeline-view coherence, plus the edge case where a lead that books but never qualifies leaves its only conversion on the wrong or canceled estimate.

**Resync cron (every 30 min):**  
`resync_callrail_estimates()` re-runs the matching logic for any `callrail_leads` rows where `estimate_id IS NULL`. Handles cases where the call arrives before the booking is created in HCP.

**Historical backfill:**  
`callrail-pull` edge function polls CallRail API v3 with date range + pagination (250/page). Fetches extended fields including `gclid`, `lead_status`, `milestones`, `sentiment`, `call_summary`. Used for one-time or periodic backfills.

---

### Stage 8: GCLID First-Touch Attribution (customer_gclids)

**Table:** `customer_gclids`  
**Schema:** `customer_id`, `gclid`, `source` (booking_form / callrail), `first_seen_at`, `estimate_id`  
**Unique constraint:** `(customer_id, gclid)`

**Purpose:**  
Enables cross-estimate, customer-scoped first-touch attribution for the Qualified Lead and Converted Lead conversion stages (which happen weeks after booking, when estimates are priced and approved).

**Population — pre-pass in `discover_pending_conversions()`:**  
Before discovery runs, the pre-pass upserts `customer_gclids` rows from two sources:
1. `booking_tags` where `key = 'gclid'` → source = `'booking_form'` (joined via `estimates → customers`)
2. `callrail_leads` where `gclid IS NOT NULL` and `customer_id IS NOT NULL` → source = `'callrail'`

The CallRail branch joins **directly** on `callrail_leads.customer_id` (not through `estimates`), so calls that correlate to a customer before any HCP estimate exists still produce a usable first-touch GCLID once the estimate is later created.

**First-touch resolution (with click lookback window):**  
When the pipeline needs a GCLID for Qualified/Converted stages, it queries `customer_gclids`, filters to rows within the click lookback window (`first_seen_at >= conversion_datetime - INTERVAL '90 days'`), and picks the earliest eligible `first_seen_at` (first-touch within window). If no GCLID is within the window, the value is NULL and the upload phase falls back to enhanced conversions (hashed email/phone).

**Lookback enforcement at discovery time:**  
The click lookback is enforced inside the discovery SQL functions, not at upload time. `get_pending_qualified_lead_conversions()` anchors the window on `estimates.updated_at`; `get_pending_converted_lead_conversions()` anchors on `MAX(approved estimate_options.updated_at)`. This prevents perpetually-pending rows caused by GCLIDs older than the API's acceptance window.

**Stale-pending cleanup (one-time backfill):**  
Migration `20260511000003_gclid_stale_pending_cleanup.sql` ran a single `UPDATE`: any pending `gads_conversion_uploads` row whose stored `gclid` was first seen more than 90 days before its `conversion_datetime` had its `gclid` set to NULL, so the next upload attempt falls back to enhanced conversions instead of repeatedly hitting `CLICK_NOT_FOUND`. This was a one-shot backfill, **not** a recurring guard — `discover_pending_conversions()` does not re-null stale GCLIDs on existing pending rows. (A recurring re-attribution pass is proposed in the `conversion-attribution-overhaul` change but is not yet implemented.)

**Google Ads — two independent time constraints:**

```
                    click_through_lookback_window_days
                    (per-ConversionAction setting, default 30d, max 90d)
                    ◄──────────────────────────────────►
                                                        │
       Click ──────────────────────────────────► Conversion ────────────────────► Upload
       (GCLID born)                             (conversion_datetime)            (now)
       first_seen_at                                       ◄────────────────────►
                                                           Upload recency window
                                                           90 days (hard API limit)
```

| Constraint | Window | Reference point | Enforced by |
|---|---|---|---|
| Window 1 — Upload recency | `conversion_datetime >= now() - 90d` | Upload time | Upload edge function (`status = 'expired'`) |
| Window 2 — Click lookback | `first_seen_at >= conversion_datetime - 90d` | Conversion event | Discovery SQL functions (GCLID subquery filter) |

These are distinct. Window 1 catches stale *conversions*. Window 2 catches stale *clicks*. A row can pass Window 1 and fail Window 2 (recent conversion with an old click), which was the source of perpetual-pending failures before this constraint was added.

**Architecture spec maintenance requirement:**  
After any implementation that changes the behavior of a pipeline stage, this spec SHALL be updated to reflect the new behavior before the change is archived.

---

### Stage 9: Conversion Pipeline (3 Stages)

**Table:** `gads_conversion_uploads` — one row per `(estimate_id, conversion_type)`  
**Config table:** `gads_conversion_config` — one row per type with `conversion_action_id`, `enabled`, `dry_run`

#### Stage 9a: Booking Lead

**In plain terms:** This stage is discovered the moment a lead exists at all — someone submitted the online booking form, that submission left tracking tags, or they called a tracked number that got matched to them. It is the "a potential customer asked for service" signal, the earliest point in the funnel. Nothing has been priced yet, so no dollar value is attached.

Estimates that carry **none** of these signals — not from the booking form, no tracking tags, and no matched call — are deliberately **not** discovered. These are typically estimates entered by hand in HousecallPro (walk-ins, repeat clients, internal records) with no marketing origin to attribute a conversion to. Reporting them to Google Ads would credit it with leads it never drove, inflating conversion counts with traffic it can't optimize against.

These estimates are still **visible** in the dashboard's conversions pipeline — `vw_conversion_candidates` lists every estimate, not just discovered ones — where they appear as **pre-discovery** rows: all three stages read "Not discovered" and the Booking Lead detail shows "No attribution data detected." Not being discovered means no conversion is uploaded; it does not mean the estimate is hidden from operators.

| Field | Value |
|---|---|
| Trigger condition | `is_booking_form = true` OR `booking_tags` rows exist OR `callrail_leads` correlated (the 3 branches in the deployed `get_pending_booking_lead_conversions()`) |
| `conversion_datetime` | `estimates.created_at` |
| `conversion_value` | NULL (no price yet) |
| GCLID source | `booking_tags.gclid` or correlated `callrail_leads.gclid` |

**Note — staged extension not yet deployed:** Migration `20260526000002_booking_lead_repeat_customer_gclid.sql` adds a 4th eligibility branch (customer has any `customer_gclids` row) and a 3rd GCLID fallback (oldest `customer_gclids` by `first_seen_at`), to discover booking leads for repeat customers whose GCLID was captured on a prior estimate. As of this writing the migration file exists in the repo but is **not applied** to the database (applied migrations end at `20260526000001`), so the live function still uses the 3 branches above. (A separate earlier `lead_source IS NOT NULL` gate was removed in `20260422000003_remove_lead_source_discovery_gate`.)

#### Stage 9b: Qualified Lead

**In plain terms:** This stage is discovered once the customer has approved at least one *priced* option on their estimate — a real, costed quote was put in front of them and they signed off on something worth more than $0. It marks the lead becoming a genuine, money-on-the-table opportunity. The value recorded is the average of all quoted options — a representative figure for what a job like this is worth.

| Field | Value |
|---|---|
| Trigger condition | At least one `estimate_option` with `approval_status IN ('approved', 'pro approved')` AND `total_amount > 0` |
| `conversion_datetime` | `estimates.updated_at` at time of qualification |
| `conversion_value` | `AVG(all estimate_options.total_amount) / 100.0` (dollars) |
| GCLID source | `customer_gclids` first-touch (earliest `first_seen_at`) |

**Note:** Uses the customer-level first-touch GCLID, not the estimate-level one: the customer may have multiple estimates, and first-touch ensures the original acquisition channel gets credit.

#### Stage 9c: Converted Lead

**In plain terms:** This stage is discovered when the customer commits to actual work — at least one option on the estimate is approved. It is the "the customer bought" signal at the bottom of the funnel. The value recorded is the real total of everything they approved — the actual revenue won, rather than the averaged estimate used for the Qualified stage.

| Field | Value |
|---|---|
| Trigger condition | At least one `estimate_option.approval_status IN ('approved', 'pro approved')` |
| `conversion_datetime` | `MAX(approved estimate_options.updated_at)` |
| `conversion_value` | `SUM(approved estimate_options.total_amount) / 100.0` (dollars) |
| GCLID source | `customer_gclids` first-touch |

#### GCLID source — Qualified vs Converted

Both Qualified and Converted select the earliest `customer_gclids.gclid` for the customer (`ORDER BY first_seen_at ASC LIMIT 1`). They differ in **the reference point for the 90-day click-lookback filter**, which mirrors each stage's own `conversion_datetime`:

| Stage | Lookback anchor | Filter |
|---|---|---|
| Qualified | `estimates.updated_at` | `cg.first_seen_at >= e.updated_at - INTERVAL '90 days'` |
| Converted | `MAX(estimate_options.updated_at) WHERE approval_status IN ('approved','pro approved')` | `cg.first_seen_at >= MAX(approved eo.updated_at) - INTERVAL '90 days'` |

Because the Converted window opens later (only when an option is approved), a click within range at qualification time may fall outside it at conversion time. In that case the Qualified row ships a GCLID and the Converted row ships NULL → enhanced-conversions fallback at upload.

Distinct from Booking Lead, which uses the per-estimate `booking_tags.gclid` or correlated `callrail_leads.gclid` directly, not `customer_gclids`.

#### Discovery cron (every 15 min):
```
discover_pending_conversions()
  ├─ Pre-pass A: upsert customer_gclids from booking_tags (via estimates→customers)
  ├─ Pre-pass B: upsert customer_gclids from callrail_leads (direct customer_id join)
  ├─ IF booking_lead.enabled: get_pending_booking_lead_conversions() → INSERT pending rows
  ├─ IF qualified_lead.enabled: get_pending_qualified_lead_conversions() → INSERT pending rows
  └─ IF converted_lead.enabled: get_pending_converted_lead_conversions() → INSERT pending rows
     (all INSERT … ON CONFLICT DO NOTHING — idempotent; new rows are created with
      lifecycle = 'queued')
```

#### Upload lifecycle state machine:

`gads_conversion_uploads` carries both a legacy `status` and a richer `lifecycle` column. A CHECK constraint enforces the mapping so existing readers of `status` keep working during the deprecation window.

| lifecycle         | status     | meaning                                                       |
|-------------------|------------|---------------------------------------------------------------|
| `queued`          | `pending`  | discovered, not yet attempted                                 |
| `sending`         | `pending`  | included in a batch currently in flight                       |
| `sent`            | `uploaded` | accepted by Google Ads                                        |
| `retrying`        | `pending`  | failed previously, disposition = `retry`, will retry          |
| `needs-attention` | `failed`   | manual triage required (disposition = `fix-*`)                |
| `failed`          | `failed`   | terminal failure (no retry; disposition = `drop`/`deliberate` exhausted) |
| `excluded`        | `skipped`  | no GCLID and no hashed identifiers — nothing to upload        |
| `expired`         | `expired`  | `conversion_datetime > 90 days` at upload time                |

Transitions are driven by `gads_error_dispositions` (see Stage 10a).

---

### Stage 9a: Error Disposition & Batch Tracking

**Tables:**

| Table | Purpose |
|---|---|
| `gads_error_dispositions` | Master lookup: one row per `error_code` (e.g. `conversionUploadError.CLICK_NOT_FOUND`) → `disposition`, `max_attempts`, `retry_after_seconds`, `no_alert`, `human_action`, `notes`, `source` (`override` or `proto-*`). Seeded with ~107 Google Ads API v23 error codes. |
| `gads_conversion_upload_batches` | One row per HTTP call to `uploadClickConversions`. Records `sent_at`, `job_id`, `http_status`, `request_error_code`, `request_error_message`, `row_count`, `accepted_count`, `rejected_count`, `conversion_type`, plus raw `request_body` and `response_body` JSON for replay/audit. |
| `gads_pipeline_state` | Singleton (`id = 1`). Operator pause switch: `paused`, `paused_reason`, `paused_error_code`, `paused_batch_id`, `paused_at`, `resumed_at`, `resumed_by`. |

**New columns on `gads_conversion_uploads`:**
- `lifecycle` — see state machine above
- `error_code`, `error_namespace`, `error_detail` (JSONB) — structured Google Ads error
- `last_attempt_at`, `attempt_count` — retry bookkeeping
- `batch_id` — FK into `gads_conversion_upload_batches`

**Dispositions:**

| Disposition  | Behavior |
|--------------|----------|
| `retry`      | Re-queue (lifecycle `retrying`) until `attempt_count >= max_attempts`, respecting `retry_after_seconds` |
| `fix-config` | Move to `needs-attention`; surface `human_action` text in NeedsAttentionInbox |
| `fix-data`   | Same as above, but the recommended fix is to data rather than config |
| `fix-triage` | Same as above, but requires manual investigation (no canned remediation) |
| `drop`       | Move to terminal `failed`. If `no_alert = true`, suppressed from dashboards |
| `deliberate` | Treated like `drop` but documents that the failure is expected (e.g. test rows) |

**Pause behavior:**  
The upload edge function reads `gads_pipeline_state` at the start of each run. If `paused = true`, the run returns early without touching any row. The dashboard surfaces a `PausedBanner` in this state. Pause is intended for incident response when a systemic error (auth, quota, schema) would otherwise cause a flood of failures.

---

### Stage 10: Google Ads Conversion Upload

**Component:** `supabase/functions/google-ads-conversion-upload/index.ts`  
**Triggered by:** pg_cron at :05, :20, :35, :50 via pg_net HTTP call

**Execution sequence:**

1. Read `gads_pipeline_state` (singleton). If `paused = true`, return early.
2. Read all `gads_conversion_uploads` rows with `status = 'pending'` (i.e. lifecycle in `queued`/`sending`/`retrying`).
3. For rows where `conversion_datetime < NOW() - 90 days` → set `lifecycle = 'expired'` (`status = 'expired'`).
4. For each remaining pending row:
   a. Look up `gads_conversion_config` for this `conversion_type`
   b. If `enabled = false` → skip
   c. If `dry_run = true` → log but do not call Google Ads API
   d. Resolve `conversion_action` resource name: `customers/{customer_id}/conversionActions/{action_id}`
   e. Classify upload method:
      - `with_gclid` — GCLID set on the upload row
      - `user_data_only` — no GCLID but customer has hashed email/phone
      - `none` → set `lifecycle = 'excluded'`, skip
   f. Build conversion payload:
      - `gclid` (from the upload row, if present)
      - `conversionDateTime` (formatted as `YYYY-MM-DD HH:MM:SS+00:00`)
      - `conversionValue` (if present)
      - `userIdentifiers` with SHA-256 hashed email and/or phone from `customers` table (enhanced conversions)
   g. Set `lifecycle = 'sending'`, attach a new or current `batch_id`.
5. Batch all payloads into a single `uploadClickConversions` API call. Insert a `gads_conversion_upload_batches` row with `request_body` (the JSON sent) and `response_body` (the JSON received, or a structured error envelope on network failure).
6. Process response — for each row:
   - **Accepted** → `lifecycle = 'sent'`, `status = 'uploaded'`, `uploaded_at = now()`
   - **Rejected with error_code** → look up disposition in `gads_error_dispositions`; transition lifecycle to `retrying`, `needs-attention`, or `failed` per the disposition table; persist `error_code`, `error_namespace`, `error_detail`, `error_message`, increment `attempt_count`/`upload_attempts`.
   - **Batch-level (HTTP) failure** → update batch row with `http_status`/`request_error_code`; member rows revert to `queued` for the next run unless the disposition pauses the pipeline.

**Enhanced conversions:**  
Customer `email` is normalized (lowercase, trim) then `SHA-256` hashed. Phone is normalized (E.164 format) then `SHA-256` hashed. These are sent as `userIdentifiers` alongside the GCLID to improve match rates for conversions where the GCLID may have expired or be unavailable.

**Google Ads API credentials (Supabase secrets):**
- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_REFRESH_TOKEN`
- `GOOGLE_ADS_CUSTOMER_ID` (direct account, no dashes)
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID` (MCC manager, optional)

**Auth pattern:** Supabase secret `GOOGLE_ADS_REFRESH_TOKEN` → exchanged for short-lived access token via Google OAuth2 token endpoint → used as `Authorization: Bearer` on API requests.

---

### Stage 11: Google Ads Analytics Sync

**Component:** `supabase/functions/gads-upload-analytics/index.ts`  
**Component:** `supabase/functions/google-ads-sync/index.ts`  
**Triggered by:** pg_cron daily at 04:00 UTC

**`gads-upload-analytics` — what it fetches:**
| Data | Table |
|---|---|
| Attribution snapshots by conversion action and date | `gads_attribution_snapshots` |
| Client-level upload health (click vs. call client) | `gads_client_upload_health` |
| Action-level upload health per run | `gads_action_upload_health` |
| Conversion action config snapshot | `gads_action_config_snapshots` |

**`google-ads-sync` — campaign spend:**  
Uses GAQL to query yesterday's `campaign.id`, `ad_group.id`, `metrics.cost_micros`, `metrics.clicks`, `metrics.impressions` by `segments.date`. Upserts into `ads_campaign_stats` on `(campaign_id, ad_group_id, date)`.

---

### Stage 12: Dashboard (React Frontend)

**Stack:** React 18 + TypeScript + Vite + React Router v6 + TanStack Query v5 + shadcn/ui + Tailwind CSS

**Auth:** `AuthContext` wraps the app. On mount: `supabase.auth.getSession()`. On change: `onAuthStateChange`. All routes behind an auth guard; unauthenticated users see `LoginPage`.

**API pattern:** All data fetching uses the Supabase JS client with the anon key. Edge function calls use `supabase.functions.invoke()` which automatically attaches the user's JWT as `Authorization: Bearer`.

**Key pages:**

| Route | Page | Data source |
|---|---|---|
| `/conversions` | redirect → `/conversions/uploads` | — |
| `/conversions/uploads` | `ConversionsPage` (Pipeline tab) | `vw_conversion_candidates` direct query |
| `/conversions/needs-attention` | `NeedsAttentionInbox` | pending rows with lifecycle `needs-attention` |
| `/conversions/batches` | `BatchesPanel` | `gads_conversion_upload_batches` with raw payloads |
| `/conversions/dispositions` | `DispositionsAdminPage` | `gads_error_dispositions` (override editor over proto seed) |
| `/conversions/upload-report` | `UploadReportPage` | `vw_gads_upload_reconciliation_daily` |
| `/conversions/config` | `ConversionConfigPage` | `GET/PUT /functions/v1/gads-conversion-config` |
| `/online-bookings` | `OnlineBookingsPage` | `vw_booking_estimates` direct query |
| `/calls` | `CallsPage` | `vw_callrail_leads` direct query |
| `/marketing` | `MarketingPage` | `ads_campaign_stats`, `gads_attribution_snapshots` |
| `/sales`, `/sales/dev` | `SalesPage`, `SalesDevPage` | `fn_get_sales_table_data()` RPC |
| `/salary`, `/commissions` | `SalaryPage`, `CommissionsPage` | commission RPCs (`func_commission_*` edge functions) |
| `/employees`, `/assignments` | `EmployeeManagerPage`, `SalesAssignmentManagerPage` | `employees`, sales-assignment views |
| `/admin` | `AdminPage` | mixed admin tooling |

`ConversionsPage` wraps the Pipeline / Needs Attention / Batches tabs in a shared `WorkbenchTabs` shell with a right-aligned link to `/conversions/dispositions` (Configure). A `PausedBanner` is rendered across all conversion pages when `gads_pipeline_state.paused = true`.

**`vw_conversion_candidates` — central pipeline view:**  
One row per estimate with any lead signal. Columns include:
- `channel` (7-value taxonomy, computed via CASE chain — see Stage 5)
- Per-stage status: `booking_lead_status`, `qualified_lead_status`, `converted_lead_status`
- Per-stage lifecycle + disposition: `booking_lifecycle`, `booking_error_code`, `booking_disposition`, `booking_no_alert`, `booking_human_action`, `booking_attempt_count`, `booking_max_attempts` (and the matching `qualified_*` / `converted_*` columns)
- `first_touch_medium`, `all_gclids` — attribution metadata
- `is_closed` — whether the estimate is in a terminal HCP status
- Customer identifiers: `customer_email`, `customer_mobile`, `customer_street`, `customer_city`, `customer_state`, `customer_zip` — used to compute the dashboard's `with_gclid` / `user_data_only` / `none` method classifier and to populate the expanded detail panel
- Call aggregation columns from correlated `callrail_leads`

**Google Ads template CSV export (client-side):**  
ConversionsPage "Export CSV" and the month/week header download icons build a shared template CSV (`Email, Phone Number, Conversion Name, Conversion Time, Conversion Value, Conversion Currency, Google Click ID, JSON Sent, JSON Echo, Error`) in `exportUploadsCsv.ts`. On click it fetches `vw_gads_upload_payload_slices` by estimate-id chunks and merges with in-memory pipeline rows (email/phone); conversion names come from `gads_conversion_config.conversion_action_name`. Month/week exports mirror the group's mode-filtered display (hidden in pre-discovery mode); the page-level export covers all conversion types for the full 90-day window. The former `export_converted_leads(timestamptz, timestamptz)` RPC was dropped (`20260611000001`).

---

### Configuration Singletons

All configuration is stored as JSONB singletons in Supabase, read/written by corresponding edge functions, and used at runtime.

| Table | Edge Function | Used By |
|---|---|---|
| `widget_tracking_config` | `widget-config` | Booking widget on load (injects GA4, GTM, Meta Pixel, TikTok, LinkedIn, Clarity, CallRail tracker scripts) |
| `booking_config` | `booking-config` | `hcp-booking` for SMS number/template; BookingWizard for sms_enabled flag |
| `slack_notify_config` | `slack-config` | `hcp-booking` `notifySlack()` for field visibility and color |
| `widget_designs` | `widget-designs` | Booking widget button rendering (styles array + selected design name) |

---

#### Scenario: New developer understands booking-to-conversion flow
- **WHEN** a new developer reads the full-stack-architecture spec
- **THEN** they SHALL be able to trace the path from a user clicking "Book Now" to a conversion appearing in Google Ads without reading any source files

#### Scenario: Channel taxonomy is documented
- **WHEN** a developer needs to understand how a lead gets its channel value
- **THEN** the spec SHALL explain both write-time (90-day guard in hcp-booking) and read-time (SQL CASE in vw_conversion_candidates) resolution with the full priority chain

#### Scenario: Conversion pipeline stages are documented
- **WHEN** a developer needs to understand what triggers each pipeline stage
- **THEN** the spec SHALL describe trigger conditions, datetime source, value source, and GCLID source for all three stages

#### Scenario: GCLID first-touch model is documented
- **WHEN** a developer needs to understand why a conversion uses a different GCLID than the booking_tag
- **THEN** the spec SHALL explain the customer_gclids table, its population pre-pass, and first-touch selection logic

#### Scenario: Error disposition and lifecycle are documented
- **WHEN** a developer needs to understand why a row is in `needs-attention`, `retrying`, or `failed`
- **THEN** the spec SHALL describe the `gads_error_dispositions` lookup, the `lifecycle ↔ status` mapping, the batch-tracking table, and the global pause switch (`gads_pipeline_state`)

#### Scenario: Click lookback enforcement is documented
- **WHEN** a developer needs to understand why a pending conversion has no GCLID despite one being present on the booking
- **THEN** the spec SHALL describe the two independent windows (upload recency vs. click lookback), the discovery-time enforcement inside `get_pending_qualified_lead_conversions()` and `get_pending_converted_lead_conversions()`, and the stale-pending cleanup that nulls GCLIDs outside the window
