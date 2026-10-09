"""Run 2 generated test suite — SOAP note completeness (stage 5, T1/T2).

Derivation (§7.6): every test is authored from the stage-1 acceptance
criteria (``qualityforge/runs/qf-run-1-soap-20261009T205906Z/requirements/
acceptance-criteria.yaml``), the API contract of the stage-2 technical
specification (section 1), and the labeled synthetic corpus
(``qualityforge/workloads/soap-evaluator/data/`` — the label is the defined
answer asserted against). The implementation is never read for assertions.

Mapping: exactly one test per criterion, in config order —
test_S_01, test_S_02, test_O_01, test_O_02, test_A_01, test_P_01, test_P_02,
test_X_01 — each asserting the criterion's labeled status across
present/missing/partial corpus cases, the full response contract (findings
exactly one per configured criterion in config order, criteria_version echo,
overall-status all-present rule, evidence rules), and R3 span validity
(``note_text[start:end] == text``) wherever evidence is produced. Two
contract-level tests pin the spec section 1 floor the corpus cannot: R4 byte
determinism over repeated POST /evaluate calls, and the 422/health/totality
semantics of the API surface.

Mechanism (review R6): criterion checks call the evaluator resolved through
the harness loader seam (conftest) — the callable the injection round wraps —
in-process, no ports. Endpoint tests use ``TestClient`` over the app module
the same seam names, also in-process.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from qualityforge.generated.tests.conftest import load_corpus

STATUS_VOCABULARY = {"present", "missing", "partial"}
RESPONSE_KEYS = {"note_id", "criteria_version", "overall_status", "findings"}
FINDING_KEYS = {"criterion_id", "section", "status", "evidence", "message"}


# --- helpers: the corpus label is the defined answer --------------------------


def labels(record: dict) -> dict[str, str]:
    """The labeled per-criterion statuses of a corpus record."""
    return {f["criterion_id"]: f["status"] for f in record["expected"]["findings"]}


def finding_for(response: dict, criterion_id: str) -> dict:
    """The single finding for a criterion (full-coverage contract makes it exist)."""
    return next(f for f in response["findings"] if f["criterion_id"] == criterion_id)


def evaluate(evaluator: Any, record: dict) -> dict:
    """POST /evaluate's body, evaluated in-process through the seam."""
    request: dict[str, Any] = {"note_id": record["note_id"], "note_text": record["note_text"]}
    if record.get("visit_type"):
        request["visit_type"] = record["visit_type"]
    return evaluator(request)


def assert_response_contract(response: dict, config: Any, note_id: str) -> None:
    """The stage-2 spec section 1 response contract, config-driven."""
    assert set(response) == RESPONSE_KEYS, note_id
    assert response["note_id"] == note_id, note_id
    assert response["criteria_version"] == config["criteria_version"], note_id
    assert [f["criterion_id"] for f in response["findings"]] == [
        c["id"] for c in config["criteria"]
    ], f"{note_id}: findings must be exactly one per configured criterion, in config order"
    section_by_id = {c["id"]: c["section"] for c in config["criteria"]}
    for finding in response["findings"]:
        assert set(finding) == FINDING_KEYS, note_id
        assert finding["status"] in STATUS_VOCABULARY, (note_id, finding["criterion_id"])
        assert finding["section"] == section_by_id[finding["criterion_id"]], (
            f"{note_id}: {finding['criterion_id']} section must match the config"
        )
        assert isinstance(finding["message"], str) and finding["message"], note_id
    all_present = all(f["status"] == "present" for f in response["findings"])
    assert response["overall_status"] == ("complete" if all_present else "incomplete"), note_id


def assert_r3_spans(note_text: str, finding: dict, note_id: str) -> None:
    """R3: spans are zero-based, end-exclusive character offsets into the RAW
    note_text, no normalization — note_text[start:end] reproduces text."""
    for span in finding["evidence"]:
        start, end = span["start"], span["end"]
        assert 0 <= start <= end <= len(note_text), (
            f"{note_id}/{finding['criterion_id']}: span bounds {start}..{end}"
        )
        assert note_text[start:end] == span["text"], (
            f"{note_id}/{finding['criterion_id']}: span text is not the raw slice"
        )


def assert_criterion_matches_labels(
    evaluator: Any, config: Any, corpus: list[dict],
    criterion_id: str, note_ids: tuple[str, ...],
) -> None:
    """Assert one criterion's labeled status on each listed corpus note, with
    the full response contract and R3 span validity on every response."""
    by_id = {r["note_id"]: r for r in corpus}
    for note_id in note_ids:
        record = by_id[note_id]
        response = evaluate(evaluator, record)
        assert_response_contract(response, config, note_id)
        finding = finding_for(response, criterion_id)
        labeled = labels(record)[criterion_id]
        assert finding["status"] == labeled, (
            f"{note_id}: {criterion_id} labeled {labeled}, got {finding['status']}"
        )
        if finding["status"] in {"present", "partial"}:
            assert finding["evidence"], f"{note_id}: {criterion_id} must carry evidence"
            assert_r3_spans(record["note_text"], finding, note_id)


