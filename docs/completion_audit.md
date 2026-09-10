# Completion Audit

**Audit date:** 2026-09-10  
**Overall status:** Author-approved benchmark frozen and ready for live
collection; confirmatory research and external publication incomplete

This document maps every requested deliverable to current authoritative
evidence. Synthetic fixture and exploratory Codex outputs are never treated as
confirmatory model results.

## Requirement-by-requirement status

| Requirement | Status | Authoritative evidence | Remaining work |
|---|---|---|---|
| Public 100-task JSONL benchmark | Frozen locally | `data/confirmatory_scenarios.jsonl`; 100 rows; SHA-256 `4bb2f63bc0bf03570021246943d4c1d871d0fe29e78edcdcfe740c0f3ee716ea`; signed `data/confirmatory_manifest.json` | Push the public repository |
| Annotation guide | Frozen locally | `docs/annotation_guide.md`; strict label schema and 61 passing tests | None before collection |
| Deterministic failed-tool simulator | Complete locally | `src/failure_transparent_agents/simulator.py`; replay and wrong-tool tests | None before collection |
| Provider-neutral evaluation harness | Complete locally | Direct OpenAI Responses, Anthropic Messages, and Bedrock OpenAI-compatible adapters; retry, resume, call, spend, and provenance controls | Credentials and authorized live execution |
| Exact model and pricing selection | Verified and approved | `data/model_verification.json`; official-source/config hash checks pass for four primary/judge configs; approval embedded in the frozen manifest | None before collection |
| One-command reproduction | Complete locally | `Makefile`, `docs/reproduction.md`, twelve installed console commands; repository URL set to `junru-zhu/failure-transparent-agents` | Push the public repository |
| Complete 1,800-response execution path | Validated with fixtures only | `results/full-scale-validation-v4/validation_manifest.json`: 1,800 responses and labels | Run the three real provider arms |
| Labeled confirmatory result set | Not achieved | No `results/confirmatory-*` primary result tree exists | 1,800 real responses and 1,800 blinded model-judge labels |
| Human validation and agreement | Workflow complete; real labels missing | Dual annotation, disagreement-only adjudication, consensus, and agreement code; fixture run produced 540 initial and 270 consensus labels | Two real independent annotators and a third reviewer for disagreements |
| Bootstrap intervals and primary tests | Implementation complete; empirical estimates missing | Hierarchical bootstrap, paired sign-flip tests, Holm correction, rates, comparisons, and fixture outputs | Rerun analysis on real labels |
| Three figures and ablation table | Generators complete; empirical figures missing | `analysis.py` and fixture SVG/LaTeX outputs | Regenerate from confirmatory labels |
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

The environment also lacks `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and
`AWS_BEARER_TOKEN_BEDROCK`.

## Decisions and inputs still required

Before paid collection:

1. Set the three credentials outside the repository.
2. Run credential smoke tests, then start the resumable provider arms.

Before public release:

1. Authenticate GitHub and push the approved public repository.
2. Confirm the eventual version tag after confirmatory results are inserted.
3. Approve Zenodo deposition and later arXiv submission as separate external
   actions.

## Completion rule

The research objective is not complete until real provider outputs, blinded
model labels, real human consensus labels, empirical analysis, final paper
results, and the authorized public archive exist and have been verified.
