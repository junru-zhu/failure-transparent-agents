# Six-model extension report

The post-confirmatory model-generalization extension is complete. It adds
Amazon Nova Micro, Meta Llama 3.1 8B Instruct, and Mistral Ministral 8B 3.0 to
the original OpenAI, Anthropic, and NVIDIA comparison. The combined analysis
contains 3,600 responses: six models, 100 tasks, three conditions, and two
repeats.

## Main result

| Model | Baseline false success | Transparency instruction | Evidence contract |
| --- | ---: | ---: | ---: |
| Claude Sonnet 5 | 34.0% | 3.0% | 0.0% |
| Ministral 8B 3.0 | 29.5% | 19.5% | 0.0% |
| NVIDIA Nemotron Super 3 | 26.5% | 20.5% | 2.0% |
| GPT-5.6 Terra | 25.0% | 5.5% | 2.0% |
| Amazon Nova Micro | 15.5% | 6.5% | 0.5% |
| Meta Llama 3.1 8B | 6.0% | 0.5% | 0.5% |
| **All six models** | **22.8%** | **9.3%** | **0.8%** |

The evidence contract reduces false success by 21.9 percentage points from
baseline (scenario-clustered 95% CI: 16.2–28.0 points; paired sign-flip
Holm-adjusted \(p < 0.00004\)). It also reduces fabricated details from 28.3%
to 0.8%, while useful responses rise from 74.9% to 98.8%. No increase in
over-refusal was detected: 2.8% at baseline versus 2.3% under the evidence
contract.

The plain transparency instruction remains strongly model-dependent, ranging
from 0.5% to 20.5% false success. In contrast, all six evidence-contract rates
fall between 0% and 2%.

## Judge validity and repair

GPT-5.6 Luna labels all 3,600 responses under the unchanged outcome rubric.
On the original 1,800 responses, agreement with the frozen GPT-5.4-mini judge
is 97.4% for false success (Cohen's \(\kappa=0.895\)), 95.2% for fabricated
details (\(\kappa=0.837\)), and 95.8–99.1% for disclosure, recovery, and
usefulness (\(\kappa=0.876\)–0.961).

The initial Luna pass produced 3,500 valid labels. Ordinary retries and an
audited exact-schema repair prompt recovered 94 additional labels. Six
persistent rows retained valid outcome booleans but paraphrased their evidence
spans; their spans were replaced with exact response substrings under a public
audit map. The audit changed zero outcome booleans.

## Cost and artifacts

The three added primary arms cost $0.0715. Unified six-model judging and repair
cost $2.0107, for a $2.0822 extension total. The three primary arms contain
600/600 successful responses each, with zero provider errors or duplicate
response IDs.

Canonical compact results are stored in `data/model_extension_summary.json`.
The v0.3.0 GitHub release includes a deterministic sanitized archive of all
3,600 responses and unified labels. Provider request IDs, retry error details,
credentials, and private execution-environment metadata are excluded.
