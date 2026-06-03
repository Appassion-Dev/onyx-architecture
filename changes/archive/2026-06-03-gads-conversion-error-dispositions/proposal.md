## Why

The current Google Ads conversion upload pipeline collapses every Google Ads API outcome into one of two terminal-ish states (`pending` with a truncated 500-character `error_message`, or `failed`), which causes three concrete operational failures:

1. **Information loss at the boundary.** The Google Ads partial-failure response contains a structured `errorCode` (an enum from one of ~6 namespaces — `conversionUploadError`, `userDataError`, `quotaError`, `internalError`, `authenticationError`, `fieldError`), a precise blame index (`location.fieldPathElements[0].index`), and a server-assigned `jobId`. Today the edge function reads only `err.message`, slices it to 500 chars, and discards the rest. We can't bucket, search, group, or alert on errors because the structured signal is gone before it reaches storage.
2. **Inverted retry behavior.** Per-row partial failures (some of which are genuinely transient — `TOO_RECENT_EVENT` says "retry after 6h", `TOO_MANY_CONVERSIONS_IN_REQUEST` says "split and retry") are marked terminal `failed`, while whole-batch HTTP failures (often config errors like `CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS` that will never recover without human action) stay `pending` and retry forever every cron tick. Cron load and Google quota are both consumed by retries that cannot succeed; rows that *would* succeed on a delayed retry never get one.
3. **No human-actionable surface.** The Workbench PUSH column shows a red X with a truncated message per row. There is no aggregation, no "5,012 rows are blocked on one Google Ads admin toggle" view, no separation of "we should fix our payload" from "the customer must change a setting" from "this row is permanently dead and that's fine". Operators triage row-by-row or not at all.

The Conversions Workbench developer brief (PUSH column / offline conversion delivery tracking) requires us to surface upload state with enough fidelity to drive operator action, and to reconcile our sent-rows against Google's settled aggregate diagnostics. Both depend on capturing the structured `errorCode` and on having a vocabulary richer than `pending` / `failed`.

## What Changes

### A. Vendored Google Ads error catalog (proto → JSON)

- Add a checked-in `supabase/generated/gads_error_catalog.json` derived from the v23 protobuf source files for `conversionUploadError`, `userDataError`, `quotaError`, `internalError`, `authenticationError`, and `fieldError`.
- Add a `npm run sync:gads-errors` script that re-fetches the proto files (URL pinned in the script), parses enum values (name + numeric tag + leading comment), and rewrites the JSON. PRs that bump the API version produce a reviewable diff.
- The Deno edge function and the React dashboard both `import` this JSON — single source of truth for enum names, no runtime proto dependency, no drift between Deno and the FE.
- Each catalog entry is keyed `"<namespace>.<ENUM_NAME>"` (e.g., `"conversionUploadError.EXPIRED_EVENT"`) so all six namespaces share one keyspace.

### B. Disposition configuration table + admin page

- New table `gads_error_dispositions` with PK `error_code` matching the catalog keyspace. Columns:
  - `disposition` — one of `retry`, `fix-config`, `fix-data`, `fix-triage`, `drop`, `deliberate`. (We chose against a separate `recovery_action` axis — disposition itself encodes the policy. `TOO_RECENT_*` becomes its own disposition like `retry-delayed` if needed, surfaced in the table.)
  - `max_attempts` — for retry dispositions; NULL = unlimited within the 90-day window.
  - `retry_after_seconds` — minimum wait between attempts (e.g., 21600 for `TOO_RECENT_*`).
  - `no_alert` — boolean. When true, rows with this code do not raise the Workbench's needs-attention badge and are collapsed in the inbox by default. Used for codes the proto explicitly tells us to ignore (e.g., `CLICK_NOT_FOUND` for EC-for-leads).
  - `human_action` — short remediation text shown in the Workbench inbox ("Toggle Enhanced Conversions for Leads in Google Ads conversion settings").
  - `notes`, `updated_at`, `updated_by`, `source` (`'proto-v23-seed'` vs `'override'`).
- Seeded from the catalog with sensible defaults (drop / fix-config / fix-data / retry per the analysis already done in this conversation).
- New admin page in the dashboard for editing disposition rows: change `disposition`, toggle `no_alert`, edit `human_action` text, override `max_attempts` / `retry_after_seconds`. Edits are stored on the row with `source='override'` so a future proto sync does not clobber operator decisions.

### C. Lifecycle and structured error columns on `gads_conversion_uploads`

- Add `error_code text` (the structured catalog key, NULL when the row succeeded or was never attempted).
- Add `error_namespace text` (denormalized for filtering, derived from `error_code`).
- Add `error_detail jsonb` for the full error object (location.fieldPathElements, message, trigger, etc.) — keep the rich payload for forensics.
- Add `lifecycle text` to replace the overloaded `status` for new behavior. Values: `queued`, `sending`, `sent`, `retrying`, `needs-attention`, `failed`, `excluded`, `expired`. The legacy `status` column stays for backward compatibility during migration; `lifecycle` is the new source of truth and is what the FE reads.
- Add a database **view** `vw_gads_conversion_uploads` that joins `gads_conversion_uploads` to `gads_error_dispositions` on `error_code` and projects a computed `disposition` column. The FE reads the view; the state machine reads the underlying tables (it needs `max_attempts` and `retry_after_seconds`, not just the disposition). Using a view rather than a stored generated column means a config change in `gads_error_dispositions` is immediately reflected in every existing row with no backfill — there is no "old rows show stale disposition" footgun.

