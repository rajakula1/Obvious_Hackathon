"""Schema validator for QualityForge conventions.

Validates the scaffold's two versioned contract files against their JSON Schema
plus the semantic rules a schema cannot express:

  criteria  a completeness-criteria config (spec section 8.2): unique criterion
            IDs, and every assumption carries an explicit note (spec section 7.1)
  manifest  a test manifest (review R2: path + SHA-256 per test file): ISO-8601
            timestamp, unique paths, safe repo-relative paths; with --repo-root
            every recorded digest is re-hashed, so a test file changed since
            finalization fails loudly — the Verify gate of spec section 7.8

Usage (from the repository root):
  python -m qualityforge.tools.validate criteria <config.yaml|config.json>
  python -m qualityforge.tools.validate manifest <manifest.json> [--repo-root DIR]

Exit codes: 0 valid, 1 invalid, 2 usage or I/O error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast

import jsonschema
import yaml

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"
CRITERIA_SCHEMA_PATH = SCHEMAS_DIR / "completeness-criteria.schema.json"
MANIFEST_SCHEMA_PATH = SCHEMAS_DIR / "test-manifest.schema.json"

EXIT_VALID = 0
EXIT_INVALID = 1
EXIT_ERROR = 2


def load_config(path: Path) -> Any:
    """Load a YAML or JSON config file (JSON is a subset of YAML 1.2)."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return json.loads(text)


def _schema_errors(instance: Any, schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [f"schema: {e.json_path}: {e.message}" for e in validator.iter_errors(instance)]


def validate_criteria(config: Any) -> list[str]:
    """All errors (schema + semantics) for a completeness-criteria config."""
    errors = _schema_errors(config, CRITERIA_SCHEMA_PATH)
    if errors:
        return errors  # the semantic checks assume schema-valid structure

    typed = cast(dict[str, Any], config)
    criteria = typed["criteria"]
    ids = [criterion["id"] for criterion in criteria]
    errors.extend(
        f"semantic: duplicate criterion id '{duplicated}'"
        for duplicated in sorted({i for i in ids if ids.count(i) > 1})
    )
    errors.extend(
        f"semantic: {criterion['id']}: source is 'assumption' but no note records "
        "the assumption explicitly (spec section 7.1)"
        for criterion in criteria
        if criterion["source"] == "assumption" and not criterion.get("note")
    )
    return errors


def _unsafe_relpath(path: str) -> bool:
    """True for absolute paths or paths escaping the repo root via '..'."""
    rel = PurePosixPath(path)
    return rel.is_absolute() or ".." in rel.parts


def validate_manifest(manifest: Any) -> list[str]:
    """All errors (schema + semantics) for a test manifest (review R2)."""
    errors = _schema_errors(manifest, MANIFEST_SCHEMA_PATH)
    if errors:
        return errors

    typed = cast(dict[str, Any], manifest)
    try:
        datetime.fromisoformat(typed["recorded_at"].replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"semantic: recorded_at is not ISO-8601: {typed['recorded_at']!r}")

    paths = [entry["path"] for entry in typed["test_files"]]
    errors.extend(
        f"semantic: duplicate manifest path '{duplicated}'"
        for duplicated in sorted({p for p in paths if paths.count(p) > 1})
    )
    errors.extend(
        f"semantic: unsafe test path {path!r} (must be repo-relative, no '..')"
        for path in paths
        if _unsafe_relpath(path)
    )
    return errors


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recheck_manifest_hashes(manifest: dict[str, Any], repo_root: Path) -> list[str]:
    """Re-hash every manifest entry against repo_root (review R2, guard 2).

    Returns one error per drifted, missing, or unsafe entry; an empty list means
    no test file changed since the manifest was recorded.
    """
    errors: list[str] = []
    for entry in manifest["test_files"]:
        rel_path = entry["path"]
        if _unsafe_relpath(rel_path):
            errors.append(f"drift: unsafe test path {rel_path!r}")
            continue
        target = repo_root / PurePosixPath(rel_path)
        if not target.is_file():
            errors.append(f"drift: {rel_path}: not found under {repo_root}")
            continue
        actual = sha256_file(target)
        if actual != entry["sha256"]:
            errors.append(
                f"drift: {rel_path}: sha256 mismatch — test file changed since "
                f"finalization (manifest {entry['sha256'][:12]}, actual {actual[:12]}); "
                "test tampering is barred (spec section 11.4, review R2)"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m qualityforge.tools.validate",
        description="Validate QualityForge criteria configs and test manifests.",
    )
    subparsers = parser.add_subparsers(dest="kind", required=True)

    criteria_parser = subparsers.add_parser(
        "criteria", help="validate a completeness-criteria config (spec section 8.2)"
    )
    criteria_parser.add_argument("config", type=Path)

    manifest_parser = subparsers.add_parser(
        "manifest", help="validate a test manifest (review R2)"
    )
    manifest_parser.add_argument("config", type=Path)
    manifest_parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="re-hash every listed test file against this root (Verify gate)",
    )

    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: cannot load {args.config}: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.kind == "criteria":
        errors = validate_criteria(config)
    else:
        errors = validate_manifest(config)
        if args.repo_root is not None and not errors:
            errors = recheck_manifest_hashes(cast(dict[str, Any], config), args.repo_root)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"INVALID: {args.config} ({len(errors)} error(s))", file=sys.stderr)
        return EXIT_INVALID

    print(f"OK: {args.config} ({args.kind})")
    return EXIT_VALID


if __name__ == "__main__":
    sys.exit(main())
