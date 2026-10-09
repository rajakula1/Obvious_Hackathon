# QualityForge skill: Run evidence and approval gates

**Spec:** Praxify QualityForge Specification §5.2, §6, §7.8, §7.9 (and §9, §12.2; review R8 writer rule)
**Consumed by:** Testing and Quality agents (Verifier role); the human gate reads its reports

## Purpose

A gate checks a **persisted artifact**, never an agent's word (§5.2). This
skill defines the three Verifier reports, the exact fields a gate reads, and
the approval-record semantics — so "pass" always means a status field in a
file, not a sentence in a log.

## The three reports (artifact type `report`, §9)

1. **Test report** (Testing Agent, stages 5 and 7): `tests_run`, `passed`,
   `failed`, per-test status with messages and traces, criteria coverage. The
   gate reads `failed == 0` and coverage naming every criterion id.
2. **Quality report** (Quality Agent, stage 7): lint, types, complexity,
   dependency, and security check results, each pass/fail, plus the
   test-manifest re-hash outcome. The gate reads every check passing and
   `manifest_rehash: match` (R2):
   `python -m qualityforge.tools.validate manifest <manifest> --repo-root .`
3. **Evaluation report** (Quality Agent, stage 8): per-criterion results on
   the labeled corpus, `overall_status`, and the `criteria_version` the run
   evaluated against — plus the explicit statement that results reflect
   software correctness against stated criteria, not clinical validity (§8.5).
   The gate reads 100% of criteria passing (§12.2).

Write each report into its stage directory (`runs/<run-id>/07-verify/`,
`runs/<run-id>/08-deliver/`). A report the gate cannot find is a failed gate,
whatever anyone believes.

## Approval and terminal states

- The run holds at `awaiting_approval` (§7.9) until an **Approval record**
  exists on the delivery gate. Approval is a record, not prose: no agent
  sentence, log quote, diff summary, or screenshot marks delivery.
- Terminal statuses (`delivered`, `rejected`, `needs_human`) are written **only
  by the runbook** (R8). Agents request; the runbook writes; the status enum
  (`qualityforge/run_status.py`) is closed (§12.2: runs ending in an undefined
  state — zero, by construction).

## Non-negotiable rules

- Gates advance on status fields in persisted files — never on claims.
- No agent writes a terminal status or an approval.
- A missing artifact fails the gate; it is never replaced by an explanation.
