"""Generated SOAP note completeness evaluator (Factory Run 1).

Standalone package: the harness wraps it (harness → generated dependency
direction); this package never imports the harness outside the app's
injection-seam branch.
"""

from .app import create_app
from .config import CriteriaConfigError, load_criteria
from .evaluator import evaluate_note
from .models import EvaluateRequest, EvaluateResponse, EvidenceSpan, Finding
from .sections import identify_sections

__all__ = [
    "CriteriaConfigError",
    "EvidenceSpan",
    "EvaluateRequest",
    "EvaluateResponse",
    "Finding",
    "create_app",
    "evaluate_note",
    "identify_sections",
    "load_criteria",
]
