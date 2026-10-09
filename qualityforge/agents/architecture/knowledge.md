# Knowledge module — Architecture Agent

Grounding for spec §7.2 decisions. Load alongside prompt.md; the skills
(`completeness-criteria`, `in-process-testing`) carry the shared rules.

## The §7.2 contract in practice

- Input is the acceptance-criteria list; output is a technical
  specification plus an execution plan whose task IDs the Coding Agent
  mirrors exactly (task parity is checkable by the smoke harness).
- The coverage map is the §7.2 gate: every criterion ID from the input
  appears in the specification, mapped to a component and a test approach.
  A criterion without a component is a hole the factory builds over.

## Dependencies (spec §7.2)

Minimal and pinned. Run 1 needs: fastapi, pydantic, PyYAML — each pinned
`name==version` in the Dependencies section; the smoke checker fails an
unpinned line. Dev/test deps: pytest and httpx (TestClient transport).

## In-process testing statement (review R6)

The specification states the rule so the Testing Agent inherits it: API
tests run in-process through `TestClient(app)`; no bound ports, no live
server. This protects the §10 run budget and removes network flake.

## Determinism by construction (review R4, AC-05)

Response serialization uses a fixed key order so identical calls are
byte-identical. Design it here — retrofitting determinism is a rewrite.
