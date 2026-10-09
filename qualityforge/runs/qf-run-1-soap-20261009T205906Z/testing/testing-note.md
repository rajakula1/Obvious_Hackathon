# Testing note — Run 2, stage 5 (Testing Agent, spec §7.6, tasks T1+T2)

Run: `qf-run-1-soap-20261009T205906Z` (Factory Run 2) · Branch: `qualityforge/run-2-soap`
(on tip `93fbe06`). This note is the stage record for the runbook node
`todo_wjtn9Qd2` (plan rows T1–T2). Recorded: 2026-10-09, UTC.

## Derivation — tests come from the criteria, not from the code (§7.6, gate law)

Authored from exactly three artifacts: the stage-1 acceptance-criteria config
(`../requirements/acceptance-criteria.yaml` — 8 `behavior_check` criteria with
pinned R3 span semantics), the stage-2 technical specification (section 1 API
contract; section 3 suite layout), and the labeled synthetic corpus
(`qualityforge/workloads/soap-evaluator/data/` — the label is the defined
answer asserted against, corpus README rules 1–8). The implementation
(`qualityforge/generated/soap_evaluator/`) was never read for assertions.
Suite files: `qualityforge/generated/tests/` — `test_soap_evaluator.py` (10
tests), `conftest.py` (seam fixtures + corpus loader), `__init__.py`.