# --- S-01: "Chief complaint is present in the Subjective section." ------------


def test_S_01(evaluator, config, corpus):
    """S-01 — "Chief complaint is present in the Subjective section."

    Labeled cases: present on a complete note, a duplicate-header note
    (union across occurrences, README rule 6), and the preamble layout;
    missing when Subjective is removed (soap-005), empty (soap-009, rule 2),
    or lacks the complaint (soap-013). The corpus defines no partial case
    for S-01 (rule 3 truncation applies to the history narrative, S-02)."""
    assert_criterion_matches_labels(
        evaluator, config, corpus, "S-01",
        ("soap-001", "soap-002", "soap-016", "soap-022", "soap-005", "soap-009", "soap-013"),
    )


# --- S-02: "History of present illness is present in the Subjective section." -


def test_S_02(evaluator, config, corpus):
    """S-02 — "History of present illness is present in the Subjective section."

    Labeled cases: present on the complete note; partial on the truncated
    history (soap-011 — cut off mid-sentence, README rule 3, evidence must
    still be present and R3-valid); missing when Subjective is removed
    (soap-005) or empty (soap-009)."""
    assert_criterion_matches_labels(
        evaluator, config, corpus, "S-02", ("soap-001", "soap-011", "soap-005", "soap-009")
    )


# --- O-01: "Vital signs are present in the Objective section." ----------------


def test_O_01(evaluator, config, corpus):
    """O-01 — "Vital signs are present in the Objective section."

    Labeled cases: present on the complete note; missing when Objective is
    removed (soap-006), garbled (soap-012 — unreadable content counts as
    absent, README rule 2), or lacks vitals (soap-014)."""
    assert_criterion_matches_labels(
        evaluator, config, corpus, "O-01", ("soap-001", "soap-006", "soap-012", "soap-014")
    )


# --- O-02: "At least one exam or objective finding is present in the Objective section."


def test_O_02(evaluator, config, corpus):
    """O-02 — "At least one exam or objective finding is present in the
    Objective section."

    Labeled cases: present on the complete note; missing when Objective is
    removed (soap-006), garbled (soap-012), or carries no exam finding
    (soap-015)."""
    assert_criterion_matches_labels(
        evaluator, config, corpus, "O-02", ("soap-001", "soap-006", "soap-012", "soap-015")
    )


# --- A-01: "At least one diagnosis or assessment statement is present in the Assessment section."


def test_A_01(evaluator, config, corpus):
    """A-01 — "At least one diagnosis or assessment statement is present in
    the Assessment section."

    Labeled cases: present on the complete note; missing when Assessment is
    removed (soap-007) or a bare header names it with no content (soap-024,
    rule 2: an empty section's content criteria are missing)."""
    assert_criterion_matches_labels(
        evaluator, config, corpus, "A-01", ("soap-001", "soap-007", "soap-024")
    )


# --- P-01: "At least one plan item is present in the Plan section." -----------


def test_P_01(evaluator, config, corpus):
    """P-01 — "At least one plan item is present in the Plan section."

    Labeled cases: present on the complete note; missing when Plan is removed
    (soap-008), a bare header with no content (soap-010, rule 2), or in the
    no-content layout note (soap-024)."""
    assert_criterion_matches_labels(
        evaluator, config, corpus, "P-01", ("soap-001", "soap-008", "soap-010", "soap-024")
    )


# --- P-02: "Plan items relate to a stated assessment." ------------------------


def test_P_02(evaluator, config, corpus):
    """P-02 — "Plan items relate to a stated assessment."

    Labeled cases (README rule 4, all four branches): present when every plan
    item relates to a stated assessment (soap-001); partial when some but not
    all relate — the mixed note (soap-019) and the duplicate-Plan mixed note
    (soap-017, rule 6 union); missing when no item relates (soap-018), the
    Plan section is empty (soap-010), or no assessment is stated (soap-007)."""
    assert_criterion_matches_labels(
        evaluator, config, corpus, "P-02",
        ("soap-001", "soap-019", "soap-017", "soap-018", "soap-010", "soap-007"),
    )


# --- X-01: "All four SOAP sections (Subjective, Objective, Assessment, Plan) are identifiable."


