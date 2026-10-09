# Stage 1 — Requirements (§7.1) — stage note

Run: `qf-run-1-soap-20261009T205906Z` (Factory Run 2) · Stage 1 of 8 · Role: Requirements Agent
Branch: `qualityforge/run-2-soap` (cut from `origin/main` at `1f3356d`)
Requirement input: `qualityforge/requirements/run-1-soap.md` — consumed as-is, verbatim (spec §8.1).
Of-record criteria: `qualityforge/workloads/soap-evaluator/criteria-v1.yaml` (v1.0.0).
Skill followed: `qualityforge/skills/acceptance-criteria/SKILL.md` (+ `completeness-criteria` policy skill).

## Artifacts in this directory

| File | What it is |
|---|---|
| `acceptance-criteria.yaml` | The Run 2 acceptance-criteria config — completeness-criteria shape per spec §8.2, validated against `qualityforge/schemas/completeness-criteria.schema.json` |
| `criteria-validation.txt` | Raw validator output for the config (unmodified stdout of the command below) |
| `requirements.md` | This stage note |

## Derivation (how the criteria were produced, per the skill)

Run 2 re-executes the Run 1 SOAP workload end-to-end to prove the factory. The
requirement input is byte-identical to Run 1's (`run-1-soap.md`, consumed
as-is), and the of-record criteria configuration v1.0.0 pins the completeness
rules, section-identification strategy (review R5), and evidence-span semantics
(review R3). The Requirements Agent therefore re-derives the criteria from the
requirement and lands them **semantically identical to the of-record v1.0.0**:

- `criteria_version` stays **"1.0.0"** — deliberately not bumped. Per spec §8.2
  and review R5 a version bump is required only when the criteria list or the
  section-detection strategy changes; neither changes for Run 2. No new
  criteria version was invented.
- **P-02 (plan-to-assessment) stays** in the criteria list.
- Evidence-span semantics and section detection are carried verbatim from the
  of-record file (they are versioned with the criteria, never hardcoded).

### Consistency evidence (commands actually run for this stage)

Semantic equality of the Run 2 config with the of-record config, by parsed YAML:

```
python3 -c "import yaml; run = yaml.safe_load(open('qualityforge/runs/qf-run-1-soap-20261009T205906Z/requirements/acceptance-criteria.yaml')); of = yaml.safe_load(open('qualityforge/workloads/soap-evaluator/criteria-v1.yaml')); print('parsed_equal:', run == of)"
→ parsed_equal: True
```

Schema validation (raw output captured to `criteria-validation.txt`, exit code 0):

```
python -m qualityforge.tools.validate criteria qualityforge/runs/qf-run-1-soap-20261009T205906Z/requirements/acceptance-criteria.yaml
→ OK: qualityforge/runs/qf-run-1-soap-20261009T205906Z/requirements/acceptance-criteria.yaml (criteria)
```

## Criteria (each with id, statement, check_type, source)

All eight criteria of the of-record v1.0.0 set, unchanged. `section` shown for
completeness; `source` is `requirement` for every criterion.

| id | statement | section | check_type | source |
|---|---|---|---|---|
| S-01 | Chief complaint is present in the Subjective section. | S | behavior_check | requirement |
| S-02 | History of present illness is present in the Subjective section. | S | behavior_check | requirement |
| O-01 | Vital signs are present in the Objective section. | O | behavior_check | requirement |
| O-02 | At least one exam or objective finding is present in the Objective section. | O | behavior_check | requirement |
| A-01 | At least one diagnosis or assessment statement is present in the Assessment section. | A | behavior_check | requirement |
| P-01 | At least one plan item is present in the Plan section. | P | behavior_check | requirement |
| P-02 | Plan items relate to a stated assessment. | P | behavior_check | requirement |
| X-01 | All four SOAP sections (Subjective, Objective, Assessment, Plan) are identifiable. | null | behavior_check | requirement |

Handoff (skill rule 5): these IDs are the linkage keys — the downstream
criterion-tests skill must yield exactly one test per criterion, repair
justifications cite criterion IDs, and generated-test commits carry
`criteria-ref: <criterion-id>` (review R2).

## Assumptions (explicit notes — nothing silently resolved)

Zero criteria carry `source: assumption`: the requirement yields verifiable
criteria with no unresolved ambiguity, matching Run 1's derivation (Run 1 stage
record: zero assumption entries, zero ambiguity flags). Two derivation-level
assumptions are recorded explicitly per skill rule 4 (§7.1):

1. **Assumption:** the of-record criteria set v1.0.0 remains the correct
   criteria set for Run 2, because the requirement input is byte-identical to
   Run 1's and no criteria or detection change is in scope for this run.
   *Note — what would change it:* an amended requirement file, or a driver
   instruction to change the criteria list or section-detection strategy; either
   would force a new `criteria_version` (spec §8.2, review R5) instead of an
   edit to this file.
2. **Assumption:** "clinical completeness" in the requirement means
   documentation completeness against documented rules (spec §2.2, §8.2) —
   software behavior on synthetic data, never clinical validity.
   *Note — what would change it:* a requirement or driver instruction extending
   scope to clinical judgment, which §2.2 and §11.2 forbid for this workload;
   that would be an escalation, not a criterion change.

## Epistemic status (skill non-negotiable, §2.2 / §8.2)

These criteria are **documentation-completeness rules, not clinical judgments**.
The evaluator they specify measures software behavior against stated
documentation rules on synthetic data (§11.1); they make no claim of clinical
validity.

## Gate self-check (§5.2 — evidence, not completion)

- [x] Config validates against `qualityforge/schemas/completeness-criteria.schema.json` — `criteria-validation.txt`, validator exit 0.
- [x] Every criterion has `id`, `statement`, `check_type`, `source` — 8/8 (table above; also enforced by the schema and the validator's semantic checks).
- [x] Assumptions carry an explicit `note` — zero `source: assumption` criteria; two derivation assumptions noted above with what would change them.
- [x] Of-record consistency — parsed YAML equal to `criteria-v1.yaml` v1.0.0; P-02 present; `criteria_version` unchanged.

Per `qualityforge/conventions/gates.md` (§5.2) this agent does **not** mark its
own completion: the driver verifies the gate against the pushed evidence and
writes the stage transition.
