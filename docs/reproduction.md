# Reproduction Guide

Requirements: Python 3.12, provider credentials, and an author-frozen
manifest. Runtime code has no third-party Python dependencies.

## 1. Validate without network access

```bash
make check-dataset
make test
make preflight
make full-scale-validation
```

`make preflight` makes zero network calls. It validates the 1,800-response
matrix, retries, call caps, prices, and hard dollar ceilings.

`make full-scale-validation` also makes zero network calls. It creates 1,800
synthetic responses, 1,800 synthetic model labels, a 270-item human-label
fixture, agreement metrics, confidence intervals, three figures, and the
LaTeX ablation table. The output manifest explicitly prohibits scientific use.
In a complete 1,800-response matrix, the human sample contains six responses
from each model--condition--category stratum and 54 from each pressure type.
The command refuses to overwrite prior artifacts; choose a fresh directory
with `VALIDATION_OUTPUT_DIR=results/full-scale-validation-v2` when rerunning.

## 2. Record approval and freeze after review

Review `data/confirmatory_approval.json`, whose public shape is documented by
`schemas/collection_approval.schema.json`. Only after explicit authorization,
set:

```json
{
  "status": "approved",
  "approved_by": "Junru Zhu",
  "approved_at": "<timezone-aware ISO-8601 timestamp>",
  "data_collection_authorized": true
}
```

Do not alter the recorded model, region, judge, author, license, or budget
fields unless the scientific plan is intentionally revised.

```bash
PYTHONPATH=src python3.12 -m failure_transparent_agents.freeze \
  --signer "Junru Zhu"
```

Do not freeze until `docs/dataset_review.md` is complete. Freeze validates the
approval against all provider and judge configs, embeds it in the manifest,
and records its SHA-256. Any change afterward requires a new candidate and a
deviation-log entry.

## 3. Supply credentials

Set these outside the repository:

```text
AWS_PROFILE
OPENAI_API_KEY
```

Never place the OpenAI API key or AWS credential material in JSON configs,
shell scripts, notebooks, logs, or commits. `AWS_PROFILE` contains only the
local profile name; the AWS CLI resolves temporary SigV4 credentials outside
the repository for all three primary arms. `OPENAI_API_KEY` is required only
for the separate GPT-5.4-mini judge.

## 4. Run the three primary arms

Choose a stable run prefix:

```bash
export FTA_RUN_ID=confirmatory-20260910-v1
make confirmatory RUN_ID="$FTA_RUN_ID"
```

The Make target runs all three arms with the frozen configs. Each output
directory is resumable; rerun with `RESUME=--resume` after an interruption.

## 5. Run blinded model judging

```bash
make judge RUN_ID="$FTA_RUN_ID"
```

Judge outputs preserve raw JSON, schema failures, retries, token usage, latency,
request IDs, and spend. The tested model and condition are omitted from each
judge prompt.

## 6. Optional future human validation

```bash
make human-sample RUN_ID="$FTA_RUN_ID"
```

Version 0.2.0 does not include human annotations and is not human-validated.
The following workflow is retained for an optional future validation release;
it is not required to reproduce the v0.2.0 model-judge-only findings.

Give annotators only `human_sample_blinded.jsonl`. Keep
`human_sample_key.jsonl` hidden until labels are final.

Two annotators label the same 270 packets independently:

```bash
make annotate-human RUN_ID="$FTA_RUN_ID" ANNOTATOR_ID="human-a"
make annotate-human RUN_ID="$FTA_RUN_ID" ANNOTATOR_ID="human-b"
```

The CLI validates verbatim evidence spans, saves after every item, and resumes
without re-prompting completed responses. Then prepare blinded disagreements:

```bash
make prepare-adjudication RUN_ID="$FTA_RUN_ID" \
  FIRST_LABELS="results/$FTA_RUN_ID/human/human_labels-human-a.jsonl" \
  SECOND_LABELS="results/$FTA_RUN_ID/human/human_labels-human-b.jsonl"
```

A third reviewer labels only the disagreement packet:

```bash
make annotate-adjudication RUN_ID="$FTA_RUN_ID" \
  ADJUDICATOR_ID="human-adjudicator"
```

