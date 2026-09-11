# Failure-Transparent Agents

A reproducible benchmark for measuring whether tool-using language-model agents accurately disclose unavailable tools, missing evidence, denied permissions, and stale data instead of claiming unsupported success.

The repository contains an author-signed, frozen benchmark and complete
experiment pipeline. All 1,800 confirmatory primary responses and all 1,800
frozen model-judge labels have been collected. The full-corpus statistical
analysis is complete. Version 0.2.0 is an author-approved model-judge-only
release and is not human-validated. On 2026-09-11, author Junru Zhu decided
to omit human validation from this release while preserving the blinded
270-response workflow as an optional future validation path.

## Research question

When an agent cannot complete a task because a required tool or input failed, how often does it:

1. falsely claim completion,
2. invent details that require unavailable evidence,
3. disclose the limitation, and
4. offer a useful recovery action?

The experiment compares three conditions:

- `baseline`: ordinary helpful-assistant instruction;
- `transparency`: explicit failure-disclosure instruction; and
- `evidence_contract`: a structured contract requiring status, evidence, limitation, and next action.

See `docs/research_protocol.md` for hypotheses, metrics, clustering, and the
confirmatory design; `docs/dataset_card.md` for scope and limitations; and
`docs/reproduction.md` for the end-to-end commands.

## Confirmatory benchmark

- 100 semantically distinct tasks in JSONL
- 20 tasks per failure category
- 20 tasks per pressure type
- four tasks in every category-pressure cell
- five failure categories
- three instruction conditions
- three provider/model families
- two repetitions
- 1,800 primary responses

Each task receives one pressure assignment. Pressure comparisons are balanced
descriptive analyses; the primary instruction comparisons remain paired within
task.

## Run the offline pilot

Requirements: Python 3.11 or newer. The pilot has no third-party runtime dependencies.

```bash
make test
make pilot
```

Equivalent commands:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m failure_transparent_agents \
  --dataset data/pilot_scenarios.jsonl \
  --output-dir results/pilot \
  --repeats 2
```

Generated files:

- `results/pilot/raw_results.jsonl`: one record per scenario, condition, and repetition;
- `results/pilot/summary.json`: aggregate rates and bootstrap confidence intervals; and
- `results/pilot/manifest.json`: run configuration and a warning that fixture output is not a model result.

## Capture live Codex outputs

The Codex adapter starts separate ephemeral `codex exec` sessions. It does not
connect to an existing interactive conversation. Live execution is opt-in,
requires an exact model identifier, and requires a call cap large enough for
the requested matrix.

Run a three-call smoke test:

```bash
PYTHONPATH=src python3 -m failure_transparent_agents \
  --provider codex \
  --model <exact-model-id> \
  --allow-live \
  --max-calls 3 \
  --scenario-limit 1 \
  --repeats 1 \
  --workers 1 \
  --dataset data/pilot_scenarios.jsonl \
  --output-dir results/codex-smoke
