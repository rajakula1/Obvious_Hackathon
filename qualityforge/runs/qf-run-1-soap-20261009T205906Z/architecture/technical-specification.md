# Technical specification — SOAP note completeness evaluator

Run: `qf-run-1-soap-20261009T205906Z` (Factory Run 2) · Stage 2 (§6 stage 2,
Architecture Agent, §7.2) · Branch: `qualityforge/run-2-soap`.
Input: the stage-1 acceptance-criteria config
(`../requirements/acceptance-criteria.yaml` — 8 criteria, `criteria_version`
1.0.0, semantically identical to the of-record
`qualityforge/workloads/soap-evaluator/criteria-v1.yaml`) — worked from the
file, not from memory. Evidence-span and section-detection semantics are
carried from that config verbatim (reviews R3, R5).
Epistemic status: documentation-completeness rules, not clinical judgments
(§2.2). Examples below are synthetic (§11.1).

## 1. API contract (spec §8.3 floor)

Two endpoints. Response field order below is the wire order: pydantic model
field order is the serialization order, so determinism (R4) holds by
construction — one code path, no post-hoc sorting.

### POST /evaluate

Request (application/json):

```json
{ "note_id": "soap-001", "note_text": "S: …\nO: …\nA: …\nP: …", "visit_type": "office visit" }
```

- `note_id` (string, required, non-empty) — echoed into the response.
- `note_text` (string, required, non-empty) — the RAW note text as submitted;
  evidence spans index this exact string (R3). No normalization is performed
  on it, ever.
