# May 11–17, 2026 — Changes Report

A walkthrough of every OpenSpec change touched between May 11 and May 17 inclusive. Each entry notes status, then breaks the work down into what landed in the **database** (schema, views, functions, migrations) and in the **frontend** (Conversions page, hooks, components). Two changes (`conversion-attribution-overhaul` and `gads-conversion-error-dispositions`) are in-progress — they were *opened* this week; their bulk implementation lands the following week (see the May 18–24 report).

---

## High-level overview of the week

The week had two jobs: **close the silent attribution data-loss holes in the GCLID pipeline, and clear structural debt before the next wave of feature work.**

Three threads run through the week:

1. **Stop losing conversions to time-window mistakes.** The discovery phase had been picking the *oldest* known Google click for a customer — correct for first-touch attribution, but it silently produced unuploadable rows whenever that oldest click pre-dated Google's lookback window. Those rows never uploaded and never expired; they accumulated retries forever. `tighten-gclid-attribution-window` plugged the immediate hole, and `conversion-attribution-overhaul` opened the much larger follow-up that rethinks the resolver, the discovery gates, and the upload cadence end-to-end.

2. **Refactor before you renovate.** The main Conversions page had grown to a single 2,040-line file, and the next planned wave (the rollup-rail redesign, new columns, new stages) was effectively blocked by its size. `refactor-conversions-page` moved the file's internal seams onto disk as a small extensible feature folder — no behavior change — so the following week's UX work could land in small, reviewable PRs.

3. **Open the foundations that next week builds on.** Both in-progress changes were conceived this week. `gads-conversion-error-dispositions` framed the move from truncated 500-character error strings to a typed, policy-driven disposition system; its migrations and UI land the following week.

Net state by Sunday: one concrete attribution loss was fixed and re-discovered, the Conversions page monolith was broken into a feature folder with documented extension points, and the two large in-progress overhauls (attribution + error dispositions) were specified and underway.

---

## May 13 — Closing a silent GCLID data-loss gap, and opening a much larger attribution overhaul

### `tighten-gclid-attribution-window` — *archived*

The discovery phase picked GCLIDs for qualified and converted leads using `ORDER BY first_seen_at ASC LIMIT 1` — deliberately choosing the *oldest* known click for a customer. Correct for first-touch attribution, except when that oldest click pre-dated the conversion event beyond Google Ads' `click_through_lookback_window_days`. Those rows never uploaded successfully and never expired — they accumulated retries indefinitely, were invisible to the existing 90-day recency expiry, and represented silent conversion data loss.

#### Database

- New migration replacing `get_pending_qualified_lead_conversions()` and `get_pending_converted_lead_conversions()` with lookback-windowed GCLID subqueries: only GCLIDs with `first_seen_at >= conversion_datetime - INTERVAL '<N> days'` are eligible for first-touch selection. When no GCLID falls in the window, the row is discovered with `gclid = NULL` and relies on enhanced conversions (hashed email/phone) for attribution.
- Optional one-time cleanup migration to re-discover / update existing `pending` rows whose stored GCLID pre-dates `conversion_datetime` beyond the lookback window.
- No change to the `gads_conversion_uploads` table schema, and none to the upload edge function — the recency window there already handled its constraint correctly. The `booking_lead` stage is untouched (it uses a per-estimate GCLID lookup, not `customer_gclids`).

#### Frontend

- None. No dashboard/UI changes.

#### Specs

- [full-stack-architecture/spec.md](openspec/specs/full-stack-architecture/spec.md) updated to document both Google Ads time-window constraints (upload recency + click lookback), their reference points, and a diagram of how they relate — plus a new standing rule that the architecture spec is updated whenever a pipeline feature ships.
- [customer-gclid-attribution/spec.md](openspec/specs/customer-gclid-attribution/spec.md) gains a requirement that GCLID resolution applies the click-lookback window filter relative to the conversion-event timestamp.

(Modifies the `customer-gclid-attribution` and `full-stack-architecture` capabilities; no new capability folders.)

### `conversion-attribution-overhaul` — *in progress*

