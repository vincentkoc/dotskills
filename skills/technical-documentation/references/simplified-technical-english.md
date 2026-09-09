# Simplified Technical English (ASD-STE100) for Technical Docs

This reference adapts the ASD-STE100 controlled-language discipline for product docs, governance files, and agent instruction files. It is derived from the `asd-ste100` skill by Dustin Yuchen Teng (MIT). See `references/third-party-notices.md`.

ASD-STE100 is the aerospace and defense standard that stops maintenance technicians from misreading English. ASD is the AeroSpace and Defense Industries Association of Europe. It eliminates the two biggest sources of misreading. The first is words with more than one meaning. The second is sentences with more than one possible structure. The same discipline protects a docs reader who cannot ask a follow-up question. It also protects an AI agent that parses an AGENTS.md or a CLI reference with no human in the loop.

## Source and scope

- Encodes the rule categories of ASD-STE100 Issue 9 (January 2025): 53 rules across 9 sections. The standard backs them with a dictionary of about 900 approved words and about 1,200 words to avoid.
- Does not reproduce the approved dictionary. ASD-STE100 is free to obtain but not free to redistribute. Request it from the official downloads page: https://www.asd-ste100.org/STE_downloads.html
- Applies the underlying principle instead: pick the plainest common word and use it the same way every time. Do not claim dictionary compliance.
- Official summary sources: https://www.asd-ste100.org/about_STE.html, https://en.wikipedia.org/wiki/Simplified_Technical_English, https://www.techscribe.co.uk/techw/asd-simplified-technical-english.htm

## Two modes, mapped to doc types

Pick a mode per file before rewriting. State the choice in the handoff.

| Mode | Apply to | What is enforced |
|---|---|---|
| Strict | Procedures, how-to steps, CLI and config reference, error messages, tool descriptions, safety and security text, AGENTS.md and alias files, CONTRIBUTING.md commands | Every structural rule, sentence caps (20 words for instructions, 25 for descriptions), one-word-one-meaning within the file |
| STE-flavored | READMEs, explanation pages, concept pages, changelogs, PR descriptions, landing and index pages | Structural rules in full. Lexical rules are advisory. Prose keeps some range |

Diataxis mapping: tutorial and how-to steps are Strict. Reference is Strict. Explanation is STE-flavored. A mixed page uses Strict for its steps and tables and STE-flavored for its narrative.

## Structural rules (apply with confidence)

| Rule | Do | Do not |
|---|---|---|
| Active voice | "The gateway deletes the session." | "The session is deleted." unless the actor is unknown or irrelevant |
| No phrasal verbs (Rule 9.3) | "Start the job." "Remove the panel." | "Spin up the job." "Take off the panel." |
| One instruction per sentence | "Open the file. Read line 3." | "Open the file and read line 3, then check it." |
| Sentence length | 20 words or fewer for instructions, 25 or fewer for descriptions | Long compound or subordinate-clause sentences |
| No semicolons (Rule 8.1) | Split into separate sentences | Any semicolon. Other punctuation stays allowed |
| Noun clusters | 3 words or fewer stacked as a noun phrase | 4-word or longer noun stacks ("gateway session transcript compaction handler") |
| No ellipsis | Keep subject, verb, and article explicit | "Files not backed up will be lost" (which files?) |
| Keep modality | "The request may have failed." stays "may have" | Promoting a hedge to a fact, or inventing a certainty |
| Paragraph limits | One topic per paragraph, 6 sentences or fewer | Multi-topic paragraphs |
| Lists for sequences | Numbered or bulleted list for 3 or more steps or conditions | A sequence buried in one prose sentence |
| Safety first | Open a warning with the command or condition | A warning buried mid-sentence |

## Lexical rules (direction of travel only)

| Rule | Do | Do not | Why it is weaker here |
|---|---|---|---|
| One word, one meaning | Pick one verb per action and reuse it ("check", never "check" and "verify" and "confirm" for the same action) | Rotate synonyms | Consistency within a file is checkable. Which word is approved is not, without the dictionary |
| One part of speech per word | "Apply oil to the valve" (noun) | "Oil the valve" (verb) | Prefer the noun form when both read equally well. Do not claim compliance |
| Verb, not noun (Rule 3.7) | "Analyze the log." | "Perform an analysis of the log." | Preferring the verb form is always safe |
| Domain terms | Keep necessary technical terms and define each once, or link to a glossary | Use jargon without ever defining it | STE allows a project glossary beyond its base dictionary |

