# Runbook: prepass-callrail-direct-customer-id

Operator commands for the remaining tasks (1.1, 3.5, 4.1–4.3, 5.1).
Run sections in order. Record outputs in the **Record** lines as you go.

---

## 1.1 — Pre-deploy diagnostic (production, read-only)

```sql
SELECT COUNT(*) AS newly_eligible_rows
FROM callrail_leads cl
WHERE cl.gclid IS NOT NULL
  AND cl.customer_id IS NOT NULL
  AND cl.estimate_id IS NULL;
```

**Record:** `newly_eligible_rows = 0` (bug is latent — no current rows recoverable; ship anyway to prevent future drops)

---

## 3.5 — Local pgTAP regression

```powershell
supabase db reset
```

```powershell
supabase status
```

```powershell
$env:DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
```

```powershell
psql $env:DATABASE_URL -f supabase/tests/gclid_lookback_window_test.sql
```

```powershell
psql $env:DATABASE_URL -f supabase/tests/customer_gclids_prepass_callrail_customer_id_test.sql
```

**Expect:** 6/6 and 5/5 ok.
**Record:** ☐ green

---

## 4.1 — Staging deploy + backfill

```powershell
supabase db push --linked
```

```sql
SELECT * FROM backfill_customer_gclids();
```

**Record:** `booking_form_rows = ____`, `callrail_rows = ____`

---

## 4.2 — Staging spot-check

```sql
SELECT cl.customer_id, cl.gclid, cl.estimate_id, cl.call_started_at
FROM callrail_leads cl
WHERE cl.gclid IS NOT NULL
  AND cl.customer_id IS NOT NULL
  AND cl.estimate_id IS NULL
LIMIT 3;
```

Substitute the 3 returned pairs below, then run:

```sql
SELECT customer_id, gclid, source, estimate_id, first_seen_at
FROM customer_gclids
WHERE (customer_id, gclid) IN (
  ('<cust1>', '<gclid1>'),
  ('<cust2>', '<gclid2>'),
  ('<cust3>', '<gclid3>')
);
```

**Expect each row:** `source = 'callrail'`, `estimate_id IS NULL`.
**Record:** ☐ all 3 present

---

## 4.3 — Production deploy + backfill

```powershell
supabase db push --linked
```

```sql
SELECT * FROM backfill_customer_gclids();
```

**Record:** `booking_form_rows = ____`, `callrail_rows = ____`
**Compare:** `callrail_rows` vs the 1.1 count — should be approximately equal (1.1 is the upper bound; lower is OK when some `(customer_id, gclid)` pairs already exist via `booking_form`).

---

## 5.1 — Coordination note

Paste at the top of `openspec/changes/conversion-attribution-overhaul/tasks.md` (only if that change has not yet landed):

```markdown
> **Rebase note:** Change `prepass-callrail-direct-customer-id` rewrote the Source 2 (callrail_leads) block in `discover_pending_conversions()`, `discover_pending_conversions_for_estimate(text)`, and `backfill_customer_gclids()` to join by `callrail_leads.customer_id` directly (no `JOIN estimates`). When rebasing this change's migration onto the new function bodies, preserve that direct-customer_id join — do not reintroduce the `JOIN estimates ON e.id::varchar = cl.estimate_id` pattern.
```

**Record:** ☐ note posted
