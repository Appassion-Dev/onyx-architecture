## Why

The conversions uploads table shows each estimate's GCLID but not _how_ the lead
arrived (house-call lead source, call vs. booking) nor _which_ Google Ads upload
mechanism actually fires (GCLID, enhanced conversions for leads, or both). Reps
auditing uploads have to expand each row and cross-reference the payload to
answer "did this go up with user data?". Surfacing both inline makes the roll-up
self-explanatory at a glance.

## What Changes

- In the per-estimate row of the channel roll-up, after the estimate/customer
  name, add two light-colored tags:
  - **House-call lead source** — `lead_source` from the estimate record.
  - **Call vs. booking** — driven by `first_touch_medium` (`'call'` → Call,
    `'form'` → Booking), falling back to `has_form` / `call_count`.
- Replace the per-row Method cell's single `GCLID` badge with one of three
  mutually-exclusive colored tags reflecting the actual upload payload:
  - **GCLID+ECL** (light green) — per-stage GCLID present **and** the customer
    has a usable identifier (email/mobile). The common case.
  - **GCLID** — GCLID present, no usable identifier. (Documented but never
    occurs in practice.)
  - **ECL** (light blue) — no GCLID, customer identifier present (enhanced
    conversions for leads only).
  - A dash remains when neither is present.
  - GCLID presence is read per-stage (`{stage}_gclid`) in all-stages event
    rows, falling back to `all_gclids` otherwise.
- Relabel the rollup Method tri-cell sublabel and tooltip to the new
  GCLID+ECL / ECL terminology (the three counts and their semantics are
  unchanged; only the labels change).

## Capabilities

### New Capabilities
- `conversions-row-lead-source-tags`: per-estimate row tags showing the
  house-call lead source and whether the lead was a call or a booking.

### Modified Capabilities
- `conversions-gclid-tag`: the per-row Method cell changes from a single GCLID
  count badge to three colored upload-mechanism tags (GCLID+ECL / GCLID / ECL),
  read from per-stage GCLID plus customer identifier presence.
- `rollup-metric-columns`: the Method tri-cell sublabel/tooltip is relabeled to
  the GCLID+ECL / ECL terminology; counts and bucket semantics are unchanged.

## Impact

- `horizon-dashboard/src/components/conversions/components/pipeline-row/PipelineRowItem.tsx`
  — row label cluster (new tags) and Method cell (three-tag rendering).
- `horizon-dashboard/src/components/conversions/lib/classifyMethod.ts` — add a
  finer classifier that distinguishes GCLID+ECL from GCLID-only (the existing
  3-bucket `classifyMethod` is retained for rollup counts).
- `horizon-dashboard/src/components/conversions/components/primitives/RollupTriCell.tsx`
  — Method sublabel + tooltip text only.
- No database, view, or edge-function changes — all fields
  (`lead_source`, `first_touch_medium`, `has_form`, `call_count`,
  `{stage}_gclid`, `all_gclids`, `customer_email`, `customer_mobile`) already
  exist on `vw_conversion_candidates` / `PipelineRow`.
