"""Defect-injection harness: prove the generated suite is not self-confirming.

Spec section 12.3, promoted to demo acceptance evidence by review R1: inject
known defects into a validated implementation and confirm the generated tests
catch them, reporting the share of injected defects detected. This module
provides the four operators of the R1 amendment — remove a section check,
drop an evidence span, flip a finding status, skip the plan-relation check —
each mapped to the criteria it targets, plus a runner that executes a test
suite against every mutant and assembles a report in the section 8.5
conventions (criteria tested; tests passed and failed; repair attempts;
remaining known limitations; the software-correctness disclaimer).

How defects are injected. The operators wrap the evaluator callable at the
seam the API contract fixes (spec section 8.3 request/response): a mutant is
an evaluator that answers every request exactly like the validated
implementation except for one injected defect. For any suite that consumes
only the contract, a seam-level mutant is observationally equivalent to a
source-level implementation with the same behavior — the suite cannot tell
the difference, which is precisely the property the check relies on. The
round never edits the implementation or the suite (spec section 11.4,
review R2); mutants exist only in memory and, for suite execution, as a
serialized evaluator spec (see loader.py).

Honesty rules the runner enforces:

- The suite must pass against the validated implementation before any mutant
  runs; a suite that fails at baseline cannot measure detection
  (SuiteBaselineError).
- A mutant whose outputs match the validated implementation on every probe
  request is vacuous: it is reported and excluded from the share denominator,
  because a suite cannot detect what does not change.
- A vacuous mutant whose suite run reports failures is a contradiction (a
  flaky suite or a harness bug) and fails loudly (HarnessConsistencyError).
- A detection share below the R1 threshold (80%) is a reportable result, not
  a harness failure — the honesty is the product (review R1).
"""

from __future__ import annotations

import copy
import importlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, NotRequired, Protocol, TypedDict

import yaml

R1_DETECTION_THRESHOLD = 0.8
DISCLAIMER = "Results reflect software correctness against stated criteria, not clinical validity."
EVALUATOR_SPEC_ENV_VAR = "QUALITYFORGE_EVALUATOR_SPEC"
PLAN_RELATION_CRITERION_ID = "P-02"

PRESENT_STATUSES = frozenset({"present", "partial"})
SECTION_ORDER = ("S", "O", "A", "P")
SOAP_SECTION_NAMES: Mapping[str, str] = {
    "S": "Subjective",
    "O": "Objective",
    "A": "Assessment",
    "P": "Plan",
}


class EvaluateRequest(TypedDict):
    """Request body of POST /evaluate (spec section 8.3)."""

    note_id: str
    note_text: str
    visit_type: NotRequired[str]


class EvidenceSpan(TypedDict):
    """Zero-based, end-exclusive character offsets into the raw note_text (R3)."""

    start: int
    end: int
    text: str


class Finding(TypedDict):
    criterion_id: str
    section: str | None
    status: str
    evidence: list[EvidenceSpan]
    message: str


class EvaluateResponse(TypedDict):
    """Response body of POST /evaluate (spec section 8.3)."""

    note_id: str
    criteria_version: str
    overall_status: str
    findings: list[Finding]


Evaluator = Callable[[EvaluateRequest], EvaluateResponse]
MutantApply = Callable[[Evaluator], Evaluator]


def overall_status_from(findings: Sequence[Finding | dict[str, Any]]) -> str:
    """Overall status per the reading the reference evaluator pins.

    Complete only when every finding is `present`: a `partial` finding means
    the note is not fully complete against the stated criteria.
    """
    all_present = all(finding["status"] == "present" for finding in findings)
    return "complete" if all_present else "incomplete"


# --- mutation operators (spec section 12.3, review R1) -----------------------


@dataclass(frozen=True)
class MutationOperator:
    """One known defect, applicable to any evaluator of the section 8.3 shape.

    `op_name` and `args` record the registry constructor that rebuilds the
    mutant from a serialized spec (loader.py); `criterion_refs` lists the
    criteria the defect targets (empty for contract-level defects such as
    dropping evidence spans, whose target is the section 8.3 evidence
    requirement rather than a single criterion).
    """

    op_id: str
    op_name: str
    args: Mapping[str, Any]
    title: str
    description: str
    targets: str
    apply: MutantApply = field(repr=False, compare=False)
    criterion_refs: tuple[str, ...] = ()


