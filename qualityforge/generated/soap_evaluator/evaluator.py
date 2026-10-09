"""Criterion checks (spec section 8.2) against the Run 1 corpus labels.

Every check is a pure function of (criterion, note, section map). Detection
uses the term families documented below; term families are versioned with the
evaluator and recorded in the run report as the heuristics' known limits —
the labeled corpus is the oracle that locks them.
"""

from __future__ import annotations

import re
from typing import Any

from .models import (
    EvaluateRequest,
    EvaluateResponse,
    EvaluatorCallable,
    EvidenceSpan,
    Finding,
)
from .sections import SECTION_ORDER, SectionMap, SectionSpan, identify_sections

CHIEF_COMPLAINT = re.compile(
    r"\bpatient\b|complain|complaint|reports|describes|pain|sore|itchy|rash|"
    r"headache|cough|heartburn|tingling|pressure|\bcut\b|\bbump\b|tooth|swelling",
    re.I,
)
HISTORY = re.compile(
    r"\bago\b|began|started|appeared|since|yesterday|worse|worsen|gradually|"
    r"past\s+\w+|after|overnight|when\b|helps?|helped|"
    r"for\s+(?:a\s+|\d+|two|three|four|five|six|seven|eight|nine|ten)?\s*"
    r"(?:days?|weeks?|months?|hours?|years?)",
    re.I,
)
VITALS = re.compile(r"vitals|temperature|pulse|respirations|blood pressure|oxygen saturation", re.I)
EXAM = re.compile(
    r"\bexam\b|\bshows?\b|\bclear\b|\bsoft\b|red\w*|rash|swelling|swollen|tender\w*|"
    r"dull|patch|plaques?|wheeze|crackles|congestion|tearing|wasting|\bgrip\b|"
    r"\bcut\b|\bbump\b|lesion|discharge",
    re.I,
)
STATEMENT = re.compile(r"[a-z]", re.I)  # any alphabetic content counts as a statement
UNRELATED_PLAN = re.compile(
    # Documented generic-wellness markers: a plan item matching these does not
    # relate to the stated assessment. Bare "exercise" is deliberately NOT a
    # marker — activity restrictions ("avoid weight-bearing exercise") are
    # condition-specific rest instructions.
    r"multivitamin|vitamin|supplement|dental|walk briskly|stretch|sugary|hydrat",
    re.I,
)

_TRUNCATION_MSG = "content truncated mid-sentence"


def _span(text: str, start: int) -> EvidenceSpan:
    return {"start": start, "end": start + len(text), "text": text}


def _finding(
    criterion: dict[str, Any],
    status: str,
    evidence: list[EvidenceSpan],
    message: str,
) -> Finding:
    return {
        "criterion_id": criterion["id"],
        "section": criterion.get("section"),
        "status": status,
        "evidence": evidence,
        "message": message,
    }


def _sentence_finding(
    criterion: dict[str, Any],
    span: SectionSpan | None,
    pattern: re.Pattern[str],
    present_msg: str,
    missing_msg: str,
    truncation_partial: bool = False,
) -> Finding:
    """present/partial/missing on the section's sentences. With
    ``truncation_partial`` (the narrative criterion S-02), matched content in
    a section that ends mid-sentence is ``partial`` — the history narrative is
    present but incomplete. Other criteria are not degraded by a truncated
    tail they did not match (the corpus labels pin this distinction)."""
    if span is None or not span.text.strip():
        return _finding(criterion, "missing", [], missing_msg)
    matches = [(start, s) for start, s in span.sentences if pattern.search(s)]
    if not matches:
        return _finding(criterion, "missing", [], missing_msg)
    first_start, first_text = matches[0]
    lead = len(first_text) - len(first_text.lstrip())
    evidence = [_span(first_text.strip(), first_start + lead)]
    if truncation_partial:
        last_sentence = span.sentences[-1][1]
        if not last_sentence.rstrip().endswith((".", "!", "?")):
            return _finding(criterion, "partial", evidence, f"{present_msg} ({_TRUNCATION_MSG})")
    return _finding(criterion, "present", evidence, present_msg)


def _check_assessment(criterion: dict[str, Any], span: SectionSpan | None) -> Finding:
    if span is None or not span.text.strip():
        return _finding(criterion, "missing", [], "No assessment stated.")
    sentences = span.sentences
    if not any(STATEMENT.search(s) for _, s in sentences):
        return _finding(criterion, "missing", [], "No assessment stated.")
    first_start, first_text = sentences[0]
    lead = len(first_text) - len(first_text.lstrip())
    return _finding(
        criterion, "present", [_span(first_text.strip(), first_start + lead)], "Assessment stated."
    )


def _plan_items(span: SectionSpan | None) -> list[tuple[int, str]]:
    if span is None:
        return []
    return [(start, text) for start, text in span.sentences if text.strip()]


def _check_plan_items(criterion: dict[str, Any], span: SectionSpan | None) -> Finding:
    """P-01: at least one plan item present (any alphabetic content)."""
    items = _plan_items(span)
    if not items:
        return _finding(criterion, "missing", [], "No plan items recorded.")
    first_start, first_text = items[0]
    lead = len(first_text) - len(first_text.lstrip())
    return _finding(
        criterion, "present", [_span(first_text.strip(), first_start + lead)], "Plan item recorded."
    )


