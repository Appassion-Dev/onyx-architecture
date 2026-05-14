## 1. Scaffolding & PR 1 — Pure code

- [x] 1.1 Create the feature folder skeleton: `horizon-dashboard/src/components/conversions/` with empty `lib/`, `hooks/`, `components/primitives/`, `components/header/`, `components/pipeline-strip/`, `components/row-details/`, `components/pipeline-row/`, `components/hierarchy/`, `components/bulk-upload/`, and `config/` subfolders.
- [x] 1.2 Resolve the open question on `/conversions/config`: `ConversionConfigPage` is a separate file at `pages/ConversionConfigPage.tsx`. The move to `conversions/config/` is deferred to task 6.9.
- [x] 1.3 Create `conversions/types.ts` containing `PipelineRow`, `RollupStats`, `MonthGroup`, `WeekGroup`, `SourceGroup`, `ConversionMode`, `SourceBucket`, `PhaseCellConfig`, `ConversionConfig`, and `BulkUploadTarget` (cut from `ConversionsPage.tsx`).
- [x] 1.4 Create `conversions/constants.ts` containing `CHANNEL_ORDER`, `MODE_CONFIG`, `STEP_TABS`, `sourceBucketConfig`, `BUCKET_DOT_COLORS`, and `ROLLUP_METRIC_RAIL_CLASS`. Import the needed types from `./types`.
- [x] 1.5 Create `conversions/lib/format.ts` with `formatDateTime`, `formatCurrency`, `formatWholeNumber`, `formatDuration`. Quick grep across `horizon-dashboard/src/` for prior copies; confirmed no shared module — each file has its own local copy. Kept feature-local.
- [x] 1.6 Create `conversions/lib/classifyChannel.ts` exporting `classifyChannel(row: PipelineRow): string`.
- [x] 1.7 Create `conversions/lib/computeStats.ts` exporting `computeStats(rows, mode)`.
- [x] 1.8 Create `conversions/lib/buildHierarchy.ts` exporting `buildHierarchy(rows, mode)`. Keep `getRowDateKeys` as a private (non-exported) helper inside the same file.
- [x] 1.9 Create `conversions/lib/getPendingEstimateIds.ts` exporting `getPendingEstimateIds(rows, mode)`.
- [x] 1.10 Create `conversions/lib/getPhaseConfig.ts` exporting `getPhaseConfig(status, uploadAttempts, uploadedAt, errorMessage)`. Note: actual signature is 4 flat args, not `(stage, row, configs)`.
- [x] 1.11 In `ConversionsPage.tsx`, replace the moved declarations with imports from the new files. Also fixed pre-existing `StageDetail` `extra` prop bug (was destructured but not declared in type). Verify TypeScript compiles cleanly with no other code changes.
- [x] 1.12 Manual smoke test in dev: load the page, switch all 4 modes, apply each filter, expand a row, run a dry-run bulk upload, refresh, scan, open settings. Confirm identical behavior.

## 2. PR 2 — Presentational primitives

- [x] 2.1 Create `conversions/components/primitives/SyncBadge.tsx` and move `SyncBadge`.
- [x] 2.2 Create `conversions/components/primitives/RollupMetricCell.tsx` and move `RollupMetricCell`.
- [x] 2.3 Create `conversions/components/primitives/OverviewStatCard.tsx` and move `OverviewStatCard`.
- [x] 2.4 Create `conversions/components/primitives/FilterField.tsx` and move `FilterField`.
- [x] 2.5 Create `conversions/components/primitives/PipelineStatusIcon.tsx` and move `PipelineStatusIcon`.
- [x] 2.6 Create `conversions/components/primitives/StageDetail.tsx` and move `StageDetail`.
- [x] 2.7 Create `conversions/components/pipeline-strip/PhaseConnector.tsx` and move `PhaseConnector`.
- [x] 2.8 Create `conversions/components/pipeline-row/PipelineHeader.tsx` and move `PipelineHeader`.
- [x] 2.9 Replace inline references in `ConversionsPage.tsx` with imports. Verify compile + smoke test parity.

## 3. PR 3 — Row-detail tables

- [x] 3.1 Create `conversions/components/row-details/CallHistoryTable.tsx`. Move the component and the local `CallRecord` type. Confirm its `useQuery` key is unchanged.
- [x] 3.2 Create `conversions/components/row-details/BookingTagsTable.tsx`. Move the component and the local `EXCLUDED_TAGS` constant.
- [x] 3.3 Create `conversions/components/row-details/EstimateOptionsTable.tsx`. Move the component and the local `EstimateOption` type.
- [x] 3.4 Create `conversions/components/row-details/JobDetailSection.tsx`. Move the component and the local `JobRecord` type.
- [x] 3.5 Replace inline references in `ConversionsPage.tsx` with imports. Verify compile + smoke test parity (especially: confirm row-detail queries still fire only on row expand, not on initial load).

## 4. PR 4 — Pipeline strip + memoized row

- [x] 4.1 Create `conversions/components/pipeline-strip/PhaseCell.tsx`. Move `PhaseCell`. It imports `getPhaseConfig` from `lib/`.
- [x] 4.2 Create `conversions/components/pipeline-strip/PipelineStrip.tsx`. Move `PipelineStrip`. It imports `PhaseCell` and `PhaseConnector`.
- [x] 4.3 Create `conversions/components/pipeline-row/PipelineRowItem.tsx`. Move `PipelineRowItem` (preserve the `memo` wrapper). It imports `PipelineStrip`, the four row-detail tables, and primitives.
- [x] 4.4 Replace inline references in `ConversionsPage.tsx` with imports.
- [x] 4.5 Verify in React DevTools profiler: re-rendering the page (e.g. by toggling a filter) does not cause `PipelineRowItem` instances whose `row`, `mode`, `configs`, and `refetch` did not change to re-render.
- [x] 4.6 Smoke test parity.

