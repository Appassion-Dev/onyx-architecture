# May 2026 — Changes Report

A plain-language walkthrough of every OpenSpec change opened in May 2026, both archived (completed) and in-progress, in date order. Each entry notes status, what was done, and any new capability folders created on that date.

---

## May 1 — Rethinking how conversions get detected

**`conversion-detection-v2`** — *archived*

The team rebuilt the core logic that decides whether a lead has "booked," "qualified," or "converted." Previously the three stages were stacked — a lead couldn't be marked "qualified" without first being "booked" — which missed legitimate phone-in and direct-HCP leads.

- The three stages became independent.
- A new lookup table now remembers which Google click ID belongs to which customer, so follow-up estimates still get credit for the original ad click.
- The dollar values shown in the dashboard and sent to Google were reconciled (they previously disagreed).
- The visual chain connecting the three stages on the dashboard was removed.

**New capability folder:** `customer-gclid-attribution`.

---

## May 7 — Knowing where leads actually come from

**`lead-channel-taxonomy`** — *archived*

The dashboard used to bucket leads into four crude categories (calls, form, Thumbtack, other). Replaced with the seven real marketing channels the business spends money on: Google Ads, Google Local Services, Google My Business, Thumbtack, Organic, Direct, Others.

Two related bugs fixed:
- Website-form bookings were saving a blank lead source. Now resolved and saved properly.
- Returning customers had their original lead source overwritten on every rebook. A 90-day window now protects the original attribution.

**New capability folders:** `lead-channel-resolver`, `conversion-channel-grouping`.

---

## May 9 — A very busy day: seven parallel changes around upload reporting and the conversions page

Most of the day was spent reorganizing how the team sees and verifies what's being sent to Google Ads.

- **`upload-reporting-page`** — *archived* — A new "Upload Report" page with three tabs (Booking, Qualified, Converted). For each day/week/month it shows what was uploaded locally vs. what Google actually received, broken down by lead source.
- **`add-upload-reconciliation-reporting`** — *archived* — Spec work establishing the underlying reporting surface: aligning local uploads with Google's daily summaries, with weekly rollups and prior-period comparison.
- **`improve-upload-reconciliation-visuals`** — *archived* — Made the reconciliation table readable at a glance: labeled visual tokens replaced letter codes, clearer period labels, and explicit indicators for matched / local-only / Google-only rows.
- **`split-conversions-analytics-uploads`** — *archived* — The Conversions sidebar item was split into "Analytics" (monitoring upload health) and "Uploads" (working individual rows).
- **`conversion-view-modes`** — *archived* — The Conversions page became mode-aware. Each tab (Pre-Discovery, Booking, Qualified, Converted) now uses its own date field, value formula, and upload action. "All" and "Closed" tabs were dropped; default is Qualified.
- **`gads-conversion-datetime-type`** — *archived* — Changed the conversion timestamp column from text to a proper timestamp type so range queries work correctly.
- **`gads-upload-analytics`** — *archived* — Added a cached layer of Google Ads analytics (attribution, upload health, config drift) so the dashboard doesn't make live Google calls on every page load.
- **`drop-reconciliation-buckets`** — *archived* — Cleanup. With the 7-channel taxonomy in place, the old 4-bucket columns and the dead page using them were removed.

**New capability folders:** `gads-gclid-verification`, `gads-upload-analytics`, `conversion-analytics-page`, `conversions-submenu-navigation`, `upload-report-page`, `upload-reconciliation-reporting`, `upload-reconciliation-visuals`, `conversion-view-mode`, and `full-stack-architecture` (promoted into a capability folder the same day).

---

## May 13 — Closing a silent data-loss gap, and starting a much bigger attribution overhaul

**`tighten-gclid-attribution-window`** — *archived*

The discovery process was picking the *oldest* known Google click for a customer, which is correct for first-touch attribution — except when that oldest click was older than Google's lookback window. Those rows would never upload successfully and never expire; they just accumulated retries forever, invisibly losing conversion data.

The fix added a window filter so only click IDs within Google's allowed lookback get chosen. If no click falls in the window, the row goes through with no click ID and relies on hashed email/phone (enhanced conversions) instead. A cleanup pass also re-discovered existing stuck rows. The architecture spec was updated to document both Google Ads time-window constraints, with a new standing rule that the arch spec gets updated whenever pipeline features ship.

**`conversion-attribution-overhaul`** — *in progress*

Opened the same day, a much larger follow-up bundling seven concrete fixes after diagnostic analysis revealed two big attribution defects: some estimates convert but never produce a qualified-lead row (because the qualified gate keys on a status that misses common HCP lifecycles), and many qualified rows exist with no click ID even though the customer has a fresh one available. Headline shifts:

- Rewrite the click-ID resolver from "oldest" to "newest within window" so a stale old click can no longer cause a NULL result when a fresh one exists.
- Add a re-attribution pass so pending rows with NULL get updated as late-arriving CallRail / booking-tag data arrives.
- Reduce the upload cron from frequent to once-per-day so re-attribution has time to settle before rows commit to Google.
- Change the qualified gate to "estimate has a priced option" (instead of relying on `work_status`).
- Change the converted gate to "a job exists for the estimate" (instead of option approval state).
- Make the per-row click-ID badge per-stage so it stays coherent with the column totals.
- Resolve the click ID once per estimate and share it across all three stage rows; enforce the 90-day window at upload time, not discovery time.

