"""Mechanical enforcement of the factory's agent rules.

Pure functions backing three skills:

- test-integrity (spec section 7.7, review R2): justifications for
  test-file changes must link to a criterion ID.
- in-process-testing (review R6): generated API tests must not bind ports
  or open network connections.
- synthetic-data (spec section 11.1): a PHI-marker heuristic scanned over
  text before it enters run records, prompts, or demo material.

The checks are deliberately simple and deterministic because orchestrator
gates call them: a rule is enforced by code, never by an agent's word
(spec section 5.2, evidence over assertion).
"""

from __future__ import annotations

import re

CRITERION_ID_PATTERN = r"[A-Z]+-[0-9]{2,}"
CRITERION_ID_RE = re.compile(r"^" + CRITERION_ID_PATTERN + r"$")
CRITERIA_REF_RE = re.compile(r"criteria-ref:\s*(" + CRITERION_ID_PATTERN + r")")

# Review R6: forbidden patterns in generated test sources, as
# (regex, human-readable violation detail).
_IN_PROCESS_VIOLATIONS: tuple[tuple[str, str], ...] = (
    (r"\buvicorn\.run\(", "starts a real server (uvicorn.run)"),
    (r"\.\brun\(\s*host\s*=", "starts a real server (.run(host=...)"),
    (r"\bapp\.run\(", "starts a real server (app.run)"),
    (r"\bsocket\.socket\(", "binds a socket (socket.socket)"),
    (r"\.bind\(", "binds a socket (.bind)"),
    (r"\.listen\(", "listens on a socket (.listen)"),
    (r"\bHTTPServer\b", "hand-rolled server (HTTPServer)"),
    (r"\bWSGIServer\b", "hand-rolled server (WSGIServer)"),
    (r"\bhttp\.server\b", "hand-rolled server (http.server)"),
)
_LOOPBACK_CLIENT_RE = re.compile(r"\b(requests|httpx)\b[^\n]*\b(localhost|127\.0\.0\.1)\b")

# Spec section 11.1: PHI-marker heuristic, as (regex, detail). A backstop,
# not a guarantee - the primary control is template-only synthetic data.
_PHI_MARKERS: tuple[tuple[str, str], ...] = (
    (r"\bMRN\b\s*[:#]\s*\S+", "medical record number label"),
    (r"\bSSN\b", "SSN label"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN-like number"),
    (r"\bDOB\b\s*[:#]", "date-of-birth label"),
    (r"\bdate of birth\b", "date-of-birth phrase"),
    (r"\b\d{3}-\d{3}-\d{4}\b", "phone-like number"),
    (r"\(\d{3}\)\s*\d{3}-\d{4}", "phone-like number"),
)


def is_criterion_id(value: str) -> bool:
    """True if value matches the criterion ID format, e.g. ``S-01``."""
    return CRITERION_ID_RE.match(value) is not None


def justification_criterion_ids(justification: str) -> list[str]:
    """Unique criterion IDs cited as ``criteria-ref: <id>``, first-seen order."""
    seen: list[str] = []
    for match in CRITERIA_REF_RE.finditer(justification):
        if match.group(1) not in seen:
            seen.append(match.group(1))
    return seen


def test_change_justified(
    *,
    diff: str,
    justification: str | None,
    valid_criterion_ids: set[str] | None = None,
) -> bool:
    """Review R2 guard 3: may this proposed test-file change be applied?

    False unless the justification cites at least one criterion ID in
    ``criteria-ref: <id>`` form and every cited ID is a known criterion
    (when ``valid_criterion_ids`` is given). An empty diff is a malformed
    attempt record and is rejected.

    The guard verifies linkage only. Weakening or deleting an assertion to
    force a pass is barred absolutely (spec section 11.4) and no
    justification can make it legitimate; a wrong criterion is fixed by a
    versioned criteria change with a new manifest, not a quiet test edit.
    """
    if not diff.strip():
        return False
    if justification is None or not justification.strip():
        return False
    cited = justification_criterion_ids(justification)
    if not cited:
        return False
    if valid_criterion_ids is not None and not set(cited) <= valid_criterion_ids:
        return False
    return True


def in_process_test_violations(source: str) -> list[str]:
    """Forbidden patterns in a generated test source (review R6).

    Returns one human-readable entry per violation; an empty list means the
    source complies with the in-process testing rule. Presence of the
    in-process client itself (``TestClient``) is checked separately by the
    smoke harness, which knows whether the file is an API test file.
    """
    violations = [
        detail for pattern, detail in _IN_PROCESS_VIOLATIONS if re.search(pattern, source)
    ]
    if _LOOPBACK_CLIENT_RE.search(source):
        violations.append(
            "network client pointed at localhost/127.0.0.1 (use the in-process client)"
        )
    return list(dict.fromkeys(violations))


def phi_scan(text: str) -> list[str]:
    """PHI-marker heuristic over text (spec section 11.1).

    Returns one entry per marker hit; an empty list means no marker matched.
    A hit means: stop - do not upload, commit, or log the text; rewrite it
    synthetically or escalate to needs_human. Heuristic backstop only: the
    primary control is that factory data is template-generated (spec 8.4).
    """
    hits = [
        f"{detail}: {match.group(0)!r}"
        for pattern, detail in _PHI_MARKERS
        for match in re.finditer(pattern, text, re.IGNORECASE)
    ]
    return list(dict.fromkeys(hits))
