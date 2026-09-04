#!/usr/bin/env python3
"""Deterministic linter for the structural ASD-STE100 rules used by the
technical-documentation skill.

Derived from https://github.com/danyuchn/asd-ste100-skill (MIT License,
Copyright (c) 2026 Dustin Yuchen Teng). Extended for docs-tree audits:
directory walking, Markdown/MDX-aware skipping, per-file summaries, and a
strict/flavored mode switch. See references/third-party-notices.md.

Checks only rules verifiable without ASD's dictionary. Deliberately never
flags hedges or modality (may/might/could): the skill treats confidence as
content, and a linter that pressures hedges out would rewrite claims.

Usage:
    ste-lint.py FILE|DIR [FILE|DIR ...]     # dirs expand to *.md/*.mdx/*.mdc/*.rst/*.txt
    echo "text" | ste-lint.py [--json]
    ste-lint.py --baseline 5 FILE           # pass unless hard violations exceed 5
    ste-lint.py --disable passive-voice,present-perfect FILE
    ste-lint.py --mode flavored FILE        # prose mode: synonym-rotation becomes advisory
    ste-lint.py --max-words 20 FILE         # instruction cap (default 25 = descriptive cap)
    ste-lint.py --summary [--top 25] DIR    # per-file table, worst first
    ste-lint.py --selftest

Exit 1 when hard ("advisory-free") violations exceed the baseline (default 0).
Advisory findings (passive voice, compound tenses) never fail the run.
"""
import json
import os
import re
import sys

DOC_EXTENSIONS = (".md", ".mdx", ".mdc", ".rst", ".txt")
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".generated"}

# Regex heuristics, not a parser. No noun-cluster rule (needs POS tagging).
# No ellipsis rule: technical writing sometimes earns one.
RULES = [
    ("semicolon", "advisory-free",
     re.compile(r";"),
     "STE bans the semicolon (Rule 8.1). Split into separate sentences."),
    ("phrasal-verb", "advisory-free",
     re.compile(r"\b(spin(?:ning|s)? up|spun up|reach(?:ing|es|ed)? out|div(?:e|es|ing|ed) into|dove into|kick(?:ing|s|ed)? off|circl(?:e|es|ing|ed) back|touch(?:ing|es|ed)? base)\b", re.I),
     "Soft phrasal verb. Use the single plain verb (start, contact, read, begin)."),
    ("marketing-adjective", "advisory-free",
     re.compile(r"\b(seamless(?:ly)?|robust(?:ly)?|cutting-edge|effortless(?:ly)?|blazing[- ]fast|world-class|state-of-the-art|game-chang(?:ing|er))\b", re.I),
     "Marketing adjective. Delete, or replace with the measurement that earns the claim."),
    ("nominalization", "advisory-free",
     re.compile(r"\b(perform|performs|performed|conduct|conducts|conducted|carry out|carries out|carried out)\s+(?:a|an|the)\s+\w+(?:tion|sion|ment|ance|ence|ysis)\b", re.I),
     "Action frozen into a noun. Use the verb (analyze, not perform an analysis of)."),
    ("passive-voice", "advisory",
     re.compile(r"\b(is|are|was|were|been|being)\s+(\w+ed|given|taken|made|done|found|seen|known|shown|written|built|sent|set|run|read|kept|held|left|put)\b(?!\s+(?:to|for|by)\s+\w+ing)", re.I),
     "Possible passive voice. Name the actor and use an active verb, unless the actor is unknown or irrelevant."),
    ("present-perfect", "advisory",
     # modal + perfect infinitive ("may have failed") is a protected hedge, not present perfect
     re.compile(r"(?<!\bmay )(?<!\bmight )(?<!\bcould )(?<!\bshould )(?<!\bwould )(?<!\bmust )\b(has|have|had)\s+(?:been\s+)?\w+(?:ed|en)\b", re.I),
     "Compound tense. Use simple past/present unless current relevance is the point (then keep and flag)."),
]

