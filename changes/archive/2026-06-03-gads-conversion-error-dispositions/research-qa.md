# Pre-Implementation Research Q&A

Answers grounded in our v23 pipeline, the six-namespace error catalog, the `gads_error_dispositions` lookup, and the batches/diagnostics design from `proposal.md`.

---

## 1. Error enum + dispositions

- **API version**: Google Ads API **v23** (`POST /v23/customers/{id}:uploadClickConversions`). Our codegen script pins this version and re-fetches the protos on bump.
- **Six namespaces we capture** (not just `ConversionUploadError`): `conversionUploadError`, `userDataError`, `quotaError`, `internalError`, `authenticationError`, `fieldError`. All keyed `"<namespace>.<ENUM_NAME>"` in one catalog.
- **Realistically reachable for our GCLID + EC-for-leads setup** (mapped to disposition):
  - `conversionUploadError.UNAUTHORIZED_CUSTOMER` → **fix-config**
  - `conversionUploadError.INVALID_CONVERSION_ACTION` / `CONVERSION_NOT_FOUND` / `CONVERSION_TRACKING_NOT_ENABLED_AT_IMPRESSION_TIME` → **fix-config**
  - `conversionUploadError.CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS` / `CONVERSION_ACTION_NOT_ELIGIBLE_FOR_ENHANCED_CONVERSIONS_FOR_LEADS` → **fix-config**
  - `conversionUploadError.CLICK_NOT_FOUND` → **drop** with `no_alert=true` (proto explicitly says ignore for EC-for-leads)
  - `conversionUploadError.EXPIRED_EVENT` (>90 days) → **drop**
  - `conversionUploadError.TOO_RECENT_EVENT` → **retry** with `retry_after_seconds=21600`
  - `conversionUploadError.DUPLICATE_ORDER_ID` / `ORDER_ID_ALREADY_IN_USE` → **drop** (Google is source of truth; our `UNIQUE(estimate_id, conversion_type)` prevents local dupes but not re-uploads)
  - `conversionUploadError.INVALID_CONVERSION_DATE_TIME` / `EVENT_NOT_ATTRIBUTED_TO_CONVERSION` → **fix-data**
  - `userDataError.INVALID_HASHED_EMAIL` / `INVALID_HASHED_PHONE_NUMBER` / `INVALID_USER_IDENTIFIER` → **fix-data**
  - `userDataError.INSUFFICIENT_MATCHING_HASHED_PII` → **drop** with `no_alert=true` (acceptable when we have GCLID)
  - `quotaError.RESOURCE_EXHAUSTED` / `RESOURCE_TEMPORARILY_EXHAUSTED` → **retry** (longer `retry_after_seconds`)
  - `internalError.*` / `authenticationError.OAUTH_TOKEN_*` → **retry** (transient) or **fix-config** (revoked credentials)
  - `fieldError.REQUIRED` / `INVALID_VALUE` → **fix-data** (payload is wrong)

### Caveman Explanation
When we tell Google "this customer clicked your ad and then booked a job," Google can come back with different types of "nope." Some nopes mean we need a human to fix a switch in the Google Ads dashboard (like agreeing to their data terms). Some mean the data we sent was bad (wrong date, mangled email). Some mean the click is too old and Google has already forgotten about it — just throw the row away. And a few mean "wait a few hours and try again." Right now we treat all of these the same way (broken forever), which wastes retries on things that will never work and drops things that would have worked if we just waited.

---

## 2. Request-level vs partial-failure errors

- **Whole-batch failures** (kill the request, no `results[]`): non-2xx HTTP. Sources:
  - Auth errors (`AuthenticationError.*`, `AuthorizationError.*` — revoked refresh token, MCC link removed) → land on `gads_conversion_upload_batches` with `request_error_code`; all rows go to `needs-attention`, not retried per-row.
  - Quota at request level (`QuotaError.RESOURCE_EXHAUSTED`) → batch-level retry with backoff; rows stay `queued`.
  - Malformed request / `INVALID_CUSTOMER_ID` / `CUSTOMER_NOT_ENABLED` → **fix-config** on the batch; surfaced via the batches panel banner.
  - Network / 5xx / `INTERNAL_ERROR` → batch-level retry.
- **Partial failures** (HTTP 200, `partialFailureError` populated, per-row blame via `details[].location.fieldPathElements[0].index`): everything in §1 above. Each surfaces as a per-row `error_code` + `error_detail` and follows that row's disposition.
- **Surfacing**:
  - Request-level errors → **Batches panel** (red batch row, `request_error_code`, drill-down lists affected rows).
  - Per-row errors → **Needs-Attention inbox** grouped by `error_code`.

### Caveman Explanation
Sometimes the whole shipment of conversions gets rejected at the door — Google won't even open the box (usually because our login expired or our account isn't set up right). Other times Google opens the box, accepts most of it, but pulls out a few individual items and says "these ones are bad." The first kind of failure affects every row in the batch and needs a human to fix the account. The second kind is per-row and gets handled one at a time based on what went wrong. We need a separate display for each so operators immediately know whether it's an account fire drill or a handful of bad rows.

---

## 3. Per-conversion attribution signal

