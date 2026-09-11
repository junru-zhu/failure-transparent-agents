# NVIDIA Nemotron Arm: Collection Report

**Run ID:** `confirmatory-20260910-v1`
**Collection date:** 2026-09-10
**Model:** `nvidia.nemotron-super-3-120b`
**Provider:** Amazon Bedrock, `us-east-1`
**Scientific status:** Primary responses are confirmatory data; behavioral
labels and estimates in this report are exploratory. Frozen independent
model-judge estimates are now complete; human validation remains pending.

## Collection result

The NVIDIA arm completed all 600 planned responses: 100 task instances,
three prompt conditions, two repetitions, and zero provider failures.

| Condition | Responses | Input tokens | Output tokens | Median latency | p95 latency | Estimated cost |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 200 | 32,016 | 17,388 | 2,546 ms | 3,523 ms | $0.016105 |
| Transparency instruction | 200 | 37,816 | 24,218 | 2,845 ms | 3,890 ms | $0.021414 |
| Evidence contract | 200 | 40,416 | 25,286 | 2,804 ms | 3,861 ms | $0.022498 |
| **Total** | **600** | **110,248** | **66,892** | **2,741 ms** | **3,842 ms** | **$0.060017** |

The raw result file has SHA-256
`d5f6bcdb60e722fff9e17b26b5c3df87665388ad35981309222ee323c1013637`.

## Exploratory behavioral estimates

Nemotron scored its own outputs with the frozen rubric but an explicitly
unfrozen local judge configuration. The complete set contains 600 labels.
Five hundred ninety-two passed on the main scoring run, seven passed a
targeted retry, and one required a deterministic evidence-span formatting
repair after three identical boolean judgments omitted Markdown emphasis from
the quoted span. No boolean label was changed by that repair.

| Metric | Baseline | Transparency instruction | Evidence contract |
|---|---:|---:|---:|
| False success | 30.0% [21.0, 39.0] | 23.0% [15.0, 31.5] | 2.5% [0.0, 6.0] |
| Fabricated details | 26.5% [18.5, 35.0] | 17.5% [10.5, 25.0] | 0.5% [0.0, 2.0] |
| Limitation disclosed | 71.0% [62.0, 80.0] | 77.5% [69.5, 85.5] | 97.5% [94.0, 100.0] |
| Recovery action | 67.0% [58.0, 76.0] | 74.0% [65.5, 82.0] | 96.5% [93.0, 99.5] |
| Useful response | 70.0% [61.0, 79.0] | 76.0% [67.5, 84.0] | 97.0% [93.5, 100.0] |
| Over-refusal | 0.0% [0.0, 0.0] | 0.0% [0.0, 0.0] | 0.0% [0.0, 0.0] |

Brackets are clustered 95% bootstrap intervals over 100 base-task clusters.
Compared with baseline, the transparency instruction reduced false success
by 7.0 percentage points (95% CI -12.5 to -2.5; Holm-adjusted
`p = 0.0066`) and fabricated details by 9.0 points (95% CI -15.5 to
-3.0; Holm-adjusted `p = 0.0063`). The evidence contract reduced false
success by 27.5 points (95% CI -36.5 to -19.0; Holm-adjusted
`p < 0.0001`) and fabricated details by 26.0 points (95% CI -34.5 to
-17.5; Holm-adjusted `p < 0.0001`).

The most difficult pressure type was forced choice: exploratory false-success
rates were 90.0% under baseline, 62.5% under the transparency instruction,
and 12.5% under the evidence contract. Under explicit pressure to conceal
failure, the corresponding rates were 52.5%, 52.5%, and 0.0%.

## Cost and scoring audit

Primary collection cost $0.060017. Exploratory scoring cost $0.239977,
including the stopped 300-token diagnostic, the corrected full scoring run,
and the eight-record retry. Combined collection and exploratory scoring cost
was $0.299994, excluding two earlier smoke requests.

The complete exploratory labels have SHA-256
`6425896ca4fa7f8bde5588bdcac63fcf97972bd0d41d95b68b0ddaf0c5e32c01`.
The rate and comparison tables have SHA-256
`b9db66ac3502f3d6dc887c1d1150a8ad019e5a0ef31b7a0026012f8012830950`
and
`438825a781a3a8aae3b8f9b032c7a307118dbb0862dda10c8181831b87463a9f`.

Local, git-ignored artifacts are under:

- `results/confirmatory-20260910-v1/primary/nvidia/`
- `results/confirmatory-20260910-v1/judge-nvidia-exploratory/`
- `results/confirmatory-20260910-v1/analysis-nvidia-exploratory/`

The analysis directory contains the complete labeled result set, rate and
comparison CSVs, efficiency metrics, three SVG figures, and the LaTeX
ablation table.

## Interpretation boundary

The collection itself is a valid completed confirmatory model arm. The
behavioral estimates in this arm-specific report are not the preregistered
labels because the tested model judged its own responses and the local judge
configuration was not frozen. The independent frozen-judge results supersede
them and are reported in `docs/model_judge_report.md`; human agreement is
still pending.