def _check_plan_relation(
    criterion: dict[str, Any], assessment: SectionSpan | None, plan: SectionSpan | None
) -> Finding:
    """P-02 (dataset README rule 4): all plan items relate to a stated
    assessment → present; some → partial; none (or no assessment, or no plan)
    → missing. Relatedness is the documented heuristic: an item is unrelated
    when it matches the generic-wellness markers; anything else counts as
    condition-specific care. Known limit: lexical, not clinical reasoning —
    recorded in the run report."""
    items = _plan_items(plan)
    assessment_stated = assessment is not None and assessment.text.strip() != ""
    if not assessment_stated or not items:
        return _finding(criterion, "missing", [], "No assessment or no plan to relate.")
    related = [item for item in items if not UNRELATED_PLAN.search(item[1])]
    if not related:
        return _finding(criterion, "missing", [], "No plan item relates to the assessment.")
    first_start, first_text = related[0]
    lead = len(first_text) - len(first_text.lstrip())
    evidence = [_span(first_text.strip(), first_start + lead)]
    if len(related) == len(items):
        return _finding(criterion, "present", evidence, "All plan items relate to the assessment.")
    return _finding(
        criterion, "partial", evidence, "Some plan items do not relate to the assessment."
    )


def _check_structure(criterion: dict[str, Any], note_text: str, section_map: SectionMap) -> Finding:
    """X-01 (dataset README rule 5): sections identifiable by marker or
    confident fallback. A markerless note the fallback cannot fully attribute
    is ambiguous → partial, never guessed."""
    found = [s for s in SECTION_ORDER if s in section_map.sections]
    evidence: list[EvidenceSpan] = []
    for section in found:
        span = section_map.sections[section]
        if span.sentences:
            first_start, first_text = span.sentences[0]
            lead = len(first_text) - len(first_text.lstrip())
            evidence.append(_span(first_text.strip(), first_start + lead))
        elif span.marker_start is not None:
            # Empty-but-marked section: the honest evidence is the raw marker
            # itself ("S:"), not a zero-length span.
            evidence.append(_span(note_text[span.marker_start : span.start], span.marker_start))
        else:
            evidence.append(_span(note_text[span.start : span.start], span.start))
    if len(found) == len(SECTION_ORDER):
        return _finding(criterion, "present", evidence, "All four SOAP sections identified.")
    if section_map.markerless_note:
        first_line = note_text.split("\n", 1)[0]
        ambiguous_evidence = (
            [_span(first_line.strip() or first_line, 0)] if note_text.strip() else []
        )
        return _finding(
            criterion,
            "partial",
            ambiguous_evidence,
            "Sections ambiguous: no header markers and the fallback could not "
            "confidently attribute all sections.",
        )
    missing = [s for s in SECTION_ORDER if s not in section_map.sections]
    return _finding(
        criterion,
        "missing",
        # AC-03: a missing finding carries no evidence — some sections may
        # have been identified, but the criterion itself is not satisfied.
        [],
        f"Section(s) {', '.join(missing)} absent or unidentifiable.",
    )


def evaluate_note(request: EvaluateRequest, config: dict[str, Any]) -> EvaluateResponse:
    """Evaluate one note against the config's criteria, in config order."""
    note_text = request["note_text"]
    header_markers = config["section_detection"]["header_markers"]
    section_map = identify_sections(note_text, header_markers)
    sections = section_map.sections

    findings: list[Finding] = []
    for criterion in config["criteria"]:
        cid = criterion["id"]
        section = criterion.get("section")
        if section is None:
            findings.append(_check_structure(criterion, note_text, section_map))
            continue
        if section not in sections:
            findings.append(
                _finding(criterion, "missing", [], f"Section {section} absent or unidentifiable.")
            )
            continue
        span = sections[section]
        if cid == "S-01":
            findings.append(
                _sentence_finding(
                    criterion,
                    span,
                    CHIEF_COMPLAINT,
                    "Chief complaint recorded.",
                    "No chief complaint in Subjective.",
                )
            )
        elif cid == "S-02":
            findings.append(
                _sentence_finding(
                    criterion,
                    span,
                    HISTORY,
                    "History of present illness recorded.",
                    "No history of present illness in Subjective.",
                    truncation_partial=True,
                )
            )
        elif cid == "O-01":
            findings.append(
                _sentence_finding(
                    criterion,
                    span,
                    VITALS,
                    "Vital signs recorded in Objective.",
                    "No vital signs in Objective.",
                )
            )
        elif cid == "O-02":
            findings.append(
                _sentence_finding(
                    criterion,
                    span,
                    EXAM,
                    "Objective examination findings recorded.",
                    "No examination findings in Objective.",
                )
            )
        elif cid == "A-01":
            findings.append(_check_assessment(criterion, span))
        elif cid == "P-01":
            findings.append(_check_plan_items(criterion, span))
        elif cid == "P-02":
            findings.append(_check_plan_relation(criterion, sections.get("A"), sections.get("P")))
        else:
            raise ValueError(f"no check implemented for criterion {cid!r}")

    overall = "complete" if all(f["status"] == "present" for f in findings) else "incomplete"
    return {
        "note_id": request["note_id"],
        "criteria_version": config["criteria_version"],
        "overall_status": overall,
        "findings": findings,
    }


def create_evaluator(config: dict[str, Any]) -> EvaluatorCallable:
    """Module-level factory the harness loader consumes (spec naming:
    module=qualityforge.generated.soap_evaluator, factory=create_evaluator).
    Returns a single-argument callable bound to one criteria config."""

    def evaluate(request: EvaluateRequest) -> EvaluateResponse:
        return evaluate_note(request, config)

    return evaluate
