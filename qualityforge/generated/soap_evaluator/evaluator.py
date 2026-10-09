"""The rule engine (stage-2 spec section 3, evaluator.py row).

One check per configured criterion — S-01, S-02, O-01, O-02, A-01, P-01,
P-02 plan-relation, X-01 — against the sections ``sections.py`` identified.
Findings are built in config order (deterministic without sorting, R4) with
evidence spans carrying the R3 semantics: zero-based, end-exclusive offsets
into the exact raw ``note_text`` — ``note_text[start:end]`` reproduces every
reported span text, with no normalization.

``create_evaluator(config)`` is the factory the harness seam names (review
R1): it closes over the criteria config and returns a pure
``(EvaluateRequest) -> EvaluateResponse`` callable. The config is consumed
read-only; no rule is hardcoded here — the config file governs (section 8.2).

Status vocabulary per the dataset README: ``present`` (content identifiable
and complete), ``missing`` (section absent/unidentifiable, section empty, or
content absent — unreadable content counts as absent), ``partial`` (content
present but truncated mid-sentence, or P-02 with some related items). The
structure criterion answers ``partial`` for an ambiguous note — never a guess
(review R5).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from qualityforge.generated.soap_evaluator.config import validate_criteria
from qualityforge.generated.soap_evaluator.models import (
    EvaluateRequest,
    EvaluateResponse,
    EvidenceSpan,
    Finding,
)
from qualityforge.generated.soap_evaluator.sections import (
    SECTION_ORDER,
    LineAtOffset,
    SectionMap,
    content_lines,
    content_sentences,
    identify_sections,
    is_complaint,
    is_finding,
    is_vital,
    lines_in,
)

Evaluator = Callable[[EvaluateRequest], EvaluateResponse]

PRESENT = "present"
MISSING = "missing"
PARTIAL = "partial"
_TERMINAL_PUNCT = (".", "!", "?")

# Criterion content predicates — documentation-completeness heuristics pinned
# by the workload's labeled corpus (spec section 8.4). These implement the
# criteria statements; they are not clinical judgments (spec section 2.2).
# The O vitals/findings and S complaint predicates ARE the sections.py
# fallback categories — shared, not duplicated.
_HISTORY = (
    re.compile(r"\bago\b"),
    re.compile(r"\byesterday\b"),
    re.compile(r"\bsince\b"),
    re.compile(r"\bbegan\b"),
    re.compile(r"\bstart(ed)?\b"),
    re.compile(r"\bappear(ed)?\b"),
    re.compile(r"\bworse(n(s|ed)?)?\b"),
    re.compile(r"\bimproved?\b"),
    re.compile(r"\breliev(ed|es)\b"),
    re.compile(r"\bpast\b"),
    re.compile(r"\bhistory of\b"),
    re.compile(r"\bthis morning\b"),
    re.compile(r"\b(one|two|three|four|five|six|seven|\d+)\s+(day|week|month|year)s?\b"),
)
# P-02 plan-relation (README rule 4): a plan item relates to the stated
# assessment unless it is a general health-maintenance item — the class of
# items the corpus labels call out as unrelated to any assessment (vitamins
# and supplements, dental care, generic exercise and diet phrasing).
_MAINTENANCE_TERMS = (
    "vitamin",
    "supplement",
    "multivitamin",
    "dental",
    "stretching",
    "sugary drink",
    "walk briskly",
)


def _span_of(line: LineAtOffset) -> EvidenceSpan:
    """An R3 span for a line: raw slice reproducing the line exactly."""
    offset, text = line
    return {"start": offset, "end": offset + len(text), "text": text}


def overall_status(findings: Sequence[Finding]) -> str:
    """The all-present rule: complete only when every finding is present.

    A ``partial`` finding leaves the note incomplete (the dataset README's
    rule 7 and the harness's pinned reading).
    """
    all_present = all(finding["status"] == PRESENT for finding in findings)
    return "complete" if all_present else "incomplete"


def _finding(criterion: Mapping[str, Any], status: str, evidence: list[EvidenceSpan]) -> Finding:
    """A finding in the wire shape; messages stay documentation-completeness."""
    suffix = {PRESENT: "satisfied.", PARTIAL: "partially satisfied.", MISSING: "not satisfied."}[
        status
    ]
    return {
        "criterion_id": str(criterion["id"]),
        "section": criterion["section"],  # type: ignore[assignment]
        "status": status,
        "evidence": evidence,
        "message": f"{criterion['statement']} — {suffix}",
    }


def _first_line(
    lines: Sequence[LineAtOffset], predicate: Callable[[str], bool]
) -> LineAtOffset | None:
    """First line satisfying the predicate, or None."""
    for line in lines:
        if predicate(line[1]):
            return line
    return None


def _label_check(
    criterion: Mapping[str, Any],
    lines: Sequence[LineAtOffset],
    predicate: Callable[[str], bool],
) -> Finding:
    hit = _first_line(lines, predicate)
    if hit is None:
        return _finding(criterion, MISSING, [])
    return _finding(criterion, PRESENT, [_span_of(hit)])


def _check_s01(criterion: Mapping[str, Any], lines: Sequence[LineAtOffset]) -> Finding:
    """S-01: a stated complaint — complaint phrasing or a symptom mention."""
    hit = _first_line(lines, is_complaint)
    if hit is None:
        return _finding(criterion, MISSING, [])
    return _finding(criterion, PRESENT, [_span_of(hit)])


def _check_s02(criterion: Mapping[str, Any], lines: Sequence[LineAtOffset]) -> Finding:
    """S-02: history present, unless the narrative ends mid-sentence (partial)."""

    def has_history(line: str) -> bool:
        lowered = line.lower()
        return any(pattern.search(lowered) for pattern in _HISTORY)

    hit = _first_line(lines, has_history)
    if hit is None:
        return _finding(criterion, MISSING, [])
    # Truncated mid-sentence: content present but incomplete (README rule 3).
    truncated = not lines[-1][1].endswith(_TERMINAL_PUNCT)
    status = PARTIAL if truncated else PRESENT
    return _finding(criterion, status, [_span_of(hit)])


def _check_p02(
    criterion: Mapping[str, Any],
    plan_items: Sequence[LineAtOffset],
    assessment: Sequence[LineAtOffset],
) -> Finding:
    """P-02: every plan item relates, unless the plan is generic maintenance."""
    if not plan_items or not assessment:
        return _finding(criterion, MISSING, [])
    related = [
        item
        for item in plan_items
        if not any(term in item[1].lower() for term in _MAINTENANCE_TERMS)
    ]
    if not related:
        return _finding(criterion, MISSING, [])
    status = PRESENT if len(related) == len(plan_items) else PARTIAL
    return _finding(criterion, status, [_span_of(related[0])])


def _check_x01(criterion: Mapping[str, Any], text: str, sections: SectionMap) -> Finding:
    """X-01: all four sections identifiable; ambiguous notes answer partial."""
    if not sections.missing:
        evidence = [
            _span_of(lines_in(text, sections.spans[section])[0]) for section in SECTION_ORDER
        ]
        return _finding(criterion, PRESENT, evidence)
    if sections.ambiguous and sections.unclaimed:
        evidence = [_span_of(lines_in(text, sections.unclaimed[:1])[0])]
        return _finding(criterion, PARTIAL, evidence)
    return _finding(criterion, MISSING, [])


def _check_criterion(
    criterion: Mapping[str, Any],
    text: str,
    sections: SectionMap,
    header_markers: Mapping[str, Sequence[str]],
) -> Finding:
    """Dispatch one configured criterion to its check."""
    criterion_id = criterion["id"]
    section = criterion["section"]
    if section is None:
        return _check_x01(criterion, text, sections)
    if section not in sections.spans:
        return _finding(criterion, MISSING, [])
    lines = content_lines(text, sections.spans[section], header_markers)
    if criterion_id == "S-01":
        return _check_s01(criterion, lines)
    if criterion_id == "S-02":
        return _check_s02(criterion, lines)
    if criterion_id == "O-01":
        return _label_check(criterion, lines, is_vital)
    if criterion_id == "O-02":
        return _label_check(criterion, lines, is_finding)
    if criterion_id in ("A-01", "P-01"):
        if not lines:
            return _finding(criterion, MISSING, [])
        return _finding(criterion, PRESENT, [_span_of(lines[0])])
    if criterion_id == "P-02":
        plan_items = content_sentences(text, sections.spans["P"], header_markers)
        assessment = content_lines(text, sections.spans.get("A", []), header_markers)
        return _check_p02(criterion, plan_items, assessment)
    raise ValueError(
        "the evaluator implements the criteria config's starting set only; "
        f"unknown criterion id {criterion_id!r}"
    )


def create_evaluator(config: Mapping[str, Any]) -> Evaluator:
    """Factory consumed by the harness seam (R1): build an evaluator from a config.

    The config is validated loudly here too — the harness hands over the raw
    parsed mapping, and drift must stop the evaluator at startup, not drift
    silently at request time.
    """
    validate_criteria(config)
    header_markers: Mapping[str, Sequence[str]] = config["section_detection"]["header_markers"]
    version = config["criteria_version"]

    def evaluate(request: EvaluateRequest) -> EvaluateResponse:
        text = request["note_text"]
        sections = identify_sections(text, config["section_detection"])
        findings = [
            _check_criterion(criterion, text, sections, header_markers)
            for criterion in config["criteria"]
        ]
        return {
            "note_id": request["note_id"],
            "criteria_version": version,
            "overall_status": overall_status(findings),
            "findings": findings,
        }

    return evaluate
