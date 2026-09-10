# Reproduction Guide

Requirements: Python 3.12, three provider credentials, and an author-frozen
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
OPENAI_API_KEY
ANTHROPIC_API_KEY
AWS_PROFILE
```

Never place API keys or AWS credential material in JSON configs, shell
scripts, notebooks, logs, or commits. `AWS_PROFILE` contains only the local
profile name; the AWS CLI resolves temporary SigV4 credentials outside the
repository.

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

## 6. Select and annotate the human sample

```bash
make human-sample RUN_ID="$FTA_RUN_ID"
```

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

Outputs include:

- joined labeled JSONL;
- rates and paired comparisons as CSV;
- agreement JSON;
- efficiency CSV;
- three standalone SVG figures; and
- a LaTeX ablation table.

The default analysis uses 10,000 hierarchical bootstrap draws and 100,000
sign-flip draws with seed `20260910`.

## 8. Audit and build the release candidate

```bash
make release-audit
make release-bundle
make release-wheel
```

The audit validates metadata consistency, the benchmark hash, the public file
allowlist, and common secret shapes. The deterministic ZIP includes an
embedded per-file manifest; a sibling `.sha256` file authenticates the
archive. `results/`, caches, build products, and local environment files are
excluded.

Before freeze, `local_release_ready` can be true while
`publication_ready` remains false. The remaining publication blockers and
post-publication DOI updates are listed explicitly in the JSON report.

## 9. Build the release wheel

`make release-wheel` is the supported release build. It builds from the exact
audited candidate ZIP in a temporary clean tree, sets a stable
`SOURCE_DATE_EPOCH`, verifies the console scripts, and rejects local debris
before writing the wheel and checksum to `dist/`. The selected interpreter
must have `setuptools==75.8.0`; use
`make release-wheel WHEEL_PYTHON=python3.11` if that is the prepared build
environment.

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

The freeze-candidate source compiles to six pages. Before submission, inspect
every rendered page again after replacing result placeholders with final
figures and tables.
