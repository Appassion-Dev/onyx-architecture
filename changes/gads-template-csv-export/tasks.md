## 1. Export module

- [x] 1.1 Export `entriesForType()` (and the `PayloadSliceRow` type) from `horizon-dashboard/src/components/conversions/components/pipeline-row/usePayloadSlices.ts` for reuse (no behavior change)
- [x] 1.2 Create `horizon-dashboard/src/components/conversions/lib/exportUploadsCsv.ts`: fetch `vw_gads_upload_payload_slices` by estimate-id chunks (≤200 ids per `.in()` query, sequential, concatenated), index results by `(estimate_id, conversion_type)`
- [x] 1.3 Implement row building per spec: Email/Phone from `PipelineRow`, Conversion Name from `configs` (fallback `conversion_type`), Conversion Time formatted `yyyy-MM-dd HH:mm:ss±HH:mm`, Value blank when null, Currency, gclid, `JSON Sent`/`JSON Echo` via `entriesForType()` compact-serialized, `Error` = narrowed `error_slice` else `error_message` else blank
- [x] 1.4 Implement CSV serialization with quote-doubling and Blob anchor-click download (same pattern as the legacy hook); filenames `gads-conversions-<weekKey>.csv` / `gads-conversions-90d.csv`
- [x] 1.5 Unit tests for `exportUploadsCsv` row building: pending row (blank JSON columns), error precedence (`error_slice` over `error_message`), null value/gclid blanks, name fallback, CSV escaping of JSON cells

## 2. Month-level and week-level export

- [x] 2.1 Add scope collection working on either `MonthGroup` or `WeekGroup`: `all` mode → `(estimate_id, stage)` per the group's `events`; single-stage modes → per the group's `rows` with the active stage; build `rowsByEstimateId` from the same source
- [x] 2.2 Add download icon button to the week header in `WeekBlock.tsx` next to `weekLabel` (lucide `Download`, defensive `stopPropagation`, disabled/spinner while exporting); hidden when `conversionMode === 'pre-discovery'`
- [x] 2.3 Add download icon button to the month header in `MonthRow.tsx` next to `monthLabel`, same states; MUST `stopPropagation` on click and not trigger the header's expand/collapse (click or Enter/Space)
- [x] 2.4 Component tests: icons hidden in pre-discovery mode; week click in `converted` mode exports only converted rows for that week; month click exports the union of its weeks and does not toggle expansion (no jsdom in this repo — covered as `collectGroupScope` unit tests + static-markup icon-visibility tests)

## 3. Page-level export

- [x] 3.1 Replace `handleExportCsv` in `ConversionsPage.tsx`: build scope from the unfiltered `rows` (all estimates, all three conversion types), call the shared export with the 90-day filename; keep `isExporting` wiring to `ConversionsHeroHeader`
- [x] 3.2 Delete `horizon-dashboard/src/lib/hooks/useConvertedLeadsExport.ts` and remove all imports/references
- [x] 3.3 Test: page export includes all three conversion types regardless of active mode and ignores filter-bar state (`collectPageScope` unit test; page passes unfiltered `rows`)

## 4. Drop legacy RPC

- [x] 4.1 Confirm the live signature of `export_converted_leads` via `pg_get_functiondef` / catalog (migrations may drift from deployed DB) and verify no remaining callers (frontend grep + Supabase logs) — live signature is `(timestamptz, timestamptz)`, not `(date, date)`; zero frontend references remain
- [ ] 4.2 Add forward migration `DROP FUNCTION IF EXISTS public.export_converted_leads(...);` with the confirmed signature; apply to the project — migration file `20260611000001_drop_export_converted_leads_fn.sql` created, but NOT applied: Supabase MCP is in read-only mode; apply via `supabase db push` or re-run with write access

## 5. Verify & document

- [ ] 5.1 Manual verification on the dashboard: month and week icons in `all` and single-stage modes (month click does not collapse/expand), page button while a mode filter + filter bar are active, files open correctly in a spreadsheet with intact JSON cells
- [x] 5.2 Update the `full-stack-architecture` reference doc (`openspec/specs/full-stack-architecture/spec.md` line ~679): replace the `export_converted_leads` RPC section with the template-export description
- [x] 5.3 Run frontend test suite and typecheck; confirm no references to the removed hook/RPC remain (175/175 tests pass; `vite build` clean — repo has no tsc; grep clean)
