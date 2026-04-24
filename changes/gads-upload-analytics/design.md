## Context

The current Google Ads conversion system already has three relevant pieces: a staged offline conversion upload pipeline, a Google Ads spend sync function, and a small set of CLI-only verification helpers. What is missing is a durable analytics layer that turns Google Ads query results into cached ERP-facing data. Today, attribution checks and upload diagnostics require manual GAQL use or log inspection, and there is no daily snapshot that can drive a dashboard health badge, configuration drift alert, or attribution-rate trend.

This change crosses multiple surfaces: Supabase edge functions, pg_cron scheduling, database storage for snapshots, and dashboard read models. It also has an external API constraint: Google Ads `click_view` lookups must be scoped to a single day and are only valid within a 90-day window, so per-row GCLID verification cannot be designed as a bulk cron scan.

## Goals / Non-Goals

**Goals:**
- Collect daily Google Ads upload analytics for the configured offline conversion actions without requiring live Google Ads queries from the dashboard.
- Persist enough structured data to support attribution rate, platform health, action health, action alive checks, and config drift detection.
- Reuse the existing Google Ads OAuth credentials and shared GAQL helper patterns already present in the repo.
- Keep row-level GCLID verification available as an operator diagnostic that complies with current Google Ads `click_view` limits.

**Non-Goals:**
- Replacing or redesigning the existing `google-ads-conversion-upload` pipeline.
- Moving Google Ads analytics reads into the frontend.
- Running scheduled bulk `click_view` scans across historical GCLIDs.
- Treating GCLID verification as a source of truth for upload success; it remains a diagnostic aid.

## Decisions

### D1: Use a dedicated daily analytics sync function rather than extending an existing function

The analytics collector should be a separate edge function with its own daily cron schedule. The upload function mutates pipeline state every 15 minutes, and the existing `google-ads-sync` function is optimized for campaign spend sync rather than upload diagnostics. A dedicated sync keeps concerns separate, allows independent retries, and makes failure modes easier to observe.

**Alternative considered:** extend `google-ads-sync`. Rejected because campaign spend sync and upload analytics have different schedules, storage models, and operator expectations.

### D2: Store analytics as typed snapshot tables with raw summary payloads preserved in JSON

The collector should persist normalized daily attribution rows by conversion action and date, plus snapshot tables for client upload health, action upload health, and action configuration. For summary-style Google Ads resources that return nested `alerts` and `daily_summaries`, the raw payload should also be retained in `jsonb` columns so the system does not lose detail when Google changes enum or summary shapes.

**Alternative considered:** store only raw function responses in logs or a single JSON table. Rejected because the dashboard needs queryable analytics and stable comparison keys.

### D3: Scope analytics queries from `gads_conversion_config`

The daily collector should read enabled conversion types with non-null `conversion_action_id` values from `gads_conversion_config` and use only those action IDs in Google Ads queries. This keeps the analytics layer aligned with the upload pipeline and avoids mixing unrelated Google Ads actions into ERP metrics.

**Alternative considered:** query every `UPLOAD_CLICKS` action in the account. Rejected because it can include legacy or experimental actions that the pipeline does not upload against.

### D4: Treat `click_view` verification as an on-demand diagnostic, not a scheduled analytics input

The required GCLID verification query belongs in a separate operator-triggered path that requires an exact click date. The daily collector must not call `click_view`, because Google Ads documents that resource as a one-day, 90-day-limited lookup surface. Keeping it on demand prevents an unreliable cron design and avoids scanning unverifiable rows.

**Alternative considered:** daily verification for all recent GCLIDs. Rejected because it conflicts with the documented query limits and would generate false negatives whenever the exact click date is unknown.

### D5: Derive `action alive` and attribution rate from stored attribution snapshots plus local upload counts

The system does not need a separate Google Ads query for an `action is alive` check. The daily attribution snapshot already contains per-action conversion counts by date, so `alive in last 7 days` and `weekly attribution rate` should be computed inside Supabase using cached attribution rows and local upload counts.

**Alternative considered:** a second per-action metrics query just for “alive” status. Rejected as redundant and more expensive to maintain.

### D6: Persist partial success at the query-slice level

Each analytics run should persist successful slices even if one Google Ads resource fails. For example, a failed client summary fetch must not discard a valid attribution snapshot gathered in the same run. The run model should therefore record per-slice success or failure, plus the last successful fetch time for each analytics surface.

**Alternative considered:** all-or-nothing sync runs. Rejected because one transient Google Ads error would make the dashboard appear blind across all upload analytics.

## Risks / Trade-offs

- [Attribution counts are only meaningful if these action IDs are dedicated to the offline upload pipeline] -> Limit the collector to configured action IDs and document that reusing those actions for other sources will distort attribution rate.
- [Google Ads summary payloads can evolve in shape or enum values] -> Store raw `alerts` and `daily_summaries` payloads in `jsonb` alongside normalized fields.
- [Config drift alerts can become noisy during active setup changes] -> Compare the latest successful snapshot to the immediately previous successful snapshot and surface drift as stateful alerts instead of transient diffs.
- [GCLID verification can return no rows even when an upload was accepted] -> Treat verification as diagnostic only and require an exact click date from the operator.
- [A daily sync may miss near-real-time operator expectations] -> Keep the analytics layer daily by design and rely on upload logs for immediate troubleshooting.

## Migration Plan

1. Add Supabase tables or views for attribution snapshots, client upload health snapshots, action upload health snapshots, and action configuration snapshots.
2. Add a dedicated analytics sync edge function entry to `supabase/config.toml` and schedule it with a daily `pg_cron` job.
3. Implement the sync function using the existing Google Ads OAuth credentials and shared request helpers.
4. Backfill a small recent window of attribution data on first deploy so the dashboard is immediately useful.
5. Update the dashboard read path to use cached analytics snapshots and derived metrics.

**Rollback:** disable the new cron job and stop reading the new snapshot tables from the dashboard. Existing upload and spend-sync behavior remains unaffected.

## Open Questions

- Which dashboard surface should own the primary platform health badge and config drift alert: Conversions, Admin, or both?
- Should the first deployment backfill 14 days or 30 days of attribution snapshots?
- Should on-demand GCLID verification responses be cached for a short period, or always be live Google Ads reads?