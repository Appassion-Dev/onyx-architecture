## 1. Database Migration

- [x] 1.1 Create migration `20260504000002_gads_conversion_datetime_type.sql` — `ALTER TABLE gads_conversion_uploads ALTER COLUMN conversion_datetime TYPE timestamptz USING conversion_datetime::timestamptz`
- [x] 1.2 In the same migration, `CREATE OR REPLACE FUNCTION discover_pending_conversions()` removing all three `::text` casts on `p.conversion_datetime` in the booking, qualified, and converted lead insert blocks
- [x] 1.3 Apply migration locally with `supabase migration up` and verify with `\d gads_conversion_uploads` that the column shows `timestamptz`

## 2. Status Constraint

- [x] 2.1 Confirm migration `20260504000001_gads_add_expired_status.sql` (already created) is applied — `'expired'` must be in the status CHECK constraint before the edge function sets it

## 3. Verification

- [x] 3.1 Run the diagnostic query confirming date comparison works without `::timestamptz` cast: `SELECT COUNT(*) FROM gads_conversion_uploads WHERE status = 'pending' AND conversion_datetime >= NOW() - INTERVAL '90 days'`
- [x] 3.2 Trigger `discover_pending_conversions()` locally and confirm rows are inserted with correct `timestamptz` values (not text)
- [x] 3.3 Invoke the edge function locally and confirm the 90-day filter log line appears with correct counts

## 4. Production Deployment

- [ ] 4.1 Apply both migrations to production via the Supabase Dashboard SQL editor in order: `20260504000001` then `20260504000002`
- [x] 4.2 Deploy the already-updated edge function (`google-ads-conversion-upload`) which is already live with the 90-day filter and contact data limit fix
- [ ] 4.3 Confirm first post-migration cron run logs `expired N rows outside 90-day window` and processes the remaining rows correctly
