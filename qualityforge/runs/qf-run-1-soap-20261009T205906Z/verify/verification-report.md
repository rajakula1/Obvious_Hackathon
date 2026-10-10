# Verification report — Factory Run 2, Stage 7 (§6 stage 7, §7.8)

**Run:** `qf-run-1-soap-20261009T205906Z` · **Branch:** `qualityforge/run-2-soap` @ `c0f0084`
**Gate:** Verify (machine checks, evidence-based — per §5.2 the gate consults
evidence, not an agent's word) · **Executed:** 2026-10-09T23:54–23:59Z (UTC)
**Scope:** V1 independent re-verification of the stage-1 acceptance criteria +
I1 injection round (see `injection-report.md`).

## Part 1 — §7.8 gate checks

| # | Check | Command | Result |
|---|---|---|---|
| 1 | R2 guard 2 — test-manifest re-hash (any drift fails the gate) | `python3 -m qualityforge.tools.validate manifest …/testing/test-manifest.json --repo-root .` | ✅ OK, zero drift |
| 2 | Generated suite | `python3 -m pytest qualityforge/generated/tests -q` | ✅ 10 passed, 0 failed |
| 3 | Full repository suite | `python3 -m pytest qualityforge/ -q --tb=short -p no:cacheprovider` | ✅ **175 passed, 0 failed** (matches the §12.2 100% bar) |
| 4 | Lint (pinned) | `ruff check qualityforge/` (ruff 0.16.10) | ✅ All checks passed! |
| 5 | Criteria config schema | `python3 -m qualityforge.tools.validate criteria …/requirements/acceptance-criteria.yaml` and of-record `criteria-v1.yaml` | ✅ OK on both |
| 6 | Dataset labels, integrity, PHI screen | `python3 -m qualityforge.tools.validate_dataset --data … --criteria …` | ✅ OK — 24 notes, criteria 1.0.0, 0 PHI hits |

**Observation (recorded, not a gate failure):** `ruff format --check
qualityforge/` reports 4 files would be reformatted (`config.py`,
`sections.py`, `generated/tests/__init__.py`, `test_soap_evaluator.py`). The
drift is pre-existing — the same 4 files at parent commit `523b34f`, before
the stage-6 repair. A formatter is not in §7.8's check list (linting, type
checks, complexity, dependencies, security); every stage's recorded evidence
for Run 2 pins `ruff check`, which is clean. Two of the 4 files are generated
test files, so "fixing" them is a §11.4 criteria-ref-routed change — left to
the orchestrator's judgment, out of this evidence-only stage.

## Part 2 — V1 per-criterion walk (independent, full corpus)

Method: for every criterion in the stage-1 config, evaluate **all 24 labeled
corpus notes** (24 × 8 = 192 evaluations) through the harness loader seam
(`qualityforge.generated.soap_evaluator:create_evaluator` over the of-record
config `qualityforge/workloads/soap-evaluator/criteria-v1.yaml`), and check
behavior against the **corpus label** — the defined answer — never against
the implementation's own claims. Raw output: `verification-walk.json`;
walk driver: `verify_criteria.py`.

| Criterion | Statement (config) | Section | check_type | Labeled cases (24 notes) | Behavior | R3 spans | Verdict |
|---|---|---|---|---|---|---|---|
| S-01 | Chief complaint is present in the Subjective section. | S | behavior_check | 19 present · 5 missing | 24/24 match | 0 errors | ✅ PASS |
| S-02 | History of present illness is present in the Subjective section. | S | behavior_check | 19 present · 4 missing · 1 partial (`soap-011`) | 24/24 match | 0 errors | ✅ PASS |
| O-01 | Vital signs are present in the Objective section. | O | behavior_check | 19 present · 5 missing (`soap-006/012/014`…) | 24/24 match | 0 errors | ✅ PASS |
| O-02 | At least one exam or objective finding is present in the Objective section. | O | behavior_check | 19 present · 5 missing (`soap-006/012/015`…) | 24/24 match | 0 errors | ✅ PASS |
| A-01 | At least one diagnosis or assessment statement is present in the Assessment section. | A | behavior_check | 21 present · 3 missing (`soap-007/020/024`) | 24/24 match | 0 errors | ✅ PASS |
| P-01 | At least one plan item is present in the Plan section. | P | behavior_check | 20 present · 4 missing (`soap-008/010/020`…) | 24/24 match | 0 errors | ✅ PASS |
| P-02 | Plan items relate to a stated assessment. | P | behavior_check | 16 present · 6 missing · 2 partial (`soap-017`, `soap-019`) | 24/24 match | 0 errors | ✅ PASS |
| X-01 | All four SOAP sections (Subjective, Objective, Assessment, Plan) are identifiable. | null | behavior_check | 19 present · 4 missing (`soap-005..008`) · 1 partial (`soap-020`, ambiguous → reported, never guessed) | 24/24 match | 0 errors | ✅ PASS |

Every check covers, per evaluated note:

- **Criterion statement + check_type** — the corpus label (present/missing/
  partial) is reproduced by the implementation for all 192 evaluations.
- **R3 span fidelity** — every evidence span is a raw slice of the request's
  `note_text`: `0 <= start <= end <= len(note_text)` and
  `note_text[start:end] == span.text`; zero normalization. All present/partial
  findings carry ≥ 1 span; missing findings carry none (§8.3 evidence rule).
- **Statuses from the config, never hardcoded (R5)** — three in-memory
  config-drivenness probes through the same factory: (a) reversing the
  criteria list reverses the findings order; (b) removing O-01 from the
  config drops exactly that finding; (c) altering the S header markers moves
  section identification (X-01 present → partial on a note only the marker
  can identify — the documented fallback cannot claim it). All follow the
  config. The stage-1 `acceptance-criteria.yaml` is **semantically identical**
  to the of-record `criteria-v1.yaml` (canonical-JSON equality; version stays
  1.0.0 — correct, no criteria change).
- **Dispatch order is config order (R4)** — findings appear exactly one per
  configured criterion, in config order, on every one of the 24 responses.
- **Determinism, byte-for-byte** — repeated calls through the same evaluator
  AND a freshly built evaluator produce identical canonical JSON on every
  note (plus the suite's endpoint-level byte-identity test, `test_R4_repeat_calls_byte_identical`).
- **Seam resolution** — the loader builds the evaluator from the serialized
  spec (module `qualityforge.generated.soap_evaluator`, factory
  `create_evaluator`, of-record config), and the loader default (reference
  evaluator) resolves too.

## Part 3 — Detection capability (I1, summarized here; full report: `injection-report.md`)

The §6 verify-gate injection round injected ONE defect through the
`QUALITYFORGE_EVALUATOR_SPEC` seam (no implementation or test file touched):
`flip_finding_statuses` — the internally consistent mutant that only
label-derived assertions can catch. Baseline 10/10 green → mutant run
**9 failed / 1 passed** → detected, share **1.00 ≥ 0.80** (R1 threshold met).
Restoration proven: seam unset → 10/10 and 175/175 green again.

## Gate outcome

**PASSED** — all §7.8 checks green on evidence; all 8 acceptance criteria
independently verified against the labeled corpus; the injected defect was
detected and the injection restored. Evidence: this report,
`injection-report.md`, `test-output.json` (artifact type `test_output`),
`verification-walk.json`, and the raw `baseline-*.txt` / `injected-pytest.txt`
/ `restored-pytest.txt` outputs. The run advances to the driver's gate
verification (§5.2) — this stage records evidence only and marks nothing
complete.