- `visit_type` (string, optional) — metadata only; no v1 criterion reads it.

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
      "evidence": [{ "start": 0, "end": 30, "text": "S: The patient reports a sore" }],
      "message": "Chief complaint present in Subjective."
    }
  ]
}
```

Semantics:

- `criteria_version` — echoed from the loaded criteria config (never a
  hardcoded literal), proving the response is config-driven.
- `findings` — exactly one entry per configured criterion, in config order.
  Config order is deterministic, so findings order is deterministic without
  any sorting step (R4).
- `status` ∈ {present, missing, partial}. Every `present`/`partial` finding
  carries non-empty `evidence` tied to spans in the note; every `missing`
  finding names its criterion via `criterion_id` (§8.3 requirements).
- `section` ∈ {S, O, A, P} ∪ {null} — null only for X-01, whose `section` is
  null in the config (it is about all four sections, not one).
- `evidence[]` — spans with the config-pinned semantics: zero-based character
  offsets into the exact raw `note_text`, `end`-exclusive, no normalization —
  `note_text[start:end]` reproduces `text`.
- `overall_status` ∈ {complete, incomplete} — complete only when every finding
  is `present`; a `partial` finding makes the note incomplete (the reading the
  harness pins in `overall_status_from`, and dataset README rule 7).
- `message` — plain, human-readable, documentation-completeness language
  only; no clinical claim of any kind (§2.2).

Error semantics:

- Malformed input → 422 (pydantic validation): missing required field, blank
  `note_id` or `note_text` (`min_length=1`), or a non-string in any field
  (`StrictStr`). The error body is FastAPI's standard 422 shape — nothing
  custom to keep deterministic.
- A well-formed string body is never an error, however empty or garbled the
  note: completeness failures are findings, not 4xx. A note with no
  identifiable sections evaluates normally — content criteria come back
  `missing`, X-01 comes back `partial` (ambiguous, never guessed — R5).
  The API is total over well-formed input.
- No other error paths exist: evaluation of valid strings cannot throw, the
  app holds no external state, and unknown routes / wrong methods get the
  framework's standard 404 / 405.

Determinism (R4): no timestamps, randomness, dict iteration over unsorted
sets, or environment-dependent output anywhere in the response path; two
identical `POST /evaluate` calls return byte-identical bodies. Verified by a
repeat-call test in the generated suite.

### GET /health

`{"status": "ok", "criteria_version": "1.0.0"}` — liveness for the TestClient
smoke and deployment sanity. Carries no PHI, reads no notes.

## 2. Data model

The wire shapes mirror the harness data contracts
(`qualityforge/harness/inject.py`) so the injection round can wrap the
generated evaluator at the seam unchanged. The generated package defines its
OWN shapes and never imports the harness — the dependency points the other
way (harness → generated), keeping the product standalone.

- `EvaluateRequest`: `note_id`, `note_text`, `visit_type?` — the parsed
  request body.
- `EvidenceSpan`: `start`, `end`, `text` — zero-based, end-exclusive character
  offsets into the raw `note_text` (R3); `note_text[start:end] == text`.
- `Finding`: `criterion_id`, `section` (S|O|A|P|null), `status`
  (present|missing|partial), `evidence[]`, `message`.
- `EvaluateResponse`: `note_id`, `criteria_version`, `overall_status`,
  `findings[]`.
- `Evaluator` — callable `(EvaluateRequest) -> EvaluateResponse`; the type the
  harness seam (`loader.get_evaluator_under_test`) resolves.
- `CriteriaConfig` — the parsed criteria YAML: `criteria_version`, `name`,
  `description`, `evidence_span_semantics`, `section_detection`
  (`strategy`, `header_markers`, `fallback`), `criteria[]` (8 rules). Loaded
  once by `config.py`; consumed read-only by `sections.py` and
  `evaluator.py`. No rule is hardcoded outside the config file.
- App layer additionally defines one pydantic `EvaluateBody` (the request
  model that produces the 422s above); it is the validation surface only —
  the wire shapes above remain the data model of record.

## 3. Module layout (qualityforge/generated/soap_evaluator/)

Stage 4 (re)generates the package here; the harness resolves its factory at
this path. One module, one responsibility:

| Module | Responsibility |
| --- | --- |
| `__init__.py` | package marker; re-exports `create_evaluator` and `create_app` |
| `models.py` | the TypedDicts above; the only shape definitions |
| `config.py` | loads the versioned YAML criteria config (pyyaml); `load_criteria(path)` validates required keys — `criteria_version`, `section_detection`, `criteria` — and fails loudly on drift |
| `sections.py` | section identification per the config strategy: case-insensitive line-start `header_markers` first (R5), the documented fallback second (scan in document order for the section's data categories); pure functions over (text, config); duplicate headers unify across occurrences (union of all occurrences of a section) |
| `evaluator.py` | the rule engine: one check per configured criterion (S-01, S-02, O-01, O-02, A-01, P-01, P-02 plan-relation, X-01) against the identified sections; builds findings with R3 spans and plain messages; `overall_status` via the all-present rule; exposes `create_evaluator(config)` — the factory the harness spec names — closing over the config |
| `app.py` | FastAPI wiring: POST /evaluate + GET /health; `create_app()` constructs the evaluator once from the config; `EvaluateBody` validates the request shape; responses are deterministic bodies |

Generated suite (Testing Agent, stage 5): `qualityforge/generated/tests/` —
pytest, one test per criterion (criterion-tests skill), in-process
`TestClient` (R6), evaluator and config obtained through the loader seam
(`QUALITYFORGE_EVALUATOR_SPEC` set → mutant resolution; unset → pristine
`create_evaluator(load_criteria())` in-process). The same suite file runs
unchanged against the validated implementation and every mutant (R1).

## 4. Dependencies — minimal, pinned (spec §7.2)

Runtime, for the Python API stage 4 builds:

| Package | Pin | Why |
| --- | --- | --- |
| fastapi | fastapi==0.143.0 | the API framework (requirement names a Python API); of-record verify-gate pin (`qualityforge/requirements-dev.txt`) |
| pydantic | pydantic==2.13.4 | request body model; field order gives the R4 fixed wire order |
| PyYAML | PyYAML==6.0.3 | criteria-config loader (config-driven criteria) |

Dev/test, for the generated suite and the quality gate:

| Package | Pin | Why |
| --- | --- | --- |
| pytest | pytest==9.0.3 | the generated suite runner |
| httpx | httpx==0.28.1 | TestClient transport for in-process API tests (R6) |
| ruff | ruff==0.16.10 | lint for the §7.8 quality checks |

Nothing else. No LLM client, no database, no port binding (R6), no utils
sprawl. (`jsonschema==4.26.0`, also in `requirements-dev.txt`, is
factory-side validator tooling — not a dependency of the generated app or its
suite, so it is excluded here.) Every line above carries an exact `==` pin; a
dependency without a pin is invalid (§7.2). Versions are the of-record pins
Run 1's verify gate installed and ran against; nothing new is introduced.

## 5. Criteria coverage map — the §7.2 gate

One row per criterion ID from the stage-1 config
(`../requirements/acceptance-criteria.yaml`). All eight are `behavior_check`;
the test approach for every row is in-process (`TestClient` over the app —
R6) with labeled synthetic corpus notes
(`qualityforge/workloads/soap-evaluator/data/`), one test per criterion
authored before implementation, and R3 span assertions
(`note_text[start:end] == text`) wherever evidence is produced.

| Criterion | Component | Test approach |
| --- | --- | --- |
| S-01 chief complaint in S | `evaluator.py` S-check via the `sections.py` S span | labeled notes: complete (present) + missing-complaint (missing); span validity asserted per R3 |
| S-02 history of present illness in S | `evaluator.py` S-check (second predicate over the S span) | labeled notes covering present/missing |
| O-01 vital signs in O | `evaluator.py` O-check via the O span | labeled notes covering present/missing |
| O-02 ≥1 exam/objective finding in O | `evaluator.py` O-check (second predicate over the O span) | labeled notes covering present/missing |
| A-01 ≥1 diagnosis/assessment in A | `evaluator.py` A-check via the A span | labeled notes covering present/missing |
| P-01 ≥1 plan item in P | `evaluator.py` P-check via the P span | labeled notes covering present/missing |
| P-02 plan items relate to a stated assessment | `evaluator.py` plan-relation check (plan items ↔ stated assessment) — all relate → present, some → partial, none / no assessment / no Plan → missing (README rule 4); the harness `skip_plan_relation_check` operator (`PLAN_RELATION_CRITERION_ID = "P-02"`) targets exactly this component | labeled notes: unrelated plan items (partial), no assessment (missing) |
| X-01 all four sections identifiable | `sections.py` `identify_sections` — header markers first (R5), documented fallback second; empty-but-present header still identifies its section (X-01 present while content criteria are missing); ambiguous note → X-01 `partial`, never guessed | labeled notes: no-standard-header notes exercising the fallback; an ambiguous note asserting `partial` |

Every criterion maps to at least one component; no design gap to flag back
to the orchestrator. The mapping is checkable: the criteria IDs above are the
linkage keys the criterion-tests skill, repair justifications, and
`criteria-ref:` commit markers use (R2).

## 6. Design notes

- **Injection seam (R1):** `create_evaluator(config)` closes over the loaded
  config. The injection round's evaluator spec names module
  `qualityforge.generated.soap_evaluator`, factory `create_evaluator`, and
  the config path; suite processes resolve the evaluator (and config) through
  `loader.get_evaluator_under_test()` so baseline and mutant runs execute a
  byte-identical suite file. Mutants exist only at the seam — the round never
  edits the implementation or the suite (§11.4, R2).
- **The generated package never imports the harness** — the dependency
  direction is harness → generated, so the product is standalone.
- **Config of record:** the generated app loads
  `qualityforge/workloads/soap-evaluator/criteria-v1.yaml` (v1.0.0) — the
  workload's versioned criteria config. The stage-1 config is this run's
  derivation evidence and is parsed-equal to it (stage-1 note: `parsed_equal:
  True`). The response echoes the version loaded from the file, so any future
  criteria change surfaces in every response without an evaluator rewrite.
- **Fallback honesty:** the fallback attributes content by the documented
  data-category scan and reports ambiguity as `partial` against X-01 — never
  a guess (R5, config fallback verbatim).
- **In-process rule inherited:** the specification states it so the Testing
  Agent inherits it: API tests run in-process through `TestClient(app)`; no
  bound ports, no live server, no network loopback (R6).
- **Disclaimer boundary (§8.5):** the API surface above reports completeness
  findings only; the software-correctness disclaimer
  ("Results reflect software correctness against stated criteria, not
  clinical validity.") is carried by the stage-8 evaluation report, not
  duplicated into every response body.
- **Synthetic examples only (§11.1):** every example in this specification,
  and every fixture the generated suite uses, is template-generated synthetic
  data; the PHI scan runs on committed text artifacts before push.
