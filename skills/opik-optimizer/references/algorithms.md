# Opik Optimizer algorithms

## Available optimizers

All optimizers are imported from `opik_optimizer`:

- `EvolutionaryOptimizer`
- `FewShotBayesianOptimizer`
- `MetaPromptOptimizer`
- `HierarchicalReflectiveOptimizer` (`HRPO` alias)
- `GepaOptimizer`
- `ParameterOptimizer`

### Common constructor defaults

The shared base default settings are in `opik_optimizer.constants`:

- `model`: `openai/gpt-5-nano`
- `verbose`: `1`
- `seed`: `42`
- `n_threads`: `12`
- `skip_perfect_score`: `True`
- `perfect_score`: `0.95`

## EvolutionaryOptimizer (supports prompt + tool optimization, multimodal)

Use when you want GA-style search over prompt text and optional tool descriptions.

Notable constructor args:

- `population_size` (default `30`)
- `num_generations` (default `15`)
- `mutation_rate`, `crossover_rate`, `tournament_size`, `elitism_size`
- `adaptive_mutation`, `enable_moo`, `enable_llm_crossover`, `enable_semantic_crossover`
- `infer_output_style`, `output_style_guidance`
- `n_threads`, `verbose`, `seed`

It also exposes `supports_prompt_optimization=True`, `supports_tool_optimization=True`, `supports_multimodal=True`.

## FewShotBayesianOptimizer (prompt optimization only, multimodal)

Use when you want example-augmented prompting and Bayesian search over few-shot count and selections.

Notable constructor args:

- `min_examples`, `max_examples`
- `enable_columnar_selection`, `enable_diversity`
- `enable_multivariate_tpe`, `enable_optuna_pruning`
- `model_parameters`, `prompt_overrides`
- `n_threads`, `seed`

It sets `supports_prompt_optimization=True`, `supports_tool_optimization=False`, `supports_multimodal=True`.

## MetaPromptOptimizer (prompt + tool optimization, multimodal)

Use for iterative prompt refinement with context-learning and Hall-of-Fame pattern reuse.

Notable constructor args:

- `prompts_per_round`
- `enable_context`
- `num_task_examples`, `task_context_columns`
- `use_hall_of_fame`
- `model`, `n_threads`, `verbose`, `seed`
- `reasoning_model`/`reasoning_model_parameters` are inherited via base constructor fields in the SDK.

Flags: `supports_prompt_optimization=True`, `supports_tool_optimization=True`, `supports_multimodal=True`.

## HierarchicalReflectiveOptimizer / HRPO (prompt + tool optimization, multimodal)

Use for root-cause-based iterative reflection.

Notable constructor args:

- `max_parallel_batches` (default `5`)
- `batch_size` (default `25`)
- `convergence_threshold` (default `0.01`)
- `reasoning_model`, `reasoning_model_parameters`
- `n_threads`, `verbose`, `seed`

Flags: `supports_prompt_optimization=True`, `supports_tool_optimization=True`, `supports_multimodal=True`.

## GepaOptimizer (prompt optimization only, multimodal)

Use when you need GEPA/Genetic-Pareto optimization.

Notable constructor args:

- `n_threads`, `verbose`, `seed`
- `model_parameters`
- `skip_perfect_score`, `perfect_score`

Flags: `supports_prompt_optimization=True`, `supports_tool_optimization=False`, `supports_multimodal=True`.

## ParameterOptimizer (parameter tuning only, multimodal)

Use when prompt content is already good and you want to tune call parameters (`temperature`, `top_p`, etc.).

Call pattern is:

```python
optimizer.optimize_parameter(
    prompt=...,
    dataset=...,
    metric=...,
    parameter_space=...,
)
```

Constructor args:

- `default_n_trials` (default `20`)
- `local_search_ratio` (default `0.3`)
- `local_search_scale` (default `0.2`)
- `model_parameters`, `n_threads`, `verbose`, `seed`

Flags: `supports_prompt_optimization=False`, `supports_tool_optimization=False`, `supports_multimodal=True`.

`optimize_prompt(...)` is explicitly unsupported and raises `NotImplementedError`.

## Decision guidance

- Start with `FewShotBayesianOptimizer` for tasks with stable answer patterns and known dataset fields.
- Start with `MetaPromptOptimizer` or `HRPO` for quality gaps that are not solved by few-shot examples alone.
- Use `EvolutionaryOptimizer` when you want wider search, explicit crossover/mutation behavior, and optional MOO.
- Use `GepaOptimizer` when you want Pareto-style prompt candidate tradeoff behavior.
- Use `ParameterOptimizer` for model hyperparameter tuning and prompt comparison only.
