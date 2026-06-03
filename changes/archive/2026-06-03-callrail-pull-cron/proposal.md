## Why

Today, the `callrail-pull` edge function only runs when a logged-in user triggers it from the UI, and its default date range is just the current day. CallRail data drifts whenever no one opens the app, leaving gaps in `callrail_leads`. We want to (1) let an unattended scheduler call this function with the platform's service-role credential, and (2) make the no-argument behavior pull the last 24 hours instead of only today — so a scheduled invocation needs no body computation.

The cron job itself will be configured outside this change (Supabase Studio / manual `cron.schedule`), so this change deliberately does not ship a migration.

## What Changes

- Modify `callrail-pull/index.ts` to accept the project's `SUPABASE_SERVICE_ROLE_KEY` as a bearer in place of a user JWT: when the bearer is an exact match for the service-role key, skip the `auth.getUser` check; otherwise the existing user-JWT path is unchanged.
- Change the default date range when the request body omits `start_date`/`end_date`: pull the last 24 hours, expressed as `start_date = yesterday (UTC)`, `end_date = today (UTC)`. UI calls that omit dates pick this up automatically.
- Log the caller class (`service` vs `user`) at the start of `handlePost` for observability.

## Capabilities

### New Capabilities
- `callrail-ingest`: On-demand ingestion of CallRail call records into `callrail_leads`, covering the auth model for both UI-triggered and service-triggered invocations and the default date range.

### Modified Capabilities
<!-- none -->

## Impact

- Code: `supabase/functions/callrail-pull/index.ts` only.
- Infra: None — scheduling is configured outside this change.
- Dependencies: None added.
- Risk: Service-role bypass widens what the function trusts; mitigated by requiring an exact match against `SUPABASE_SERVICE_ROLE_KEY` (not just "any valid JWT").
