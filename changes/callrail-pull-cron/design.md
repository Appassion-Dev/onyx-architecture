## Context

`supabase/functions/callrail-pull/index.ts` is currently invoked from the UI with a user JWT and validated via `sbAuth.auth.getUser(token)`. Its default date range (when the body omits dates) is today only — too narrow for a periodic scheduler that should catch anything that happened in the last day.

A scheduler will eventually call this function unattended. That scheduler is being configured outside this change (Supabase Studio / manual `cron.schedule`), so this change only needs to make the function safe and useful for both human and machine callers.

## Goals / Non-Goals

**Goals:**
- Allow the function to be called with the platform's service-role credential, not only a user session JWT.
- Make the no-argument behavior cover the last 24 hours, so a scheduler does not need to compute dates.
- Preserve the current UI-triggered behavior exactly for callers that send a user JWT or explicit dates.

**Non-Goals:**
- Shipping the cron job itself in a migration. Scheduling is set up out-of-band.
- New ingestion modes, backfill orchestration, mapper/schema changes, or webhook replacement.

## Decisions

### Decision 1: Service-role bypass inside the existing function, not a new function

The function checks the bearer against `SUPABASE_SERVICE_ROLE_KEY`. On exact match, skip `auth.getUser` and proceed. Otherwise, run the existing user-JWT path unchanged.

**Why over alternatives:**
- *Split into a separate `callrail-pull-cron` function*: duplicates ~200 lines of fetch/map/upsert code. Drift risk.
- *Drop auth entirely (verify_jwt = false)*: exposes the endpoint publicly. Unacceptable.
- *Use a different shared secret header*: another secret to provision; the service role is already what any platform-level caller will have, and is exactly the "trust me, I'm the platform" credential.

### Decision 2: Default to last 24 hours instead of today

When the body omits `start_date`/`end_date`, the function now uses `start_date = yesterday (UTC)`, `end_date = today (UTC)`. A scheduler firing every N minutes just POSTs `{}` and always covers the rolling window; UI calls that omit dates get the same window. Explicit-date callers are unaffected.

**Why over alternatives:**
- *Keep "today" as default, have the scheduler compute dates in SQL*: pushes date arithmetic into whatever scheduler ends up calling this. Encoding it in the function is one source of truth.
- *Default to 48h or longer*: larger CallRail API spend per call with marginal benefit; 24h covers any reasonable scheduler cadence.

## Risks / Trade-offs

- **Service-role bypass widens the trust boundary** → Mitigated by requiring an exact equality check against `SUPABASE_SERVICE_ROLE_KEY` (a `===` string compare), not "any JWT signed by Supabase". Logs explicitly distinguish `service` vs `user` invocations.
- **Default window changed from 1 day to 2 days** → 2× rows fetched per no-argument call. CallRail upsert is idempotent on `callrail_id`, so no DB-side duplication. UI button users who relied on a today-only default will now see yesterday's rows too; treated as a minor improvement, not a regression.
- **Concurrent scheduler + UI invocations** → Idempotent at the DB layer (`onConflict: callrail_id`); worst case is duplicate API spend for a window, which is acceptable.

## Migration Plan

1. Redeploy the edge function (`mcp__supabase__deploy_edge_function`).
2. Configure the schedule out-of-band (Supabase Studio or a manual `cron.schedule` SQL call — not part of this change).
3. Spot-check `callrail_leads` for rows whose `start_time` falls in the last 24 hours after the first scheduled fire.

**Rollback:** Redeploy the previous function version; unschedule the cron job wherever it was created. No data migration to undo — upserts are additive.
