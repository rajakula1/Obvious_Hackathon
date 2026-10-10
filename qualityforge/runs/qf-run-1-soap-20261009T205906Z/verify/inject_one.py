#!/usr/bin/env python3
"""Stage-7 I1 injection round — Run 2 (qf-run-1-soap-20261009T205906Z).

One defect injected through the §12.3/R1 harness seam (qualityforge/harness/
inject.py, run_injection_round), exactly the Run 1 pattern — never by editing
the implementation or the suite. The mutant is a serialized evaluator spec
carried to the suite subprocess via QUALITYFORGE_EVALUATOR_SPEC (loader.py):
module qualityforge.generated.soap_evaluator, factory create_evaluator, the
of-record config, ONE operator.

Injected defect: flip_finding_statuses — every finding's status is flipped
between present and missing and overall_status is recomputed, so the response
stays internally consistent. Only assertions derived from the corpus labels
can detect it — the self-confirmation trap §12.3 exists to expose.

Sequence enforced by the harness (SuiteBaselineError otherwise):
  1. baseline: the pristine evaluator passes the unchanged suite in a fresh
     subprocess — detection is unmeasurable otherwise;
  2. mutant run: suite must FAIL (detection);
  3. vacuity probe: every mutant output must differ from the validated
     implementation on the 24 probe requests (HarnessConsistencyError on a
     contradiction — a flaky suite or harness bug);
  4. consistency: no "identical outputs yet suite failures".

Output: the DetectionReport JSON (§8.5 shape, the Run 1 report.json form) on
stdout; exit 0 iff baseline passed, the mutant was detected (or honestly
reported undetected — a FINDING either way), and no harness error fired.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(os.environ.get("QF_REPO_ROOT", Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(REPO_ROOT))

from qualityforge.harness.inject import (  # noqa: E402
    PytestSuiteRunner,
    flip_finding_statuses,
    run_injection_round,
)

RUN_ID = "qf-run-1-soap-20261009T205906Z"
OF_RECORD_CONFIG = REPO_ROOT / "qualityforge/workloads/soap-evaluator/criteria-v1.yaml"
NOTES_DIR = REPO_ROOT / "qualityforge/workloads/soap-evaluator/data/notes"
GENERATED_SUITE = REPO_ROOT / "qualityforge/generated/tests"


def probes() -> list[dict]:
    """The 24 workload notes as §8.3 evaluate requests (vacuity probe set)."""
    out = []
    for path in sorted(NOTES_DIR.glob("soap-*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        request: dict = {"note_id": record["note_id"], "note_text": record["note_text"]}
        if record.get("visit_type"):
            request["visit_type"] = record["visit_type"]
        out.append(request)
    return out


def main() -> int:
    operator = flip_finding_statuses()
    runner = PytestSuiteRunner(
        suite_paths=(GENERATED_SUITE,), repo_root=REPO_ROOT, timeout_seconds=120
    )
    print(
        f"injection round: operator={operator.op_id} suite={GENERATED_SUITE} "
        f"config={OF_RECORD_CONFIG} probes={len(probes())}",
        file=sys.stderr,
    )
    report = run_injection_round(
        run_id=RUN_ID,
        module="qualityforge.generated.soap_evaluator",
        factory="create_evaluator",
        config_path=OF_RECORD_CONFIG,
        suite_runner=runner,
        operators=[operator],
        probes=probes(),
    )
    print(json.dumps(report.to_dict(), indent=2))
    detected = report.mutants_detected
    valid = len(report.valid_mutants)
    ok = report.baseline.all_passed and detected > 0
    print(
        f"summary: baseline {report.baseline.passed} passed / {report.baseline.failed} failed; "
        f"detection {detected}/{valid}; r1_threshold_met={report.r1_threshold_met}",
        file=sys.stderr,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
