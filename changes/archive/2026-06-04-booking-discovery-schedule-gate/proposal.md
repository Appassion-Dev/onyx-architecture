## Why

Booking-lead conversion discovery currently fires for **any** estimate that carries an attribution signal, regardless of whether a real appointment was ever booked. We want to gate `booking_lead` discovery so it only fires once an estimate has genuinely been **scheduled**. The original request proposed gating on `estimates.work_status = 'scheduled'`, but investigation showed that field is a transient, point-in-time status that makes conversions age out and get lost — and that the more reliable signal it intended to capture (`schedule.scheduled_start`) is not currently being imported at all. This change defines a gate built on durable signals and fixes the import gap it depends on.

## Background: Original Request

> Modify the existing unpushed migration to apply a new gate to the booking discovery function.
> **Gate (all 3 required):** `estimates.work_status = 'scheduled'` **AND** `schedule.scheduled_start IS NOT NULL` **AND** `assigned_employees[]` is non-empty. Conversion date stays the same for now (`estimates.created_at`).

The "existing unpushed migration" is `supabase/migrations/20260526000002_booking_lead_repeat_customer_gclid.sql`, which redefines `public.get_pending_booking_lead_conversions()`. It is confirmed **not yet deployed** — the live database still runs the older two-branch version of the function — so the gate can be folded into that same migration rather than introducing a new one.

## Investigation Findings

1. **`work_status` is a transient, current-state field.** Of 7,716 estimates, only 154 are currently `work_status = 'scheduled'`; thousands sit in later states (`created job from estimate`, `complete rated`, etc.) — they *were* scheduled but have moved on. A booking is a past event; gating it on current state means an estimate is only eligible during the brief window it sits in `'scheduled'`, and the discovery cron must catch it then. Combined with the existing once-ever `NOT EXISTS` guard, a missed window means the conversion is lost permanently.

2. **`schedule.scheduled_start` is the durable signal — but it is not being imported.** The HCP API *does* return it: `supabase/housecall_dtos/Estimate` defines both `schedule` and `work_timestamps`, and a live `GET /estimates` response confirms they are populated. Critically, the `schedule` object **persists through the lifecycle** — a live `complete rated` estimate still carried `schedule.scheduled_start` — so "an appointment was booked" is a durable fact, unlike `work_status`. However, the bulk importer never writes it: `transformSchedule` (and `transformWorkTimestamps`) in `supabase/functions/hcp-import-data/import-estimates.ts` are **defined but never called** — confirmed in both the repo and the deployed edge function (v39). Phase 7's `batchUpsertRelated` wires up assignments, option tags, notes, and options, but omits schedules.

3. **The `schedules` table is populated only by two narrow paths, neither being the normal import:**
   - `hcp-booking` (the booking-widget webhook) writes clean, deterministic `sch_<estimateId>` rows — but only for direct widget bookings (106 estimates ever).
   - A one-time Dec 3–4 2025 backfill wrote 311,199 rows using a non-deterministic `sched_est_<id>_<Date.now()>` id — append-only, so it duplicated ~276 rows per estimate across only ~1,019 estimates. It is frozen and never updated since.
   - Result: of the 154 currently-`scheduled` estimates, only **41** have any `scheduled_start` row (34 from the stale backfill, 7 from `hcp-booking`); **113 have none**, including 28 created since May 2026.

4. **The original 3-condition gate would collapse discovery to ~41 estimates ever** and would silently worsen over time, because the binding constraint (`work_status='scheduled'` ∩ `schedules` coverage) is driven by an incomplete, mostly-stale table — not by reality.

5. **`created_at` is the correct conversion datetime.** The "ideal" signal — the moment an estimate *becomes* scheduled — is not available from HCP (the payload has `scheduled_start`, the appointment time, but no transition timestamp). `scheduled_start` itself is the wrong value: it is the future appointment time, not the booking moment, and it distorts Smart Bidding's click→conversion lag. We verified against Google's API docs that there is **no rule rejecting future-dated conversions** and that `CONVERSION_PRECEDES_EVENT` only forbids a conversion *before* the click, so the earlier concern that `scheduled_start` would "break uploads" was unfounded — but `created_at` remains the honest, lag-correct choice and is unchanged.

## Why the Original Request Doesn't Fully Fit, and What We Propose Instead

