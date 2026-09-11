# Frozen Model-Judge and Preliminary Analysis Report

**Run ID:** `confirmatory-20260910-v1`  
**Scoring completed:** 2026-09-11  
**Frozen judge:** `gpt-5.4-mini`  
**Resolved model snapshot:** `gpt-5.4-mini-2026-03-17`  
**Scientific status:** Full-corpus confirmatory model-judge analysis complete;
human validation remains pending.

## Coverage and cost

The frozen, condition-blinded judge scored all 1,800 successful primary
responses. The final label set contains 1,800 unique, schema-valid records and
has SHA-256
`d864203bda8e3fde4cfce5f9688c1870c30c724d5e1a5837f249031789398809`.

The judge used 2,624 calls, including correction and adjudication attempts,
and consumed `$3.68948475` of the approved `$60` judge cap. The preceding
one-call smoke test cost `$0.00003825`, making the key-backed scoring total
`$3.68952300`.

The strict first pass produced 1,631 valid labels and 169 evidence-span
validation errors. Recovery preserved the frozen rubric and model:

- 120 labels passed a targeted retry with stricter verbatim-span instructions;
- 37 labels had stable boolean decisions across five parseable attempts and
  received audited span-only formatting repairs;
- 10 labels passed a final blinded adjudication prompt; and
- two remaining labels received audited span-only repair, including one
  false-success tie resolved by three agreeing same-model tie-break judgments.

No repair silently changed a stable boolean decision. Raw outputs, validation
errors, repair audits, call counts, spend, and hashes remain in the local,
git-ignored run directory.

## Preliminary full-corpus estimates

These estimates use the frozen model judge over all 1,800 responses. Brackets
are 95% hierarchical bootstrap intervals over 100 base-task clusters.

| Metric | Baseline | Transparency instruction | Evidence contract |
|---|---:|---:|---:|
| False success | 32.0% [23.8, 40.3] | 11.8% [8.0, 16.0] | 1.3% [0.3, 2.7] |
| Fabricated details | 37.5% [29.7, 45.7] | 17.3% [13.0, 22.0] | 3.3% [1.7, 5.3] |
| Limitation disclosed | 69.3% [61.3, 77.2] | 89.0% [84.7, 93.0] | 98.3% [96.8, 99.5] |
| Recovery action | 59.5% [51.7, 67.0] | 83.0% [77.7, 88.0] | 98.0% [96.3, 99.3] |
| Useful response | 69.8% [61.8, 77.7] | 90.2% [86.0, 94.0] | 98.3% [96.8, 99.5] |
| Over-refusal | 0.0% [0.0, 0.0] | 0.0% [0.0, 0.0] | 0.5% [0.0, 1.3] |

All four preregistered primary comparisons favored the intervention:

| Comparison versus baseline | Absolute change | 95% CI | Risk ratio | Holm-adjusted p |
|---|---:|---:|---:|---:|
| Transparency: false success | -20.2 pp | [-26.7, -14.0] | 0.370 | 0.000040 |
| Evidence contract: false success | -30.7 pp | [-39.0, -22.8] | 0.042 | 0.000040 |
| Transparency: fabricated details | -20.2 pp | [-26.8, -13.7] | 0.462 | 0.000040 |
| Evidence contract: fabricated details | -34.2 pp | [-42.3, -25.8] | 0.089 | 0.000040 |

The intervention pattern appeared in every model, although the explicit
transparency instruction was less effective for Nemotron than for the other
two tested models. Baseline-to-evidence-contract false-success rates were
36.0% to 0.0% for Claude Sonnet 5, 31.0% to 2.0% for Nemotron Super 3 120B,
and 29.0% to 2.0% for GPT-5.6 Terra.

Pressure comparisons remain descriptive because pressure variants are
balanced across, rather than crossed within, identical tasks. Forced-choice
and conceal-failure prompts produced the highest baseline false-success rates.

## Analysis artifacts

The frozen analysis used 10,000 hierarchical bootstrap repetitions, 100,000
paired sign-flip repetitions, and seed `20260910`. It produced:

- complete labeled results and rate, comparison, and efficiency tables;
- three SVG figures;
- a LaTeX pressure-ablation table; and
- a machine-readable analysis summary.

Local paths:

- `results/confirmatory-20260910-v1/judge/`
- `results/confirmatory-20260910-v1/judge-recovery/`
- `results/confirmatory-20260910-v1/analysis-model-judge/`

## Remaining scientific gate

The preregistered 270-response packet was selected before model-judge labels
were inspected and remains condition/model blinded. Two independent human
annotators must label the packet, disagreements must receive blinded
adjudication, and agreement must be reported for all six labels. Until that
step is complete, the estimates above are full-corpus model-judge findings,
not human-validated final claims.
