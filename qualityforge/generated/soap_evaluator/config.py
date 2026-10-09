"""Criteria-config loader (stage-2 spec section 3, config.py row).

Loads the versioned YAML criteria config — the of-record file is
``qualityforge/workloads/soap-evaluator/criteria-v1.yaml`` — and validates the
required keys, failing loudly on drift. The evaluator consumes the config
file, never a hardcoded copy of the rules: criteria change through version
bumps of this file, not evaluator rewrites (workload skill, section 8.2).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

REQUIRED_TOP_LEVEL_KEYS = ("criteria_version", "section_detection", "criteria")
REQUIRED_SECTION_DETECTION_KEYS = ("strategy", "header_markers", "fallback")
REQUIRED_CRITERION_KEYS = ("id", "statement", "section", "check_type")
# The of-record criteria config for this workload, resolved from the package
# location so ``create_app()`` works from any working directory.
DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[3]
    / "qualityforge/workloads/soap-evaluator/criteria-v1.yaml"
)


class CriteriaConfigError(ValueError):
    """The criteria config is missing required keys or is structurally wrong."""


def validate_criteria(config: Any) -> Mapping[str, Any]:
    """Validate a parsed criteria config, failing loudly on drift.

    Returns the config unchanged when valid so callers can keep using the
    parsed mapping directly. Every check names the drifted key in its error.
    """
    if not isinstance(config, Mapping):
        raise CriteriaConfigError(
            f"criteria config must be a mapping, got {type(config).__name__}"
        )
    missing = [key for key in REQUIRED_TOP_LEVEL_KEYS if key not in config]
    if missing:
        raise CriteriaConfigError(f"criteria config is missing required keys: {missing}")

    version = config["criteria_version"]
    if not isinstance(version, str) or not version.strip():
        raise CriteriaConfigError("criteria_version must be a non-empty string")

    detection = config["section_detection"]
    if not isinstance(detection, Mapping):
        raise CriteriaConfigError("section_detection must be a mapping")
    missing_detection = [
        key for key in REQUIRED_SECTION_DETECTION_KEYS if key not in detection
    ]
    if missing_detection:
        raise CriteriaConfigError(
            f"section_detection is missing required keys: {missing_detection}"
        )
    markers = detection["header_markers"]
    if not isinstance(markers, Mapping) or not markers:
        raise CriteriaConfigError(
            "section_detection.header_markers must be a non-empty mapping"
        )

    criteria = config["criteria"]
    if not isinstance(criteria, list) or not criteria:
        raise CriteriaConfigError("criteria must be a non-empty list")
    for index, criterion in enumerate(criteria):
        if not isinstance(criterion, Mapping):
            raise CriteriaConfigError(f"criteria[{index}] must be a mapping")
        missing_criterion = [key for key in REQUIRED_CRITERION_KEYS if key not in criterion]
        if missing_criterion:
            raise CriteriaConfigError(
                f"criteria[{index}] ({criterion.get('id', '?')}) is missing required keys: "
                f"{missing_criterion}"
            )
    return config


def load_criteria(path: Path | str) -> Mapping[str, Any]:
    """Load and validate the criteria YAML at ``path`` (loud on drift)."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        config = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CriteriaConfigError(f"criteria config {path} is not valid YAML: {exc}") from exc
    return validate_criteria(config)
