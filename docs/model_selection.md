# Model Selection and Pricing Snapshot

**Snapshot date:** 2026-09-10  
**Status:** Candidate configuration; author and budget approval required

The machine-readable companion is `data/model_verification.json` and its
public schema is `schemas/model_verification.schema.json`. On 2026-09-10, all
four primary/judge configs were rechecked against the official sources below.
Preflight validates the exact config hashes, model IDs, interfaces, region,
prices, and documented parameter constraints. Freeze records the snapshot
hash so it cannot change silently after signoff.

## Selection principles

The confirmatory experiment uses one current, economically practical model from
each requested family. Models are treated as heterogeneous replications, not a
leaderboard. Exact model IDs, provider endpoints, prices, and configuration
file hashes are recorded in every run manifest.

The selected candidates are:

| Family | Candidate | Interface |
|---|---|---|
| OpenAI | `gpt-5.6-terra` | OpenAI Responses API |
| Anthropic | `claude-sonnet-5` | Anthropic Messages API |
| NVIDIA/open weight | `nvidia.nemotron-super-3-120b` | Amazon Bedrock OpenAI-compatible Chat Completions |

## Rationale

`gpt-5.6-terra` is OpenAI's balanced current model. The arm sets reasoning
effort to `none` so the benchmark measures a direct response to the visible
failed-tool evidence and does not spend the short output budget on hidden
reasoning tokens.

`claude-sonnet-5` is Anthropic's current speed/intelligence balance and has a
pinned dateless API model ID. Sonnet 5 currently rejects non-default sampling
parameters, so the configuration leaves `temperature` unset and uses adaptive
thinking defaults.

NVIDIA Nemotron 3 Super 120B is an open-weight hybrid MoE model designed for
agentic workloads. Amazon Bedrock exposes the exact NVIDIA model through an
OpenAI-compatible endpoint with published per-token pricing, avoiding an
unpriced trial endpoint.

## Documented and reservation pricing

Prices are USD per one million tokens. Configuration values are reservation
prices used to enforce the hard cap:

| Model | Current documented input/cache/output | Config reservation input/cache/output |
|---|---|---|
| GPT-5.6 Terra | 2.00 / 0.20 / 12.00 | 2.00 / 0.20 / 12.00 |
| Claude Sonnet 5 | 2.00 / 0.20 / 10.00 | 3.00 / 0.30 / 15.00 |
| Nemotron 3 Super 120B on Bedrock, us-east-1 | 0.15 / not separately listed / 0.65 | 0.15 / 0.15 / 0.65 |

Anthropic's current pricing table lists $2 input and $10 output, while its
migration guide also contains an August 31, 2026 transition notice to $3 and
$15. Because that date has passed, the harness reserves at the higher announced
rate while retaining the current table values separately in the verification
snapshot. This avoids understating hard-cap exposure and must be rechecked
immediately before freeze.

The Nemotron cached-input price is conservatively set equal to ordinary input
because the cited Bedrock price does not advertise a lower cache-read rate.

## Primary sources

- OpenAI GPT-5.6 Terra model and pricing:
  `https://developers.openai.com/api/docs/models/gpt-5.6-terra`
- Anthropic model ID:
  `https://platform.claude.com/docs/en/about-claude/models/whats-new-sonnet-5`
- Anthropic pricing:
  `https://platform.claude.com/docs/en/about-claude/pricing`
- Anthropic migration and transition notice:
  `https://platform.claude.com/docs/en/about-claude/models/migration-guide`
- NVIDIA model ID:
  `https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-nvidia-nemotron-super-3-120b.html`
- Amazon Bedrock NVIDIA pricing:
  `https://aws.amazon.com/bedrock/pricing/`
- Bedrock OpenAI-compatible authentication:
  `https://docs.aws.amazon.com/bedrock/latest/userguide/inference-chat-completions-mantle.html`

## Approval gate

Before paid calls:

1. Recheck every source above for model availability and price changes.
2. Confirm the three exact models and region.
3. Confirm the combined hard cap encoded across the provider configs.
4. Set the three API-key environment variables without committing secrets.
5. Freeze the dataset manifest and provider-config hashes.

The explicit decision is stored in `data/confirmatory_approval.json`. The
freeze command validates every listed config, model, region, and cap rather
than relying on this prose snapshot alone.

## Judge configuration

The candidate main judge is `gpt-5.4-mini` with a separate $60 hard cap. This
keeps full-corpus judging inexpensive but shares a model family with one tested
arm. The paper must report that limitation, and the 270-response human sample
is therefore required rather than optional.
