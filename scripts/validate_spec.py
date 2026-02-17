#!/usr/bin/env python3
"""Validate local skills against core AgentSkills specification rules.

Checks are based on:
- https://agentskills.io/specification
- https://agentskills.io/what-are-skills
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
LOCAL_SKILL_ROOTS = [ROOT_DIR / "skills", ROOT_DIR / "private-skills"]
SECTION_ROOTS = ("references", "scripts", "assets")
PUBLIC_SKILLS_ROOT = ROOT_DIR / "skills"
PUBLIC_SKILL_LICENSE = "AGPL-3.0-only"
PUBLIC_SKILL_SOURCE = "https://github.com/vincentkoc/dotskills"
REPO_LICENSE_FILE = ROOT_DIR / "LICENSE"
AGENTS_DOC_FILE = ROOT_DIR / "AGENTS.md"
PUBLIC_OPENAI_YAML_FILE = Path("agents/openai.yaml")
PUBLIC_OPENAI_REQUIRED_INTERFACE_FIELDS = (
    "display_name",
    "short_description",
    "default_prompt",
    "icon_small",
    "icon_large",
)

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TOP_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
METADATA_KEY_RE = re.compile(r"^\s{2,}([A-Za-z0-9_.-]+):\s*(.*)$")
MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
PATH_RE = re.compile(r"(?<![\w./-])((?:references|scripts|assets)/[A-Za-z0-9._/-]+)")


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def find_local_skill_dirs() -> List[Path]:
    skill_dirs: List[Path] = []
    for root in LOCAL_SKILL_ROOTS:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / "SKILL.md").is_file():
                skill_dirs.append(child)
    return skill_dirs


def parse_frontmatter(
    text: str, skill_file: Path
) -> Tuple[Dict[str, object], str, List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    lines = text.splitlines()

    if not lines or lines[0].strip() != "---":
        return {}, "", [f"{skill_file}:1 missing YAML frontmatter start ('---')"], warnings

    front_end = None
    for idx, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            front_end = idx
            break
    if front_end is None:
        return {}, "", [f"{skill_file}: missing YAML frontmatter end ('---')"], warnings

    front_lines = lines[1 : front_end - 1]
    body = "\n".join(lines[front_end:])
    data: Dict[str, object] = {}
    current_block = ""

    for line_no, raw_line in enumerate(front_lines, start=2):
        line = raw_line.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        top_match = TOP_KEY_RE.match(line)
        if top_match:
            key = top_match.group(1)
            raw_value = top_match.group(2)
            if key == "metadata":
                current_block = "metadata"
                if raw_value.strip() == "":
                    data["metadata"] = {}
                else:
                    errors.append(
                        f"{skill_file}:{line_no} metadata must be a key-value map (indented entries)"
                    )
                    data["metadata"] = {}
                continue

            current_block = ""
            data[key] = strip_quotes(raw_value)
            continue

        if current_block == "metadata":
            meta_match = METADATA_KEY_RE.match(line)
            if not meta_match:
                errors.append(
                    f"{skill_file}:{line_no} invalid metadata entry; expected '  key: value'"
                )
                continue
            meta = data.setdefault("metadata", {})
            if not isinstance(meta, dict):
                errors.append(f"{skill_file}:{line_no} metadata must be a map")
                continue
            meta_key = meta_match.group(1)
            meta_val = strip_quotes(meta_match.group(2))
            meta[meta_key] = meta_val
            continue

        errors.append(f"{skill_file}:{line_no} invalid frontmatter line: {line}")

    return data, body, errors, warnings


def validate_name(
    skill_dir: Path, skill_file: Path, front: Dict[str, object], errors: List[str]
) -> None:
    name = str(front.get("name", "")).strip()
    if not name:
        errors.append(f"{skill_file}: missing required frontmatter field 'name'")
        return
    if len(name) > 64:
        errors.append(f"{skill_file}: name must be <= 64 characters")
    if not NAME_RE.fullmatch(name):
        errors.append(
            f"{skill_file}: name must use lowercase letters, numbers, and single hyphens only"
        )
    if name != skill_dir.name:
        errors.append(
            f"{skill_file}: name '{name}' must match parent directory '{skill_dir.name}'"
        )


def validate_description(skill_file: Path, front: Dict[str, object], errors: List[str]) -> None:
    description = str(front.get("description", "")).strip()
    if not description:
        errors.append(f"{skill_file}: missing required frontmatter field 'description'")
        return
    if len(description) > 1024:
        errors.append(f"{skill_file}: description must be <= 1024 characters")


def validate_optional_frontmatter(
    skill_file: Path, front: Dict[str, object], errors: List[str], warnings: List[str]
) -> None:
    compatibility = str(front.get("compatibility", "")).strip()
    if "compatibility" in front:
        if not compatibility:
            errors.append(f"{skill_file}: compatibility must be non-empty when provided")
        elif len(compatibility) > 500:
            errors.append(f"{skill_file}: compatibility must be <= 500 characters")

    if "metadata" in front:
        metadata = front["metadata"]
        if not isinstance(metadata, dict):
            errors.append(f"{skill_file}: metadata must be a key-value map")
        else:
            for key, value in metadata.items():
                key_s = str(key).strip()
                val_s = str(value).strip()
                if not key_s:
                    errors.append(f"{skill_file}: metadata keys must be non-empty strings")
                if val_s == "":
                    errors.append(f"{skill_file}: metadata['{key_s}'] must be non-empty")

    if "allowed-tools" in front:
        allowed_tools = str(front.get("allowed-tools", "")).strip()
        if not allowed_tools:
            errors.append(f"{skill_file}: allowed-tools must be non-empty when provided")
        if "," in allowed_tools:
            warnings.append(
                f"{skill_file}: allowed-tools should be space-delimited (commas are discouraged)"
            )


def is_internal_skill(front: Dict[str, object]) -> bool:
    metadata = front.get("metadata")
    if not isinstance(metadata, dict):
        return False
    internal = str(metadata.get("internal", "")).strip().lower()
    return internal in {"1", "true", "yes", "y", "on"}


def is_public_skill(skill_dir: Path, front: Dict[str, object]) -> bool:
    return skill_dir.parent == PUBLIC_SKILLS_ROOT and not is_internal_skill(front)


def validate_repo_license(errors: List[str]) -> None:
    if not REPO_LICENSE_FILE.is_file():
        errors.append(
            f"{REPO_LICENSE_FILE}: missing repository license file (expected AGPL-3.0 text)"
        )
        return

    text = REPO_LICENSE_FILE.read_text(encoding="utf-8", errors="replace")
    if "GNU AFFERO GENERAL PUBLIC LICENSE" not in text:
        errors.append(f"{REPO_LICENSE_FILE}: does not look like AGPL-3.0 license text")
    if "Version 3, 19 November 2007" not in text:
        errors.append(f"{REPO_LICENSE_FILE}: expected AGPLv3 version marker is missing")


def validate_public_skill_policy(
    skill_dir: Path, skill_file: Path, front: Dict[str, object], errors: List[str]
) -> None:
    if not is_public_skill(skill_dir, front):
        return

    license_value = str(front.get("license", "")).strip()
    if license_value != PUBLIC_SKILL_LICENSE:
        errors.append(
            f"{skill_file}: public skill must set license: {PUBLIC_SKILL_LICENSE}"
        )

    metadata = front.get("metadata")
    if not isinstance(metadata, dict):
        errors.append(
            f"{skill_file}: public skill must define metadata.source: {PUBLIC_SKILL_SOURCE}"
        )
        return

    source_value = str(metadata.get("source", "")).strip()
    if source_value != PUBLIC_SKILL_SOURCE:
        errors.append(
            f"{skill_file}: public skill metadata.source must be {PUBLIC_SKILL_SOURCE}"
        )


def parse_scalar(value: str) -> object:
    value = strip_quotes(value.strip())
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value


def parse_simple_yaml_mapping(payload: str, context: str, errors: List[str]) -> Dict[str, object]:
    data: Dict[str, object] = {}
    stack: list[tuple[int, Dict[str, object]]] = [(0, data)]

    for raw_line in payload.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent % 2 != 0:
            errors.append(f"{context}: unsupported indentation level: {line}")
            continue

        while indent < stack[-1][0]:
            stack.pop()

        if indent > stack[-1][0] and indent != stack[-1][0] + 2:
            errors.append(f"{context}: unsupported indentation level: {line}")
            continue

        target = stack[-1][1]
        if ":" not in line:
            errors.append(f"{context}: invalid line (expected key: value): {line}")
            continue

        key, value = line.strip().split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            errors.append(f"{context}: empty key in line: {line}")
            continue

        if value == "":
            new_map: Dict[str, object] = {}
            target[key] = new_map
            stack.append((indent + 2, new_map))
        else:
            target[key] = parse_scalar(value)

    return data


def parse_openai_defaults_from_agents(errors: List[str]) -> Dict[str, str]:
    if not AGENTS_DOC_FILE.is_file():
        errors.append(f"{AGENTS_DOC_FILE}: missing AGENTS.md for openai defaults")
        return {}

    text = AGENTS_DOC_FILE.read_text(encoding="utf-8", errors="replace")
    section_match = re.search(
        r"^## OpenAI Metadata Defaults\s*$([\s\S]*?)(?=^##\s+|\Z)",
        text,
        flags=re.MULTILINE,
    )
    if not section_match:
        errors.append(
            f"{AGENTS_DOC_FILE}: missing '## OpenAI Metadata Defaults' section"
        )
        return {}

    section_text = section_match.group(1)
    block_match = re.search(r"```yaml\s*([\s\S]*?)\s*```", section_text)
    if not block_match:
        errors.append(
            f"{AGENTS_DOC_FILE}: OpenAI defaults section must include a ```yaml fenced block"
        )
        return {}

    defaults_payload = parse_simple_yaml_mapping(
        block_match.group(1), f"{AGENTS_DOC_FILE} openai defaults", errors
    )
    openai_defaults = defaults_payload.get("openai_yaml_defaults")
    if not isinstance(openai_defaults, dict):
        errors.append(
            f"{AGENTS_DOC_FILE}: defaults block must define openai_yaml_defaults mapping"
        )
        return {}

    interface_defaults = openai_defaults.get("interface")
    if not isinstance(interface_defaults, dict):
        errors.append(
            f"{AGENTS_DOC_FILE}: openai_yaml_defaults must include interface mapping"
        )
        return {}

    parsed_defaults: Dict[str, str] = {}
    for key, value in interface_defaults.items():
        key_s = str(key).strip()
        value_s = str(value).strip()
        if not key_s:
            errors.append(f"{AGENTS_DOC_FILE}: empty interface default key")
            continue
        if not value_s:
            errors.append(
                f"{AGENTS_DOC_FILE}: openai interface default '{key_s}' must be non-empty"
            )
            continue
        parsed_defaults[key_s] = value_s

    for required_key in ("icon_small", "icon_large"):
        if required_key not in parsed_defaults:
            errors.append(
                f"{AGENTS_DOC_FILE}: openai interface default '{required_key}' is required"
            )

    return parsed_defaults


def validate_openai_icon_path(
    skill_dir: Path, openai_path: Path, field_name: str, value: str, errors: List[str]
) -> None:
    if value.startswith(("http://", "https://", "data:")):
        return

    target = (skill_dir / value).resolve()
    if not target.exists():
        errors.append(
            f"{openai_path}: interface.{field_name} path not found from skill root: '{value}'"
        )


def validate_public_skill_openai_metadata(
    skill_dir: Path,
    skill_file: Path,
    front: Dict[str, object],
    openai_defaults: Dict[str, str],
    errors: List[str],
    warnings: List[str],
) -> None:
    if not is_public_skill(skill_dir, front):
        return

    openai_path = skill_dir / PUBLIC_OPENAI_YAML_FILE
    if not openai_path.is_file():
        errors.append(
            f"{skill_file}: public skill must include {PUBLIC_OPENAI_YAML_FILE.as_posix()}"
        )
        return

    payload = openai_path.read_text(encoding="utf-8", errors="replace")
    openai_data = parse_simple_yaml_mapping(payload, str(openai_path), errors)
    if not openai_data:
        return

    interface = openai_data.get("interface")
    if not isinstance(interface, dict):
        # Backward compatibility for legacy top-level fields.
        legacy_fields = {
            key: openai_data.get(key)
            for key in PUBLIC_OPENAI_REQUIRED_INTERFACE_FIELDS
            if key in openai_data
        }
        if legacy_fields:
            warnings.append(
                f"{openai_path}: legacy top-level interface fields detected; nest them under 'interface'"
            )
            interface = legacy_fields
        else:
            errors.append(f"{openai_path}: missing required top-level mapping 'interface'")
            return

    for field in PUBLIC_OPENAI_REQUIRED_INTERFACE_FIELDS:
        value = str(interface.get(field, "")).strip()
        if not value:
            errors.append(f"{openai_path}: interface.{field} is required for public skills")

    for key, expected_value in openai_defaults.items():
        actual_value = str(interface.get(key, "")).strip()
        if actual_value != expected_value:
            errors.append(
                f"{openai_path}: interface.{key} must match AGENTS.md default '{expected_value}'"
            )

    for icon_field in ("icon_small", "icon_large"):
        value = str(interface.get(icon_field, "")).strip()
        if value:
            validate_openai_icon_path(skill_dir, openai_path, icon_field, value, errors)

    policy = openai_data.get("policy")
    if policy is not None:
        if not isinstance(policy, dict):
            errors.append(f"{openai_path}: policy must be a mapping when provided")
        elif "allow_implicit_invocation" in policy and not isinstance(
            policy.get("allow_implicit_invocation"), bool
        ):
            errors.append(f"{openai_path}: policy.allow_implicit_invocation must be boolean")


def normalize_ref(raw_ref: str) -> str:
    ref = raw_ref.strip().strip("`'\"")
    ref = ref.split("#", 1)[0]
    ref = ref.split("?", 1)[0]
    ref = re.sub(r"[),.;:]+$", "", ref)
    return ref


def extract_relative_refs(body: str) -> List[str]:
    refs: set[str] = set()
    for match in MD_LINK_RE.finditer(body):
        target = normalize_ref(match.group(1))
        if target.startswith(("http://", "https://", "mailto:", "/")):
            continue
        if target.startswith(SECTION_ROOTS):
            refs.add(target)

    for match in PATH_RE.finditer(body):
        refs.add(normalize_ref(match.group(1)))

    return sorted(refs)


def validate_refs(
    skill_dir: Path, skill_file: Path, body: str, errors: List[str], warnings: List[str]
) -> None:
    for ref in extract_relative_refs(body):
        if ".." in Path(ref).parts:
            errors.append(f"{skill_file}: disallowed upward path in reference '{ref}'")
            continue

        parts = Path(ref).parts
        if len(parts) > 2:
            warnings.append(
                f"{skill_file}: '{ref}' is too deep; keep references one level from SKILL.md"
            )
            continue

        target = skill_dir / ref
        if not target.exists():
            warnings.append(f"{skill_file}: referenced path does not exist: '{ref}'")


def validate_body(skill_file: Path, body: str, errors: List[str], warnings: List[str]) -> None:
    if not body.strip():
        errors.append(f"{skill_file}: markdown body is empty")
        return

    lines = body.splitlines()
    if len(lines) > 500:
        warnings.append(f"{skill_file}: SKILL.md body has {len(lines)} lines (recommended < 500)")


def run_skills_ref_validator(skill_dirs: Sequence[Path]) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if shutil.which("skills-ref") is None:
        warnings.append("skills-ref not found in PATH; skipping external validator")
        return errors, warnings

    for skill_dir in skill_dirs:
        proc = subprocess.run(
            ["skills-ref", "validate", str(skill_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
            errors.append(f"{skill_dir}: skills-ref validate failed: {err}")
    return errors, warnings


def main() -> int:
    skill_dirs = find_local_skill_dirs()
    if not skill_dirs:
        print("[WARN] No local SKILL.md entries found under skills/ or private-skills/")
        return 0

    errors: List[str] = []
    warnings: List[str] = []
    validated = 0
    validate_repo_license(errors)
    openai_defaults = parse_openai_defaults_from_agents(errors)

    for skill_dir in skill_dirs:
        skill_file = skill_dir / "SKILL.md"
        text = skill_file.read_text(encoding="utf-8")
        front, body, parse_errors, parse_warnings = parse_frontmatter(text, skill_file)
        errors.extend(parse_errors)
        warnings.extend(parse_warnings)
        if parse_errors:
            continue

        validate_name(skill_dir, skill_file, front, errors)
        validate_description(skill_file, front, errors)
        validate_optional_frontmatter(skill_file, front, errors, warnings)
        validate_public_skill_policy(skill_dir, skill_file, front, errors)
        validate_public_skill_openai_metadata(
            skill_dir, skill_file, front, openai_defaults, errors, warnings
        )
        validate_body(skill_file, body, errors, warnings)
        validate_refs(skill_dir, skill_file, body, errors, warnings)
        validated += 1

    skills_ref_errors, skills_ref_warnings = run_skills_ref_validator(skill_dirs)
    errors.extend(skills_ref_errors)
    warnings.extend(skills_ref_warnings)

    for warning in warnings:
        print(f"[WARN] {warning}")
    for error in errors:
        print(f"[FAIL] {error}")

    if errors:
        print(
            f"AgentSkills spec validation failed with {len(errors)} issue(s) "
            f"across {len(skill_dirs)} skill(s)."
        )
        return 1

    print(
        f"AgentSkills spec validation passed. Checked {validated} local skill(s); "
        f"{len(warnings)} warning(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
