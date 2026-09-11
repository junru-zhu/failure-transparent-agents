# GPT-5.6 Terra Arm: Collection Report

**Run ID:** `confirmatory-20260910-v1`  
**Collection date:** 2026-09-10  
**Model:** `us.openai.gpt-5.6-terra`  
**Provider:** Amazon Bedrock, `us-east-1`  
**Scientific status:** Confirmatory primary-response collection complete;
frozen full-corpus model-judge scoring complete; human validation pending.

## Cost estimate and actual cost

The frozen offline preflight reserved a worst-case maximum of $9.3075312 for
600 requests, including capacity for one provider retry per request. The arm
retained its $20 hard cap and 1,200-call cap.

A one-request smoke test used 132 input and 30 output tokens, cost
$0.0006864, and completed in 2,446 ms.

The completed canonical responses cost $0.6535144. Two transient transport
failures succeeded on their configured retry. Conservatively charging the
failed attempts at their reservation bounds produced total recorded budget
consumption of $0.6692400. The separate smoke request is not included in that
matrix total.

## Collection result

The arm completed all 600 planned responses: 100 task instances, three prompt
conditions, and two repetitions. Every canonical response is successful and
resolves to `us.openai.gpt-5.6-terra`.

| Condition | Responses | Input tokens | Output tokens | Median latency | p95 latency | Successful-response cost |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 200 | 28,094 | 6,763 | 943 ms | 1,756 ms | $0.1510784 |
| Transparency instruction | 200 | 34,094 | 8,737 | 1,084 ms | 2,100 ms | $0.1903352 |
| Evidence contract | 200 | 36,294 | 17,595 | 1,392 ms | 2,302 ms | $0.3121008 |
| **Total** | **600** | **98,482** | **33,095** | **1,114 ms** | **2,100 ms** | **$0.6535144** |

The raw result file has SHA-256
`69d6c4bc2473ed8cb992f380ea56fe17fd832594e08498b6f10f02104f025fd8`.
It contains 600 unique response IDs, 600 successes, and zero canonical
provider errors.

## Retry audit

Two responses required a second attempt. One first attempt timed out while
reading the response; the other encountered a transient TLS record-layer
failure. Both identical frozen requests succeeded automatically on retry.
The final matrix used 602 provider calls and required no targeted repair.

## Reproducibility boundary

The arm uses Bedrock's OpenAI-compatible Responses endpoint with AWS Signature
Version 4 authentication, `reasoning.effort` set to `none`, and `store` set to
`false`. No AWS credential, API key, bearer token, or private execution-profile
name is stored in the repository.

Local, git-ignored artifacts are under:

- `results/confirmatory-20260910-v1/primary/openai/`

The frozen GPT-5.4-mini judge has scored these responses. Cross-model
behavioral results and their human-validation boundary are reported in
`docs/model_judge_report.md`.
