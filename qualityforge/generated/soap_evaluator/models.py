"""Data shapes of the SOAP note completeness evaluator (spec section 8.3).

The evaluator is standalone: these TypedDicts mirror the contract the
defect-injection harness wraps (qualityforge/harness/inject.py) without
importing it — the dependency points from the harness to this package, never
the other way.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NotRequired, TypedDict


class EvaluateRequest(TypedDict):
    """Request body of POST /evaluate (spec section 8.3)."""

    note_id: str
    note_text: str
    visit_type: NotRequired[str]


class EvidenceSpan(TypedDict):
    """Zero-based, end-exclusive character offsets into the raw note_text.

    Pinned by review R3 and the criteria config's evidence_span_semantics:
    ``note_text[start:end]`` reproduces ``text`` with no whitespace or unicode
    normalization of any kind.
    """

    start: int
    end: int
    text: str


class Finding(TypedDict):
    """One criterion's result: present | missing | partial (spec section 8.3)."""

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


type EvaluatorCallable = Callable[[EvaluateRequest], "EvaluateResponse"]
