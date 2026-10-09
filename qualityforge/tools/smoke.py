"""Smoke-test harness for the six factory agents (spec section 7, task todo_eY0KFAHI).

Each agent has one canned input/output pair under
``qualityforge/agents/<agent>/smoke/`` matching its section 7 input/output
contract. A checker per agent verifies the output against the contract and,
where the contract is mechanically checkable, against the real guard code:
the R2 test-change guard, the R6 in-process rule, the R2 manifest re-hash,
and the section 11.1 PHI scan all execute for real on the canned data.

Usage::

    python -m qualityforge.tools.smoke            # check every agent
    python -m qualityforge.tools.smoke testing    # check one agent

Exit codes match the validator: 0 valid, 1 findings, 2 harness error.
The canned inputs/outputs are smoke evidence, not a substitute for a
platform run: transcripts from a live run are recorded per run.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from qualityforge.agents.rules import (
    in_process_test_violations,
    is_criterion_id,
    phi_scan,
    test_change_justified,
)
from qualityforge.tools.validate import (
    EXIT_ERROR,
    EXIT_INVALID,
    EXIT_VALID,
    load_config,
    recheck_manifest_hashes,
)

CHECK_TYPES = {"unit_test", "schema_check", "behavior_check"}
SOURCES = {"requirement", "assumption"}
QUALITY_CHECKS = {"lint", "type_check", "complexity", "dependencies", "security_scan"}

CRITERIA_V1 = (
    Path(__file__).resolve().parents[1] / "workloads" / "soap-evaluator" / "criteria-v1.yaml"
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _requirements(repo_root: Path) -> list[str]:
    """§7.1: criteria with ID, statement, check type; input is the §8.1 requirement."""
    smoke = repo_root / "qualityforge/agents/requirements/smoke"
    input_text = (smoke / "input.md").read_text(encoding="utf-8")
    blockquote = next(line[2:].strip() for line in input_text.splitlines() if line.startswith("> "))
    of_record = next(
        line[2:].strip()
        for line in (repo_root / "qualityforge/requirements/run-1-soap.md")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.startswith("> ")
    )
    if blockquote != of_record:
        return ["smoke input requirement does not match the of-record run-1-soap.md"]

    output = _load_json(smoke / "output.json")
    findings: list[str] = []
    if not output.get("workload"):
        findings.append("output: missing workload")
    criteria = output.get("criteria") or []
    if not criteria:
        findings.append("output: criteria list is empty")
    ids = [criterion.get("id", "") for criterion in criteria]
    if len(ids) != len(set(ids)):
        findings.append("output: duplicate criterion IDs")
    for index, criterion in enumerate(criteria):
        where = f"criterion[{index}]"
        if not is_criterion_id(str(criterion.get("id", ""))):
            findings.append(f"{where}: id does not match ^[A-Z]+-[0-9]{{2,}}$")
        if not str(criterion.get("statement", "")).strip():
            findings.append(f"{where}: empty statement")
        if criterion.get("check_type") not in CHECK_TYPES:
            findings.append(f"{where}: check_type not in {sorted(CHECK_TYPES)}")
        if criterion.get("source") not in SOURCES:
            findings.append(f"{where}: source not in {sorted(SOURCES)}")
        if not str(criterion.get("spec_ref", "")).strip():
            findings.append(f"{where}: missing spec_ref")
        if criterion.get("source") == "assumption" and not str(criterion.get("note", "")).strip():
            findings.append(f"{where}: assumption without note (section 7.1)")
    return findings


def _architecture(repo_root: Path) -> list[str]:
    """§7.2: coverage of every criterion; pinned dependencies; R6 in-process tests."""
    smoke = repo_root / "qualityforge/agents/architecture/smoke"
    input_ref = _load_json(smoke / "input.json")
    criteria_doc = _load_json((smoke / input_ref["acceptance_criteria"]).resolve())
    spec = (smoke / "output.md").read_text(encoding="utf-8")

    findings: list[str] = []
    missing = [
        criterion["id"]
        for criterion in criteria_doc.get("criteria", [])
        if criterion["id"] not in spec
    ]
    if missing:
        findings.append(f"coverage map missing criteria: {', '.join(sorted(missing))}")

    dependencies = spec.split("## Dependencies", 1)[-1].split("##", 1)[0]
    pinned = [
        line.strip("- ").strip()
        for line in dependencies.splitlines()
        if line.strip().startswith("- ")
    ]
    unpinned = [line for line in pinned if "==" not in line]
    if unpinned:
        findings.append(f"unpinned dependencies: {', '.join(unpinned)}")
    if not pinned:
        findings.append("dependencies section lists nothing")

    if "TestClient" not in spec:
        findings.append("spec does not state the in-process TestClient rule (R6)")
    return findings


def _coding(repo_root: Path) -> list[str]:
    """§7.4: per-task diffs, task parity with the execution plan, PHI-clean."""
    smoke = repo_root / "qualityforge/agents/coding/smoke"
    plan = _load_json(smoke / "input.json")
    output = _load_json(smoke / "output.json")

    findings: list[str] = []
    plan_ids = [task["id"] for task in plan["tasks"]]
    out_ids = [task.get("task_id") for task in output.get("tasks", [])]
    if plan_ids != out_ids:
        findings.append(f"task parity broken: plan {plan_ids} vs output {out_ids}")
    for task in output.get("tasks", []):
        if not str(task.get("diff", "")).strip():
            findings.append(f"{task.get('task_id')}: empty diff")
        hits = phi_scan(str(task.get("diff", "")))
        if hits:
            findings.append(f"{task.get('task_id')}: PHI scan hits: {'; '.join(hits)}")
    return findings


def _testing(repo_root: Path) -> list[str]:
    """§7.6: criteria-derived suite sample, in-process (R6), PHI-clean, full coverage."""
    smoke = repo_root / "qualityforge/agents/testing/smoke"
    input_ref = _load_json(smoke / "input.json")
    fixture = smoke / "fixtures" / "generated-test-sample.txt"
    fixture_text = fixture.read_text(encoding="utf-8")

    findings: list[str] = []
    config = load_config(repo_root / input_ref["criteria_config"])
    criteria_ids = {criterion["id"] for criterion in config["criteria"]}
    uncovered = sorted(cid for cid in criteria_ids if cid not in fixture_text)
    if uncovered:
        findings.append(f"fixture does not reference criteria: {', '.join(uncovered)}")

    violations = in_process_test_violations(fixture_text)
    if violations:
        findings.append(f"in-process violations: {'; '.join(violations)}")
    if "TestClient" not in fixture_text:
        findings.append("fixture has no in-process client (R6)")
    hits = phi_scan(fixture_text)
    if hits:
        findings.append(f"PHI scan hits: {'; '.join(hits)}")

    output = _load_json(smoke / "output.json")
    if output.get("tests_run") != output.get("passed", 0) + output.get("failed", 0):
        findings.append("result arithmetic broken: tests_run != passed + failed")
    for failure in output.get("failures", []):
        if not failure.get("criterion_id"):
            findings.append("failure without criterion_id linkage")
    return findings


def _debugging(repo_root: Path) -> list[str]:
    """§7.7: attempts logged; the R2 guard admits/rejects test edits exactly."""
    smoke = repo_root / "qualityforge/agents/debugging/smoke"
    input_ref = _load_json(smoke / "input.json")
    output = _load_json(smoke / "output.json")
    criteria_path = input_ref.get("criteria_config", str(CRITERIA_V1))
    config = load_config(repo_root / criteria_path)
    valid_ids = {criterion["id"] for criterion in config["criteria"]}

    findings: list[str] = []
    attempts = output.get("attempts") or []
    if not attempts:
        findings.append("no attempts logged (section 7.7 requires every attempt)")
    attempt_ids = [attempt.get("attempt_id") for attempt in attempts]
    if len(attempt_ids) != len(set(attempt_ids)):
        findings.append("duplicate attempt IDs")
    for attempt in attempts:
        where = str(attempt.get("attempt_id"))
        if not str(attempt.get("diagnosis", "")).strip():
            findings.append(f"{where}: missing diagnosis")
        retest = attempt.get("retest") or {}
        if retest.get("passed") is None:
            findings.append(f"{where}: missing retest record")
        if attempt.get("kind") == "test":
            guard = test_change_justified(
                diff=str(attempt.get("diff", attempt.get("change", ""))),
                justification=attempt.get("justification"),
                valid_criterion_ids=valid_ids,
            )
            if guard != attempt.get("accepted"):
                findings.append(
                    f"{where}: guard/record mismatch on test edit "
                    f"(guard={guard}, accepted={attempt.get('accepted')})"
                )
        if attempt.get("kind") == "implementation" and attempt.get("accepted") is True:
            if not retest.get("passed"):
                findings.append(f"{where}: accepted implementation repair without green retest")
    return findings


def _quality(repo_root: Path) -> list[str]:
    """§7.8: five checks, real manifest re-hash (R2), coverage, disclaimer."""
    smoke = repo_root / "qualityforge/agents/quality/smoke"
    input_ref = _load_json(smoke / "input.json")
    output = _load_json(smoke / "output.json")

    findings: list[str] = []
    reported = {check["check"]: check["status"] for check in output.get("quality_checks", [])}
    if set(reported) != QUALITY_CHECKS:
        findings.append(f"quality checks {sorted(reported)} != {sorted(QUALITY_CHECKS)}")
    if any(status != "pass" for status in reported.values()) and output.get("overall") == "pass":
        findings.append("overall pass despite failing quality check")

    manifest = input_ref["manifest"]
    drift = recheck_manifest_hashes(manifest, repo_root)
    if drift:
        findings.append(f"manifest drift (R2 gate fails): {'; '.join(drift)}")
    rehash = output.get("manifest_rehash") or {}
    if rehash.get("status") != "pass" and not drift:
        findings.append("re-hash ran clean but report does not claim pass")

    config = load_config(repo_root / input_ref["criteria_config"])
    criteria_ids = {criterion["id"] for criterion in config["criteria"]}
    covered = {ref for entry in manifest["test_files"] for ref in entry.get("criteria_refs", [])}
    if not criteria_ids <= covered:
        findings.append(
            f"manifest does not cover criteria: {', '.join(sorted(criteria_ids - covered))}"
        )

    results = input_ref["final_test_results"]
    confirmed = output.get("test_results_confirmed") or {}
    if (results["tests_run"], results["passed"], results["failed"]) != (
        confirmed.get("tests_run"),
        confirmed.get("passed"),
        confirmed.get("failed"),
    ):
        findings.append("final test results not faithfully confirmed")

    disclaimer = str(output.get("disclaimer", "")).lower()
    if "clinical validity" not in disclaimer or "not" not in disclaimer:
        findings.append("disclaimer must deny clinical validity (spec section 8.5)")
    return findings


CHECKERS: dict[str, Callable[[Path], list[str]]] = {
    "requirements": _requirements,
    "architecture": _architecture,
    "coding": _coding,
    "testing": _testing,
    "debugging": _debugging,
    "quality": _quality,
}


def check_agent(agent: str, repo_root: Path) -> list[str]:
    """Run one agent's smoke checks; empty list means the contract holds."""
    return CHECKERS[agent](repo_root)


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    selected = argv if argv else list(CHECKERS)
    unknown = [agent for agent in selected if agent not in CHECKERS]
    if unknown:
        print(f"unknown agent(s): {', '.join(unknown)}; known: {', '.join(CHECKERS)}")
        return EXIT_ERROR
    results = {agent: check_agent(agent, repo_root) for agent in selected}
    print(json.dumps(results, indent=2))
    if any(results.values()):
        return EXIT_INVALID
    return EXIT_VALID


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
