# Contributing

Contributions that make failure transparency easier to measure, reproduce, or
adopt are welcome.

## High-impact contributions

- **Run a new model.** Reuse the frozen 100-task benchmark and submit sanitized
  results with the exact model ID, provider route, parameters, date, and cost.
- **Add a failure task.** Propose a fictional task that requires unavailable
  evidence and has a feasible recovery path.
- **Replicate the findings.** Run the benchmark through another provider,
  region, or open-weight serving stack.
- **Improve measurement.** Add human annotation, judge-robustness checks, or a
  provider-neutral adapter without weakening provenance.
- **Improve onboarding.** Documentation, examples, and platform support are
  valuable contributions.

Use the GitHub issue templates before beginning a large contribution. They make
it easier to agree on scope and preserve comparability.

## Local setup

The runtime uses only the Python standard library.

```bash
git clone https://github.com/junru-zhu/failure-transparent-agents.git
cd failure-transparent-agents
make demo
make test
make check-dataset
```

Python 3.11 or newer is supported; repository validation uses Python 3.12.

## Pull requests

1. Keep API keys, AWS credentials, request IDs, and private paths out of every
   commit.
2. Add or update tests for behavioral changes.
3. Run `make test`, `make check-dataset`, and `make release-audit`.
4. State whether the change affects frozen scenarios, prompts, labels,
   statistical estimates, or only presentation.
5. Do not describe deterministic fixture output as empirical model evidence.

Changes to frozen scientific artifacts must receive a new version and a
deviation-log entry. Presentation and documentation improvements must not
silently change empirical claims.

## Submitting a new model result

New result submissions should include:

- exact model and resolved snapshot, when available;
- API or serving interface and region;
- prompt/config hashes;
- output-token limit, temperature, reasoning settings, and retries;
- successful response and provider-error counts;
- sanitized labeled results or a reproducible path to generate them;
- latency, token, and estimated-cost summaries;
- a clear statement of whether labels are human, model-judge, or both.

Results are not automatically merged into a headline leaderboard. The
maintainer first checks comparability, provenance, and licensing.

## Research integrity

The current v0.2.0 findings use a frozen model judge and are not
human-validated. Contributions must preserve that limitation unless they add
real human validation.
