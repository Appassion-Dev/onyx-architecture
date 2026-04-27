## Why

The dashboard can currently show local conversion upload rows and cached Google Ads health payloads, but it cannot answer the operational question the team actually asks every day: for a given day or week, how many uploads did we send, how many did Google mark successful, and how many did Google mark failed for each conversion event we care about. Without a grouped reconciliation view, operators have to mentally stitch together row-level Uploads data and raw `daily_summaries` payloads, which makes trend checking, source comparisons, event-by-event review, and prior-period comparisons slow and error-prone.

## What Changes

- Add a reporting surface that groups local conversion uploads and cached Google Ads `daily_summaries` by the same calendar day so the dashboard can show uploaded counts alongside Google successful counts and failed counts for that date.
- Group the reporting surface first by conversion events defined in dashboard settings so today's seeded `booking`, `qualified`, and `converted` sections appear now and future configured actions extend the reporting catalog automatically without hardcoded tabs.
- Add weekly rollups that aggregate the same reconciliation data by week and show prior-period comparison alongside current-period totals.
- Add normalized lead-source buckets for reporting, starting with `form`, `calls`, `thumbtack`, and `other`, so daily and weekly totals can be segmented in a way operators can actually use without colliding with the top-level event names.
- Make the reporting surface explicit about reconciliation limits: Google daily summaries are aggregated by client/action/date, so the page shows bucket-level comparison rather than row-by-row proof of acceptance.
- Reuse stored local ledger rows and cached Google analytics payloads instead of requiring live Google Ads queries during dashboard page loads.
- Render active event sections only for enabled configured actions that have local or Google activity in the selected period, while still allowing one-sided local-only or Google-only rows within a rendered section.

## Capabilities

### New Capabilities
- `upload-reconciliation-reporting`: Daily and weekly reconciliation reporting that shows local upload totals alongside cached Google Ads successful and failed daily summary counts, including prior-period comparison and source-bucket segmentation.

### Modified Capabilities
<!-- Existing capabilities whose REQUIREMENTS are changing (not just implementation).
     Only list here if spec-level behavior changes. Each needs a delta spec file.
     Use existing spec names from openspec/specs/. Leave empty if no requirement changes. -->

## Impact

- `horizon-dashboard/src/components/pages/`: the Conversions area will need a reporting surface for grouped reconciliation, not just row-level upload operations and analytics panels.
- `supabase/migrations/` and/or reporting views: the dashboard will likely need a local aggregation source that aligns `gads_conversion_uploads` with cached Google `daily_summaries` at day and week grain.
- `gads_conversion_uploads`, `gads_client_upload_health`, and `gads_action_upload_health`: these stored datasets become the reporting inputs for uploaded totals, successful counts, failed counts, retry state, and period comparisons.
- Reporting normalization: the reporting layer will use enabled `gads_conversion_config` rows as the reporting catalog so local conversion types and Google conversion actions resolve into config-driven top-level event sections instead of a hardcoded list, while ignoring unmapped Google actions in the reporting page.
- Lead-source enrichment logic: reporting will need a stable classification layer that maps current source signals into operator-friendly buckets such as form, calls, thumbtack, and other.