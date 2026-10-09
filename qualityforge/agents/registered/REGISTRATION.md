# Registration record — QualityForge agents and skills

Task todo_eY0KFAHI · registered October 9, 2026 via the Obvious SDK.

## Skills — registered, completed

Registered with `obvious skills create` with the full SKILL.md attached as
content (status `completed` immediately). Raw registration responses are
stored beside this record; the repo sources remain the configuration of
truth.

| Skill | ID | Repo source | Raw response |
|---|---|---|---|
| `qualityforge-completeness-criteria` | `skl_OlzihvuIve79` | `../completeness-criteria/SKILL.md` | `completeness-criteria.json` |
| `qualityforge-synthetic-data` | `skl_d1YHA3MmCIQY` | `../synthetic-data/SKILL.md` | `synthetic-data.json` |
| `qualityforge-test-integrity` | `skl_a99oUqKd9Ck6` | `../test-integrity/SKILL.md` | `test-integrity.json` |
| `qualityforge-in-process-testing` | `skl_NidEUkQSC0yp` | `../in-process-testing/SKILL.md` | `in-process-testing.json` |
| `qualityforge-acceptance-criteria` | `skl_4xEqYpCw7KUu` | `../acceptance-criteria/SKILL.md` | `acceptance-criteria.json` |
| `qualityforge-criterion-tests` | `skl_XPTGhfztroSU` | `../criterion-tests/SKILL.md` | `criterion-tests.json` |
| `qualityforge-bounded-repair` | `skl_MrYIQGJ1myhZ` | `../bounded-repair/SKILL.md` | `bounded-repair.json` |
| `qualityforge-run-evidence` | `skl_EQzG9owWizl7` | `../run-evidence/SKILL.md` | `run-evidence.json` |
| `qualityforge-soap-note-completeness` | `skl_1ih3m36HEyM1` | `../soap-note-completeness/SKILL.md` | `soap-note-completeness.json` |

The five procedure skills (rows 5–9) were registered October 9, 2026
(18:36 UTC batch) under the skills-review task, with the full SKILL.md
attached as content like the four policy skills above.

Recreate reproducibly from the repo at any time:

```bash
cat qualityforge/skills/<skill>/SKILL.md | obvious skills create \
  --name=qualityforge-<skill> \
  --description="<see SKILL.md header>" \
  --triggers="<see SKILL.md header>" \
  --stdin=content
```

An earlier registration of `qualityforge-completeness-criteria`
(`skl_2NSf5g79r1Zv`) was created without content by a malformed CLI call and
was deleted before the clean registration above.

## Agents — registration-ready, not platform-registered

The SDK's `agents` surface for this thread is read-only (`agents list`,
`agents get`, `agents listKnowledge`, `agents listSkills`, …) — it exposes
**no agent creation action**. Registering the six agents as platform records
is therefore not possible from here; this is recorded as a blocker, not
silently claimed as done. What exists instead:

- Full registration-ready definitions in the repo:
  `qualityforge/agents/<agent>/agent.yaml` (identity, model hints, skills,
  knowledge) + `prompt.md` (system prompt source of truth) +
  `knowledge.md` (knowledge-module content).
- The canned §7 input/output smoke transcripts under each agent's
  `smoke/`, checked by `python -m qualityforge.tools.smoke` and
  `qualityforge/tests/test_smoke.py`.

When the platform exposes agent creation, register each agent from its
files — the definitions are already in the reproducible shape the
registration consumed for skills:

```bash
# Procedure once an agents.create action exists:
#   for each agent in requirements architecture coding testing debugging quality:
#     obvious agents create \
#       --name=qualityforge-<agent> \
#       --prompt-file=qualityforge/agents/<agent>/prompt.md \
#       --config=qualityforge/agents/<agent>/agent.yaml
#   then save each raw response under qualityforge/agents/registered/<agent>.json
```

The six definitions are complete and smoke-tested regardless of
registration status; the blocked step is only their platform-side
instantiation.
