# Technical specification — SOAP note completeness evaluator

Run: qf-run-1-soap-20261009T172617Z · Stage 2 (§6 stage 2, Architecture Agent) ·
Input: acceptance-criteria.yaml (AC-01…AC-11) + criteria-v1.yaml v1.0.0 ·
Epistemic status: documentation-completeness rules, not clinical judgments (§2.2).

## 1. API contract (spec §8.3 floor)

Two endpoints. Request/response field order below is the wire order (AC-05
fixed key order comes from pydantic model field order — deterministic by
construction, one code path).

### POST /evaluate

Request (application/json):

```json
{ "note_id": "soap-001", "note_text": "S: …\nO: …\nA: …\nP: …", "visit_type": "office visit" }
```

- `note_id` (str, required) — echoed into the response.
- `note_text` (str, required) — the RAW note text; spans index this exact string.
- `visit_type` (str, optional) — metadata; not used by v1 criteria.

200 response:

```json
{
  "note_id": "soap-001",
  "criteria_version": "1.0.0",
  "overall_status": "complete",
  "findings": [
    {
      "criterion_id": "S-01",
      "section": "S",
      "status": "present",
      "evidence": [{ "start": 0, "end": 83, "text": "S: The patient reports …" }],
      "message": "Chief complaint present in Subjective."
    }
  ]
}
```

- `overall_status` ∈ {complete, incomplete} — complete only when every finding
  is `present` (a `partial` finding makes the note incomplete; the reading the
  harness pins in `overall_status_from`).
- `findings` contains one entry per configured criterion (8 criteria in v1).
- `status` ∈ {present, missing, partial}. `evidence` is empty for `missing`.
- Evidence spans: zero-based character offsets into the raw `note_text`,
  end-exclusive, no normalization — `note_text[start:end]` reproduces `text` (R3/AC-04).
- Malformed input (missing/blank `note_id` or `note_text`, wrong types) → 422
  via pydantic validation.

### GET /health

`{"status": "ok", "criteria_version": "1.0.0"}` — liveness for TestClient smoke
and deployment sanity; carries no PHI and reads no notes.

Determinism (AC-05): one evaluation code path per request, no timestamps,
randomness, dict iteration over unsorted sets, or environment-dependent output;
two identical calls produce byte-identical bodies. Verified by a repeat-call
test in the generated suite.

## 2. Data model

Mirrors the harness data contracts (qualityforge/harness/inject.py) so the
injection round can wrap the generated evaluator unchanged — the generated
package defines its OWN TypedDicts (it never imports the harness):

- `EvaluateRequest`: note_id, note_text, visit_type?
- `EvidenceSpan`: start, end, text (zero-based, end-exclusive, raw note_text)
- `Finding`: criterion_id, section (S|O|A|P|null), status, evidence[], message
- `EvaluateResponse`: note_id, criteria_version, overall_status, findings[]
- `Evaluator` = Callable[[EvaluateRequest], EvaluateResponse] — the harness seam type.
- `CriteriaConfig`: the loaded criteria-v1.yaml (criteria_version, name,
  section_detection with header_markers + fallback, evidence_span_semantics,
  criteria list of 8 rules S-01…X-01).

## 3. Module layout (qualityforge/generated/soap_evaluator/)

| Module | Responsibility |
| --- | --- |
| `__init__.py` | package marker; re-exports `create_evaluator` and the app factory |
| `models.py` | the TypedDicts above; the only shape definitions |
| `config.py` | loads the versioned YAML criteria config (pyyaml), exposes `load_criteria(path)` and validates required keys — criteria_version, section_detection, criteria |
| `sections.py` | section identification per the config strategy: case-insensitive line-start header markers first (R5), documented fallback second (scan for data categories in document order); ambiguous → `partial` on X-01, never guessed; pure functions over (text, config) |
| `evaluator.py` | the rule engine: one check per configured criterion (S-01, S-02, O-01, O-02, A-01, P-01, P-02 plan-relation, X-01) against the identified sections; builds findings with R3 spans and messages; `overall_status` via all-present rule; exposes `create_evaluator(config)` — the factory the harness spec names — closing over the config |
| `app.py` | FastAPI wiring: POST /evaluate + GET /health; constructs the evaluator once from the config at startup; validates request shape; returns deterministic bodies |

