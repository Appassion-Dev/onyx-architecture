# May 18–24, 2026 — Changes Report

A walkthrough of every OpenSpec change touched between May 18 and May 24 inclusive, plus the changes that landed just past the window as the week's closeout (`classify-callrail-call-forwarding-as-direct` and `gads-upload-fix-and-refactor` on May 25, `callrail-pull-cron` on May 26). Each entry notes status, then breaks the work down into what landed in the **database** (schema, views, functions, migrations) and in the **frontend** (Conversions page, Workbench, hooks, components). The foundational `gads-conversion-error-dispositions` change is also complete (its final manual-verification step has since been signed off).

---

## High-level overview of the week

The week was dominated by one big idea: **make the Google Ads upload pipeline observable, testable, and operator-actionable end-to-end.** The previous two weeks had rebuilt detection and attribution; this week turned the same energy on the upload side and on the screens operators actually look at when something is wrong.

Three threads run through every change:

1. **From "did we send it?" to "did Google accept it, and if not, why?"** The Conversions rollup rail was rebuilt around payload mechanism (Method), local push outcome (Push), and Google-side acceptance (Acceptance) — directly mirroring the questions Smart Bidding cares about. The error-disposition system that landed mid-week converted Google's structured error codes from a truncated 500-character message into a typed, policy-driven state machine that knows when to retry, when to ask an operator, and when to give up. Raw request/response JSON is now persisted per batch and viewable from the Workbench, so when something fails, an operator can read the exact wire payload Google saw.

2. **Plug the silent-data-loss holes that the new tooling exposed.** Two small but consequential CallRail attribution fixes landed: the discovery pre-pass now joins CallRail leads to customers directly (recovering GCLIDs that were dropped whenever a CallRail row had a `customer_id` but no `estimate_id`), and `Call forwarding` source values are now classified as `Direct` instead of `Other`. A third fix backfilled `lifecycle = 'queued'` on rows that the discovery functions had been inserting with `lifecycle = NULL` — invisible to the new lifecycle-aware uploader.

3. **Get the upload edge function into a state where each step is independently testable.** The 399-line `handlePost` was broken into eleven purpose-named modules, four spec-compliance bugs were fixed in the process, and unit tests were added for every module plus an orchestrator-level test that exercises every routing branch of `handlePost` via the existing `_mock_response` hook — no live Google calls required.

Net result by the close of the week: the upload pipeline is no longer a single 400-line function returning truncated strings. It is a state machine driven by a configurable disposition table, with per-batch raw payloads visible in the UI, per-module unit tests, and a redesigned rollup rail that exposes the Smart Bidding signal-quality and acceptance metrics directly.

---

## May 19 — Redesigning the Conversions rollup rail

**`conversions-rollup-redesign`** — *complete*

The biggest UX-level change of the period. The Conversions page rollup rail (Month → Week → Source) was rebuilt around metrics that map directly to how Google Ads actually receives conversions, an `All Conv` mode was added that shows booked / qualified / converted side-by-side, and the per-row upload UI was collapsed in favor of a single top-of-page Upload button.

### Database

- [vw_conversion_candidates](supabase/migrations/) was extended to expose customer `email`, `mobile_number`, and service-address fields, plus a `customer_has_user_identifier` flag for the new **Method** classifier. This is what lets the Method column distinguish `with_gclid`, `user_data_only`, and `none` rows without a second round trip.
- No other schema work — the new **Acceptance** column reuses the existing [vw_gads_upload_reconciliation_daily](supabase/migrations/) view that already powers the Upload Report page.

### Frontend

