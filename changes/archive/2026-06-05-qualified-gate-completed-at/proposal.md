## Why

The qualified gate currently anchors `conversion_datetime` to `estimates.updated_at` — a 100%-covered but lagging proxy (median ~0.86 d, and ~0.37 d on the currently-covered subset) for the real estimate-visit completion. The literal signal, `work_timestamps.completed_at`, is now revived and importing cleanly (one deterministic row per estimate, no duplication) after the `2026-06-05-qualified-gate-finalization` change wired the importer. That change explicitly **deferred** adopting `completed_at` "until the table carries clean data" — it now does. This change makes the gate prefer the literal completion timestamp where present, falling back to `updated_at` where it is not.

## What Changes

- **Re-key `conversion_datetime` to `COALESCE(work_timestamps.completed_at, estimates.updated_at)`.** Rewrite `get_pending_qualified_lead_conversions()` so the conversion timestamp uses the estimate's `work_timestamps.completed_at` when present, and falls back to `estimates.updated_at` otherwise. `completed_at` is `timestamp without time zone` storing HCP's UTC value; it is interpreted as UTC (`completed_at AT TIME ZONE 'UTC'`) so the COALESCE and the `timestamptz` return type are sound.
- **Align `ORDER BY` to the same coalesced expression** so pending rows order by the actual conversion timestamp they will be uploaded with.
- **Keep unchanged:** the finalization gate (`work_status IN ('complete rated','complete unrated','created job from estimate')` + a priced option), the conversion value (average of all options' `total_amount / 100.0`), the `NOT EXISTS` de-dup, and the **GCLID resolver's 90-day window anchor** (stays on `estimates.updated_at` — the fully-covered anchor — so attribution is consistent across rows regardless of `completed_at` coverage).
- **No importer or schema changes.** `work_timestamps` is already populated by the wired importer; broader `completed_at` coverage is an operational backfill concern, not part of this change.

## Capabilities

### New Capabilities
<!-- None — no new capability is introduced. -->

### Modified Capabilities
- `pipeline-stage-qualified`: the "Qualified lead conversion datetime" requirement changes from "use `estimates.updated_at`" to "use `work_timestamps.completed_at` when present, else `estimates.updated_at`". No other requirement in the capability changes.

## Impact

- **Database**: rewrite `get_pending_qualified_lead_conversions()` (currently deployed with the finalization gate) via a new migration — change only the `conversion_datetime` expression and the `ORDER BY`; a correlated lookup into `work_timestamps` keyed on `estimate_id`.
- **Conversion timing in Google Ads**: where `completed_at` exists, qualified fires ~0.37 d earlier (closer to true completion); where it does not, timing is unchanged. **Coverage today is partial** — `completed_at` drives the timestamp for only ~9% of the ~4,900 qualified cohort (580 of 4,904 have a `work_timestamps` row; 452 have a non-null `completed_at`). The COALESCE degrades gracefully and the `completed_at` share grows automatically as imports backfill the table — no further code change needed.
- **Not in scope**: the finalization gate criteria, GCLID resolver / window anchor, conversion value formula, the converted-lead gate, and any `work_timestamps` backfill/import operation.
