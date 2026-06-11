## ADDED Requirements

### Requirement: Per-estimate upload payload slice view

The system SHALL provide a database view `vw_gads_upload_payload_slices` that projects every `gads_conversion_uploads` row (`u.*`) plus derived columns sliced from that row's batch payload. Slices SHALL be keyed by `orderId = estimate_id` against the row's own `batch_id`, and SHALL include:
- `request_slice`: the request `conversions` entries whose `orderId` equals the row's `estimate_id`.
- `response_results_slice`: the positional `results[i]` entries for this estimate's matched request indices.
- `error_slice`: the `partialFailureError` errors whose `location.fieldPathElements` reference a matched request index with `fieldName = "conversions"`.
- `response_slice_kind`: a discriminator with exactly one of `missing`, `unknown`, `accepted`, `results`, or `errors`.

The view SHALL be defined `WITH (security_invoker = true)` and SHALL NOT modify or depend on changes to `vw_gads_conversion_uploads`, `vw_conversion_candidates`, or `vw_gads_upload_reconciliation_daily`.

#### Scenario: Accepted upload with a success result
- **WHEN** an upload row's batch response contains a `results[i]` entry for the row's matched request index and no error references that index
- **THEN** `response_results_slice` SHALL contain that entry and `response_slice_kind` SHALL be `results`

#### Scenario: Row rejected with a per-row error
- **WHEN** the batch response `partialFailureError` contains an error whose `fieldPathElements` reference the row's matched index
- **THEN** `error_slice` SHALL contain that error and `response_slice_kind` SHALL be `errors`, taking precedence over any positional results entry

#### Scenario: Request entries sliced by orderId
- **WHEN** the batch `request_body.conversions` contains entries with `orderId` equal to the row's `estimate_id`
- **THEN** `request_slice` SHALL contain exactly those entries and exclude entries for other estimates

#### Scenario: Network-error response envelope
- **WHEN** the row's batch `response_body` is a network-error envelope (contains `network_error`)
- **THEN** `response_slice_kind` SHALL be `unknown` so the consumer can fall back to the full batch payload

#### Scenario: No batch or no captured payload
- **WHEN** the row has no `batch_id`, or its batch `response_body` is null
- **THEN** the slice columns SHALL be null and `response_slice_kind` SHALL be `missing`

### Requirement: Slices are narrowed to a single conversion type

Because the slices are keyed by `orderId = estimate_id`, a row's `request_slice` / `response_results_slice` / `error_slice` MAY include conversions for other conversion types when the batch carried multiple types for the same estimate. The view SHALL tag each `error_slice` entry with the `conversionAction` of the request conversion it references (request and results entries already carry `conversionAction` natively). The detail panel SHALL narrow all three slices to the row's own conversion type by matching each entry's `conversionAction` to the row's `conversion_action`, so a per-type View shows only that type's payload.

#### Scenario: A View shows only its own conversion type
- **WHEN** a batch carried multiple conversion types for the estimate and the user opens a type's Request, Response, or Errors View
- **THEN** the displayed payload SHALL contain only entries whose `conversionAction` matches that conversion type, excluding the other types' entries

#### Scenario: Error entries are tagged with conversionAction
- **WHEN** an `error_slice` entry is projected by the view
- **THEN** it SHALL include the `conversionAction` of the request conversion its `fieldPathElements` index references

#### Scenario: Fallback when conversion_action is unknown
- **WHEN** the row's `conversion_action` is null (legacy rows predating the column)
- **THEN** narrowing SHALL fall back to the full estimate-level slice rather than dropping all entries

### Requirement: Independent per-conversion-type batch slicing

Each view row SHALL slice the payload of its own `batch_id`, so an estimate whose conversion types were uploaded in different batches yields correct, independent slices per type.

#### Scenario: Estimate's types span multiple batches
- **WHEN** an estimate's `booking_lead`, `qualified_lead`, and `converted_lead` rows reference three different `batch_id` values
- **THEN** each row's slices SHALL be derived from its own batch and SHALL NOT mix entries across batches

### Requirement: Estimate detail panel fetches slices by estimate_id

The estimate conversion detail surface SHALL fetch all of an estimate's available slices in a single request filtered by `estimate_id` only, without a `conversion_type` argument. The frontend SHALL index the returned rows by `conversion_type` and render the stage in view, and SHALL treat a conversion type with no returned row as a normal empty state rather than an error.

#### Scenario: Opening a multi-type estimate detail panel
- **WHEN** the detail panel opens for an estimate that has more than one uploaded conversion type
- **THEN** a single request filtered by `estimate_id` SHALL return one row per existing upload type, each with its slices

#### Scenario: Conversion type not yet uploaded
- **WHEN** a stage shown in the panel has no upload row for the estimate
- **THEN** the panel SHALL render that stage as an empty / "not uploaded" state without error

### Requirement: Estimate detail panel layout for slice display

The estimate detail pane SHALL display upload payload slices within each conversion type's own stage detail section (Booking / Qualified / Converted), scoped to that conversion type. Slices SHALL NOT be presented as a single combined section listing all three types, and SHALL NOT be placed in a separate side container. Within a stage section, the request / response / error slices SHALL be presented as "View" links. Activating a View link SHALL open a JSON popup that reuses the existing `PayloadViewer` component (the same popup used on the Batches page) rather than a new dialog implementation, to avoid frontend duplication.

#### Scenario: Slice links live inside each conversion type's section
- **WHEN** the estimate detail pane is open
- **THEN** each conversion type's slice "View" links SHALL appear inside that type's own stage detail section, and SHALL NOT be combined into one section or rendered in a separate side container

#### Scenario: Activating a View link opens the JSON popup
- **WHEN** the user clicks a slice's "View" link
- **THEN** the existing `PayloadViewer` popup SHALL open displaying that slice's JSON, with no separate/new dialog component introduced

#### Scenario: No payload for a slice
- **WHEN** a conversion type's slice has no payload to show (its `response_slice_kind` is `missing`, or the corresponding slice column is empty)
- **THEN** that type's stage section SHALL indicate the empty state instead of presenting an actionable View link

### Requirement: Slice exposure is limited to the opened estimate

The detail surface SHALL receive only the opened estimate's own slices and SHALL NOT receive other estimates' request/response payloads from the same batch. Access to the view SHALL be governed by the caller's grants/RLS on `gads_conversion_upload_batches` via `security_invoker`.

#### Scenario: Opening one estimate does not expose others
- **WHEN** the detail panel opens for one estimate whose uploads shared a batch with other estimates
- **THEN** the returned slices SHALL contain only the opened estimate's identifiers and entries

### Requirement: Slices reflect the latest attempt

Because `gads_conversion_uploads.batch_id` references the most recent batch for the row, the view SHALL surface slices for that latest attempt only. Full per-attempt history is out of scope for this view.

#### Scenario: Row retried into a newer batch
- **WHEN** an upload row previously failed in one batch and was later re-sent in a newer batch
- **THEN** the view's slices SHALL reflect the newer batch referenced by `batch_id`
