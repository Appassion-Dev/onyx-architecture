## Context

Today the Google Ads conversion upload pipeline has a single status column (`gads_conversion_uploads.status`) with five values (`pending`, `uploaded`, `skipped`, `expired`, `failed`) and a free-text `error_message` truncated to 500 characters. Every per-row Google Ads API error is collapsed into one of those buckets, and the upstream `errorCode` enum that Google returns is discarded before it reaches the database. This conflates "transient — retry later" with "permanent payload bug" with "customer must change a setting in Google Ads", which is why the proposal exists.

The upload edge function ([supabase/functions/google-ads-conversion-upload/index.ts](supabase/functions/google-ads-conversion-upload/index.ts)) currently does its retry decision inline: if the partial-failure response contains any details, it marks the row `failed`; otherwise it leaves it `pending` for the next cron tick. There is no central rulebook. Every new error code shipped by Google ends up in one of those two paths by accident of how the response is shaped, not by intent.

The React dashboard reads `status` directly in [getPhaseConfig.tsx](horizon-dashboard/src/components/conversions/lib/getPhaseConfig.tsx) and renders a per-row chip. There is no inbox, no grouping, no remediation copy. Operators see "red X" with 14 truncated characters of error text per row.

Constraints that shape the design:

- **Single source of truth for enum names** across two runtimes (Deno edge functions + browser React). The Google Ads API SDK does not ship a generated TypeScript catalog of the partial-failure enum values. We need our own.
- **No backsliding** on the existing `status` column — third-party consumers (analytics dashboards, internal reports) read it, so we cannot ALTER it out from under them in a single release.
- **Operator-editable rulebook.** The disposition decisions must live in the database, not in code, so that an operator changing `EXPIRED_EVENT` from `drop` to `retry` does not require a redeploy.
- **Proto file fragility.** Google can rename or renumber enum values at API version bumps. The catalog must be regeneratable (and the diff reviewable in PR) so we are never left guessing what an unknown `errorCode` means.

Stakeholders: the Conversions Workbench operators (triage), the marketing team (cares about conversion delivery), and engineering on-call (gets paged today by stuck retry loops).

## Goals / Non-Goals

**Goals:**

- Capture the structured Google Ads `errorCode` on every row that errors, alongside the namespace, the original error detail object, and the batch the row was sent in.
- Replace inline retry decisions with a database-driven disposition lookup that an operator can edit through the admin UI.
- Give operators a triage surface (Needs Attention inbox grouped by `error_code`) that collapses thousands of identical errors into one actionable row with remediation text.
- Stop retrying terminal errors. Stop terminating retryable ones.
- Persist the Google-assigned `jobId` per batch so we can later reconcile against Google's aggregate diagnostics.
- Keep the existing `status` column writing in parallel for one release cycle so external consumers do not break on day one.
- Pause the cron when a batch-level error indicates broken upload configuration, and surface that pause to operators as a critical banner.

**Non-Goals:**

- A `recovery_action` axis (`wait` / `backoff` / `split-batch`) — disposition + the batch-level pause behavior cover every observed case. No `recovery_action` column.
- Batch splitting on `TOO_MANY_CONVERSIONS_IN_REQUEST`. That error in practice means the upload config is misconfigured, not that the batch is genuinely too big; we treat the whole batch as `fix-config` and pause.
- Self-assigned `job_id`. Google generates the ID; we store it.
- Final UI copy for the batch → aggregate diagnostics reconciliation panel. The data plumbing is in scope; the user-facing framing of the "shared bucket" caveat is deferred.
- Removing the legacy `status` column. That happens in a follow-up change after one release cycle of parallel writes.
- Backfilling structured `error_code` on historical rows. The original `errorCode` is unrecoverable from a 500-char-truncated `error_message`, so historical rows get `error_code = NULL` and a `lifecycle` derived from their legacy `status` only.

## Decisions

### D1. Vendored JSON catalog generated from proto, parsed by a hand-written tokenizer

**Decision:** Check in `supabase/generated/gads_error_catalog.json` derived from six v23 protobuf files (`conversion_upload_error.proto`, `user_data_error.proto`, `quota_error.proto`, `internal_error.proto`, `authentication_error.proto`, `field_error.proto`). A new script `scripts/sync-gads-errors.mjs` re-fetches the protos (URLs pinned in the script) and rewrites the JSON. The script parses with a small hand-written enum-block tokenizer, not a full protobuf library.

