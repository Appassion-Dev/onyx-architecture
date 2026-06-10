## Context

The conversions rollup (`ConversionsPage` → `MonthsTable` → ... → `SourceGroupBlock` → `PipelineRowItem`) renders one estimate per row in single-stage modes and one stage event per row in all-mode. Each estimate carries three stage statuses on its `PipelineRow` (`booking_status`, `qualified_status`, `converted_status`); a `null` status means that stage has not been discovered yet, which `StageDetail` already surfaces as "Not discovered" inside the expanded panel.

There was previously no collapsed-state signal of incomplete discovery, so operators expanded rows one by one to find gaps, and channel headers gave no aggregate view. The expanded detail tables (`EstimateOptionsTable`, `JobDetailSection`) also linked to HousecallPro inconsistently.

This change is purely presentational — it reads existing view columns and adds no data dependencies.

## Goals / Non-Goals

**Goals:**
- Make incomplete stage discovery visible at the collapsed row level and at the channel rollup level.
- Reuse one definition of "discovered" so the row and channel signals never diverge.
- Tighten the HousecallPro deep links in the expanded detail tables.

**Non-Goals:**
- No change to how stages are discovered (`discover_pending_conversions*` is untouched — see `per-estimate-discovery`).
- No change to the database, `vw_conversion_candidates`, or any RPC.
- No new warning at the Week or Month rollup levels (channel is the requested aggregation level).

## Decisions

**Single source of truth for "missing stages" — `getMissingStages(row)`.**
A shared helper in `lib/missingStages.ts` resolves the missing stages, and both `PipelineRowItem` and `SourceGroupBlock` consume it, so the row badge, the channel aggregate, and the tooltips all derive from the same rule. Alternative considered: inline the checks in each component — rejected because the rule would drift and the stage labels would be duplicated.

**Sequential gap rule, not "any null stage".**
Booking → Qualified → Converted is a strictly sequential process: reaching a later stage implies the earlier ones happened. So an undiscovered stage is only anomalous when a *later* stage has been discovered (a gap). The helper finds the index of the latest discovered stage and returns the undiscovered stages before it; a trailing undiscovered stage (e.g. Booking present, Qualified/Converted not yet reached) is normal progression and is NOT reported. Examples: Qualified present + Booking null → `["Booking"]` (warn); Booking present + Qualified null → `[]` (no warn); Converted present + Booking null → warn. Alternative considered: flag every null stage — rejected because it would fire on every estimate still moving through the funnel, drowning the genuine out-of-order anomalies.

**Row badge = count of missing stages (0–2), color-scaled.**
Because Converted is the final stage, at most Booking and Qualified can precede a discovered stage, so the per-estimate count is bounded at 2: 1 → yellow `#f5c518`, 2 → orange `#ff8a3d` (a `MISSING_STAGE_COUNT_COLOR` map retains a `3 → red #ee5d50` entry defensively, though the gap rule makes 3 unreachable). The triangle stays the original orange `#ffb547`; only the number is severity-colored. The tooltip lists the named missing stages.

**Channel badge = total missing conversions, not affected-estimate count.**
The channel aggregates many estimates, so the per-estimate 1–3 scale does not apply. The badge shows the sum of missing stages across all estimates in the channel (`reduce` over `getMissingStages(r).length`), which can exceed 3, so it is rendered in the triangle's orange rather than the severity scale. The tooltip disambiguates: "{total} missing conversions across {affected} of {total estimates}".

**All-mode estimate source.**
In all-mode `SourceGroup.rows` is empty and the estimates live on `SourceGroup.events`; in other modes the reverse holds. The channel computation derives unique estimates by deduping `events` on `estimate_id` in all-mode, and uses `rows` directly otherwise — so the aggregate counts each estimate once regardless of mode.

**Inline HCP links in detail tables.**
`EstimateOptionsTable` moves the existing `ExternalLink` anchor out of its trailing column into the Option cell, directly after the option name (the empty trailing `<th>` is removed). `JobDetailSection` gains an `ExternalLink` anchor next to the job ID pointing at `https://pro.housecallpro.com/app/jobs/{job_id}`, matching the URL convention already used across the dashboard.

## Risks / Trade-offs

- **All-mode shows the row badge on every event row for the same estimate** → Acceptable: the badge reflects estimate-level state ("this estimate has missing stages"), which is true for each of its event rows; the tooltip names the same stages consistently.
- **Two different number semantics (row = missing stages, channel = total missing conversions)** → Mitigated by tooltips on both that spell out the meaning; at-a-glance both read as "more is worse."
- **Channel badge not color-scaled** → Intentional, since the total is unbounded and a 1–3 scale would mislead; kept orange to match the triangle.
