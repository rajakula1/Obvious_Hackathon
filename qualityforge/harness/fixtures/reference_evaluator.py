"""Reference mini-implementation of the SOAP note completeness evaluator.

The "validated implementation" the smoke round injects defects into (spec
section 12.3, review R1). It is deliberately small but honest: a full,
deterministic implementation of the section 8.2 starting criteria over the
section 8.3 contract, consuming the criteria config rather than a hardcoded
copy of the rules (section 8.2, review R5) and emitting evidence spans with
the pinned R3 semantics (zero-based, end-exclusive character offsets into
the raw note_text, no normalization).

Heuristics, pinned here because the synthetic corpus of spec section 8.4 is
built to them (all data is synthetic — spec section 11.1):

- Sections are identified by the config's header markers, matched
  case-insensitively at the start of a line; the earliest match wins and a
  section runs to the next section marker or end of note.
- Criterion content labels are matched case-insensitively as substrings of
  the section's lines: chief complaint ("Chief complaint:", "CC:"), history
  of present illness ("HPI:", "History of present illness:"), vital signs
  ("Vitals:", "Vital signs:"), exam findings ("Exam:", "Physical exam:",
  "Findings:"), diagnosis ("Diagnosis:", "Assessment:").
- P-02 (plan items relate to a stated assessment): every plan item must
  mention a diagnosis term — the text following a diagnosis label in the
  Assessment section, semicolon-split. All items relate: present; none:
  missing; some: partial. No Assessment section or no plan items: missing.
- X-01 (all four sections identifiable): present when all four markers are
  found, partial when some are (the structure is partially identifiable),
  missing when none are — an unidentifiable note is never guessed at.

Scope limits, stated rather than hidden: this fixture implements exactly the
section 8.2 starting set (criteria S-01 through X-01); a config with an
unknown criterion id fails loudly instead of silently passing. Findings for
null-section criteria (the Structure rules) carry section: null — the
criteria config is authoritative (review R5). `visit_type` is accepted and
ignored. The implementation is a pure function of (request, config): no
clocks, no randomness, deterministic per the section 8.3 requirement.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from qualityforge.harness.inject import (
    SECTION_ORDER,
    EvaluateRequest,
    EvaluateResponse,
    Evaluator,
    EvidenceSpan,
    Finding,
    overall_status_from,
)

CHIEF_COMPLAINT_LABELS = ("chief complaint:", "cc:")
HPI_LABELS = ("hpi:", "history of present illness:")
VITALS_LABELS = ("vitals:", "vital signs:")
EXAM_LABELS = ("exam:", "physical exam:", "findings:")
DIAGNOSIS_LABELS = ("diagnosis:", "assessment:")

# Line-at-offset pairs threaded through the checks so evidence spans can be
# cut straight from the raw note text with the pinned R3 semantics.
LineAtOffset = tuple[int, str]

CheckFn = Callable[..., Finding]


def _lines(text: str, span: tuple[int, int]) -> list[LineAtOffset]:
    """Non-empty lines of text[span[0]:span[1]] as (offset of first char, line)."""
    start, end = span
    entries: list[LineAtOffset] = []
    cursor = start
    for raw in text[start:end].split("\n"):
        stripped = raw.strip()
        if stripped:
            entries.append((cursor + len(raw) - len(raw.lstrip()), stripped))
        cursor += len(raw) + 1
    return entries


def _is_marker_line(line: str, header_markers: Mapping[str, Sequence[str]]) -> bool:
    lowered = line.lower()
    return any(
        lowered.startswith(marker.lower())
        for markers in header_markers.values()
        for marker in markers
    )


def identify_sections(
    text: str, header_markers: Mapping[str, Sequence[str]]
) -> dict[str, tuple[int, int]]:
    """Spans (start, end-exclusive) of each section identified by its markers."""
    all_lines = _lines(text, (0, len(text)))
    starts: dict[str, int] = {}
    for section in SECTION_ORDER:
        markers = tuple(marker.lower() for marker in header_markers[section])
        for offset, line in all_lines:
            if any(line.lower().startswith(marker) for marker in markers):
                starts[section] = offset
                break
    spans: dict[str, tuple[int, int]] = {}
    for section, start in starts.items():
        later = [pos for other, pos in starts.items() if other != section and pos > start]
        spans[section] = (start, min(later) if later else len(text))
    return spans


def _span_of(line_at_offset: LineAtOffset) -> EvidenceSpan:
    offset, line = line_at_offset
    return {"start": offset, "end": offset + len(line), "text": line}


def _finding(criterion: Mapping[str, Any], status: str, evidence: list[EvidenceSpan]) -> Finding:
    suffix = {
        "present": "satisfied",
        "partial": "partially satisfied",
        "missing": "not satisfied",
    }[status]
    return {
        "criterion_id": criterion["id"],
        "section": criterion["section"],
        "status": status,
        "evidence": evidence,
        "message": f"{criterion['statement']} — {suffix}.",
    }


def _find_line(lines: Sequence[LineAtOffset], labels: tuple[str, ...]) -> LineAtOffset | None:
    for entry in lines:
        lowered = entry[1].lower()
        if any(label in lowered for label in labels):
            return entry
    return None


def _label_finding(criterion: Mapping[str, Any], hit: LineAtOffset | None) -> Finding:
    if hit is None:
        return _finding(criterion, "missing", [])
    return _finding(criterion, "present", [_span_of(hit)])


def _after_label(line: str, labels: tuple[str, ...]) -> str | None:
    lowered = line.lower()
    hits = [(lowered.find(label), label) for label in labels if label in lowered]
    if not hits:
        return None
    index, label = min(hits)
    return line[index + len(label) :]


def _diagnosis_terms(a_lines: Sequence[LineAtOffset]) -> list[str]:
    terms: list[str] = []
    for _offset, line in a_lines:
        after = _after_label(line, DIAGNOSIS_LABELS)
        if after is None:
            continue
        for part in after.split(";"):
            term = part.strip().rstrip(".").strip().lower()
            if term:
                terms.append(term)
    return terms


def _plan_items(
    lines: Sequence[LineAtOffset], header_markers: Mapping[str, Sequence[str]]
) -> list[LineAtOffset]:
    return [entry for entry in lines if not _is_marker_line(entry[1], header_markers)]


def _check_p01(
    criterion: Mapping[str, Any],
    lines: Sequence[LineAtOffset],
    _text: str,
    _spans: Mapping[str, tuple[int, int]],
    header_markers: Mapping[str, Sequence[str]],
) -> Finding:
    items = _plan_items(lines, header_markers)
    return _label_finding(criterion, items[0] if items else None)


def _check_p02(
    criterion: Mapping[str, Any],
    lines: Sequence[LineAtOffset],
    text: str,
    spans: Mapping[str, tuple[int, int]],
    header_markers: Mapping[str, Sequence[str]],
) -> Finding:
    a_lines = _lines(text, spans["A"]) if "A" in spans else []
    terms = _diagnosis_terms(a_lines)
    items = _plan_items(lines, header_markers)
    if not terms or not items:
        return _finding(criterion, "missing", [])
    related = [item for item in items if any(term in item[1].lower() for term in terms)]
    if not related:
        return _finding(criterion, "missing", [])
    status = "present" if len(related) == len(items) else "partial"
    return _finding(criterion, status, [_span_of(related[0])])


def _check_structure(
    criterion: Mapping[str, Any], text: str, spans: Mapping[str, tuple[int, int]]
) -> Finding:
    found = [section for section in SECTION_ORDER if section in spans]
    if not found:
        return _finding(criterion, "missing", [])
    evidence = [_span_of(_lines(text, spans[section])[0]) for section in found]
    status = "present" if len(found) == len(SECTION_ORDER) else "partial"
    return _finding(criterion, status, evidence)


def _label_check(labels: tuple[str, ...]) -> CheckFn:
    def check(
        criterion: Mapping[str, Any],
        lines: Sequence[LineAtOffset],
        *_args: Any,
    ) -> Finding:
        return _label_finding(criterion, _find_line(lines, labels))

    return check


_CHECKS: Mapping[str, CheckFn] = {
    "S-01": _label_check(CHIEF_COMPLAINT_LABELS),
    "S-02": _label_check(HPI_LABELS),
    "O-01": _label_check(VITALS_LABELS),
    "O-02": _label_check(EXAM_LABELS),
    "A-01": _label_check(DIAGNOSIS_LABELS),
    "P-01": _check_p01,
    "P-02": _check_p02,
}


def _check_criterion(
    criterion: Mapping[str, Any],
    text: str,
    spans: Mapping[str, tuple[int, int]],
    header_markers: Mapping[str, Sequence[str]],
) -> Finding:
    criterion_id = criterion["id"]
    section = criterion["section"]
    if section is None:
        return _check_structure(criterion, text, spans)
    if section not in spans:
        return _finding(criterion, "missing", [])
    check = _CHECKS.get(criterion_id)
    if check is None:
        raise ValueError(
            "the reference evaluator implements the section 8.2 starting set only; "
            f"unknown criterion id {criterion_id!r}"
        )
    return check(criterion, _lines(text, spans[section]), text, spans, header_markers)


def create_evaluator(config: Mapping[str, Any]) -> Evaluator:
    """Factory consumed by the harness loader: build an evaluator from a config."""
    header_markers: Mapping[str, Sequence[str]] = config["section_detection"]["header_markers"]
    version = config["criteria_version"]

    def evaluate(request: EvaluateRequest) -> EvaluateResponse:
        text = request["note_text"]
        spans = identify_sections(text, header_markers)
        findings = [
            _check_criterion(criterion, text, spans, header_markers)
            for criterion in config["criteria"]
        ]
        return {
            "note_id": request["note_id"],
            "criteria_version": version,
            "overall_status": overall_status_from(findings),
            "findings": findings,
        }

    return evaluate