- **No per-conversion attribution feedback exists.** Google returns `results[]` confirming the upload was *accepted*, not whether it was *counted/attributed*. There is no per-row "attributed to click X" signal at any later time.
- **Aggregate diagnostics are the only feedback path:**
  - `offline_conversion_upload_client_summary` — daily totals per customer (success/failure counts, last upload date, last error code).
  - `offline_conversion_upload_conversion_action_summary` — grain is **(customer × conversion_action × upload_date × status)**; counts, last error code, pending-event windows. Already pulled by `gads-upload-analytics` into `gads_action_upload_health`.
  - **Data delay**: ~3 hours typical, up to 24h. Backfill window ~14 days.
- **Implication**: the attribution reconciliation panel can only say *"Of N rows we uploaded in this (action × day) bucket, Google reports M succeeded / K failed with code X"* — not "row 12345 was attributed." The batches → `gads_action_upload_health` join lives within this constraint; the "shared bucket" caveat is explicitly deferred per the proposal.

### Caveman Explanation
When we send a conversion to Google, Google says "got it" — but it never tells us whether that specific booking actually got credited to an ad click. The only report Google gives back is a daily summary: "out of everything you sent today for this conversion type, X worked and Y didn't." We can't zoom in to one specific customer and ask "did Google count this one?" So our dashboard will show totals and error counts, but it can't put a green checkmark on individual rows meaning "Google confirmed this one." That's just a limitation of the Google Ads API.

---

## 4. `job_id`

- **Returned on the upload response** as `jobId` at the top level of `UploadClickConversionsResponse`. Join key into both diagnostics summary resources via the `job_id` segment.
- **Stored on `gads_conversion_upload_batches.job_id`**, indexed; rows reference the batch via `batch_id` FK.
- **Recommendation: let Google generate it.** Self-assigning triggers `INVALID_JOB_ID(52)` if format is wrong, adds uniqueness/collision concerns, and gives nothing over our internal `batch_id` UUID. Documented in the proposal under "Out of scope."

### Caveman Explanation
Every time we send a batch of conversions to Google, Google stamps it with a tracking number called a job ID. We can use that number later to look up how many conversions in that batch were accepted. We could try to make up our own tracking number, but Google is picky about the format and we'd risk errors for no benefit — Google's stamp is just as good. We save it on our end so we can tie our batch records to Google's reports.

---

## 5. GCLID vs user-data-only uploads

- **Behavior**: `uploadClickConversions` accepts either or both. With GCLID: direct click-to-conversion attribution. With only `userIdentifiers` (hashed email/phone): EC-for-leads matching against logged-in Google users — fuzzier, lower match rate.
- **Error differences by path**:
  - GCLID-bearing → can hit `CLICK_NOT_FOUND` (drop+mute), `UNPARSEABLE_GCLID`, `EXPIRED_EVENT`.
  - User-data-only → can hit `INSUFFICIENT_MATCHING_HASHED_PII`, `INVALID_HASHED_*`, `CONVERSION_ACTION_NOT_ELIGIBLE_FOR_ENHANCED_CONVERSIONS_FOR_LEADS`.
- **Distinguishing accepted-with-GCLID from accepted-with-user-data**: **the upload response does not tell you.** `results[]` confirms acceptance only. Post-hoc signal is the diagnostics summary (click-based vs enhanced match counts at action-day grain).
- **Action**: store `gclid_present`, `email_present`, `phone_present` flags on `gads_conversion_uploads` at upload time to compute our own data-quality KPI ("% sent with click ID") without depending on Google. Reconcile against diagnostics' enhanced-vs-click split for ground truth.

### Caveman Explanation
There are two ways we can tell Google "this person came from one of your ads." The strong way is a click ID — a code attached to the person's booking that proves exactly which ad they clicked. The weak way is a hashed email or phone number — Google tries to match it against its own logged-in users, but it's fuzzy and often fails. Google accepts both but never tells us which one it actually used. So we track on our own side whether each row had a click ID when we sent it, giving us a "data quality score" — the higher the percentage of rows with a real click ID, the more reliable our conversion reporting is.

---

## 6. Version-sensitive / recently changed

- **v23 is current.** v22 sunsets mid-2026 — no regression allowed.
- **April 2026 EC settings unification**: enhanced-conversions-for-leads is no longer a separate toggle from EC-for-web in newer accounts.
  - `CONVERSION_ACTION_NOT_ELIGIBLE_FOR_ENHANCED_CONVERSIONS_FOR_LEADS` is being phased out in favor of a unified code. Our catalog sync picks this up automatically on a proto bump; disposition is the same (`fix-config`), `human_action` text is updated via an operator override.
  - `customer_data_terms` acceptance is now per-customer-account, not per-conversion-action. A single `CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS` blocks **all** uploads — the batches panel banner is what surfaces this.
- **Field path indices are stable** in v23 partial-failure responses; the `location.fieldPathElements[0].index` per-row blame join is documented and won't shift.
- **`order_id` length cap**: 64 characters. HCP estimate IDs fit comfortably; add a guard at payload-build time.
- **Hashing**: SHA-256 lowercase-trimmed is unchanged. No format migration.

### Caveman Explanation
Google updates its API every few months. We're on version 23, which is current. The main recent change (April 2026) is that Google merged two privacy settings into one — so one admin toggle in Google Ads now controls everything instead of two separate ones. This is mostly good news for us: fewer config errors to explain to operators. The one thing to watch is that a missing data-terms agreement now blocks every single upload for an account, not just certain conversion types — so we need to make that visible front-and-center when it happens rather than burying it in individual row errors.