# One word, one meaning: groups of verbs commonly rotated for the same action.
# Only pairs where the members are genuinely interchangeable. error/fault/failure
# are distinct concepts and stay out.
SYNONYM_GROUPS = [
    ("check", "verify", "confirm", "validate"),
    ("delete", "remove", "erase"),
    ("start", "launch", "begin", "initiate"),
    ("stop", "halt", "terminate"),
    ("show", "display"),
    ("use", "utilize", "employ"),
    ("fix", "repair", "correct"),
    ("send", "transmit"),
    ("get", "retrieve", "fetch", "obtain"),
    ("change", "modify", "alter"),
]

DEFAULT_MAX_WORDS = 25  # descriptive cap; pass --max-words 20 for procedures

CODE_FENCE = re.compile(r"^(```|~~~)")
INLINE_CODE = re.compile(r"`[^`]*`")
MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
BARE_URL = re.compile(r"https?://\S+")
HTML_COMMENT = re.compile(r"<!--.*?-->")
MDX_IMPORT = re.compile(r"^\s*(import|export)\s")
TABLE_ROW = re.compile(r"^\s*\|")
FRONTMATTER_DELIM = re.compile(r"^---\s*$")


def _word_re(base):
    return re.compile(r"\b" + base + r"(?:s|es|ed|d|ing)?\b", re.I)


def _clean_line(line):
    """Strip syntax that is not prose so counts and matches reflect the text a reader sees."""
    line = INLINE_CODE.sub("", line)
    line = HTML_COMMENT.sub("", line)
    line = MD_LINK.sub(r"\1", line)
    line = BARE_URL.sub("", line)
    return line


def lint(text, filename="<stdin>", max_words=DEFAULT_MAX_WORDS, mode="strict"):
    findings = []
    words_total = 0
    in_fence = False
    in_frontmatter = False
    # first occurrence of each synonym-group member: (group_idx, base) -> (line, col, match)
    seen_synonyms = {}
    lines = text.splitlines()
    for lineno, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if lineno == 1 and FRONTMATTER_DELIM.match(stripped):
            in_frontmatter = True
            continue
        if in_frontmatter:
            if FRONTMATTER_DELIM.match(stripped):
                in_frontmatter = False
            continue
        if CODE_FENCE.match(stripped):
            in_fence = not in_fence
            continue
        if in_fence or TABLE_ROW.match(raw) or MDX_IMPORT.match(raw):
            continue
        line = _clean_line(raw)
        words_total += len(line.split())
        for rule_id, level, pattern, msg in RULES:
            for m in pattern.finditer(line):
                findings.append({"file": filename, "line": lineno, "col": m.start() + 1,
                                 "rule": rule_id, "level": level,
                                 "match": m.group(0), "message": msg})
        for gi, group in enumerate(SYNONYM_GROUPS):
            for base in group:
                if (gi, base) in seen_synonyms:
                    continue
                m = _word_re(base).search(line)
                if m:
                    seen_synonyms[(gi, base)] = (lineno, m.start() + 1, m.group(0))
        for sent in re.split(r"(?<=[.!?])\s+", line):
            n = len(sent.split())
            if n > max_words:
                findings.append({"file": filename, "line": lineno, "col": 1,
                                 "rule": "long-sentence", "level": "advisory-free",
                                 "match": f"{n} words",
                                 "message": f"Sentence has {n} words (cap {max_words}). Split it."})
    # synonym rotation: flag each member after the first, at its first occurrence
    rotation_level = "advisory" if mode == "flavored" else "advisory-free"
    for gi, group in enumerate(SYNONYM_GROUPS):
        present = [(seen_synonyms[(gi, b)], b) for b in group if (gi, b) in seen_synonyms]
        if len(present) > 1:
            present.sort()  # document order
            first_base = present[0][1]
            for (lineno, col, match), base in present[1:]:
                findings.append({"file": filename, "line": lineno, "col": col,
                                 "rule": "synonym-rotation", "level": rotation_level,
                                 "match": match,
                                 "message": f"'{base}' and '{first_base}' name the same action. Pick one and use it every time."})
    findings.sort(key=lambda f: (f["line"], f["col"]))
    return findings, words_total


