#!/usr/bin/env python3
"""Stage-7 V1 criteria walk — Run 2 (qf-run-1-soap-20261009T205906Z).

Independent per-criterion verification (spec §7.8, §5.2): for every criterion
in the stage-1 acceptance-criteria config, evaluate every labeled corpus note
through the harness loader seam and check the implementation's behavior
against the corpus label — never against the implementation's own claims.

Checks, per criterion and per note:
  C1 behavior      actual status == labeled status (corpus label is ground truth)
  C2 R3 spans      every evidence span is a raw slice: note_text[start:end] == text,
                   zero-based, end-exclusive, non-empty for present/partial
  C3 evidence rule present/partial carry >= 1 span; missing carries none
  C4 dispatch order findings appear exactly one per configured criterion, in
                   config order (R4) — on every response
  C5 version echo  criteria_version echoes the config's value

Round-level checks:
  C6 determinism   byte-for-byte: repeated evaluations and a freshly built
                   evaluator produce identical canonical JSON per note
  C7 config-driven no hardcoding: an in-memory reordered config moves the
                   findings order; a config with a criterion removed drops
                   that finding; altered header markers change section
                   detection — behavior follows the config file (R5)
  C8 seam          the loader resolves the generated evaluator
                   (qualityforge.generated.soap_evaluator:create_evaluator)
                   over the of-record config, and the loader default resolves
  C9 config identity the stage-1 acceptance-criteria.yaml is semantically
                   identical to the of-record criteria-v1.yaml

Output: one JSON document on stdout (per-criterion verdicts + evidence).
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

# Repo root: parents[4] when the script sits at
# qualityforge/runs/<run>/verify/verify_criteria.py (committed form);
# QF_REPO_ROOT overrides for scratch runs outside the repo.
REPO_ROOT = Path(os.environ.get("QF_REPO_ROOT", Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(REPO_ROOT))

import qualityforge.generated.soap_evaluator as gen  # noqa: E402
from qualityforge.harness import loader  # noqa: E402
from qualityforge.harness.inject import (  # noqa: E402
    build_evaluator_spec,
    evaluator_from_spec,
    load_config,
)

RUN_ID = "qf-run-1-soap-20261009T205906Z"
STAGE1_CONFIG = (
    REPO_ROOT
    / "qualityforge/runs/qf-run-1-soap-20261009T205906Z/requirements/acceptance-criteria.yaml"
)
OF_RECORD_CONFIG = REPO_ROOT / "qualityforge/workloads/soap-evaluator/criteria-v1.yaml"
NOTES_DIR = REPO_ROOT / "qualityforge/workloads/soap-evaluator/data/notes"
GENERATED_MODULE = "qualityforge.generated.soap_evaluator"
GENERATED_FACTORY = "create_evaluator"

PRESENT_STATUSES = {"present", "partial"}


def load_corpus() -> list[dict]:
    records = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(NOTES_DIR.glob("soap-*.json"))
    ]
    return sorted(records, key=lambda r: r["note_id"])


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def span_errors(note_text: str, finding: dict) -> list[str]:
    errors: list[str] = []
    for span in finding["evidence"]:
        start, end, text = span["start"], span["end"], span["text"]
        if not (0 <= start <= end <= len(note_text)):
            errors.append(f"{finding['criterion_id']}: span bounds {start}..{end} out of range")
        elif note_text[start:end] != text:
            errors.append(
                f"{finding['criterion_id']}: span text not the raw slice "
                f"(note_text[{start}:{end}]={note_text[start:end]!r} != {text!r})"
            )
    return errors


def main() -> int:
    corpus = load_corpus()
    stage1 = load_config(STAGE1_CONFIG)
    of_record = load_config(OF_RECORD_CONFIG)

    # C8 — the harness seam resolves the generated evaluator over the of-record
    # config, exactly as the suite's default spec names it.
    baseline_spec = build_evaluator_spec(GENERATED_MODULE, GENERATED_FACTORY, OF_RECORD_CONFIG, ())
    evaluator = evaluator_from_spec(baseline_spec)
    loader_default = evaluator_from_spec(loader.default_spec())

    # C9 — semantic identity of the stage-1 config vs the of-record config.
    config_identity = {
        "stage1_path": str(STAGE1_CONFIG.relative_to(REPO_ROOT)),
        "of_record_path": str(OF_RECORD_CONFIG.relative_to(REPO_ROOT)),
        "semantically_identical": canonical(stage1) == canonical(of_record),
        "criteria_version": stage1["criteria_version"],
        "name": stage1["name"],
    }

    criteria = stage1["criteria"]
    # Per-criterion accumulators over the FULL corpus (24 notes x 8 criteria).
    results: dict[str, dict[str, Any]] = {
        c["id"]: {
            "id": c["id"],
            "statement": c["statement"],
            "section": c["section"],
            "check_type": c["check_type"],
            "notes_evaluated": 0,
            "behavior_matches": 0,
            "labeled_cases": {},  # status -> [note_ids]
            "mismatches": [],
            "span_errors": [],
            "evidence_rule_errors": [],
            "order_errors": [],
            "version_echo_errors": [],
            "verdict": "UNRUN",
        }
        for c in criteria
    }
    config_ids = [c["id"] for c in criteria]
    determinism_failures: list[str] = []
    order_failures: list[str] = []

    for record in corpus:
        note_id, note_text = record["note_id"], record["note_text"]
        request: dict[str, Any] = {"note_id": note_id, "note_text": note_text}
        if record.get("visit_type"):
            request["visit_type"] = record["visit_type"]
        labeled = {f["criterion_id"]: f["status"] for f in record["expected"]["findings"]}

        # C6 — determinism: same instance, and a freshly built evaluator.
        first = evaluator(copy.deepcopy(request))
        second = evaluator(copy.deepcopy(request))
        fresh = evaluator_from_spec(baseline_spec)(copy.deepcopy(request))
        if not (canonical(first) == canonical(second) == canonical(fresh)):
            determinism_failures.append(note_id)

        # C4 — dispatch order on every response.
        actual_ids = [f["criterion_id"] for f in first["findings"]]
        if actual_ids != config_ids:
            order_failures.append(f"{note_id}: findings order {actual_ids}")

        for finding in first["findings"]:
            cid = finding["criterion_id"]
            row = results[cid]
            row["notes_evaluated"] += 1
            actual, expected = finding["status"], labeled[cid]
            row["labeled_cases"].setdefault(expected, []).append(note_id)
            # C1 — behavior against the corpus label.
            if actual == expected:
                row["behavior_matches"] += 1
            else:
                row["mismatches"].append(f"{note_id}: labeled {expected}, got {actual}")
            # C2 — R3 raw-slice spans.
            row["span_errors"].extend(span_errors(note_text, finding))
            # C3 — evidence rule.
            if actual in PRESENT_STATUSES and not finding["evidence"]:
                row["evidence_rule_errors"].append(
                    f"{note_id}: {actual} finding carries no evidence"
                )
            if actual == "missing" and finding["evidence"]:
                row["evidence_rule_errors"].append(f"{note_id}: missing finding carries evidence")
            # C5 — version echo (per finding's enclosing response, checked once below).

        # C5 — criteria_version echo on every response.
        if first["criteria_version"] != stage1["criteria_version"]:
            results["X-01"]["version_echo_errors"].append(note_id)

    # C7 — config-drivenness probes: behavior must follow the config, not
    # hardcoded rule lists. Probes run against the seam factory with in-memory
    # config variations (no file is edited).
    probes: list[dict[str, Any]] = []

    reordered = copy.deepcopy(of_record)
    reordered["criteria"] = list(reversed(reordered["criteria"]))
    # Build an evaluator from the reordered config directly through the factory.
    from_reordered = gen.create_evaluator(reordered)
    probe_request = {
        "note_id": "probe-reorder",
        "note_text": "S: fever\nO: afebrile\nA: fever\nP: rest",
    }
    base_order = [f["criterion_id"] for f in evaluator(copy.deepcopy(probe_request))["findings"]]
    new_order = [
        f["criterion_id"] for f in from_reordered(copy.deepcopy(probe_request))["findings"]
    ]
    probes.append(
        {
            "probe": "criteria reordered in memory",
            "expected": "findings order follows the new config order",
            "base_order": base_order,
            "reordered_config_order": new_order,
            "follows_config": new_order == list(reversed(base_order)),
        }
    )

    dropped = copy.deepcopy(of_record)
    dropped["criteria"] = [c for c in dropped["criteria"] if c["id"] != "O-01"]
    from_dropped = gen.create_evaluator(dropped)
    out = from_dropped(copy.deepcopy(probe_request))
    ids = [f["criterion_id"] for f in out["findings"]]
    probes.append(
        {
            "probe": "criterion O-01 removed from an in-memory config copy",
            "expected": "no O-01 finding; remaining order preserved",
            "finding_ids": ids,
            "follows_config": "O-01" not in ids and ids == [c["id"] for c in dropped["criteria"]],
        }
    )

    altered = copy.deepcopy(of_record)
    altered["section_detection"]["header_markers"]["S"] = ["ZZ-SUBJECTIVE-ZZ:"]
    from_altered = gen.create_evaluator(altered)
    # S content that matches no S fallback category (no complaint phrasing, no
    # symptom terms): under the of-record config the "S:" marker identifies the
    # section (X-01 present); under the altered config no marker names it and
    # the fallback cannot confidently claim it — X-01 answers partial (R5:
    # ambiguity is reported, never guessed). Markers provably drive detection.
    marker_note = (
        "S: friendly dragon visited today\nO: pulse 72 regular\nA: likely flu\nP: rest and fluids"
    )
    out_base = evaluator(copy.deepcopy({"note_id": "probe-markers", "note_text": marker_note}))
    out_altered = from_altered(
        copy.deepcopy({"note_id": "probe-markers", "note_text": marker_note})
    )
    x01_base = next(f for f in out_base["findings"] if f["criterion_id"] == "X-01")
    x01_altered = next(f for f in out_altered["findings"] if f["criterion_id"] == "X-01")
    probes.append(
        {
            "probe": "S header markers altered in an in-memory config copy",
            "expected": (
                "section detection follows the config markers: X-01 present under the "
                "of-record markers, partial under altered markers (S content matches no "
                "fallback category, so only the marker can identify it)"
            ),
            "x01_base": x01_base["status"],
            "x01_altered": x01_altered["status"],
            "follows_config": (
                x01_base["status"] == "present" and x01_altered["status"] == "partial"
            ),
        }
    )

    # Verdicts.
    for row in results.values():
        ok = (
            not row["mismatches"]
            and not row["span_errors"]
            and not row["evidence_rule_errors"]
            and not row["order_errors"]
            and not row["version_echo_errors"]
            and row["behavior_matches"] == row["notes_evaluated"] == len(corpus)
        )
        row["verdict"] = "PASS" if ok else "FAIL"

    round_ok = (
        not determinism_failures
        and not order_failures
        and all(p["follows_config"] for p in probes)
        and config_identity["semantically_identical"]
        and all(r["verdict"] == "PASS" for r in results.values())
    )

    report = {
        "artifact_type": "verification_walk",
        "run_id": RUN_ID,
        "stage": "7. Verify (§7.8 Quality Agent, V1 criteria walk)",
        "corpus_notes": len(corpus),
        "evaluations": len(corpus) * len(criteria),
        "seam": {
            "module": GENERATED_MODULE,
            "factory": GENERATED_FACTORY,
            "of_record_config": str(OF_RECORD_CONFIG.relative_to(REPO_ROOT)),
            "resolved": True,
            "loader_default_resolves": loader_default is not None,
        },
        "config_identity": config_identity,
        "determinism": {
            "byte_identical_repeat_and_fresh": not determinism_failures,
            "failing_notes": determinism_failures,
        },
        "dispatch_order": {
            "config_order_on_every_response": not order_failures,
            "failures": order_failures,
        },
        "config_drivenness_probes": probes,
        "criteria": list(results.values()),
        "round_verdict": "PASS" if round_ok else "FAIL",
    }
    print(json.dumps(report, indent=2))
    return 0 if round_ok else 1


if __name__ == "__main__":
    sys.exit(main())
