# Component mapping — planned tasks → stage-2 components

Run: `qf-run-1-soap-20261009T205906Z` (Factory Run 2) · Stage 3 companion
note to `execution-plan.md`. Every planned task is tied to the stage-2
component it will build (`../architecture/technical-specification.md`) — no
task exists without a spec component, and no spec component lacks a task.

| Planned task | Stage-2 component(s) built | Spec anchor |
| --- | --- | --- |
| C1 | `models.py` (the TypedDict wire shapes — the only shape definitions) + `config.py` (loads the versioned YAML criteria config; `load_criteria(path)` validates required keys and fails loudly on drift) | spec §2 data model, §3 module table |
| C2 | `sections.py` — pure functions over (text, config): case-insensitive line-start `header_markers` first (R5), documented fallback second; duplicate headers unify; ambiguous → `partial`. Directly carries the X-01 behavior | spec §3 module table, §5 X-01 row |
| C3 | `evaluator.py` — one check per configured criterion (S-01, S-02, O-01, O-02, A-01, P-01, P-02 plan-relation, X-01), R3 evidence spans, `overall_status` all-present rule, and the `create_evaluator(config)` factory — the seam the harness names (R1) | spec §3 module table, §5 coverage map, §6 design notes |
| C4 | `app.py` (FastAPI wiring — POST /evaluate + GET /health; `EvaluateBody`; deterministic bodies, R4) + `__init__.py` (re-exports `create_evaluator` and `create_app`) | spec §1 API contract, §3 module table |
| T1–T2 | Generated suite `qualityforge/generated/tests/` — pytest, one test per criterion (criterion-tests skill), in-process `TestClient` (R6), evaluator + config resolved through the loader seam (`QUALITYFORGE_EVALUATOR_SPEC`) | spec §3 generated-suite paragraph, §5 test approaches |
| D1 / R1s | Minimal fixes to `evaluator.py` / `sections.py` / `app.py` only — generated test files are protected (manifest + re-hash, R2); the harness (not this task) applies mutants at the seam | spec §6 design notes; bounded-repair skill |
| V1 | Whole generated package re-verified: suite rerun (§12.2), ruff 0.16.10, manifest re-hash (R2) | spec §4 dependency pins; run-evidence skill |
| I1 | The harness seam unchanged: `loader.get_evaluator_under_test` resolves `create_evaluator` from `qualityforge.generated.soap_evaluator` — mutants exist only at the seam; the implementation and suite are never edited by the round | spec §6 injection-seam note; harness `qualityforge/harness/` |
| H1 / DL | The evidence package (plan, diffs, test results, repair history, verification report, injection summary) + the delivery PR | spec §7.9; run-evidence skill |

Dependency direction preserved: the generated package never imports the
harness — harness → generated (spec §2), so the product stays standalone.
