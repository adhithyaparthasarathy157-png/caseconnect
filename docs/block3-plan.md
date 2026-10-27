# Block 3 plan — institution registry and profiles

## Existing baseline

- Institutions already have internal IDs, Permanent IDs, verification flags, name/location fields, region/status, case relationship, unique raw Permanent-ID constraint, authorized create/edit APIs, name/ID/region search, and case-history route.
- Cases already require a valid institution foreign key and use permission-scoped case visibility.
- Institution create/edit actions already produce audit events.

## Gaps to close

1. Canonicalize Permanent IDs and textual lookups to prevent whitespace/case variants from creating accidental duplicates; do not claim an official ID format.
2. Add a real, permission-scoped consolidated profile endpoint including accessible cases, history summaries and visible overlap relationships.
3. Record safe before/after institution edit details.
4. Upgrade the Institutions screen with search/filter, profile/case history, related-overlap context, and authorized create/edit forms with understandable errors.
5. Add API/integration tests for normalization, profile correctness, audit details, access restrictions, and persistence.

## Safety

All changes are additive or normalization-only, with no deletion endpoint/cascade behavior. Synthetic data and isolated test databases will be used for verification.
