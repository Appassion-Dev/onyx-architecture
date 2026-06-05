## Why

The qualified-lead gate written in migration `20260526000001` keys on option **approval** (`approval_status IN ('approved','pro approved')`), but we want qualified to fire on estimate **finalization** — the estimate reaching a settled, non-cancelled state — keyed on `work_status` and anchored to `estimates.updated_at`, the timestamp we verified is both 100% covered and the most faithful proxy (median 0.86 d) for the real estimate-visit completion. Separately, the `work_timestamps` table (the literal completion signal) is a dead, 635×-duplicated, ~6M-row relic frozen since 2025-12-04; we want to revive it now so a following change can adopt it once it carries clean data.

## What Changes

- **(BREAKING) Re-key the qualified gate to estimate finalization.** Rewrite `get_pending_qualified_lead_conversions()` so the gate fires when `estimates.work_status IN ('complete rated','complete unrated','created job from estimate')` **AND** the estimate has ≥1 `estimate_options` row with `total_amount > 0`. This **replaces** the approval-based gate currently in migration `20260526000001`; `approval_status` is no longer consulted (the finalized `work_status` is the commitment proxy). The existing migration file is modified **in place**.
- **Keep `conversion_datetime = estimates.updated_at`.** No fallback chain — it is 100% covered, so there is nothing to fall back to.
- **Keep unchanged:** the conversion value (average of all options' `total_amount / 100.0`), the existing GCLID resolver, and the `NOT EXISTS` de-dup.
- **Revive `work_timestamps`.** `TRUNCATE` the ~6M bloated rows (safe — no inbound FKs, views, or functions depend on the table) and fix the estimate **and** job importers in `hcp-import-data` to (a) use a deterministic id (`ts_est_<id>` / `ts_job_<id>`) and (b) wire the currently-orphaned `transformWorkTimestamps` into the related-records phase, so the table repopulates as one row per estimate/job on the next import.
- **Defer** using `work_timestamps` as a date signal to a following change; `estimates.updated_at` stays primary until the table carries clean data.

## Capabilities

### New Capabilities
- `work-timestamps-import`: `hcp-import-data` populates `work_timestamps` with deterministic, idempotent ids for estimates and jobs, and the legacy bloat is cleared so the table starts clean.

### Modified Capabilities
- `pipeline-stage-qualified`: discovery gate changes from "an approved priced option exists" to "estimate is finalized (`work_status IN ('complete rated','complete unrated','created job from estimate')`) AND a priced option (`total_amount > 0`) exists"; `approval_status` is no longer consulted.

## Impact

- **Database**: rewrite `get_pending_qualified_lead_conversions()` in `supabase/migrations/20260526000001_qualified_lead_gate_approval_status.sql` (not yet deployed); **new** migration `TRUNCATE`-ing `work_timestamps`.
- **Edge functions**: `hcp-import-data` — `import-estimates.ts` and `import-jobs.ts` (deterministic id + wire `transformWorkTimestamps` into `batchUpsertRelated`).
- **Conversion timing in Google Ads**: qualified now fires at estimate finalization and the cohort grows to include the `'created job from estimate'` population. **Trade-off:** finalized-but-unapproved completes (especially `complete unrated`, only ~13% approved) are admitted as qualified — accepted as the cost of a fully-covered, `work_status`-based gate.
- **Not in scope**: GCLID resolver changes, converted-gate changes, and adopting `work_timestamps.completed_at` as the conversion timestamp (all deferred / tracked elsewhere).
