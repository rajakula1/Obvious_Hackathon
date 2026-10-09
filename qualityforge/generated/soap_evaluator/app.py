"""FastAPI surface of the SOAP note completeness evaluator (spec section 8.3).

The app is a thin, deterministic wrapper around a single-argument evaluator
callable (request in, response out):

- Tests bind through FastAPI's in-process TestClient (review R6) — the API
  never binds a live port inside a sandbox run.
- The evaluator is resolved through the defect-injection seam: with
  QUALITYFORGE_EVALUATOR_SPEC unset the baseline callable runs; when set, the
  harness loader wraps the SAME evaluator with the spec's operators, so the
  injection round exercises the identical API surface with zero code edits
  (spec section 12.3, review R1). The harness import is lazy and lives only
  in that branch — the core package stays standalone without the env var.
"""

from __future__ import annotations

import os
from functools import partial

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from .config import load_criteria
from .evaluator import evaluate_note
from .models import EvaluateRequest, EvaluateResponse

ENV_EVALUATOR_SPEC = "QUALITYFORGE_EVALUATOR_SPEC"


class EvaluateBody(BaseModel):
    """Request schema (spec section 8.3). Strict strings: a blank or
    non-string field is malformed input and answers 422."""

    model_config = ConfigDict(extra="ignore")

    note_id: StrictStr = Field(min_length=1)
    note_text: StrictStr = Field(min_length=1)
    visit_type: StrictStr | None = None


def _resolve_evaluator(config: dict):
    """Bind the baseline callable, or the harness-wrapped callable when the
    injection seam is configured. Both are single-argument callables."""
    spec_path = os.environ.get(ENV_EVALUATOR_SPEC)
    if not spec_path:
        return partial(evaluate_note, config=config)
    from qualityforge.harness.loader import load_evaluator  # runtime seam only

    return load_evaluator(spec_path)


def _to_request(body: EvaluateBody) -> EvaluateRequest:
    request: EvaluateRequest = {"note_id": body.note_id, "note_text": body.note_text}
    if body.visit_type is not None:
        request["visit_type"] = body.visit_type
    return request


def create_app() -> FastAPI:
    """Build the API with the criteria config loaded once at startup — a
    config that fails validation must fail startup, not requests."""
    config = load_criteria()
    evaluator = _resolve_evaluator(config)

    app = FastAPI(
        title="SOAP Note Completeness Evaluator",
        description="Run 1 completeness evaluator (software correctness, not clinical validity).",
        version=config["criteria_version"],
    )

    @app.post("/evaluate")
    def post_evaluate(body: EvaluateBody) -> EvaluateResponse:
        return evaluator(_to_request(body))

    @app.get("/health")
    def get_health() -> dict[str, str]:
        return {"status": "ok", "criteria_version": config["criteria_version"]}

    return app
