## Why

The Google Ads offline conversion pipeline can upload rows and log acceptance, but it does not yet produce a cached analytics layer that answers the operational questions the ERP needs every day: whether Google credited uploaded conversions, whether upload health is degrading, whether action settings drifted, and whether a captured GCLID can be verified against Google click data. Without a dedicated change for this layer, the dashboard would depend on ad hoc GAQL checks and function logs instead of durable analytics snapshots.

## What Changes

- Add a daily Google Ads upload analytics collection flow that snapshots attribution metrics, upload-health summaries, and conversion-action configuration for the configured offline conversion actions.
- Add cached datasets that let the dashboard compute attribution rate from Google-recorded conversions versus Supabase upload counts without issuing live Google Ads queries on page load.
- Add platform-health and config-drift signals that can drive dashboard badges, alerts, and historical comparisons.
- Add an on-demand GCLID verification path for recent rows; document it in this change, but keep it out of the daily cron because Google Ads restricts `click_view` queries to a single day within a 90-day window.
- Document the required Google Ads queries for the feature set:

  1. Daily attribution by conversion action:

     ```sql
     SELECT
       conversion_action.id,
       conversion_action.name,
       metrics.all_conversions,
       metrics.all_conversions_value,
       segments.date
     FROM conversion_action
     WHERE conversion_action.id IN (<action IDs>)
       AND segments.date DURING LAST_14_DAYS
     ORDER BY conversion_action.id, segments.date
     ```

  2. Client-level offline upload health:

     ```sql
     SELECT
       offline_conversion_upload_client_summary.client,
       offline_conversion_upload_client_summary.status,
       offline_conversion_upload_client_summary.total_event_count,
       offline_conversion_upload_client_summary.successful_event_count,
       offline_conversion_upload_client_summary.alerts,
       offline_conversion_upload_client_summary.daily_summaries,
       offline_conversion_upload_client_summary.last_upload_date_time
     FROM offline_conversion_upload_client_summary
     ```

  3. Conversion-action-level offline upload health:

     ```sql
     SELECT
       offline_conversion_upload_conversion_action_summary.client,
       offline_conversion_upload_conversion_action_summary.conversion_action_id,
       offline_conversion_upload_conversion_action_summary.conversion_action_name,
       offline_conversion_upload_conversion_action_summary.daily_summaries,
       offline_conversion_upload_conversion_action_summary.alerts
     FROM offline_conversion_upload_conversion_action_summary
     ```

  4. Conversion action configuration snapshot:

     ```sql
     SELECT
       conversion_action.id,
       conversion_action.name,
       conversion_action.status,
       conversion_action.primary_for_goal,
       conversion_action.include_in_conversions_metric,
       conversion_action.counting_type,
       conversion_action.click_through_lookback_window_days
     FROM conversion_action
     WHERE conversion_action.id IN (<action IDs>)
     ```

  5. On-demand GCLID verification for a known click date:

     ```sql
     SELECT
       click_view.gclid,
       campaign.name,
       ad_group.name,
       click_view.keyword,
       click_view.keyword_info.text,
       segments.device,
       segments.date
     FROM click_view
     WHERE click_view.gclid = '<gclid>'
       AND segments.date = '<click date>'
     ```

- Document derived metrics that do not require separate Google Ads queries:
  - `action is alive` for the last 7 days derives from the daily attribution snapshot.
  - `weekly attribution rate` derives from Supabase upload counts plus the daily attribution snapshot.

## Capabilities

### New Capabilities
- `gads-upload-analytics`: Collect and cache Google Ads upload attribution, upload-health summaries, and conversion-action configuration so the dashboard can render reliable analytics and drift alerts from stored data.
- `gads-gclid-verification`: Verify a captured GCLID against Google Ads click data on demand using an exact click-date lookup that complies with current `click_view` query limits.

### Modified Capabilities
<!-- No existing capabilities to modify. -->

## Impact

- `supabase/functions/`: a new or extended Google Ads analytics collector will need to reuse the existing OAuth and GAQL helpers.
- `supabase/config.toml` and `supabase/migrations/`: the analytics collector will need explicit function config, storage tables/views, and a daily cron schedule.
- `horizon-dashboard/src/components/pages/`: conversions or admin surfaces will read cached analytics snapshots instead of live Google Ads data.
- Google Ads API usage: adds daily summary reads plus on-demand `click_view` diagnostics while avoiding unsupported bulk verification patterns.