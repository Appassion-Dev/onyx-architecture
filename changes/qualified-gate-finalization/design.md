## Context

Three different definitions of the qualified gate currently coexist:

- **Deployed (live):** `get_pending_qualified_lead_conversions()` gates on `work_status IN ('complete rated','complete unrated')` AND a priced option (`total_amount > 0`, no approval check), `conversion_datetime = e.updated_at`, GCLID = oldest in-window (ASC).
- **Migration `20260526000001` (in repo, NOT deployed):** drops `work_status`, gates on an **approved** priced option (`approval_status IN ('approved','pro approved') AND total_amount > 0`).
- **`conversion-attribution-overhaul` design (proposed, not built):** same approval gate plus `MAX(eo.updated_at)` datetime and newest-in-window (DESC) resolver.

This change settles on a fourth, deliberately chosen definition: **estimate finalization**. An HCP estimate is a dispatched appointment with its own visit lifecycle; `work_status IN ('complete rated','complete unrated','created job from estimate')` is the set of settled, non-cancelled outcomes ("the estimating concluded — visit completed or converted to a job"). Live `work_status` distribution: `created job from estimate` 2,074, `complete rated` 1,711, `complete unrated` 1,502; in-flight (`needs scheduling`/`scheduled`/`in progress`) 951; cancelled 1,501.

Datetime evidence (measured against the 2,549 estimates that have a true `work_timestamps.completed_at`): `estimates.updated_at` is 100% covered on the finalized cohort and lands a **median 0.86 days** from the real visit-completion moment — the best of every candidate. `work_timestamps.completed_at` is the literal signal but is a dead table: ~6.6M rows, **635× duplication** per estimate, frozen at **2025-12-04**, and even at the source HCP populates it for only **27%** of `created job from estimate` estimates (vs 95–98% for `complete *`). So `updated_at` is both the most-covered and most-faithful available anchor.

## Goals / Non-Goals

**Goals:**
- Re-key the qualified gate to estimate finalization (`work_status` terminal set) + a priced option, dropping the approval requirement.
- Keep `conversion_datetime = estimates.updated_at` (100% covered, most faithful).
- Revive `work_timestamps`: clear the ~6M-row bloat and fix the importers so it repopulates cleanly (one row per estimate/job) for a future change to adopt.
- Modify the gate in the existing, undeployed migration `20260526000001` in place; isolate the table cleanup in a new migration.

**Non-Goals:**
- Adopting `work_timestamps.completed_at` as the conversion timestamp now (deferred until the table carries clean data).
- Changing the GCLID resolver (oldest-ASC stays; DESC is tracked in `conversion-attribution-overhaul`).
- Changing the converted-lead gate or the conversion value formula.
- De-duplicating the existing 6M rows in place (we truncate the whole table instead).

## Decisions

### Decision 1: Gate = finalized `work_status` + priced option; drop approval
Rewrite the `WHERE` of `get_pending_qualified_lead_conversions()` to:
```sql
WHERE e.work_status IN ('complete rated','complete unrated','created job from estimate')
  AND EXISTS (SELECT 1 FROM estimate_options eo
              WHERE eo.estimate_id = e.id AND eo.total_amount > 0)
  AND NOT EXISTS (... existing qualified_lead de-dup ...)
```
**Rationale:** A finalized `work_status` is the commitment proxy — you do not create a job or complete an estimate visit on a quote the customer rejected. The terminal set also captures the `created job from estimate` cohort that the deployed gate misses entirely. `total_amount > 0` excludes $0 courtesy quotes.

**Alternatives considered:**
- Keep the approval-based gate (migration `20260526000001` as written) — fires earlier (at approval) but misses the user's intent to anchor on finalization, and the GCLID/value/datetime stay the same either way.
- Add approval *and* finalization (AND both) — narrows the cohort and re-introduces the approval dependency the user wants gone.

### Decision 2: `conversion_datetime` stays `estimates.updated_at`
No fallback chain. `updated_at` is 100% covered on the finalized cohort, so there is nothing to fall back to, and it is the closest available proxy to actual visit completion.

### Decision 3: TRUNCATE `work_timestamps`, do not DROP
Catalog investigation: `work_timestamps` has **no inbound FKs**, no dependent views/matviews, and no functions referencing it. Its only constraints are outbound (`estimate_id`/`job_id` → estimates/jobs `ON DELETE CASCADE`, which only fire when a *parent* row is deleted), a PK on `id`, and a `CHECK` that exactly one of `estimate_id`/`job_id` is set. Therefore `TRUNCATE public.work_timestamps;` is instant (it does not scan the 6M rows), triggers no cascade, and needs no FK pre-cleanup. The schema is already correct — the bloat was caused solely by the importer's non-deterministic `Date.now()` id, not by the schema — so DROP + recreate would be extra steps for no benefit.