Opened the same day. Diagnostic analysis of `gads_conversion_uploads` surfaced two large, distinct attribution defect classes: (1) some estimates convert but never produce a `qualified_lead` row, because the qualified gate keys on `estimates.work_status IN ('complete rated','complete unrated')` while real HCP lifecycles establish qualified-quality earlier (the most common stuck status is `'created job from estimate'`); and (2) many `qualified_lead` rows carry `gclid IS NULL` even though the customer has a usable GCLID in `customer_gclids` today — because the resolver picks the *oldest* click and drops to NULL when it falls outside the window, discovery never re-resolves an existing row, and frequent uploads commit NULL-gclid rows to Google before late-arriving CallRail/booking-tag data can populate `customer_gclids`. The proposal bundles seven traceable changes.

#### Database

- **(BREAKING) Rewrite the GCLID resolver** from "oldest, ASC" to **newest in-window, DESC** against `customer_gclids` within the 90-day click-lookback window. The resolver returns NULL only when the customer has *no* in-window GCLID — killing the failure mode where a stale oldest entry gets filtered out and NULL is returned despite fresher in-window clicks existing.
- **Add a re-attribution pass** to `discover_pending_conversions()` and `discover_pending_conversions_for_estimate()`: re-run the modern resolver against existing rows where `status = 'pending' AND gclid IS NULL AND conversion_type IN ('qualified_lead','converted_lead')`, updating the GCLID in place. Once a row leaves `pending`, it is not retroactively touched. This breaks the "NULL is sticky" lifecycle.
- **(BREAKING) Change the qualified-lead gate** in `get_pending_qualified_lead_conversions()` to fire when an estimate has at least one `estimate_options` row with `approval_status IN ('approved','pro approved')` AND `total_amount > 0`, removing the `estimates.work_status` allowlist. Qualified now reflects customer acceptance of measurable scope, not the rating step.
- **(BREAKING) Change the converted-lead gate** in `get_pending_converted_lead_conversions()` to fire when a `jobs` row exists for the estimate (via `jobs.original_estimate_id`), replacing the `estimate_options.approval_status` gate.
- **(BREAKING) Resolve the GCLID once per estimate per discovery run** and share it across all three stage rows (booking / qualified / converted), hoisting the resolver out of the per-stage detection functions. The per-stage 90-day window check moves to **upload time**.
- `vw_conversion_candidates` and `vw_gads_upload_reconciliation_daily` to be reviewed/updated where their stage semantics depend on the old gate definitions. Existing rows are *not* retroactively reconciled (they become fossil rows); the re-attribution pass does still update NULL-gclid pending rows.

#### Frontend

- **Per-stage GCLID badge.** In `booking`/`qualified`/`converted` modes the badge reflects the GCLID actually stored on that stage's `gads_conversion_uploads` row (`booking_gclid` / `qualified_gclid` / `converted_gclid`) rather than the estimate-wide `all_gclids` pool — making the badge and the column-level GCLID total tautologically coherent. `pre-discovery` mode retains the pool view. No schema change needed (the per-stage columns are already exposed by `vw_conversion_candidates`).

#### Edge function

- `google-ads-conversion-upload` cron reduced from frequent to **once per day**, giving the discovery + re-attribution loop a longer settling window before any NULL-gclid row is committed to Google as enhanced-conversion-only. The manual UI upload path is unaffected.
- Per-stage in-window check at upload time: a stage drops its outbound `gclid` to NULL (falling back to enhanced conversions) when the stored GCLID's `first_seen_at` is more than 90 days before that stage's `conversion_datetime` — without rewriting the stored row.

Note: qualified and converted events will fire earlier in the funnel after this lands, so Smart Bidding models may need a brief re-learning period. Existing pgTAP tests covering the gates and lookback window need updating.

---

## May 14 — Cleaning the house before the next renovation

**`refactor-conversions-page`** — *archived*

`horizon-dashboard/src/components/pages/ConversionsPage.tsx` had grown to **2,040 lines / ~92 KB** in a single file — ~25 inline components, ~10 pure helpers, 4 row-detail data widgets (each with its own `useQuery`), 5 pieces of page state, and ~470 lines of JSX. The next planned wave (table-structure changes, hook swaps, new pipeline stages) was blocked by the monolith: every change forced a scroll through the whole file, made diffs noisy, and risked unrelated regressions. Refactoring first kept the behavioral PRs small and bisectable.

### Database

- None. Pure structural refactor — no schema, edge-function, or network change.

### Frontend

