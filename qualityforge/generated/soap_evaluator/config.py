"""Criteria-config loader (spec section 8.2, review R5).

The evaluator consumes the versioned YAML config — never a hardcoded copy of
the rules. Changing criteria is a change to the config file (a new
criteria_version), not an evaluator rewrite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "qualityforge" / "workloads" / "soap-evaluator" / "criteria-v1.yaml"
)

_REQUIRED_KEYS = ("criteria_version", "section_detection", "criteria")
_REQUIRED_SECTION_KEYS = ("header_markers", "fallback")


class CriteriaConfigError(ValueError):
    """The criteria config is missing required structure — fail loudly."""


def load_criteria(path: Path | str | None = None) -> dict[str, Any]:
    """Load and structurally validate a criteria config; a config that cannot
    name its own version, detection strategy, and criteria list must stop the
    evaluator at startup, not drift silently at request time."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise CriteriaConfigError(f"{config_path}: config must be a mapping")
    missing = [key for key in _REQUIRED_KEYS if key not in raw]
    if missing:
        raise CriteriaConfigError(f"{config_path}: missing required keys {missing}")
    detection = raw["section_detection"]
    if not isinstance(detection, dict):
        raise CriteriaConfigError(f"{config_path}: section_detection must be a mapping")
    missing = [key for key in _REQUIRED_SECTION_KEYS if key not in detection]
    if missing:
        raise CriteriaConfigError(f"{config_path}: section_detection missing {missing} (review R5)")
    criteria = raw["criteria"]
    if not isinstance(criteria, list) or not criteria:
        raise CriteriaConfigError(f"{config_path}: criteria must be a non-empty list")
    versions = {c.get("id") for c in criteria if isinstance(c, dict)}
    if None in versions or len(versions) != len(criteria):
        raise CriteriaConfigError(f"{config_path}: every criterion needs a unique id")
    return raw
