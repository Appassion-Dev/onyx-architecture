## Context

`ConversionsPage.tsx` renders an expandable detail panel for each row. Today the panel conditionally renders the Booking Lead and Qualified Lead sections behind `row.booking_status != null` and `row.qualified_status != null` guards respectively. This was correct when the view only returned discovered estimates — every visible row was guaranteed to have at least one non-null stage status.

After `conversions-unified-view` lands, pre-discovery estimates appear in the table with all three stage statuses as `null`. When a user expands one of these rows the panel shows only the Converted Lead placeholder and the Job section — suppressing the `BookingTagsTable`, `CallHistoryTable`, and `EstimateOptionsTable` that would tell the operator why this estimate is (or isn't) ad-attributed.

`StageDetail` currently has `status: string` in its props — it doesn't accept `null`.

## Goals / Non-Goals

**Goals:**
- All three stage sections render for every expanded row, regardless of discovery state
- `StageDetail` handles `null` status gracefully with a neutral "Not discovered" display
- Existing empty states in `BookingTagsTable`, `CallHistoryTable`, `EstimateOptionsTable`, and `JobDetailSection` are preserved and surfaced for pre-discovery rows
- A single consolidated empty-state message covers the case where a Booking Lead section has no form and no calls

**Non-Goals:**
- Changing the actual discovery logic or triggering discovery from within the expanded panel (the existing `PhaseCell` click-to-discover in the pipeline strip handles that)
- Pagination or lazy loading of the expanded subtables
- Any DB or API changes

## Decisions

### Decision 1: Remove gates, not add overrides

**Chosen**: Delete the two `{row.booking_status != null && (...)}` and `{row.qualified_status != null && (...)}` conditionals entirely. The sections always render.

**Alternative considered**: Keep the gates but add a separate "pre-discovery view" block beneath. Rejected: duplicates JSX, harder to maintain, creates two divergent code paths for what is fundamentally the same section.

### Decision 2: `StageDetail` accepts `status: string | null`

**Chosen**: Loosen the `status` prop type to `string | null`. When `null`, render:
- No icon (or a neutral `—` placeholder)
- Label text unchanged (e.g., "Booking Lead")
- Status line shows "Not discovered" in muted text
- All other fields (GCLID, value, date) suppressed since they're meaningless without a status

**Alternative considered**: Create a separate `StageDetailEmpty` component. Rejected: `StageDetail` is already parameterized — adding one null branch is simpler than a parallel component.

### Decision 3: Booking Lead empty state when both subtables are empty

**Chosen**: When `booking_status` is null AND `has_form` is false AND `call_count === 0`, show a single "No attribution data detected" line instead of the two consecutive "No form submission recorded" / "No calls recorded" messages that would otherwise stack.

**Rationale**: The two-message stack is fine for discovered estimates (you know what's present), but for a pre-discovery estimate it reads as redundant. A single neutral message is cleaner.

**For Qualified Lead**: `EstimateOptionsTable` already renders "No estimate options found" on its own — no change needed.

## Risks / Trade-offs

**[Risk] Expanded panel becomes longer** → Each row now always shows three stage sections. For estimates that are fully discovered and uploaded this is the same as today. For pre-discovery rows the panel grows by two sections. Acceptable: the sections are compact and the empty states are a single line.

**[Risk] `StageDetail` null path is untested today** → The component has never received `null` status. The null branch must be carefully rendered to avoid crashes (e.g., `status.charAt(0)` would throw). The existing status-label derivation `status.charAt(0).toUpperCase() + status.slice(1)` must be guarded.

## Migration Plan

Frontend-only. No migration, no deployment coordination beyond landing after `conversions-unified-view`. Can technically be implemented before `conversions-unified-view` — pre-discovery rows simply never appear until that view lands.