- New `'all'` value added to `ConversionMode`; `STEP_TABS` re-ordered to `Pre-Discovery · All Conv · Booking · Qualified · Converted` with `All Conv` in the second slot.
- The rollup rail columns changed from `Rows | GCLID | Uploaded | Sync | Value` to `Stage | Method | Push | Acceptance | Value`. In `all` mode each cell shows three sub-values (booked / qualified / converted); in single-stage mode it shows one.
- [computeStats.ts](horizon-dashboard/src/components/conversions/lib/computeStats.ts) returns the new `{ stageCounts, methodCounts, pushCounts, value }` shape, replacing the flat `RollupStats`.
- New `RollupMetricCell` primitive supports the tri-cell per-stage layout used in `all` mode.
- A new hook fetches upload-reconciliation rows scoped to the visible hierarchy window (reusing `vw_gads_upload_reconciliation_daily` and the same TZ + week-keying logic from `lib/uploadReport.ts`).
- The per-row upload card and the per-week / per-month bulk-upload buttons were all removed. The page now exposes exactly one bulk-upload affordance: the existing Upload button in `ConversionsHeroHeader`, which uploads pending rows across the currently filtered hierarchy. Per-row retry stays reachable only from the expanded StageDetail panel.
- The estimate number (`#{estimate_number}`) on each row became a clickable external link to HousecallPro (`https://pro.housecallpro.com/app/estimates/{estimate_id}`). The expanded detail panel grew a customer-information block (name, email, phone, service address) pulled from the extended view.

**New capability folders:** `rollup-metric-columns`, `rollup-acceptance-metric`, `pipeline-row-hcp-link`.

---

## May 20 — Locking down the upload edge function with tests

**`gads-upload-step-tests`** — *complete*

After the upload edge function was split into eleven small modules, only two of them (`outcomes.ts` and `error-parsing.ts`) had unit tests. The other nine seams were covered only by manual end-to-end runs against a live Google Ads account — a silent regression risk. This change is test-coverage-only; no production behavior changes.

### Database

- None. The change is strictly additive on the test surface.

### Frontend

- None. This is edge-function infrastructure.

### Edge function tests (the actual work)

- New per-module test files alongside each module: `pause-state.test.ts`, `pickup.test.ts`, `payload-builder.test.ts`, `batches.test.ts`, `ads-api.test.ts`, `hashing.test.ts`, `runtime.test.ts`, `disposition.test.ts`. Standalone `error-parsing.test.ts` even though some of its cases are also covered indirectly by `outcomes.test.ts`.
- Shared `test-helpers.ts` extracts the `createFakeSupabase()` factory that previously lived in `outcomes.test.ts`, with a `CapturedCall` type and an `op` discriminator (`'update' | 'insert' | 'select' | 'select.maybeSingle' | 'select.single'`). It models every chain used in production (`update().eq`, `update().in`, `select().eq().maybeSingle`, `select().in().gte().lt`, `update().in().lt().select(c, {count})`, `insert().select().single`, bare `select()`) and throws `Error("unsupported chain: ...")` on anything else.
- New orchestrator-level `index.test.ts` exercises `handlePost` end-to-end using the fake Supabase client and the existing `_mock_response` test hook — covering pause exit, no-eligible exit, no-uploadable exit, classify-skip-only exit, batch success, per-row partial failure, batch-level failure with pause trip, and batch-level failure without pause trip. No live Google calls.
- [index.ts](supabase/functions/google-ads-conversion-upload/index.ts) gained a thin seam to support the orchestrator test: `handlePost(req: Request, sbOverride?: SupabaseClient)` with `const sb = sbOverride ?? getSupabase();`. The `Deno.serve` handler still calls `handlePost(req)` with one argument — production path unchanged.

---

## May 21 — Persisting raw Google Ads batch payloads, defaulting the lifecycle column, and surfacing the JSON in the UI

Three small parallel changes that close visibility and correctness gaps the error-disposition work opened up.

### `capture-raw-batch-payloads` — *complete*

When a batch fails or a customer disputes attribution, reconstructing the request from `gads_conversion_uploads` rows joined by `batch_id` is an approximation — it omits payload ordering, the exact wire shape, and any successful-result detail Google returned. Now the function persists both bodies verbatim.

**Database**

- New migration adds `request_body jsonb` and `response_body jsonb` to [gads_conversion_upload_batches](supabase/migrations/). Both nullable; no backfill — existing rows stay NULL.

**Frontend**

- None in this change. The viewer for these columns landed the same day under `view-batch-raw-payloads` (below).

**Edge function**

- [ads-api.ts](supabase/functions/google-ads-conversion-upload/ads-api.ts) now returns the request body alongside the response; [outcomes.ts](supabase/functions/google-ads-conversion-upload/outcomes.ts) and [batches.ts](supabase/functions/google-ads-conversion-upload/batches.ts) write both columns on every terminal path (success, partial failure, batch failure, network error, mock-response test path). Identifiers in `request_body` are already SHA-256 hashed — no additional PII risk.