**Why:**
- A single JSON file is `import`-able from both the Deno edge function and the Vite/React dashboard with no runtime parsing, no proto dependency, and no `npm`/`jsr` divergence between the two runtimes.
- The enum block of a proto file is regular and trivial to tokenize (`ENUM_NAME = <int>; // <comment>`). A full protobuf library would add 100+ kB of dependency to lint a 200-line file.
- A reviewable JSON diff in PR is the safety net for Google renaming or renumbering enums. The seed defaults in `gads_error_dispositions` reference enum *names*, not numeric tags, so a renumber alone is harmless; a rename surfaces as a JSON diff that requires reviewer attention.

**Alternatives considered:**
- *Use `protobufjs` at runtime.* Rejected: adds a runtime dependency to both Deno and the browser bundle, for a one-time codegen step.
- *Generate TypeScript constants instead of JSON.* Rejected: two outputs (one for Deno, one for the FE) means twice the codegen complexity and a real risk of drift if one regenerates and the other doesn't. JSON is universal.
- *Don't vendor — fetch at runtime.* Rejected: Google's proto URLs aren't versioned in a way that protects us from upstream edits; we need a checked-in pinned version.

### D2. Six namespaces share one keyspace, keys formatted `<namespace>.<ENUM_NAME>`

**Decision:** `gads_error_dispositions.error_code` is a single text PK like `"conversionUploadError.EXPIRED_EVENT"` or `"userDataError.HASHED_FORMAT_REQUIRED"`. The catalog JSON is one flat object keyed by this format.

**Why:**
- Google's partial-failure response uses an `errorCode` discriminated-union shape where exactly one of six namespace fields is set. We always know the namespace at parse time, so prefixing is mechanical.
- A single PK is simpler than a composite `(namespace, code)` for joins, foreign keys, and the FE's grouped inbox.
- Collisions are real: `INTERNAL_ERROR` exists in multiple namespaces. Namespacing them prevents accidental disposition reuse across unrelated meanings.

**Alternatives considered:**
- *One disposition table per namespace.* Rejected: forces six joins or a UNION in the pickup query, and the FE admin page becomes six tabs.
- *Composite key `(namespace, code)`.* Rejected: every FK becomes two columns, every query becomes two-column joins, for no concrete benefit.

### D3. `lifecycle` is a new column; legacy `status` writes in parallel for one release

**Decision:** Add `lifecycle text` to `gads_conversion_uploads` with values `queued`, `sending`, `sent`, `retrying`, `needs-attention`, `failed`, `excluded`, `expired`. The edge function writes both `status` and `lifecycle` for one release cycle. The FE reads `lifecycle` (via the view). External consumers continue to read `status`. A follow-up change deprecates `status`.

**Why:**
- Widening the existing `status` CHECK constraint to include `queued`, `sending`, `retrying`, `needs-attention`, `excluded` would silently break any downstream consumer that does `WHERE status IN ('uploaded', 'failed', ...)` exhaustively. Some such consumers exist (the reconciliation view at minimum).
- Parallel writes give downstream consumers a deprecation window without a flag day.
- A new column also documents intent. Anyone reading the schema sees `lifecycle` as the new state and `status` as legacy-with-a-comment.

**Mapping for parallel writes** (until `status` is retired):

| `lifecycle`        | written `status` |
|--------------------|------------------|
| `queued`           | `pending`        |
| `sending`          | `pending`        |
| `sent`             | `uploaded`       |
| `retrying`         | `pending`        |
| `needs-attention`  | `failed`         |
| `failed`           | `failed`         |
| `excluded`         | `skipped`        |
| `expired`          | `expired`        |

**Alternatives considered:**
- *Widen the `status` CHECK in place.* Rejected: silently breaks downstream consumers and conflates the deprecation with the rollout.
- *Rename `status` to `lifecycle` with a backward-compat view.* Rejected: more invasive, and the rename itself breaks anything that writes to `status` (the edge function and a few SQL functions).

### D4. Database VIEW projects computed `disposition`; not a generated column

**Decision:** `vw_gads_conversion_uploads` is a view that joins `gads_conversion_uploads` to `gads_error_dispositions` on `error_code` and projects a computed `disposition` column. The FE reads the view. The state machine in the edge function joins to `gads_error_dispositions` directly (because it needs `max_attempts` and `retry_after_seconds`, not just the disposition string).

