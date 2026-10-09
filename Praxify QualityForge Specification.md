# Praxify QualityForge: Specification

**Product:** Praxify QualityForge, an Autonomous Healthcare AI Feature Factory **Organization:** PraxifyAI **Target platform:** Obvious workspace (spec-driven, multi-agent orchestration) **Build window:** 8 to 10 hours **Status:** Draft v0.2 for build

## 1. Purpose

Praxify QualityForge is an autonomous software engineering system. It accepts a feature requirement for a MedScribe AI component, designs the solution, writes the implementation, generates tests, executes the code in a sandbox, diagnoses and fixes failures, and delivers a validated feature for human approval.

The product is the factory itself, not a healthcare application. Its first workload is a generated application: a SOAP note completeness evaluator. This ties the factory directly to PraxifyAI while showing that the system can build and verify software on its own.

QualityForge is built on the Obvious workspace. Obvious supplies orchestration, task gating, code execution, and integrations; QualityForge supplies the agents, skills, specifications, and test assets that make it a healthcare AI feature factory.

The critical demonstration is not that an AI writes code. It is that the system **executes** the code, detects real failures, makes corrections, and verifies the result without a human steering each step.

## 2. Goals and Non-Goals

### 2.1 Goals

1. Demonstrate an end-to-end autonomous loop: requirement → design → code → test → debug → verify → deliver.
2. Use real tools for repository operations, file modification, code execution, and test running, rather than agents describing those actions in text.
3. Produce a working, tested SOAP note completeness evaluator as the first generated application.
4. Record every run so each repair attempt and test result is inspectable.
5. Stop at a human approval gate before anything is treated as delivered.
6. Be reusable: a second requirement should run through the same factory with no changes to the factory itself.

### 2.2 Non-Goals

- Proving clinical validity. Passing software tests shows the code meets its stated criteria, not that the criteria are clinically correct.
- Processing real patient data. All inputs are synthetic.
- Auto-merging or auto-deploying into any production MedScribe AI environment.
- Building a full IDE, chat interface, or general-purpose coding assistant.
- Covering every healthcare workflow. Scope is one focused first workload.

## 3. Why QualityForge

The deciding requirement is an autonomous code factory, so the product must be the autonomous software engineering system itself, not a single healthcare application. QualityForge puts these capabilities at the core:

- Automatically writes and modifies code
- Executes tests and fixes failures
- Demonstrates an autonomous feedback loop, from failing test to verified fix
- Stays relevant to healthcare by validating healthcare AI applications
- Fits an 8 to 10 hour build with a focused first workload

## 4. Users and Stakeholders

| Role | Interest |
| --- | --- |
| Founder / architect (PraxifyAI) | Defines feature requirements, reviews and approves deliverables |
| Evaluators of the factory demo | Judge autonomy, code generation, testing, debugging, and end-to-end execution |
| Future healthcare buyers (CTOs, CMIOs) | Want evidence that AI features are tested and gated before release |

## 5. System Overview

### 5.1 End-to-End Flow

```
        Feature Requirement
                |
                v
       Requirements Agent
                |
                v
        Architecture Agent
                |
                v
         Task Orchestrator
                |
                v
          Coding Agent
                |
                v
       Isolated Code Sandbox
                |
                v
          Testing Agent
                |
          Tests Passing?
           /         \
         No           Yes
         |             |
         v             v
    Debugging      Code Quality
       Agent         Checks
         |             |
         +--> Retest   v
                 Human Review
                       |
                       v
              Feature Delivered
```

### 5.2 Design Principles

- **Spec first.** The specification is the product: acceptance criteria are precise and machine-readable so agents can build from them without supervision.
- **Deterministic orchestration.** The platform's task graph and dependency evaluation control flow; agents do the reasoning, not the sequencing.
- **Real tools, real execution.** Agents act through tools (read/write files, run commands, run tests). A claimed result without a tool-produced artifact does not count.
- **Isolation.** All generated code runs only in the sandbox.
- **Evidence over assertion.** Every stage emits a persisted artifact (spec, plan, diff, test output, report), and completion gates check that evidence rather than an agent's word.
- **Human last.** Delivery requires an explicit human approval.

### 5.3 Obvious Platform Mapping

