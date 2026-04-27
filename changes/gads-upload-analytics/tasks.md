## 1. Analytics Storage

- [x] 1.1 Create a Supabase migration for upload analytics snapshot storage tables for daily attribution, client upload health, action upload health, and action configuration snapshots
- [x] 1.2 Add keys and indexes that enforce the expected snapshot grain for action/date and run-timestamp lookups
- [x] 1.3 Add storage fields for raw Google Ads summary payloads (`alerts`, `daily_summaries`) alongside normalized columns
- [x] 1.4 Add a database read model or query surface for derived metrics such as `action alive` and attribution rate

## 2. Daily Analytics Sync Function

- [x] 2.1 Scaffold a dedicated upload analytics sync edge function and register it explicitly in `supabase/config.toml`
- [x] 2.2 Reuse the existing Google Ads OAuth and request helper pattern for the new analytics sync function
- [x] 2.3 Load enabled conversion action IDs from `gads_conversion_config` and exclude disabled or unmapped conversion types from query scope
- [x] 2.4 Implement the daily attribution GAQL query and persist per-action, per-date snapshot rows
- [x] 2.5 Implement the client-level and action-level upload health queries and persist normalized fields plus raw summary payloads
- [x] 2.6 Implement the conversion action configuration query and persist snapshots needed for drift detection
- [x] 2.7 Record per-query-slice success and failure so one failed Google Ads resource does not discard successful slices from the same run

## 3. Scheduling and Backfill

- [x] 3.1 Add a daily `pg_cron` job that invokes the analytics sync edge function through `pg_net`
- [x] 3.2 Add an initial backfill path for a recent attribution window so the dashboard is useful immediately after deployment
- [x] 3.3 Verify the new schedule runs independently from the existing conversion upload and spend sync jobs

## 4. GCLID Verification Path

- [x] 4.1 Add an operator-facing verification path that accepts a GCLID and exact click date
- [x] 4.2 Validate missing click dates and out-of-window click dates before issuing any Google Ads query
- [x] 4.3 Implement the compliant `click_view` query and return structured match or no-match diagnostics
- [x] 4.4 Verify that the scheduled analytics sync never issues `click_view` queries

## 5. Dashboard Read Path (MarketingPage — analytics summary)

- [x] 5.1 Add Supabase reads to `MarketingPage` for cached upload analytics snapshots and the latest drift state
- [x] 5.2 Surface a platform health badge and per-action health indicators from cached upload health snapshots in `MarketingPage`
- [x] 5.3 Surface `action alive` and attribution-rate trends from cached attribution snapshots plus local upload counts in `MarketingPage`
- [x] 5.4 Surface pipeline funnel (booked / qualified / converted counts and values) from `vw_conversion_candidates` in `MarketingPage`
- [x] 5.5 Surface Google Ads campaign spend and cost-per-lead metrics from `ads_campaign_stats` in `MarketingPage`
- [x] 5.6 Add an operator workflow in `ConversionsPage` for row-level GCLID verification and render the diagnostic response clearly

## 6. MarketingPage Reframe

- [x] 6.1 Replace sample-data imports in `MarketingPage` with live Supabase queries using TanStack Query
- [x] 6.2 Replace the mock advertising channel performance table with a Google Ads campaign performance view sourced from `ads_campaign_stats`
- [x] 6.3 Replace the mock call performance line chart with a weekly trend derived from `vw_callrail_leads` grouped by `call_started_at`
- [x] 6.4 Replace the mock funnel chart with stage funnel data from `vw_conversion_candidates` (booked → qualified → converted)
- [x] 6.5 Replace mock header KPI cards with live aggregates: total leads (CallRail count), qualified rate (qualified / booked from conversion pipeline), total ad spend (`ads_campaign_stats` sum), and Google Ads attribution rate (from cached upload analytics once available, placeholder until then)
- [x] 6.6 Add upload analytics section to `MarketingPage`: platform health badge, per-action upload health, `action alive` status, and config drift alert — rendered from cached snapshot data

## 7. Verification

- [x] 7.1 Verify the migration and analytics sync function locally against the local Supabase stack
- [x] 7.2 Verify a successful sync writes all expected analytics slices to storage
- [ ] 7.3 Verify partial Google Ads query failure still preserves successful slices and records the failure state
- [ ] 7.4 Verify GCLID checks reject unsupported requests and return explicit no-match diagnostics when Google Ads returns zero rows
- [ ] 7.5 Verify `MarketingPage` reads cached analytics only and does not require live Google Ads queries to render
- [ ] 7.6 Verify `MarketingPage` sample-data imports are fully removed and all displayed values are sourced from Supabase