## Simple tenses, with one exception

STE permits infinitive, imperative, simple present, simple past, simple future, and past participle as adjective. It excludes present perfect and other compound forms: "we received the report", not "we have received the report".

Where the compound form carries information the simple form cannot, keep it and flag it. "The job has completed" (output available now) differs from "the job completed" (at some past point). "May have failed" is a hedge, not a tense violation. When the tense rule and the modality rule conflict, modality wins.

## Scan checklist (mechanical, run before any rewrite)

1. Synonym rotation: the same thing has several names in one file ("the user", "the customer", "the client"). Fix: one name, every time.
2. Hedge stacking: qualifiers pile up until the sentence asserts nothing ("it is important to note that this may potentially help"). Fix: state the claim, or delete it.
3. Nominalization: an action frozen into a noun (`perform an analysis of`). Fix: use the verb.
4. Marketing adjectives: `seamless`, `robust`, `powerful`, `cutting-edge`, `effortless`, `blazing-fast`. Fix: delete, or replace with the measurement that earns the claim.
5. Run-on sentences: several ideas joined by semicolons or dashes. Fix: one idea per sentence.
6. Soft phrasal verbs: `spin up`, `reach out`, `dive into`, `kick off`. Fix: the single plain verb.

`scripts/ste-lint.py` runs this checklist deterministically. It checks semicolons, sentence length, phrasal verbs, nominalization, marketing adjectives, synonym rotation, passive voice, and compound tenses. It never flags hedges or modality. Use `--mode flavored` for prose files and `--max-words 20` for procedure files. Use `--summary` for a docs tree and `--baseline N` when adopting on existing docs.

## Rewrite process

1. Pick the mode from the table above.
2. Read the input once for meaning. Do not rewrite before you know what the text must still say afterward.
3. Run the lint, then walk the text sentence by sentence and flag every violation. In STE-flavored mode, flag lexical violations but do not enforce them.
4. Rewrite each flagged sentence while preserving the meaning exactly.
   - Check modality before you commit. A shorter sentence that upgrades a hedge to a fact is a different claim, not a simplification.
   - Never add a fact the source did not state: no new cause, frequency, or mechanism.
   - If a rewrite would drop a safety condition, a scope qualifier, or a number, keep the longer phrasing and flag it.
5. Re-run the lint on the rewritten text. Hard violations must not increase.
6. If the input already complies, say so. Do not force changes onto compliant text.

## Output contract for rewrites

- Default: the rewritten text alone, ready to paste. No preamble, no mode announcement, no violation count.
- One permitted addition: a single line prefixed `Kept as-is:` that names any phrase kept longer on purpose and the precision it protects.
- On request ("show the diff", "which rules did it break"): output a table with columns `Rule violated | Original | Simplified`. Follow it with `Mode: <mode>. <n> violations found.` and one line on anything deliberately not simplified.

## Boundaries

Will:
- Rewrite ambiguous or dense English into short, single-meaning, active-voice sentences.
- Preserve every fact, condition, scope qualifier, and hedge in the original.
- Suggest a one-line glossary entry for domain terms that must stay.

Will not:
- Claim ASD dictionary compliance or produce certified STE documentation.
- Simplify creative or marketing copy where voice is the point.
- Silently drop a safety condition or exception to shorten a sentence.
- Convert "may have failed" into "failed", or "could be caused by X" into "X is the cause".
- Make weak content useful. STE fixes form, not substance. A hollow paragraph rewritten under these rules is a clean hollow paragraph. Say so instead of polishing it.
- Shorten past the point of clarity. Stop when the sentence is unambiguous, not when it is shortest.

See `references/ste-examples.md` for worked before/after examples, including docs-specific ones. That file quotes non-compliant text on purpose, so the linter flags it. Do not "fix" the examples.