| Test | Criterion (verbatim statement) | Labeled corpus cases asserted |
| --- | --- | --- |
| `test_S_01` | Chief complaint is present in the Subjective section. | present: soap-001, soap-002 (marker-style variety), soap-016 (duplicate-header union, rule 6), soap-022 (preamble layout) · missing: soap-005 (S removed), soap-009 (S empty, rule 2), soap-013 (complaint absent). No partial label exists for S-01 in the corpus. |
| `test_S_02` | History of present illness is present in the Subjective section. | present: soap-001 · **partial: soap-011** (truncated mid-sentence, rule 3 — evidence still required + R3-valid) · missing: soap-005, soap-009 |
| `test_O_01` | Vital signs are present in the Objective section. | present: soap-001 · missing: soap-006 (O removed), soap-012 (garbled content counts as absent, rule 2), soap-014 (no vitals) |
| `test_O_02` | At least one exam or objective finding is present in the Objective section. | present: soap-001 · missing: soap-006, soap-012, soap-015 (no exam finding) |
| `test_A_01` | At least one diagnosis or assessment statement is present in the Assessment section. | present: soap-001 · missing: soap-007 (A removed), soap-024 (bare header, no content) |
| `test_P_01` | At least one plan item is present in the Plan section. | present: soap-001 · missing: soap-008 (P removed), soap-010 (P empty), soap-024 |
| `test_P_02` | Plan items relate to a stated assessment. | README rule 4, all four branches: present: soap-001 (all relate) · **partial: soap-019** (mixed), **soap-017** (duplicate-Plan mixed, rule 6) · missing: soap-018 (none relate), soap-010 (P empty), soap-007 (no assessment stated) |
| `test_X_01` | All four SOAP sections (Subjective, Objective, Assessment, Plan) are identifiable. | present: soap-001 (markers), soap-021 (headerless, fallback pass), soap-022/023 (layout variants), soap-009/010/024 (empty-but-present header still identifies) · **partial: soap-020** (ambiguous note — the brief's required ambiguous→partial case) · missing: soap-005–008 (a section removed) · `section` must be null (config-driven) |
| `test_R4_repeat_calls_byte_identical` | Spec section 1 determinism (R4) | two identical POST /evaluate calls + a fresh app instance → byte-identical bodies (complete + partial notes) |
| `test_api_contract_422_health_and_seam_consistency` | Spec section 1 contract floor | 422 semantics (missing field, blank note_id/note_text `min_length=1`, non-strings `StrictStr`) · totality over well-formed contentless input · `/health` echo · endpoint body == seam evaluator response |

Every criterion test also asserts, on every response it inspects: findings
exactly one per configured criterion **in config order**, `criteria_version`
echoed from the config, finding key set, status vocabulary, section matching
the config, non-empty message, the all-present overall rule, evidence
presence for present/partial, and **R3 span validity** —
`note_text[start:end] == text` with `0 <= start <= end <= len(note_text)` on
the raw, unnormalized note text.

## Mechanism — the loader seam, and why the conftest never mutates the env

Evaluator and config are resolved **only** through the harness loader seam
(`qualityforge/harness/loader.py` / `inject.py`): the conftest reads
`QUALITYFORGE_EVALUATOR_SPEC` when the injection round sets it (baseline or
mutant) and otherwise falls back to the generated-baseline spec —
`qualityforge.generated.soap_evaluator:create_evaluator` over the of-record
config `qualityforge/workloads/soap-evaluator/criteria-v1.yaml` — parsed
through `loader.parse_spec_text` so the default is held to the harness's own
validation. The conftest deliberately does NOT set the variable:
`qualityforge/tests/test_reference_suite.py` resolves
`get_evaluator_under_test()` at module import and expects the loader default;
a process-global set would corrupt the combined whole-repo run. Criterion
checks call the seam-resolved evaluator callable — the type the injection
round wraps (R1) — so the same suite file detects mutants unchanged; endpoint
tests use in-process `TestClient` over the app module the seam names (R6: no
ports, no loopback; `in_process_test_violations` returns CLEAN for both
files). No test imports the generated package directly.

## Execution — honest results (T2)

Environment: `pip install -r qualityforge/requirements-dev.txt` (the of-record
pins, spec section 4: fastapi==0.143.0, pydantic==2.13.4, PyYAML==6.0.3,
pytest==9.0.3, httpx==0.28.1, ruff==0.16.10, jsonschema==4.26.0). Python
3.13.14.

| Check | Result |
| --- | --- |
| Generated suite (`pytest qualityforge/generated/tests/ -v`) | **9 passed, 1 failed** (`1 failed, 9 passed, 1 warning in 0.18s`) |
| Whole-repo sanity (`pytest qualityforge/ -q`) | **1 failed, 174 passed** — all pre-existing factory/reference tests stay green; the single failure is the generated contract-floor test below |
| `ruff check qualityforge` (pinned 0.16.10) | **clean** ("All checks passed!") |
| `in_process_test_violations` (R6, both test files) | **CLEAN** |

**The 1 failure is honest stage-6 (D1) input — the implementation deviates
from the stage-2 spec's section 1 contract in four ways.** The test collects
all violations in one pass (assertion strength unchanged; not weakened — the
implementation is not mine to fix, §11.4):

1. blank `note_id` → HTTP 200, spec pins 422 (`min_length=1`);
2. blank `note_text` → HTTP 200, spec pins 422 (`min_length=1`);
3. contentless well-formed note: X-01 not `partial` — spec: "A note with no
   identifiable sections … X-01 comes back partial (ambiguous, never guessed)";
4. `GET /health` → `{"status":"ok"}` — spec pins `{"status":"ok",
   "criteria_version":"1.0.0"}` (version echo).

All 8 criterion tests pass: every labeled status across present/missing/
partial corpus cases is reproduced, R3 spans slice the raw note text exactly
wherever evidence is produced, config order and version echo hold, and R4
byte determinism holds. The seam-consistency property (endpoint body ==
seam-evaluator response) held on the run (no violation recorded for it).

## Baseline context (pre-existing state before this stage)

Before this stage's commits, the run-1 generated suite (AC-01…AC-08, manifest
under `qualityforge/runs/qf-run-1-soap/`) was stale against the stage-4
regenerated package: `1 failed, 174 passed, 2 errors` — the errors were
`load_criteria() missing 1 required positional argument: 'path'` (run-1
conftest called the old signature) and the failure was the blank-note_id 422
case. Run 2 (re)generates the product through the pipeline: stage 4
regenerated the package over run-1's, and stage 5 regenerates the suite over
run-1's at the spec-assigned path `qualityforge/generated/tests/`. Run-1's
evidence remains intact as history in its own run directory. The 174
non-generated tests are untouched and green throughout.

## Manifest (R2) and finalization

`test-manifest.json` was recorded **after the last test-file edit**
(finalization, gates.md §5.2 guard 1): repository-relative paths + SHA-256 +
bytes for the three suite files, `criteria_refs` = the eight stage-1 criterion
IDs on the test module; `recorded_by: "testing_agent"`. Validated with the
factory's own validator (guard 2 command): `python -m qualityforge.tools.
validate manifest <manifest> --repo-root .` → **OK**. From this point the
suite is frozen (R2): any later edit goes through the bounded-repair skill
with a `criteria-ref:` justification.

Evidence in this directory: `test-results.txt` (raw command outputs),
`test-output.json` (structured `test_output` artifact), `test-manifest.json`,
this note. No task was marked complete — the driver verifies the gate (§5.2).
