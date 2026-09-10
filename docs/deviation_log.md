# Confirmatory Deviation Log

No confirmatory collection has begun.

After author freeze, append one entry per change:

| Date | Version | Stage | Change | Reason | Expected impact | Approved by |
|---|---|---|---|---|---|---|
| 2026-09-10 | 2026-09-10.v2 | presentation | Corrected the release audit to read the frozen manifest's `signed_by` field instead of the nonexistent top-level `approved_by` field; regenerated the identical dataset candidate and repeated author freeze before collection. | The first post-freeze release audit incorrectly reported that the signed manifest lacked author signoff. | None on scenarios, prompts, collection, scoring, or analysis; release readiness is now reported correctly. | Junru Zhu |

Stages are `collection`, `scoring`, `analysis`, or `presentation`. Never edit or
delete an earlier entry; corrections receive a new row.
