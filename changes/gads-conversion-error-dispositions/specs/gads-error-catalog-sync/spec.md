## ADDED Requirements

### Requirement: Vendored JSON catalog of Google Ads error enums

The system SHALL provide a checked-in catalog at `supabase/generated/gads_error_catalog.json` that enumerates every error enum value from six Google Ads API protobuf namespaces: `conversionUploadError`, `userDataError`, `quotaError`, `internalError`, `authenticationError`, and `fieldError`. The file SHALL be imported directly by the Deno edge function and the React dashboard with no runtime parsing required.

#### Scenario: Catalog structure

- **WHEN** the catalog file is loaded
- **THEN** it SHALL be a JSON object keyed by `"<namespace>.<ENUM_NAME>"` (e.g., `"conversionUploadError.EXPIRED_EVENT"`)
- **THEN** each value SHALL be an object `{ name: string, namespace: string, tag: number, description: string }` where `description` is the leading comment from the proto file with newlines collapsed and `//` markers stripped

#### Scenario: Catalog coverage

- **WHEN** the catalog is checked against the v23 protobuf source files
- **THEN** every enum value defined in any of the six namespaces SHALL be present in the catalog
- **THEN** no enum value from any other namespace SHALL be present

#### Scenario: Both runtimes import the same catalog

- **WHEN** the Deno edge function or the React dashboard needs to look up an enum
- **THEN** both runtimes SHALL import the same `supabase/generated/gads_error_catalog.json` file
- **THEN** neither runtime SHALL depend on a runtime protobuf library

### Requirement: Catalog sync script regenerates the JSON from pinned proto URLs

The system SHALL provide an npm script `npm run sync:gads-errors` that fetches the six protobuf source files from URLs pinned in the script, parses the enum blocks, and rewrites `supabase/generated/gads_error_catalog.json`. Re-running the script on an unchanged source set SHALL produce an unchanged JSON file (deterministic output).

#### Scenario: Successful regeneration

- **WHEN** a maintainer runs `npm run sync:gads-errors`
- **THEN** the script SHALL fetch each pinned proto URL, parse the enum block, and write the updated JSON
- **THEN** the resulting diff SHALL be reviewable in a pull request

#### Scenario: Malformed proto blocks fail loudly

- **WHEN** a fetched proto file contains an enum value that does not match the expected `^\s*[A-Z_][A-Z0-9_]*\s*=\s*\d+\s*;.*$` shape, or any source file is empty
- **THEN** the script SHALL exit with a non-zero status and SHALL NOT overwrite the existing JSON
- **THEN** an error message SHALL identify the offending file and line

#### Scenario: Deterministic ordering

- **WHEN** the script is run twice in succession against the same proto sources
- **THEN** the two output JSON files SHALL be byte-identical (keys sorted lexicographically, no trailing whitespace differences)