def _drop_findings(evaluator: Evaluator, doomed: frozenset[str]) -> Evaluator:
    def mutant(request: EvaluateRequest) -> EvaluateResponse:
        response = copy.deepcopy(evaluator(request))
        response["findings"] = [
            finding for finding in response["findings"] if finding["criterion_id"] not in doomed
        ]
        return response

    return mutant


def remove_section_check(config: Mapping[str, Any], *, section: str) -> MutationOperator:
    """The section check was never implemented: its findings are never reported."""
    ids = tuple(sorted(c["id"] for c in config["criteria"] if c["section"] == section))
    if not ids:
        raise ValueError(
            f"cannot remove the {section!r} section check: "
            "the criteria config defines no criteria for it"
        )
    name = SOAP_SECTION_NAMES.get(section, section)

    def apply(evaluator: Evaluator) -> Evaluator:
        return _drop_findings(evaluator, frozenset(ids))

    return MutationOperator(
        op_id=f"remove-section-check-{section.lower()}",
        op_name="remove_section_check",
        args={"section": section},
        title=f"Remove the {name} section check",
        description=(
            f"The evaluator never reports findings for the {name} ({section}) criteria "
            f"({', '.join(ids)}), as if that section check had not been implemented."
        ),
        targets=f"findings for every {name} ({section}) criterion",
        apply=apply,
        criterion_refs=ids,
    )


def drop_evidence_spans() -> MutationOperator:
    """Present and partial findings lose their evidence (spec section 8.3)."""

    def apply(evaluator: Evaluator) -> Evaluator:
        def mutant(request: EvaluateRequest) -> EvaluateResponse:
            response = copy.deepcopy(evaluator(request))
            for finding in response["findings"]:
                if finding["status"] in PRESENT_STATUSES:
                    finding["evidence"] = []
            return response

        return mutant

    return MutationOperator(
        op_id="drop-evidence-spans",
        op_name="drop_evidence_spans",
        args={},
        title="Drop evidence spans from present findings",
        description=(
            "Every present or partial finding loses its evidence spans, violating the "
            "section 8.3 requirement that present and partial findings carry supporting evidence."
        ),
        targets="evidence field of every present or partial finding (spec section 8.3)",
        apply=apply,
    )


_FLIPPED_STATUSES = {"present": "missing", "missing": "present"}


def flip_finding_statuses() -> MutationOperator:
    """Every finding status is flipped; overall_status is recomputed.

    The response stays internally consistent, so only assertions derived from
    the labeled expectations can detect it — the self-confirmation trap that
    spec section 12.3 exists to expose.
    """

    def apply(evaluator: Evaluator) -> Evaluator:
        def mutant(request: EvaluateRequest) -> EvaluateResponse:
            response = copy.deepcopy(evaluator(request))
            for finding in response["findings"]:
                finding["status"] = _FLIPPED_STATUSES.get(finding["status"], finding["status"])
            response["overall_status"] = overall_status_from(response["findings"])
            return response

        return mutant

    return MutationOperator(
        op_id="flip-finding-statuses",
        op_name="flip_finding_statuses",
        args={},
        title="Flip finding statuses",
        description=(
            "Every finding has its status flipped between present and missing (partial is "
            "untouched) and overall_status is recomputed from the flipped findings."
        ),
        targets="status field of every finding, with overall_status recomputed",
        apply=apply,
    )


def skip_criterion_check(config: Mapping[str, Any], *, criterion_id: str) -> MutationOperator:
    """One criterion is never checked: its finding is absent from every response."""
    if not any(c["id"] == criterion_id for c in config["criteria"]):
        raise ValueError(f"cannot skip {criterion_id!r}: not defined in the criteria config")

    def apply(evaluator: Evaluator) -> Evaluator:
        return _drop_findings(evaluator, frozenset({criterion_id}))

    return MutationOperator(
        op_id=f"skip-criterion-check-{criterion_id.lower()}",
        op_name="skip_criterion_check",
        args={"criterion_id": criterion_id},
        title=f"Skip the {criterion_id} check",
        description=(
            f"Criterion {criterion_id} is never checked: "
            "its finding is missing from every response."
        ),
        targets=f"the {criterion_id} finding",
        apply=apply,
        criterion_refs=(criterion_id,),
    )


