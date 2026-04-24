## Context

`ConversionConfigPage` (`horizon-dashboard/src/components/pages/ConversionConfigPage.tsx`) is a standalone React page at `/conversions/config` that reads and writes `gads_conversion_config` rows via the `gads-conversion-config` edge function. It is reached by navigating from `ConversionsPage` (`/conversions`).

Three bugs exist:

1. **No back button** — the page is a dead-end. Users must use the browser back button or sidebar.
2. **Empty fields on SPA navigation** — `ConversionsPage` uses the same React Query key (`['gads-conversion-config']`) but fetches only `conversion_type, enabled, dry_run` from the table directly. When the user navigates to `ConversionConfigPage`, React Query finds a cache hit with that partial shape. `ConversionConfigPage` renders the stale partial data (no `conversion_action_id` / `conversion_action_name`) before the background refetch completes — or the refetch may be suppressed by deduplication. Result: fields appear empty.
3. **All save buttons show loading** — a single `useMutation` instance is shared across all three config cards. `mutation.isPending` is one boolean, so all three Save buttons simultaneously show a spinner and become disabled whenever any one save is in flight.

## Goals / Non-Goals

**Goals:**
- Add a back button that navigates to `/conversions`
- Eliminate the empty-field flash by decoupling `ConversionConfigPage`'s query from the cache written by `ConversionsPage`
- Scope the save loading state to only the card that triggered the save

**Non-Goals:**
- Changing the edge function or database schema
- Refactoring `ConversionsPage`'s config query
- Optimistic updates or undo support

## Decisions

### Decision: Use a distinct React Query key for the full config query

**Chosen**: `['gads-conversion-config-full']` in `ConversionConfigPage`.

**Rationale**: The two pages fetch fundamentally different shapes from the same resource. Sharing a key means whichever query runs last wins, and the partial shape from `ConversionsPage` poisons the cache for `ConversionConfigPage`. Using a separate key gives each its own cache entry; the full-detail key is fetched fresh on every mount of `ConversionConfigPage`.

**Alternatives considered**:
- *Add `action_id`/`action_name` to `ConversionsPage`'s query* — unnecessary data fetched on a page that doesn't display it; not surgical.
- *Use `initialData` from the partial cache and always force a refetch* — more complex, still produces a flash since `initialData` is used synchronously.
- *Add `staleTime: 0` + `gcTime: 0`* — doesn't solve the shape mismatch; the partial data is still served before the refetch resolves.

### Decision: Track saving row with `savingType` state

**Chosen**: Replace `mutation.isPending` usage in button props with `savingType === cfg.conversion_type`, where `savingType: string | null` is component state set to the `conversion_type` being saved and cleared on mutation settle.

**Rationale**: The simplest correct model — one string that names the in-flight row. Cheaper than converting to per-row mutations or a mutation queue.

**Alternatives considered**:
- *One `useMutation` per row* — verbose, no meaningful benefit for a 3-row UI.
- *Track by index* — fragile if sort order changes.

### Decision: Back button placement

**Chosen**: Inline text link with `ArrowLeft` icon in the page header area, above the `<h1>`, navigating to `/conversions` via `useNavigate`.

**Rationale**: Consistent with how other detail-to-list navigation is handled in the dashboard (e.g., SalesAssignmentManagerPage). Avoids adding a breadcrumb system that doesn't exist elsewhere.

## Risks / Trade-offs

- **Cache duplication**: Two keys for the same table/endpoint means two cache entries that can drift. Acceptable — `ConversionsPage` only needs `enabled`/`dry_run` for the dry-run banner, and `ConversionConfigPage` invalidates `['gads-conversion-config-full']` after a PUT. `ConversionsPage` will pick up changes on its next mount/refetch naturally.
- **`savingType` desync on error**: If the mutation errors and `onError` doesn't clear `savingType`, the button stays disabled. Mitigation: clear `savingType` in both `onSuccess` and `onError` callbacks on the mutation's `onSettled`.

## Migration Plan

Frontend-only change. No migration needed. Deploy is a standard Vercel build push.

## Open Questions

*(none)*
