## Context

The Google Ads conversion upload pipeline has two paths: a legacy UI-driven path (`gads-upload-booking` edge function, called directly from `OnlineBookingsPage` and `CallsPage`) and a config-driven batch path (`google-ads-conversion-upload` edge function, called by pg_cron every 15 minutes). The legacy path reads a single `GOOGLE_ADS_CONVERSION_ACTION_ID` env var and ignores `gads_conversion_config` entirely — meaning `enabled`, `dry_run`, and per-stage action IDs are bypassed. The ConversionsPage exists and shows per-stage status (booking/qualified/converted) via `PipelineStrip` / `PhaseCell` but has no upload interactivity.

## Goals / Non-Goals

**Goals:**
- Remove all upload UI from `OnlineBookingsPage` and `CallsPage`
- Delete the `gads-upload-booking` edge function
- Add scoped upload params to `google-ads-conversion-upload` so the UI can trigger single-cell and per-bucket uploads without a new function
- Add `discover_pending_conversions_for_estimate()` DB function for on-demand per-estimate discovery
- Make `PhaseCell` interactive: hover reveals action, click starts a 5s countdown, expiry calls the upload
- Add week/month bulk upload buttons: Dialog confirm → countdown toast → scoped upload

**Non-Goals:**
- Redesigning the Conversions page layout or hierarchy
- Changing how cron-triggered uploads work (batch path stays untouched)
- Adding real-time push notifications for upload completion
- Exposing upload history or audit log in the UI (future feature)

## Decisions

### D1: Extend `google-ads-conversion-upload` rather than creating a new function

The batch function already implements config lookup, `dry_run` handling, enhanced conversion hashing, partial failure handling, and audit writes. A new function would duplicate all of this.

**Extension**: Accept optional `estimate_ids: string[]` and `conversion_types: string[]` in the request body. If present, add `AND estimate_id = ANY(estimate_ids)` and/or `AND conversion_type = ANY(conversion_types)` to the pending-row query. Empty body = full batch (cron behavior unchanged).

**Alternative considered**: New `gads-upload-single` function — rejected because it would duplicate ~200 lines of upload/audit logic and create a second code path to maintain.

### D2: In-cell countdown uses `Progress` component, not SVG

The dashboard has a Radix-based `Progress` component with `bg-primary/20` track and `bg-primary` indicator using `transition-all`. For the 5s countdown we set `value={100}` on mount then transition to `value={0}` via `duration-[5000ms]`, which gives a smooth visual drain using existing CSS classes.

A `useEffect` with `setTimeout(5000)` triggers the upload when the countdown expires; a Cancel button calls `clearTimeout` and resets state.

**Alternative considered**: SVG `stroke-dashoffset` ring — rejected as it requires custom CSS not in the theme.

### D3: Bulk upload uses Dialog confirm modal + countdown toast

For single-cell upload the in-cell countdown is sufficient — the user sees exactly what they're confirming (one stage, one estimate). For week/month bulk the user needs to see the count and dry-run warning before committing.

Flow: `Dialog` (count + dry-run warning + Confirm/Cancel) → on Confirm, dismiss dialog, show `toast.custom()` with `Progress` bar draining from 100→0 over 5s with a Cancel button. Cancelling the toast dismisses it without uploading.

**Alternative considered**: Countdown toast only (no modal) — rejected for bulk because the stakes are higher and the count/dry-run info doesn't fit cleanly in the small toast.

### D4: Null PhaseCell triggers per-estimate discovery

`discover_pending_conversions` already exists as a SQL function but is global (all estimates). A new `discover_pending_conversions_for_estimate(p_estimate_id text)` adds `AND e.id = p_estimate_id` to each sub-query and is called via `supabase.rpc()` from the UI.

On success, the row is refetched — if a pending row was created the cell transitions from null/dashed to pending/yellow automatically.

### D5: Skipped stage cells are not clickable

`skipped` status means no gclid and no contact data — re-uploading would produce the same result. Clicking a skipped cell would be misleading. Display only, no interaction.

### D6: Motion design — precision over flair

This is an internal operations dashboard. The aesthetic target is **refined precision**: every animation communicates system state, not decoration. Guidelines:

**Countdown Progress bar**
- Easing: `ease-linear` (not Tailwind's default `ease-in-out`) — a countdown must feel like a clock. Variable-rate motion makes remaining time unreadable.
- Color: the indicator color matches the cell's status accent, not `--primary` (indigo):
  - Pending (first attempt): amber — use `style={{ '--tw-bg-opacity': 1 }}` override or inline `backgroundColor: '#ffb547'`
  - Error retry: red — `backgroundColor: '#ee5d50'` (matches `--destructive`)
  - This preserves the cell's visual language instead of jarring the user with an unrelated color.
- Track: `bg-[#e9edf7]` (matches the dashboard border/secondary color)

**Hover icon crossfade**
- The status icon (Clock, XCircle) and the upload icon (ArrowUpCircle or Upload) should crossfade, not hard-swap.
- Implementation: render both icons stacked with `absolute` positioning; outgoing icon transitions `opacity` 1→0, incoming transitions 0→1, both over `duration-150`.
- On hover exit, reverse the transition.

**Cell entering countdown mode**
- The cell border transitions from its status accent to `--primary` (indigo) over `duration-200` — a visual "arming" cue.
- The Cancel button fades in with `opacity-0 → opacity-100` + `translate-y-1 → translate-y-0` over `duration-150`.

**Upload success flash**
- After refetch resolves with `status === 'uploaded'`, the cell background briefly flashes `bg-[#01b574]/20` before settling to the standard `bg-[#e8fdf4]` green uploaded state.
- This is the only "high-impact moment" in the interaction and deserves the only non-instant transition in the whole flow.
- Use a 600ms `transition-colors` that settles naturally.

**Bulk countdown toast**
- Same Progress bar rules (linear, amber/cell-color indicator).
- The toast itself uses Sonner's default entry animation — do not override it.

## Risks / Trade-offs

- **Countdown cancellation race**: If the network call fires before cancel is processed (edge case in slow renders), cancel may arrive too late. Mitigation: guard with a cancelled ref checked before the fetch call.
- **Stale pending-row state**: After a user-triggered upload the page refetches, but if the upload is async (takes >1s) the cell may briefly show "pending" again. Mitigation: optimistic local state update to "uploading" spinner while request is in flight, then refetch.
- **Removing gads-upload-booking while it's still referenced in OnlineBookingsPage**: Must remove UI references and the function folder atomically — deploy order matters. UI changes should be deployed first (removing the call site) before the function folder is deleted from production.
- **gads_upload_status column in vw_booking_estimates**: This view field is no longer needed in the UI but the column may still exist in the view/table. Removing it from the UI is safe; the view can be cleaned up separately.

## Migration Plan

1. Deploy `google-ads-conversion-upload` update (adds optional body params — backward compatible, cron call with `{}` still works).
2. Apply Supabase migration for `discover_pending_conversions_for_estimate()`.
3. Deploy dashboard changes: remove upload UI from `OnlineBookingsPage` and `CallsPage`; add interactive upload to `ConversionsPage`.
4. Delete `supabase/functions/gads-upload-booking/` folder (no longer called).
5. Optionally clean up `gads_upload_status` from the bookings view (cosmetic — no functional impact).

**Rollback**: Steps 1–3 are independently safe. If the ConversionsPage upload fails, the cron path continues to upload everything automatically. No data loss risk.
