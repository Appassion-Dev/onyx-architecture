## 1. SQL: Fix Pipeline View

- [x] 1.1 Replace `LEFT JOIN callrail_leads` with `LEFT JOIN LATERAL (SELECT COUNT(*)::int AS call_count FROM callrail_leads WHERE estimate_id = e.id::varchar) call_agg ON true`
- [x] 1.2 Replace `LEFT JOIN estimate_options` with `LEFT JOIN LATERAL (SELECT COALESCE(SUM(total_amount), 0) AS total_amount FROM estimate_options WHERE estimate_id = e.id AND approval_status IN ('approved', 'pro approved')) eo_agg ON true`
- [x] 1.3 Update `display_value` to use `eo_agg.total_amount / 100.0` instead of `eo.total_amount / 100.0`
- [x] 1.4 Update `booking_source` to use `call_agg.call_count > 0` instead of `cl.callrail_id IS NOT NULL`
- [x] 1.5 Add `call_count` output column (`call_agg.call_count`)
- [x] 1.6 Verify or add `GRANT SELECT ON callrail_leads TO authenticated` for lazy-load queries
- [x] 1.7 Apply migration to local database and verify one row per estimate

## 2. Frontend: Data Layer Updates

- [x] 2.1 Add `call_count: number` to `PipelineRow` interface
- [x] 2.2 Create `useCallHistory(estimateId)` hook using TanStack Query to lazy-load callrail_leads records (enabled only when expanded and call_count > 0)

## 3. Frontend: Pipeline Phase Visuals

- [x] 3.1 Replace flat icon columns with connected pipeline strip component (`PipelineStrip`) showing 3 phase cells with connector lines
- [x] 3.2 Implement phase cell styling: green (uploaded), amber (pending), red (error), gray (skipped), outline (null) using Horizon theme tokens
- [x] 3.3 Add inline data beneath each phase cell (upload date, "Pending", or truncated error)
- [x] 3.4 Update `PipelineHeader` to match new pipeline strip layout

## 4. Frontend: Call Count Badge

- [x] 4.1 Update Source column to show call count badge (e.g., "Call (3)" or "Form" + call indicator)

## 5. Frontend: Call Detail Panel

- [x] 5.1 Create `CallHistoryTable` component rendering columns: Date, Type, Duration, Source, Lead Status, GCLID
- [x] 5.2 Implement duration formatting (seconds → m:ss)
- [x] 5.3 Handle form_submission event_type (Type = "Form", Duration = "—")
- [x] 5.4 Integrate `CallHistoryTable` into expanded detail panel below stage details, conditionally rendered when call_count > 0

## 6. Verify

- [x] 6.1 Confirm zero TypeScript errors
- [x] 6.2 Confirm no duplicate rows in pipeline view for estimates with multiple calls
