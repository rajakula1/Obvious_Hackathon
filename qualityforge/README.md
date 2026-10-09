# QualityForge factory conventions

Scaffold of the Praxify QualityForge factory. Spec: `../Praxify QualityForge
Specification.md` (Draft v0.2); amendments: the pinned review, recommendations
R1–R8. The spec is the product (§5.2): agents and the runbook consume these
files directly, not a verbal copy of them.

Generated workloads and run artifacts land here too (`workloads/`, `runs/` —
see `conventions/gates.md` for the layout).

## Layout

| Path | Contents |
|---|---|
| `run_status.py` | Run-status enum: the ten statuses of spec §9, with stage / gate / terminal groupings |
| `conventions/gates.md` | Evidence and gate conventions for every §6 stage |
| `schemas/completeness-criteria.schema.json` | Versioned completeness-criteria config schema (§8.2) |
| `schemas/completeness-criteria.example.yaml` | The §8.2 starting set as a validating sample |
| `schemas/test-manifest.schema.json` | Test-manifest format: path + SHA-256 per test file (R2) |
| `tools/validate.py` | Validator: schema + semantic checks, manifest re-hash (R2 Verify gate) |
| `tools/validate_dataset.py` | Dataset validator: label well-formedness, criteria-config alignment, manifest re-hash, zero-hit PHI scan (§8.4, §11.1) |
| `workloads/soap-evaluator/` | Run 1 workload spec assets: machine-readable acceptance criteria (`acceptance-criteria.yaml`, §7.1) and criteria config v1 (`criteria-v1.yaml`, §8.2) |
| `workloads/soap-evaluator/data/` | Synthetic SOAP notes corpus: 24 labeled notes + corpus manifest + label semantics (§8.4) |
| `requirements/run-1-soap.md` | Run 1 requirement input, verbatim from spec §8.1 |
| `factory/run.js` | Runbook (R8): instantiates the run task DAG with budgets and evidence gates; terminal-status writer restricted to the §9 enum |
| `tests/` | pytest suite covering the enum, the validator, the workload spec assets, and the dataset |

## Convention → spec map

| Convention | Defined by | Spec section | Review rec |
|---|---|---|---|
| Ten run statuses | `run_status.py` | §9 (groupings: §6, §7.3, §7.9) | R8 |
| Only the runbook writes terminal statuses | `conventions/gates.md` | §12.2, §7.3 | R8 |
| Required evidence per pipeline stage | `conventions/gates.md` | §6, §5.2 | — |
| Artifact-type vocabulary (`spec`, `diff`, `test_output`, `report`) | `conventions/gates.md` | §9 | — |
| Approval is a gate record, not an artifact | `conventions/gates.md` | §7.9, §9 | — |
| Versioned criteria config schema | `schemas/completeness-criteria.schema.json` | §8.2, §7.1, §9 | R5 |
| Evidence-span semantics pinned in the config | `schemas/completeness-criteria.schema.json` | §8.3 | R3 |
| Section-detection strategy in the config | `schemas/completeness-criteria.schema.json` | §8.2 | R5 |
| Test manifest: path + SHA-256 per test file | `schemas/test-manifest.schema.json` | §11.4, §7.7 | R2 |
| Run 1 acceptance criteria + criteria config v1 | `workloads/soap-evaluator/` | §7.1, §8.1–8.3, §12.1 | R1, R3, R4, R5 |
| Verify-gate re-hash of the manifest | `tools/validate.py` | §7.8 | R2 |
| `criteria-ref:` commit rule for test files | `conventions/gates.md` | §11.4 | R2 |
| Runbook instantiates the run DAG; only it writes run statuses, terminal ones restricted to §9 | `factory/run.js` | §5.3, §6, §7.3, §9, §10, §12.2 | R8 |

## Usage

From the repository root:

```bash
# test suite
python -m pytest qualityforge/

# validate a completeness-criteria config (YAML or JSON)
python -m qualityforge.tools.validate criteria qualityforge/schemas/completeness-criteria.example.yaml

# validate a test manifest, re-hashing every recorded test file (R2 Verify gate)
python -m qualityforge.tools.validate manifest runs/<run_id>/05-test/test-manifest.json --repo-root .
```

Exit codes: `0` valid, `1` invalid, `2` usage or I/O error.

## CI

`.github/workflows/ci.yml` (repo root) runs `ruff check qualityforge` and
`python -m pytest qualityforge/` on pushes and pull requests. Dependencies are
pinned in `qualityforge/requirements-dev.txt` (spec §7.2: minimal and pinned).