### D. Disposition-driven state machine in the upload edge function

- The edge function captures the structured `errorCode` from each partial-failure detail (joining to the per-row `location.fieldPathElements[0].index`) and writes `error_code`, `error_namespace`, `error_detail`, `last_attempt_at`, increments `attempt_count`.
- After writing the error, it derives the next `lifecycle` by looking up `disposition` in `gads_error_dispositions`:
  - `retry` → `lifecycle = 'retrying'` (pickup loop will re-select once `now() >= last_attempt_at + retry_after_seconds` and `attempt_count < max_attempts`).
  - `fix-config` / `fix-data` / `fix-triage` → `lifecycle = 'needs-attention'`. **No auto-retry.** A human must intervene; the Workbench provides a "Reset to Queued" affordance that clears `error_code` and `attempt_count` and returns the row to `lifecycle = 'queued'`.
  - `drop` → `lifecycle = 'failed'` (terminal). If the disposition row has `no_alert = true`, the Workbench mutes it.
  - `deliberate` → `lifecycle = 'excluded'` (terminal, intentional).
- The pickup query joins to `gads_error_dispositions` so the state machine never hard-codes "EXPIRED_EVENT means drop"; the table is the rulebook.
- Whole-batch HTTP failures are written to the new batches table (see E) rather than left to retry forever; the batch's `request_error_code` drives whether to circuit-break (deferred — see "Out of scope" below).

### E. Batch tracking table

- New table `gads_conversion_upload_batches`:
  - `id uuid pk`
  - `sent_at timestamptz`
  - `job_id text` — server-assigned `jobId` from Google's response (we let Google generate it; `INVALID_JOB_ID(52)` confirms self-assignment is a footgun we don't need to take on yet)
  - `http_status int`
  - `request_error_code text` / `request_error_message text` — populated when the batch itself fails (vs per-row partial failures)
  - `row_count int`, `accepted_count int`, `rejected_count int`
- `gads_conversion_uploads.batch_id uuid` FK referencing the batch the row was last sent in.
- Enables a per-batch panel in the Workbench: "Batch a3f7… · 53 rows · 51 accepted · 2 rejected · Job ID …" with a drill-down to the rows.
- Sets the foundation for joining batches to the existing aggregate diagnostics in `gads_action_upload_health` for "of the rows we sent in this batch's (action × day) bucket, Google attributed N to ad clicks". (UI for this attribution-reconciliation panel is in this scope; the precise framing of the "shared bucket" caveat is deferred — see "Out of scope".)

### F. Workbench surface changes

- PUSH column chip rendering ([getPhaseConfig.tsx](horizon-dashboard/src/components/conversions/lib/getPhaseConfig.tsx)) gains cases for every `lifecycle` value: `needs-attention` (yellow triangle), `failed` (red X with tooltip showing `error_code` and `human_action`), `excluded` (gray dash), `expired` (gray clock), `retrying` (amber clock with attempt count). `no_alert` rows render as a subdued gray check.
- New "Needs Attention" inbox panel on the Workbench, grouped by `error_code`, showing count + `human_action` text + bulk actions ("Reset all to queued" after a config fix). Honors `no_alert` to mute groups by default.
- New "Batches" panel on the Workbench listing recent batches with their accept/reject counts and a drill-down to constituent rows.
- New "Error Dispositions" admin page for editing the lookup table.

### G. Pipeline pause on batch-level config errors

- When a Google Ads API call fails at the *batch* level (HTTP non-2xx or a request-level error code) with a code whose disposition is `fix-config`, the edge function writes the failure to `gads_conversion_upload_batches` and sets a global pause flag in a new singleton table `gads_pipeline_state` (`paused`, `paused_reason`, `paused_batch_id`, `paused_at`, `resumed_at`, `resumed_by`).
- The cron entrypoint checks `gads_pipeline_state.paused` first; if true, it exits immediately without making API calls.
- The Workbench shows a sticky red banner (visible across every Conversions tab) with the pause reason, a link to the offending batch, and a "Resume Uploads" button. Resume clears the flag and lets the next cron tick proceed.
- Rows in the failed batch stay in `lifecycle = 'queued'` — they were not individually at fault and will flow into the next successful batch once the operator fixes the config.
- This replaces what would otherwise be a "circuit-break" recovery action and removes the need for batch-splitting logic for `TOO_MANY_CONVERSIONS_IN_REQUEST` (which in practice signals a misconfigured upload, not a too-big batch).

### H. Out of scope (explicitly deferred)