def skip_plan_relation_check(config: Mapping[str, Any]) -> MutationOperator:
    """The plan-relation check (spec section 8.2, criterion P-02) is skipped."""
    criterion = next((c for c in config["criteria"] if c["id"] == PLAN_RELATION_CRITERION_ID), None)
    if criterion is None:
        raise ValueError(
            f"cannot skip the plan-relation check: {PLAN_RELATION_CRITERION_ID} is not defined "
            "in this criteria config"
        )
    if criterion["section"] != "P":
        raise ValueError(
            f"{PLAN_RELATION_CRITERION_ID} is not a Plan criterion in this config; the "
            "plan-relation operator does not apply"
        )
    operator = skip_criterion_check(config, criterion_id=PLAN_RELATION_CRITERION_ID)
    return replace(
        operator,
        op_id="skip-plan-relation-check",
        title=f"Skip the plan-relation check ({PLAN_RELATION_CRITERION_ID})",
        description=(
            "Plan items are never checked against stated assessments: the "
            f"{PLAN_RELATION_CRITERION_ID} finding is missing from every response "
            "(spec section 8.2)."
        ),
    )


@dataclass(frozen=True)
class _RegistryEntry:
    constructor: Callable[..., MutationOperator]
    requires_config: bool


OPERATOR_REGISTRY: Mapping[str, _RegistryEntry] = {
    "remove_section_check": _RegistryEntry(remove_section_check, True),
    "drop_evidence_spans": _RegistryEntry(drop_evidence_spans, False),
    "flip_finding_statuses": _RegistryEntry(flip_finding_statuses, False),
    "skip_criterion_check": _RegistryEntry(skip_criterion_check, True),
}


# --- evaluator specs: serializable mutants for suite subprocesses ------------


class EvaluatorSpecError(ValueError):
    """A serialized evaluator spec is malformed or names something unknown."""


def build_evaluator_spec(
    module: str,
    factory: str,
    config_path: Path | str,
    operators: Sequence[MutationOperator],
) -> dict[str, Any]:
    """Serialize how to build an evaluator: implementation + config + operators."""
    return {
        "module": module,
        "factory": factory,
        "config_path": str(config_path),
        "operators": [
            {"op": operator.op_name, "args": dict(operator.args)} for operator in operators
        ],
    }


