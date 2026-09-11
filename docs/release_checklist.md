# Public Release Checklist

## Scientific gate

- [x] Author freeze manifest is present and hash checks pass.
- [x] The embedded collection approval matches the public approval record.
- [x] No confirmatory output was inspected before hypotheses and rubric froze.
- [x] Provider failures and exclusions are published.
- [x] Human sample was selected before model-judge labels were inspected.
- [x] Junru Zhu authorized omission of human validation from v0.2.0 on
      2026-09-11.
- [x] Claims are explicitly model-judge-only and not human-validated.
- [ ] Optional future human files, agreement, adjudication, and consensus
      artifacts are published in a later validation release.
- [x] Claims match model-judge effect sizes and confidence intervals.
- [x] The paper says 100 distinct synthetic tasks and does not overstate the
      descriptive pressure comparison.

## Privacy, policy, and secrets

- [x] `rg` finds no API keys, bearer tokens, private URLs, or employer data.
- [x] All model-output dispositions are approved for release.
- [x] Raw request IDs have disposition `removed` and are excluded from public
      artifacts.
- [x] All entities and values remain fictional.

## Software and data

- [x] Dataset checks, tests, preflight, and full-scale validation pass; the
      latest full-scale validation used a fresh timestamped output directory.
- [x] `make release-audit` reports no local errors and `make release-bundle`
      produces a deterministic archive, embedded manifest, and checksum.
- [ ] A clean environment reproduces fixture and confirmatory analysis.
- [x] JSONL files validate and have published SHA-256 hashes.
- [x] The collection approval conforms to its public schema and executable
      config checks.
- [x] The model-verification snapshot validates every config and its hash is
      included in the frozen manifest.
- [x] Figures and LaTeX table regenerate from labeled results.
- [x] The Python release wheel builds and contains all command modules.
- [x] The wheel is built from the audited source ZIP and contains no local
      `.DS_Store`, cache, or bytecode artifacts.
- [x] The paper compiles without overfull boxes and every page is reviewed.
- [x] `CITATION.cff`, `LICENSE`, and `.zenodo.json` are correct.
- [x] Versioned GitHub release notes and `CHANGELOG.md` match the package.

## Authorship and publication

- [x] Author list and order are confirmed; affiliation and contribution text
      remain to be added if required by the submission venue.
- [x] Repository owner/name and public visibility are approved.
- [x] v0.2.0 tag and release notes are approved.
- [x] Explicit GitHub release authorization is recorded.
- [ ] Zenodo archive is created from the exact GitHub release.
- [ ] DOI is inserted into README, citation metadata, and paper.
- [ ] arXiv category, abstract, and source bundle are reviewed.
- [ ] Workshop submission is treated separately from the preprint.

External publication is never performed by the harness.

`make release-audit` validates the source release candidate only. For the
authorized v0.2.0 model-judge-only release, build the final source and
sanitized results artifacts with:

```bash
make model-only-release-all RUN_ID=confirmatory-20260910-v1
make model-only-release-wheel
```

The v0.2.0 approval requires all model-output dispositions to be approved and
raw request IDs to be removed. It does not assert that human validation was
performed. The human-label final publication gate remains available for a
future human-validated release.

- [ ] Run `make model-only-release-all` and `make model-only-release-wheel`.
- [ ] Confirm the source worktree is clean and every packaged source file is
  tracked in the release commit.
- [ ] Inspect the results-bundle manifest and verify 1,800 public responses
  with 1,800 frozen model-judge labels.
- [ ] Confirm the results ZIP contains no request IDs, retry errors, private
  sample key, human annotation files, credentials, local user paths, or private
  execution-environment identifiers.
