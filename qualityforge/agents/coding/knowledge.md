# Knowledge module — Coding Agent

Grounding for spec §7.4 decisions. Load alongside prompt.md; the
`synthetic-data` skill carries the shared PHI rules.

## The §7.4 contract in practice

- Input is one task (architecture plan entry + implementation rules);
  output is a unified diff against the current implementation, in the
  smoke shape: `diff` text, `task_id` parity, `files_touched`.
- One task, one diff. Cross-task refactors are scope creep — the
  orchestrator sequences dependencies (§7.3), not the agent.

## Test files are not yours (review R2)

The Coding Agent never edits test files. The R2 guard
(`qualityforge/agents/rules.py::test_change_justified`) runs on any diff
touching them; a diff that changes an assertion fails it categorically —
there is no justification that legitimizes weakening an assertion (§11.4).

## §11.1 screen

`phi_scan` runs over diff content before a diff is accepted. The
corpus-only rule (§8.4) means literals in code and fixtures come from
the labeled synthetic dataset, never invented "realistic" values.

## Isolation (spec §7.5)

Diffs apply inside an isolated sandbox instance; nothing the Coding
Agent writes leaves the sandbox except as the diff artifact itself.
