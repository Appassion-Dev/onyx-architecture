## Context

`vw_conversion_candidates.channel` is the canonical resolved-channel column consumed by the Conversions page weekly rollup and the `vw_gads_upload_reconciliation_daily` view. Its priority chain (defined in `conversion-channel-grouping/spec.md`) ends in two CallRail-source branches:

```sql
-- Source pattern repeated across all CallRail branches:
WHEN EXISTS (
    SELECT 1 FROM unnest(COALESCE(call_agg.callrail_sources, ARRAY[]::text[])) src(value)
    WHERE LOWER(src.value) LIKE '%<keyword>%'
) THEN '<Channel>'::varchar
```

Branches exist for: `%thumbtack%`, `%google ads% / %adwords% / %paid search%`, `%local services% / %lsa%`, `%google my business% / %maps%`, `%organic% / %seo%`, `%direct%`. After the recent migration `20260522000001_vw_conversion_candidates_callrail_by_customer.sql`, `callrail_sources` is aggregated per **customer** (not per estimate), so repeat estimates inherit their customer's call history. The correlation key is no longer the bug.

The CallRail data itself encodes "the customer dialed a tracking number directly" in two places:
- `callrail_leads.source = 'Call forwarding'` (tracker-mode descriptor — 40 rows)
- `callrail_leads.medium = 'direct'` and/or `utm_medium = 'direct'` (structured attribution fields — also set on these rows)

The existing `%direct%` branch matches the literal `source = 'Direct'` value but not `'Call forwarding'`. Distribution of CallRail `(source, medium)` pairs in production confirms `'Call forwarding'` is the only material miss in the Direct bucket among CallRail rows that actually propagate through to the view; remaining gaps (`Van Wrap`, `Facebook Ads / paid-social`) are 3 and 1 source-level rows respectively and are out of scope here.

**Real-world impact sizing.** Of 40 `(source='Call forwarding', medium='direct')` rows in `callrail_leads`, only 1 has `customer_id` populated and produces estimates the view classifies (3 estimates / 1 customer). The other 39 carry CNAM-style values in `customer_name` ("TAMPA CENTRA FL", "WELLCARE", "ONSTAR OPERATIO", "WIRELESS CALLER", etc.) and phone numbers that match no customer at any point in time — call-tracking noise from spam, robocalls, and unidentified callers. The trigger correctly leaves them with `customer_id IS NULL`; they have no corresponding estimate in `vw_conversion_candidates` and no algorithmic improvement could attribute them. Therefore the affected-estimate population for this change is exactly **3 estimates / 1 customer**, not 40.

## Goals / Non-Goals

**Goals:**
- Classify CallRail leads with `source = 'Call forwarding'` as `channel = 'Direct'` in `vw_conversion_candidates`. Affected population: 3 estimates / 1 customer (the only Call-forwarding caller in `callrail_leads` whose phone matches a real customer record).
- Preserve every other branch's behavior, ordering, and precedence. Specifically, ensure `'Google Local Services / direct'` and `'GLS (Google Local Services) / direct'` still resolve to GLS via the earlier `%local services% / %lsa%` branch.
- Keep the change idiomatic — the new branch should look like every other CallRail-source branch in the CASE (substring `LIKE` on `callrail_sources`).

**Non-Goals:**
- Projecting `cl.medium` or `cl.utm_medium` into `call_agg` and rewriting the CASE to consume them. That structural fix is genuinely better long-term but is out of scope here; this change is the minimum-surface fix for the observed bug.
- Adding a `Van Wrap` → Direct mapping. Different source string, 3 rows, separate concern.
- Re-examining `vw_gads_upload_reconciliation_daily`'s mapping of `channel = 'Direct'` → `source_bucket = 'form'` for call-origin Direct rows.
- Changing the priority chain order or the taxonomy enum.

## Decisions

### D1. New CASE branch matches `LOWER(src.value) LIKE '%call forwarding%'`

The new branch mirrors the style of every other CallRail-source branch: `unnest(callrail_sources)` + `LOWER() LIKE '%substring%'`. Substring matching (rather than equality) is the established idiom across the CASE because CallRail's `source` field is free-form and benefits from variant tolerance.

**Alternative considered: exact equality (`= 'call forwarding'`).** Rejected as inconsistent with the rest of the CallRail-source branches. The form-tag branches do use exact equality, but those operate on a controlled UTM enum — different substrate, different style.

