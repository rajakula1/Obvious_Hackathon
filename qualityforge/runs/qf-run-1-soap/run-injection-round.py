"""Defect-injection round driver — Factory Run 1 (§12.3, review R1).

Executes the generated test suite unchanged against the pristine evaluator
(baseline gate) and against the four §12.3/R1 mutants, then prints the
DetectionReport as JSON. The harness (qualityforge.harness.inject) owns every
detection judgment; this driver only assembles the round inputs and
serializes the report.

Usage:  python3 qualityforge/runs/qf-run-1-soap/run-injection-round.py > report.json
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from qualityforge.harness.inject import (  # noqa: E402
    PytestSuiteRunner,
    drop_evidence_spans,
    flip_finding_statuses,
    load_config,
    remove_section_check,
    run_injection_round,
    skip_criterion_check,
)

CONFIG_PATH = REPO_ROOT / "qualityforge/workloads/soap-evaluator/criteria-v1.yaml"
NOTES_DIR = REPO_ROOT / "qualityforge/workloads/soap-evaluator/data/notes"


def main() -> None:
    config = load_config(CONFIG_PATH)
    records = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(NOTES_DIR.glob("soap-*.json"))
    ]
    probes = [
        {"note_id": r["note_id"], "note_text": r["note_text"]}
        for r in sorted(records, key=lambda r: r["note_id"])
    ]

    report = run_injection_round(
        run_id="qf-run-1-soap-20261009T172617Z",
        module="qualityforge.generated.soap_evaluator",
        factory="create_evaluator",
        config_path=CONFIG_PATH,
        suite_runner=PytestSuiteRunner(
            suite_paths=(REPO_ROOT / "qualityforge/generated/tests",),
            repo_root=REPO_ROOT,
        ),
        operators=[
            remove_section_check(config, section="O"),
            drop_evidence_spans(),
            flip_finding_statuses(),
            skip_criterion_check(config, criterion_id="P-02"),
        ],
        probes=probes,
    )
    print(json.dumps(dataclasses.asdict(report), indent=2))


if __name__ == "__main__":
    main()
