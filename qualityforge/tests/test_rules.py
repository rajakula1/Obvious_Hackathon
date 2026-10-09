"""Guard-rule coverage: R2 justification gate, R6 in-process rule, §11.1 PHI scan.

Unit tests for qualityforge/agents/rules.py — the pure helpers the
test-integrity, in-process-testing, and synthetic-data skills reference, and
the smoke harness and orchestrator gates call. The accepted-justification
path and the assertion-weakening absolute bar are both exercised here
(review R2).
"""

from __future__ import annotations

import pytest

from qualityforge.agents import rules

JUSTIFIED_DIFF = (
    "--- a/tests/test_evaluate.py\n+++ b/tests/test_evaluate.py\n"
    "@@ -1,3 +0,1 @@\n-assert old_behavior\n+assert corrected_behavior  # criteria-ref: P-02"
)
KNOWN_IDS = {"S-01", "P-02", "X-01"}


# --- is_criterion_id (criterion ID format) -------------------------------------


@pytest.mark.parametrize("value", ["S-01", "AC-11", "X-01", "CRIT-0001"])
def test_criterion_id_accepts_canonical_form(value: str) -> None:
    assert rules.is_criterion_id(value)


@pytest.mark.parametrize("value", ["", "s-01", "S-1", "S-", "-01", "S_01", "S-01-extra"])
def test_criterion_id_rejects_malformed(value: str) -> None:
    assert not rules.is_criterion_id(value)


# --- justification_criterion_ids (criteria-ref extraction) ---------------------


def test_justification_ids_extract_and_dedupe() -> None:
    justification = (
        "criteria-ref: P-02 because the assertion referenced the wrong rule; "
        "criteria-ref: S-01 for the added span check; criteria-ref: P-02 repeated"
    )
    assert rules.justification_criterion_ids(justification) == ["P-02", "S-01"]


def test_justification_ids_empty_without_marker() -> None:
    assert rules.justification_criterion_ids("because the test was wrong") == []


# --- test_change_justified (review R2 guard) ------------------------------------


def test_guard_accepts_justified_test_change() -> None:
    justification = "Wired criterion P-02 against the wrong span; criteria-ref: P-02"
    assert rules.test_change_justified(
        diff=JUSTIFIED_DIFF,
        justification=justification,
        valid_criterion_ids=KNOWN_IDS,
    )


@pytest.mark.parametrize(
    ("diff", "justification"),
    [
        (JUSTIFIED_DIFF, None),  # no justification at all
        (JUSTIFIED_DIFF, ""),  # empty justification
        (JUSTIFIED_DIFF, "the test looked wrong"),  # no criteria-ref marker
        (JUSTIFIED_DIFF, "criteria-ref: Q-99"),  # cites an unknown criterion
        ("", "criteria-ref: P-02"),  # empty diff is a malformed record
        ("   \n", "criteria-ref: P-02"),  # whitespace-only diff
    ],
)
def test_guard_rejects_unlinked_or_malformed_changes(diff: str, justification: str | None) -> None:
    assert not rules.test_change_justified(
        diff=diff, justification=justification, valid_criterion_ids=KNOWN_IDS
    )


def test_guard_allows_marker_without_known_id_set() -> None:
    """Without a known-ID set the marker alone admits the change; the PR-layer
    CI check owns set membership there."""
    assert rules.test_change_justified(diff=JUSTIFIED_DIFF, justification="criteria-ref: Q-99")


# --- in_process_test_violations (review R6) --------------------------------------


def test_in_process_clean_testclient_file() -> None:
    source = "from fastapi.testclient import TestClient\nclient = TestClient(app)\n"
    assert rules.in_process_test_violations(source) == []


@pytest.mark.parametrize(
    ("source", "fragment"),
    [
        ("uvicorn.run(app, host='0.0.0.0')", "uvicorn.run"),
        ("app.run(host='127.0.0.1')", "app.run"),
        ("sock = socket.socket()", "socket.socket"),
        ("server.bind(('0.0.0.0', 8080))", ".bind"),
        ("from http.server import HTTPServer", "HTTPServer"),
        ("import httpx\nhttpx.post('http://localhost:8000/evaluate')", "localhost"),
    ],
)
def test_in_process_violations_detected(source: str, fragment: str) -> None:
    violations = rules.in_process_test_violations(source)
    assert violations and fragment in "\n".join(violations)


def test_in_process_violations_deduplicate() -> None:
    source = "sock.bind(())\nsock.bind(())\n"
    assert len(rules.in_process_test_violations(source)) == 1


# --- phi_scan (spec section 11.1) -------------------------------------------------


def test_phi_scan_clean_synthetic_note() -> None:
    note = (
        "S: Patient reports persistent cough. O: Temperature 38.1 C. "
        "A: Bronchitis. P: Rest and fluids."
    )
    assert rules.phi_scan(note) == []


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("MRN: A1B2C3", "medical record number"),
        ("SSN on file", "SSN"),
        ("id 123-45-6789 issued", "SSN-like"),
        ("DOB: 1980-04-12", "date-of-birth label"),
        ("patient date of birth recorded", "date-of-birth phrase"),
        ("call (555) 123-4567 today", "phone-like"),
        ("phone 555-123-4567 on record", "phone-like"),
    ],
)
def test_phi_scan_flags_markers(text: str, fragment: str) -> None:
    hits = rules.phi_scan(text)
    assert hits and fragment in "\n".join(hits)
