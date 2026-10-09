"""Dataset validator for the synthetic SOAP notes corpus (spec section 8.4).

Validates qualityforge/workloads/soap-evaluator/data against the versioned
completeness-criteria config before any factory run consumes it:

  structure   every note file parses, note_id matches the filename and the
              corpus convention, required fields are well-typed (spec 8.3/8.4)
  labels      expected findings cover exactly the criteria config's criterion
              IDs, in config order, with statuses from the response vocabulary
              (present | missing | partial); overall_status is "complete" if
              and only if every criterion status is "present"
  integrity   the corpus manifest's per-note SHA-256 digests match the files
              on disk — the same re-hash discipline as the R2 test manifest
  phi         the section 11.1 synthetic-data rule, mechanized: a pattern scan
              over every string in every note record returns zero hits — always

Usage (from the repository root):
  python -m qualityforge.tools.validate_dataset
  python -m qualityforge.tools.validate_dataset --data DIR --criteria CONFIG.yaml

Exit codes: 0 valid, 1 invalid, 2 usage or I/O error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, cast

import yaml

from qualityforge.tools.validate import (
    EXIT_ERROR,
    EXIT_INVALID,
    EXIT_VALID,
    load_config,
    validate_criteria,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "workloads" / "soap-evaluator" / "data"
# Of-record criteria config for Run 1 (PR #3). Override with --criteria when
# validating against a different versioned config.
DEFAULT_CRITERIA = (
    Path(__file__).resolve().parents[1] / "workloads" / "soap-evaluator" / "criteria-v1.yaml"
)

# Dataset contract (spec section 8.4): a labeled corpus of 20 to 30 notes.
MIN_NOTES = 20
MAX_NOTES = 30
NOTE_ID_PATTERN = re.compile(r"^soap-[0-9]{3}$")
NOTE_ID_FIELD = "note_id"
CATEGORIES = {
    "complete",
    "missing_section",
    "empty_section",
    "partial_content",
    "duplicate_headers",
    "plan_unrelated",
    "fallback_detection",
    "layout_variation",
}
FINDING_STATUSES = {"present", "missing", "partial"}
OVERALL_STATUSES = {"complete", "incomplete"}

# PHI-pattern scan (section 11.1: no PHI enters the workspace, sandbox, logs, or
# demo material). The corpus is authored without names, absolute dates, contact
# details, or identifiers; the scan keeps that property mechanized. Relative
# time references ("two days ago") and clinical measurements are not PHI.
PHI_PATTERNS: dict[str, re.Pattern[str]] = {
    "dob_label": re.compile(r"(?i)\b(?:dob|d\.o\.b\.|date\s+of\s+birth)\b"),
    "mrn_label": re.compile(r"(?i)\b(?:mrn|medical\s+record(?:\s+number)?)\b"),
    "ssn_label": re.compile(r"(?i)\b(?:ssn|social\s+security)\b"),
    "ssn_number": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone_number": re.compile(r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    "email_address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "long_digit_run": re.compile(r"\b\d{7,}\b"),
    "five_digit_run": re.compile(r"\b\d{5}\b"),
    "date_iso": re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    "date_numeric_us": re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    "date_month_name": re.compile(
        r"(?i)\b(?:january|february|march|april|may|june|july|august|september|"
        r"october|november|december)\s+\d{1,2},?\s+\d{4}\b"
    ),
    "patient_name_pair": re.compile(r"\b(?:patient|pt)\s*[:=]\s*[A-Z][a-z]+\s+[A-Z][a-z]+"),
}


def iter_strings(value: Any) -> list[str]:
    """Every string in a JSON-like structure, in document order."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for key, item in value.items() for text in iter_strings([key, item])]
    if isinstance(value, list):
        return [text for item in value for text in iter_strings(item)]
    return []


