# Knowledge module — Quality Agent

Grounding for spec §7.8 decisions. Load alongside prompt.md; the skills
(`completeness-criteria`, `test-integrity`) carry the shared rules.

## The §7.8 contract in practice

- Input is the run transcript; output is the quality report: one check
  result per §7.8 item, each with its evidence reference. `passed: false`
  on any check routes the run back to Debugging via the orchestrator —
  the report never fixes anything itself.

## The five checks

1. Every criterion has evidence meeting its `check_type`.
2. Test-manifest re-hash: recorded SHA-256 digests recomputed over the
   current files; any drift fails the gate (§11.4, review R2). This is
   the mechanical no-test-tampering check — `recheck_manifest_hashes`.
3. Criteria-coverage set: every criterion ID appears in at least one
   passed test (`derived_from` linkage, AC-06).
4. Attempt records complete: every failure has a §7.7 record.
5. §8.5 disclaimer present in the evaluation report — the software/
   clinical-validity line is part of the deliverable, not a footnote.

## The handoff (§7.9)

On `passed: true`, the run stops at `awaiting_approval` and the report
becomes `report_to_human`. Approval is a gate record with decider and
timestamp (§9) — the Quality Agent never marks the run complete.
