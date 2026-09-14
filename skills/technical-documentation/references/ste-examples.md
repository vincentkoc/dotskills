# STE Before / After Examples

Worked examples for `references/simplified-technical-english.md`. Parts 1 and 2 are adapted from the `asd-ste100` skill (MIT, see `references/third-party-notices.md`). Part 3 is built for docs-tree audits.

Word counts are whitespace tokens (`text.split()`), the same tokenizer `scripts/ste-lint.py` uses.

## Part 1: Official STE rule illustrations (paraphrased)

| Rule | Before | After | Why |
|---|---|---|---|
| One meaning per word | "Verify the system." / "Check the connections." / "Confirm receipt." | "Make sure the system is correct." (one term, used consistently) | Three near-synonyms force the reader to guess whether they mean the same action |
| One part of speech per word | "Oil the valve." | "Apply oil to the valve." | If "oil" is approved only as a noun, the verb use breaks the one-word-one-role guarantee |
| Precise verb meaning | "Follow the safety instructions." | "Obey the safety instructions." | "Follow" can mean "come after" or "obey" |
| Simple tense only | "We have received the technical reports." | "We received the technical reports." | Present perfect adds a second parse |
| Verb, not noun | "Perform an inspection of the filter." | "Inspect the filter." | The noun form hides the action |
| No phrasal verbs | "Take off the access panel." | "Remove the access panel." | "Take off" also means "depart" and "deduct" |

## Part 2: Agent-facing text

### Tool description

Before (44 words, two instructions, present perfect in relative clauses):

> This tool will attempt to synchronize state across the various backends that have been configured, and if a conflict is detected it may resolve it automatically depending on the strategy that has been set, or otherwise it will surface the conflict for manual review.

After:

> The tool tries to synchronize state across the configured backends. If it finds a conflict, it reads the configured strategy. If the strategy allows automatic resolution, the tool may resolve the conflict without a user. If the tool does not resolve the conflict, it reports the conflict for manual review.

Not flagged: "will attempt to" and "may resolve". Those are hedges. The rewrite must not promise success the source did not promise.

### Error message

Before (28 words, three claims in one sentence):

> An error may have occurred while processing your request due to a possible mismatch in the expected data format, which could be caused by an outdated client version.

After:

> Your request may have failed. The cause may be a data format that does not match what the server expects. An outdated client can cause this mismatch. Check your client version.

This example is why the modality rule exists. An earlier rewrite produced "The request failed" and "an outdated client is the most common cause". Both read better. Both are wrong: the first asserts a failure the system only suspects, and the second invents a frequency claim.

### Inter-agent instruction

Before (36 words, present perfect, stacked subordinate clauses):

> Once the upstream job has completed and assuming no errors were raised, the downstream agent should proceed to consume the output artifact, though it is worth noting that partial artifacts are sometimes produced under timeout conditions.

After:

> Wait for the upstream job to finish with no errors. Then read the output artifact. Warning: a timeout can produce a partial artifact. Check that the artifact is complete before you use it.

Two deliberate calls: "should proceed to consume" became the imperative "read", which STE permits for instructions. The final sentence is new content that makes the warning actionable, so it is called out rather than passed off as a rewrite.

### README prose (STE-flavored mode)

Before (34 words, marketing adjectives, semicolon):

> Our caching layer is designed to slot seamlessly into your existing stack with minimal friction and no vendor lock-in; it leverages semantic similarity to dramatically reduce the cache misses that traditionally plague LLM workloads.

After:

> A normal cache matches requests by exact text, so a small change in wording causes a cache miss. This cache compares the meaning of a new prompt against the prompts it already holds. It runs alongside your current stack and stores no data outside it.

Flavored mode kept the explanatory rhythm and did not force one fixed term per concept. It still cut the marketing adjectives, the semicolon, and the length.

## Part 3: Docs-tree cases

### Configuration reference entry (Strict)

Before:

> The `gateway.timeoutMs` setting, which has been available since the gateway was refactored and which most users will probably never need to touch, controls how long the gateway waits before it gives up on an upstream that isn't responding; the default is generally fine.

After:

> `gateway.timeoutMs` sets how long the gateway waits for an upstream response before it fails the request. Default: 30000. Most deployments keep the default.

Kept as-is: nothing. The number 30000 was taken from the config schema during the rewrite, not invented. If the schema is not available, write "Default: see the config schema" instead of guessing.

### Procedure step with a buried warning (Strict, 20-word cap)

Before:

> Run the migration script, making sure you've backed up the database first since the script drops the sessions table before it recreates it and there's no undo.

After:

> Warning: the migration script drops the `sessions` table and there is no undo.
>
> 1. Back up the database.
> 2. Run the migration script.

### Oversized page intro (STE-flavored)

Before:

> This comprehensive guide dives deep into everything you need to know about the Slack channel integration, from initial setup through advanced configuration, troubleshooting, and best practices, so grab a coffee.

After:

> This page covers the Slack channel: setup, configuration, and troubleshooting. Start with Setup. Use the sidebar to jump to a section.

The rewrite also signals a structural finding: a page whose intro promises "everything" is usually a split candidate. Record that separately as an IA finding rather than fixing it in the prose pass.

### Compliant text (no change)

> Restart the gateway. Then check the health endpoint.

Report: already compliant. Do not touch.