**Why:**
- An operator flipping `EXPIRED_EVENT` from `drop` to `retry` in the admin UI must be immediately reflected in every row, including the 30,000 historical ones with that code. A generated/materialized column would require a backfill on every disposition change.
- The view has zero write cost — disposition changes are pure metadata updates.
- The edge function does not read the view because it needs the unprojected columns (`max_attempts`, `retry_after_seconds`, `no_alert`) for its retry decision. A single join in the pickup query is cheap.

**Alternatives considered:**
- *Generated column on `gads_conversion_uploads`.* Rejected: stale on disposition change; requires backfill.
- *Materialize the join into a separate table.* Rejected: introduces a third place that has to stay in sync.
- *FE joins client-side via two queries.* Rejected: every FE query becomes a fan-out of two requests + a join in JavaScript; the inbox grouping becomes harder.

### D5. Disposition values are `retry` / `fix-config` / `fix-data` / `fix-triage` / `drop` / `deliberate`

**Decision:** The disposition column is a 6-value enum-style text field. Each row of `gads_error_dispositions` picks exactly one.

**Why each value:**
- `retry` — transient. Edge function sets `lifecycle = 'retrying'`. Pickup re-selects when timing allows. Honors `max_attempts` and `retry_after_seconds`.
- `fix-config` — customer-side Google Ads configuration is wrong (e.g., `CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS`, `CONVERSION_TRACKING_NOT_ENABLED`). Edge function sets `lifecycle = 'needs-attention'`. Bulk-reset enabled once the human flips the setting.
- `fix-data` — payload is bad and the row needs different inputs (e.g., `INVALID_HASHED_PHONE_NUMBER_FORMAT`, `INVALID_CONVERSION_DATE_TIME`). `lifecycle = 'needs-attention'`. Reset clears `error_code` and `attempt_count`.
- `fix-triage` — we don't know yet, an operator needs to look. `lifecycle = 'needs-attention'`. Default for any code not yet in the disposition table.
- `drop` — terminal, expected. `EXPIRED_EVENT` after 90 days, `DUPLICATE_CLICK_CONVERSION_IN_REQUEST` when we accidentally double-submit. `lifecycle = 'failed'`, often with `no_alert = true`.
- `deliberate` — terminal, we filtered the row out by policy before sending (not really an upstream error — used for our own pre-flight skips like "no GCLID and no enhanced-conversions identifiers"). `lifecycle = 'excluded'`.

**Why six and not three:**
- Three categories (`retryable` / `terminal` / `operator-action`) loses the actionable distinction between "I need to fix our code" (`fix-data`) and "the customer needs to flip a setting" (`fix-config`), which is the highest-value signal for the inbox grouping.
- Six is the smallest set where the inbox's "what should I do?" question gets a different concrete answer per disposition.

**Alternatives considered:**
- *A `recovery_action` axis orthogonal to disposition.* Rejected per proposal section G.
- *Boolean flags (`is_retryable`, `is_terminal`, `needs_human`).* Rejected: the cross-product has illegal combinations and the FE has to derive a single label anyway.

### D6. `no_alert` is a boolean column, not an alert severity level

**Decision:** `gads_error_dispositions.no_alert boolean` toggles whether the Workbench raises the needs-attention badge for rows with this code. Default is `false` for `fix-*`, `true` for the proto-documented "expected and ignorable" codes (e.g., `CLICK_NOT_FOUND` when using Enhanced Conversions for Leads — Google explicitly says "expected, ignore").

**Why a boolean and not a 0–5 severity:**
- The product question is binary: does this code raise the operator badge, yes or no?
- Severity adds a knob without a use case. If a third severity tier emerges (e.g., "summarize but don't badge"), it can be added later.

### D7. Batch-level errors classified `fix-config` pause the cron globally

**Decision:** When a Google Ads API call returns a *batch-level* error (HTTP non-2xx, or a request-level `errorCode` that prevents any rows from being accepted), the edge function:

1. Writes a row to `gads_conversion_upload_batches` with `request_error_code`, `request_error_message`, and zero `accepted_count`.
2. Looks up the disposition for that `error_code`. If the disposition is `fix-config`, sets a global pause flag.
3. Leaves the constituent rows in `lifecycle = 'queued'` (NOT `needs-attention`) — they did not individually fail, the whole pipeline did. Once the pause is cleared, they flow naturally into the next batch.

