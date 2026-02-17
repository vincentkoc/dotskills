# Example patterns and implementation notes

Use these patterns before writing new implementations.

## 1) user-only edits (keep system fixed)

```python
from opik_optimizer import ChatPrompt, MetaPromptOptimizer
from opik_optimizer.datasets import context7_eval

prompt = ChatPrompt(
    system="You are a reliable assistant.",
    user="{user_query}",
)

result = MetaPromptOptimizer(model="openai/gpt-4o-mini").optimize_prompt(
    prompt=prompt,
    dataset=context7_eval(),
    metric=lambda item, output: 1.0 if output and item.get("reference_answer", "") in output else 0.0,
    optimize_prompts="user",
)
```

## 2) multimodal prompt optimization

```python
from opik_optimizer import ChatPrompt, HRPO
from opik_optimizer.datasets import driving_hazard

prompt = ChatPrompt(
    messages=[
        {"role": "system", "content": "Be precise and safety-oriented."},
        {"role": "user", "content": [
            {"type": "text", "text": "{question}"},
            {"type": "image_url", "image_url": {"url": "{image}"}},
        ]},
    ]
)

result = HRPO(model="openai/gpt-5.2").optimize_prompt(
    prompt=prompt,
    dataset=driving_hazard(count=20),
    validation_dataset=driving_hazard(split="test", count=5),
    metric=lambda item, output: 1.0,
    max_trials=10,
)
```

## 3) MCP tool optimization (MetaPromptOptimizer)

```python
from opik_optimizer import ChatPrompt, MetaPromptOptimizer
from opik_optimizer.datasets import context7_eval

prompt = ChatPrompt(
    system="Use docs tools when needed.",
    user="{user_query}",
    tools={
        "mcpServers": {
            "context7": {
                "url": "https://mcp.context7.com/mcp",
                "headers": {"CONTEXT7_API_KEY": "YOUR_API_KEY"},
            }
        }
    },
)

result = MetaPromptOptimizer(model="openai/gpt-5-nano").optimize_prompt(
    prompt=prompt,
    dataset=context7_eval(),
    metric=lambda item, output: 1.0 if str(output).strip() else 0.0,
    optimize_prompts=False,
    optimize_tools=True,
)
```

## 4) Parameter tuning

```python
from opik_optimizer import ChatPrompt, ParameterOptimizer
from opik_optimizer.algorithms.parameter_optimizer.types import ParameterSearchSpace, ParameterSpec, ParameterType

search_space = ParameterSearchSpace(
    parameters=[
        ParameterSpec(name="temperature", distribution=ParameterType.FLOAT, low=0.0, high=1.0),
        ParameterSpec(name="top_p", distribution=ParameterType.FLOAT, low=0.0, high=1.0),
    ]
)

result = ParameterOptimizer(model="openai/gpt-4o-mini").optimize_parameter(
    prompt=ChatPrompt(system="Answer briefly.", user="{question}"),
    dataset=dataset,
    metric=metric,
    parameter_space=search_space,
)
```

## 5) prompt segment editing for controlled updates

```python
from opik_optimizer.utils import prompt_segments

segments = prompt_segments.extract_prompt_segments(prompt)
target = {
    "message:0": "Give strict JSON output with keys: answer, confidence.",
}
updated = prompt_segments.apply_segment_updates(prompt, target)
```

## 6) Prompt template customization

Use `prompt_overrides` to edit internal optimizer templates:

```python
from opik_optimizer import EvolutionaryOptimizer

optimizer = EvolutionaryOptimizer(
    model="openai/gpt-5-mini",
    prompt_overrides={"synonyms_system_prompt": "Return one synonym only."},
)
```

Or callable overrides to mutate multiple templates at once via `PromptLibrary`.
