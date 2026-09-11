# Failure-Transparent Agents v0.2.0

**Status:** Authorized model-judge-only release; not human-validated

This release contains the complete preregistered benchmark and experiment
machinery for measuring unsupported task-completion claims after a required
tool or evidence source fails.

## Included

- 100 semantically distinct synthetic tasks;
- deterministic failure traces for web, attachment, execution, permission,
  and stale-data failures;
- three prompt conditions and provider-neutral direct API adapters;
- bounded cost, retry, provenance, and resumable execution controls;
- blinded model judging and an optional future 270-response dual-human
  annotation workflow;
- optional disagreement-only third-review adjudication and consensus tooling;
- clustered bootstrap and paired randomization analysis;
- three publication figures and one ablation table generator;
- an eight-page LaTeX paper with model-judge-only results;
- deterministic source archive, checksum, and embedded file manifest; and
- a fail-closed final scientific publication gate with separate clean-source
  and sanitized scientific-results archive builders.

## Validation

- 1,800 synthetic fixture responses and 1,800 fixture labels completed;
- 540 independent fixture annotations produced 270 consensus labels;
- all generated fixture artifacts are marked as unsuitable for scientific
  claims;
- the benchmark contains 20 tasks per failure category and pressure type;
- all 1,800 confirmatory primary responses and frozen model-judge labels
  completed;
- all model-output dispositions are approved for release and raw provider
  request IDs are removed from the public results bundle;
- the paper compiles to eight pages and passes structural and visual PDF
  checks; and
- the package installs in a clean environment and exposes all documented
  commands.

## Important limitations

The full-corpus estimates use a frozen, blinded model judge. They are
model-judge-only and not human-validated. No human annotations, human--human
agreement, model--human agreement, or human-label sensitivity estimates are
reported in v0.2.0. This limits confidence in the absolute label rates and
leaves open the possibility of systematic model-judge bias.

On 2026-09-11, author Junru Zhu explicitly authorized this release while
omitting human validation for this version. The frozen human-sample workflow
is retained as an optional future validation path. Synthetic fixture outputs
remain prohibited from scientific use.

GitHub publication is authorized. Zenodo deposition, DOI insertion, preprint
submission, and workshop submission remain separate actions.

## Reproduction

Run:

```bash
make check-dataset
make test
make preflight
make full-scale-validation
make release-audit
make model-only-release-all RUN_ID=confirmatory-20260910-v1
make model-only-release-wheel
```

The release bundle contains an embedded `release-manifest.json`; its sibling
`.sha256` file authenticates the archive itself.

For v0.2.0, `make model-only-release-all` creates the final source ZIP and
sanitized scientific-results ZIP; `make model-only-release-wheel` builds the
wheel from the final source ZIP. The approval record authorizes all
model-output dispositions and requires raw request IDs to be removed. The
human-validation workflow and `make final-release-all` remain available for a
future, human-validated release.