def load_config(path: Path | str) -> Any:
    """Load a YAML or JSON criteria config (JSON is a subset of YAML 1.2)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return json.loads(text)


def _operator_from_entry(entry: Mapping[str, Any], config: Mapping[str, Any]) -> MutationOperator:
    name = entry.get("op")
    registered = OPERATOR_REGISTRY.get(name) if isinstance(name, str) else None
    if registered is None:
        raise EvaluatorSpecError(
            f"unknown operator {name!r}; known operators: {sorted(OPERATOR_REGISTRY)}"
        )
    args = entry.get("args", {})
    try:
        if registered.requires_config:
            return registered.constructor(config, **args)
        return registered.constructor(**args)
    except TypeError as exc:
        raise EvaluatorSpecError(
            f"operator {name!r} rejected its arguments {args!r}: {exc}"
        ) from exc


def evaluator_from_spec(spec: Mapping[str, Any]) -> Evaluator:
    """Build an evaluator (pristine or mutated) from a serialized spec."""
    try:
        module = importlib.import_module(str(spec["module"]))
    except ImportError as exc:
        raise EvaluatorSpecError(
            f"could not import evaluator module {spec['module']!r}: {exc}"
        ) from exc
    factory = getattr(module, str(spec["factory"]), None)
    if not callable(factory):
        raise EvaluatorSpecError(
            f"factory {spec['factory']!r} not found or not callable in module {spec['module']!r}"
        )
    config = load_config(Path(spec["config_path"]))
    evaluator = factory(config)
    for entry in spec.get("operators", []):
        operator = _operator_from_entry(entry, config)
        evaluator = operator.apply(evaluator)
    return evaluator


# --- suite execution ----------------------------------------------------------


class SuiteRunError(RuntimeError):
    """A suite subprocess could not run or its results could not be parsed."""


class SuiteBaselineError(RuntimeError):
    """The suite fails against the validated implementation — detection is unmeasurable."""


class HarnessConsistencyError(RuntimeError):
    """The round observed a contradiction (flaky suite or harness bug)."""


@dataclass(frozen=True)
class SuiteResult:
    passed: int
    failed: int
    failed_test_ids: tuple[str, ...] = ()
    summary_line: str = ""

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.passed > 0


class SuiteRunner(Protocol):
    """Executes the suite against a serialized evaluator spec (None = loader default)."""

    def run(self, mutant_spec: dict[str, Any] | None) -> SuiteResult: ...


_SUMMARY_COUNT = re.compile(r"(\d+) (passed|failed|errors?)")


def _parse_pytest_summary(stdout: str, stderr: str) -> SuiteResult:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    failed_ids = tuple(
        line.removeprefix("FAILED ").split(" - ")[0].strip()
        for line in lines
        if line.startswith("FAILED ")
    )
    summary = next(
        (line for line in reversed(lines) if _SUMMARY_COUNT.search(line) or "no tests ran" in line),
        None,
    )
    if summary is None:
        raise SuiteRunError(f"could not parse a pytest summary from:\n{(stdout + stderr)[-2000:]}")
    if "no tests ran" in summary:
        raise SuiteRunError(
            f"the suite collected no tests ({summary!r}) — "
            "a suite that collects nothing detects nothing"
        )
    passed = failed = errors = 0
    for count, kind in _SUMMARY_COUNT.findall(summary):
        number = int(count)
        if kind == "passed":
            passed = number
        elif kind == "failed":
            failed = number
        else:
            errors += number
    if errors:
        raise SuiteRunError(f"pytest reported {errors} error(s): {summary!r}")
    return SuiteResult(
        passed=passed, failed=failed, failed_test_ids=failed_ids, summary_line=summary
    )


@dataclass(frozen=True)
class PytestSuiteRunner:
    """Runs a pytest suite in a fresh subprocess per suite execution.

    The evaluator under test is selected by EVALUATOR_SPEC_ENV_VAR inside the
    subprocess (loader.py); `run(None)` pops the variable so the loader default
    (the pristine reference evaluator) is used. The generated suite itself
    stays in-process (review R6); the subprocess boundary isolates mutants,
    and each execution is cheap against the run budget (spec section 10).
    """

    suite_paths: tuple[Path, ...]
    repo_root: Path
    timeout_seconds: int = 120

    def run(self, mutant_spec: dict[str, Any] | None) -> SuiteResult:
        env = os.environ.copy()
        if mutant_spec is None:
            env.pop(EVALUATOR_SPEC_ENV_VAR, None)
        else:
            env[EVALUATOR_SPEC_ENV_VAR] = json.dumps(mutant_spec)
        command = [
            sys.executable,
            "-m",
            "pytest",
            *(str(path) for path in self.suite_paths),
            "--tb=no",
            "-q",
            "-rf",
            "-p",
            "no:cacheprovider",
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SuiteRunError(
                f"pytest exceeded {self.timeout_seconds}s: {' '.join(command)}"
            ) from exc
        if completed.returncode not in (0, 1):
            raise SuiteRunError(
                f"pytest exited {completed.returncode} (expected 0 or 1):\n"
                f"{(completed.stdout + completed.stderr)[-4000:]}"
            )
        return _parse_pytest_summary(completed.stdout, completed.stderr)


# --- the round and its report (spec section 8.5 conventions) ------------------


DEFAULT_LIMITATIONS: tuple[str, ...] = (
    "Mutants inject defects at the evaluation seam fixed by the API contract (spec section 8.3); "
    "for any suite that consumes only the contract, a seam-level mutant is observationally "
    "equivalent to a source-level implementation with the same behavior.",
    "The injection round measures detection only and records no repair attempts; detect, repair, "
    "retest evidence is produced by the Debug stage (spec sections 6 and 7.7).",
    "The detection share is measured against the probe requests supplied to the round and the "
    "suite under test; a suite may also detect a mutant on inputs outside the probe set.",
    "Vacuous mutants — identical output to the validated implementation on every probe — are "
    "reported and excluded from the share denominator; a vacuous mutant means the probe set or "
    "the operator's targeting is too narrow.",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


@dataclass(frozen=True)
class CriterionRef:
    id: str
    statement: str
    section: str | None


@dataclass(frozen=True)
class MutantResult:
    op_id: str
    title: str
    description: str
    targets: str
    criterion_refs: tuple[str, ...]
    spec: Mapping[str, Any]
    detected: bool
    vacuous: bool
    probes_different: int
    suite: SuiteResult


@dataclass(frozen=True)
class DetectionReport:
    """Detection-share report in the section 8.5 conventions."""

    run_id: str
    criteria_name: str
    criteria_version: str
    criteria_tested: tuple[CriterionRef, ...]
    contract_targets: tuple[str, ...]
    baseline: SuiteResult
    mutants: tuple[MutantResult, ...]
    limitations: tuple[str, ...] = DEFAULT_LIMITATIONS
    disclaimer: str = DISCLAIMER

    @property
    def mutants_total(self) -> int:
        return len(self.mutants)

    @property
    def valid_mutants(self) -> tuple[MutantResult, ...]:
        return tuple(mutant for mutant in self.mutants if not mutant.vacuous)

    @property
    def mutants_detected(self) -> int:
        return sum(1 for mutant in self.valid_mutants if mutant.detected)

    @property
    def detection_share(self) -> float | None:
        valid = self.valid_mutants
        if not valid:
            return None
        return self.mutants_detected / len(valid)

    @property
    def r1_threshold_met(self) -> bool | None:
        share = self.detection_share
        return None if share is None else share >= R1_DETECTION_THRESHOLD

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": "defect_injection_detection",
            "run_id": self.run_id,
            "criteria_name": self.criteria_name,
            "criteria_version": self.criteria_version,
            "criteria_tested": [asdict(ref) for ref in self.criteria_tested],
            "contract_targets": list(self.contract_targets),
            "baseline": {
                "passed": self.baseline.passed,
                "failed": self.baseline.failed,
            },
            "mutants": [asdict(mutant) for mutant in self.mutants],
            "mutants_total": self.mutants_total,
            "mutants_detected": self.mutants_detected,
            "detection_share": self.detection_share,
            "r1_threshold": R1_DETECTION_THRESHOLD,
            "r1_threshold_met": self.r1_threshold_met,
            # The harness detects and records; repair is the Debugging Agent's
            # loop (spec section 6). Populated by the orchestrator when this
            # report is wired into a full run — empty by construction here.
            "repair_attempts": [],
            "limitations": list(self.limitations),
            "disclaimer": self.disclaimer,
        }

    def render_markdown(self) -> str:
        share = self.detection_share
        share_text = "n/a (no non-vacuous mutants)" if share is None else f"{share:.0%}"
        threshold = {
            True: "met",
            False: "not met",
            None: "n/a",
        }[self.r1_threshold_met]
        lines = [
            f"# Defect-injection detection report — {self.run_id}",
            f"Criteria set: {self.criteria_name} v{self.criteria_version}",
            "",
            "## Tests passed and failed",
            (
                f"Baseline (validated implementation): {self.baseline.passed} passed, "
                f"{self.baseline.failed} failed."
            ),
            "",
            "| Mutant | Criteria | Tests passed | Tests failed | Detected |",
            "|---|---|---|---|---|",
        ]
        for mutant in self.mutants:
            refs = ", ".join(mutant.criterion_refs) if mutant.criterion_refs else "—"
            flag = " (vacuous)" if mutant.vacuous else ""
            detected = "yes" if mutant.detected else "no"
            lines.append(
                f"| {mutant.op_id}{flag} | {refs} | {mutant.suite.passed} "
                f"| {mutant.suite.failed} | {detected} |"
            )
        lines += [
            "",
            "## Injected defects",
            *[f"- **{m.op_id}** — {m.title}: {m.description}" for m in self.mutants],
            "",
            "## Detection share",
            (
                f"{self.mutants_detected} of {len(self.valid_mutants)} non-vacuous mutants "
                f"detected — detection share {share_text}."
            ),
            f"Review R1 threshold ({R1_DETECTION_THRESHOLD:.0%}): {threshold}.",
            "",
            "## Criteria tested",
            *[
                f"- **{ref.id}** (section {ref.section}): {ref.statement}"
                for ref in self.criteria_tested
            ],
        ]
        if self.contract_targets:
            lines += [
                "",
                "## Contract-level targets",
                *[f"- {target}" for target in self.contract_targets],
            ]
        lines += [
            "",
            "## Repair attempts",
            (
                "None. The injection round measures detection only; the detect, repair, retest "
                "loop is the Debug stage's evidence (spec sections 6 and 7.7)."
            ),
            "",
            "## Remaining known limitations",
            *[f"- {limitation}" for limitation in self.limitations],
            "",
            "## Scope",
            self.disclaimer,
            "",
        ]
        return "\n".join(lines)

    def save(self, path: Path | str) -> Path:
        path = Path(path)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path


def run_injection_round(
    *,
    run_id: str,
    module: str,
    factory: str,
    config_path: Path | str,
    suite_runner: SuiteRunner,
    operators: Sequence[MutationOperator],
    probes: Sequence[EvaluateRequest],
    limitations: Sequence[str] = DEFAULT_LIMITATIONS,
) -> DetectionReport:
    """Inject every operator as one mutant, run the suite, report detection.

    The suite must pass at baseline (the pristine evaluator built from
    `module`/`factory`/`config_path` with no operators); each mutant is then
    serialized to a spec, executed against the suite, and probed in-process
    for vacuity. The returned report follows the section 8.5 conventions.
    """
    if not probes:
        raise ValueError("the round needs at least one probe request to test mutants against")

    config = load_config(config_path)
    base_spec = build_evaluator_spec(module, factory, config_path, ())
    base_evaluator = evaluator_from_spec(base_spec)

    baseline = suite_runner.run(base_spec)
    if not baseline.all_passed:
        raise SuiteBaselineError(
            "the suite must pass against the validated implementation before mutants are "
            f"injected (baseline: "
            f"{baseline.summary_line or f'{baseline.passed} passed, {baseline.failed} failed'}; "
            f"failures: {list(baseline.failed_test_ids)})"
        )

    base_canonical = [_canonical(base_evaluator(probe)) for probe in probes]
    mutants: list[MutantResult] = []
    for operator in operators:
        mutant_spec = build_evaluator_spec(module, factory, config_path, (operator,))
        mutant_evaluator = evaluator_from_spec(mutant_spec)
        probes_different = sum(
            1
            for probe, base_out in zip(probes, base_canonical, strict=True)
            if _canonical(mutant_evaluator(probe)) != base_out
        )
        result = suite_runner.run(mutant_spec)
        detected = result.failed > 0
        if probes_different == 0 and detected:
            raise HarnessConsistencyError(
                f"{operator.op_id}: outputs identical to the validated implementation on every "
                "probe, yet the suite reported failures — a flaky suite or a harness bug"
            )
        mutants.append(
            MutantResult(
                op_id=operator.op_id,
                title=operator.title,
                description=operator.description,
                targets=operator.targets,
                criterion_refs=operator.criterion_refs,
                spec=mutant_spec,
                detected=detected,
                vacuous=probes_different == 0,
                probes_different=probes_different,
                suite=result,
            )
        )

    criteria_by_id = {criterion["id"]: criterion for criterion in config["criteria"]}
    tested_ids = sorted({ref for operator in operators for ref in operator.criterion_refs})
    unknown = [ref for ref in tested_ids if ref not in criteria_by_id]
    if unknown:
        raise ValueError(f"operators reference criteria missing from the config: {unknown}")
    criteria_tested = tuple(
        CriterionRef(
            id=ref,
            statement=criteria_by_id[ref]["statement"],
            section=criteria_by_id[ref]["section"],
        )
        for ref in tested_ids
    )
    contract_targets = tuple(
        operator.targets for operator in operators if not operator.criterion_refs
    )

    return DetectionReport(
        run_id=run_id,
        criteria_name=config["name"],
        criteria_version=config["criteria_version"],
        criteria_tested=criteria_tested,
        contract_targets=contract_targets,
        baseline=baseline,
        mutants=tuple(mutants),
        limitations=tuple(limitations),
    )
