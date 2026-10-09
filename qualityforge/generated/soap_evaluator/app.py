"""HTTP wiring for the evaluator (stage-2 spec section 3, app.py row).

``create_app`` builds the FastAPI application over the same evaluator factory
the harness seam names (review R1): the app consumes ``create_evaluator``
from this package's ``__init__`` re-export, so the harness and the API load
evaluators through one seam and drift between them is impossible.

Wire shapes (spec section 8.3):

- ``POST /evaluate`` — body ``{"note_id": ..., "note_text": ...}`` (pydantic,
  strict about extra fields); response is the evaluation record whose field
  order IS the wire order — response bodies are built so JSON key order is
  deterministic (note_id, criteria_version, overall_status, findings, and
  each finding's keys in declared order).
- ``GET /health`` — ``{"status": "ok"}``.

Config resolution order: the explicit ``config`` argument, then the
``QF_CRITERIA_CONFIG`` environment variable, then the of-record criteria
config for this workload. A missing or invalid config fails loudly at
startup (spec section 8.2).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from qualityforge.generated.soap_evaluator.config import DEFAULT_CONFIG_PATH, load_criteria
from qualityforge.generated.soap_evaluator.evaluator import Evaluator, create_evaluator
from qualityforge.generated.soap_evaluator.models import EvaluateResponse

_ENV_CONFIG = "QF_CRITERIA_CONFIG"


class EvaluateBody(BaseModel):
    """Request body of POST /evaluate — exactly the two wire fields."""

    model_config = ConfigDict(extra="forbid")

    note_id: str
    note_text: str


def _resolve_config(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Explicit argument, then env var, then the of-record criteria config."""
    if config is not None:
        return config
    env_path = os.environ.get(_ENV_CONFIG)
    if env_path:
        return load_criteria(Path(env_path))
    return load_criteria(DEFAULT_CONFIG_PATH)


def create_app(config: Mapping[str, Any] | None = None) -> FastAPI:
    """Build the API app around an evaluator built from the resolved config."""
    evaluator: Evaluator = create_evaluator(_resolve_config(config))
    app = FastAPI(title="SOAP note completeness evaluator", version="1.0.0")

    @app.post("/evaluate", response_model=EvaluateResponse)
    def evaluate_note(body: EvaluateBody) -> EvaluateResponse:
        return evaluator({"note_id": body.note_id, "note_text": body.note_text})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