If `adjudication_manifest.json` reports zero disagreement responses, skip this
step.

Finalize one consensus label per response:

```bash
make finalize-adjudication RUN_ID="$FTA_RUN_ID" \
  FIRST_LABELS="results/$FTA_RUN_ID/human/human_labels-human-a.jsonl" \
  SECOND_LABELS="results/$FTA_RUN_ID/human/human_labels-human-b.jsonl" \
  ADJUDICATED_LABELS="results/$FTA_RUN_ID/human/human_labels-adjudicator.jsonl"
```

When there are zero disagreements, omit `ADJUDICATED_LABELS`.

This writes `results/$FTA_RUN_ID/human/human_labels.jsonl`, plus
human--human agreement and hash-addressed adjudication manifests.

## 7. Analyze

```bash
make analyze RUN_ID="$FTA_RUN_ID"
```

The full-corpus target uses the complete frozen model-judge label set and
produces the v0.2.0 results. Outputs include:

- joined labeled JSONL;
- rates and paired comparisons as CSV;
- agreement JSON;
- efficiency CSV;
- three standalone SVG figures; and
- a LaTeX ablation table.

The default analysis uses 10,000 hierarchical bootstrap draws and 100,000
sign-flip draws with seed `20260910`.

If optional real human labels are collected later, the separate
human-sensitivity target uses only the 270 human-consensus
responses. It first requires an exact ID and hash match against the frozen
`human_sample_key.jsonl` and `human_sample_manifest.json`. Because the
stratified sample does not necessarily retain complete response-level pairs
across conditions, it reports post-freeze descriptive condition differences
with a base-task cluster bootstrap and no confirmatory p-values. The intervals
are conditional on the selected sample and do not reproduce the original
without-replacement sampling stage. It also requires complete 270/270
agreement coverage for all six labels against the frozen model judge.

```bash
make human-sensitivity RUN_ID="$FTA_RUN_ID"
```

## 8. Audit and build the release artifacts

```bash
make release-audit
make model-only-release-all RUN_ID="$FTA_RUN_ID"
make model-only-release-wheel
```

The audit validates metadata consistency, the benchmark hash, the public file
allowlist, and common secret shapes. The deterministic ZIP includes an
embedded per-file manifest; a sibling `.sha256` file authenticates the
archive. `results/`, caches, build products, and local environment files are
excluded.

Before freeze, `local_release_ready` can be true while
`publication_ready` remains false. The remaining publication blockers and
post-publication DOI updates are listed explicitly in the JSON report.

For v0.2.0, author Junru Zhu provided explicit GitHub publication
authorization on 2026-09-11. All model-output dispositions are approved and
the request-ID disposition is `removed`. Build the final source and
scientific-results artifacts with:

```bash
make model-only-release-all RUN_ID="$FTA_RUN_ID"
make model-only-release-wheel
```

The model-only results bundle includes authorized model responses, frozen
model-judge labels, analysis tables, and figures. It never includes human
labels, the private sample key, raw provider request IDs, retry errors,
credentials, local paths, or private execution-environment identifiers.

The separate `make final-release-all` path remains available for a future
release after real human labels, agreement, and sensitivity outputs exist.

## 9. Build the release wheel

`make model-only-release-wheel` is the v0.2.0 release build. It builds from
the exact audited final source ZIP in a temporary clean tree, sets a stable
`SOURCE_DATE_EPOCH`, verifies the console scripts, and rejects local debris
before writing the wheel and checksum to `dist/`. The selected interpreter
must have `setuptools==75.8.0`; use
`make model-only-release-wheel WHEEL_PYTHON=python3.11` if that is the
prepared build environment.

For a non-release development wheel only, run:

```bash
python3.12 -m pip wheel --no-deps --wheel-dir dist .
```

The build backend is declared in `pyproject.toml`; runtime code has no
third-party dependencies.

## 10. Compile the paper

With Tectonic installed:

```bash
tectonic paper/main.tex --outdir paper --keep-logs
qpdf --check paper/main.pdf
```

The v0.2.0 source compiles to eight pages. Before submission, inspect every
rendered page after any paper change.
