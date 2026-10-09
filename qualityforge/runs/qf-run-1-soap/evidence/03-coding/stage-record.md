# Coding stage record — Factory Run 1 (§6 stage 4)

**Completed:** 2026-10-09T17:39:50Z
**Commit:** `21d84c0` — `feat: soap note completeness evaluator`
**Agent role:** Coding Agent (repository prompt `qualityforge/agents/coding-agent.md`)
**No manual code edits.** All code entered the branch through the Coding
Agent's file-tool writes; the derivation check below is verification only.

## What was generated

| Module | Responsibility |
|---|---|
| `models.py` | Request/response/evidence TypedDicts (§8.3); R3 span semantics in the type contract |
| `config.py` | Versioned criteria-config loader with structural validation (§8.2, R5) |
| `sections.py` | Section identification: config markers → documented fallback; duplicate-header union; absolute offsets into raw text |
| `evaluator.py` | S-01…P-02 criterion checks; truncation-partial S-02; P-02 generic-wellness relatedness heuristic; X-01 structure with ambiguous→partial |
| `app.py` | FastAPI `/evaluate` + `/health`; in-process by design (R6); defect-injection seam `QUALITYFORGE_EVALUATOR_SPEC` (§12.3, R1) |

## Design decisions recorded

1. **P-02 relatedness heuristic.** The corpus labels define relatedness
   outcomes but no mechanical rule; the evaluator documents its own: a plan
   item is unrelated when it matches a versioned generic-wellness marker list
   (multivitamin / vitamin / supplement / dental / walk briskly / stretch /
   sugary / hydration). Bare "exercise" is deliberately not a marker —
   activity *restrictions* ("avoid weight-bearing exercise") are
   condition-specific rest instructions. Known limit: lexical, not clinical
   reasoning. Recorded here and repeated in the evaluation report.
2. **Truncation partiality is scoped to S-02.** The corpus labels (soap-011)
   pin that a truncated history narrative is `partial` while the chief
   complaint (S-01) matched from complete sentences stays `present`. Other
   criteria are not degraded by a truncated tail they did not match.
3. **Fallback claims only unclaimed lines.** Marker-owned content is never
   re-attributed by the fallback heuristic (R5 discipline).
4. **The harness import is lazy and seam-only.** `app.py` imports
   `qualityforge.harness.loader` only when `QUALITYFORGE_EVALUATOR_SPEC` is
   set; the generated package is otherwise standalone (dependency direction:
   harness → generated).

## Self-derivation check (Coding Agent, pre-test)

The evaluator was run against all 24 labeled corpus notes (the label sweep
the Testing Agent will assert in the generated suite):

- First pass: 17/24. Two root causes:
  1. Marker-span starts used line-relative offsets (absolute offset missing),
     so non-first sections swallowed neighboring content — fixed in
     `sections.py` (`start = offset + content_pos + sep`).
  2. The history pattern lacked the duration fragment
     (`for <n> days|weeks|...`), and truncation partiality applied to every
     criterion instead of the narrative criterion — fixed in `evaluator.py`.
- After fixes and lint/format: **24/24 notes reproduce every criterion
  status and overall_status**; ruff check and format pass clean.

## Integrity

- Generated code: 6 files, 646 insertions, written via file tools by the
  Coding Agent role; commit `21d84c0` carries no other changes.
- Test-file tamper guards (R2) do not yet apply — no tests exist at this
  commit; the Testing Agent's manifest is the R2 trigger.