Generated suite (Testing Agent, stage 5): `qualityforge/generated/tests/test_soap_evaluator.py`
— pytest, in-process `TestClient` (R6), evaluator obtained through the loader
seam: `QUALITYFORGE_EVALUATOR_SPEC` set → `evaluator_from_spec` (mutant runs);
unset → pristine `create_evaluator(load_criteria(criteria-v1.yaml))` in-process
(one `pytest.approx`-free, fixture-scoped evaluator).

## 4. Dependencies (pinned, minimal — spec §7.2)

| Package | Version | Why |
| --- | --- | --- |
| fastapi | ==0.143.0 | the API framework (requirement names a Python API) |
| pydantic | ==2.13.4 | request/response models; field order gives AC-05 fixed key order |
| httpx | ==0.28.1 | TestClient transport for the generated suite (R6) |
| pyyaml | ==6.0.3 | criteria-config loader (AC-06) |

Nothing else. No LLM client, no database, no port binding (R6), no utils
sprawl. Repo dev pins (pytest, ruff) come from qualityforge/requirements-dev.txt.

## 5. Criteria coverage map — config criteria v1.0.0

| Criterion | Component | Test approach (generated suite) |
| --- | --- | --- |
| S-01 chief complaint in S | `evaluator.py` `_check_s01` via `sections.py` S span | labeled notes: complete (present) + missing-S (missing); evidence-span assertion per R3 |
| S-02 HPI in S | `evaluator.py` `_check_s02` | labeled notes covering present/missing |
| O-01 vitals in O | `evaluator.py` `_check_o01` | labeled notes covering present/missing |
| O-02 exam finding in O | `evaluator.py` `_check_o02` | labeled notes covering present/missing |
| A-01 diagnosis in A | `evaluator.py` `_check_a01` | labeled notes covering present/missing |
| P-01 plan item in P | `evaluator.py` `_check_p01` | labeled notes covering present/missing |
| P-02 plan relates to assessment | `evaluator.py` `_check_p02` (term overlap plan↔A) | notes with unrelated plan items (partial/missing) — the harness `skip_plan_relation_check` operator targets this check |
| X-01 all four sections identifiable | `sections.py` `identify_sections` + fallback | notes without standard headers (fallback path); ambiguous → partial (never guessed) |

## 6. AC coverage map — acceptance criteria AC-01…AC-11

| AC | Satisfied by |
| --- | --- |
| AC-01 API contract | `app.py` + `models.py`; suite schema checks on live TestClient responses |
| AC-02 evidence on present/partial | `evaluator.py` finding builder; suite check 4 |
| AC-03 missing findings name criterion_id | finding builder iterates config IDs; suite asserts per-criterion findings |
| AC-04 R3 span semantics | `sections.py` offsets into raw note_text; suite asserts `note_text[start:end] == text` |
| AC-05 byte-identical repeat calls | deterministic single code path in `app.py`; suite repeat-call test |
| AC-06 config-driven criteria + version | `config.py` loader; response carries `criteria_version`; suite asserts version echo |
| AC-07 config-versioned detection + fallback tested | `sections.py` implements the config strategy; suite includes no-standard-header notes |
| AC-08 generated tests green on final retest | stage 5/6 of this run; CI |
| AC-09 injection round ≥ 80% + share reported | stage 7 of this run via `qualityforge/harness/inject.py` runner (4 operators) |
| AC-10 repair-loop evidence with logged attempts | stages 5–6 records; injection round supplies material if the natural run passes first try |
| AC-11 evaluation report with disclaimer | stage 8 report, §8.5 shape, verbatim DISCLAIMER |

## Design notes

- **Injection seam**: `create_evaluator(config)` closes over the loaded config;
  the harness spec names module `qualityforge.generated.soap_evaluator` (resolved
  via the package `__init__` or `evaluator` module — the runner's spec carries
  the exact module path), factory `create_evaluator`, config_path the repo's
  criteria-v1.yaml. Baseline round = spec with zero operators; the suite file
  is byte-identical across baseline and mutant runs (R1).
- **The generated package never imports the harness** — the dependency points
  the other way (harness → generated), keeping the product standalone.
- **Fallback honesty**: the fallback identifies sections by data-category
  scanning and reports ambiguity as `partial` against X-01 rather than
  guessing — matching the config's documented fallback verbatim.
- No criterion was left without a component; no design gap to flag back.
