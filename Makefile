PYTHON ?= python3.12
WHEEL_PYTHON ?= $(PYTHON)
PYTHONPATH := $(CURDIR)/src
RUN_ID ?= confirmatory-20260910-v1
RESULT_ROOT := results/$(RUN_ID)
VALIDATION_OUTPUT_DIR ?= results/full-scale-validation
RELEASE_OUTPUT_DIR ?= dist
RELEASE_ARCHIVE ?= $(RELEASE_OUTPUT_DIR)/failure-transparent-agents-0.2.0-release-candidate.zip
RESUME ?=
WORKERS ?= 4
DATASET := data/confirmatory_scenarios.jsonl
DATASET_MANIFEST := data/confirmatory_manifest.json
RAW_ARGS := --raw $(RESULT_ROOT)/primary/openai/raw_results.jsonl \
	--raw $(RESULT_ROOT)/primary/anthropic/raw_results.jsonl \
	--raw $(RESULT_ROOT)/primary/nvidia/raw_results.jsonl

.PHONY: test pilot dataset check-dataset preflight full-scale-validation freeze \
	confirmatory confirmatory-openai confirmatory-anthropic confirmatory-nvidia \
	judge human-sample annotate-human prepare-adjudication \
	annotate-adjudication finalize-adjudication analyze release-audit \
	release-bundle release-wheel clean

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests -v

pilot:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents \
		--dataset data/pilot_scenarios.jsonl \
		--output-dir results/pilot \
		--repeats 2

dataset:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/generate_confirmatory_dataset.py \
		--overwrite

check-dataset:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/generate_confirmatory_dataset.py \
		--check

preflight:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.preflight \
		--output results/preflight/confirmatory-plan.json

full-scale-validation:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.full_scale_validation \
		--output-dir $(VALIDATION_OUTPUT_DIR) \
		--bootstrap-repetitions 1000 \
		--permutation-repetitions 10000

freeze:
	test -n "$(SIGNER)"
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.freeze \
		--signer "$(SIGNER)"

confirmatory: confirmatory-openai confirmatory-anthropic confirmatory-nvidia

confirmatory-openai:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.confirmatory \
		--dataset $(DATASET) \
		--dataset-manifest $(DATASET_MANIFEST) \
		--provider-config configs/providers/openai-gpt-5.6-terra.json \
		--output-dir $(RESULT_ROOT)/primary/openai \
		--run-id $(RUN_ID) \
		--repeats 2 --workers $(WORKERS) --allow-live $(RESUME)

confirmatory-anthropic:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.confirmatory \
		--dataset $(DATASET) \
		--dataset-manifest $(DATASET_MANIFEST) \
		--provider-config configs/providers/anthropic-claude-sonnet-5.json \
		--output-dir $(RESULT_ROOT)/primary/anthropic \
		--run-id $(RUN_ID) \
		--repeats 2 --workers $(WORKERS) --allow-live $(RESUME)

confirmatory-nvidia:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.confirmatory \
		--dataset $(DATASET) \
		--dataset-manifest $(DATASET_MANIFEST) \
		--provider-config configs/providers/nvidia-nemotron-3-super-bedrock.json \
		--output-dir $(RESULT_ROOT)/primary/nvidia \
		--run-id $(RUN_ID) \
		--repeats 2 --workers $(WORKERS) --allow-live $(RESUME)

judge:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.judge \
		$(RAW_ARGS) \
		--dataset $(DATASET) \
		--dataset-manifest $(DATASET_MANIFEST) \
		--provider-config configs/judges/openai-gpt-5.4-mini.json \
		--output-dir $(RESULT_ROOT)/judge \
		--annotator-id openai-gpt-5.4-mini-judge-v1 \
		--workers $(WORKERS) --parse-retries 1 --allow-live $(RESUME)

human-sample:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.sampling \
		$(RAW_ARGS) \
		--dataset $(DATASET) \
		--output-dir $(RESULT_ROOT)/human \
		--sample-size 270 --seed 20260910

annotate-human:
	test -n "$(ANNOTATOR_ID)"
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.annotation \
		--packets $(RESULT_ROOT)/human/human_sample_blinded.jsonl \
		--output $(RESULT_ROOT)/human/human_labels-$(ANNOTATOR_ID).jsonl \
		--annotator-id "$(ANNOTATOR_ID)"

prepare-adjudication:
	test -n "$(FIRST_LABELS)"
	test -n "$(SECOND_LABELS)"
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.adjudication prepare \
		--packets $(RESULT_ROOT)/human/human_sample_blinded.jsonl \
		--first "$(FIRST_LABELS)" \
		--second "$(SECOND_LABELS)" \
		--output-dir $(RESULT_ROOT)/human/adjudication

annotate-adjudication:
	test -n "$(ADJUDICATOR_ID)"
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.annotation \
		--packets $(RESULT_ROOT)/human/adjudication/adjudication_blinded.jsonl \
		--output $(RESULT_ROOT)/human/human_labels-adjudicator.jsonl \
		--annotator-id "$(ADJUDICATOR_ID)"

finalize-adjudication:
	test -n "$(FIRST_LABELS)"
	test -n "$(SECOND_LABELS)"
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.adjudication finalize \
		--packets $(RESULT_ROOT)/human/human_sample_blinded.jsonl \
		--first "$(FIRST_LABELS)" \
		--second "$(SECOND_LABELS)" \
		$(if $(strip $(ADJUDICATED_LABELS)),--adjudicated "$(ADJUDICATED_LABELS)") \
		--output $(RESULT_ROOT)/human/human_labels.jsonl

analyze:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.analysis \
		$(RAW_ARGS) \
		--labels $(RESULT_ROOT)/judge/model_judge_labels.jsonl \
		--model-judge-labels $(RESULT_ROOT)/judge/model_judge_labels.jsonl \
		--human-labels $(RESULT_ROOT)/human/human_labels.jsonl \
		--output-dir $(RESULT_ROOT)/analysis \
		--bootstrap-repetitions 10000 \
		--permutation-repetitions 100000 \
		--seed 20260910

release-audit:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.release \
		--audit-only

release-bundle:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.release \
		--output-dir $(RELEASE_OUTPUT_DIR)

release-wheel: release-bundle
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m failure_transparent_agents.release \
		--wheel-from-archive $(RELEASE_ARCHIVE) \
		--wheel-python $(WHEEL_PYTHON) \
		--output-dir $(RELEASE_OUTPUT_DIR)

clean:
	$(PYTHON) -c "from pathlib import Path; import shutil; p=Path('results'); shutil.rmtree(p) if p.exists() else None"
