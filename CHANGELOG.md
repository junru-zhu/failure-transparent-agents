# Changelog

All notable public changes are recorded here. The project uses semantic
versioning for software artifacts and a separate dated candidate version for
the benchmark protocol.

## 0.3.0 - 2026-09-12

### Added

- Post-confirmatory evaluation of Amazon Nova Micro, Meta Llama 3.1 8B
  Instruct, and Mistral Ministral 8B 3.0.
- Unified six-model analysis over 3,600 responses using GPT-5.6 Luna, with
  judge-sensitivity results against the frozen GPT-5.4-mini labels.
- Deterministic sanitized six-model results archive with all response rows,
  model-judge labels, aggregate tables, figures, audit manifests, and
  per-file hashes.
- Six-model IEEE and INSAI/Springer paper revisions with regenerated vector
  figures and explicit confirmatory-versus-post-confirmatory reporting.

### Validation

- All six model arms contain 600/600 successful responses.
- The unified result set contains 3,600 unique responses and 3,600 valid
  model-judge labels.
- Provider request IDs, retry error details, credentials, local paths, and
  private execution-environment identifiers are excluded from public bundles.
- Version 0.3.0 remains model-judge-only and is not human-validated.

## 0.2.0 - 2026-09-11

### Added

- 100-task confirmatory benchmark candidate with five failure categories and
  five balanced pressure types.
- Deterministic failed-tool simulator and direct OpenAI, Anthropic, and
  NVIDIA-on-Bedrock adapters.
- Hard call and dollar caps, retry provenance, interruption-safe resume, and
  offline preflight.
- Strict blinded model judging and an optional future workflow for balanced
  dual-human annotation, blinded adjudication, and consensus labels.
- Hierarchical bootstrap intervals, paired randomization tests, Holm
  correction, efficiency reporting, three SVG figures, and a LaTeX table.
- Eight-page result-bearing paper and release metadata for GitHub and Zenodo.
- Deterministic release audit and source archive with embedded file hashes.
- Post-freeze authenticated human-sensitivity analysis, fail-closed final
  publication gate, clean-commit source release, and sanitized results bundle.
- Author-approved model-judge-only results release with all model-output
  dispositions approved and raw request IDs removed.

### Validation

- Full 1,800-response fixture execution is successful.
- Fixture outputs remain explicitly prohibited from scientific use.
- Confirmatory collection completed for all three model arms: 1,800/1,800
  canonical responses.
- Frozen GPT-5.4-mini judging completed with 1,800/1,800 schema-valid labels.
- Full-corpus clustered analysis, three figures, and the result-bearing paper
  are complete.
- Junru Zhu authorized publication on 2026-09-11 without human annotation for
  this version. Version 0.2.0 is model-judge-only and not human-validated;
  human agreement and sensitivity analysis remain optional future work.
