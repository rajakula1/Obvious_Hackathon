"""Stub evaluator module for round-level harness tests.

Emits a single present S-01 finding for any request — just enough of the
section 8.3 contract for round mechanics (vacuity probing, spec building) to
be exercised without the full reference evaluator. Used where a round needs a
base evaluator whose response lacks whole sections of findings, e.g. to make
remove-section-check vacuous.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def create_evaluator(config: Mapping[str, Any]):
    """Factory matching the spec's factory(config) signature; config mostly ignored."""

    def evaluate(request):
        return {
            "note_id": request["note_id"],
            "criteria_version": config["criteria_version"],
            "overall_status": "incomplete",
            "findings": [
                {
                    "criterion_id": "S-01",
                    "section": "S",
                    "status": "present",
                    "evidence": [{"start": 0, "end": 1, "text": request["note_text"][:1]}],
                    "message": "stub evaluator — S-01 always present",
                }
            ],
        }

    return evaluate