QualityForge runs on the Obvious workspace instead of a custom runtime. Obvious supplies orchestration, state, gating, and code execution; QualityForge supplies the agents, skills, specifications, and test assets. The capabilities below come from [Obvious's public information page](https://www.obvious.ai/llm-info) (updated August 2026) and must be confirmed in the workspace during the first hour of the build.

| QualityForge component | Provided by Obvious | Built for QualityForge |
| --- | --- | --- |
| Task Orchestrator | Multi-agent orchestration, task delegation, dependency tracking, parallel threads | Task plan template, retry and iteration policy, escalation rules |
| Run state and completion | Initiative state in Postgres, mechanically evaluated dependency graphs, completion gates backed by database evidence | Evidence each gate requires: test report, quality report, approval record |
| Requirements, Architecture, Coding, Testing, Debugging, and Quality agents | Custom agents, agent modes, skills system | Agent instructions and healthcare skills (completeness criteria, synthetic data rules) |
| Isolated Code Sandbox | Code execution and compute, billed in credits | Test commands, resource limits, verified isolation settings |
| Delivery | GitHub integration | Pull request packaging and review notes, to a dedicated demo repository |
| Human Review Gate | Humans verify at checkpoints; roles and permissions on Team plans | Approve, request changes, and reject policy, plus the evidence package |
| Context and history | Persistent memory and shared project workspace | Criteria versions, decisions, and run history conventions |

Obvious bills model reasoning and code execution in credits. The same page lists Personal Pro at $200 per month with 235 credits, and extra credits at $0.85 each, so every run carries a credit budget.

## 6. Pipeline Stages

| Stage | Autonomous action | Expected output |
| --- | --- | --- |
| 1. Analyze | Interpret the feature requirement | Acceptance criteria |
| 2. Design | Define the API contract and data model | Technical specification |
| 3. Plan | Break implementation into tasks | Execution plan |
| 4. Generate | Write Python code | Working API |
| 5. Test | Generate and execute unit tests | Test results |
| 6. Debug | Analyze failures and modify code | Corrected implementation |
| 7. Verify | Rerun tests and perform code-quality checks | Verification report |
| 8. Deliver | Package the changes for human review | Pull request through the GitHub integration, or a reviewed code artifact |

## 7. Component Specifications

### 7.1 Requirements Agent

- **Input:** a free-text feature requirement.
- **Output:** a structured acceptance criteria list. Each criterion has an ID, a plain statement, and a verifiable check type (unit test, schema check, or behavior check).
- **Rules:** flag ambiguous or untestable statements instead of guessing, and record assumptions explicitly.

### 7.2 Architecture Agent

- **Input:** acceptance criteria.
- **Output:** a technical specification covering the API contract, data model, module layout, and dependencies.
- **Rules:** keep dependencies minimal and pinned; every acceptance criterion maps to at least one component.

### 7.3 Task Orchestrator

- Implemented with Obvious's native task orchestration: the plan becomes ordered tasks with explicit dependencies, and independent tasks run in parallel threads.
- **Controls:** maximum repair attempts per failure (default 3), maximum total iterations per run, a per-run time budget, and a per-run credit budget.
- **Escalation:** when limits are reached, the run stops with status `needs_human` and a failure summary. It never reports success it has not verified; completion is marked by evidence-backed gates, not by an agent's statement.

### 7.4 Coding Agent

- Writes and modifies files in the sandbox workspace through file tools.
- Works task by task from the plan and produces a diff for each task.

### 7.5 Isolated Code Sandbox

- Executes generated code and tests in the Obvious workspace's code execution environment, with no access to real data or credentials.
- Network and resource limits use the strictest options the workspace offers; the actual isolation settings are verified and recorded in the first hour, not assumed.
- Returns stdout, stderr, exit code, and test reports as artifacts.
- Execution consumes credits, so each run has a credit budget.

### 7.6 Testing Agent

- Generates unit tests from the acceptance criteria and executes them in the sandbox.
- Produces a structured result: tests run, passed, failed, and the failure messages and traces.
- **Rule:** tests must derive from acceptance criteria, not from reading the implementation alone, to avoid tests that only confirm what the code already does.

### 7.7 Debugging Agent

- Receives failing test output, the relevant code, and the criterion that failed.
- Proposes a minimal fix, applies it through the file tools, and triggers a retest.
- **Rules:** must not weaken or delete a test to make it pass; any change to a test requires a stated justification that links to a criterion; each attempt is logged.

### 7.8 Code Quality Checks

- Runs after all tests pass: linting, type checks, complexity limits, dependency checks, and a basic security scan.
- Produces a verification report. A failed quality check returns the run to the Debugging Agent within the same retry budget.

### 7.9 Human Review Gate

- Presents the plan, diffs, test results, repair history, and verification report in the workspace.
- Actions: **Approve**, **Request changes** (with notes that restart the relevant stage), or **Reject**.
- Nothing is marked delivered without an approval record; the delivery gate stays open until that record exists in the platform's task state.

## 8. First Workload: SOAP Note Completeness Evaluator

### 8.1 Requirement Given to the Factory

> Build a Python API that evaluates the clinical completeness of SOAP notes. It must identify missing sections, return structured findings with supporting evidence, generate unit tests, execute those tests, fix implementation defects, and produce an evaluation report.

### 8.2 Initial Completeness Criteria

Criteria are explicit, documented documentation-completeness rules, not clinical judgments. A starting set for the factory to refine:

- **Subjective:** chief complaint present; history of present illness present.
- **Objective:** vital signs present; at least one exam or objective finding present.
- **Assessment:** at least one diagnosis or assessment statement present.
- **Plan:** at least one plan item present; plan items relate to a stated assessment.
- **Structure:** all four SOAP sections identifiable.

The criteria live in a versioned configuration file so they can be changed without rewriting the evaluator.

### 8.3 Illustrative API Contract

The factory is expected to produce the final contract. The following is the target shape used to judge the result.

**Request:** `POST /evaluate`

```json
{
  "note_id": "string",
  "note_text": "string",
  "visit_type": "string (optional)"
}
```

**Response:**

```json
{
  "note_id": "string",
  "criteria_version": "string",
  "overall_status": "complete | incomplete",
  "findings": [
    {
      "criterion_id": "string",
      "section": "S | O | A | P",
      "status": "present | missing | partial",
      "evidence": [{ "start": 0, "end": 0, "text": "string" }],
      "message": "string"
    }
  ]
}
```

**Requirements:**

- Every `present` or `partial` finding includes supporting evidence tied to a span in the note.
- Every `missing` finding names the criterion that failed.
- Output is deterministic for the same input and criteria version.

### 8.4 Test Data

- A set of **synthetic** SOAP notes: some complete, some with sections removed or corrupted.
- Each synthetic note carries a labeled expected result so the factory's tests have a defined answer.
- No real patient data, and no data derived from real encounters.

### 8.5 Evaluation Report

Each run produces a report listing criteria tested, tests passed and failed, repair attempts, remaining known limitations, and the explicit statement that results reflect software correctness against stated criteria, not clinical validity.

## 9. Data Model

Obvious holds run state, tasks, dependencies, and gate status; QualityForge adds domain records as workspace artifacts. Every run remains a self-contained, reviewable record.

| Entity | Key fields | Intended home on Obvious |
| --- | --- | --- |
| Run | run\_id, requirement\_text, status, start/end time, iteration count, budget used | Obvious initiative and task state |
| Criterion | id, statement, check\_type, source (requirement or assumption) | Versioned workspace artifact |
| Task | id, description, assigned agent, status, dependencies | Obvious tasks and dependency graph |
| Artifact | id, run\_id, type (spec, diff, test\_output, report), content or path, created time | Workspace artifacts and repository files |
| Attempt | id, task\_id, failing test, change summary, result | Workspace artifact linked to the task |
| Approval | run\_id, reviewer, decision, notes, time | Completion-gate record on the delivery task |

Run statuses: `analyzing`, `designing`, `generating`, `testing`, `debugging`, `verifying`, `awaiting_approval`, `delivered`, `needs_human`, `rejected`.

## 10. Non-Functional Requirements

| Area | Requirement |
| --- | --- |
| Reliability | A run always ends in a defined status; no silent failures or infinite loops |
| Reproducibility | A run's artifacts and tool outputs are persisted so it can be reviewed afterward |
| Safety | All code executes in the sandbox with resource limits |
| Transparency | Each repair attempt records what failed, what changed, and the retest result |
| Performance | A first-workload run completes within the build window's demo budget, targeted at 15 minutes or less |
| Maintainability | Agents, tools, and criteria are configurable and separable |
| Cost | Each run carries a credit budget checked before execution; model reasoning and code execution consume credits |

## 11. Compliance and Safety Guardrails

1. **Synthetic data only.** No PHI enters the Obvious workspace, the sandbox, logs, or demo material.
2. **No clinical validity claims.** Reports and UI copy must state that results verify software behavior against documented criteria.
3. **Human approval required.** The factory never merges, deploys, or modifies production MedScribe AI systems. The GitHub integration connects only to a dedicated demo repository.
4. **No test tampering.** The Debugging Agent may not remove or weaken tests to force a pass; changes to tests need a justification linked to an acceptance criterion.
5. **Bounded autonomy.** Retry, iteration, time, and credit limits are enforced by the orchestration layer, not left to the agents.
6. **Public-facing content.** Anything published about the build shows the factory, its gates, and its results, and excludes proprietary MedScribe AI logic.
7. **Platform certifications do not replace data controls.** Obvious describes itself as HIPAA-ready, but that does not change rule 1: QualityForge uses synthetic data only.

## 12. Success Metrics

### 12.1 Demo Acceptance Criteria

The build is successful when a single run, started from the requirement in Section 8.1 with no manual code edits, shows all of the following:

- [ ] Acceptance criteria and a technical specification are generated and stored
- [ ] Code is written by the Coding Agent through file tools
- [ ] Unit tests are generated and executed in the sandbox
- [ ] At least one real test failure is detected and repaired by the Debugging Agent, with the attempt recorded
- [ ] All tests pass on the final retest and quality checks pass
- [ ] The run stops at the human review gate with a complete evidence package
- [ ] The evaluation report is produced with the required disclaimer

### 12.2 Quantitative Measures

| Metric | Target |
| --- | --- |
| End-to-end run completes without manual code edits | Yes |
| Test pass rate at delivery | 100% of generated tests |
| Acceptance criteria covered by at least one test | 100% |
| Repair attempts used per failure | 3 or fewer |
| Runs ending in an undefined state | 0 |

### 12.3 Strongly Recommended Extension

To show the tests are meaningful rather than self-confirming, add a **defect-injection check**: introduce known defects into a good implementation (for example, remove a section check) and confirm the generated tests catch them. Report the share of injected defects detected.

## 13. Future Workloads

After the first workload works, give the factory a second MedScribe AI feature requirement without changing the factory itself. Each new workload is a new specification run through the same pipeline, which shows QualityForge is a reusable engineering system rather than a one-off build.

Constraints for any later workload: synthetic data only, publicly available reference criteria only, and outputs framed as software verified against stated criteria.

## 14. Minimal User Interface

Use the Obvious workspace as the interface wherever it already shows tasks, artifacts, and approvals. Build a custom single-page view only for what it does not show:

- The requirement and current run status
- The task plan with per-task status
- Generated files and diffs
- Test results by run iteration
- The repair attempt history
- The approval panel (Approve, Request changes, Reject)

## 15. Build Plan (8 to 10 Hours)

| Hours | Focus | Deliverable |
| --- | --- | --- |
| 0 to 1 | Workspace setup and platform verification: confirm agent, task-gate, code-execution, and GitHub capabilities, and write the requirement and acceptance criteria as a precise, machine-readable spec | Verified capability list, spec, and criteria |
| 1 to 2 | Orchestration configuration: task plan template, dependency graph, retry and credit budgets, completion gates | Orchestration setup with evidence-backed gates |
| 2 to 4 | Agents and skills: Requirements, Architecture, Coding, Testing, Debugging, and Quality agents, plus a completeness-criteria skill and the synthetic note set | Configured agents, skills, and synthetic data |
| 4 to 6 | Test execution, repair loop, and quality checks wired as gates | Working repair loop with logged attempts |
| 6 to 7 | Human approval gate and GitHub delivery to a demo repository | Approval gate and pull request packaging |
| 7 to 8 | Defect-injection check and evaluation report | Detection results and report |
| 8 to 10 | End-to-end demo run, workspace view refinements, and rehearsal | Recorded demo run |

**Cut order if time runs short:** polish the UI first, then the defect-injection extension, then breadth of completeness criteria. Do not cut the sandbox, the repair loop, or the human gate, because they are the core of the demonstration.

## 16. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Generated tests only confirm the code's current behavior | Derive tests from acceptance criteria; run the defect-injection check |
| Debugging Agent loops or thrashes | Hard retry and iteration limits in the orchestrator; escalate to `needs_human` |
| Debugging Agent weakens tests to pass | Test-change rule with justification and review visibility |
| Scope grows beyond the build window | Fixed first workload; defined cut order |
| Overstating clinical value | Required disclaimer in reports and UI; synthetic data only |
| Platform capabilities differ from assumptions | Verify agent, task-gate, code-execution, and GitHub support in the first hour, and keep the specification platform-neutral so a fallback exists |
| Credit use exceeds the plan | Per-run credit budget, a focused first workload, and a usage check after each run |
| GitHub integration reaches real repositories | Connect only a dedicated demo repository with no access to production code |
| Completion gates pass on agent claims instead of evidence | Define each gate by a required artifact (test report, quality report, approval record), not a status message |

## 17. Assumptions and Open Questions

**Assumptions**

- Obvious provides the orchestration, custom agents, skills, task gating, code execution, and GitHub integration described on its public information page; each is verified in the first hour of the build.
- The selected Obvious plan includes enough credits for several end-to-end runs; this is not yet confirmed.
- Python is the implementation language for generated applications.
- A single reviewer (the founder) acts as the human approval gate for the demo.

**Open questions**

- Which agent mode (thinking speed and depth) should each agent use, and should the coding and review agents differ?
- Should the final artifact be a pull request in a dedicated demo repository (the default in this spec) or a packaged review bundle?
- Which completeness criteria belong in the first version beyond the starting set in Section 8.2?
- What is the exact demo audience and format (live run, recording, or both)?
