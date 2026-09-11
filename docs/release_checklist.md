# Public Release Checklist

## Scientific gate

- [x] Author freeze manifest is present and hash checks pass.
- [x] The embedded collection approval matches the public approval record.
- [x] No confirmatory output was inspected before hypotheses and rubric froze.
- [x] Provider failures and exclusions are published.
- [x] Human sample was selected before model-judge labels were inspected.
- [ ] Two independent human files, human--human agreement, blinded
      adjudication, and the consensus manifest are published.
- [ ] Agreement is reported for all six labels.
- [x] Preliminary claims match model-judge effect sizes and confidence intervals.
- [x] The paper says 100 distinct synthetic tasks and does not overstate the
      descriptive pressure comparison.

## Privacy, policy, and secrets

- [x] `rg` finds no API keys, bearer tokens, private URLs, or employer data.
- [ ] Provider terms permit release of model outputs.
- [ ] Raw request IDs are reviewed for disclosure risk.
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
- [ ] Git tag and release notes are approved.
- [ ] Zenodo archive is created from the exact GitHub release.
- [ ] DOI is inserted into README, citation metadata, and paper.
- [ ] arXiv category, abstract, and source bundle are reviewed.
- [ ] Workshop submission is treated separately from the preprint.

External publication is never performed by the harness.

`make release-audit` validates the source release candidate only. It does not
substitute for the scientific or authorization checks above. Before creating a
final tag, run:

```bash
make final-publication-gate RUN_ID=<run> \
  HUMAN_FIRST_LABELS=<first-human-file> \
  HUMAN_SECOND_LABELS=<second-human-file>
```

The final gate fails closed until real human labels, six-label agreement,
adjudication/consensus manifests, human sensitivity outputs, request-ID
disposition, provider-output dispositions, version approval, and explicit
GitHub release authorization are present.

- [ ] Run `make final-release-all`, not the legacy source-only
  `--require-publication-ready` option.
- [ ] Confirm the source worktree is clean and every packaged source file is
  tracked in the release commit.
- [ ] Inspect the results-bundle manifest and verify the expected 1,800 public
  labeled responses, or document every provider arm excluded by approval.
- [ ] Confirm the results ZIP contains no request IDs, retry errors, private
  sample key, independent annotator files, credentials, local user paths, or
  private execution-environment identifiers.