### `gads-discovery-lifecycle-default` — *complete*

After the disposition refactor, the uploader picks up rows by filtering on `lifecycle IN ('queued', 'retrying')`. The two discovery functions (`discover_pending_conversions` and `discover_pending_conversions_for_estimate`) had never been updated when the `lifecycle` column was introduced — they were inserting with `status = 'pending'` only and leaving `lifecycle = NULL`. New rows were therefore invisible to the new uploader and silently never sent.

**Database**

- One-time backfill of any `lifecycle = NULL` rows (most-recent count was 18 stranded `pending` rows plus subsequent fresh inserts): `upload_attempts = 0 → 'queued'`, `upload_attempts > 0 → 'retrying'`.
- Column-level `DEFAULT 'queued'` added to `gads_conversion_uploads.lifecycle` as a safety net.
- Both discovery functions rewritten so the INSERT column list explicitly includes `lifecycle` with literal `'queued'` — the default still matters as a guard, but the assignment is now visible in the function body. Function bodies are otherwise byte-identical to the versions in `20260504000002_gads_conversion_datetime_type.sql`.
- Two migrations: `20260520000001_gads_lifecycle_default.sql` (the column default) and `20260520000002_gads_discover_set_lifecycle.sql` (the function rewrites).

**Frontend**

- None. Pure database fix.

### `view-batch-raw-payloads` — *complete*

The raw `request_body` / `response_body` JSON that `capture-raw-batch-payloads` started persisting was invisible in the app until this change. Investigation of a failed or partially-rejected batch required hand-querying Supabase. The Workbench Batches panel is where operators already triage uploads — that is where the raw payloads needed to surface.

**Database**

- None. Read-only UI on existing columns.

**Frontend**

- New **Request** and **Response** columns in [BatchesPanel.tsx](horizon-dashboard/src/components/conversions/batches/BatchesPanel.tsx). At the batch-row level, each cell opens a viewer with the full pretty-printed JSON of `request_body` / `response_body`.
- In the per-batch drill-down (constituent rows), the same two columns. For each estimate row, the cell shows just that estimate's slice: `request_body.conversions[]` matched by `gclid` (or order id), and `response_body.partialFailureError.errors[]` / `response_body.results[]` matched by index.
- New `PayloadViewer` component — a modal/popover with monospace, indented JSON, copy-to-clipboard, and a clear "no payload captured" empty state for legacy NULL rows.
- [useBatches](horizon-dashboard/src/components/conversions/batches/useBatches.ts) selects `request_body` / `response_body`; `useBatchConstituents` additionally selects `gclid` and (where available) the row's position in its batch for slicing.

**New capability folder:** `gads-batch-payload-viewer`.

---

## May 22 — Recovering CallRail GCLIDs lost to a structurally unnecessary join

**`prepass-callrail-direct-customer-id`** — *complete*

The `customer_gclids` discovery pre-pass (and its sibling `backfill_customer_gclids`) reached `callrail_leads → customer_id` indirectly through `JOIN estimates e ON e.id::varchar = cl.estimate_id`. That join silently dropped every CallRail lead whose `estimate_id` was NULL — which happens whenever the BEFORE-trigger correlator (`correlate_callrail_estimate`) matched a customer but could not pick a "most recent estimate" at write time. The lead's `customer_id` is already populated by the same trigger and is the value the pre-pass actually consumes; routing through `estimates` was structurally unnecessary and excluded usable GCLIDs.

### Database

- One migration replacing the two pre-pass orchestrators (`discover_pending_conversions`, `discover_pending_conversions_for_estimate`) and the `backfill_customer_gclids` function. The CallRail branch becomes `FROM callrail_leads cl WHERE cl.gclid IS NOT NULL AND cl.customer_id IS NOT NULL` (plus, in the per-estimate variant, `AND cl.customer_id = v_customer_id`).
- `customer_gclids.estimate_id` writes change semantically: the inserted value for the CallRail source is now `cl.estimate_id` directly (may be NULL) rather than the joined-through `e.id`. This column is informational — no resolver reads it — but the semantic shift is documented.
- No data migration required; running `SELECT backfill_customer_gclids()` once after deploy reclaims the historically dropped rows.
- `vw_conversion_candidates` is untouched. It still uses `cl.estimate_id` for per-estimate aggregates; improving that linkage is a separate concern.

