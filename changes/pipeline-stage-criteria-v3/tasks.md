## 1. Rewrite Discovery Functions

- [x] 1.1 Create migration that replaces `get_pending_booking_lead_conversions()` with broadened criteria: `is_booking_form = true` OR `booking_tags` exists OR `callrail_leads` correlated OR `lead_source IS NOT NULL`. Value = NULL, datetime = `estimates.created_at`, GCLID = `COALESCE(booking_tags.gclid, callrail_leads.gclid)`.
- [x] 1.2 Replace `get_pending_qualified_lead_conversions()` in the same migration: gate = any `estimate_options.total_amount IS NOT NULL`. Value = SUM of approved/pro-approved options / 100.0, datetime = `estimates.updated_at`, GCLID = same COALESCE pattern.
- [x] 1.3 Replace `get_pending_converted_lead_conversions()` in the same migration: gate = any `estimate_options.approval_status IN ('approved', 'pro approved')`. Value = SUM of approved/pro-approved options / 100.0, datetime = `MAX(estimate_options.updated_at)` where approved, GCLID = same COALESCE pattern. Remove all joins to the `jobs` table.

## 2. Update Pipeline View

- [x] 2.1 Create migration that replaces `vw_gads_conversion_pipeline` to reflect the new stage criteria, value calculations, and datetime sources. Remove any `jobs` table references. Ensure one row per estimate with LATERAL subqueries for each stage.

## 3. Validate

- [x] 3.1 Run discovery functions against local database and verify pending rows match new criteria (spot-check booking leads include phone/GLS sources, qualified leads include quoted-but-unapproved estimates, converted leads include approved estimates without requiring job completion).
- [x] 3.2 Query the updated pipeline view and verify no row duplication, correct value calculations, and correct datetime values.
