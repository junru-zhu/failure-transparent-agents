# Completion Audit

**Audit date:** 2026-09-11
**Overall status:** confirmatory collection, frozen model judging, and
full-corpus analysis complete; human validation and external publication
incomplete

This document maps every requested deliverable to current authoritative
evidence. Synthetic fixture and exploratory Codex outputs are never treated as
confirmatory model results.

## Requirement-by-requirement status

| Requirement | Status | Authoritative evidence | Remaining work |
|---|---|---|---|
| Public 100-task JSONL benchmark | Frozen and public | `data/confirmatory_scenarios.jsonl`; 100 rows; SHA-256 `4bb2f63bc0bf03570021246943d4c1d871d0fe29e78edcdcfe740c0f3ee716ea`; signed `data/confirmatory_manifest.json` | None |
| Annotation guide | Frozen locally | `docs/annotation_guide.md`; strict label schema and 63 passing tests | None before collection |
| Deterministic failed-tool simulator | Complete locally | `src/failure_transparent_agents/simulator.py`; replay and wrong-tool tests | None before collection |
| Provider-neutral evaluation harness | Complete locally | Bedrock OpenAI Responses/SigV4, Anthropic Messages, and native InvokeModel adapters; retry, resume, call, spend, and provenance controls | Authorized live execution |
| Exact model and pricing selection | Verified and approved | `data/model_verification.json`; official-source/config hash checks pass for four primary/judge configs; approval embedded in the frozen manifest | None before collection |
| One-command reproduction | Complete and public | `Makefile`, `docs/reproduction.md`, fourteen installed console commands; repository URL set to `junru-zhu/failure-transparent-agents` | None |
| Complete 1,800-response execution path | Complete | `docs/nvidia_arm_report.md`, `docs/claude_arm_report.md`, and `docs/openai_arm_report.md`; every arm has 600/600 canonical responses | None |
| Labeled confirmatory result set | Frozen model-judge labels complete | `docs/model_judge_report.md`; 1,800/1,800 schema-valid labels; final label SHA-256 `d864203bda8e3fde4cfce5f9688c1870c30c724d5e1a5837f249031789398809` | Validate against human consensus labels |
| Human validation and agreement | Workflow complete; real labels missing | Dual annotation, disagreement-only adjudication, consensus, and agreement code; fixture run produced 540 initial and 270 consensus labels | Two real independent annotators and a third reviewer for disagreements |
| Bootstrap intervals and primary tests | Frozen full-corpus analysis complete; human-sensitivity implementation tested | `docs/model_judge_report.md`; 10,000-draw bootstrap and 100,000-draw paired tests over 100 task clusters; separate descriptive cluster-bootstrap sensitivity command | Run the sensitivity command after real human consensus labels exist |
| Three figures and ablation table | Frozen model-judge artifacts complete | `results/confirmatory-20260910-v1/analysis-model-judge/` | Recheck after human validation and package for release |
| Six-to-eight-page paper | Preliminary result-bearing draft complete | `paper/main.tex` and eight-page `paper/main.pdf`; SHA-256 `afc06c8e3a761e2b421e1f5f519a32d686016f56d3b22fff8641cc991e16ae63`; model-judge results and figures explicitly marked pending human validation | Insert agreement and human sensitivity results, then final visual review |
| GitHub-ready software/data artifact | Public repository active; final builders implemented | Deterministic clean-commit source ZIP plus a separate disclosure-aware scientific-results ZIP; checksums, release report, changelog, release notes, CI, MIT license, and citation metadata | Run both final builders after human validation and explicit approval, then publish |
| Zenodo-ready metadata | Complete locally | `.zenodo.json`, `CITATION.cff`, release audit | Publish exact GitHub release, create DOI, then insert DOI into README, citation metadata, and paper |
| arXiv/workshop submission | Not achieved | Submission checklist only | Authorship confirmation, final results, DOI, and explicit submission authorization |

## Current executable gates

`results/preflight/confirmatory-plan.json` currently plans:

- 1,800 primary responses and at most 3,600 provider attempts;
- a conservative primary bound of `$21.4642236`;
- a model-judge bound of `$44.155494`;
- an aggregate bound of `$65.6197176` under a `$120` hard cap; and
- zero network calls during preflight.

Preflight now reports no blocking checks and `ready_for_live_run: true`.

All three primary arms and the frozen GPT-5.4-mini judge completed. Judging
used 2,624 calls and `$3.68948475` of the `$60` hard cap, plus a
`$0.00003825` smoke test.

## Decisions and inputs still required

Before final scientific reporting:

1. Obtain two independent annotations of the frozen 270-response packet.
2. Adjudicate disagreements and run agreement plus human-only sensitivity
   analysis.

Before public release:

1. Confirm the eventual version tag after confirmatory results are inserted.
2. Approve Zenodo deposition and later arXiv submission as separate external
   actions.

## Completion rule

The research objective is not complete until blinded real-human validation,
agreement and sensitivity analyses, final figures and tables, and the paper
all support the same claims. Provider collection and frozen model judging are
already complete; no additional paid API calls are required.
