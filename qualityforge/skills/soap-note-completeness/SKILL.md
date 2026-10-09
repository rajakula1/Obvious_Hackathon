# QualityForge skill: SOAP note completeness (workload)

**Spec:** Praxify QualityForge Specification §8.1–8.5 (reviews R3, R5; §2.2, §11.1)
**Consumed by:** Requirements, Architecture, and Coding agents (Spec and Builder roles)

## Purpose

The workload rules for the SOAP-note completeness evaluator (Run 1): where the
of-record criteria live, how section detection and evidence spans behave, what
the fixtures are, and the disclaimer the product carries. Everything here is
documentation completeness of SOAP notes — **never clinical validity** (§2.2).

## Workflow steps (the of-record rules)

1. **Criteria config is the single source of truth:**
   `qualityforge/workloads/soap-evaluator/criteria-v1.yaml` (v1.0.0). The
   evaluator consumes this file, never a hardcoded copy of the rules; any
   change to the criteria list or the detection strategy is a **new
   `criteria_version`** (bump the file), not an evaluator rewrite (§8.2). The
   shipped v1.0.0 is the §8.2 starting set including plan-to-assessment
   relatedness (`P-02`); the config of record governs.
2. **Section detection** (R5, pinned in the config):
   `header_markers_with_fallback` — header markers matched case-insensitively
   as line-start prefixes (`S:`, `Subjective:`, `Subjective -`, and the O/A/P
   equivalents); the documented fallback scans the note in document order for
   each section's known content categories. An ambiguous note reports
   `partial` against the structure criterion — never guessed.
3. **Evidence spans** (R3, pinned in the config): zero-based character offsets
   into the exact raw `note_text` string from the request, end-exclusive, no
   normalization: `note_text[start:end]` must reproduce the reported evidence
   text.
4. **Fixtures:** the labeled synthetic corpus
   `qualityforge/workloads/soap-evaluator/data/` — 24 notes with expected
   results plus `corpus.manifest.json` (per-note SHA-256, re-hashed at
   validation). Labels are decidable via the dataset README's semantics. Any
   corpus for this workload must include at minimum: two complete notes, one
   missing each section, one broken or garbled header, one partial-content
   note — the shipped corpus exceeds this mix. Any corpus edit re-records the
   manifest; the re-hash fails loudly otherwise. Synthetic notes only — no
   PHI, ever (§11.1, synthetic-data skill).
5. **Disclaimer:** the evaluator reports documentation completeness only. Its
   evaluation report carries the explicit statement that results reflect
   software correctness against stated criteria, not clinical validity
   (§8.5); criteria, findings, and UI copy make no clinical claim of any kind.

## Non-negotiable rules

- The config file governs; nothing hardcodes the rules — that is what
  criteria versions are for.
- Spans must reproduce evidence text exactly: no normalization, no guessing.
- No clinical judgments in criteria, findings, or reports (§2.2).
- Synthetic notes only; the factory never sees real patient data (§11.1).
