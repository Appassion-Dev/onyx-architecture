## 1. Database Migration

- [x] 1.1 Create migration file `supabase/migrations/20260422000002_enrich_conversion_candidates.sql`
- [x] 1.2 Extend `call_agg` lateral to also aggregate `ARRAY_AGG(DISTINCT cl.campaign)` as `callrail_campaigns`, `ARRAY_AGG(DISTINCT cl.gclid)` as `callrail_gclids`, and `MIN(cl.call_started_at)` as `first_call_at`
- [x] 1.3 Add `assign_agg` lateral joining `estimates_settings → employees` to produce `assigned_employee_id` and `assigned_employee_name`
- [x] 1.4 Add `form_gclid_agg` lateral aggregating `ARRAY_AGG(DISTINCT bt.value)` from `booking_tags` where `key = 'gclid'`
- [x] 1.5 Add `all_gclids` computed column: `ARRAY_AGG(DISTINCT g ORDER BY g) FROM UNNEST(COALESCE(form_gclid_agg.booking_gclids, '{}') || COALESCE(call_agg.callrail_gclids, '{}')) g WHERE g IS NOT NULL`
- [x] 1.6 Add `first_touch_medium` computed column using CASE logic comparing `is_booking_form`, `call_count`, and `first_call_at` vs `e.created_at`
- [x] 1.7 Verify migration: drop old view, create new view, re-grant SELECT to `authenticated` and `service_role`

## 2. Frontend — Type & Query Updates

- [x] 2.1 Extend `PipelineRow` interface in `ConversionsPage.tsx` with: `callrail_campaigns: string[] | null`, `all_gclids: string[] | null`, `assigned_employee_id: string | null`, `assigned_employee_name: string | null`, `first_touch_medium: string | null`
- [x] 2.2 Confirm `vw_conversion_candidates` query uses `select('*')` (already does) — new columns automatically included

## 3. Filter Bar

- [x] 3.1 Add filter state to `ConversionsPage`: `stepFilter`, `sourceFilter`, `mediumFilter`, `campaignFilter`, `assigneeFilter` (all defaulting to `'all'`)
- [x] 3.2 Compute dynamic source options via `useMemo`: collect all distinct non-null values from `rows.flatMap(r => r.callrail_sources ?? [])`
- [x] 3.3 Compute dynamic campaign options via `useMemo`: collect all distinct non-null values from `rows.flatMap(r => r.callrail_campaigns ?? [])`
- [x] 3.4 Import `useEmployees` from `@/lib/hooks/useEmployees` and `EmployeeBadge` from `@/components/ui/employee-badge`
- [x] 3.5 Implement `filteredRows` via `useMemo` applying all five active filters with AND logic to `rows`
- [x] 3.6 Render filter bar between the page header and the month hierarchy — five `<Select>` dropdowns in a horizontal row, each with an "All" default option
- [x] 3.7 Step dropdown: options "All", "Pre-discovery", "Has Booking", "Has Qualified", "Has Converted", "Closed"
- [x] 3.8 Source dropdown: dynamic options from step 3.2
- [x] 3.9 Medium dropdown: options "All", "Form", "Call"
- [x] 3.10 Campaign dropdown: dynamic options from step 3.3
- [x] 3.11 Assignee dropdown: options "All", "Unassigned", then one entry per employee from `useEmployees()` rendered with `EmployeeBadge`
- [x] 3.12 Pass `filteredRows` (not `rows`) into `buildHierarchy`; update subtitle count to show `filteredRows.length`

## 4. GCLID Count Badge

- [x] 4.1 Import `Tooltip`, `TooltipContent`, `TooltipProvider`, `TooltipTrigger` from `@/components/ui/tooltip` (if not already imported)
- [x] 4.2 In the source badge section of `PipelineRowItem`, after existing badges, add conditional render: if `row.all_gclids?.length > 0` render the GCLID badge
- [x] 4.3 Render badge as `<span>GCLID ×{row.all_gclids.length}</span>` styled like the "Ad" badge on the Calls page (`bg-[#4318ff]/10 text-[#4318ff] border-[#4318ff]/20`)
- [x] 4.4 Wrap badge in `<TooltipProvider>` / `<Tooltip>` with `<TooltipContent>` listing each GCLID value in a `<p className="font-mono text-xs">` per entry

## 6. Show Zero Values Filter

- [x] 6.1 Import `Checkbox` from `@/components/ui/checkbox` in `ConversionsPage.tsx`
- [x] 6.2 Add `showZeroValues` boolean state (default `false`) to `ConversionsPage`
- [x] 6.3 Add zero-value filter logic to `filteredRows` `useMemo`: when `showZeroValues` is false, exclude rows where `display_value` is NULL, 0, or negative
- [x] 6.4 Render a "Show zero values" `<Checkbox>` + label in the filter bar, to the right of the existing dropdowns

## 5. Qualified Lead Detail Enrichment

- [x] 5.1 In `EstimateOptionsTable`, add `ExternalLink` icon import from `lucide-react`
- [x] 5.2 Add a fourth column to the options table header: "Link" (or visually just the icon)
- [x] 5.3 In each option row, add a `<td>` containing `<a href="https://pro.housecallpro.com/app/estimates/{opt.id}" target="_blank" rel="noopener noreferrer"><ExternalLink className="h-3.5 w-3.5 text-[#a3aed0] hover:text-[#4318ff]" /></a>`
- [x] 5.4 In the `PipelineRowItem` Qualified Lead section (the div wrapping `<StageDetail label="Qualified Lead">`), read `row.assigned_employee_id` and `row.assigned_employee_name`
- [x] 5.5 Resolve employee color: `useEmployees()` data → find by id → `color_hex` → `#${color_hex}`
- [x] 5.6 Render assignee row between `StageDetail` and `EstimateOptionsTable`: `<span>Assigned:</span> <EmployeeBadge name={name} color={color} />` — only when `assigned_employee_name` is non-null