The pause is a single boolean stored in a new singleton table `gads_pipeline_state` (one row, PK `id = 1`) with columns `paused boolean`, `paused_reason text`, `paused_batch_id uuid`, `paused_at timestamptz`, `resumed_at timestamptz`, `resumed_by text`. The edge function's cron entrypoint checks `paused` before doing any work; if true, it logs and exits early. The Workbench surfaces a red banner with the pause reason, the batch link, and a "Resume Uploads" button that clears the flag (and records `resumed_at` / `resumed_by`).

`TOO_MANY_CONVERSIONS_IN_REQUEST` is one example. Other batch-level codes that should trigger pause: `CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS`, `CONVERSION_TRACKING_NOT_ENABLED`, `INVALID_CUSTOMER_ID`, authentication failures. These all map to `fix-config` in the seed, so the rule "batch-level + `fix-config` → pause" is sufficient — no separate hardcoded list.

**Why:**
- A batch-level config error means *every subsequent batch* will fail with the same error. Continuing to fire the cron just burns API quota and adds noise. Pause is the correct behavior.
- Pausing globally (rather than skipping the bad batch) is right because a config error affects the account, not a row subset. There is no "good subset" to keep trying.
- Keeping the rows in `queued` rather than marking them `needs-attention` preserves the model that `needs-attention` is row-level (row had a per-row error). The pause is pipeline-level, and the rows themselves are blameless.
- The disposition table remains the rulebook — we look up `disposition` for the batch-level `error_code` the same way we look up per-row codes. No second switch statement.

**Alternatives considered:**
- *Mark all rows in the failed batch `needs-attention` and let the operator bulk-reset after fixing the config.* Rejected: rows can be in multiple batches over their lifetime; marking them needs-attention for a config error they did nothing wrong in dilutes the inbox signal.
- *Auto-resume after N minutes.* Rejected: the underlying problem requires a human flipping a setting in Google Ads. Time alone won't fix it.
- *Per-conversion-type pause.* Rejected: batch-level config errors observed in practice (terms not accepted, conversion tracking off, invalid customer ID) affect the whole account, not a conversion type. Adding granularity solves no real problem.

### D11. Disposition admin page is gated only by login, not by role

**Decision:** Any logged-in dashboard user can edit `gads_error_dispositions` rows through the admin page. No new role or claim.

**Why:** The Workbench is already login-gated and operationally trusted. The downside of a bad disposition edit is bounded (rows pause for human attention or retry incorrectly) and self-correcting (visible in the inbox). Adding a role system for one page is more friction than the risk warrants.

### D12. Catalog JSON includes enum descriptions (proto comments)

**Decision:** `supabase/generated/gads_error_catalog.json` stores each enum as `{ "name": "...", "tag": 42, "namespace": "...", "description": "..." }`. The description is the leading comment from the proto file, normalized (newlines collapsed, leading `//` stripped). The seed migration uses `description` as the default `human_action` text; the admin page surfaces it as the tooltip for the code.

**Why:**
- The descriptions are the most accurate source of operator-facing remediation copy. Hand-writing them risks drift from Google's documented meaning.
- JSON size impact is ~3× but absolute size is still small (<100 kB for all six namespaces).
- The codegen step that strips comments is trivial; keeping them is the path of less effort.

### D8. Edits to disposition rows are tagged `source='override'` and survive proto resyncs

**Decision:** The seed migration inserts rows with `source = 'proto-v23-seed'`. The admin page sets `source = 'override'` on edited rows. The next `npm run sync:gads-errors` script:
1. Adds new rows (for newly added enum values) with `source = 'proto-vNN-seed'`.
2. Updates `notes` and `human_action` on rows where `source` starts with `proto-` — these are still the seed default and safe to refresh.
3. **Does not touch** rows where `source = 'override'`. Operator decisions survive proto bumps.

**Why:** An operator who changed `EXPIRED_EVENT` from `drop` to `retry` for a specific reason does not want a routine catalog resync silently reverting their decision. The `source` column makes this explicit and the resync script enforces it.

### D9. Default disposition for unknown `error_code` is `fix-triage`

**Decision:** When the edge function captures an `error_code` that has no row in `gads_error_dispositions`, it falls through to the disposition `fix-triage`. The row is marked `lifecycle = 'needs-attention'`. It does not retry.

**Why:** Unknown means "Google shipped a new enum value or our parser missed one". Treating it as retryable risks a tight loop. Treating it as `drop` discards rows we might have been able to recover. `fix-triage` parks it for an operator to look at — and the inbox grouping will surface it as a new error_code with N rows, which is itself the right signal to add a disposition row.

### D10. Batch table writes happen even on success

