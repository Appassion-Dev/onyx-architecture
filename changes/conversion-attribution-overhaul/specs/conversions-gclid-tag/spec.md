## MODIFIED Requirements

### Requirement: GCLID count badge in its own column
Each estimate row in the Conversions page SHALL include a dedicated "GCLID" column (separate from the Source column). The badge data source SHALL depend on the active conversion mode:

| Mode            | Badge data source                  | Badge content                            |
|-----------------|------------------------------------|------------------------------------------|
| `pre-discovery` | `row.all_gclids` (estimate pool)   | `GCLID ×N` when N ≥ 1; empty when 0     |
| `booking`       | `row.booking_gclid`                | `GCLID` when not NULL; empty when NULL   |
| `qualified`     | `row.qualified_gclid`              | `GCLID` when not NULL; empty when NULL   |
| `converted`     | `row.converted_gclid`              | `GCLID` when not NULL; empty when NULL   |

In stage modes (`booking`, `qualified`, `converted`), the badge reflects the GCLID actually stored on that stage's `gads_conversion_uploads` row, so the per-row badge and the column-level GCLID totals (which count rows where `*_gclid IS NOT NULL`) are coherent.

#### Scenario: Pre-discovery mode shows pool count
- **WHEN** the conversion mode is `pre-discovery` and `all_gclids` contains 2 entries
- **THEN** the GCLID column shows `GCLID ×2`

#### Scenario: Stage mode shows the per-stage stored GCLID
- **WHEN** the conversion mode is `qualified` and `row.qualified_gclid = 'CjwK...'`
- **THEN** the GCLID column shows a `GCLID` badge

#### Scenario: Stage mode hides the badge when the stage's stored GCLID is NULL
- **WHEN** the conversion mode is `qualified` and `row.qualified_gclid IS NULL`
- **THEN** the GCLID column does NOT show a `GCLID` badge for that row

#### Scenario: Stage badge and column total are coherent
- **WHEN** the conversion mode is `qualified` and 10 rows are visible in a group, of which 7 have `qualified_gclid IS NOT NULL`
- **THEN** exactly 7 row-level `GCLID` badges are rendered AND the column-level GCLID total for the group reads `7`

### Requirement: GCLID tooltip on hover
The GCLID badge SHALL show a tooltip on hover.

- In `pre-discovery` mode the tooltip lists every value from `all_gclids`, one per line, in monospace font.
- In stage modes (`booking`, `qualified`, `converted`) the tooltip shows the single per-stage GCLID value (`booking_gclid` / `qualified_gclid` / `converted_gclid`) in monospace font.

#### Scenario: Tooltip in pre-discovery mode lists all pool entries
- **WHEN** the user hovers over the badge in `pre-discovery` mode and `all_gclids` has 2 entries
- **THEN** the tooltip lists 2 lines, one per GCLID, in monospace font

#### Scenario: Tooltip in stage mode shows the single stored value
- **WHEN** the user hovers over the badge in `qualified` mode and `qualified_gclid = 'CjwK...'`
- **THEN** the tooltip shows that one value in monospace font

## ADDED Requirements

### Requirement: Pool-count hint when stage badge is hidden
In stage modes, when the per-stage badge is hidden because the stage's stored GCLID is NULL, the row SHALL display a small muted indicator (e.g., `n in pool`) when `row.all_gclids` contains at least one entry. The indicator SHALL be visually distinct from the primary `GCLID` badge (e.g., neutral text colour, smaller weight) and SHALL show a tooltip listing every value in `all_gclids`. When `all_gclids` is empty AND the stage's stored GCLID is NULL, no indicator is rendered.

#### Scenario: Stage GCLID is NULL but pool is non-empty — indicator shown
- **WHEN** the conversion mode is `qualified`, `row.qualified_gclid IS NULL`, and `row.all_gclids` has 2 entries
- **THEN** the row shows a muted `2 in pool` indicator (not the primary `GCLID` badge)

#### Scenario: Stage GCLID and pool both empty — nothing shown
- **WHEN** the conversion mode is `qualified`, `row.qualified_gclid IS NULL`, and `row.all_gclids` is empty or NULL
- **THEN** the row shows no GCLID indicator at all

#### Scenario: Stage GCLID populated — primary badge shown, no pool indicator
- **WHEN** the conversion mode is `qualified` and `row.qualified_gclid IS NOT NULL`
- **THEN** the row shows the primary `GCLID` badge AND does NOT show the muted pool indicator