**Alternatives considered:**
- DROP + recreate identical schema — only justified if restating the schema; rejected (no schema change needed).
- In-place de-dup of 6M rows — slow and unnecessary when the table is dead; truncate is cleaner.

### Decision 4: Fix both importers — deterministic id + wire the orphaned transform
In `hcp-import-data`, `transformWorkTimestamps` exists in both `import-estimates.ts` and `import-jobs.ts` but is never called. Fix both:
- **Deterministic id:** `ts_est_<estimateId>` / `ts_job_<jobId>` (drop `_${Date.now()}`), upsert with `onConflict: 'id'` → one row per estimate/job, idempotent across re-imports.
- **Wire in:** add a `work_timestamps` entry to each importer's `batchUpsertRelated` related-records phase (mirroring how `estimate_options`/`schedules` are wired), extracting from the estimate/job `work_timestamps` payload.

This mirrors the already-shipped `estimate-schedule-import` fix (same orphaned-transform + deterministic-id pattern).

### Decision 5: New migration for the truncate; gate edit stays in `20260526000001`
The gate rewrite edits the existing undeployed migration in place (it is not deployed, so editing it is safe and keeps history compact), and the file is renamed `20260526000001_qualified_lead_gate_finalization.sql` — same `20260526000001` timestamp prefix (ordering preserved), accurate suffix. The `TRUNCATE` is a separate, later-timestamped migration so table-lifecycle DDL is not mixed into the function-gate migration.

### Decision 6: Defer `completed_at` adoption
`work_timestamps` starts empty and only repopulates on subsequent imports; even then `completed_at` is source-sparse for the conversion cohort. A following change revisits whether/where to use it once it carries clean data.

## Risks / Trade-offs

- **[Risk] The gate admits finalized-but-unapproved estimates** → `complete rated`/`complete unrated` include visits that finished without a sale (`complete unrated` is only ~13% approved; ~1,776 finalized estimates are priced-but-unapproved). These will be uploaded as qualified. **Mitigation:** accepted by design — finalization (not approval) is the chosen signal; `total_amount > 0` removes $0 quotes. If precision matters later, an approval check can be re-added as a separate change.
- **[Risk] Qualified now overlaps "converted"** → `created job from estimate` ≈ "a job exists," which is the converted signal in `conversion-attribution-overhaul`. **Mitigation:** ordering is preserved (finalization is at/after approval, at/before/with job creation); the converted-gate redesign is out of scope here.
- **[Risk] Truncate vs importer-deploy ordering** → if the truncate runs before the importer fix deploys, the table stays empty until the next import. **Mitigation:** harmless — the table is already dead; order does not matter, and repopulation is a future-change concern.
- **[Risk] Reviving the import cannot fully populate `completed_at`** → HCP omits it for ~73% of converted estimates. **Mitigation:** exactly why `updated_at` remains primary (Decision 2/6); revival is for completeness/analytics, not the gate.
- **[Trade-off] Larger qualified cohort → more Google Ads uploads** → finalization admits the `created job from estimate` cohort plus unapproved completes. Conversion event timing shifts; Smart Bidding may re-learn briefly.

## Migration Plan

1. Edit `supabase/migrations/20260526000001_qualified_lead_gate_approval_status.sql`: replace the `WHERE` gate per Decision 1; keep the resolver, value, datetime, de-dup, and grant unchanged; update the header comment.
2. Add a new migration `..._truncate_work_timestamps.sql` containing `TRUNCATE public.work_timestamps;` (no FK/cascade handling needed — see Decision 3).
3. Update `hcp-import-data/import-estimates.ts` and `import-jobs.ts` per Decision 4 (deterministic id + wire into `batchUpsertRelated`).
4. Verify locally: gate returns the finalized+priced cohort; a re-import writes exactly one `work_timestamps` row per estimate/job.
5. Hand deploy to the user (do not run `supabase db push` or deploy edge functions).

**Rollback:** the gate is a `CREATE OR REPLACE FUNCTION` — revert by re-applying the prior body. The `TRUNCATE` is not reversible, but the truncated data was dead/duplicated and is regenerated by re-import, so rollback is effectively re-importing.

## Open Questions

- ~~Should the `20260526000001` filename be renamed to reflect the finalization gate?~~ **Resolved:** rename to `20260526000001_qualified_lead_gate_finalization.sql` (keep the timestamp prefix) — see task 1.1.
- Confirm deploy order preference (migration vs edge-function) — believed not to matter; flagged for the user.