### Frontend

- None. Consumers read from `customer_gclids` and don't care which join produced a row.

---

## May 25 — Week closeout: classifying call-forwarding leads as Direct, and finishing the upload-function refactor

These two changes landed on May 25, one day past the nominal window; they are included here as the closeout of the week's upload-and-attribution work.

### `classify-callrail-call-forwarding-as-direct` — *complete*

`vw_conversion_candidates.channel` was resolving to `'Other'` for three estimates (one customer — Curt Chandler, estimates #5953, #7543, and a sibling) whose CallRail lead had `source = 'Call forwarding'` and `medium = 'direct'` — the canonical "customer dialed a CallRail tracking number directly" signal. The existing CallRail branch of the channel CASE scanned `callrail_sources` for `LIKE '%direct%'`, which matched literal `source = 'Direct'` but missed the `'Call forwarding'` tracker-mode value entirely. The wider population of `'Call forwarding'` rows (40 total) doesn't translate into more affected estimates — 39 of 40 are call-tracking noise (CNAM strings, spam, unidentified callers) with no customer record at any point in time.

**Database**

- One migration replacing `vw_conversion_candidates` (CASCADE drop also recreates `vw_gads_upload_reconciliation_daily`, mirroring `20260522000001_vw_conversion_candidates_callrail_by_customer.sql`). Schema unchanged; only the channel CASE body grows by one branch: `LOWER(src.value) LIKE '%call forwarding%'` → `'Direct'`. The new branch is positioned after every higher-precedence CallRail branch so a hypothetical `'Google Local Services / direct'` row still resolves to GLS via the earlier `%local services%` branch.
- No data migration. The view recomputes on read; 3 production estimates reclassify from `'Other'` → `'Direct'` the moment the migration deploys.

**Frontend**

- None. The Conversions page weekly rollup picks up the new Direct rows automatically; the Direct group label and ordering are unchanged.

### `gads-upload-fix-and-refactor` — *complete*

Follow-up cleanup after the error-disposition change shipped. Two parts: four small spec-compliance fixes (real but quiet bugs that verification against the `conversion-upload` spec surfaced) and the full module split of the 399-line `handlePost`.

**Database**

- No schema change. The fixes only change the *values* the edge function writes; existing CHECK constraints and the `vw_gads_conversion_uploads` view are unaffected.

**Frontend**

- No direct changes. Downstream impact: the FE reads `vw_gads_conversion_uploads`. After the fixes, queued/excluded rows that previously projected a contradictory `disposition` now project `NULL`. The Needs Attention inbox already filters by `lifecycle = 'needs-attention'` so it is not affected; the Batches drill-down may show rows with `error_code = NULL` where it previously showed stale codes — which is the correct state.

**Edge function (the actual work)**

- *Spec compliance fixes:* expired rows now write the reason to `error_detail` instead of the legacy `error_message`; stale `error_code` is cleared when rows transition to `excluded` or back to `queued` (otherwise the disposition view projects a contradictory state); a defensive bounds check in `parsePartialFailure` drops out-of-range per-row error indices with a `console.warn` so an unexpected Google response can no longer silently mark rows as sent; `require-await` linter fixes on `hashEmail` and `hashPhone` (both `return sha256hex(...)` with no internal `await`).
- *Full module split:* the 399-line `handlePost` in [index.ts](supabase/functions/google-ads-conversion-upload/index.ts) shrinks to ~70 lines of orchestration + `Deno.serve` entry. Eleven sibling modules sit alongside it:
  - **Pure helpers (kept):** `error-parsing.ts`, `disposition.ts`, `hashing.ts`.
  - **New modules:** `types.ts` (domain interfaces, no logic), `runtime.ts` (`corsHeaders`, `json`, `getSupabase` — the only module that touches `Deno.env`), `pause-state.ts` (`checkPipelinePause` + `tripPipelinePause` — the single funnel for `gads_pipeline_state`), `pickup.ts` (`loadDispositions`, `selectAndExpire` with the 90-day expire UPDATE, `loadConfig`), `payload-builder.ts` (`classifyRows`, `buildPayloads`), `ads-api.ts` (`callGoogleAds` — the only `fetch()` to Google), `batches.ts` (`createBatch`, `markSending`), `outcomes.ts` (`markNoIdExcluded`, `handleBatchFailure`, `applyPerRowOutcomes` — every terminal-row UPDATE and the batch-row finalize).
- `deno lint` on the function drops from 5 findings to 3 (remaining 3 are project-wide `no-import-prefix` issues handled separately).

---

## May 26 — Letting CallRail ingestion run unattended

**`callrail-pull-cron`** — *complete*

The `callrail-pull` edge function only ran when a logged-in user triggered it from the UI, and its default date range was just the current day. So whenever no one opened the app, `callrail_leads` drifted and accumulated gaps. This change makes the function callable by an unattended scheduler with the platform's service-role credential and changes the no-argument behavior to pull the last 24 hours, so a scheduled invocation needs no body computation.

### Database

- None. The cron job itself is configured outside this change (Supabase Studio / manual `cron.schedule`), so it deliberately ships no migration.

### Frontend

- None. UI calls that omit dates simply pick up the new last-24-hours default automatically.

### Edge function (the actual work)

- [callrail-pull/index.ts](supabase/functions/callrail-pull/index.ts) now accepts the project's `SUPABASE_SERVICE_ROLE_KEY` as a bearer in place of a user JWT: when the bearer is an *exact* match for the service-role key, the `auth.getUser` check is skipped; otherwise the existing user-JWT path is unchanged.
- Default date range when the request body omits `start_date` / `end_date` changes from "today only" to the last 24 hours, expressed as `start_date = yesterday (UTC)`, `end_date = today (UTC)`.
- `handlePost` logs the caller class (`service` vs `user`) at the start for observability.
- Risk noted in the proposal: the service-role bypass widens what the function trusts; mitigated by requiring an exact match against `SUPABASE_SERVICE_ROLE_KEY` rather than accepting any valid JWT.

**New capability folder:** `callrail-ingest`.

---

## Foundational change completed this week

The change below is the foundation the rest of the week's upload work depends on; it is now complete.

### `gads-conversion-error-dispositions` — *complete*

The foundational change the rest of the week's upload work depends on. The previous pipeline collapsed every Google response into "pending" or "failed" with errors truncated to 500 characters of free-form text. The result: structured error codes lost before they reached storage, transient errors marked permanent (and never retried), permanent config errors stayed "pending" and retried forever, and operators had no aggregate view of what was actually blocking uploads.

#### Database

- **New table `gads_error_dispositions`** (PK `error_code` matching the catalog keyspace, e.g. `"conversionUploadError.EXPIRED_EVENT"`) with columns `disposition` (`retry` / `fix-config` / `fix-data` / `fix-triage` / `drop` / `deliberate`), `max_attempts`, `retry_after_seconds`, `no_alert`, `human_action` (remediation text shown in the inbox), `notes`, `updated_at`, `updated_by`, `source` (`'proto-v23-seed'` vs `'override'`). CHECK on `disposition`; defaults for `retry_after_seconds`, `no_alert`, `source`, `updated_at`.
- **Seeded with 97 entries** from a generated SQL VALUES list (see codegen below). Sensible defaults per analysis: `EXPIRED_EVENT` → drop / no_alert=true, `CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS` → fix-config, `TOO_RECENT_EVENT` → retry / 21600s, `CLICK_NOT_FOUND` → drop / no_alert=true, `TOO_MANY_CONVERSIONS_IN_REQUEST` → fix-config.
- **New table `gads_conversion_upload_batches`** with `id uuid DEFAULT gen_random_uuid()`, `sent_at timestamptz`, `job_id text` (Google-assigned), `http_status int`, `request_error_code text`, `request_error_message text`, `row_count int`, `accepted_count int`, `rejected_count int`. Index on `sent_at DESC` for the panel pagination.
- **New singleton table `gads_pipeline_state`** with `id integer PRIMARY KEY CHECK (id = 1)`, `paused`, `paused_reason`, `paused_batch_id`, `paused_error_code`, `paused_at`, `resumed_at`, `resumed_by`. Seed row `(1, false, ...)`.
- **New columns on `gads_conversion_uploads`:** `error_code text`, `error_namespace text`, `error_detail jsonb`, `lifecycle text` (values: `queued`, `sending`, `sent`, `retrying`, `needs-attention`, `failed`, `excluded`, `expired`), `last_attempt_at timestamptz`, `batch_id uuid REFERENCES gads_conversion_upload_batches(id) ON DELETE SET NULL`. Indexes on `lifecycle` (pickup) and `error_code` (inbox grouping). CHECK constraint enforces the `(lifecycle, status)` mapping while permitting `lifecycle IS NULL` for legacy rows.
- **Lifecycle backfill** maps existing `status` values: `pending` + attempts=0 → `queued`, `pending` + attempts>0 → `retrying`, `uploaded` → `sent`, `skipped` → `excluded`, `failed` → `failed`, `expired` → `expired`. Embedded `DO $$ RAISE EXCEPTION` sanity check confirms no NULL `lifecycle` after backfill.
- **New view `vw_gads_conversion_uploads`** left-joins `gads_conversion_uploads` to `gads_error_dispositions` on `error_code` and projects the computed `disposition`, `no_alert`, and `human_action`. The FE reads the view; the state machine reads the underlying tables (it needs `max_attempts` and `retry_after_seconds`). Using a view rather than a stored generated column means a config change in `gads_error_dispositions` is immediately reflected in every existing row with no backfill.
- **`vw_conversion_candidates` updated** to expose `lifecycle`, `error_code`, `disposition`, `no_alert`, `human_action`, `attempt_count`, `max_attempts` per stage by switching its per-stage joins from `gads_conversion_uploads` to `vw_gads_conversion_uploads` (migration `20260518000005_pipeline_view_with_lifecycle.sql`).
- Migrations: `20260518000001_gads_error_dispositions_schema.sql` (tables & columns), `20260518000002_gads_dispositions_view.sql` (view + grants), `20260518000003_gads_dispositions_seed.sql` (97-row seed), `20260518000004_gads_lifecycle_backfill.sql` (status → lifecycle backfill), `20260518000005_pipeline_view_with_lifecycle.sql` (candidates view update).

#### Frontend

- **PUSH column chip rendering.** [getPhaseConfig.tsx](horizon-dashboard/src/components/conversions/lib/getPhaseConfig.tsx) signature updated to accept `(lifecycle, errorCode, disposition, noAlert, attemptCount, maxAttempts, uploadedAt, humanAction)`. Mapping per the phase-cell-upload spec: `needs-attention` (yellow triangle), `failed` (red X with tooltip showing `error_code` and `human_action`), `excluded` (gray dash), `expired` (gray clock), `retrying` (amber clock with attempt count), `sent` (green check), `sending` / `queued` per spec. `no_alert = true` overrides with a muted gray render. Consumers (`PhaseCell`, `PipelineStrip`, `PipelineRowItem`) all updated to the new prop shape. Hover-to-upload activation now considers `lifecycle ∈ ('queued', 'retrying', 'needs-attention')` as actionable (via `ACTIONABLE_LIFECYCLES` in `PhaseCell.tsx`).
- **Needs Attention inbox.** New route `/conversions/needs-attention`, new component `NeedsAttentionInbox.tsx`, new TanStack hook `useNeedsAttentionGroups()` querying `vw_gads_conversion_uploads` aggregated by `error_code` / `error_namespace` / `disposition` / `no_alert` / `human_action` (30s `staleTime`, client-side aggregation — inbox volumes don't warrant a server-side aggregate). Group cards render in row-count-descending order with disposition tag, `human_action` text, and row count. "Show rows" drill-down lists constituent rows. Group-level "Reset all N to queued" with confirm dialog clears `error_code` / `error_namespace` / `error_detail` / `attempt_count` and sets `lifecycle = 'queued'`. A "Muted (N groups)" accordion footer hides `no_alert = true` groups. Unknown-code groups (NULL disposition) get a "Configure disposition" action that deep-links to `/conversions/dispositions?prefill=<error_code>`. New tab added to `WorkbenchTabs.tsx`.
- **Batches panel.** New route `/conversions/batches`, new component `BatchesPanel.tsx`, new hook `useBatches({ page, pageSize: 50 })` querying `gads_conversion_upload_batches` ordered by `sent_at DESC`. Columns: sent_at (NY tz), abbreviated `job_id`, `row_count`, `accepted_count`, `rejected_count`, status indicator (green / amber / red with tooltip for `request_error_message` on failed batches). Batch drill-down queries `vw_gads_conversion_uploads WHERE batch_id = <id>`. Paused-pipeline tag rendered on the batch whose id equals `gads_pipeline_state.paused_batch_id`.
- **Error Dispositions admin page.** Edits to `disposition`, `no_alert`, `human_action`, `max_attempts`, `retry_after_seconds`. Edits store `source = 'override'` so a future proto sync does not clobber operator decisions.

#### Edge function and tooling

- **Vendored catalog.** New `supabase/generated/gads_error_catalog.json` (97 entries) derived from the v23 protobuf source for `conversionUploadError`, `userDataError`, `quotaError`, `internalError`, `authenticationError`, `fieldError`. Generated by `horizon-dashboard/scripts/sync-gads-errors.mjs` with pinned URLs, an enum-block tokenizer, description normalization, and sorted-key JSON output for deterministic re-runs. npm script `sync:gads-errors` invokes it. Seed-generator `horizon-dashboard/scripts/gen-dispositions-seed.mjs` reads the catalog and emits the SQL VALUES list for the seed migration.
- **State machine in the edge function.** Pause pre-flight check returns HTTP 423 with reason payload when `gads_pipeline_state.paused = true`. Pickup query reads `gads_conversion_uploads` joined to `gads_error_dispositions`, selecting `lifecycle = 'queued'` OR (`lifecycle = 'retrying'` AND retry timing OK). Retry timing and attempt budget are enforced in JS over the candidate set (PostgREST cannot express the join filter directly). `parsePartialFailure` walks `partialFailureError.details[]`, extracts each `errorCode` discriminated-union, normalizes to `"<namespace>.<ENUM_NAME>"`, and captures `location.fieldPathElements[0].index`. Per-row dispositions are looked up from an in-memory `Map` built from a single `SELECT * FROM gads_error_dispositions` at function start. Unknown codes default to `lifecycle = 'needs-attention'` (the `fix-triage` behavior). Batch-level `fix-config` failures additionally trip the pipeline-pause flag.
- **Legacy `status` written in parallel** with `lifecycle` for one release cycle so external consumers aren't broken on day one.

---

## Themes for the week

1. **Operator action over operator inference.** The error-disposition table, the Needs Attention inbox, the batches panel, and the raw-payload viewer all share the same shape: instead of showing a row with a truncated error message and leaving the operator to figure out what to do, the system already knows the policy (`retry` / `fix-config` / `fix-data` / `drop` / `deliberate`) and surfaces the remediation text along with the row. The disposition table is the rulebook; the UI is the read of the rulebook.

2. **Acceptance, not just upload.** The Conversions rollup rail rebuild and the raw-payload viewer both push the operator's view past "did we send it?" to "did Google accept it, and if not, what exactly did they say?" Both are necessary because most Smart Bidding attribution loss happens in that gap.

3. **Testable seams.** The upload edge function went from a single 400-line function to eleven independently importable modules with per-module unit tests and an orchestrator-level test that exercises every branch via the existing mock hook. Combined with the spec-compliance fixes that landed during the split, the function is now in a state where future extensions (batch splitting, self-assigned job IDs, attribution reconciliation joins) can be added one module at a time without re-reading the orchestration.

4. **Attribution losses found by the new tooling.** Two CallRail fixes (`prepass-callrail-direct-customer-id` recovering rows lost to a structurally unnecessary join, `classify-callrail-call-forwarding-as-direct` reclassifying 3 estimates from `Other` to `Direct`) and the `gads-discovery-lifecycle-default` backfill (18+ rows the new uploader was silently skipping) all share an origin story: as the pipeline got more legible, the silent gaps stopped being silent.
