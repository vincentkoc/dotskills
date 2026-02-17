# Candidate Scorecard

Score each candidate 0-5 in each dimension:

- `frequency`: repeated occurrences across distinct sessions
- `impact`: time-to-resolution / incident severity
- `actionability`: can the pattern be handled by deterministic checks/workflows
- `toolability`: enough local tooling commands to automate
- `novelty`: not already covered by existing skill coverage

`confidence` = average score / 5.

Prioritize candidates with:
- frequency >= 3
- confidence >= 0.72
- impact >= 3
