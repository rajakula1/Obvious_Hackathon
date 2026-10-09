"""Wire shapes of the SOAP note completeness evaluator (stage-2 spec section 2).

These TypedDicts are the generated package's own data model of record — they
mirror the harness's contract shapes so the injection round can wrap this
evaluator at the seam unchanged, but the dependency points one way only:
harness -> generated. This module never imports the harness.

Field order in these shapes is the wire order of the API responses (spec R4):
response dicts are constructed in field order, so two identical POST /evaluate
calls serialize byte-identically with no sorting step.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class EvaluateRequest(TypedDict):
    """Request body of POST /evaluate (stage-2 spec section 1)."""

    note_id: str
    note_text: str
    visit_type: NotRequired[str]


class EvidenceSpan(TypedDict):
    """Zero-based, end-exclusive character offsets into the raw note_text (R3).

    ``note_text[start:end] == text`` always holds: spans index the exact raw
    string submitted by the caller, with no normalization of any kind.
    """

    start: int
    end: int
    text: str


class Finding(TypedDict):
    """One criterion's result (stage-2 spec section 1 semantics)."""

    criterion_id: str
    section: str | None
    status: str  # present | missing | partial
    evidence: list[EvidenceSpan]
    message: str


class EvaluateResponse(TypedDict):
    """Response body of POST /evaluate (stage-2 spec section 1)."""

    note_id: str
    criteria_version: str
    overall_status: str  # complete | incomplete
    findings: list[Finding]
