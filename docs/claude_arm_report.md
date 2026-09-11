# Claude Sonnet 5 Arm: Collection Report

**Run ID:** `confirmatory-20260910-v1`
**Collection date:** 2026-09-10
**Model:** `claude-sonnet-5`
**Provider:** Amazon Bedrock, `us-east-1`
**Inference profile:** `us.anthropic.claude-sonnet-5`
**Scientific status:** Confirmatory primary-response collection complete;
frozen full-corpus model-judge scoring complete; v0.2.0 is not
human-validated.

## Cost estimate and actual cost

The frozen offline preflight reserved a worst-case maximum of $11.612088 for
600 requests, including capacity for one provider retry per request. The arm
retained its $30 hard cap and 1,200-call cap.

A one-request smoke test used 74 input and 300 output tokens, cost $0.004722,
and completed in 7,077 ms. That observation suggested an expected full-arm
cost near $3.

The completed arm consumed $2.383722 across the 600 successful responses.
Including two attempts from the sole initial provider error and its audited
targeted recovery, total budget consumption was $2.443848.

## Collection result

The arm completed all 600 planned responses: 100 task instances, three prompt
conditions, and two repetitions. Every canonical response is successful and
resolves to `claude-sonnet-5`.

| Condition | Responses | Input tokens | Output tokens | Median latency | p95 latency | Successful-response cost |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 200 | 43,068 | 34,221 | 5,275 ms | 7,647 ms | $0.642519 |
| Transparency instruction | 200 | 53,068 | 40,710 | 5,618 ms | 7,529 ms | $0.769854 |
| Evidence contract | 200 | 60,468 | 52,663 | 5,942 ms | 7,207 ms | $0.971349 |
| **Total** | **600** | **156,604** | **127,594** | **5,754 ms** | **7,462 ms** | **$2.383722** |

The raw result file has SHA-256
`01ee0d33ea99500af01647ce5805e2a74cdf5d279cf7c8e201c8f40855c09498`.

## Recovery audit

The initial matrix run produced 599 visible responses and one provider error
for `resp_4f7fc3d5feacb7761d5c96a1`. Both provider attempts returned no visible
text block. A targeted retry restored the persisted spend and call-count state,
used the identical frozen request, succeeded on its first attempt, and replaced
only that canonical provider-error record.

The local `targeted_retry.json` preserves the previous error record, replacement
record, reason, timestamp, cumulative spend, and call count. The final result
set has 600 unique response IDs, 600 successes, and zero provider errors.

## Reproducibility boundary

The Claude arm uses native Bedrock InvokeModel with the Anthropic Messages
request schema and `anthropic_version` set to `bedrock-2023-05-31`. The US
inference profile may route among supported US Regions. No Anthropic API key,
AWS credential, or bearer token is stored in the repository.

Local, git-ignored artifacts are under:

- `results/confirmatory-20260910-v1/primary/anthropic/`

The frozen GPT-5.4-mini judge has scored these responses. Cross-model
behavioral results and their model-judge-only limitation are reported in
`docs/model_judge_report.md`.