**Decision:** Every call to the Google Ads `uploadClickConversions` endpoint writes a row to `gads_conversion_upload_batches`, regardless of whether it was a partial failure or a complete success. The row carries the `job_id`, row counts, HTTP status, and (if applicable) the batch-level error code.

**Why:**
- The Workbench Batches panel needs every batch, not just failed ones.
- The eventual reconciliation against `gads_action_upload_health` needs to know "which batches contributed to today's (action × day) bucket".
- A batch row with 0 errors is small. The storage cost is negligible.

## FE Design — Workbench surfaces

The proposal's section F lists four FE changes (PUSH column chips, Needs Attention inbox, Batches panel, Dispositions admin page) plus the new pipeline-pause banner from D7. This section pins down the layout, data flow, and component placement before the spec phase.

### F1. PUSH column chip rendering (per `lifecycle`)

[getPhaseConfig.tsx](horizon-dashboard/src/components/conversions/lib/getPhaseConfig.tsx) currently switches on `status` and `upload_attempts`. It is rewritten to switch on `lifecycle` and (where relevant) `disposition` from the view.

| `lifecycle`        | Icon                       | Color                  | Sub-text                                     |
|--------------------|----------------------------|------------------------|----------------------------------------------|
| `queued`           | Clock                      | amber `#ffb547`        | "Queued"                                     |
| `sending`          | Spinner (animated)         | amber `#ffb547`        | "Sending…"                                   |
| `sent`             | CheckCircle2               | green `#01b574`        | localized `uploaded_at` date                 |
| `retrying`         | Clock with retry glyph     | amber `#ffb547`        | `Attempt ${attempt_count}/${max_attempts ?? '∞'}` |
| `needs-attention`  | AlertTriangle              | **red `#ee5d50`**       | `error_code` short form (last segment after `.`) |
| `failed`           | XCircle                    | red `#ee5d50`          | `error_code` short form, or "Failed" if `no_alert` |
| `excluded`         | MinusCircle                | gray `#a3aed0`         | "Excluded"                                   |
| `expired`          | Clock with strikethrough   | gray `#a3aed0`         | "Expired"                                    |
| (no row)           | em dash                    | dashed gray border     | empty                                        |

When the joined `no_alert = true` for the row's `error_code`, the chip renders subdued — gray border, gray text, no badge weight — regardless of `lifecycle`. Hover surfaces a tooltip with the full `error_code` and the `human_action` text from the disposition row.

The cell signature in the view consumer:

```ts
getPhaseConfig(
  lifecycle: Lifecycle,
  errorCode: string | null,
  disposition: Disposition | null,
  noAlert: boolean,
  attemptCount: number,
  maxAttempts: number | null,
  uploadedAt: string | null,
): PhaseCellConfig
```

The legacy four-argument signature (`status`, `uploadAttempts`, `uploadedAt`, `errorMessage`) is removed in the same PR that switches the FE to reading `vw_gads_conversion_uploads`.

### F2. Needs Attention inbox

New route: `/conversions/needs-attention` (component `NeedsAttentionInbox.tsx`), accessible from a new tab in the Workbench header alongside the existing pipeline view.

Layout (single-column):

```
┌────────────────────────────────────────────────────────────────────┐
│ Needs Attention                                    [⛶] [filters]   │
├────────────────────────────────────────────────────────────────────┤
│ ▾ conversionUploadError.CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS  │
│   5,012 rows · fix-config                                          │
│   "Toggle 'Customer match' acceptance in Google Ads Audience       │
│    Manager → Customer Lists → settings."                           │
│   [ Reset all 5,012 to queued ]    [ Open in Google Ads ↗ ]        │
│   ▸ Show rows                                                      │
├────────────────────────────────────────────────────────────────────┤
│ ▾ userDataError.HASHED_FORMAT_REQUIRED                             │
│   17 rows · fix-data                                               │
│   "Email/phone fields must be SHA-256 hashed. Re-check normalization."│
│   [ Reset all 17 to queued ]                                       │
│   ▸ Show rows                                                      │
├────────────────────────────────────────────────────────────────────┤
│ ▾ conversionUploadError.UNKNOWN_NEW_CODE (no disposition)          │
│   3 rows · fix-triage (default)                                    │
│   "No disposition configured — needs operator review."             │
│   [ Configure disposition ]                                        │
└────────────────────────────────────────────────────────────────────┘
```

Behavior:

