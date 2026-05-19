# PUSH column — status, identifier, and error model

Reconciles the Workbench design model with the v23 API research (`research-qa.md`, 2026-05-15). This is the source of truth for the PUSH column.

## Data model — four fields per row

The PUSH column renders from four independent fields. Don't merge them into a single enum.

1. **`push_status`** — lifecycle state, one per row, mutually exclusive.
2. **`push_identifier_flags`** — what was sent with the upload (booleans, set once at push time).
3. **`push_error_code`** — namespaced code from the API, nullable.
4. **`push_disposition`** — derived from the code, drives behavior.

## 1. `push_status` — lifecycle states

| Status | Meaning | Color |
|---|---|---|
| `Queued` | in the push queue, not yet sent | gray |
| `Sent` | accepted by the API — **terminal at row level**; not confirmed counted | blue |
| `Retrying` | transient failure, will resend automatically | amber |
| `Failed` | permanent failure, needs a human | red |
| `Skipped` | not eligible to push (no identifier) | gray |
| `Excluded` | deliberately held back | gray |

`Sent` is the end of the line for a single conversion. Do **not** add `Counted` or `Dropped` as row statuses. Per item 3 of the research: Google returns no per-conversion attribution signal, only aggregate daily summaries at (customer × conversion_action × upload_date) grain. Attribution lives only on group rows and tiles, sourced from `offline_conversion_upload_conversion_action_summary` via `gads_action_upload_health`. Reconciliation delay is ~3h typical, up to 24h, with a ~14-day backfill window.

## 2. `push_identifier_flags` — what was sent

Three booleans stored at upload time on `gads_conversion_uploads`. Set once, never change.

| Flag | Meaning |
|---|---|
| `gclid_present` | a Google click ID was attached — deterministic match |
| `email_present` | hashed email included (SHA-256, lowercase-trimmed) |
| `phone_present` | hashed phone included (SHA-256, lowercase-trimmed) |

Display label is **derived** from the flags, never stored as a status:

- `gclid_present = true` → render as **linked** (any combination with GCLID)
- `gclid_present = false` AND (`email_present` OR `phone_present`) → render as **unlinked**
- all false → row is `Skipped` with `NO_ID`

Use these flags to compute the linked-share KPI locally without depending on Google. Reconcile against the diagnostics' click-based vs enhanced match split for ground truth.

## 3. `push_error_code` — namespaced enum

API v23. Codes are stored as `"<namespace>.<ENUM_NAME>"` in a single catalog, keyed across six namespaces:

- `conversionUploadError`
- `userDataError`
- `quotaError`
- `internalError`
- `authenticationError`
- `fieldError`

The codegen script pins v23 and re-fetches protos on bump. v22 sunsets mid-2026.

## 4. `push_disposition` — derived from the code

Five dispositions, not four. `fix-config` and `fix-data` need different operator UI (toggle in Google Ads vs fix the payload) and are split accordingly.

### `retry` → `Retrying`
Transient or time-based. Auto-resends with backoff.

| Code | Notes |
|---|---|
| `conversionUploadError.TOO_RECENT_EVENT` | `retry_after_seconds=21600` (6h) |
| `quotaError.RESOURCE_EXHAUSTED` | longer `retry_after_seconds`, batch-level backoff |
| `quotaError.RESOURCE_TEMPORARILY_EXHAUSTED` | same |
| `internalError.*` | transient |
| `authenticationError.OAUTH_TOKEN_*` | retry if transient; flips to `fix-config` if credentials revoked |

### `fix-config` → `Failed`
Account or conversion-action setup. Needs a human to flip a toggle in Google Ads.

| Code | Notes |
|---|---|
| `conversionUploadError.UNAUTHORIZED_CUSTOMER` | account access |
| `conversionUploadError.INVALID_CONVERSION_ACTION` | wrong/disabled action |
| `conversionUploadError.CONVERSION_NOT_FOUND` | action missing |
| `conversionUploadError.CONVERSION_TRACKING_NOT_ENABLED_AT_IMPRESSION_TIME` | tracking gap |
| `conversionUploadError.CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS` | **account-wide block** — see operator notes below |
| `conversionUploadError.CONVERSION_ACTION_NOT_ELIGIBLE_FOR_ENHANCED_CONVERSIONS_FOR_LEADS` | being phased out in favor of unified code (April 2026) |
| `authenticationError.OAUTH_TOKEN_*` (revoked) | re-auth required |

### `fix-data` → `Failed`
Payload is wrong. Fix the row, requeue.

