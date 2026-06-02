# Conversion Tracking Compliance Checklist

> **Reference:** [Onyx_Conversion_Tracking_WorkingDoc.html](ref/Onyx_Conversion_Tracking_WorkingDoc.html)  
> **Status:** DRAFT v0.1  
> **Purpose:** Verify how closely the current implementation matches this specification

---

## Section 0 — Whole System (5-Step Pipeline)

For each step, confirm the corresponding code/logic exists and is wired correctly.

- [ ] **Step 1 — Catch the events**
  - **Task:** Locate the sync/ingest code that pulls estimates from Housecall Pro
  - **Task:** Verify there is logic that detects `options[].status` transitions to `"scheduled"`, `"complete rated"`, `"complete unrated"`, `"created job from estimate"`, and `approval_status` transitions to `"approved"` / `"pro approved"`
  - **Task:** Confirm the sync runs on a schedule (not just on-demand) to catch events in real time

- [ ] **Step 2 — Freeze the timestamp**
  - **Task:** Verify a snapshot mechanism exists that captures `observed_at` when a status transition is first seen
  - **Task:** Confirm the fallback chain for Qualified timestamp is implemented (sent-snapshot → approved-snapshot → completed_at → started_at → on_my_way_at → created_at)
  - **Task:** Confirm `booked_at` is stored for BOOKING_CONFIRMED, not `scheduled_start` or raw `created_at`

- [ ] **Step 3 — Link the lead source**
  - **Task:** Verify CallRail phone-number-to-estimate matching logic exists
  - **Task:** Verify GCLID retrieval from CallRail (or form capture) is implemented
  - **Task:** Check that lead sources are being stored on the conversion event record

- [ ] **Step 4 — Send & confirm**
  - **Task:** Locate the Google Ads API upload function (edge function or server-side code)
  - **Task:** Verify it stores the API response (success or error) per row in a database table
  - **Task:** Confirm there is no silent swallowing of upload failures — errors must be surfaced

- [ ] **Step 5 — Monitor for gaps**
  - **Task:** Verify monitoring queries or dashboard logic exists for each of the 5 gap conditions
  - **Task:** Confirm alerts or a UI exists so gaps are visible to operators, not just logged

---

## Section 1 — Catch the Events & Freeze the Timestamp

### BOOKING_CONFIRMED (id 7576326162) — Scheduled

- [ ] **HCP field detection:** `options[].status` = `"scheduled"` AND `assigned_employees[]` non-empty
  - **Task:** Search codebase for `status` + `"scheduled"` logic; verify `assigned_employees` is checked, not just status

- [ ] **Timestamp source:** `booked_at` = moment sync first observes scheduled + assigned state
  - **Task:** Find where `booked_at` is set; confirm it is derived from the observation time, not from HCP fields like `scheduled_start`

- [ ] **Snapshot field:** `observed_at` captured as snapshot
  - **Task:** Verify an `observed_at` or equivalent snapshot timestamp column exists in the event/conversion table

- [ ] **Fallback rule:** Use `created_at` only when `created_at == updated_at` (estimate created already-scheduled)
  - **Task:** Find the fallback logic; confirm it checks `created_at == updated_at` before using `created_at`

- [ ] **Validation needed:** Confirm `updated_at` moves when status → `scheduled`
  - **Task:** Inspect a sample of HCP estimate data; verify `updated_at` changes when status transitions to scheduled

- [ ] **Watch:** `scheduled_start` is future appointment date — NOT the conversion time
  - **Task:** Confirm `scheduled_start` is NOT used as the conversion timestamp anywhere in the code

- [ ] **Watch:** `created_at` can predate booking by minutes to hours — validate against `updated_at`
  - **Task:** Write a query or inspection check to confirm `created_at` can be earlier than `updated_at` for scheduled estimates

### Qualified Leads (id 6802897127) — Qualified

- [ ] **HCP field detection:** `options[].status` ∈ {`"complete rated"`, `"complete unrated"`, `"created job from estimate"`}, OR option approved on-site
  - **Task:** Search for status values `"complete rated"`, `"complete unrated"`, `"created job from estimate"` in the codebase
  - **Task:** Verify logic handles "approved on-site" (approval_status = approved without going through sent state)

