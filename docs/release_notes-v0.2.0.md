# Failure-Transparent Agents v0.2.0

**Status:** Result-bearing release candidate; human validation pending

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
- an eight-page LaTeX paper with preliminary model-judge results; and
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
- the paper compiles to eight pages and passes structural and visual PDF
  checks; and
- the package installs in a clean environment and exposes all documented
  commands.

## Important limitations

The full-corpus estimates use a frozen, blinded model judge and remain
preliminary until the preregistered 270-response sample receives two
independent human annotations, disagreement adjudication, and agreement
analysis. Synthetic fixture outputs remain prohibited from scientific use.
The post-freeze human sensitivity implementation authenticates the exact
frozen sample and reports descriptive, sample-conditional intervals only.

Repository publication, Zenodo deposition, DOI insertion, and preprint
submission remain separate authorized actions.

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

After human validation and explicit publication approval, use
`make final-release-all` to create the clean source snapshot and sanitized
scientific-results ZIP. The legacy source-only
`--require-publication-ready` option is not final scientific authorization.