```

The adapter invokes Codex without a shell, uses ephemeral sessions, loads the
local provider configuration needed for managed authentication, ignores agent
rules, and requests a read-only sandbox. If the agent nevertheless invokes a
command, file operation, MCP tool, or web search, the call is rejected because
the supplied synthetic tool trace must remain its only evidence.

For larger approved runs, `--workers` enables bounded parallel calls while
preserving deterministic output order. The live call cap remains global across
all workers.

Live records deliberately contain `"evaluation": null`. The current heuristic
evaluator recognizes planted fixture strings only and must not be used to score
real model outputs. Benchmark findings in this release use the separate frozen,
blinded rubric-based model judge and must be described as not human-validated.
Codex reports token usage but not a dollar cost through this adapter, so
`estimated_cost_usd` is `null`.

## Validate and preflight

```bash
make check-dataset
make test
make preflight
make full-scale-validation
```

The preflight makes zero network calls. The current plan contains 1,800 primary
responses, at most 3,600 attempts, $60 in primary hard caps, and a separate
$60 model-judge cap. The generated plan reports the current conservative cost
bound. It also validates `data/model_verification.json`, a dated official-doc
snapshot binding each exact model ID, interface, region, price, and parameter
constraint to its config hash.

`make full-scale-validation` exercises the exact 1,800-response cardinality,
the 1,800 model labels, two independent annotations of the deterministic
270-response human sample, blinded adjudication, consensus labels, agreement,
bootstrap analysis, figures, and LaTeX table using synthetic fixtures. Its
manifest sets `scientific_use_prohibited: true`; these artifacts validate
software only and are never model findings.

## Build the v0.2.0 release

```bash
make release-audit
make model-only-release-all RUN_ID=confirmatory-20260910-v1
make model-only-release-wheel
```

The audit checks version, author, license, dataset hash, required public
artifacts, and common credential shapes. The bundle is deterministic and
contains an embedded SHA-256 manifest; local results, caches, build products,
and private sampling keys outside the public source tree are excluded. A
sibling checksum and machine-readable report are written to `dist/`.
The wheel target rebuilds from the exact audited ZIP in a temporary clean
tree, normalizes timestamps, and rejects `.DS_Store`, bytecode, and cache
artifacts before copying the wheel into `dist/`. Its selected interpreter must
have the pinned build backend available; override it with
`WHEEL_PYTHON=python3.11` when needed.

Before author freeze, the audit is expected to report publication blockers
while still returning `local_release_ready: true`. For v0.2.0, publication
authorization records author Junru Zhu, approves all model-output
dispositions, and requires removal of raw request IDs. Zenodo DOI insertion
remains a separate post-publication action.

## Freeze and run

Complete `docs/dataset_review.md` and explicitly approve
`data/confirmatory_approval.json`, then:

```bash
make freeze SIGNER="Junru Zhu"
make confirmatory RUN_ID=confirmatory-20260910-v1
make judge RUN_ID=confirmatory-20260910-v1
make analyze RUN_ID=confirmatory-20260910-v1
```

The primary live targets require an authorized `AWS_PROFILE`; the independent
judge additionally requires `OPENAI_API_KEY`.
The Claude and NVIDIA arms use temporary AWS SigV4 credentials through native
Bedrock InvokeModel, so no bearer API key is stored. All arms enforce config
hashes, call caps, and dollar caps; progress is resumable with
`RESUME=--resume`.

Freezing rejects a pending or incomplete approval record. The approved record
must name the author and MIT license, match every exact provider/model config,
record `us-east-1` for the Claude and NVIDIA arms, match the GPT-5.4-mini judge, and
authorize the $60 primary plus $60 judge caps. Its hash and contents become
part of the frozen manifest.

The full v0.2.0 analysis uses all 1,800 frozen model-judge labels. No human
annotations, human--human agreement, model--human agreement, or human-label
sensitivity results are claimed for this release.

The human-sample and annotation commands remain available as an optional
future validation workflow. If used later, they create a condition/model-
blinded packet, independent labels, disagreement adjudication, consensus
labels, agreement estimates, and descriptive human-label sensitivity
intervals. Those future results are not part of v0.2.0.

```bash
make human-sample RUN_ID=confirmatory-20260910-v1
```

For the authorized v0.2.0 release, `make model-only-release-all` builds the
final source ZIP and sanitized model-judge-only results ZIP.
`make model-only-release-wheel` builds the wheel from that final source ZIP.
All model-output dispositions are approved for release. Raw provider request
IDs are removed, as are retry-error details, the private sample key,
credentials, local paths, and private execution-environment identifiers.

## Research integrity

- All scenarios are synthetic and use fictional entities.
- Pilot fixture responses must never be reported as empirical model findings.
- Hypotheses and exclusion rules are frozen before paid runs.
- The manifest records author signoff and hashes every collection/scoring config.
- Deviations from the protocol are recorded rather than silently incorporated.
- Model outputs, frozen model-judge labels, and analysis code are approved for
  release; raw provider request IDs are removed.
- All empirical claims must state that v0.2.0 is model-judge-only and not
  human-validated.

## Status

- [x] Research protocol drafted
- [x] Offline harness scaffolded
- [x] Synthetic pilot dataset created
- [x] Offline pilot validated
- [x] Gated Codex CLI adapter implemented for unscored live capture
- [x] 100-distinct-task benchmark candidate generated
- [x] OpenAI-compatible and native Bedrock adapters implemented
- [x] Hard budget, call-cap, retry, and resume controls implemented
- [x] Blinded model judge and 270-item human sampler implemented
- [x] Resumable dual-human annotation and blinded adjudication implemented
- [x] Clustered inference, agreement, figures, and LaTeX table implemented
- [x] Full 1,800-response synthetic pipeline validation passed
- [x] Release wheel and GitHub/Zenodo metadata validated
- [x] Eight-page LaTeX preprint draft compiled and visually reviewed
- [x] Machine-enforced authorship/model/region/license/budget approval gate
- [x] GitHub/Zenodo release metadata prepared
- [x] Deterministic release archive and metadata audit implemented
- [x] Fail-closed final publication gate and sanitized results builder implemented
- [x] Human annotation rubric reviewed and author-frozen
- [x] API budget approved
- [x] Confirmatory manifest signed
- [x] NVIDIA paid arm complete: 600/600 responses, zero provider failures
- [x] Claude paid arm complete: 600/600 canonical responses
- [x] OpenAI paid arm complete: 600/600 canonical responses
- [x] Frozen GPT-5.4-mini judge complete: 1,800/1,800 labels
- [x] Full-corpus clustered analysis, three figures, and ablation table complete
- [x] Model-judge-only v0.2.0 publication authorized by Junru Zhu
- [x] All model-output dispositions approved; request IDs set to removed
- [x] Model-judge results inserted into the paper
- [ ] Optional future human annotation and validation

The completed NVIDIA collection and explicitly exploratory self-judge
analysis are summarized in `docs/nvidia_arm_report.md`. The report does not
substitute those labels for the frozen independent judge.
The completed Claude collection and cost/recovery audit are summarized in
`docs/claude_arm_report.md`.
The completed OpenAI collection and retry/cost audit are summarized in
`docs/openai_arm_report.md`.
The frozen judge, recovery audit, cost, and full-corpus estimates are
summarized in `docs/model_judge_report.md`. They are released as
model-judge-only findings and are not human-validated.
