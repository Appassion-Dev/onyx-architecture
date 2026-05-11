## Why

The discovery phase picks GCLIDs for qualified and converted leads using `ORDER BY first_seen_at ASC LIMIT 1` — deliberately choosing the *oldest* known click for a customer. This is correct for first-touch attribution, but it silently produces unuploadable rows when the oldest GCLID pre-dates the conversion event beyond the Google Ads `click_through_lookback_window_days` setting. Those rows never expire and never succeed: they accumulate retry counts indefinitely, are invisible to the existing 90-day recency expiry, and represent silent conversion data loss.

## What Changes

- **Discovery SQL** (`get_pending_qualified_lead_conversions`, `get_pending_converted_lead_conversions`): Add a `first_seen_at` window filter so only GCLIDs within the `click_through_lookback_window_days` of the conversion event are eligible for first-touch selection. When no GCLID falls within the window, the row is discovered with `gclid = NULL` and relies on enhanced conversions (hashed email/phone) for attribution.
- **Architecture spec** (`openspec/specs/full-stack-architecture/spec.md`): Update to document both Google Ads time-window constraints (upload recency + click lookback), their reference points, and the diagram showing how they relate. Also add a standing requirement that the architecture spec be updated whenever a pipeline feature is implemented.
- **Spec update** (`openspec/specs/customer-gclid-attribution/spec.md`): Add requirement that GCLID resolution applies the click lookback window filter relative to the conversion event timestamp.
- **Backfill / cleanup**: Identify and re-discover existing `pending` rows where the stored GCLID pre-dates `conversion_datetime` beyond the lookback window.

## Capabilities

### New Capabilities

_(none — this change tightens an existing capability, it does not introduce new ones)_

### Modified Capabilities

- `customer-gclid-attribution`: The GCLID resolution requirement changes — `first_seen_at ASC` selection must now be bounded by the lookback window (`first_seen_at >= conversion_datetime - INTERVAL '<N> days'`). This is a spec-level behavioral change, not just implementation detail.
- `full-stack-architecture`: Arch spec must be updated to document both Google Ads time constraints and to establish the norm that it is kept current after each feature implementation.

## Impact

**Code**
- `supabase/migrations/` — new migration replacing `get_pending_qualified_lead_conversions()` and `get_pending_converted_lead_conversions()` with lookback-windowed GCLID subqueries
- `supabase/migrations/` — optional one-time cleanup migration to re-discover or update pending rows with stale GCLIDs

**Specs**
- `openspec/specs/customer-gclid-attribution/spec.md` — new requirement + scenarios for windowed GCLID resolution
- `openspec/specs/full-stack-architecture/spec.md` — two-window diagram + arch-spec maintenance norm

**No changes to**
- Upload edge function (the recency window already handles Window 1 correctly)
- `gads_conversion_uploads` table schema
- Dashboard / UI
- `booking_lead` stage (uses per-estimate GCLID lookup, not `customer_gclids`)
