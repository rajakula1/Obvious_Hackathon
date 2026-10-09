# Synthetic SOAP notes dataset (spec section 8.4)

Labeled test corpus for the Run 1 SOAP-note completeness evaluator. Every note
is invented from scratch for this dataset: **no real patient data and nothing
derived from real encounters** (spec section 11.1). A PHI-pattern scan over
every string of every record is part of validation and must always return zero
hits.

## Layout

| Path | Contents |
|---|---|
| `notes/soap-001.json` … `soap-024.json` | One note record per file: `note_id`, `category`, optional `visit_type`, `note_text`, `expected` (labeled result), `rationale` |
| `corpus.manifest.json` | Corpus metadata: criteria version the labels align to, note count, category counts, per-note SHA-256 (re-hashed at validation, like the R2 test manifest) |

The request a test sends is `note_text` (+ `visit_type` when present); the
label is the defined answer the generated tests assert against.

## Label semantics — the rules that make an expected result decidable

Labels use the response vocabulary of spec section 8.3: per-criterion
`present | missing | partial`, and `overall_status` of `complete | incomplete`.
One expected finding per criterion of the of-record criteria config
(`../criteria-v1.yaml`, version 1.0.0), listed in config order.

1. **present** — the criterion's required content is identifiable and complete
   in its section.
2. **missing** — the section is absent or unidentifiable, the section is empty,
   or the required content is absent. Content that is present but unreadable
   (corrupted/garbled) counts as absent.
3. **partial** — the required content is present but incomplete (truncated
   mid-sentence), or — for P-02 only — some but not all plan items relate to a
   stated assessment.
4. **P-02 relatedness**: all plan items relate to a stated assessment →
   `present`; some do → `partial`; none do, or no assessment is stated, or the
   Plan section is absent/empty → `missing`.
5. **X-01 structure**: a section is *identifiable* when a header marker from
   the config names it, or the documented fallback confidently attributes
   content to it. An empty-but-present header still identifies its section, so
   X-01 is `present` while the section's content criteria are `missing` (rule 2). Fallback cannot confidently
   attribute content (ambiguous note) → X-01
   `partial`, exactly as the criteria config's fallback rule states.
6. **Duplicate headers**: findings consider the union of all occurrences of a
   section (soap-016 completes across two Subjective headers).
7. **overall_status**: `complete` if and only if every criterion is `present`.
8. **Evidence spans are deliberately not labeled.** The criteria config pins
   span semantics (review R3); spans are the evaluator's output to compute and
   tests verify their presence and validity, not a second copy of the truth
   stored here.

## Corpus composition (24 notes)

| Category | IDs | Exercises |
|---|---|---|
| `complete` | soap-001…004 | all marker styles (`S:`, `Subjective:`, `Subjective -`), verbose and terse |
| `missing_section` | soap-005…008 | each individual section removed once |
| `empty_section` | soap-009…010 | header present, no content (S empty; P empty) |
| `partial_content` | soap-011…015 | truncated S; garbled O; no chief complaint; no vitals; no exam finding |
| `duplicate_headers` | soap-016…017 | union across duplicates; duplicate P with mixed relatedness |
| `plan_unrelated` | soap-018…019 | all plan items unrelated; mixed relatedness |
| `fallback_detection` | soap-020…021 | ambiguous free text (X-01 partial); headerless but well-ordered (fallback pass) |
| `layout_variation` | soap-022…024 | preamble before headers; out-of-order sections; bare headers with no content |

## Validation

From the repository root:

```bash
python -m qualityforge.tools.validate_dataset                       # data/ + criteria-v1.yaml
python -m qualityforge.tools.validate_dataset --data DIR --criteria CONFIG.yaml
```

Checks: record structure and field types, unique filename-matching note IDs,
labels covering exactly the criteria config IDs in config order with valid
statuses, overall-status consistency, corpus size (20–30, spec section 8.4),
manifest counts and per-note SHA-256 re-hash, and a zero-hit PHI-pattern scan
(DOB/MRN/SSN labels and numbers, phones, emails, digit runs, absolute dates in
numeric or month-name form, name-shaped values after a `patient:` label).

Corpus authoring policy that keeps the scan at zero: no names (subjects are
"the patient"), only relative time references ("two days ago"), no contact
details or identifiers. Any corpus edit requires re-recording
`corpus.manifest.json` — the re-hash fails loudly otherwise.

The pytest suite (`qualityforge/tests/test_validate_dataset.py`) runs the same
checks in CI.