def scan_phi(text: str) -> list[tuple[str, int]]:
    """PHI-pattern hits in one text as (pattern_name, 1-based line number)."""
    hits: list[tuple[str, int]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for name, pattern in PHI_PATTERNS.items():
            if pattern.search(line):
                hits.append((name, line_number))
    return hits


def load_notes(data_dir: Path) -> tuple[list[tuple[Path, dict[str, Any]]], list[str]]:
    """Load notes/*.json in sorted order; JSON or type failures become errors."""
    notes_dir = data_dir / "notes"
    errors: list[str] = []
    loaded: list[tuple[Path, dict[str, Any]]] = []
    if not notes_dir.is_dir():
        return loaded, [f"semantic: notes directory not found: {notes_dir}"]
    for path in sorted(notes_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(f"semantic: {path.name}: invalid JSON ({exc})")
            continue
        if not isinstance(record, dict):
            errors.append(f"semantic: {path.name}: top-level JSON must be an object")
            continue
        loaded.append((path, cast(dict[str, Any], record)))
    return loaded, errors


def _check_labels(note_id: str, record: dict[str, Any], criteria: dict[str, Any]) -> list[str]:
    """Label well-formedness for one record against the criteria config."""
    errors: list[str] = []
    expected = record["expected"]
    overall = expected["overall_status"]
    if overall not in OVERALL_STATUSES:
        errors.append(
            f"semantic: {note_id}: expected.overall_status {overall!r} "
            f"not in {sorted(OVERALL_STATUSES)}"
        )

    criterion_order = [criterion["id"] for criterion in criteria["criteria"]]
    seen: list[str] = []
    for position, finding in enumerate(expected["findings"]):
        cid = finding["criterion_id"]
        seen.append(cid)
        status = finding["status"]
        if status not in FINDING_STATUSES:
            errors.append(
                f"semantic: {note_id}: finding {position} status {status!r} "
                f"not in {sorted(FINDING_STATUSES)}"
            )
        if cid not in criterion_order:
            errors.append(
                f"semantic: {note_id}: finding {position} references unknown criterion {cid!r}"
            )
    if seen != criterion_order:
        errors.append(
            f"semantic: {note_id}: expected findings must cover exactly the criteria config IDs "
            f"in config order ({', '.join(criterion_order)}); got ({', '.join(seen)})"
        )

    all_present = all(finding["status"] == "present" for finding in expected["findings"])
    expected_overall = "complete" if all_present else "incomplete"
    if overall != expected_overall:
        errors.append(
            f"semantic: {note_id}: overall_status {overall!r} inconsistent with per-criterion "
            f"statuses (complete iff every criterion is present)"
        )
    return errors


def validate_records(
    loaded: list[tuple[Path, dict[str, Any]]], criteria: dict[str, Any]
) -> list[str]:
    """Structure + label checks across all loaded records."""
    errors: list[str] = []
    seen_ids: dict[str, str] = {}
    for path, record in loaded:
        note_id = record.get(NOTE_ID_FIELD)
        label = f"{path.name}: " if not isinstance(note_id, str) else f"{note_id} ({path.name}): "
        for field in (NOTE_ID_FIELD, "category", "note_text", "expected", "rationale"):
            if field not in record:
                errors.append(f"semantic: {label}missing required field {field!r}")
        if not isinstance(note_id, str) or not NOTE_ID_PATTERN.fullmatch(note_id):
            errors.append(
                f"semantic: {label}note_id {note_id!r} does not match {NOTE_ID_PATTERN.pattern}"
            )
            continue
        if note_id in seen_ids:
            errors.append(f"semantic: {note_id}: duplicate note_id (also in {seen_ids[note_id]})")
        seen_ids[note_id] = path.name
        if path.name != f"{note_id}.json":
            errors.append(f"semantic: {note_id}: filename must be {note_id}.json")

        category = record.get("category")
        if category not in CATEGORIES:
            errors.append(f"semantic: {note_id}: category {category!r} not in {sorted(CATEGORIES)}")
        text = record.get("note_text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"semantic: {note_id}: note_text must be a non-empty string")
        rationale = record.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(f"semantic: {note_id}: rationale must be a non-empty string")
        visit_type = record.get("visit_type")
        if visit_type is not None and not isinstance(visit_type, str):
            errors.append(f"semantic: {note_id}: visit_type must be a string when present")

        if isinstance(record.get("expected"), dict) and isinstance(criteria.get("criteria"), list):
            errors.extend(_check_labels(note_id, record, criteria))
    return errors


def _unsafe_relpath(path: str) -> bool:
    rel = PurePosixPath(path)
    return rel.is_absolute() or ".." in rel.parts


def validate_manifest(
    manifest: dict[str, Any], data_dir: Path, loaded: list[tuple[Path, dict[str, Any]]]
) -> list[str]:
    """Corpus-manifest consistency: counts, coverage, and per-note re-hash."""
    errors: list[str] = []
    required = (
        "manifest_version",
        "criteria_version",
        "note_count",
        "category_counts",
        "phi_scan",
        "notes",
    )
    for field in required:
        if field not in manifest:
            errors.append(f"semantic: corpus manifest missing required field {field!r}")
    if errors:
        return errors

    phi_scan = manifest["phi_scan"]
    if not isinstance(phi_scan, dict) or phi_scan.get("expected_hits") != 0:
        errors.append("semantic: corpus manifest phi_scan.expected_hits must be 0 (section 11.1)")

    actual_paths = {f"notes/{path.name}" for path, _ in loaded}
    listed: dict[str, str] = {}
    for entry in manifest["notes"]:
        rel_path = entry.get("path", "")
        digest = entry.get("sha256", "")
        if not isinstance(rel_path, str) or not isinstance(digest, str):
            errors.append(
                f"semantic: corpus manifest entry with path {rel_path!r} must carry "
                f"string path and sha256"
            )
            continue
        if _unsafe_relpath(rel_path):
            errors.append(f"drift: unsafe manifest path {rel_path!r}")
            continue
        if rel_path in listed:
            errors.append(f"semantic: duplicate manifest path {rel_path!r}")
        listed[rel_path] = digest
        target = data_dir / PurePosixPath(rel_path)
        if not target.is_file():
            errors.append(f"drift: {rel_path}: not found under {data_dir}")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != digest:
            errors.append(
                f"drift: {rel_path}: sha256 mismatch — note file changed since the manifest was "
                f"recorded (manifest {digest[:12]}, actual {actual[:12]}); re-record the manifest "
                f"after any corpus edit"
            )
    for missing in sorted(actual_paths - set(listed)):
        errors.append(f"drift: {missing}: note file on disk is not listed in the corpus manifest")
    for extra in sorted(set(listed) - actual_paths):
        errors.append(f"drift: {extra}: manifest lists a note file that no longer exists")

    if manifest["note_count"] != len(loaded):
        errors.append(
            f"semantic: manifest note_count {manifest['note_count']} != corpus size {len(loaded)}"
        )
    if not MIN_NOTES <= len(loaded) <= MAX_NOTES:
        errors.append(
            f"semantic: corpus size {len(loaded)} outside the section 8.4 contract "
            f"({MIN_NOTES}-{MAX_NOTES})"
        )

    counts = Counter(record.get("category") for _, record in loaded)
    if dict(counts) != manifest["category_counts"]:
        errors.append(
            f"semantic: manifest category_counts {manifest['category_counts']} != "
            f"corpus {dict(counts)}"
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m qualityforge.tools.validate_dataset",
        description="Validate the synthetic SOAP notes corpus (spec sections 8.4 and 11.1).",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DATA_DIR,
        help="corpus directory (default: workloads/soap-evaluator/data)",
    )
    parser.add_argument(
        "--criteria",
        type=Path,
        default=DEFAULT_CRITERIA,
        help="completeness-criteria config the labels align to",
    )
    args = parser.parse_args(argv)

    if not args.data.is_dir():
        print(f"ERROR: corpus directory not found: {args.data}", file=sys.stderr)
        return EXIT_ERROR

    try:
        criteria = load_config(args.criteria)
        criteria_errors = validate_criteria(criteria)
        manifest = cast(
            dict[str, Any],
            json.loads((args.data / "corpus.manifest.json").read_text(encoding="utf-8")),
        )
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: cannot load inputs: {exc}", file=sys.stderr)
        return EXIT_ERROR

    errors: list[str] = []
    if criteria_errors:
        errors.extend(f"criteria config invalid: {error}" for error in criteria_errors)
    elif manifest.get("criteria_version") != criteria["criteria_version"]:
        errors.append(
            f"semantic: manifest criteria_version {manifest.get('criteria_version')!r} != "
            f"criteria config {criteria['criteria_version']!r} — labels and criteria "
            f"must stay aligned"
        )

    loaded, load_errors = load_notes(args.data)
    errors.extend(load_errors)
    if not criteria_errors:
        errors.extend(validate_records(loaded, criteria))
        errors.extend(validate_manifest(manifest, args.data, loaded))

    for path, record in loaded:
        for text in iter_strings(record):
            for pattern_name, line_number in scan_phi(text):
                errors.append(
                    f"phi: {path.name} (line {line_number}): pattern {pattern_name!r} matched"
                )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"INVALID: {args.data} ({len(errors)} error(s))", file=sys.stderr)
        return EXIT_INVALID

    print(
        f"OK: {args.data} ({len(loaded)} notes, criteria {criteria['criteria_version']}, "
        f"phi hits: 0)"
    )
    return EXIT_VALID


if __name__ == "__main__":
    sys.exit(main())
