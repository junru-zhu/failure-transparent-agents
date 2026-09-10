# Public Release Checklist

## Scientific gate

- [ ] Author freeze manifest is present and hash checks pass.
- [ ] The embedded collection approval matches the public approval record.
- [ ] No confirmatory output was inspected before hypotheses and rubric froze.
- [ ] Provider failures and exclusions are published.
- [ ] Human sample was selected before model-judge labels were inspected.
- [ ] Two independent human files, human--human agreement, blinded
      adjudication, and the consensus manifest are published.
- [ ] Agreement is reported for all six labels.
- [ ] Claims match effect sizes and confidence intervals.
- [ ] The paper says 100 distinct synthetic tasks and does not overstate the
      descriptive pressure comparison.

## Privacy, policy, and secrets

- [ ] `rg` finds no API keys, bearer tokens, private URLs, or employer data.
- [ ] Provider terms permit release of model outputs.
- [ ] Raw request IDs are reviewed for disclosure risk.
- [ ] All entities and values remain fictional.

## Software and data

- [ ] `make check-dataset`, `make test`, `make preflight`, and
      `make full-scale-validation` pass.
- [ ] `make release-audit` reports no local errors and `make release-bundle`
      produces a deterministic archive, embedded manifest, and checksum.
- [ ] A clean environment reproduces fixture and confirmatory analysis.
- [ ] JSONL files validate and have published SHA-256 hashes.
- [ ] The collection approval conforms to its public schema and executable
      config checks.
- [ ] The model-verification snapshot validates every config and its hash is
      included in the frozen manifest.
- [ ] Figures and LaTeX table regenerate from labeled results.
- [ ] The Python release wheel builds and contains all command modules.
- [ ] The wheel is built from the audited source ZIP and contains no local
      `.DS_Store`, cache, or bytecode artifacts.
- [ ] The paper compiles without overfull boxes and every page is reviewed.
- [ ] `CITATION.cff`, `LICENSE`, and `.zenodo.json` are correct.
- [ ] Versioned GitHub release notes and `CHANGELOG.md` match the package.

## Authorship and publication

- [ ] Author list, order, affiliations, and contributions are confirmed.
- [ ] Repository owner/name and public visibility are approved.
- [ ] Git tag and release notes are approved.
- [ ] Zenodo archive is created from the exact GitHub release.
- [ ] DOI is inserted into README, citation metadata, and paper.
- [ ] arXiv category, abstract, and source bundle are reviewed.
- [ ] Workshop submission is treated separately from the preprint.

External publication is never performed by the harness.
