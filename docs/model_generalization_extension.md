# Six-model generalization extension

This extension evaluates whether the original three-model result transfers to
three inexpensive model families. It preserves the frozen 100-task dataset,
three instruction conditions, two repeats, prompts, simulator outputs, outcome
definitions, and clustered analysis. It is a post-confirmatory generalization
study, not part of the original preregistered three-model comparison.

## Added primary models

| Family | Model | Route | Role |
| --- | --- | --- | --- |
| Amazon | Nova Micro | Amazon Bedrock Converse, US geographic profile | Small proprietary model |
| Meta | Llama 3.1 8B Instruct | Amazon Bedrock Converse, US geographic profile | Older open-weight model |
| Mistral | Ministral 8B 3.0 | Amazon Bedrock Converse, on-demand | Current inexpensive open-weight model |

The extension adds 1,800 primary responses: 3 models × 100 tasks × 3
conditions × 2 repeats. Together with the original study, the six-model
analysis contains 3,600 responses.

## Evaluation

GPT-5.6 Luna labels all 3,600 responses with the unchanged strict annotation
prompt, producing one internally consistent six-model result set. The original
GPT-5.4-mini labels remain unchanged and serve as a judge-sensitivity analysis
for the original 1,800 responses. No human labels are claimed.

## Claims and analysis

The primary extension question is whether the evidence contract keeps observed
false-success rates low across all six tested model configurations. Secondary
analyses report model-specific false success, fabricated details, limitation
disclosure, useful recovery, over-refusal, latency, token use, and estimated
cost. Confidence intervals and paired tests retain scenario-clustered
resampling.

The added cohort is interpreted as model-family and price-tier generalization.
It does not convert the synthetic benchmark into a population estimate and
does not retroactively alter the original confirmatory hypotheses.

## Reproduction

```bash
AWS_PROFILE=<approved-profile> make model-extension \
  PYTHON=.venv/bin/python WORKERS=8

AWS_PROFILE=<approved-profile> make model-extension-judge \
  PYTHON=.venv/bin/python WORKERS=12

make model-extension-analyze PYTHON=.venv/bin/python
```

Credential names and values are operational inputs only and are not recorded
in the results, paper, or public release.