- [ ] **Anchor timestamp fallback chain (in priority order):**
  - **Task:** For each step below, locate the code that implements it:

  1. [ ] **Sent snapshot** — `updated_at` when status → submitted for signoff (primary anchor)
     - **Task:** Find where status `"submitted"` or equivalent is tracked; confirm `updated_at` is snapshotted at that point

  2. [ ] **Approved snapshot** — `updated_at` when `approval_status` → approved / pro approved
     - **Task:** Find `approval_status` transition logic; confirm `updated_at` is captured when approval happens

  3. [ ] `completed_at` — visit finished
     - **Task:** Verify `completed_at` is in the fallback chain and is used when no snapshot exists

  4. [ ] `started_at` — tech began on-site
     - **Task:** Verify `started_at` is in the fallback chain after `completed_at`

  5. [ ] `on_my_way_at` — tech en route
     - **Task:** Verify `on_my_way_at` is in the fallback chain after `started_at`

  6. [ ] `option.created_at` — last resort
     - **Task:** Confirm `option.created_at` is the final fallback and is only used as last resort

- [ ] **Snapshot tracker requirement:** Sent-first logic requires live snapshot tracker — confirm this is implemented
  - **Task:** Find the snapshot tracker table/logic; confirm it stores `updated_at` at each status transition
  - **Task:** If snapshot tracker is NOT yet live, confirm the code falls through correctly to real timestamps

- [ ] **Counting type:** `MANY_PER_CLICK`, $250 default (not counted toward bidding)
  - **Task:** Verify the Google Ads conversion action is configured as `MANY_PER_CLICK` with $250 value

- [ ] **Watch:** No real `sent_at`/`approved_at` fields exist — top two anchors are snapshots only
  - **Task:** Confirm there is no `sent_at` or `approved_at` field being used as a direct timestamp (must be snapshots)

### Converted Leads (id 6794281105) — Converted

- [ ] **HCP field detection:** `options[].approval_status` ∈ {`"approved"`, `"pro approved"`} AND linked Job (`job_…`) exists
  - **Task:** Find `approval_status` check; confirm it requires BOTH approved/pro approved AND a linked Job ID
  - **Task:** Verify `"created job from estimate"` status alone is NOT sufficient (needs real Job ID)

- [ ] **Timestamp source:** `job.created_at` (immutable)
  - **Task:** Find where the conversion timestamp is set; confirm it uses `job.created_at`, not `estimate.updated_at` or `option.updated_at`

- [ ] **Value source:** `options[].total_amount` ÷ 100 (cents to dollars)
  - **Task:** Find where conversion value is set; confirm division by 100 is applied (cents → dollars)
  - **Task:** Verify the value is pulled from `options[].total_amount`, not from a Job-level amount field

- [ ] **Validation:** Confirm real Job ID exists — not status `"created job from estimate"` alone
  - **Task:** Run a data check: count estimates with `"created job from estimate"` status vs. those with actual `job_id` — confirm the gap is understood

- [ ] **Note:** Only action that counts toward bidding
  - **Task:** Verify this conversion action has `include_in_conversions: true` in Google Ads (vs false for Scheduled/Qualified)

### Confirmed Field Paths (all sections)

- [ ] Estimate root `id` = `csr_…`
  - **Task:** Verify estimate ID prefix is `csr_` in the data model

- [ ] `work_status` field present
  - **Task:** Confirm `work_status` is being captured from HCP payload

- [ ] `schedule.scheduled_start` / `scheduled_end` (future appointment slot)
  - **Task:** Confirm these fields are being read but NOT used as conversion timestamps

- [ ] `work_timestamps.{on_my_way_at, started_at, completed_at}`
  - **Task:** Verify all three timestamp fields are being captured in the sync

- [ ] `lead_source` field present
  - **Task:** Confirm `lead_source` is being stored on conversion events

- [ ] Per option: `id` = `est_…`, `status`, `approval_status`, `total_amount` (cents), `created_at`, `updated_at`
  - **Task:** Verify option-level `id` prefix is `est_`; confirm all listed fields are mapped

- [ ] Dates stored as ISO-8601 UTC (`…Z`); reports in ET
  - **Task:** Confirm dates are stored in UTC and converted to ET only at display time

### Core Rule Validated

- [ ] Conversion timestamp = when status transition is **first observed** (snapshot), never `scheduled_start`
  - **Task:** Search for any remaining uses of `scheduled_start` as a conversion timestamp — confirm none exist

