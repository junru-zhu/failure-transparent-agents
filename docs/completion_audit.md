# Completion Audit

**Audit date:** 2026-09-11
**Overall status:** confirmatory collection, frozen model judging, and
full-corpus analysis complete; v0.2.0 authorized for model-judge-only
publication and not human-validated

This document maps every requested deliverable to current authoritative
evidence. Synthetic fixture and exploratory Codex outputs are never treated as
confirmatory model results.

## Requirement-by-requirement status

| Requirement | Status | Authoritative evidence | Remaining work |
|---|---|---|---|
| Public 100-task JSONL benchmark | Frozen and public | `data/confirmatory_scenarios.jsonl`; 100 rows; SHA-256 `4bb2f63bc0bf03570021246943d4c1d871d0fe29e78edcdcfe740c0f3ee716ea`; signed `data/confirmatory_manifest.json` | None |
| Annotation guide | Frozen locally | `docs/annotation_guide.md`; strict label schema and tested workflow | Optional future human validation |
| Deterministic failed-tool simulator | Complete locally | `src/failure_transparent_agents/simulator.py`; replay and wrong-tool tests | None before collection |
| Provider-neutral evaluation harness | Complete locally | Bedrock OpenAI Responses/SigV4, Anthropic Messages, and native InvokeModel adapters; retry, resume, call, spend, and provenance controls | Authorized live execution |
| Exact model and pricing selection | Verified and approved | `data/model_verification.json`; official-source/config hash checks pass for four primary/judge configs; approval embedded in the frozen manifest | None before collection |
| One-command reproduction | Complete and public | `Makefile`, `docs/reproduction.md`, installed console commands; repository URL set to `junru-zhu/failure-transparent-agents` | None |
| Complete 1,800-response execution path | Complete | `docs/nvidia_arm_report.md`, `docs/claude_arm_report.md`, and `docs/openai_arm_report.md`; every arm has 600/600 canonical responses | None |
| Labeled confirmatory result set | Complete for v0.2.0 | `docs/model_judge_report.md`; 1,800/1,800 schema-valid frozen model-judge labels; final label SHA-256 `d864203bda8e3fde4cfce5f9688c1870c30c724d5e1a5837f249031789398809` | None for the model-judge-only release |
| Human validation and agreement | Not conducted for v0.2.0 | Junru Zhu authorized omission on 2026-09-11; dual annotation, adjudication, consensus, and agreement tooling remains available | Optional future validation only |
| Bootstrap intervals and primary tests | Frozen full-corpus model-judge analysis complete | `docs/model_judge_report.md`; 10,000-draw bootstrap and 100,000-draw paired tests over 100 task clusters | Optional human-label sensitivity analysis is outside v0.2.0 |
| Three figures and ablation table | Frozen model-judge artifacts complete | `results/confirmatory-20260910-v1/analysis-model-judge/` | Package for release |
| Six-to-eight-page paper | Model-judge-only result-bearing draft complete | `paper/main.tex` and eight-page `paper/main.pdf`; SHA-256 `d4ccd538361a6d08e92022a79ca80804ddfe61a33b361142994c8c84a4304987`; no human results are claimed | Keep the not-human-validated limitation explicit |
| GitHub-ready software/data artifact | Publication authorized | Deterministic source ZIP and sanitized model-judge-only results ZIP; all model-output dispositions approved; raw request IDs removed; checksums, release notes, CI, MIT license, and citation metadata prepared | Build artifacts and publish the approved GitHub release |
| Zenodo-ready metadata | Complete locally | `.zenodo.json`, `CITATION.cff`, release audit | Publish exact GitHub release, create DOI, then insert DOI into README, citation metadata, and paper |
| arXiv/workshop submission | Not achieved | Submission checklist only | Venue review, optional DOI, and explicit submission authorization |

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

## Publication decision and remaining actions

Author Junru Zhu approved v0.2.0 on 2026-09-11 as model-judge-only and not
human-validated. Human annotation is not a release gate for this version.
All model-output dispositions are approved, and public artifacts must remove
raw provider request IDs.

Remaining actions are to build the source and model-only results artifacts,
publish the approved GitHub tag/release, and separately decide whether to
create a Zenodo DOI or submit a preprint. Human annotation remains optional
future work.

## Completion rule

Version 0.2.0 is complete for release when its source, sanitized model-judge
results, figures, tables, and paper consistently state that the findings are
model-judge-only and not human-validated. No additional paid API calls or
human annotation are required for this version.
