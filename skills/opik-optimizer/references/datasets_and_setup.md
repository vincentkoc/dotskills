# Datasets and environment setup

## Dataset helpers

`opik_optimizer.datasets` exports built-in loaders used across examples:

`ai2_arc`, `arc_agi2`, `cnn_dailymail`, `context7_eval`, `driving_hazard`,
`election_questions`, `gsm8k`, `halu_eval`, `hover`, `hotpot`, `ifbench`, `medhallu`,
`rag_hallucinations`, `ragbench_sentence_relevance`, `tiny_test`, `truthful_qa`, `pupa`.

Each dataset helper typically accepts `count`, `split`, and dataset-specific kwargs.

## Installation and runtime

- Install: `pip install opik-optimizer`.
- Configure provider keys as expected by LiteLLM (e.g., OpenAI, Anthropic).
- Optional Opik tracking:
  - `opik configure` to set platform project credentials.
  - `project_name` / `OPIK_PROJECT_NAME` controls tracing project context.

## Useful limits and defaults

- Default thread cap from SDK helpers:
  - minimum 1, maximum 32.
- Default thread fallback for omitted values derives from CPU count, clamped to `[1, 32]`.
- `ParameterOptimizer` default trials: `20`.
- Few-shot Bayesian defaults:
  - min examples `2`, max examples `8`.
- Evolutionary defaults:
  - population `30`, generations `15`, mutation `0.2`, crossover `0.8`.

## Validation and reproducibility

- Set `seed` in optimizer constructor for deterministic behavior.
- Use `max_trials`, `n_threads`, and fixed dataset splits (`train`, `test` style dataset args) for run reproducibility.
