# Failure-Transparent Agents

A reproducible benchmark for measuring whether tool-using language-model agents accurately disclose unavailable tools, missing evidence, denied permissions, and stale data instead of claiming unsupported success.

The repository contains an author-signed, frozen benchmark and complete
experiment pipeline. Its zero-cost fixture provider validates the machinery;
fixture and Codex-pilot results are not evidence about the three confirmatory
model arms. Confirmatory preflight is ready, and paid collection now waits only
for the three provider credentials.

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
real model outputs. A blinded rubric-based judge and human validation are still
required before reporting findings. Codex reports token usage but not a dollar
cost through this adapter, so `estimated_cost_usd` is `null`.

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

## Build a release candidate

```bash
make release-audit
make release-bundle
make release-wheel
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
while still returning `local_release_ready: true`. Publication readiness also
requires the approved freeze and the final public repository URL. Zenodo DOI
insertion is a documented post-publication action.

## Freeze and run

Complete `docs/dataset_review.md` and explicitly approve
`data/confirmatory_approval.json`, then:

```bash
make freeze SIGNER="Junru Zhu"
make confirmatory RUN_ID=confirmatory-20260910-v1
make judge RUN_ID=confirmatory-20260910-v1
make human-sample RUN_ID=confirmatory-20260910-v1
make analyze RUN_ID=confirmatory-20260910-v1
```

The live targets require `OPENAI_API_KEY` and an authorized `AWS_PROFILE`.
The Claude and NVIDIA arms use temporary AWS SigV4 credentials through native
Bedrock InvokeModel, so no bearer API key is stored. All arms enforce config
hashes, call caps, and dollar caps; progress is resumable with
`RESUME=--resume`.

Freezing rejects a pending or incomplete approval record. The approved record
must name the author and MIT license, match every exact provider/model config,
record `us-east-1` for the Claude and NVIDIA arms, match the GPT-5.4-mini judge, and
authorize the $60 primary plus $60 judge caps. Its hash and contents become
part of the frozen manifest.

The human-sample target writes a condition/model-blinded packet and a separate
private key. Two annotators use the resumable terminal workflow independently;
a third reviewer receives only disagreements and blinded annotations. The
finalizer writes the one-consensus-label-per-response file consumed by
`make analyze`.

## Research integrity

- All scenarios are synthetic and use fictional entities.
- Pilot fixture responses must never be reported as empirical model findings.
- Hypotheses and exclusion rules are frozen before paid runs.
- The manifest records author signoff and hashes every collection/scoring config.
- Deviations from the protocol are recorded rather than silently incorporated.
- Raw responses, labels, and analysis code will be released with the paper where provider terms permit.

## Status

- [x] Research protocol drafted
- [x] Offline harness scaffolded
- [x] Synthetic pilot dataset created
- [x] Offline pilot validated
- [x] Gated Codex CLI adapter implemented for unscored live capture
- [x] 100-distinct-task benchmark candidate generated
- [x] Direct OpenAI, Anthropic, and NVIDIA/Bedrock adapters implemented
- [x] Hard budget, call-cap, retry, and resume controls implemented
- [x] Blinded model judge and 270-item human sampler implemented
- [x] Resumable dual-human annotation and blinded adjudication implemented
- [x] Clustered inference, agreement, figures, and LaTeX table implemented
- [x] Full 1,800-response synthetic pipeline validation passed
- [x] Release wheel and GitHub/Zenodo metadata validated
- [x] Six-page LaTeX preprint draft compiled and visually reviewed
- [x] Machine-enforced authorship/model/region/license/budget approval gate
- [x] GitHub/Zenodo release metadata prepared
- [x] Deterministic release archive and metadata audit implemented
- [x] Human annotation rubric reviewed and author-frozen
- [x] API budget approved
- [x] Confirmatory manifest signed
- [x] NVIDIA paid arm complete: 600/600 responses, zero provider failures
- [x] Claude paid arm complete: 600/600 canonical responses
- [ ] OpenAI paid arm complete
- [ ] Human annotation completed
- [ ] Final results inserted into the paper

The completed NVIDIA collection and explicitly exploratory self-judge
analysis are summarized in `docs/nvidia_arm_report.md`. The report does not
substitute those labels for the frozen independent judge or human validation.
The completed Claude collection and cost/recovery audit are summarized in
`docs/claude_arm_report.md`.