- **Recovery action axis.** We are not modeling `recovery_action` as a separate column. Disposition encodes the policy, and batch-level pause behavior (section G) handles the circuit-break case.
- **Batch splitting.** Not implemented. `TOO_MANY_CONVERSIONS_IN_REQUEST` becomes a `fix-config` batch-level failure that pauses the pipeline.
- **Self-assigned `job_id`.** For now, Google generates the `jobId` and we store it on the batch row.
- **Attribution reconciliation UI copy.** The data plumbing joining batches to `gads_action_upload_health` is in scope; the exact UI framing of the "shared (action × day) bucket may include rows from other batches" caveat is deferred to a follow-up.

## Capabilities

### New Capabilities

- `gads-error-catalog-sync`: Vendored JSON catalog of Google Ads API error enums (six namespaces) plus the codegen script that derives it from the v23 protobuf source. Single import surface for both Deno edge functions and the React dashboard.
- `gads-error-dispositions`: The `gads_error_dispositions` lookup table, its seeded defaults, the database view that projects a computed `disposition` onto upload rows, and the dashboard admin page for editing disposition behavior (including `no_alert` and `human_action`).
- `gads-conversion-batches`: The `gads_conversion_upload_batches` table, the `batch_id` FK on `gads_conversion_uploads`, and the Workbench batches panel showing per-batch accept/reject counts and Google `job_id`.
- `gads-needs-attention-inbox`: The Workbench needs-attention triage view that groups rows by `error_code`, surfaces `human_action` remediation text, supports bulk "Reset to queued" after a fix, and respects `no_alert` muting.
- `gads-pipeline-pause`: The `gads_pipeline_state` singleton, the edge function's pre-flight pause check, and the Workbench sticky red banner with the Resume action. Triggered automatically when a batch-level error maps to a `fix-config` disposition.

### Modified Capabilities

- `conversion-upload`: The edge function now captures structured `errorCode`, writes `error_code` / `error_namespace` / `error_detail` / `batch_id` / `last_attempt_at`, derives `lifecycle` from `gads_error_dispositions`, honors `max_attempts` and `retry_after_seconds` for retry dispositions, and stops auto-retrying `fix-*` and `drop` dispositions. Whole-batch failures land on the batches table; batch-level `fix-config` failures additionally trip the pipeline-pause flag.
- `phase-cell-upload`: PUSH column chip renders all new `lifecycle` values (`needs-attention`, `failed`, `excluded`, `expired`, `retrying`, `sent`, `sending`, `queued`) and respects the `no_alert` flag for muted display.

## Impact

- **Database schema** — new tables `gads_error_dispositions`, `gads_conversion_upload_batches`, `gads_pipeline_state` (singleton); new columns on `gads_conversion_uploads` (`error_code`, `error_namespace`, `error_detail`, `lifecycle`, `last_attempt_at`, `batch_id`); new view `vw_gads_conversion_uploads`. Legacy `status` column retained for backward compatibility through the migration window. Status `CHECK` constraint stays as-is; new state values live on `lifecycle`.
- **Edge function** — [supabase/functions/google-ads-conversion-upload/index.ts](supabase/functions/google-ads-conversion-upload/index.ts) is restructured around the disposition lookup. New helpers for parsing `partialFailureError.details[]`, normalizing error keys to the catalog format, and writing batch rows. Pickup query joins the dispositions table.
- **Codegen / tooling** — new `scripts/sync-gads-errors.{ts,mjs}` (TBD which directory; likely under `horizon-dashboard/scripts/` to share `npm` with the dashboard). Adds one npm script. No new runtime dependencies — the proto is parsed with a small hand-written tokenizer for the enum block, not a full protobuf library.
- **Dashboard** — [getPhaseConfig.tsx](horizon-dashboard/src/components/conversions/lib/getPhaseConfig.tsx) updated for new lifecycle values. New routes and components under `src/components/conversions/` for the needs-attention inbox, batches panel, and dispositions admin page. New TanStack Query hooks for the disposition table and batches.
- **Aggregate diagnostics** — [supabase/functions/gads-upload-analytics/index.ts](supabase/functions/gads-upload-analytics/index.ts) is unchanged in this proposal; the batches → `gads_action_upload_health` join happens in the dashboard query layer.
- **Backward compatibility** — existing `status` values continue to be written by the edge function in parallel with `lifecycle` for one release cycle so any external consumer of `status` (e.g., reports, snippets) is not broken on day one. A follow-up change can deprecate `status`.
- **Migration data backfill** — existing rows get `lifecycle` populated from `status` (`pending` → `queued` if `attempt_count = 0` else `retrying`; `uploaded` → `sent`; `skipped` → `excluded`; `failed` → `failed`; `expired` → `expired`). `error_code` is left NULL for historical rows (we cannot recover the structured code from the truncated `error_message`).
- **Operational** — operators get a much smaller triage surface (groups not rows). Cron load drops because `fix-*` rows stop being re-uploaded each tick. Google quota consumption drops for the same reason.