- Groups are ordered by row-count descending by default; secondary sort: most-recent `last_attempt_at`.
- `no_alert = true` groups are collapsed in a "Muted (3 groups)" footer accordion at the bottom, not in the main list.
- Reset action is **group-level** (not per-row in the primary flow). It runs an UPDATE that sets `lifecycle = 'queued'`, `error_code = NULL`, `error_namespace = NULL`, `error_detail = NULL`, `attempt_count = 0` for all rows in the group. A confirm dialog shows the count: "Reset 5,012 rows to queued? They will be picked up by the next cron tick."
- Per-row reset is available via "Show rows" → drilldown table → row-level menu, but is one click deeper than group-level on purpose.
- "Configure disposition" jumps to the Dispositions admin page pre-filled with the unknown `error_code`.
- The data source is a single Supabase query that aggregates `vw_gads_conversion_uploads` by `error_code`:

  ```sql
  SELECT error_code, error_namespace, disposition, no_alert, human_action,
         COUNT(*) AS row_count, MAX(last_attempt_at) AS most_recent
  FROM vw_gads_conversion_uploads
  WHERE lifecycle = 'needs-attention'
  GROUP BY error_code, error_namespace, disposition, no_alert, human_action;
  ```

  Wrapped in a TanStack Query hook `useNeedsAttentionGroups()` with a 30s `staleTime`.

### F3. Batches panel

New route: `/conversions/batches` (component `BatchesPanel.tsx`), tab adjacent to Needs Attention in the Workbench header.

Layout (table):

| Sent at              | Job ID         | Rows | Accepted | Rejected | Status                           |
|----------------------|----------------|-----:|---------:|---------:|----------------------------------|
| 2026-05-18 14:02 EDT | 124…b9         |   53 |       51 |        2 | ● Partial (2 rejected)           |
| 2026-05-18 13:00 EDT | 124…a1         |   42 |        0 |        0 | ▲ Failed — CUSTOMER_NOT_ACCEPTED…|
| 2026-05-18 12:00 EDT | 124…0c         |   58 |       58 |        0 | ✓ Accepted                       |

- Clicking a row expands a drill-down listing the rows in that batch with their `lifecycle` + `error_code`, sourced from `vw_gads_conversion_uploads WHERE batch_id = ?`.
- A batch row with `request_error_code IS NOT NULL` (batch-level failure) gets a red triangle and a tooltip with the full error message. If this batch is the one that paused the pipeline (matches `gads_pipeline_state.paused_batch_id`), the row also gets a "Paused pipeline" tag.
- Pagination: page size 50, ordered by `sent_at` descending.
- No filters in v1 (date range, conversion type, etc. deferred).

### F4. Error Dispositions admin page

New route: `/conversions/dispositions` (component `DispositionsAdminPage.tsx`), surfaced from the Workbench header as a small "Configure" link, not a primary tab. Gated only by login per D11.

Layout (editable table):

| Error Code                                | Namespace            | Description (tooltip)             | Disposition          | Max attempts | Retry after | Mute  | Human action (editable)                  |
|-------------------------------------------|----------------------|-----------------------------------|----------------------|-------------:|------------:|:-----:|-------------------------------------------|
| conversionUploadError.EXPIRED_EVENT       | conversionUploadError | "Click is older than 90 days."   | drop ▾               |       —      |     —       |  ☑    | "Expected — click outside the 90d window."|
| conversionUploadError.CLICK_NOT_FOUND     | conversionUploadError | "Click ID not associated…"        | drop ▾               |       —      |     —       |  ☑    | "Expected for Enhanced Conversions for Leads." |
| conversionUploadError.CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS | conversionUploadError | "Customer match terms not accepted." | fix-config ▾ | — | — | ☐ | (editable) |
| userDataError.HASHED_FORMAT_REQUIRED      | userDataError         | "Email/phone must be hashed."     | fix-data ▾           |       —      |     —       |  ☐    | (editable)                                |

- Disposition is a dropdown of the 6 values. Mute is a checkbox. Max attempts and retry after are inline number editors (NULL = unlimited). Human action is a free text input.
- Edits save inline via a TanStack mutation. Save sets `source = 'override'`, `updated_at = now()`, `updated_by = auth.uid()`.
- A row with `source = 'override'` shows a small "✎ Overridden" badge next to the code, with a "Reset to seed default" button in a row-level menu that restores the original values and sets `source = 'proto-vNN-seed'`.
- Filter bar above the table: namespace dropdown, disposition dropdown, free-text search.
- An "Unknown codes" callout at the top of the page surfaces any `error_code` observed in `gads_conversion_uploads` that does NOT have a row in `gads_error_dispositions`. Clicking it opens a "Create disposition" form pre-filled with the unknown code. This closes the loop where a new Google enum can be triaged into the system without a code change.