- All conversions-page code moved into a dedicated feature folder at [horizon-dashboard/src/components/conversions/](horizon-dashboard/src/components/conversions/), mirroring the [booking/](horizon-dashboard/src/components/booking/) pattern. `pages/ConversionsPage.tsx` becomes a thin re-export of the orchestrator (router import path unchanged); `/conversions/config` moves under `conversions/config/`.
- Split into pure-logic / hooks / components layers: shared `types.ts` and `constants.ts`; pure functions under `lib/` (`classifyChannel`, `computeStats`, `buildHierarchy`, `getPendingEstimateIds`, `getPhaseConfig`, format helpers); custom hooks under `hooks/`; presentational primitives, hierarchy blocks, row, row-detail panels, and dialog under `components/`.
- Extracted `useConversionFilters(rows)` owning the entire filter cluster (mode + channel + campaign + assignee state, derived `filteredRows`, derived option lists, `activeFilterCount`, `resetFilters`) — the single-file extension point for future filter dimensions.
- Extracted `useBulkUpload(refetch)` owning the dialog-target state, the 5-second cancellable countdown, the toast lifecycle, and the upload `fetch` call.
- Extracted `useConversionsPipeline()` and `useConversionConfigs()` wrapping the two `useQuery` calls; the pipeline-rows query becomes the single point future table-structure changes will touch.
- Row-rendering contract codified as `<MonthCard> → <WeekBlock> → <SourceGroupBlock> → <PipelineRowItem>`, taking `mode`/`configs`/`refetch` as drilled props (no context); `PipelineRowItem` keeps its `memo` wrapper and stable prop identities.
- Stage-rendering contract codified via a `<PipelineStrip>` whose cells are driven by `getPhaseConfig(stage, row, configs)` — adding a stage becomes: extend `ConversionMode`, add a `MODE_CONFIG` entry, add a `getPhaseConfig` branch, no other edits.
- No behavior or visual change; query keys (`'gads-conversions-pipeline'`, `'gads-conversion-config'`), props, and Supabase calls unchanged; no new dependencies; no tests added (per user request).

**New capability folder:** `conversions-page-structure`.

---

## May 15 — Making upload errors operator-actionable (opened)

**`gads-conversion-error-dispositions`** — *in progress*

The current upload pipeline collapses every Google response into "pending" or "failed", with errors truncated to 500 characters of free-form text. The result: structured error codes are lost before they reach storage, transient errors get marked permanent (and never retry), permanent config errors stay "pending" and retry forever, and operators have no aggregate view of what's actually blocking uploads. This change was opened and specified this week; its full database, frontend, and edge-function implementation lands the following week (see the May 18–24 report).

### Database (planned)

- New `gads_error_dispositions` table mapping each error code to a policy (`retry` / `fix-config` / `fix-data` / `fix-triage` / `drop` / `deliberate`), with per-code retry limits, minimum wait times, alerting flags, and remediation text.
- New structured columns on the upload rows (`error_code`, `error_namespace`, `error_detail` jsonb) plus a richer `lifecycle` enum replacing the overloaded `status`.
- A view joining uploads to dispositions so a config change is instantly reflected in every existing row with no backfill.

### Frontend (planned)

- An admin page where operators can edit dispositions.

### Edge function and tooling (planned)

- A vendored Google Ads error catalog (proto → JSON) so the edge function and dashboard share one source of truth, with a script that re-fetches on API version bumps.
- A disposition-driven state machine in the edge function that uses these signals to retry the right things and stop retrying the rest.

---

## Themes for the week

1. **Attribution honesty, made concrete.** Both GCLID changes share one origin story: the pipeline had been quietly losing or degrading click-ID attribution through time-window edge cases. `tighten-gclid-attribution-window` fixed the immediate "oldest click is out of window → row never uploads, never expires" loss; `conversion-attribution-overhaul` generalized the fix into a newest-in-window resolver, a re-attribution pass, and lifecycle-correct discovery gates.

2. **Refactor before feature.** `refactor-conversions-page` is deliberately behavior-free. Its entire value is unblocking the following week — the rollup-rail redesign, new columns, and new stages all plug into the seams (`useConversionFilters`, `getPhaseConfig`, the `MonthCard → … → PipelineRowItem` chain) this change put on disk.

3. **Foundations opened now, implemented next.** The two in-progress changes were conceived this week but land mostly the next: `gads-conversion-error-dispositions` is the foundation the whole following week of upload work depends on, and `conversion-attribution-overhaul` reshapes the discovery gates that the rollup redesign's Method/Acceptance columns ultimately report on.
