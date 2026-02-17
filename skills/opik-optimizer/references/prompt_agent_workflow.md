# Prompt, agent, tools, and metric workflow

## Public object model

`opik_optimizer` exports:

- `ChatPrompt`
- `OptimizationResult`
- `FewShotBayesianOptimizer`, `EvolutionaryOptimizer`, `MetaPromptOptimizer`,
  `HierarchicalReflectiveOptimizer`, `GepaOptimizer`, `ParameterOptimizer`
- `datasets` module
- `OptimizableAgent`, `LiteLLMAgent`

### `ChatPrompt`

`ChatPrompt` is the core runtime prompt object.
Use one of:

- `ChatPrompt(system=..., user=...)`
- `ChatPrompt(messages=[...])`

Placeholders from dataset rows are required for optimization variables, for example:

```python
ChatPrompt(system="You are a math tutor.", user="{question}")
```

Useful fields:

- `name` default: `"chat-prompt"`
- `tools` (OpenAI function tools or MCP)
- `function_map` (callable map for function tools)
- `model` and `model_kwargs` are passed to runtime execution.

### Tool tool-calling formats

Function tool schema:

```python
{
    "type": "function",
    "function": {
        "name": "...",
        "description": "...",
        "parameters": {"type": "object", "properties": {...}},
    },
}
```

MCP style:

```python
{
    "type": "mcp",
    "server_label": "...",
    "server_url": "https://...",
    "headers": {"Authorization": "Bearer ..."},
    "allowed_tools": ["..."],
}
```

Cursor-style MCP config may be passed directly in `tools`.

## `optimize_prompt` workflow

Signature (from `BaseOptimizer`):

```python
optimize_prompt(
    prompt,
    dataset,
    metric,
    agent=None,
    experiment_config=None,
    n_samples=None,
    n_samples_minibatch=None,
    n_samples_strategy=None,
    auto_continue=False,
    project_name=None,
    optimization_id=None,
    validation_dataset=None,
    max_trials=10,
    allow_tool_use=True,
    optimize_prompts="system",
    optimize_tools=None,
    *args,
    **kwargs,
)
```

Important behavior:

- `optimize_prompts` accepts role selectors (`"system"`, `"user"`, list, etc.) and is normalized to a role set.
- `optimize_tools=True` enables tool description optimization only on supported optimizers.
- If `validation_dataset` is passed, runs can use it for ranking/selection when supported.
- `agent` defaults to `LiteLLMAgent`; custom agents can be injected.
- `optimize_prompt` runs stop early if baseline score reaches configured thresholds.

## Metrics

Metric protocol: `MetricFunction(dataset_item: dict, llm_output: str) -> float | ScoreResult | list[ScoreResult]`.

Examples in this repo:

- string numeric scores from custom functions.
- metric objects returning `ScoreResult` (for richer reason/debug text).

## `optimize_parameter` workflow

Only for `ParameterOptimizer`:

```python
optimize_parameter(
    prompt,
    dataset,
    metric,
    parameter_space,
    validation_dataset=None,
    experiment_config=None,
    max_trials=None,
    n_samples=None,
    n_samples_minibatch=None,
    n_samples_strategy=None,
    agent=None,
    project_name="Optimization",
    sampler=None,
    callbacks=None,
    timeout=None,
    local_trials=None,
    local_search_scale=None,
    optimization_id=None,
)
```

Use when content should not be edited, only parameter values.

## `OptimizationResult` and interpretation

`result.score`, `result.initial_score`, `result.history`, `result.optimizer`,
`result.prompt`, `result.initial_prompt`, `result.optimization_id`.

Helpful methods:

- `result.display()` for human-readable summary.
- `result.get_optimized_model_kwargs()`
- `result.get_optimized_parameters()`

## Prompt segment targeting

From `opik_optimizer.utils.prompt_segments`:

- `extract_prompt_segments(ChatPrompt)` returns IDs like `system`, `user`, `message:0`, `tool:<name>`.
- `apply_segment_updates(ChatPrompt, updates)` returns a new prompt with only target segments replaced.

Use this for stable targeting when editing only user/system/assistant blocks.