### F5. Pipeline pause banner

A global, persistently-rendered banner inside the Workbench shell (above the tab nav, below the page header) — visible on every Conversions tab when `gads_pipeline_state.paused = true`.

```
┌────────────────────────────────────────────────────────────────────┐
│ ⛔ Uploads paused at 14:02 EDT — CUSTOMER_NOT_ACCEPTED_CUSTOMER_   │
│    DATA_TERMS on batch 124…a1. Fix in Google Ads then resume.      │
│    [ View batch ]  [ Open Google Ads ↗ ]  [ Resume uploads ]       │
└────────────────────────────────────────────────────────────────────┘
```

- Red background, white text. Sticky.
- Data source: a small TanStack hook `usePipelineState()` that polls `gads_pipeline_state` every 30s and on tab focus.
- "Resume uploads" is a confirm dialog → UPDATE that sets `paused = false`, `resumed_at = now()`, `resumed_by = auth.uid()`. The next cron tick proceeds.
- "View batch" links into the Batches panel scrolled to the offending batch.
- When `paused = false`, the banner is absent. No persistent "all good" state.

### F6. Reused primitives

- The chip rendering uses the existing palette from `tailwind.config.js` and the existing `lucide-react` icon set.
- Tables use the existing `DataTable` and `OverviewStatCard` primitives under `components/conversions/components/primitives/`.
- TanStack Query hooks follow the existing `useXxx()` convention with a 30s `staleTime` and `refetchOnWindowFocus: true`.
- Confirm dialogs reuse the existing `BulkUploadConfirmDialog` shape from `components/bulk-upload/`.

## Risks / Trade-offs

- **Parallel `status` + `lifecycle` writes can drift.** [Risk] The edge function computes `lifecycle` and derives `status` from it; if a future code path writes `status` without `lifecycle` (e.g., an SQL trigger or a manual UPDATE), the two will drift silently. → **Mitigation:** Add a SQL CHECK constraint that enforces the `lifecycle` → `status` mapping (D3 table) so any out-of-spec write fails. Drop the constraint when `status` is retired.

- **Disposition table is now in the request path.** [Risk] The pickup query joins to `gads_error_dispositions` on every cron tick. A bad index or a table-scan join could regress cron throughput. → **Mitigation:** The disposition table is bounded (~150 rows total across all six namespaces), so a hash join is effectively constant-time. Add `gads_error_dispositions(error_code)` as PK (already required for the join). Bench the new pickup query against the old one before merging.

- **Proto parser fragility.** [Risk] A hand-rolled tokenizer assumes Google's enum block formatting stays stable. If they reformat (multi-line comments inside the enum block, weird whitespace), the parser silently produces wrong output. → **Mitigation:** The sync script computes a content hash of each proto and refuses to write the JSON if any source file is empty or malformed; the parser asserts each enum value matches `^\\s*[A-Z_][A-Z0-9_]*\\s*=\\s*\\d+\\s*;.*$` and bails on the first non-match. A maintainer running `npm run sync:gads-errors` sees the error and updates the parser. Worst case: stale catalog, but never silently wrong.

- **`fix-triage` default could fill the inbox.** [Risk] If Google ships a new error code that affects many rows before we add a disposition for it, the inbox fills with thousands of `fix-triage` rows. → **Mitigation:** The inbox groups by `error_code`, so 10,000 rows show as one entry. The seed migration covers every currently-defined enum value (catalog has full coverage at seed time). New codes are rare (proto bumps are quarterly at most).

- **Resetting a `needs-attention` row clears `attempt_count`.** [Risk] An operator could repeatedly reset a row that genuinely needs a code fix, masking a real bug. → **Mitigation:** The Reset action is exposed at the *group* level in the inbox with a confirm dialog showing the row count, not as a per-row click-stress affordance. Per-row reset still exists but is one click deeper. If stress-resetting becomes a real problem in practice we'll add a log table; not building one preemptively.

- **View-based `disposition` is not indexable.** [Risk] FE queries like "all rows with disposition `fix-config`" can't use an index on `disposition` because it's computed. → **Mitigation:** The inbox query filters by `lifecycle = 'needs-attention'` (indexed) first, then groups by `error_code`. We never scan the view's `disposition` column over all rows. If a query pattern emerges that does, we'll revisit (likely as a stored function or a partial index on the join key).

