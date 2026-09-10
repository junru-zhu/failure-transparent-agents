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
| OpenAI | `gpt-5.6-terra` via `us.openai.gpt-5.6-terra` | Amazon Bedrock Responses API |
| Anthropic | `claude-sonnet-5` | Amazon Bedrock native InvokeModel |
| NVIDIA/open weight | `nvidia.nemotron-super-3-120b` | Amazon Bedrock native InvokeModel |

## Rationale

`gpt-5.6-terra` is OpenAI's balanced current model. The authorized Bedrock
catalog exposes it through the active `us.openai.gpt-5.6-terra` geographic
inference profile. The arm uses Bedrock's OpenAI-compatible Responses endpoint
with temporary AWS SigV4 credentials and sets reasoning effort to `none`.

`claude-sonnet-5` is Anthropic's current speed/intelligence balance and has a
pinned dateless model ID. The authorized Bedrock catalog exposes the exact model
through the active `us.anthropic.claude-sonnet-5` US inference profile.
The request preserves the Anthropic Messages schema, leaves `temperature`
unset, and uses temporary AWS SigV4 credentials.

NVIDIA Nemotron 3 Super 120B is an open-weight hybrid MoE model designed for
agentic workloads. Amazon Bedrock exposes the exact NVIDIA model through
native InvokeModel with the chat-completions message schema and published
per-token pricing. Collection uses temporary AWS SigV4 credentials rather than
persisting a bearer API key.

## Documented and reservation pricing

Prices are USD per one million tokens. Configuration values are reservation
prices used to enforce the hard cap:

| Model | Current documented input/cache/output | Config reservation input/cache/output |
|---|---|---|
| GPT-5.6 Terra on Bedrock, US geographic routing | 2.20 / 0.22 / 13.20 | 2.20 / 0.22 / 13.20 |
| Claude Sonnet 5 after 2026-08-31 | 3.00 / 0.30 / 15.00 | 3.00 / 0.30 / 15.00 |
| Nemotron 3 Super 120B on Bedrock, us-east-1 | 0.15 / not separately listed / 0.65 | 0.15 / 0.15 / 0.65 |

The Claude experiment runs after the announced August 2026 transition and
therefore uses the standard $3 input and $15 output rate per million tokens.
The rate and Bedrock availability are rechecked immediately before freeze.

The Nemotron cached-input price is conservatively set equal to ordinary input
because the cited Bedrock price does not advertise a lower cache-read rate.

## Primary sources

- OpenAI GPT-5.6 Terra model and pricing:
  `https://developers.openai.com/api/docs/models/gpt-5.6-terra`
- Amazon Bedrock GPT-5.6 Terra model, Responses endpoint, inference profiles,
  authentication, and regional pricing:
  `https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-oss-56.html`
- Anthropic model ID:
  `https://platform.claude.com/docs/en/about-claude/models/whats-new-sonnet-5`
- Anthropic pricing:
  `https://platform.claude.com/docs/en/about-claude/pricing`
- Anthropic migration and transition notice:
  `https://platform.claude.com/docs/en/about-claude/models/migration-guide`
- Amazon Bedrock Claude Sonnet 5:
  `https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-5.html`
- Anthropic Messages request body on Bedrock:
  `https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html`
- NVIDIA model ID:
  `https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-nvidia-nemotron-super-3-120b.html`
- Amazon Bedrock NVIDIA pricing:
  `https://aws.amazon.com/bedrock/pricing/`
- Bedrock InvokeModel CLI:
  `https://docs.aws.amazon.com/cli/latest/reference/bedrock-runtime/invoke-model.html`

## Approval gate

Before paid calls:

1. Recheck every source above for model availability and price changes.
2. Confirm the three exact models and region.
3. Confirm the combined hard cap encoded across the provider configs.
4. Set one authorized AWS profile for the three primary arms and the
   OpenAI API-key variable for the separate judge without committing secrets.
5. Freeze the dataset manifest and provider-config hashes.

The explicit decision is stored in `data/confirmatory_approval.json`. The
freeze command validates every listed config, model, region, and cap rather
than relying on this prose snapshot alone.

## Judge configuration

The candidate main judge is `gpt-5.4-mini` with a separate $60 hard cap. This
keeps full-corpus judging inexpensive but shares a model family with one tested
arm. The paper must report that limitation, and the 270-response human sample
is therefore required rather than optional.
