"""Public seam of the generated SOAP evaluator package.

The harness loads ``create_evaluator`` from this module path (review R1) —
the re-exports below ARE the seam. The app factory shares it.
"""

from qualityforge.generated.soap_evaluator.app import EvaluateBody, create_app
from qualityforge.generated.soap_evaluator.config import load_criteria, validate_criteria
from qualityforge.generated.soap_evaluator.evaluator import Evaluator, create_evaluator
from qualityforge.generated.soap_evaluator.models import (
    EvaluateRequest,
    EvaluateResponse,
    EvidenceSpan,
    Finding,
)

__all__ = [
    "EvaluateBody",
    "EvaluateRequest",
    "EvaluateResponse",
    "Evaluator",
    "EvidenceSpan",
    "Finding",
    "create_app",
    "create_evaluator",
    "load_criteria",
    "validate_criteria",
]
