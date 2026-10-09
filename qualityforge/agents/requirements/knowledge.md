# Knowledge module — Requirements Agent

Grounding for spec §7.1 decisions. Load alongside prompt.md; the skills
(`completeness-criteria`, `synthetic-data`) carry the shared rules.

## The §7.1 contract in practice

- Output is a structured acceptance-criteria list in the of-record Run 1
  shape: `workloads/soap-evaluator/acceptance-criteria.yaml` (AC-01…AC-11).
  The downstream agents consume that file, not prose.
- `check_type` decides who verifies later: `unit_test` needs a named test in
  the generated suite; `schema_check` is validated structurally;
  `behavior_check` is observed on controlled inputs.

## Flags and assumptions (spec §7.1)

- A flag records something the requirement leaves undefined; an assumption
  (`source: assumption` + `note`) records a decision the agent made. Both
  surface in the run transcript. Neither is silent.
- Run 1's real flag: "supporting evidence" had no span semantics until
  review R3 pinned them (zero-based, end-exclusive character offsets into
  the raw `note_text`). The pinned semantics live in the criteria config.

## Epistemic status (spec §2.2, §8.2)

The criteria are documentation-completeness rules. Say so wherever the list
is presented. The evaluator's output never establishes clinical validity
(spec §8.5's disclaimer is downstream of this).

## ID linkage (review R2)

Criterion IDs minted here become the linkage keys for: test-manifest
`criteria_refs`, repair justifications, and `criteria-ref:` commit markers
on test-file changes. Renumbering after tests exist breaks the evidence
chain — don't.
