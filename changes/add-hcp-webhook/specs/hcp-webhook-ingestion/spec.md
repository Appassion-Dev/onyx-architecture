## ADDED Requirements

### Requirement: Public webhook endpoint

The system SHALL expose a public Supabase edge function `hcp-webhook` that accepts HTTP `POST` requests at `/functions/v1/hcp-webhook` without requiring a Supabase JWT (`verify_jwt = false`).

#### Scenario: POST request is accepted

- **WHEN** a `POST` request is received at `/functions/v1/hcp-webhook`
- **THEN** the function processes it (verifies signature and logs) and returns a `2xx` response with a JSON body

#### Scenario: Non-POST method is rejected

- **WHEN** a request using any method other than `POST` or `OPTIONS` is received
- **THEN** the function returns `405 Method Not Allowed`

#### Scenario: CORS preflight

- **WHEN** an `OPTIONS` request is received
- **THEN** the function returns a `2xx` response with CORS headers and no body processing

### Requirement: Signing key configuration

The system SHALL read the HMAC signing secret from a `HCP_WEBHOOK_SIGNING_KEY` environment variable and SHALL NEVER include the secret's value in any log output or response.

#### Scenario: Signing key is present

- **WHEN** `HCP_WEBHOOK_SIGNING_KEY` is set and a request arrives
- **THEN** the function uses it as the HMAC key to compute the expected signature

#### Scenario: Signing key is missing

- **WHEN** `HCP_WEBHOOK_SIGNING_KEY` is not set and a request arrives
- **THEN** the function logs an error indicating the key is unset and treats signature verification as failed/unconfirmed
- **AND** the secret value never appears in logs or the response under any condition

### Requirement: HCP timestamped HMAC-SHA256 verification

The system SHALL verify request authenticity by computing `HMAC-SHA256` using `HCP_WEBHOOK_SIGNING_KEY` as the key over the message `"${Api-Timestamp}.${rawBody}"`, where `Api-Timestamp` and `Api-Signature` are taken from the request headers and `rawBody` is the exact unparsed request body. The computed digest SHALL be base64-encoded for comparison against `Api-Signature` (base64 is the default encoding, matching the project's `callrail-webhook` function). The comparison SHALL be constant-time.

#### Scenario: Signature computed over raw body

- **WHEN** the function verifies a request
- **THEN** it reads the raw request body as a string and computes the HMAC over `Api-Timestamp + "." + rawBody`
- **AND** it does NOT re-serialize (parse-then-stringify) the body before hashing

#### Scenario: Constant-time comparison

- **WHEN** the computed HMAC is compared against the `Api-Signature` header
- **THEN** the base64-encoded digest is compared in constant time with respect to the input bytes

#### Scenario: Missing signature headers

- **WHEN** a request is missing `Api-Signature` or `Api-Timestamp`
- **THEN** the function logs the absence and treats verification as failed/unconfirmed

### Requirement: Digest-encoding resolution logging

Because HCP does not document whether `Api-Signature` is hex- or base64-encoded, the system defaults to base64 for comparison but SHALL log the locally computed HMAC in BOTH hex and base64 encodings alongside the received `Api-Signature` value, so the base64 default can be confirmed (or the encoding flipped to hex) from a genuine delivery.

#### Scenario: Both encodings are logged

- **WHEN** the function computes the expected HMAC for a request
- **THEN** it logs the hex-encoded digest, the base64-encoded digest, and the received `Api-Signature` header value together

### Requirement: Request logging (phase 1 behavior)

The system SHALL log each incoming request for observability, including the HTTP method, request headers (excluding any secret value), the raw body, and the parsed JSON body when parseable. In this phase the function SHALL NOT write to the database and SHALL NOT route or interpret events by their `event` key.

#### Scenario: Request is logged

- **WHEN** a `POST` request is received
- **THEN** the function logs the method, headers, raw body, and parsed body
- **AND** it performs no database writes
- **AND** it performs no event-key-specific routing or handling

#### Scenario: Unparseable body

- **WHEN** the request body is not valid JSON
- **THEN** the function still logs the raw body and records that JSON parsing failed, without throwing an unhandled error
