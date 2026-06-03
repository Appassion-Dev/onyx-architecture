# callrail-ingest Specification

## Purpose

Defines the behavior of the `callrail-pull` edge function, which ingests CallRail call records into the `callrail_leads` table. It covers caller authentication, default date-range handling, and idempotent upserts so the function can be safely invoked both interactively (user session) and on a schedule (service-role).

## Requirements

### Requirement: Edge function authenticates both user and service-role callers

The `callrail-pull` edge function SHALL accept two classes of bearer token on the `Authorization` header:

1. A user session JWT, which MUST be validated via `auth.getUser(token)` before the pull proceeds.
2. The project's `SUPABASE_SERVICE_ROLE_KEY`, compared by exact string equality. When matched, the function SHALL skip user lookup and proceed.

Any other bearer, or a missing `Authorization` header, MUST result in HTTP 401.

#### Scenario: Valid user JWT
- **WHEN** a request arrives with `Authorization: Bearer <valid user JWT>`
- **THEN** the function validates the token via `auth.getUser`, and on success continues to the CallRail pull

#### Scenario: Service-role bearer
- **WHEN** a request arrives with `Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>`
- **THEN** the function skips `auth.getUser` and continues to the CallRail pull

#### Scenario: Invalid bearer
- **WHEN** a request arrives with a bearer that is neither a valid user JWT nor the service-role key
- **THEN** the function responds with HTTP 401 and does not call CallRail

#### Scenario: Missing Authorization header
- **WHEN** a request arrives with no `Authorization` header
- **THEN** the function responds with HTTP 401

### Requirement: Default date range is the last 24 hours

When the request body omits `start_date` and `end_date`, the function SHALL pull calls for the last 24 hours, expressed as a 2-day UTC window: `start_date = yesterday`, `end_date = today` (both `YYYY-MM-DD`).

#### Scenario: Empty JSON body
- **WHEN** a request is POSTed with body `{}` (or no body)
- **THEN** the function pulls CallRail calls with `start_date = yesterday (UTC YYYY-MM-DD)` and `end_date = today (UTC YYYY-MM-DD)`

#### Scenario: Explicit date range
- **WHEN** a request body provides `start_date` and `end_date` in `YYYY-MM-DD` format
- **THEN** the function uses those dates verbatim for the CallRail query

#### Scenario: Malformed date
- **WHEN** a request body provides `start_date` or `end_date` that does not match `^\d{4}-\d{2}-\d{2}$`
- **THEN** the function responds with HTTP 400 and does not call CallRail

### Requirement: Idempotent upsert into callrail_leads

The function SHALL upsert fetched calls into `callrail_leads` with `onConflict: callrail_id`, in batches of at most 500 rows. Re-running the function for an overlapping date range MUST NOT produce duplicate rows.

#### Scenario: Re-running for the same day
- **WHEN** the function is invoked twice in quick succession for the same date range
- **THEN** the second invocation updates existing rows rather than inserting duplicates, and `callrail_leads` row count for that range is unchanged