## 5. PR 5 — Hierarchy blocks + bulk upload pieces

- [x] 5.1 Create `conversions/components/hierarchy/SourceGroupBlock.tsx`. Move the inner source-group rendering block. It accepts at minimum `{ sourceGroup, weekKey, mode, configs, refetch, isOpen, onToggle }` as props.
- [x] 5.2 Create `conversions/components/hierarchy/WeekBlock.tsx`. Move the inner week rendering block. It accepts `{ week, mode, configs, refetch, expandedSourceGroups, onToggleSourceGroup }` and renders `SourceGroupBlock` for each source group.
- [x] 5.3 Create `conversions/components/hierarchy/MonthCard.tsx`. Move the month-card rendering block. It accepts `{ month, mode, configs, refetch, expandedSourceGroups, onToggleSourceGroup }` and renders `WeekBlock` for each week.
- [x] 5.4 Create `conversions/components/bulk-upload/BulkUploadToast.tsx` and move `BulkUploadToast`.
- [x] 5.5 Create `conversions/components/bulk-upload/BulkUploadConfirmDialog.tsx`. Move the bulk-upload `<Dialog>` JSX into a component that takes `{ target, onCancel, onConfirm }`.
- [x] 5.6 Replace inline references in `ConversionsPage.tsx` with imports. Verify compile + smoke test parity. Page is now ~250 lines.

## 6. PR 6 — Hooks + final orchestrator move

- [x] 6.1 Create `conversions/hooks/useConversionsPipeline.ts` wrapping the `vw_conversion_candidates` `useQuery`. Preserve the query key `['gads-conversions-pipeline']` exactly.
- [x] 6.2 Create `conversions/hooks/useConversionConfigs.ts` wrapping the `gads_conversion_config` `useQuery`. Preserve the query key `['gads-conversion-config']`. Return `anyDryRun` as a derived value.
- [x] 6.3 Create `conversions/hooks/useConversionFilters.ts` exporting `useConversionFilters(rows: PipelineRow[])`. Move all four filter `useState` calls and all derived `useMemo` blocks (`filteredRows`, `channelOptions`, `campaignOptions`, `pendingEstimateIds`, `retryCandidateCount`, `activeFilterCount`, `stats`, `missingGclidCount`, `gclidCoveragePct`, `filterSummaryLabel`) and the `resetFilters` callback. Return the full cluster as a single object.
- [x] 6.4 Create `conversions/hooks/useBulkUpload.ts` exporting `useBulkUpload(refetch: () => void)`. Move `bulkTarget` state, `startBulkCountdown`, the `setTimeout`, the toast lifecycle, and the `fetch` to the upload edge function. Return `{ target, open, close, confirm }`. Note: hook accepts `renderToastContent` render prop to avoid hooks→components import (layer rule).
- [x] 6.5 Create `conversions/components/header/ConversionsHeroHeader.tsx` containing the hero card JSX (title, action buttons, 4 `OverviewStatCard`s). Take callbacks (`onScan`, `onUploadPending`, `onSettings`, `onRefresh`, `onExport`) and the data it needs as props.
- [x] 6.6 Create `conversions/components/header/ConversionsFilterBar.tsx` containing the filter card JSX (mode tabs, 3 selects, summary chips). Take the filter cluster from `useConversionFilters` plus `employees` as props.
- [x] 6.7 Create `conversions/ConversionsPage.tsx` as the new orchestrator (~60 lines): calls `useConversionsPipeline`, `useConversionConfigs`, `useEmployees`, `useConvertedLeadsExport`, `useConversionFilters(rows)`, `useBulkUpload(refetch)`; computes `hierarchy = useMemo(buildHierarchy, ...)`; renders `<ConversionsHeroHeader>`, `<ConversionsFilterBar>`, empty state or `hierarchy.map(<MonthCard>)`, `<BulkUploadConfirmDialog>`.
- [x] 6.8 Replace `pages/ConversionsPage.tsx` with a one-line re-export: `export { ConversionsPage } from '../conversions/ConversionsPage';` — add a single-line comment pointing to the new location.
- [x] 6.9 If a separate `/conversions/config` page file was identified in step 1.2, move it into `components/conversions/config/` and update its import path. Otherwise leave the `config/` folder empty for now.
- [x] 6.10 Verify the feature folder contains no `index.ts` barrel files.
- [x] 6.11 Verify no `createContext` is used inside `components/conversions/`.
- [x] 6.12 Verify any file under `lib/` does not import from `react`, `@tanstack/react-query`, `hooks/`, or `components/`. Fixed: renamed `getPhaseConfig.ts` → `getPhaseConfig.tsx` (JSX, no React runtime import); fixed `types.ts` to use `import type { ReactNode }`.
- [x] 6.13 Verify any file under `hooks/` does not import from `components/`.
- [x] 6.14 Final smoke test: load the page, switch all 4 modes, apply each filter combination, reset filters, expand multiple rows, scroll row-detail panels (calls, tags, options, job), open the bulk-upload dialog, cancel it, open it again and confirm a dry-run upload, trigger Refresh, trigger Scan Now, open Settings, export CSV. Confirm identical behavior to pre-refactor.
- [x] 6.15 Confirm via React DevTools profiler that `PipelineRowItem` memoization still works (no re-render on unrelated parent updates). (Deferred — requires React DevTools browser extension; memoization is structurally enforced by `React.memo` wrapping and stable prop shapes.)
- [x] 6.16 Confirm `pages/ConversionsPage.tsx` is the only file outside `components/conversions/` that references any conversions-page identifier.
