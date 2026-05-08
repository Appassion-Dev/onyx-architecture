## MODIFIED Requirements

### Requirement: Filter by source
The Conversions page SHALL provide a "Channel" dropdown that filters estimates to those with a matching `channel` value. Options are the seven taxonomy channel names: All, Google Ads, GLS, GMB, Thumbtack, Organic, Direct, Other.

#### Scenario: Default state
- **WHEN** the Channel dropdown is set to "All"
- **THEN** all estimates in the 90-day window are shown regardless of channel

#### Scenario: Filter to Google Ads
- **WHEN** user selects "Google Ads" from the Channel dropdown
- **THEN** only estimates where `channel = 'Google Ads'` are shown

#### Scenario: Filter to GLS
- **WHEN** user selects "GLS" from the Channel dropdown
- **THEN** only estimates where `channel = 'GLS'` are shown

#### Scenario: Filter to Other
- **WHEN** user selects "Other" from the Channel dropdown
- **THEN** only estimates where `channel = 'Other'` are shown

## REMOVED Requirements

### Requirement: Filter by first-touch medium
**Reason**: The `first_touch_medium` filter (Form / Call) is superseded by the channel-based grouping. The medium distinction (form vs call) is retained as a supporting signal in the view but is no longer a standalone filter dropdown option.
**Migration**: Consumers relying on `first_touch_medium` filtering should switch to `channel` filtering. The `first_touch_medium` column remains in the view and can be used as a secondary filter if needed.
