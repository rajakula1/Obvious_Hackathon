# Stage 1 — Requirements (§6 stage 1) — stage record

Run: qf-run-1-soap-20261009T172617Z · Branch: qualityforge/run-1-soap-evaluator

## Execution

The §8.1 requirement (qualityforge/requirements/run-1-soap.md, 510 chars,
synthetic-data rule §11.1 attached) was interpreted into the machine-readable
acceptance-criteria list following the Requirements Agent contract
(qualityforge/agents/requirements/prompt.md):

- Output artifact: `qualityforge/workloads/soap-evaluator/acceptance-criteria.yaml`
  — 11 criteria, AC-01…AC-11, each with id / statement / check_type
  (unit_test | schema_check | behavior_check) / source / spec_ref / review_ref.
- Criteria config named by the list: `criteria-v1.yaml` (§8.2 completeness
  rules, version 1.0.0, schema: qualityforge/schemas/completeness-criteria.schema.json).

## Gate check (evidence, not assertion)

- `python -m qualityforge.tools.validate criteria qualityforge/workloads/soap-evaluator/criteria-v1.yaml`
  → `OK` (criteria-validation.txt).
- Workload criteria suite: `pytest qualityforge/tests/test_workload_criteria.py`
  → 8 passed.
- Provenance: all 11 criteria `source: requirement`; zero `source: assumption`
  entries; zero ambiguity flags — the requirement yielded verifiable criteria
  with no unresolved ambiguity (Requirements Agent rule 1: nothing was silently
  resolved).

## Review amendments carried into the criteria (linkage keys for this run)

- AC-04 — evidence-span semantics pinned per R3 (zero-based, end-exclusive
  character offsets into raw `note_text`).
- AC-05 — determinism as a byte-identical repeat-call test per R4.
- AC-09 — defect-injection round ≥ 80% detection share per R1.
- AC-10 — repair-loop evidence from the natural run or the injection round per R1.
- Section-detection strategy (R5) and in-process TestClient rule (R6) live in
  the criteria config / agent rules respectively.

## Epistemic status (Requirements Agent rule 3, §2.2 / §8.2)

These criteria are **documentation-completeness rules, not clinical
judgments**. The evaluator they specify measures software behavior against
stated documentation rules on synthetic data; they make no claim of clinical
validity.

## Result

Stage gate PASSED on evidence. Handoff to Architecture with AC-01…AC-11 as the
linkage keys (every test, repair justification, and `criteria-ref:` commit in
this run references these IDs).