def expand_paths(paths):
    """Expand directories to doc files (sorted, deterministic). Files pass through unchanged."""
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for name in sorted(files):
                    if name.lower().endswith(DOC_EXTENSIONS):
                        out.append(os.path.join(root, name))
        else:
            out.append(p)
    return out


def summarize(per_file):
    rows = []
    for filename, (findings, words) in per_file.items():
        hard = sum(1 for f in findings if f["level"] == "advisory-free")
        advisory = len(findings) - hard
        per100 = round(hard * 100 / words, 1) if words else 0.0
        rows.append({"file": filename, "hard": hard, "advisory": advisory,
                     "words": words, "hard_per_100_words": per100})
    rows.sort(key=lambda r: (-r["hard_per_100_words"], -r["hard"], r["file"]))
    return rows


def report(findings, words_total, as_json, hard_count, baseline):
    rate = round(len(findings) * 100 / words_total, 1) if words_total else 0.0
    if as_json:
        print(json.dumps({"violations": findings, "count": len(findings),
                          "hard_count": hard_count, "baseline": baseline,
                          "words": words_total, "per_100_words": rate}, indent=2))
        return
    for f in findings:
        print(f"{f['file']}:{f['line']}:{f['col']} {f['rule']}: {f['message']} [{f['match']}]")
    print(f"\n{len(findings)} violations ({hard_count} hard, baseline {baseline}), "
          f"{words_total} words, {rate} per 100 words")
    print("Hedges/modality (may, might, could) are never flagged: confidence is content.")


def report_summary(rows, as_json, top, hard_count, baseline):
    shown = rows[:top] if top else rows
    if as_json:
        print(json.dumps({"files": shown, "file_count": len(rows),
                          "hard_count": hard_count, "baseline": baseline}, indent=2))
        return
    print(f"{'hard':>6} {'adv':>5} {'words':>7} {'/100w':>6}  file")
    for r in shown:
        print(f"{r['hard']:>6} {r['advisory']:>5} {r['words']:>7} {r['hard_per_100_words']:>6}  {r['file']}")
    if top and len(rows) > top:
        print(f"... {len(rows) - top} more file(s) not shown (use --top 0 for all)")
    print(f"\n{len(rows)} files, {hard_count} hard violations (baseline {baseline})")


