# Completion Audit

**Audit date:** 2026-09-10  
**Overall status:** NVIDIA confirmatory collection complete; OpenAI,
Anthropic, frozen judging, human validation, and external publication
incomplete

This document maps every requested deliverable to current authoritative
evidence. Synthetic fixture and exploratory Codex outputs are never treated as
confirmatory model results.

## Requirement-by-requirement status

| Requirement | Status | Authoritative evidence | Remaining work |
|---|---|---|---|
| Public 100-task JSONL benchmark | Frozen locally | `data/confirmatory_scenarios.jsonl`; 100 rows; SHA-256 `4bb2f63bc0bf03570021246943d4c1d871d0fe29e78edcdcfe740c0f3ee716ea`; signed `data/confirmatory_manifest.json` | Push the public repository |
| Annotation guide | Frozen locally | `docs/annotation_guide.md`; strict label schema and 62 passing tests | None before collection |
| Deterministic failed-tool simulator | Complete locally | `src/failure_transparent_agents/simulator.py`; replay and wrong-tool tests | None before collection |
| Provider-neutral evaluation harness | Complete locally | Direct OpenAI Responses, Anthropic Messages, and native Bedrock InvokeModel/SigV4 adapters; retry, resume, call, spend, and provenance controls | Credentials and authorized live execution |
| Exact model and pricing selection | Verified and approved | `data/model_verification.json`; official-source/config hash checks pass for four primary/judge configs; approval embedded in the frozen manifest | None before collection |
| One-command reproduction | Complete locally | `Makefile`, `docs/reproduction.md`, twelve installed console commands; repository URL set to `junru-zhu/failure-transparent-agents` | Push the public repository |
| Complete 1,800-response execution path | NVIDIA arm complete; two arms pending | `results/confirmatory-20260910-v1/primary/nvidia/`: 600/600 responses, zero provider failures, $0.060017 | Run the OpenAI and Anthropic arms |
| Labeled confirmatory result set | Exploratory NVIDIA labels complete; frozen labels pending | `docs/nvidia_arm_report.md`; 600 complete self-judge labels and analysis artifacts are local and git-ignored | Run the frozen GPT-5.4-mini judge over all three arms |
| Human validation and agreement | Workflow complete; real labels missing | Dual annotation, disagreement-only adjudication, consensus, and agreement code; fixture run produced 540 initial and 270 consensus labels | Two real independent annotators and a third reviewer for disagreements |
| Bootstrap intervals and primary tests | Exploratory NVIDIA estimates complete | `docs/nvidia_arm_report.md`; full 10,000-draw bootstrap and 100,000-draw paired tests | Rerun on frozen three-model labels |
| Three figures and ablation table | Exploratory NVIDIA artifacts complete | `results/confirmatory-20260910-v1/analysis-nvidia-exploratory/` | Regenerate from frozen three-model labels |
| Six-to-eight-page paper | Draft complete | `paper/main.pdf`: six pages, structurally valid; SHA-256 `15a539a45c48b3085bc3fd6f6b8e2ff937f173691e70bfd601b810af019ee4b7` | Replace explicit result placeholders and revise claims after analysis |
| GitHub-ready software/data artifact | Complete locally | Deterministic source ZIP, checksum, release report, changelog, release notes, CI, MIT license, citation metadata, and initialized local Git repository | Authenticate GitHub and push `junru-zhu/failure-transparent-agents` |
| Zenodo-ready metadata | Complete locally | `.zenodo.json`, `CITATION.cff`, release audit | Publish exact GitHub release, create DOI, then insert DOI into README, citation metadata, and paper |
| arXiv/workshop submission | Not achieved | Submission checklist only | Authorship confirmation, final results, DOI, and explicit submission authorization |

## Current executable gates

`results/preflight/confirmatory-plan.json` currently plans:

- 1,800 primary responses and at most 3,600 provider attempts;
- a conservative primary bound of `$20.6180844`;
- a model-judge bound of `$44.155494`;
- an aggregate bound of `$64.7735784` under a `$120` hard cap; and
- zero network calls during preflight.

Preflight now reports no blocking checks and `ready_for_live_run: true`.

The NVIDIA arm completed through the authorized local `AWS_PROFILE`. The
environment still lacks `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`.

## Decisions and inputs still required

Before remaining paid collection:

1. Set the OpenAI and Anthropic credentials outside the repository.
2. Run credential smoke tests, then start those two resumable provider arms.

Before public release:

1. Authenticate GitHub and push the approved public repository.
2. Confirm the eventual version tag after confirmatory results are inserted.
3. Approve Zenodo deposition and later arXiv submission as separate external
   actions.

## Completion rule

The research objective is not complete until real provider outputs, blinded
model labels, real human consensus labels, empirical analysis, final paper
results, and the authorized public archive exist and have been verified.
