# Offline Pilot Validation Report

**Run date:** 2026-09-10  
**Provider:** Deterministic fixture  
**API cost:** $0  
**Scientific status:** Infrastructure validation only; not an empirical model experiment

## Coverage

- 20 synthetic scenarios
- 5 balanced categories, 4 scenarios each
- 3 instruction conditions
- 2 repetitions
- 120 generated fixture responses

Category balance:

| Category | Scenarios |
|---|---:|
| Execution failed | 4 |
| Missing attachment | 4 |
| Permission denied | 4 |
| Stale data | 4 |
| Web unavailable | 4 |

## Pipeline checks

The fixture deliberately emits known unsupported claims under a deterministic subset of baseline cases and transparent responses under intervention conditions. The evaluator recovered the planted behavior:

| Condition | Responses | Planted false-success labels | Limitation disclosures | Recovery actions |
|---|---:|---:|---:|---:|
| Baseline | 40 | 28 | 12 | 12 |
| Transparency | 40 | 0 | 40 | 40 |
| Evidence contract | 40 | 0 | 40 | 40 |

These rates describe fixture construction, not language-model behavior. They must not be quoted as evidence supporting the paper's hypotheses.

## Validation performed

- The original pilot-stage suite passed 7 tests; the completed freeze-candidate
  suite now passes 61 tests.
- Python bytecode compilation passed for source and tests.
- JSONL schema and duplicate-ID validation passed.
- Scenario categories are exactly balanced.
- Raw-result, summary, and manifest generation passed.
- Every generated manifest carries a fixture-only warning.
- A pilot run exposed that the heuristic did not recognize “retrieve” as a recovery action; the vocabulary was corrected and the full validation reran successfully.
- LaTeX compilation was not run because no TeX engine is installed on this
  host. The paper has since been expanded into a full preregistered draft with
  explicit placeholders and no confirmatory claims.
- A later full-cardinality fixture run exercised 1,800 responses, 1,800 model
  labels, 270 human-label fixtures, agreement, bootstrap analysis, all three
  figures, and the LaTeX table.

## Gate before paid experiments

The infrastructure gates are now implemented. Paid collection still requires:

1. Author review and signed freeze of the dataset, rubric, prompts, configs,
   and analysis plan.
2. Re-verification of model availability and prices.
3. Explicit approval of the $120 combined primary-plus-judge ceiling.
4. The three credential environment variables.
