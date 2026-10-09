"""Section identification for SOAP notes (stage-2 spec section 3, sections.py row).

Pure functions over (text, config) implementing the config's pinned detection
strategy (review R5): header markers first, the documented fallback second.

1. Header markers (config ``header_markers``) match case-insensitively as
   line-start prefixes. A section runs from its marker line to the next
   marker line of any section (or the end of the note), so duplicate headers
   unify: every occurrence of a section contributes its lines — the union the
   dataset README pins as rule 6.
2. The documented fallback second: for a section no header names, scan the
   note's unattributed text in document order for content matching the
   section's known data categories — the categories the config's fallback
   text names: S complaint and history narrative; O measurements and observed
   findings; A diagnoses and assessments; P ordered actions and follow-ups.
   Each missing section claims the first forward run of sentences its
   categories match, in S -> O -> A -> P order.

An ambiguous note — a section still missing while unattributable content
remains — surfaces as ``ambiguous`` so the structure criterion (X-01) answers
``partial`` instead of guessing (R5; the config fallback rule, verbatim).

Every offset this module emits is a zero-based character offset into the raw
text, end-exclusive (R3): ``text[start:end]`` reproduces the reported line or
sentence exactly. No normalization is ever applied to the text itself.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

SECTION_ORDER = ("S", "O", "A", "P")
STRATEGY = "header_markers_with_fallback"

LineAtOffset = tuple[int, str]
Span = tuple[int, int]

# The documented fallback's data categories (config fallback text) as named
# deterministic patterns. These implement documentation-completeness
# categories, not clinical judgments (spec section 2.2).
_COMPLAINT_PHRASES = (
    "the patient reports",
    "the patient describes",
    "the patient complains",
    "complains of",
    "presents with",
)
_SYMPTOM_TERMS = (
    "bump",
    "cough",
    "cut",
    "discomfort",
    "dizziness",
    "earache",
    "fatigue",
    "fever",
    "headache",
    "heartburn",
    "itchy",
    "limp",
    "nausea",
    "numbness",
    "pain",
    "rash",
    "sore throat",
    "soreness",
    "swelling",
    "tingling",
    "wound",
)
# A symptom term directly preceded by one of these prefixes is a negated
# mention ("No fever") and does not attribute content to a section.
_NEGATION_PREFIXES = ("no ", "not ", "without ", "denies ", "free of ")
_VITAL_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bvitals?\b",
        r"\bvital signs\b",
        r"\bpulse\b",
        r"\bblood pressure\b",
        r"\btemperature\b.*\d",
        r"\brespirations?\b",
        r"\boxygen saturation\b",
    )
)
_FINDING_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bexams?\b",
        r"\bexamination\b",
        r"\bshow(s|ed|ing)?\b",
        r"\bclear\b",
        r"\bred\b",
        r"\bswelling\b",
        r"\bswollen\b",
        r"\btender(ness)?\b",
        r"\bredness\b",
        r"\brash\b",
        r"\bpatch(y)?\b",
        r"\bplaques?\b",
        r"\blesion(s)?\b",
        r"\bwound\b",
        r"\bcut\b",
        r"\bbump\b",
        r"\bintact\b",
    )
)
_ASSESSMENT_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bdiagnosis\b",
        r"\bassessment\b",
        r"\bconsistent with\b",
        r"\blikely\b",
        r"\bfits?\b",
        r"\bsuspected\b",
        r"\bprobable\b",
    )
)
# Ordered actions and follow-ups: sentences that START with an action verb.
_ACTION_STARTERS = (
    "rest",
    "take",
    "apply",
    "use",
    "continue",
    "return",
    "avoid",
    "begin",
    "stop",
    "schedule",
    "elevate",
    "increase",
    "limit",
    "try",
    "seek",
    "switch",
    "keep",
    "wash",
    "rinse",
    "wear",
    "ice",
    "do not",
    "follow up",
    "come back",
)
_ADVISORY_PATTERNS = (re.compile(r"\b(is|are) advised\b"),)
_SENTENCE_END = re.compile(r"[.!?]")
_LETTER = re.compile(r"[a-z]")


@dataclass(frozen=True)
class SectionMap:
    """Sections identified in a note, per the config's detection strategy.

    ``spans`` maps a section to the document-order occurrence spans of every
    occurrence (header-derived or fallback-claimed) — the union the dataset
    README's duplicate-header rule pins. ``missing`` lists sections nothing
    identified; ``ambiguous`` is true when a section is missing while
    unattributable content remains, so the structure criterion answers
    ``partial`` rather than guessing. ``unclaimed`` holds the spans of that
    unattributable content — the textual basis of the ambiguity, usable as
    the structure finding's evidence.
    """

    spans: dict[str, list[Span]]
    missing: frozenset[str]
    ambiguous: bool
    unclaimed: tuple[Span, ...] = ()


def _lines(text: str, span: Span) -> list[LineAtOffset]:
    """Non-empty lines of ``text[span]`` as (offset of first char, line)."""
    start, end = span
    entries: list[LineAtOffset] = []
    cursor = start
    for raw in text[start:end].split("\n"):
        stripped = raw.strip()
        if stripped:
            entries.append((cursor + len(raw) - len(raw.lstrip()), stripped))
        cursor += len(raw) + 1
    return entries


def _sentences(text: str, span: Span) -> list[LineAtOffset]:
    """Sentences of ``text[span]`` as (offset of first char, sentence).

    Splits on sentence terminators; a period between digits (``37.1``) does
    not split. Slices stay R3-exact: offsets track stripped boundaries.
    """
    start, end = span
    entries: list[LineAtOffset] = []
    chunk: list[str] = []
    chunk_start = start
    for index, char in enumerate(text[start:end]):
        chunk.append(char)
        if _SENTENCE_END.match(char) is None:
            continue
        if char == "." and index > 0 and text[start + index - 1].isdigit():
            nxt = start + index + 1
            if nxt < end and text[nxt].isdigit():
                continue
        joined = "".join(chunk)
        stripped = joined.strip()
        if stripped:
            entries.append((chunk_start + len(joined) - len(joined.lstrip()), stripped))
        chunk = []
        chunk_start = start + index + 1
    joined = "".join(chunk)
    stripped = joined.strip()
    if stripped:
        entries.append((chunk_start + len(joined) - len(joined.lstrip()), stripped))
    return entries


def _section_of(line: str, header_markers: Mapping[str, Sequence[str]]) -> str | None:
    """The section whose marker this line starts with, or None."""
    lowered = line.lower()
    for section in SECTION_ORDER:
        if any(lowered.startswith(str(marker).lower()) for marker in header_markers[section]):
            return section
    return None


def is_marker_line(line: str, header_markers: Mapping[str, Sequence[str]]) -> bool:
    """True when the line is a bare header marker with no content after it."""
    lowered = line.lower()
    return any(
        lowered == str(marker).lower() for markers in header_markers.values() for marker in markers
    )


def _has_letter(line: str) -> bool:
    """Readable line: content with no letters (garble/noise) counts as absent."""
    return _LETTER.search(line.lower()) is not None


def lines_in(text: str, spans: Sequence[Span]) -> list[LineAtOffset]:
    """All non-empty lines across the spans, in document order (R3 offsets)."""
    return [entry for span in spans for entry in _lines(text, span)]


def content_lines(
    text: str,
    spans: Sequence[Span],
    header_markers: Mapping[str, Sequence[str]],
) -> list[LineAtOffset]:
    """Readable content lines of the section: not bare markers, not garble."""
    return [
        entry
        for entry in lines_in(text, spans)
        if _has_letter(entry[1]) and not is_marker_line(entry[1], header_markers)
    ]


def content_sentences(
    text: str,
    spans: Sequence[Span],
    header_markers: Mapping[str, Sequence[str]],
) -> list[LineAtOffset]:
    """Readable sentences of the section's content lines, in document order.

    Bare marker lines and garble are not content, so they yield no items —
    a bare ``P:`` marker is an empty plan, not a plan item.
    """
    items: list[LineAtOffset] = []
    for offset, line in content_lines(text, spans, header_markers):
        for relative, sentence in _sentences(line, (0, len(line))):
            items.append((offset + relative, sentence))
    return items


def _symptom_hit(sentence: str) -> bool:
    """A symptom term mention that is not negated in the immediate context."""
    lowered = sentence.lower()
    for term in _SYMPTOM_TERMS:
        at = lowered.find(term)
        while at != -1:
            # Keep the trailing space: the negation prefixes end with one.
            before = lowered[max(0, at - 10) : at]
            if not before.endswith(_NEGATION_PREFIXES):
                return True
            at = lowered.find(term, at + len(term))
    return False


def is_complaint(sentence: str) -> bool:
    """S data category: complaint and history narrative (the patient's report)."""
    lowered = sentence.lower()
    return any(phrase in lowered for phrase in _COMPLAINT_PHRASES) or _symptom_hit(sentence)


def is_vital(sentence: str) -> bool:
    """O data category: measurements — vitals with numeric context."""
    lowered = sentence.lower()
    return any(pattern.search(lowered) for pattern in _VITAL_PATTERNS)


def is_finding(sentence: str) -> bool:
    """O data category: observed findings on examination."""
    lowered = sentence.lower()
    return any(pattern.search(lowered) for pattern in _FINDING_PATTERNS)


def is_assessment(sentence: str) -> bool:
    """A data category: diagnoses and assessment statements."""
    lowered = sentence.lower()
    return any(pattern.search(lowered) for pattern in _ASSESSMENT_PATTERNS)


def is_action(sentence: str) -> bool:
    """P data category: ordered actions and follow-ups."""
    lowered = sentence.lower()
    if any(lowered.startswith(starter) for starter in _ACTION_STARTERS):
        return True
    return any(pattern.search(lowered) for pattern in _ADVISORY_PATTERNS)


def _matches_category(section: str, sentence: str) -> bool:
    """Does the sentence match the section's documented data categories?"""
    if section == "S":
        return is_complaint(sentence)
    if section == "O":
        return is_vital(sentence) or is_finding(sentence)
    if section == "A":
        return is_assessment(sentence)
    if section == "P":
        return is_action(sentence)
    return False


def _header_spans(
    text: str, header_markers: Mapping[str, Sequence[str]]
) -> dict[str, list[Span]]:
    """Occurrence spans per section from header markers alone.

    A section runs from its marker line to the next marker line of any
    section (or the end of the note), so duplicate headers unify and
    out-of-order sections keep their own spans. Preamble text before the
    first marker belongs to no section.
    """
    markers: list[tuple[int, str]] = []
    for offset, line in _lines(text, (0, len(text))):
        section = _section_of(line, header_markers)
        if section is not None:
            markers.append((offset, section))
    occurrences: dict[str, list[Span]] = {}
    for index, (offset, section) in enumerate(markers):
        end = markers[index + 1][0] if index + 1 < len(markers) else len(text)
        occurrences.setdefault(section, []).append((offset, end))
    return occurrences


def _fallback_claims(
    text: str,
    regions: Sequence[Span],
    missing: Sequence[str],
) -> tuple[dict[str, list[Span]], list[Span]]:
    """Attribute unattributed content to missing sections, in document order.

    Scans the unattributed sentences in document order; each missing section
    (in S -> O -> A -> P order) claims the first forward run of sentences its
    documented data categories match. Returns the claimed spans per section
    and the spans of sentences nothing claimed (the ambiguity evidence).
    """
    pool = [entry for region in regions for entry in _sentences(text, region)]
    claimed_spans: set[Span] = set()
    claims: dict[str, list[Span]] = {}
    cursor = 0
    for section in SECTION_ORDER:
        if section not in missing:
            continue
        index = cursor
        while index < len(pool) and not _matches_category(section, pool[index][1]):
            index += 1
        if index >= len(pool):
            continue
        run_end = index
        while run_end + 1 < len(pool) and _matches_category(section, pool[run_end + 1][1]):
            run_end += 1
        spans = [(pool[i][0], pool[i][0] + len(pool[i][1])) for i in range(index, run_end + 1)]
        claims[section] = spans
        claimed_spans.update(spans)
        cursor = run_end + 1
    unclaimed = [
        (offset, offset + len(sentence))
        for offset, sentence in pool
        if (offset, offset + len(sentence)) not in claimed_spans
    ]
    return claims, unclaimed


def identify_sections(text: str, section_detection: Mapping[str, object]) -> SectionMap:
    """Identify every SOAP section: header markers first, fallback second (R5)."""
    strategy = section_detection.get("strategy")
    if strategy != STRATEGY:
        raise ValueError(f"unsupported section_detection strategy: {strategy!r}")
    header_markers = section_detection["header_markers"]
    if not isinstance(header_markers, Mapping):
        raise ValueError("section_detection.header_markers must be a mapping")
    absent = [section for section in SECTION_ORDER if section not in header_markers]
    if absent:
        raise ValueError(f"section_detection.header_markers is missing sections: {absent}")

    occurrences = _header_spans(text, header_markers)

    # Unattributed text: everything outside every header occurrence span.
    regions: list[Span] = []
    cursor = 0
    for start, end in sorted(span for spans in occurrences.values() for span in spans):
        if start > cursor:
            regions.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < len(text):
        regions.append((cursor, len(text)))

    missing = frozenset(section for section in SECTION_ORDER if section not in occurrences)
    claims, unclaimed = _fallback_claims(text, regions, sorted(missing))

    spans = {section: list(occurrences[section]) for section in occurrences}
    for section, claimed in claims.items():
        spans[section] = claimed
    ambiguous = bool(missing - set(claims)) and any(
        _has_letter(text[start:end]) for start, end in unclaimed
    )
    return SectionMap(
        spans=spans,
        missing=frozenset(missing - set(claims)),
        ambiguous=ambiguous,
        unclaimed=tuple(unclaimed),
    )