| Code | Notes |
|---|---|
| `conversionUploadError.INVALID_CONVERSION_DATE_TIME` | timezone bug |
| `conversionUploadError.EVENT_NOT_ATTRIBUTED_TO_CONVERSION` | mapping issue |
| `userDataError.INVALID_HASHED_EMAIL` | bad hash/normalization |
| `userDataError.INVALID_HASHED_PHONE_NUMBER` | bad hash/normalization |
| `userDataError.INVALID_USER_IDENTIFIER` | malformed identifier |
| `fieldError.REQUIRED` | missing required field |
| `fieldError.INVALID_VALUE` | bad payload value |

### `drop` → `Skipped` (pre-push) or terminal `Failed`
Unrecoverable. Some carry `no_alert=true` and should **not** count toward the Push errors tile.

| Code | Disposition | `no_alert` | Notes |
|---|---|---|---|
| `conversionUploadError.CLICK_NOT_FOUND` | drop | **true** | proto explicitly says ignore for EC-for-leads |
| `conversionUploadError.EXPIRED_EVENT` | drop | false | GCLID >90 days |
| `conversionUploadError.DUPLICATE_ORDER_ID` | drop | false | Google is source of truth; UNIQUE constraint on `(estimate_id, conversion_type)` prevents local dupes but not re-uploads |
| `conversionUploadError.ORDER_ID_ALREADY_IN_USE` | drop | false | same |
| `userDataError.INSUFFICIENT_MATCHING_HASHED_PII` | drop | **true** | acceptable when GCLID is present |
| `NO_ID` (local pre-check) | `Skipped` | n/a | never pushed |

### `deliberate` → `Excluded`
Not a Google error — our own upstream rule. Always carries a reason tag.

| Reason | Notes |
|---|---|
| `RETURN_CUSTOMER` | ~12% upstream filter, excluded before queue |

## Request-level vs partial-failure errors

These are surfaced differently:

| Type | When | Surface |
|---|---|---|
| **Request-level** (non-2xx, whole batch dies) | revoked refresh token, MCC link removed, `INVALID_CUSTOMER_ID`, `CUSTOMER_NOT_ENABLED`, 5xx, `INTERNAL_ERROR`, request-level `RESOURCE_EXHAUSTED` | Batches panel — red batch row with `request_error_code`, drill-down to affected rows. Rows go to needs-attention, not retried per-row. Quota and 5xx retry at batch level with backoff (rows stay queued). |
| **Partial-failure** (HTTP 200, `partialFailureError` populated) | everything in §4 above | Needs-Attention inbox, grouped by `error_code`. Per-row blame via `details[].location.fieldPathElements[0].index` — stable in v23. |

Operators need both views: a request-level alert is an account fire drill; partial-failure rows are individual issues.

## Render rules

The PUSH cell shows a status pill + a tag.

- The **tag slot** shows `push_error_code` when present, otherwise the derived identifier label (`linked` / `unlinked` / `NO_ID`).
- When `push_status = Sent`, the tag is the identifier label only.
- **Every** `Skipped` and `Excluded` row must carry a reason tag. No bare pills.
- Drops with `no_alert=true` render the same as other drops in the row, but the Push errors tile filters them out.

## Tile-counting rules

| Tile | Counts |
|---|---|
| Push errors | `push_disposition IN ('fix-config', 'fix-data')` only. Excludes `retry`, all drops (including `no_alert=false`), and deliberate. |
| Acceptance | Aggregate, from `gads_action_upload_health`. Headline last fully settled week (3–24h diagnostics lag, never the current unsettled day). |
| Unlinked share | `gclid_present = false` ÷ all `Sent` rows. |

## `job_id`

Returned at the top level of `UploadClickConversionsResponse`. Stored indexed on `gads_conversion_upload_batches.job_id`. Rows reference the batch via `batch_id` FK. **Let Google generate it** — self-assigning risks `INVALID_JOB_ID(52)` and adds collision concerns with no upside. It's the join key into both diagnostics summary resources via the `job_id` segment.

## v23 / April 2026 notes for operators

- **EC-for-leads is no longer a separate toggle** from EC-for-web in newer accounts. The `CONVERSION_ACTION_NOT_ELIGIBLE_FOR_ENHANCED_CONVERSIONS_FOR_LEADS` code is being phased out for a unified code; disposition stays `fix-config` and the `human_action` text gets refreshed via operator override on proto bump.
- **Customer-data-terms acceptance is per-customer-account, not per-conversion-action.** A single `CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS` blocks **every** upload for the account until accepted. This is surfaced as a banner in the Batches panel, not buried per-row.
- **`order_id` cap: 64 characters.** HCP estimate IDs fit, but enforce at payload build.
- **Hashing:** SHA-256 lowercase-trimmed, unchanged across versions.
