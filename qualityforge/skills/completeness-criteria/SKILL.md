# QualityForge skill: Completeness criteria

**Spec:** Praxify QualityForge Specification §8.2 (review R3, R5)
**Consumed by:** Requirements, Architecture, Testing, and Quality agents
**Of-record config:** `workloads/soap-evaluator/criteria-v1.yaml` (v1.0.0)

## Purpose

How to author, version, and consume the machine-readable completeness-criteria
configuration. Criteria are **documented documentation-completeness rules, not
clinical judgments** (spec §8.2). The config file is the single source of truth:
the evaluator and every downstream agent consume the file, never a verbal or
hardcoded copy of its rules. That is what lets criteria change without
rewriting the evaluator.

## Workflow steps

1. Work from the of-record config file
   (`workloads/soap-evaluator/criteria-v1.yaml` — the §8.2 starting set,
   versioned); `schemas/completeness-criteria.example.yaml` is the schema
   sample. Never restate criteria from memory.
2. Every criterion carries: `id` matching `^[A-Z]+-[0-9]{2,}$` (e.g. `S-01`),
   a plain verifiable `statement`, a `section` (`S`/`O`/`A`/`P`/`null`),
   a `check_type` (`unit_test` | `schema_check` | `behavior_check`), and a
   `source` (`requirement` | `assumption`).
3. Record every assumption explicitly: a criterion with `source: assumption`
   must carry a `note` stating the assumption. This is enforced by the
   validator (spec §7.1).
4. Bump `criteria_version` (semver) on any criteria or detection-logic change.
   Changing detection logic is a criteria-version change, not an evaluator
   rewrite (review R5).
5. Evidence spans obey the pinned semantics in the config (review R3):
   zero-based **character** offsets into the exact raw `note_text` from the
   request, `end`-exclusive, **no** whitespace or unicode normalization.
   Never index a normalized copy.
6. Identify sections via the config's `header_markers` first; only if no
   marker matches, apply the documented `fallback` heuristic in the config.
   An ambiguous note is reported as `partial` against the Structure criterion
   (`X-01`) — never guessed.
7. Validate before any downstream use:
   `python -m qualityforge.tools.validate criteria <config.yaml|config.json>`

## Non-negotiable rules

- Criteria IDs are the linkage keys for generated tests, repair justifications,
  and `criteria-ref:` commit markers (review R2). Never invent, reuse, or
  renumber an ID casually.
- No clinical claims: criteria check documentation completeness against
  documented rules, nothing more (spec §2.2, §11.2).
- Passing these criteria verifies software behavior, not clinical correctness.
