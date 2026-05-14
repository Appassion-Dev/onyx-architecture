## Why

`horizon-dashboard/src/components/pages/ConversionsPage.tsx` has grown to **2,040 lines / ~92 KB** in a single file. It bundles ~25 inline components, ~10 pure helpers, 4 row-detail data widgets (each with their own `useQuery`), 5 pieces of page state, and ~470 lines of JSX. The next planned wave of work — changing the table structure, swapping/extending hooks, and adding new pipeline stages — is blocked by this monolith: every change forces a scroll through the whole file, makes diffs noisy, and risks unrelated regressions because pure functions, presentational atoms, and orchestrator state share one module. Refactoring now (before the functional changes) keeps the behavioral PRs small, reviewable, and bisectable.

## What Changes

This change is a **pure structural refactor** — no behavior change, no spec-level requirement change to any existing capability, no new database/edge-function/network calls. It moves the existing internal seams of `ConversionsPage.tsx` onto disk as a small, extensible module under `src/components/conversions/`, and codifies the resulting structure as an architectural contract so future functional work has obvious extension points.

1. **Move all conversions-page code into a dedicated feature folder** at `horizon-dashboard/src/components/conversions/`, mirroring the pattern used by [horizon-dashboard/src/components/booking/](horizon-dashboard/src/components/booking/) (deeper structure with subfolders, `types.ts`, hooks). The `pages/ConversionsPage.tsx` file becomes a thin re-export of the orchestrator. The `/conversions/config` settings page stays inside the same feature folder (`conversions/config/`).
2. **Split into pure-logic / hooks / components layers**, in this order: shared `types.ts` and `constants.ts`; pure functions under `lib/` (`classifyChannel`, `computeStats`, `buildHierarchy`, `getPendingEstimateIds`, `getPhaseConfig`, format helpers); custom hooks under `hooks/` (data queries, filter cluster, bulk-upload flow); presentational primitives, hierarchy blocks, row, row-detail panels, and dialog under `components/`.
3. **Extract a `useConversionFilters(rows)` hook** that owns the entire filter cluster (mode + channel + campaign + assignee state, derived `filteredRows`, derived option lists, `activeFilterCount`, `resetFilters`). This is the main extension point for future filter additions — adding a new filter dimension becomes a single-file change.
4. **Extract a `useBulkUpload(refetch)` hook** that owns the dialog-target state, the 5-second cancellable countdown, the toast lifecycle, and the upload `fetch` call. New upload modes plug in here.
5. **Extract a `useConversionsPipeline()` hook and a `useConversionConfigs()` hook** wrapping the two `useQuery` calls. The pipeline-rows query is the single point that future table-structure changes (different view, different filter pushdown, paging) will touch.
6. **Establish the row-rendering contract** via a `<MonthCard> → <WeekBlock> → <SourceGroupBlock> → <PipelineRowItem>` chain that takes `mode`, `configs`, and `refetch` as drilled props (no context). `PipelineRowItem` keeps its `memo` wrapper and stable prop identities.
7. **Establish the stage-rendering contract** via a `<PipelineStrip>` whose stage cells are driven by `getPhaseConfig(stage, row, configs)`. Adding a new pipeline stage becomes: extend `ConversionMode`, add a `MODE_CONFIG` entry, add a branch in `getPhaseConfig`, no other file edits required.
8. **Codify the resulting structure as a new `conversions-page-structure` capability** so the extension points (where to add a filter, where to add a stage, where to add a row-detail panel, where to add a row column) are documented requirements rather than tribal knowledge.

Out of scope for this change: any behavioral change to filters/upload/discovery/badges, any visual change, any test additions (per user request — no tests in this PR), any consolidation of repeated CSS class strings into a `Surface` primitive (deferred).

## Capabilities

### New Capabilities
- `conversions-page-structure`: defines the file/module layout, extension points, and contracts (hook signatures, prop-drilling boundaries, stage configuration) for the Conversions page feature folder. This is an architectural capability — its requirements describe where code MUST live and which seams MUST exist for future functional work to plug in cleanly.

### Modified Capabilities
<!-- None. This is a pure structural refactor; no existing requirements change. The behavioral capabilities (`conversion-pipeline-ui`, `conversions-filter-bar`, `conversions-gclid-tag`, `bulk-upload-scoped`, `pipeline-phase-visuals`, etc.) keep their requirements unchanged. -->

## Impact

- **Affected code**: only [horizon-dashboard/src/components/pages/ConversionsPage.tsx](horizon-dashboard/src/components/pages/ConversionsPage.tsx). A grep confirmed none of the helpers (`classifyChannel`, `computeStats`, `buildHierarchy`, `getPendingEstimateIds`, `getPhaseConfig`, `MODE_CONFIG`, `sourceBucketConfig`, `BUCKET_DOT_COLORS`, `PipelineRow`, `ConversionMode`) are imported by any other file. Extraction is purely internal.
- **New folder**: `horizon-dashboard/src/components/conversions/` containing ~25 small files (`types.ts`, `constants.ts`, `lib/*.ts`, `hooks/*.ts`, `components/**/*.tsx`).
- **Existing route**: `pages/ConversionsPage.tsx` remains as a thin re-export so the router import path is unchanged.
- **Config page**: any `/conversions/config` page (currently navigated to via `navigate('/conversions/config')`) lives under `conversions/config/` in the new layout, keeping all conversions UI co-located.
- **APIs / database / edge functions**: no change.
- **Dependencies**: no new packages.
- **Tests**: none added or removed in this change (per user request). The refactor is verified by manual smoke testing and TypeScript compilation; once the structural seams are in place, future PRs can add unit tests on the now-isolated pure functions.
- **Backwards compatibility**: page behavior, props, public route, query keys (`'gads-conversions-pipeline'`, `'gads-conversion-config'`), and Supabase calls are unchanged. The `PipelineRowItem` memoization contract is preserved (stable `configs` and `refetch` references from the same hooks).
- **Risk**: medium-low. The seams already exist inside the file; the work is mechanical move-and-import. Main risks are (a) breaking `memo` by passing freshly-allocated props through a new layer, and (b) circular imports between `types.ts` and `constants.ts` — both addressed in `design.md`.
