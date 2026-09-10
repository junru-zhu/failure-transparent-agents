# Dataset Card: Failure-Transparent Agents

## Summary

`data/confirmatory_scenarios.jsonl` is a synthetic benchmark for user-visible
behavior after a required tool, input, permission, or data-freshness condition
fails.

| Property | Value |
|---|---:|
| Semantic tasks | 100 |
| Pressure types | 5 |
| Tasks | 100 |
| Failure categories | 5 |
| Unique user requests | 100 |
| Deterministic tool traces | 100 |
| Current candidate SHA-256 | `4bb2f63bc0bf03570021246943d4c1d871d0fe29e78edcdcfe740c0f3ee716ea` |

The 100 rows are semantically distinct synthetic tasks. Each task receives one
of neutral, expected-answer, urgency, forced-choice, or conceal-failure
pressure. Analyses cluster repetitions and instruction conditions on
`base_task_id`.

## Intended uses

- Measure false completion claims after a visible prerequisite failure.
- Measure concrete fabrication requiring unavailable evidence.
- Compare failure-transparency instructions and structured evidence contracts.
- Test sensitivity to user pressure.
- Validate agent-monitoring and guardrail evaluation pipelines.

## Out-of-scope uses

- Ranking general model intelligence or safety.
- Estimating real-world hallucination prevalence.
- Evaluating hidden chain-of-thought.
- Testing permission bypass, exploitation, or live private systems.
- Treating the planted claims as factual knowledge questions.

## Construction

Every row contains:

- a fictional user request;
- a deterministic failed-tool observation;
- required evidence;
- two planted unsupported claims;
- a feasible recovery hint; and
- safe partial help that remains possible.

Category/status consistency and stale-date arithmetic are validated. The
generator guarantees 20 rows per category, 20 per pressure type, four tasks in
every category-pressure cell, and 100 unique task and tool-trace identifiers.

## Data characteristics

The benchmark uses fictional companies, products, values, files, APIs, and
events. It contains no personal data, employer data, copyrighted documents, or
real credentials. Prompts are English-only and mostly short, so results may
not generalize to other languages, cultures, or long contexts.

## Known limitations

- Twenty curated tasks per category still provide limited domain coverage.
- Pressure comparisons can be confounded by task content because pressure is
  balanced across distinct tasks rather than randomized within identical
  content.
- Tool failures are one-step and deterministic.
- No partial successes, conflicting sources, or multi-tool recovery plans are
  included.
- Values planted in expected-answer prompts may make fabrication unusually
  easy to identify.
- The benchmark evaluates reporting after failure, not whether an agent
  correctly detects subtle tool corruption.

## Versioning

The generator is `scripts/generate_confirmatory_dataset.py`. The candidate
manifest remains unfrozen until author review. Freezing records the dataset,
protocol, rubric, prompt, config, source, authorship/license, and explicit
collection-approval hashes. Any content change after freeze requires a new
candidate version and deviation-log entry.
