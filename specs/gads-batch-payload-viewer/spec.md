## Requirements

### Requirement: Raw payload columns on the batch row

The batches table at `/conversions/batches` SHALL display two additional columns, **Request** and **Response**, on each batch row, sourced from `gads_conversion_upload_batches.request_body` and `gads_conversion_upload_batches.response_body`. Each cell SHALL render as a clickable affordance that opens a viewer showing the pretty-printed JSON for that entire batch.

#### Scenario: Both payloads captured

- **WHEN** a batch row has `request_body` and `response_body` populated
- **THEN** the Request and Response cells SHALL each render a "View" affordance with a small badge showing payload size (e.g. "View · 2.4 KB")
- **AND** clicking the affordance SHALL open a viewer with the JSON indented (2-space), syntax-highlighted or at minimum monospace, and a copy-to-clipboard button

#### Scenario: Network-error response envelope

- **WHEN** `response_body` contains the structured `{ network_error, captured_at }` envelope written for network failures
- **THEN** the Response viewer SHALL still render that JSON as-is without special transformation, so the failure detail is inspectable verbatim

#### Scenario: Payload missing (legacy or pre-capture row)

- **WHEN** `request_body` IS NULL or `response_body` IS NULL on a batch row (legacy rows written before `capture-raw-batch-payloads` shipped)
- **THEN** the corresponding cell SHALL render a disabled "—" placeholder with hover tooltip "No payload captured"
- **AND** no viewer SHALL open on click

### Requirement: Per-estimate payload slices in the drill-down

The batch drill-down (the constituent-rows section shown when a batch is expanded) SHALL display the same **Request** and **Response** columns on every constituent row. Each cell SHALL open a viewer scoped to **only that estimate's slice** of the batch payload — not the full batch payload.

The request slice for an estimate row SHALL be the entry in `request_body.conversions[]` whose `orderId` equals the estimate row's `estimate_id`. `orderId` is set on every uploaded conversion by the payload builder (regardless of `conversion_type` or whether `gclid` is present), making it the authoritative match key. If multiple entries match (same estimate uploaded twice in one batch), all matching entries SHALL be shown as an array.

The response slice for an estimate row SHALL be derived from the same array index `i` as the matched request entry, drawn from whichever of these is present:
- `response_body.partialFailureError.details[*].errors[]` filtered to entries whose `location.fieldPathElements` references operation index `i`, **or**
- `response_body.results[i]` if Google returned per-row results.

If neither yields a slice for index `i`, the response cell SHALL show "Accepted (no per-row detail returned)" since Google omits successful entries from partial-failure detail.

#### Scenario: Estimate row matches a request entry

- **WHEN** an expanded batch's constituent row has an `estimate_id` that equals `request_body.conversions[i].orderId` for some `i`
- **THEN** the Request cell SHALL open a viewer showing just that one conversion object, pretty-printed

#### Scenario: Estimate row was rejected with a per-row error

- **WHEN** an expanded batch's constituent row corresponds to operation index `i`, and `response_body.partialFailureError` contains errors referencing that index
- **THEN** the Response cell SHALL open a viewer showing an array of those error objects, pretty-printed

#### Scenario: Estimate row was accepted in a partial-failure batch

- **WHEN** an expanded batch's constituent row corresponds to operation index `i` and no `partialFailureError` entry references `i`
- **THEN** the Response cell SHALL render "Accepted" with a tooltip explaining Google omits successful rows from partial-failure detail

#### Scenario: Slice cannot be resolved

- **WHEN** an expanded batch's constituent row has no `orderId` match in `request_body.conversions[]` (e.g. payload missing, or row was excluded before the API call)
- **THEN** both cells SHALL render a disabled "—" placeholder with hover tooltip "No payload slice for this row"

### Requirement: GCLID column on constituent rows

The batch drill-down SHALL display a **GCLID** column on every constituent row, sourced from `vw_gads_conversion_uploads.gclid`. This makes visible which estimates were sent with a Google click ID versus uploaded via user-data identifiers only.

#### Scenario: Row has a GCLID

- **WHEN** the constituent row's `gclid` is non-null
- **THEN** the GCLID cell SHALL render the value in a monospace font, truncated for layout (e.g. first 12 characters followed by `…`), with the full value available via hover tooltip

#### Scenario: Row has no GCLID

- **WHEN** the constituent row's `gclid` is null
- **THEN** the cell SHALL render a muted `—` with tooltip "No GCLID — uploaded via user-data identifiers only"

### Requirement: Viewer UX

The payload viewer SHALL be a modal or popover that:

- Renders JSON pretty-printed with 2-space indentation in a monospace font.
- Provides a "Copy JSON" button that copies the displayed JSON to the clipboard.
- Provides a title indicating the scope ("Batch <short id> — Request", "Batch <short id> — Estimate <estimate_id> Response", etc.).
- Is dismissible via Escape, an explicit close button, and backdrop click.

#### Scenario: Copy to clipboard

- **WHEN** the user clicks "Copy JSON" inside the viewer
- **THEN** the displayed JSON text (exactly what is rendered) SHALL be written to the clipboard
- **AND** a brief confirmation indicator SHALL appear

#### Scenario: Dismissal

- **WHEN** the viewer is open and the user presses Escape, clicks the close button, or clicks the backdrop
- **THEN** the viewer SHALL close and focus SHALL return to the cell that opened it
