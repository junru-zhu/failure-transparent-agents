# Failure-Transparent Agents v0.2.0

**Status:** Release candidate; confirmatory collection has not started

This release contains the complete preregistered benchmark and experiment
machinery for measuring unsupported task-completion claims after a required
tool or evidence source fails.

## Included

- 100 semantically distinct synthetic tasks;
- deterministic failure traces for web, attachment, execution, permission,
  and stale-data failures;
- three prompt conditions and provider-neutral direct API adapters;
- bounded cost, retry, provenance, and resumable execution controls;
- blinded model judging and a 270-response dual-human annotation workflow;
- disagreement-only third-review adjudication and consensus labels;
- clustered bootstrap and paired randomization analysis;
- three publication figures and one ablation table generator;
- a six-page LaTeX freeze-candidate paper; and
- deterministic source archive, checksum, and embedded file manifest.

## Validation

- 1,800 synthetic fixture responses and 1,800 fixture labels completed;
- 540 independent fixture annotations produced 270 consensus labels;
- all generated fixture artifacts are marked as unsuitable for scientific
  claims;
- the benchmark contains 20 tasks per failure category and pressure type;
- the paper compiles to six pages and passes structural PDF checks; and
- the package installs in a clean environment and exposes all documented
  commands.

## Important limitations

There are no confirmatory model results in this release candidate. The
synthetic fixture and exploratory Codex outputs validate software paths only.
Do not cite them as evidence for model behavior.

Live collection requires explicit author and budget approval, a signed frozen
manifest, and credentials for all three provider arms. Human validation must
be performed by actual independent annotators. Repository publication,
Zenodo deposition, DOI insertion, and preprint submission require separate
authorization.

## Reproduction

Run:

```bash
make check-dataset
make test
make preflight
make full-scale-validation
make release-audit
make release-bundle
make release-wheel
```

The release bundle contains an embedded `release-manifest.json`; its sibling
`.sha256` file authenticates the archive itself.
