# Failure-Transparent Agents v0.3.0

**Status:** Authorized six-model, model-judge-only release; not
human-validated

This release preserves the frozen three-model confirmatory study and adds a
separately frozen post-confirmatory generalization extension. The complete
analysis contains six models, 100 tasks, three prompt conditions, two repeats,
3,600 model responses, and 3,600 schema-valid GPT-5.6-Luna labels.

## Main result

Across all six models, false success is 22.8% at baseline, 9.3% with the plain
failure-transparency instruction, and 0.8% under the structured evidence
contract. Fabricated details fall from 28.3% to 0.8%, while useful responses
rise from 74.9% to 98.8%.

The original 1,800-response study remains the confirmatory analysis. The added
cohort and unified six-model estimates are post-confirmatory generalization
evidence and do not retroactively alter the original hypotheses.

## Included artifacts

- audited source ZIP and Python wheel;
- eight-page IEEE-style paper and the INSAI/Springer manuscript;
- deterministic sanitized six-model results ZIP;
- 3,600 authorized model responses and model-judge labels;
- rates, confidence intervals, paired comparisons, efficiency results,
  pressure ablation, and editable SVG figures;
- extension freeze, verification, repair, and exact-span audit metadata;
- publication manifest containing every payload hash.

## Disclosure and privacy

- No human annotation was conducted or claimed.
- Provider request IDs and retry error details are removed.
- Credentials, local paths, account identifiers, and private
  execution-environment details are excluded.
- Six persistent judge-format rows received exact-span corrections under a
  public audit map; zero outcome booleans changed.

## Reproduce the release

```bash
make release-audit
make six-model-results-bundle PYTHON=.venv/bin/python
make six-model-release-wheel PYTHON=.venv/bin/python
make paper PYTHON=.venv/bin/python
make insai-paper PYTHON=.venv/bin/python
```

The historical v0.2.0 release remains available as the immutable artifact for
the original three-model study.
