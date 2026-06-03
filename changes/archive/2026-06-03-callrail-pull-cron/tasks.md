## 1. Edge function auth bypass

- [x] 1.1 In `supabase/functions/callrail-pull/index.ts`, extract the bearer token and short-circuit user validation when the token exactly equals `Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")`. Keep the existing user-JWT path for all other bearers.
- [x] 1.2 Log the caller class (`"service"` vs `"user"`) at the start of `handlePost` for observability.
- [x] 1.3 Verify behavior locally: POST `{}` with the service-role bearer → 200; POST with no bearer → 401; POST with a junk bearer → 401.

## 2. Default date range = last 24h

- [x] 2.1 In `supabase/functions/callrail-pull/index.ts`, change the no-body default so `start_date = yesterday (UTC YYYY-MM-DD)` and `end_date = today (UTC YYYY-MM-DD)`. Explicit-date callers are unaffected.

## 3. Deploy & verify

- [x] 3.1 Deploy the updated edge function (`mcp__supabase__deploy_edge_function`).
- [x] 3.2 Smoke-test: POST `{}` with the service-role bearer; confirm HTTP 200 and that `callrail_leads` gains rows whose `start_time` falls in the last 24 hours.