---

## May 14 — Cleaning the house before the next renovation

**`refactor-conversions-page`** — *archived*

A pure structural refactor — no behavior changes. The main Conversions page had grown into a single 2,040-line file. The next round of planned work was effectively blocked by its size.

The page was broken into a dedicated feature folder with separate layers for pure logic, hooks, and components. Nothing visible changed; the point was to create clear extension points so future PRs stay small and reviewable.

**New capability folder:** `conversions-page-structure`.

---

## May 15 — Making upload errors operator-actionable

**`gads-conversion-error-dispositions`** — *in progress*

The current upload pipeline collapses every Google response into "pending" or "failed," with errors truncated to 500 characters of free-form text. The result: structured error codes are lost before they reach storage, transient errors get marked permanent (and never retry), permanent config errors stay "pending" and retry forever, and operators have no aggregate view of what's actually blocking uploads.

The change introduces:
- A vendored Google Ads error catalog (proto → JSON) so the edge function and dashboard share one source of truth, with a script that re-fetches on API version bumps.
- A new `gads_error_dispositions` table that maps each error code to a policy (retry, fix-config, fix-data, fix-triage, drop, deliberate), with per-code retry limits, minimum wait times, alerting flags, and remediation text. Operators can edit dispositions in an admin page.
- New structured columns on the upload rows (`error_code`, `error_namespace`, `error_detail` jsonb, plus a richer `lifecycle` enum replacing the overloaded `status`).
- A view that joins uploads to dispositions so a config change is instantly reflected in every existing row with no backfill.
- A disposition-driven state machine in the edge function that uses these signals to retry the right things and stop retrying the rest.

---

## May 18 — Spec compliance and modular split for the upload function

**`gads-upload-fix-and-refactor`** — *in progress*

Follow-up cleanup after the error-disposition change shipped. Two parts:

- **Spec compliance fixes:** expired rows now write to `error_detail` instead of the legacy `error_message`; stale `error_code` is cleared when rows transition to `excluded` or back to `queued`; a defensive bounds check stops out-of-range error indices from silently marking rows as sent; two minor linter fixes on hashing helpers.
- **Full module split:** the 399-line `handlePost` in the upload edge function is broken into purpose-named modules (`runtime`, `pause-state`, `pickup`, `payload-builder`, `ads-api`, `batches`, `outcomes`, plus types and pure helpers). `index.ts` shrinks to ~70 lines of orchestration. Each module becomes unit-testable in isolation.

---

## May 19 — Redesigning the rollup rail

**`conversions-rollup-redesign`** — *archived*

The biggest UX-level change of the month. The Conversions page rollup rail (the bar showing totals at the month / week / source level) was rebuilt around metrics that map directly to how Google actually receives conversions.

- Old columns (`Rows | GCLID | Uploaded | Sync | Value`) replaced with `Stage | Method | Push | Acceptance | Value`.
- New "All Conv" mode shows booked, qualified, and converted side-by-side.
- New **Method** column splits rows by upload payload: with a click ID, with hashed user data only, or unable to upload — answering the Smart Bidding signal-quality question directly.
- New **Acceptance** column on weekly/monthly rows compares what was sent vs. what Google actually accepted.
- The per-row upload card and the per-week/per-month bulk-upload buttons were all removed in favor of a single top-of-page Upload button that respects current filters.
- The estimate number on each row became a clickable link to HousecallPro; the detail panel now shows customer name, email, phone, and service address.

**New capability folders:** `pipeline-row-hcp-link`, `rollup-acceptance-metric`, `rollup-metric-columns`.

---

## May 20 — Locking down the upload function with tests

**`gads-upload-step-tests`** — *in progress*

After the upload edge function was split into eleven small modules, only two of them had unit tests. The other nine seams were covered only by manual end-to-end runs against a live Google Ads account — a silent regression risk.

This change adds per-module unit tests for every exported function (happy path plus each documented failure branch), plus an orchestrator-level test for `handlePost` that uses the existing `_mock_response` hook to exercise every routing branch (pause exit, no-eligible exit, no-uploadable exit, batch success, per-row partial failure, batch-level failure with and without pause trip) without going to Google. A shared `test-helpers.ts` extracts the fake Supabase factory. No production code changes — bugs found by tests will land as follow-ups.

---

## Themes for the month

Three threads run through May, with the in-progress changes pushing each one further:

1. **Attribution honesty.** Independent stage detection, customer-level click ID tracking, the lookback-window fix, and the channel taxonomy all push toward knowing who really sent each lead. The in-progress `conversion-attribution-overhaul` extends this with a smarter resolver, re-attribution, and lifecycle-correct gates.
2. **Visibility into what Google actually receives.** Upload Report page, reconciliation reporting, cached analytics, the new Acceptance column — all answer "did Google take it?" The in-progress `gads-conversion-error-dispositions` turns the *errors* Google sends back into operator-actionable categories rather than 500-character message strings.
3. **Cleaning up before scaling up.** The page refactor, the bucket-column removal, the datetime-type fix, and the analytics/uploads split paid down structural debt. The in-progress upload-function module split and step-test coverage do the same on the backend side — getting the upload edge function into a state where each step can be tested and changed independently.