def test_X_01(evaluator, config, corpus):
    """X-01 — "All four SOAP sections (Subjective, Objective, Assessment,
    Plan) are identifiable."

    Labeled cases (README rule 5): present under header markers (soap-001),
    under the documented fallback when content is confidently ordered
    (soap-021), and when a header is present-but-empty (soap-009, soap-010,
    soap-024 — an empty-but-present header still identifies its section, so
    X-01 is present while the section's content criteria are missing);
    PARTIAL on the ambiguous note (soap-020 — the fallback cannot confidently
    attribute content, and ambiguity is reported, never guessed); missing
    when a section is removed outright (soap-005..soap-008). X-01's section
    is null in the config and in every response."""
    assert_criterion_matches_labels(
        evaluator, config, corpus, "X-01",
        ("soap-001", "soap-009", "soap-010", "soap-021", "soap-022", "soap-023", "soap-024"),
    )
    assert_criterion_matches_labels(evaluator, config, corpus, "X-01", ("soap-020",))
    assert_criterion_matches_labels(
        evaluator, config, corpus, "X-01", ("soap-005", "soap-006", "soap-007", "soap-008")
    )


# --- R4: byte determinism over the endpoint -----------------------------------


def test_R4_repeat_calls_byte_identical(client, app_module, corpus):
    """R4 — two identical POST /evaluate calls return byte-identical JSON,
    and a freshly built app instance agrees (determinism is not cross-request
    state). One complete note and one partial note (soap-019)."""
    by_id = {r["note_id"]: r for r in load_corpus()}
    for note_id in ("soap-001", "soap-019"):
        record = by_id[note_id]
        payload = {"note_id": record["note_id"], "note_text": record["note_text"]}
        first = client.post("/evaluate", json=payload)
        second = client.post("/evaluate", json=payload)
        assert first.status_code == second.status_code == 200, note_id
        assert first.content == second.content, f"{note_id}: repeat call must be byte-identical"
        fresh = TestClient(app_module.create_app()).post("/evaluate", json=payload)
        assert first.content == fresh.content, f"{note_id}: fresh instance must be byte-identical"


# --- API contract floor: 422 semantics, totality, health, seam consistency ----


def test_api_contract_422_health_and_seam_consistency(client, evaluator, config, corpus):
    """Stage-2 spec section 1, the API contract floor the corpus cannot pin.

    Malformed input -> 422 (missing required field, blank note_id or
    note_text under min_length=1, non-string fields under StrictStr). A
    well-formed string body is never an error however empty the note: content
    criteria come back missing and X-01 partial (ambiguous, never guessed).
    GET /health is the liveness surface and echoes the config version. And
    the endpoint body equals the seam evaluator's response for the same note —
    one seam, no drift between the harness surface and the API surface."""
    # Collect every contract-floor violation in one pass — stage 6 gets the
    # full inventory, not just the first breach (assertion strength unchanged).
    violations: list[str] = []
    for bad in (
        {"note_text": "S: complaint"},
        {"note_id": "x"},
        {"note_id": "", "note_text": "S: complaint"},
        {"note_id": "x", "note_text": ""},
        {"note_id": 7, "note_text": "S: complaint"},
        {"note_id": "x", "note_text": ["S: complaint"]},
    ):
        resp = client.post("/evaluate", json=bad)
        if resp.status_code != 422:
            violations.append(f"malformed input {bad} -> HTTP {resp.status_code}, expected 422")

    contentless = client.post(
        "/evaluate", json={"note_id": "soap-contentless", "note_text": "   \n\t  "}
    )
    if contentless.status_code != 200:
        violations.append(
            f"well-formed contentless body -> HTTP {contentless.status_code}, "
            "expected 200 (the API is total over well-formed input)"
        )
    else:
        body = contentless.json()
        assert_response_contract(body, config, "soap-contentless")
        if finding_for(body, "X-01")["status"] != "partial":
            violations.append(
                "contentless note: X-01 must be partial (no identifiable sections is "
                "ambiguous, never guessed)"
            )
        for criterion in config["criteria"]:
            finding = finding_for(body, criterion["id"])
            if criterion["id"] != "X-01" and finding["status"] != "missing":
                violations.append(f"contentless note: {criterion['id']} must be missing")

    expected_health = {"status": "ok", "criteria_version": config["criteria_version"]}
    health = client.get("/health")
    if health.status_code != 200 or health.json() != expected_health:
        violations.append(
            f"GET /health -> HTTP {health.status_code} {health.text!r}, "
            f"expected 200 {expected_health!r}"
        )

    record = {r["note_id"]: r for r in corpus}["soap-001"]
    payload = {"note_id": record["note_id"], "note_text": record["note_text"]}
    via_endpoint = client.post("/evaluate", json=payload).json()
    via_seam = evaluate(evaluator, record)
    if via_endpoint != via_seam:
        violations.append(
            "endpoint body must equal the seam evaluator's response (one seam, no drift)"
        )

    assert not violations, "API contract floor violations: " + "; ".join(violations)