def selftest():
    bad = ("The panel is removed; spin up the job. "
           "Perform an analysis of the seamless log. "
           "We have received the report.")
    findings, _ = lint(bad)
    rules = {f["rule"] for f in findings}
    for expected in ("semicolon", "phrasal-verb", "nominalization",
                     "marketing-adjective", "passive-voice", "present-perfect"):
        assert expected in rules, expected
    # hedges must never be flagged, including modal + perfect infinitive
    findings, _ = lint("The request may have failed. It could be a timeout. "
                       "The disk might have filled.")
    assert findings == [], findings
    # code blocks skipped
    findings, _ = lint("```\nx = a; y = b\n```")
    assert findings == []
    findings, _ = lint(("word " * 30).strip() + ".")
    assert any(f["rule"] == "long-sentence" for f in findings)
    # instruction cap is configurable
    findings, _ = lint(("word " * 22).strip() + ".", max_words=20)
    assert any(f["rule"] == "long-sentence" for f in findings)
    # synonym rotation: second member flagged, first named as the keeper
    findings, _ = lint("Check the config file. Then verify the output. Verify twice.")
    rot = [f for f in findings if f["rule"] == "synonym-rotation"]
    assert len(rot) == 1 and "'verify' and 'check'" in rot[0]["message"], rot
    assert rot[0]["level"] == "advisory-free"
    # flavored mode demotes rotation to advisory
    findings, _ = lint("Check the config file. Then verify the output.", mode="flavored")
    rot = [f for f in findings if f["rule"] == "synonym-rotation"]
    assert rot and rot[0]["level"] == "advisory", rot
    # single consistent term: no flag
    findings, _ = lint("Check the config. Check the output.")
    assert not any(f["rule"] == "synonym-rotation" for f in findings)
    # per-file labels
    findings, _ = lint("a; b", filename="x.md")
    assert findings[0]["file"] == "x.md"
    # YAML frontmatter skipped, table rows skipped, MDX imports skipped
    doc = ("---\ntitle: a; b\ndescription: " + ("w " * 40).strip() + "\n---\n"
           "import Foo from './foo'; export const x = 1;\n"
           "| a; b | " + ("w " * 40).strip() + " |\n"
           "Plain sentence.\n")
    findings, words = lint(doc)
    assert findings == [], findings
    assert words == 2, words
    # link URLs and inline code do not count as prose or trigger rules
    findings, words = lint("See [the guide](https://x.y/a;b?c=d) and `a; b` now.")
    assert findings == [], findings
    assert words == 5, words
    # directory expansion is deterministic and filtered
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "node_modules"))
        os.makedirs(os.path.join(tmp, "b"))
        for rel in ("z.md", "a.mdx", "b/c.md", "skip.png", "node_modules/x.md"):
            with open(os.path.join(tmp, rel), "w", encoding="utf-8") as fh:
                fh.write("x; y\n")
        got = [os.path.relpath(p, tmp) for p in expand_paths([tmp])]
        assert got == ["a.mdx", "z.md", os.path.join("b", "c.md")], got
    # summary ordering: worst rate first
    rows = summarize({"clean.md": ([], 100),
                      "bad.md": ([{"level": "advisory-free"}] * 3, 30),
                      "meh.md": ([{"level": "advisory-free"}, {"level": "advisory"}], 200)})
    assert [r["file"] for r in rows] == ["bad.md", "meh.md", "clean.md"], rows
    print("selftest OK")


def main(argv):
    if "--selftest" in argv:
        selftest()
        return 0
    as_json = "--json" in argv
    summary = "--summary" in argv
    baseline = 0
    top = 25
    max_words = DEFAULT_MAX_WORDS
    mode = "strict"
    disabled = set()
    paths = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--baseline":
            i += 1
            baseline = int(argv[i])
        elif a == "--disable":
            i += 1
            disabled = set(argv[i].split(","))
        elif a == "--max-words":
            i += 1
            max_words = int(argv[i])
        elif a == "--mode":
            i += 1
            mode = argv[i]
            if mode not in ("strict", "flavored"):
                print(f"unknown mode: {mode} (use strict or flavored)", file=sys.stderr)
                return 2
        elif a == "--top":
            i += 1
            top = int(argv[i])
        elif not a.startswith("--"):
            paths.append(a)
        i += 1

    per_file = {}
    findings, words_total = [], 0
    if paths:
        for p in expand_paths(paths):
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError as exc:
                print(f"{p}: cannot read ({exc})", file=sys.stderr)
                continue
            f, w = lint(text, filename=p, max_words=max_words, mode=mode)
            f = [x for x in f if x["rule"] not in disabled]
            per_file[p] = (f, w)
            findings.extend(f)
            words_total += w
    else:
        findings, words_total = lint(sys.stdin.read(), max_words=max_words, mode=mode)
        findings = [f for f in findings if f["rule"] not in disabled]

    hard_count = sum(1 for f in findings if f["level"] == "advisory-free")
    if summary:
        report_summary(summarize(per_file), as_json, top, hard_count, baseline)
    else:
        report(findings, words_total, as_json, hard_count, baseline)
    return 1 if hard_count > baseline else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
