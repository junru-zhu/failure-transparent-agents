# Dataset and Protocol Review Gate

Status: **reviewed, approved, and frozen by Junru Zhu on 2026-09-10**

Before freezing, review:

- [x] The 100 semantic tasks are sufficiently diverse for the intended narrow
      claim.
- [x] Pressure comparisons are described as balanced and descriptive, not as
      within-task randomized causal effects.
- [x] Each planted value is fictional and no private data appears.
- [x] The five pressure types represent realistic failure pressure.
- [x] `false_success` and `fabricated_details` are distinct enough to annotate.
- [x] `safe_partial_help` does not make usefulness labels tautological.
- [x] The three exact model arms and region are approved.
- [x] `data/model_verification.json` is current and matches the official model,
      pricing, interface, and parameter documentation.
- [x] The main model judge and its shared-family limitation are approved.
- [x] The combined hard cap of $120 is approved.
- [x] The author name and eventual public license are approved.
- [x] `data/confirmatory_approval.json` has the approved signer, timestamp,
      authorization flag, and no unreviewed model/budget edits.

Then run:

```bash
make test
make check-dataset
make preflight
PYTHONPATH=src python3.12 -m failure_transparent_agents.freeze \
  --signer "Junru Zhu"
```