- **Storing full `error_detail jsonb` per row.** [Risk] The full error object can be 1–2 kB per row, and at ~500 errored rows/day for ~90 days that's modest (~7 MB) but worth flagging if error volume spikes. → **Mitigation:** Acceptable for v1. If volume spikes we can move `error_detail` to a separate `gads_conversion_upload_errors(row_id, error_detail)` side table.

- **`source='override'` is a one-way valve.** [Risk] Once an operator overrides a row, the proto resync stops updating it. If the proto changes the *meaning* of an enum (e.g., narrows what `EXPIRED_EVENT` means), the override row keeps the old behavior. → **Mitigation:** The admin page surfaces a "Last reviewed: <date>" and a "Reset to seed default" affordance. Quarterly maintenance: scan override rows whose `updated_at` is older than the most recent seed sync and prompt review.

## Migration Plan

Land in this order, one PR per step so each is independently revertable:

1. **Catalog + sync script** — add `supabase/generated/gads_error_catalog.json` and `scripts/sync-gads-errors.mjs`. No DB or runtime changes. Verifies the codegen works in isolation.
2. **Schema migration** — new tables (`gads_error_dispositions`, `gads_conversion_upload_batches`), new columns on `gads_conversion_uploads` (`error_code`, `error_namespace`, `error_detail`, `lifecycle`, `last_attempt_at`, `batch_id`), the view, and the CHECK constraint linking `status` to `lifecycle` (D3). Seeds the disposition table from the catalog. **Edge function unchanged at this point** — it still writes `status` only; new columns stay NULL on new writes.
3. **Backfill** — populate `lifecycle` for existing rows from `status` per the proposal's mapping (`pending+attempts=0 → queued`, `pending+attempts>0 → retrying`, `uploaded → sent`, `skipped → excluded`, `failed → failed`, `expired → expired`). Run as a one-shot SQL script in the same migration window.
4. **Edge function rewrite** — restructure around the disposition lookup, write all new columns + the batch row, derive `lifecycle` from the join, keep writing `status` per the parallel-write mapping. Includes the small set of hardcoded `error_code` branches (e.g., batch-splitting on `TOO_MANY_CONVERSIONS_IN_REQUEST` — if we choose to ship it in v1; otherwise defer).
5. **Dashboard UI** — update `getPhaseConfig.tsx` to handle the new `lifecycle` values, add the Needs Attention inbox, Batches panel, and Error Dispositions admin page. The FE switches from reading `gads_conversion_uploads.status` to reading `vw_gads_conversion_uploads.lifecycle` in the same PR.
6. **One release cycle later, a separate change** — deprecate `status`. Add a comment, then remove the parallel writes, then drop the column.

**Rollback strategy:**
- Steps 1–2 are pure additive. Rollback is dropping the new tables/columns.
- Step 3 is data-only. Rollback is `UPDATE ... SET lifecycle = NULL`.
- Step 4 (edge function rewrite) is the highest-risk step. Rollback is redeploying the prior edge function build; the new columns it wrote stay populated but unused, and the FE (still on the old version) continues reading `status` until step 5. The CHECK constraint from D3 will not block a rollback because the legacy code path produces `(status, lifecycle=NULL)` rows, which the constraint must permit. → Add to the CHECK constraint: `lifecycle IS NULL OR (mapping holds)`.
- Step 5 is FE-only. Rollback is redeploying the prior dashboard build.
- Step 6 (deprecation) is its own change with its own rollback plan.

## Open Questions

- **Exact list of batch-level error codes that trigger pause vs. just record-and-skip.** The rule "batch-level + `fix-config` disposition → pause" covers the obvious set, but a few codes are ambiguously batch-level vs. per-row (e.g., `INTERNAL_ERROR` from `internalError` namespace can appear at either level). Resolve during spec write by enumerating which protobuf fields in the API response constitute "batch-level".
- **`gads_pipeline_state` schema specifics.** Singleton row enforcement: CHECK `id = 1` plus a unique index, or a one-row table with a trigger. Pick during spec write.
- **Tab order in the Workbench header.** With three tabs now (Pipeline, Needs Attention, Batches) plus a "Configure" link, what is the default landing tab and what is the order? Probably Pipeline → Needs Attention → Batches; "Configure" is right-aligned. Confirm during spec write.
