## ADDED Requirements

### Requirement: Method tri-cell labels use GCLID+ECL / ECL terminology
The rollup Method tri-cell SHALL display its sublabel and hover tooltip using the
GCLID+ECL / ECL terminology that matches the per-row Method tags, while the three
underlying counts and their classification semantics
(`with_gclid` / `user_data_only` / `none`) remain unchanged. The `with_gclid`
count SHALL be labeled to denote any-GCLID uploads (GCLID, with or without
enhanced-conversion identifiers); the `user_data_only` count SHALL be labeled
"ECL"; the `none` count SHALL be labeled "none".

#### Scenario: Sublabel terminology
- **WHEN** a rollup Method tri-cell renders its sublabel
- **THEN** the sublabel SHALL read using the GCLID+ECL / ECL / none terminology
  (replacing the prior `gclid / eoc / none` wording)

#### Scenario: Tooltip terminology
- **WHEN** the user hovers the rollup Method tri-cell
- **THEN** the tooltip SHALL describe the first count as GCLID-based uploads
  (with or without identifiers), the second as ECL (enhanced conversions for
  leads, no GCLID), and the third as none (cannot upload)

#### Scenario: Counts unchanged
- **WHEN** the rollup Method tri-cell renders its three counts
- **THEN** the counts SHALL be the same `with_gclid` / `user_data_only` / `none`
  values as before, summing to the Stage count for the same window
