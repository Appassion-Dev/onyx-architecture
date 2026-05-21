## ADDED Requirements

### Requirement: Persist raw request and response per batch

The upload function SHALL persist the exact JSON request body sent to the Google Ads `uploadClickConversions` endpoint and the parsed JSON response received from Google onto the `gads_conversion_upload_batches` row for the batch. Both values SHALL be written exactly once per batch invocation, as part of the same write that finalizes the batch row's `http_status` / `accepted_count` / `rejected_count` / `request_error_*` fields.

The table `gads_conversion_upload_batches` SHALL include two `jsonb` columns, `request_body` and `response_body`, both nullable. Pre-existing rows (predating this change) MAY remain `NULL`; no backfill is required.

The `request_body` SHALL be the object `{ "conversions": [...], "partialFailure": true }` whose `JSON.stringify`-ed form was POSTed to Google, with each `conversions[i]` entry exactly as built by the payload-builder (including hashed `userIdentifiers`, `gclid`, `conversionAction`, `conversionDateTime`, `orderId`, and optional `conversionValue`/`currencyCode`/`consent` fields).

#### Scenario: Successful batch records both bodies

- **WHEN** the function POSTs a batch to `uploadClickConversions` and Google returns a 2xx response
- **THEN** the batch row's `request_body` SHALL equal the JSON object that was POSTed and `response_body` SHALL equal the parsed JSON Google returned, both written in the same update as `accepted_count`, `rejected_count`, `http_status`, and `job_id`

#### Scenario: Partial-failure batch records both bodies

- **WHEN** the function POSTs a batch and Google returns a 2xx response containing a `partialFailureError`
- **THEN** the batch row's `request_body` and `response_body` SHALL both be populated; `response_body` SHALL include the `partialFailureError` field exactly as Google returned it

#### Scenario: Non-2xx HTTP batch failure records request body

- **WHEN** the function POSTs a batch and Google returns a non-2xx HTTP status
- **THEN** the batch row's `request_body` SHALL be populated and `response_body` SHALL be `NULL` (the body is not assumed to be JSON); the existing `request_error_code` / `request_error_message` / `http_status` fields SHALL still be set per current behavior

#### Scenario: Network failure records request body and structured envelope

- **WHEN** the `fetch` call throws before a response is received (network, DNS, TLS, timeout)
- **THEN** the batch row's `request_body` SHALL be populated and `response_body` SHALL be a JSON object `{ "network_error": "<truncated error message>", "captured_at": "<ISO-8601 timestamp>" }` distinguishable from a real Google response by the presence of the `network_error` key

#### Scenario: Mock-response test path records both bodies

- **WHEN** the upload is invoked with `_mock_response` set (test hook in `UploadRequestBody`)
- **THEN** the batch row's `request_body` SHALL be populated with the body that would have been sent and `response_body` SHALL be populated with the mock response value; no HTTP call is made

#### Scenario: Capture failure does not corrupt batch accounting

- **WHEN** writing `request_body` or `response_body` to the batch row fails
- **THEN** the existing batch finalization behavior (per-row outcome updates, `accepted_count` / `rejected_count`, lifecycle transitions on `gads_conversion_uploads`) SHALL still complete; the batch row's other columns SHALL be written; the new columns MAY remain `NULL` for that batch and the function SHALL surface the error in its normal error-propagation path
