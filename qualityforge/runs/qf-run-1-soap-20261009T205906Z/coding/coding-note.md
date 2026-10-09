# Stage 4 — Coding note (Run 2, qf-run-1-soap-20261009T205906Z)

Branch `qualityforge/run-2-soap`, work on tip `d9c9152`. All four tasks
implemented through file tools (write-file / edit-file) per gate §5.2; every
diff in this directory is the scoped `git diff` of one task's files against
the branch base.

## What was built, per task

- **C1 — `models.py` + `config.py`** (`c1.diff`): wire TypedDicts
  (EvaluateRequest, EvaluateResponse, Finding, EvidenceSpan) and criteria
  loading with loud structural validation (`load_criteria`, `validate_criteria`,
  `CriteriaConfigError`). `DEFAULT_CONFIG_PATH` resolves the of-record
  criteria config relative to the package, so `create_app()` works from any
  working directory.
- **C2 — `sections.py`** (`c2.diff`): section identification per the config's
  pinned strategy (`header_markers_with_fallback`, R5) — header markers first
  (case-insensitive line-start match; a section runs from its marker line to
  the next marker line of any section, so duplicate headers unify per the
  dataset README and out-of-order sections keep their own spans), the
  documented fallback second (unattributed text is sentence-scanned in
  document order; each missing section claims the first forward run of
  sentences matching its data categories, in S→O→A→P order), and an
  ambiguous note (a section still missing while unattributable content
  remains) surfaced as `SectionMap.ambiguous` so X-01 answers `partial`
  instead of guessing. All offsets are zero-based, end-exclusive, into the
  raw `note_text` (R3); the sentence splitter never splits a period between
  digits, and negated symptom mentions ("No fever") do not attribute content.
- **C3 — `evaluator.py`** (`c3.diff`): one check per criterion
  (S-01, S-02, O-01, O-02, A-01, P-01, P-02, X-01) dispatched from config
  order (R4 — no sorting), evidence spans as exact raw slices
  (`note_text[start:end]` reproduces every span text), `overall_status` via
  the all-present rule, and the `create_evaluator(config)` factory named by
  the harness seam (R1). The O vitals/findings and S complaint predicates
  are the same functions the fallback uses — one source of truth.
- **C4 — `app.py` + `__init__.py`** (`c4.diff`): `create_app(config)` builds
  FastAPI over the same factory seam; `POST /evaluate` (pydantic
  `EvaluateBody`, strict about extra fields) and `GET /health`; response
  field order is the declared wire order and is deterministic across calls;
  the package `__init__` re-exports the seam the loader imports.

## Config path used

`qualityforge/workloads/soap-evaluator/criteria-v1.yaml` (of-record,
criteria_version 1.0.0) — loaded via `load_criteria`; `criteria_version` is
echoed from the loaded config, never hardcoded. The harness loader
(`qualityforge/harness/loader.py`) resolves the same module/factory pair
through `QUALITYFORGE_EVALUATOR_SPEC`; verified end-to-end below.

## Repair attempts (2 of 3 budget; §7.3)

1. **Corpus-probe repair (one cycle, three defects fixed together).** A
   scratch probe outside the repo ran the labeled corpus through the
   evaluator: (a) fallback claim spans were built as
   `offset + len(sentence)` mis-applied to the sentence string (TypeError);
   (b) the negation guard `.rstrip()`ed away the space its prefixes end
   with, so "No fever" read as a symptom (soap-013 S-01 false present);
   (c) bare `P:` markers counted as plan items (soap-010 P-02 false
   present). Fixed at the root; probe green after (24/24 notes, below).
2. **Contract-gap repair.** The import smoke caught `app.py` importing
   `DEFAULT_CONFIG_PATH`, which C1's `config.py` did not define — added the
   of-record path constant to `config.py` (config knowledge lives there).

## Local check output (required by the plan)

```
$ python -m ruff check qualityforge
All checks passed!

$ python /home/user/work/import_smoke.py   (TestClient, in-process)
ROUTES: [(['GET'], '/health'), (['POST'], '/evaluate')]
HEALTH: 200 {'status': 'ok'}
EVAL STATUS: 200
WIRE KEYS: ['note_id', 'criteria_version', 'overall_status', 'findings']
VERSION ECHO: 1.0.0
OVERALL: complete
  S-01 S present evidence='S: The patient reports a mild sore throat for two days.'
  S-02 S present evidence='S: The patient reports a mild sore throat for two days.'
  O-01 O present evidence='O: Vitals: temperature 37.1 C, pulse 80. The throat is red.'
  O-02 O present evidence='O: Vitals: temperature 37.1 C, pulse 80. The throat is red.'
  A-01 A present evidence='A: The findings fit a viral infection.'
  P-01 P present evidence='P: Rest and warm fluids are advised.'
  P-02 P present evidence='P: Rest and warm fluids are advised.'
  X-01 None present evidence='S: The patient reports a mild sore throat for two days.'
DETERMINISTIC: True
SEAM CONFIG VERSION: 1.0.0
SEAM FACTORY RESULT: evaluate qualityforge.generated.soap_evaluator.evaluator
SEAM EVAL: "complete"
```

The SEAM lines drive the loader exactly as the factory runner will
(`QUALITYFORGE_EVALUATOR_SPEC` naming
`qualityforge.generated.soap_evaluator:create_evaluator` with the of-record
config path) — the R1 seam fits.

## Supplementary scratch verification (outside the repo, no test file touched)

A probe ran all 24 labeled notes through `create_evaluator` against the
notes' embedded expectations: per-criterion statuses and overall_status
match on 24/24 notes, and every evidence span reproduces its raw slice
exactly (`RESULT failures=0 span_bugs=0`). This is authoring-time evidence
only; stage 5 owns conformance.
