"""Generated unit tests — Run 1 SOAP completeness evaluator.

Tests derive from the §7.1 acceptance criteria and the labeled synthetic
corpus (the label is the defined answer asserted against), not from reading
the implementation. The evaluator under test comes from the harness loader
(conftest installs the pristine generated spec when the env var is unset);
the same suite runs unchanged against every injection-round mutant (§12.3,
review R1). All API tests are in-process TestClient calls (review R6).

Coverage map: AC-01 schema + 422s · AC-02 evidence presence + span slice ·
AC-03 missing ⇒ no evidence · AC-05 byte determinism · AC-06 version from
config · AC-07 corpus sweep + fallback notes · AC-08 overall from findings ·
AC-04 via raw-text slice fidelity (unnormalized note included).
"""

from __future__ import annotations

import importlib
import json
import os

from fastapi.testclient import TestClient

from qualityforge.generated.soap_evaluator import create_app
from qualityforge.generated.tests.conftest import NOTES_DIR, REPO_ROOT
from qualityforge.harness.loader import EVALUATOR_SPEC_ENV_VAR, parse_spec_text

STATUS_VOCABULARY = {"present", "missing", "partial"}
SECTIONS_VOCABULARY = {"S", "O", "A", "P", None}
RESPONSE_KEYS = {"note_id", "criteria_version", "overall_status", "findings"}
FINDING_KEYS = {"criterion_id", "section", "status", "evidence", "message"}


def expected_status_map(record: dict) -> dict[str, str]:
    """The corpus label as a criterion-id → status map (the defined answer)."""
    return {f["criterion_id"]: f["status"] for f in record["expected"]["findings"]}


def got_status_map(response_json: dict) -> dict[str, str]:
    return {f["criterion_id"]: f["status"] for f in response_json["findings"]}


def span_slices_exact(note_text: str, response_json: dict) -> list[str]:
    """Every evidence span must slice the raw note text exactly (AC-02/04)."""
    problems: list[str] = []
    for finding in response_json["findings"]:
        for span in finding["evidence"]:
            start, end, text = span["start"], span["end"], span["text"]
            if not (0 <= start <= end <= len(note_text)):
                problems.append(f"{finding['criterion_id']}: bounds {start}..{end}")
            elif note_text[start:end] != text:
                problems.append(f"{finding['criterion_id']}: {text!r} != raw slice")
    return problems


def evaluate_record(client: TestClient, record: dict):
    return client.post(
        "/evaluate", json={"note_id": record["note_id"], "note_text": record["note_text"]}
    )


# --- AC-06: version comes from the criteria config -----------------------------


def test_health_reports_ok_and_configured_version(client, config):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["criteria_version"] == config["criteria_version"]


# --- AC-01: response schema and full criteria coverage -------------------------


def test_evaluate_response_schema_and_criteria_coverage(client, config, corpus):
    for record in corpus:
        resp = evaluate_record(client, record)
        assert resp.status_code == 200, record["note_id"]
        body = resp.json()
        assert set(body) == RESPONSE_KEYS, record["note_id"]
        assert body["note_id"] == record["note_id"]
        assert body["criteria_version"] == config["criteria_version"]
        assert [f["criterion_id"] for f in body["findings"]] == [
            c["id"] for c in config["criteria"]
        ], record["note_id"]
        for finding in body["findings"]:
            assert set(finding) == FINDING_KEYS, record["note_id"]
            assert finding["status"] in STATUS_VOCABULARY
            assert finding["section"] in SECTIONS_VOCABULARY
            assert finding["message"]


# --- AC-07 / AC-08: the corpus label is the asserted answer --------------------


def test_corpus_labels_reproduced(client, corpus):
    for record in corpus:
        resp = evaluate_record(client, record)
        assert resp.status_code == 200
        body = resp.json()
        assert got_status_map(body) == expected_status_map(record), record["note_id"]
        assert body["overall_status"] == record["expected"]["overall_status"], record["note_id"]


def test_overall_status_derived_from_findings(client, corpus):
    for record in corpus:
        body = evaluate_record(client, record).json()
        all_present = all(f["status"] == "present" for f in body["findings"])
        assert body["overall_status"] == ("complete" if all_present else "incomplete")


# --- AC-02 / AC-04: evidence spans slice the raw note text ---------------------


def test_present_and_partial_findings_have_evidence(client, corpus):
    for record in corpus:
        body = evaluate_record(client, record).json()
        for finding in body["findings"]:
            if finding["status"] in {"present", "partial"}:
                assert finding["evidence"], (record["note_id"], finding["criterion_id"])


