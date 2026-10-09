# Technical specification — SOAP note completeness evaluator

Smoke output of the Architecture Agent (spec section 7.2), derived from the
acceptance criteria AC-01 through AC-11. Stored as a `spec` artifact at the
Design gate.

## API contract

`POST /evaluate` — request `{note_id, note_text, visit_type?}`; response per
the §8.3 target shape: `note_id`, `criteria_version` (from the criteria
config), `overall_status` (`complete` | `incomplete`), `findings[]` with
`criterion_id`, `section`, `status`, `evidence[]` spans, `message`.
Determinism (AC-05): response bodies serialize with a fixed key order so two
identical calls return byte-identical JSON.

## Data model

- `CompletenessCriteria` — loaded from the versioned config
  (`criteria_config:` in the acceptance criteria; v1.0.0 of-record).
- `Finding` — criterion_id, section, status, evidence spans, message.
- `EvaluationResult` — note_id, criteria_version, overall_status, findings.

## Module layout

| Module | Responsibility |
|---|---|
| `app/config.py` | Loads the versioned criteria config (AC-06) |
| `app/sections.py` | Section identification: header markers, then the config's fallback heuristic (AC-07) |
| `app/evaluator.py` | Criteria evaluation; builds findings with evidence spans (AC-02, AC-03, AC-04) |
| `app/main.py` | FastAPI app; `POST /evaluate`; deterministic serialization (AC-01, AC-05) |

## Dependencies

- fastapi==0.115.6
- pydantic==2.10.4
- PyYAML==6.0.3

Dev/test dependencies: pytest, httpx (TestClient transport). Generated API
tests run in-process through `TestClient(app)` — never a bound port
(review R6).

## Criteria coverage map

| Criterion | Component | Test approach |
|---|---|---|
| AC-01 | `app/main.py` | `TestClient` schema check |
| AC-02 | `app/evaluator.py` | `TestClient` behavior check |
| AC-03 | `app/evaluator.py` | `TestClient` behavior check |
| AC-04 | `app/evaluator.py` | `TestClient` behavior check (span arithmetic) |
| AC-05 | `app/main.py` | `TestClient` repeat-call byte-equality test |
| AC-06 | `app/config.py` | unit test on config load + version reporting |
| AC-07 | `app/sections.py` | unit tests: header notes and headerless notes |
| AC-08 | Testing Agent suite | generated pytest suite, green final retest |
| AC-09 | Defect-injection round | injection harness, detection share reported |
| AC-10 | Debugging Agent loop | attempt records with retest evidence |
| AC-11 | Evaluation report | report structure check |

Every acceptance criterion maps to at least one component (spec section
7.2). No criterion is left uncovered.
