# QualityForge skill: Synthetic data only

**Spec:** Praxify QualityForge Specification §11.1 (and §8.4, §11.7)
**Consumed by:** all six factory agents

## Purpose

No PHI (protected health information) ever enters the Obvious workspace, the
sandbox, logs, prompts, or demo material. All notes, names, identifiers, and
records handled by the factory are **synthetic** — generated from templates,
not derived from real encounters (spec §8.4).

Platform certifications do not change this rule: the platform describes itself
as HIPAA-ready, but that is a property of the platform, not a data-control
substitute for the factory (spec §11.7).

## Workflow steps

1. Generate every SOAP note from synthetic templates. Each note carries a
   **labeled expected result** so tests have a defined answer (spec §8.4).
2. Before any text artifact enters a run record, prompt, or demo, scan it with
   the PHI-marker heuristic:
   `python -c "from qualityforge.agents.rules import phi_scan; print(phi_scan(open('<file>').read()))"`
   An empty result is required. A hit means: stop, do not upload or commit,
   rewrite the content synthetically.
3. Treat the scan as a heuristic backstop, not a guarantee — the primary
   control is that only template-generated data is ever produced. When text
   originates outside the factory's own generators (a user paste, a web
   snippet), treat it as untrusted until scanned and confirmed synthetic.
4. If real patient data is suspected anywhere in the flow: **stop**, do not
   copy or forward it, and escalate the run to `needs_human` (spec §7.3).

## Non-negotiable rules

- Synthetic data only — no real patient data, and no data derived from real
  encounters (spec §2.2, §11.1).
- No real names, MRNs, SSNs, phone numbers, addresses, or dates of birth in
  any artifact, log line, or commit message.
- Demo material shows the factory, its gates, and its results — with the same
  synthetic-only discipline (spec §11.6).