- [ ] `created_at` NOT used when `created_at != updated_at` (estimate's birth predates booking)
  - **Task:** Find the conditional logic `created_at == updated_at` that gates `created_at` fallback usage

---

## Section 2 — Link Each Conversion to Its Lead Source

### Source Priority Order

1. [ ] **CallRail tracked calls** — Tracking numbers on every call; match phone → estimate; pull GCLID from CallRail
   - **Task:** Find the CallRail integration code (phone number matching logic)
   - **Task:** Verify GCLID is being retrieved from CallRail and stored on the conversion event
   - **Task:** Confirm phone → estimate matching is working (test with a known estimate + call pair)

2. [ ] **Online booking** — Web form / booking-page leads; GA4 fire exists but needs GTM + GCLID capture on form
   - **Task:** Find the booking page / form code
   - **Task:** Verify GA4 event fires on form submission
   - **Task:** Verify GCLID is captured on the form (via GTM variable or direct implementation) and passed to backend
   - **Task:** Confirm GCLID is stored linked to the lead/estimate record

3. [ ] **Google Local Services (LSA)** — Currently tracked via CallRail only; plan to integrate Google LSA directly
   - **Task:** Determine current state: CallRail-only tracking, or Google LSA integration exists?
   - **Task:** If LSA integration is planned, find any existing LSA-related code or documentation
   - **Task:** Verify LSA leads are not being misattributed to other sources

4. [ ] **Referral / organic** — No click to attribute; need tagging method (intake question or HCP lead-source field) for clean exclusion
   - **Task:** Find the intake form or HCP lead-source field that captures referral/organic
   - **Task:** Verify these sources are explicitly flagged (not just left as unknown)
   - **Task:** Confirm referral/organic leads are excluded from Google Ads uploads, not uploaded with bad attribution

5. [ ] **Recurring / repeat customers** — Detect repeat customer → suppress or send at $1
   - **Task:** Find the repeat customer detection logic (phone number match, email match, or HCP customer ID history)
   - **Task:** Verify recurring customers are either suppressed from uploads OR sent at $1 value
   - **Task:** Confirm the chosen approach (suppress vs $1) matches the policy decision in Section !

---

## Section 3 — Send to Google Ads & Confirm Acceptance

### Upload Fields

| Field | Source | Compliance Check |
|-------|--------|------------------|
| `gclid` | CallRail match or form capture | [ ] Missing GCLID tracked as known gap, not failure |
| `conversion_action` | One of three IDs (7576326162, 6802897127, 6794281105) | [ ] Matches the action that fired the stage |
| `conversion_date_time` | Frozen `booked_at` / `completed_at` / `job.created_at` | [ ] In account timezone; within click-conversion window |
| `conversion_value` | Job value (cents ÷ 100) for Converted | [ ] Overrides $250 default; currency verified |

### Per-Field Tasks

- [ ] **`gclid` field**
  - **Task:** Find where `gclid` is sourced (CallRail or form); verify it is passed to the upload payload
  - **Task:** Confirm that records with missing GCLID are logged as a gap, not rejected as errors
  - **Task:** Check the `gads_conversion_uploads` table for a `gclid_missing` or similar flag

- [ ] **`conversion_action` field**
  - **Task:** Find the three Google Ads conversion action IDs in the codebase (7576326162, 6802897127, 6794281105)
  - **Task:** Verify each conversion type maps to the correct ID in the upload payload
  - **Task:** Confirm the ID is looked up dynamically (not hardcoded) in case IDs change

- [ ] **`conversion_date_time` field**
  - **Task:** Find where the timestamp for each conversion type is sourced (booked_at, completed_at, job.created_at)
  - **Task:** Verify the timestamp is converted to account timezone before upload (not sent as UTC)
  - **Task:** Confirm the timestamp is within the click-conversion window for the action

- [ ] **`conversion_value` field**
  - **Task:** Find where conversion value is set; verify it uses `options[].total_amount / 100`
  - **Task:** Confirm the value only applies to Converted leads (not Scheduled or Qualified)
  - **Task:** Verify currency is USD (no currency conversion needed)

### Response Handling

- [ ] **Store success/error per row** in `gads_conversion_uploads` table
  - **Task:** Find the `gads_conversion_uploads` table schema; verify it has columns for `success`, `error_message`, `gads_response_id`
  - **Task:** Find the code that inserts the upload response into the table; confirm it captures both success and failure

- [ ] **Surface partial-failure errors** — not swallowed silently
  - **Task:** Find where upload errors are handled; verify they are NOT caught and discarded
  - **Task:** Confirm errors are written to the `gads_conversion_uploads` table AND surfaced somewhere visible (UI, logs, alerts)

- [ ] **Re-send capability** for failed uploads
  - **Task:** Find any mechanism to retry a failed upload (button, scheduled job, manual trigger)
  - **Task:** Verify re-send uses the frozen timestamp (not a new `now()` as the conversion time)

---

## Section 4 — Monitor for Missing Conversions

### Monitoring Checks

| Check | Fires When | Compliance Check |
|-------|-----------|------------------|
| Scheduled but no source | Booked estimate has no CallRail/form/LSA match | [ ] Unattributed lead flagged |
| Qualified but never Scheduled | Completed estimate with no prior booked snapshot | [ ] Snapshot logic gap detected |
| Converted but not uploaded | Job exists with GCLID but no successful upload row | [ ] Missing upload detected |
| Upload error / rejected | Google returned error for a row | [ ] Error surfaced for re-send/fix |
| Stale snapshot | Status advanced in HCP but no event row written | [ ] Sync gap detected |

### Per-Check Tasks

- [ ] **Scheduled but no source**
  - **Task:** Find or write a query that joins booked estimates to CallRail/form/LSA matches
  - **Task:** Confirm the query returns estimates that are `scheduled` but have no `gclid` or lead source
  - **Task:** Verify this gap appears in the monitoring UI or alert output

- [ ] **Qualified but never Scheduled**
  - **Task:** Find or write a query that checks for estimates where Qualified event exists but no Scheduled event precedes it
  - **Task:** Confirm the query catches cases where `completed_at` or approved snapshot exists without a prior `booked_at` snapshot
  - **Task:** This indicates the snapshot tracker missed a status transition

- [ ] **Converted but not uploaded**
  - **Task:** Find or write a query that joins `gads_conversion_uploads` (successful uploads) against jobs with `approval_status` = approved
  - **Task:** Confirm the query returns jobs that are approved + have a GCLID but no successful upload row
  - **Task:** Verify this appears as a pending or failed item in the monitoring UI

- [ ] **Upload error / rejected**
  - **Task:** Query `gads_conversion_uploads` for rows where `success = false` and `error_message` is not null
  - **Task:** Confirm these errors surface somewhere visible (dashboard card, log, alert) — not just in the DB

- [ ] **Stale snapshot**
  - **Task:** Find or write a query that detects status changes in HCP that have no corresponding event row in the local DB
  - **Task:** Example: estimate `updated_at` moved forward but no new `conversion_events` row was written
  - **Task:** This requires comparing HCP `updated_at` against the last event timestamp in the local table

### Dashboard/Alert Requirements

- [ ] **Monitoring dashboard exists**
  - **Task:** Find the monitoring dashboard or UI component
  - **Task:** Confirm it displays all 5 gap conditions

- [ ] **Alerts fire automatically**
  - **Task:** Find any scheduled job or trigger that runs the gap queries
  - **Task:** Verify alerts are sent (email, Slack, PagerDuty) when gaps are found

- [ ] **Partial-failure errors visible, not silent**
  - **Task:** Confirm upload failures appear in the UI, not just in server logs
  - **Task:** Verify operators can see which specific conversions failed and why

---

## Section ! — Decisions to Make

> These are policy decisions — implementation must reflect the chosen answers. Check the current codebase to determine if these have been explicitly decided and implemented.

- [ ] **Decision 1:** Scheduled & Qualified → observation-only (`include_in_conversions: false`) or biddable?
  - *Lean: keep observation-only — bid on Converted, watch upper funnel*
  - **Task:** Find the Google Ads conversion action configuration for the Scheduled and Qualified actions
  - **Task:** Verify `include_in_conversions` is set to `false` for both (or confirm they are NOT set up as conversion actions at all)
  - **Task:** If they are being uploaded as biddable conversions, this is a gap

- [ ] **Decision 2:** LSA — CallRail-only, or build Google LSA direct integration?
  - *Lean: build integration for proper lead-level attribution*
  - **Task:** Search for any Google LSA API integration code (search for "lsa", "local services", "google local services")
  - **Task:** If no LSA integration exists, verify CallRail is the only attribution source for LSA leads
  - **Task:** Determine if the CallRail-only approach is causing attribution gaps for LSA leads

- [ ] **Decision 3:** Recurring & referral leads — exclude from uploads, report-only, or send at $1?
  - *Lean: exclude from Google uploads, keep for internal reporting*
  - **Task:** Find where repeat customers and referral leads are detected
  - **Task:** Verify the current behavior: are they excluded, sent at $1, or sent at full value?
  - **Task:** Check if there's a `lead_source` filter on the upload logic that excludes these sources

- [ ] **Decision 4:** Qualified/Converted counting — `MANY_PER_CLICK` or `ONE_PER_CLICK`?
  - *Many-per-click can inflate when one customer spawns several estimates/jobs*
  - **Task:** Find the Google Ads conversion action settings for Qualified and Converted
  - **Task:** Verify the counting method matches the policy decision
  - **Task:** If Many-per-click is in use, check for evidence of inflation (one customer, multiple conversions)

---

## Implementation Artifacts to Examine

> For each artifact below: open it, find the relevant code sections, and apply the checks from prior sections.

- [ ] **`supabase/functions/gads-conversion-upload/`** (or similar edge function name)
  - **Task:** List all files in `supabase/functions/` and identify anything related to Google Ads, conversion, or upload
  - **Task:** Review the upload function signature, payload construction, and response handling
  - **Task:** Verify the three conversion action IDs are present (7576326162, 6802897127, 6794281105)

- [ ] **`supabase/migrations/` for `gads_conversion_uploads` table**
  - **Task:** Find the migration that creates `gads_conversion_uploads`; note the columns and indexes
  - **Task:** Verify the table has `success`, `error_message`, `gads_response_id`, `gclid`, `conversion_action`, `conversion_date_time`, `conversion_value`
  - **Task:** Check for any `conversion_events` or `estimate_snapshots` table that tracks status transitions

- [ ] **`supabase/migrations/` for snapshot tracking tables**
  - **Task:** Find any table that stores snapshots of `updated_at` at each status transition (sent-snapshot, approved-snapshot)
  - **Task:** Verify the snapshot table links to the estimate ID and stores the frozen timestamp

- [ ] **`horizon-dashboard/` — booking page / conversion tracking UI**
  - **Task:** Search `horizon-dashboard/src/` for `gads`, `conversion`, `google ads` references
  - **Task:** Find the monitoring dashboard or conversion log UI
  - **Task:** Verify the UI displays upload results (success/failure counts, error messages)

- [ ] **CallRail integration code**
  - **Task:** Find where CallRail is called (edge function, background job, external script)
  - **Task:** Verify phone number → estimate matching is implemented
  - **Task:** Verify GCLID is retrieved from CallRail and stored on the conversion event

- [ ] **GTM/form GCLID capture implementation**
  - **Task:** Find the GTM container or tag configuration for the booking page
  - **Task:** Verify the GCLID variable is set from the URL parameter (gclid, gclsrc)
  - **Task:** Verify the GA4 event tag fires on form submission and includes the GCLID

- [ ] **Housecall Pro sync code**
  - **Task:** Find the code that syncs estimates from HCP to Supabase
  - **Task:** Verify it captures all required fields: `options[].status`, `options[].approval_status`, `assigned_employees`, `work_timestamps`, `lead_source`
  - **Task:** Verify `updated_at` is tracked so snapshot-on-change can be detected

---

## Summary Scoring

| Section | Items | Compliance Check |
|---------|-------|------------------|
| 0 — 5-Step Pipeline | ~5 tasks | _ / 5 |
| 1 — Event Detection | ~28 tasks | _ / 28 |
| 2 — Lead Source Linking | ~14 tasks | _ / 14 |
| 3 — Google Ads Upload | ~13 tasks | _ / 13 |
| 4 — Monitoring | ~15 tasks | _ / 15 |
| ! — Decisions Implemented | ~10 tasks | _ / 10 |
| Implementation Artifacts | ~14 tasks | _ / 14 |
| **Overall** | **~99 tasks** | **%** |

---

## How to Use This Checklist

1. **Pick a section** (e.g., Section 3 — Google Ads Upload)
2. **Work through each checkbox** — the **Task:** lines underneath each item specify exactly what to look at and how to verify it
3. **Mark `[x]`** when verified compliant, `[gap]` when non-compliant, or `[n/a]` if not applicable
4. **Note specific gaps** in the Comments column or in a separate `gaps.md` file
5. **Sum up the score** in the Summary table above
6. **Prioritize fixes** based on which sections have the most gaps