def test_evidence_spans_slice_raw_note_text_exactly(client, corpus):
    for record in corpus:
        body = evaluate_record(client, record).json()
        problems = span_slices_exact(record["note_text"], body)
        assert not problems, (record["note_id"], problems)


def test_unnormalized_note_text_keeps_span_fidelity(client):
    """AC-04: offsets index the raw request string — no normalization. The
    synthetic note carries double spaces, a tab, and a non-ASCII character."""
    raw = (
        "S:  Patient reports a mild  café cough\tthat began 3 days ago.\n"
        "O:    Temp 37.2 C, pulse 78. Both ears show mild redness.\n"
        "A: Viral upper respiratory infection.\n"
        "P: Rest and fluids. Return if fever persists beyond five days."
    )
    body = client.post("/evaluate", json={"note_id": "synthetic-raw", "note_text": raw}).json()
    assert body["overall_status"] == "complete"
    assert not span_slices_exact(raw, body), "spans must slice the unnormalized text"


# --- AC-03: missing findings carry no evidence ---------------------------------


def test_missing_findings_carry_no_evidence(client, corpus):
    for record in corpus:
        body = evaluate_record(client, record).json()
        for finding in body["findings"]:
            if finding["status"] == "missing":
                assert finding["evidence"] == [], (record["note_id"], finding["criterion_id"])


# --- AC-05: byte-identical repeat calls -----------------------------------------


def test_deterministic_repeat_calls_byte_identical(client, corpus):
    for record in corpus[:3]:
        payload = {"note_id": record["note_id"], "note_text": record["note_text"]}
        first = client.post("/evaluate", json=payload)
        second = client.post("/evaluate", json=payload)
        # Fresh app instance too — determinism is not cross-request state.
        fresh = TestClient(create_app()).post("/evaluate", json=payload)
        assert first.content == second.content == fresh.content, record["note_id"]


# --- AC-01: malformed requests are rejected -------------------------------------


def test_malformed_requests_return_422(client):
    for bad in (
        {"note_text": "S: complaint"},
        {"note_id": "", "note_text": "S: complaint"},
        {"note_id": "x"},
        {"note_id": "x", "note_text": ""},
        {"note_id": 7, "note_text": "S: complaint"},
        {"note_id": None, "note_text": "S: complaint"},
    ):
        resp = client.post("/evaluate", json=bad)
        assert resp.status_code == 422, bad


# --- AC-07: fallback identification on markerless notes -------------------------


def test_fallback_notes_identified_without_markers(client, corpus):
    by_id = {r["note_id"]: r for r in corpus}
    for note_id, x01_expected in (("soap-020", "partial"), ("soap-021", "present")):
        record = by_id[note_id]
        lines = [ln.strip() for ln in record["note_text"].splitlines() if ln.strip()]
        assert not any(ln[:2] in {"S:", "O:", "A:", "P:"} for ln in lines), (
            f"{note_id} is a markerless corpus note by construction"
        )
        body = evaluate_record(client, record).json()
        x01 = next(f for f in body["findings"] if f["criterion_id"] == "X-01")
        assert x01["status"] == x01_expected, note_id
        assert x01["evidence"], note_id


# --- AC-08 support: the injection seam resolves the spec consistently -----------


def test_seam_spec_round_trip_matches_app_resolution(client):
    """The app's evaluator resolution is consistent across fresh instances:
    with the harness spec set (injection round) it must parse, name a
    callable factory, and evaluate identically to the fixture client; with
    it unset (CI baseline) the app binds the generated evaluator and must
    still be instance-independent."""
    raw = os.environ.get(EVALUATOR_SPEC_ENV_VAR, "")
    if raw.strip():
        spec = parse_spec_text(raw)
        assert set(spec) >= {"module", "factory", "config_path"}
        module = importlib.import_module(str(spec["module"]))
        assert callable(getattr(module, str(spec["factory"]), None)), spec

    record = json.loads((NOTES_DIR / "soap-001.json").read_text(encoding="utf-8"))
    payload = {"note_id": record["note_id"], "note_text": record["note_text"]}
    baseline = client.post("/evaluate", json=payload)
    fresh = TestClient(create_app()).post("/evaluate", json=payload)
    assert baseline.status_code == fresh.status_code == 200
    assert baseline.content == fresh.content
    assert REPO_ROOT.is_dir()