- **Replace `work_status = 'scheduled'` with `schedule.scheduled_start IS NOT NULL` as the primary "is scheduled" signal.** `scheduled_start` is durable (survives the lifecycle), so conversions don't age out; `work_status` is transient and would lose conversions to cron timing.
- **Keep `assigned_employees[]` non-empty** as an additional corroborating condition (sourced from `estimate_assignments`, which is reliably populated for 7,033 / 7,716 estimates).
- **Drop the attribution source-signal requirement from eligibility — keep it commented out for potential re-add.** The current function requires at least one source signal (`is_booking_form = true`, a `booking_tags` row, a correlated `callrail_leads` row, and — in the unpushed migration — a `customer_gclids` row). These SHALL NOT be used to gate the new/updated discovery; eligibility is defined **solely** by the schedule gate above (`scheduled_start` + `assigned_employees`). The source-signal `WHERE` conditions SHALL be **preserved as inline comments** in `get_pending_booking_lead_conversions()` (not deleted), so they can be re-enabled later without rewriting them. GCLID *resolution* — the separate `COALESCE(booking_tags, callrail_leads[, customer_gclids])` that derives the gclid value for upload — is unaffected and stays.
- **Single source of truth:** the gate (and the commented-out source signals) live only in `get_pending_booking_lead_conversions()`. Both discovery entry points inherit it automatically — the bulk `gads_discover_pending_conversions()` and the on-demand `discover_pending_conversions_for_estimate()` both `SELECT … FROM get_pending_booking_lead_conversions()`, so no second function body needs editing.
- **Keep `conversion_datetime = estimates.created_at`** unchanged.
- **Fix the import gap that the gate depends on:** un-orphan schedule import in `hcp-import-data` so `scheduled_start` is actually populated for bulk-imported estimates, using a deterministic id that converges with `hcp-booking`'s `sch_<estimateId>` convention (no more append-only duplication), plus a one-time backfill and a dedupe of the frozen Dec-2025 rows. Without this, the gate is non-functional.

### Explicit non-goals / unreliable approaches we will NOT use

- **Catching the exact transition into `'scheduled'` is unreliable and SHALL NOT be used as the gate.** It depends on observing a transient state at the right moment between cron runs; misses are permanent.
- **Dating the conversion at the moment-of-becoming-scheduled is not possible to determine reliably.** HCP does not expose a "scheduled_at" transition timestamp, and it cannot be reconstructed from polling without an HCP webhook delivering the state-change event. Until such a webhook exists, `created_at` is the conversion datetime.

## Open Questions

- **Cancelled bookings — undecided.** Because `schedule.scheduled_start` persists after cancellation, a `scheduled_start IS NOT NULL` gate will also match estimates that were booked and then cancelled (`work_status IN ('user canceled', 'pro canceled')`). It is genuinely unresolved whether those should count as `booking_lead` conversions (a booking *did* occur; cancellation came later — Google Ads' usual stance) or be excluded. This is the one place `work_status` might re-enter the gate, as an **exclusion** filter rather than the primary signal. No decision has been made; the specs/design phase must resolve it before implementation.

## Capabilities

### New Capabilities
- `estimate-schedule-import`: The HCP estimate import SHALL populate `schedules` from the estimate payload's `schedule` object, using a deterministic, idempotent id (converging with `hcp-booking`'s `sch_<estimateId>`), plus a one-time backfill of existing estimates and de-duplication of the frozen `sched_est_*` rows.

### Modified Capabilities
- `pipeline-stage-booking`: The "Booking lead discovery criteria" requirement is **replaced** — eligibility is defined solely by the schedule gate (`schedule.scheduled_start IS NOT NULL` AND non-empty `assigned_employees[]` via `estimate_assignments`). The existing attribution source-signal branches (`is_booking_form`, `booking_tags`, `callrail_leads`, `customer_gclids`, and the spec's documented `lead_source IS NOT NULL`) are removed from eligibility and **preserved only as commented-out code** for potential re-add — not transient `work_status='scheduled'` as originally requested. The "Booking lead conversion datetime" requirement is reaffirmed as `estimates.created_at` (unchanged), with the transition-time approach explicitly ruled out.

## Impact

- **Migration:** `supabase/migrations/20260526000002_booking_lead_repeat_customer_gclid.sql` (currently unpushed) — fold the new gate into `get_pending_booking_lead_conversions()` and **rename the file** to reflect its new purpose, since it no longer governs lead-source checks. Proposed name: `20260526000002_booking_lead_schedule_gate.sql` (timestamp prefix kept to preserve migration ordering; safe to rename because it is unapplied). Rewrite the header comment accordingly. Of that migration's two original changes: the `customer_gclids` **eligibility** OR-branch is now **commented out** alongside the other source signals (its broadening is superseded by the schedule gate), while the `customer_gclids` fallback in the GCLID-**resolution** `COALESCE` **stays** (value derivation for repeat customers). The previously-required source-signal `WHERE` branches are retained as inline comments, not deleted.
- **Implication of decoupling eligibility from attribution:** booking_leads will now be discovered for any scheduled + assigned estimate, including those with no GCLID (e.g. non-PPC / walk-in). Such rows enter the pipeline but are not uploadable to Google Ads (null gclid) and will surface as not-uploadable downstream — a deliberate consequence of using the schedule gate alone.
- **Edge function:** `supabase/functions/hcp-import-data/import-estimates.ts` — un-orphan `transformSchedule` into Phase 7 with a deterministic id + `onConflict`; redeploy. (`transformWorkTimestamps` remains orphaned and is noted but out of scope for this change.)
- **Data:** one-time schedule backfill for existing estimates; dedupe ~311k frozen `sched_est_*` rows (keep one per estimate).
- **Downstream:** `booking_lead` discovery volume changes (only genuinely-scheduled, attributed estimates qualify); the `gads_conversion_uploads` pipeline and pipeline view reflect the tighter criteria. No change to upload mechanics or `conversion_datetime`.
- **Pre-existing drift to be aware of:** the live `get_pending_booking_lead_conversions()` lags the migration file, and the `pipeline-stage-booking` spec documents a `lead_source IS NOT NULL` branch not present in the live function — to be reconciled when specs are written.
