# QualityForge skill: Test integrity (no test tampering)

**Spec:** Praxify QualityForge Specification §7.7, §11.4 (review R2)
**Consumed by:** Debugging, Testing, and Quality agents

## Purpose

The Debugging Agent may never remove or weaken a test to force a pass. The
rule is **mechanized**, not a promise (review R2): a recorded manifest, a
Verify-gate re-hash, and criterion-linked justifications. Under retry pressure
the tempting shortcut — editing the test instead of the code — is the single
most damaging failure this factory can exhibit; these guards make it fail
loudly instead of silently.

## The three mechanical guards

1. **Manifest.** When the Testing Agent finalizes tests, the orchestrator
   records a manifest artifact — one entry per test file: repository-relative
   path + SHA-256 (schema: `qualityforge/schemas/test-manifest.schema.json`).
2. **Re-hash.** The Verify gate (spec §7.8) recomputes every digest before the
   quality report is issued; any drift fails the gate:
   `python -m qualityforge.tools.validate manifest <manifest.json> --repo-root .`
3. **Justification.** Any change to a generated test file requires a stated
   justification that links the change to an acceptance criterion ID. At the
   PR layer, commits touching generated test files carry
   `criteria-ref: <criterion-id>` in the message — a one-line CI check.

## Workflow steps (Debugging Agent)

1. Receive the failing test output, the relevant code, and the failed
   criterion. Diagnose against the **criterion**, not against the test's
   convenience.
2. Default to fixing the **implementation**. A test change is the exception,
   never the path of least resistance.
3. If the fix touches a test file, STOP and run
   `qualityforge.agents.rules.test_change_justified` with the proposed
   justification: it returns False unless the justification cites a valid
   criterion ID (format `criteria-ref: S-01`). A rejected change must not be
   applied — log the attempt as rejected and fix the implementation instead.
4. Weakening or deleting an assertion to make a test pass is **never**
   justifiable. If the criterion itself is wrong, that is a criteria-version
   change (see the completeness-criteria skill) with a new manifest — not a
   quiet test edit.
5. Log every attempt: what failed, what changed, the retest result (spec §7.7).

## Non-negotiable rules

- No test may be removed, weakened, or skipped to force a pass (spec §11.4).
- Every test-file change carries a justification linked to a criterion ID.
- Digest drift on a manifest entry fails the Verify gate — tampering cannot
  pass silently.
