## 1. Database Migration

- [x] 1.1 Create migration `DROP VIEW IF EXISTS public.vw_gads_conversion_pipeline` and `CREATE VIEW public.vw_conversion_candidates` with: all estimates as the base (no gate filter), LEFT JOIN to `gads_conversion_uploads` pivoted for `booking_lead`, `qualified_lead`, `converted_lead`, LATERAL subquery for approved estimate options sum (`display_value`), LATERAL subquery for job context via `estimate_options → jobs` (most recent job, LIMIT 1), LEFT JOIN to `customers` for `customer_name`, LATERAL subquery for CallRail `call_count` and `callrail_sources`, source signal columns (`has_form`, `lead_source`), and `is_closed` boolean computed from stage states.
- [x] 1.2 Grant `SELECT` on `vw_conversion_candidates` to `authenticated` and `service_role`.
- [x] 1.3 Validate the view locally: confirm row count equals total estimates (no filter), confirm stage columns are NULL for undiscovered estimates, confirm `is_closed = false` for pre-discovery rows, confirm `is_closed = true` for fully-uploaded rows.

## 2. Frontend — Interface and Query

- [x] 2.1 In `ConversionsPage.tsx`, extend the `PipelineRow` interface to add `job_id: string | null`, `invoice_number: string | null`, `job_work_status: string | null`, `job_total: number | null`.
- [x] 2.2 Change the `useQuery` fetch from `.from('vw_gads_conversion_pipeline')` to `.from('vw_conversion_candidates')` and add `.gte('estimate_created_at', new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString())` to the query chain.

## 3. Validate

- [ ] 3.1 Load the dashboard locally and confirm pre-discovery estimates now appear with dashed `—` PhaseCell columns.
- [ ] 3.2 Confirm that estimates already in the pipeline continue to show their stage status, upload attempts, and GCLID correctly.
- [ ] 3.3 Confirm that estimates with jobs show the job fields (spot-check at least one estimate with a known job).
- [ ] 3.4 Confirm that the 90-day filter is applied: estimates older than 90 days do not appear in the dashboard.