**Alternative considered: extend the existing `%direct%` branch to also match `%call forwarding%` via `OR`.** Functionally identical to a separate branch. Kept as a distinct branch because the trigger condition (`Call forwarding` is a CallRail tracker-mode value, semantically distinct from a literal `source = 'Direct'`) reads more clearly as its own line, and a future reader scanning for "where do we classify Call forwarding" finds an exact match.

### D2. Placement: before the existing `%direct%` branch, after every higher-precedence CallRail branch

Order matters in a CASE. The new branch must sit:
- **After** the GMB / Google Ads / GLS / Thumbtack / Organic CallRail branches, so a hypothetical `'Google Local Services / direct'` or `'Google Organic / direct'` row still resolves to its more specific channel rather than collapsing to Direct.
- **Adjacent to** (immediately before) the existing `%direct%` branch, because both branches map to the same `'Direct'` result and they're conceptually paired.

Inserting it immediately before the `%direct%` branch produces the smallest, most readable diff.

### D3. Single migration, CASCADE-recreate pattern

The CASE lives inside the `vw_conversion_candidates` view definition. Postgres requires `DROP VIEW ... CASCADE` to replace it, which also drops `vw_gads_upload_reconciliation_daily`. The May-22 migration (`20260522000001`) established the recreate-both-in-one-file pattern; this migration follows it verbatim — copy the existing view bodies, alter only the channel CASE, recreate `vw_gads_upload_reconciliation_daily` unchanged.

**Alternative considered: introduce a SQL function for the channel CASE to avoid view replacement churn.** Rejected as scope creep — refactoring the view to call a function is a separate change with its own tradeoffs (function-call overhead, planner opacity, additional indirection for readers). The current pattern already exists and is understood.

### D4. No data migration

The view recomputes on every read. The 40 affected production rows reclassify the instant the migration deploys. No backfill, no idempotent re-assertion needed.

## Risks / Trade-offs

- **[Risk] A future CallRail source string might contain "call forwarding" as a substring in a non-Direct context.** Unlikely — `'Call forwarding'` is a CallRail tracker-mode label, not a marketing source. CallRail tracker modes don't overlap with paid/organic source labels. Mitigation: if it ever happens, that row also matches earlier higher-precedence branches (Google Ads, GLS, etc.) and resolves there first; only when no other branch matches does this one fire.
- **[Risk] Reclassifying 40 rows from `Other` → `Direct` shifts the Conversions page weekly rollup numbers.** Intended improvement, not a regression — those rows were Direct all along. Mitigation: none needed; operator should expect the bucket totals to shift on first read after deploy.
- **[Trade-off] We're patching one source-string value rather than fixing the underlying "classifier reads `source`, not `medium`" structural defect.** Acknowledged. The structural fix (project `cl.medium` into `call_agg`, add a medium-based branch) is the right long-term move but is intentionally scoped out. This change closes the only Call-forwarding case actually reachable in the view today; the structural fix is warranted only when future cases accumulate.
- **[Risk] Merge order against any future change touching the same view.** The view is recreated wholesale in each migration, so two unmerged migrations both editing it will conflict. Mitigation: this change is small; rebase trivially if needed.

## Migration Plan

1. **Pre-deploy verification.** Confirm the affected-row count matches expectation:
   ```sql
   SELECT COUNT(*) FROM public.vw_conversion_candidates vc
   WHERE vc.channel = 'Other'
     AND EXISTS (
       SELECT 1 FROM unnest(COALESCE(vc.callrail_sources, ARRAY[]::text[])) src(value)
       WHERE LOWER(src.value) LIKE '%call forwarding%'
     );
   ```
   Expected: **3** (Curt Chandler's 3 estimates). The 40 underlying `callrail_leads` rows do not translate 1:1 to view rows — 39 have `customer_id IS NULL` and never reach the view. A materially different count means assumptions about precedence interaction need re-checking before applying.

2. **Deploy the migration.** Single file replacing `vw_conversion_candidates` (and CASCADE-recreating `vw_gads_upload_reconciliation_daily`). Schema unchanged; only the channel CASE adds one branch.

3. **Verify post-deploy.** Re-run the same query — count should now be 0. Spot-check a known affected estimate (e.g., `csr_02760bb8d5fc4a208bf723ce16c909ea`, Curt Chandler #7543) and confirm `channel = 'Direct'`.

4. **Rollback.** Re-apply the prior migration. View definitions are recreated wholesale; no row data is mutated and nothing else depends on the channel value being `'Direct'` vs. `'Other'` at storage layer.

## Open Questions

- None blocking.
