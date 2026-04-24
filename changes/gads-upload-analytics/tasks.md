## 1. Analytics Storage

- [ ] 1.1 Create a Supabase migration for upload analytics snapshot storage tables for daily attribution, client upload health, action upload health, and action configuration snapshots
- [ ] 1.2 Add keys and indexes that enforce the expected snapshot grain for action/date and run-timestamp lookups
- [ ] 1.3 Add storage fields for raw Google Ads summary payloads (`alerts`, `daily_summaries`) alongside normalized columns
- [ ] 1.4 Add a database read model or query surface for derived metrics such as `action alive` and attribution rate

## 2. Daily Analytics Sync Function

- [ ] 2.1 Scaffold a dedicated upload analytics sync edge function and register it explicitly in `supabase/config.toml`
- [ ] 2.2 Reuse the existing Google Ads OAuth and request helper pattern for the new analytics sync function
- [ ] 2.3 Load enabled conversion action IDs from `gads_conversion_config` and exclude disabled or unmapped conversion types from query scope
- [ ] 2.4 Implement the daily attribution GAQL query and persist per-action, per-date snapshot rows
- [ ] 2.5 Implement the client-level and action-level upload health queries and persist normalized fields plus raw summary payloads
- [ ] 2.6 Implement the conversion action configuration query and persist snapshots needed for drift detection
- [ ] 2.7 Record per-query-slice success and failure so one failed Google Ads resource does not discard successful slices from the same run

## 3. Scheduling and Backfill

- [ ] 3.1 Add a daily `pg_cron` job that invokes the analytics sync edge function through `pg_net`
- [ ] 3.2 Add an initial backfill path for a recent attribution window so the dashboard is useful immediately after deployment
- [ ] 3.3 Verify the new schedule runs independently from the existing conversion upload and spend sync jobs

## 4. GCLID Verification Path

- [ ] 4.1 Add an operator-facing verification path that accepts a GCLID and exact click date
- [ ] 4.2 Validate missing click dates and out-of-window click dates before issuing any Google Ads query
- [ ] 4.3 Implement the compliant `click_view` query and return structured match or no-match diagnostics
- [ ] 4.4 Verify that the scheduled analytics sync never issues `click_view` queries

## 5. Dashboard Read Path

- [ ] 5.1 Add Supabase reads for cached upload analytics snapshots and the latest drift state
- [ ] 5.2 Surface a platform health badge and per-action health indicators from cached upload health snapshots
- [ ] 5.3 Surface `action alive` and attribution-rate metrics from cached attribution snapshots plus local upload counts
- [ ] 5.4 Add an operator workflow for row-level GCLID verification and render the diagnostic response clearly

## 6. Verification

- [ ] 6.1 Verify the migration and analytics sync function locally against the local Supabase stack
- [ ] 6.2 Verify a successful sync writes all expected analytics slices to storage
- [ ] 6.3 Verify partial Google Ads query failure still preserves successful slices and records the failure state
- [ ] 6.4 Verify GCLID checks reject unsupported requests and return explicit no-match diagnostics when Google Ads returns zero rows
- [ ] 6.5 Verify the dashboard reads cached analytics only and does not require live Google Ads queries to render