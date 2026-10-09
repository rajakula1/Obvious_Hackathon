"""SOAP section identification (spec section 8.2, review R5).

Strategy comes from the criteria config — never hardcoded here:

1. Header markers first: a line whose leading text starts with one of the
   config's marker strings (case-insensitive) opens that section. Duplicate
   headers merge into one span per section (union across occurrences).
2. Documented fallback second: for a section with no marker, scan the note's
   non-marker lines for content matching the section's known data
   categories. The fallback attributes only what it can match confidently;
   an ambiguous note is reported as ``partial`` against the structure
   criterion (X-01), never guessed.

All offsets are zero-based, end-exclusive character offsets into the RAW
``note_text`` — no whitespace or unicode normalization anywhere (review R3).
"""

from __future__ import annotations

import re
from typing import NamedTuple

SECTION_ORDER = ("S", "O", "A", "P")

# Fallback evidence patterns, one per section (documented heuristic; the
# criteria config's fallback text names the data categories: complaint and
# history narrative; measurements and observed findings; diagnoses and
# assessments; ordered actions and follow-ups). Word-bounded so results are
# deterministic.
FALLBACK_PATTERNS: dict[str, re.Pattern[str]] = {
    # S: a complaint or history narrative — the patient's report.
    "S": re.compile(r"patient reports|patient describes|complains|\bsymptoms\b", re.I),
    # O: measurements (vitals) or observed findings.
    "O": re.compile(
        r"temperature|pulse|respirations|blood pressure|oxygen saturation|"
        r"\bexam\b|\bshows?\b|\bclear\b|swelling",
        re.I,
    ),
    # A: a diagnosis or assessment statement.
    "A": re.compile(r"diagnos|consistent with|fits? a\b|likely\b|assessment", re.I),
    # P: an ordered action or follow-up — imperative advice or a prescription.
    "P": re.compile(
        r"^\s*(rest|take|apply|use|begin|continue|schedule|avoid|return)\b|"
        r"advised|prescribed|recommend",
        re.I,
    ),
}

# Sentence run: a digit.dot.digit sequence ("37.2") is a decimal, not a
# boundary — the class consumes it as one unit so vital-sign numbers do not
# split mid-number (caught by the generated suite's unnormalized-note test).
_SENTENCE_RE = re.compile(r"(?:[^.!?]|\d\.\d)+(?:[.!?]+|$)")
_LINE_RE = re.compile(r"[^\n]+")


class SectionSpan(NamedTuple):
    """One section's identified content: a span of raw note_text plus its
    sentences with absolute offsets. An empty-but-marked section is still
    identified (text == ""); the dataset README's rule 5 makes that present
    structure with absent content. ``marker_start`` points at the opening
    marker (evidence for empty sections); it is ``None`` for fallback spans,
    whose first content line is the evidence instead."""

    start: int
    end: int
    text: str
    source: str  # "marker" | "fallback"
    marker_start: int | None = None

    @property
    def sentences(self) -> list[tuple[int, str]]:
        return sentences_with_offsets(self.text, self.start)


class SectionMap(NamedTuple):
    """The identification outcome for a note."""

    sections: dict[str, SectionSpan]
    markerless_note: bool  # no header marker anywhere (fallback-only note)
    any_markers: bool


def lines_with_offsets(text: str) -> list[tuple[int, str]]:
    """Every non-empty line with its start offset in the raw text."""
    return [(m.start(), m.group()) for m in _LINE_RE.finditer(text)]


def sentences_with_offsets(text: str, base: int) -> list[tuple[int, str]]:
    """Sentence-split a segment, keeping absolute offsets into the raw note.

    A final unpunctuated run counts as a sentence — that is exactly the
    truncated-content signal the corpus labels encode for ``partial``.
    """
    out: list[tuple[int, str]] = []
    for match in _SENTENCE_RE.finditer(text):
        chunk = match.group()
        if chunk.strip():
            out.append((base + match.start(), chunk))
    return out


def _marker_prefix_len(line: str, header_markers: dict[str, list[str]]) -> tuple[str, int] | None:
    """The section whose marker this line starts with, and the offset just
    past the marker (before consuming separator punctuation)."""
    stripped = line.lstrip()
    lead = len(line) - len(stripped)
    for section in SECTION_ORDER:
        for marker in sorted(header_markers.get(section, []), key=len, reverse=True):
            if stripped.lower().startswith(marker.lower()):
                return section, lead + len(marker)
    return None


def identify_sections(text: str, header_markers: dict[str, list[str]]) -> SectionMap:
    """Identify every section per the config strategy: markers, then fallback.

    Duplicate headers merge: a section's span runs from its first content
    character to the end of its last segment (the raw slice between them is
    part of the span, so offsets stay honest).
    """
    marker_spans: dict[str, list[tuple[int, int, int]]] = {}
    lines = lines_with_offsets(text)

    for index, (offset, line) in enumerate(lines):
        hit = _marker_prefix_len(line, header_markers)
        if hit is None:
            continue
        section, content_pos = hit
        marker_start = offset + (len(line) - len(line.lstrip()))
        # Content runs from just past the marker to the line before the next
        # marker line (or EOF).
        end = len(text)
        for next_index in range(index + 1, len(lines)):
            next_offset, next_line = lines[next_index]
            if _marker_prefix_len(next_line, header_markers) is not None:
                end = next_offset
                break
        start = min(offset + content_pos + _sep_len(line[content_pos:]), end)
        marker_spans.setdefault(section, []).append((start, end, marker_start))

    sections: dict[str, SectionSpan] = {}
    for section, spans in marker_spans.items():
        first_start, last_end = spans[0][0], spans[-1][1]
        sections[section] = SectionSpan(
            first_start, last_end, text[first_start:last_end], "marker", spans[0][2]
        )

    # Fallback: sections with no marker get their content attributed from
    # lines the marker sections do not already own (the config's documented
    # fallback rule).
    any_markers = bool(marker_spans)
    covered = [(start, end) for spans in marker_spans.values() for start, end, _marker in spans]

    def unclaimed(offset: int, line: str) -> bool:
        return not any(start <= offset < end for start, end in covered)

    for section in SECTION_ORDER:
        if section in sections:
            continue
        pattern = FALLBACK_PATTERNS[section]
        matched = [
            (offset, line)
            for offset, line in lines
            if unclaimed(offset, line) and pattern.search(line)
        ]
        if matched:
            start = matched[0][0]
            end = matched[-1][0] + len(matched[-1][1])
            sections[section] = SectionSpan(start, end, text[start:end], "fallback")

    return SectionMap(sections=sections, markerless_note=not any_markers, any_markers=any_markers)


def _sep_len(rest: str) -> int:
    """Separator characters (spaces, colons, dashes) between the marker and
    the content — part of the marker line, never part of the evidence."""
    stripped = rest.lstrip(" :-—")
    return len(rest) - len(stripped)
