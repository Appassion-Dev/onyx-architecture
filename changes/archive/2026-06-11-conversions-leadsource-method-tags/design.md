## Context

The conversions roll-up renders each estimate as a `PipelineRowItem` with a
label cluster (estimate # + customer name) and a five-slot metric rail
(Stage / Method / Push / Acceptance / Value). Today the Method cell shows a
single `GCLID ×N` badge derived from `row.all_gclids.length`, and there is no
inline indication of the lead's source or whether it arrived as a call or a
booking.

All data needed is already on `PipelineRow` (from `vw_conversion_candidates`):
`lead_source`, `first_touch_medium`, `has_form`, `call_count`,
`booking_gclid` / `qualified_gclid` / `converted_gclid`, `all_gclids`,
`customer_email`, `customer_mobile`. No backend change is required.

The existing `classifyMethod(row, stage)` returns three buckets
(`with_gclid` / `user_data_only` / `none`) and powers the rollup tri-cell
counts. It deliberately collapses GCLID-with-identifiers and GCLID-only into
`with_gclid` because the payload builder uploads via GCLID in both cases. The
new per-row tag needs a finer distinction.

## Goals / Non-Goals

**Goals:**
- Two light-colored inline tags per row: house-call lead source and call/booking.
- Three colored Method tags per row that reflect the actual upload mechanism:
  GCLID+ECL, GCLID, ECL.
- Keep rollup Method counts intact; only update their labels/tooltip wording.

**Non-Goals:**
- No change to `vw_conversion_candidates`, edge functions, or the payload
  builder.
- No change to the rollup Method *count* semantics (still
  `with_gclid / user_data_only / none`); only display labels change.
- No change to the Stage / Push / Acceptance / Value cells.

## Decisions

### Decision: Add a finer classifier rather than overload `classifyMethod`
Add `classifyRowMethod(row, stage): 'gclid_ecl' | 'gclid_only' | 'ecl_only' | 'none'`
to `classifyMethod.ts`, reusing the existing `hasUserIdentifier` and
`stageGclid` helpers. Leave `classifyMethod` (3-bucket) untouched so rollup
counts are unaffected.
- _Why not extend `classifyMethod` to 4 buckets?_ It feeds `MethodCounts`
  (3 fields) consumed by the rollup; widening it would ripple through
  `computeStats`, `RollupTriCell`, and tests for no rollup-level benefit. The
  per-row need is display-only.

### Decision: Per-stage GCLID basis for the Method tag
In all-stages mode each row is a `StageEvent` with `eventStage`; in single-stage
modes the active stage is known. Resolve the stage the same way the row already
resolves its lifecycle (`stageKey = eventStage ?? (mode if qualified/converted else 'booking')`)
and read `{stage}_gclid`. Fall back to `all_gclids.length > 0` only when no
stage-specific gclid column applies (defensive; in practice stageKey always
resolves). This matches `rollup-metric-columns`' per-stage `{stage}_gclid` rule,
so a row's tag is consistent with the bucket it lands in at the rollup.

### Decision: Call vs. booking driven by `first_touch_medium`
Primary signal is `first_touch_medium`: `'call'` → **Call**, `'form'` →
**Booking**. When `first_touch_medium` is NULL/other, fall back to `has_form`
(→ Booking) then `call_count > 0` (→ Call). If none resolve, render nothing for
that tag (the lead-source tag may still render). This mirrors the existing
gads-reconciliation view classification.

### Decision: Tag colors and styling
Reuse the existing light tag style (`rounded-full border px-2 py-0.5 text-[10px]
font-semibold`). Color assignments:
- GCLID+ECL → light green (`border-[#cfe9e1] bg-[#ebfbf6] text-[#017a50]`).
- ECL → light blue (`border-[#d7e4ff] bg-[#f0f4ff] text-[#4962a8]`).
- GCLID-only → keep the existing GCLID purple (`#eef2ff` / `#4318ff`).
- Lead-source + call/booking tags → light neutral/blue tints consistent with the
  row's other light tags.
Final hexes are confirmed in the spec scenarios; exact shades may be nudged at
implementation to match the design system.

### Decision: Keep the GCLID tooltip
The GCLID+ECL / GCLID tags retain the existing hover tooltip listing
`all_gclids` values. The ECL tag (no GCLID) shows no GCLID tooltip.

## Risks / Trade-offs

- [Row crowding — up to four tags now sit in the label cluster] → Tags are
  `text-[10px]` and the cluster already wraps (`flex-wrap`); the missing-stage
  warning shares the row without issue.
- [Per-stage vs. all_gclids divergence — a row may have `all_gclids` populated
  but a NULL stage-specific gclid] → Intentional: the tag reflects what the
  *current stage's* payload sends, matching rollup semantics. The GCLID tooltip
  still lists all gclids for transparency.
- [Label drift between per-row tags and rollup counts] → Rollup keeps
  `with_gclid` (= gclid_ecl + gclid_only). Since gclid_only "never happens",
  the relabeled `gclid+ecl` count stays accurate in practice; the tooltip notes
  it counts any-GCLID uploads.

## Migration Plan

Pure frontend, additive. Deploy with the dashboard build; no data migration or
backfill. Rollback is reverting the three touched files.
