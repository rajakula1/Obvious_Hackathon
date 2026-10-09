"""Wiring locks for the QualityForge skill layer.

The five-skill expansion (spec: QualityForge five-skill expansion and factory
re-run) is wiring: a hand-edited agent.yaml, a skill without a platform
registration, or a prompt that drifted from its agent config must fail CI here
instead of surfacing in review or mid-run. Locks:

1. every ``skills/<slug>/`` directory has a ``registered/<slug>.json`` and vice versa;
2. every ``agent.yaml`` skills entry resolves to a registered ``SKILL.md``;
3. each agent's prompt names exactly the skills its yaml lists;
4. every SKILL.md follows the file convention (header block + required sections);
5. the six agents' skill sets match the spec wiring matrix exactly.
"""

import json
import re
from pathlib import Path

import pytest
import yaml

QUALITYFORGE = Path(__file__).resolve().parents[1]
SKILLS_DIR = QUALITYFORGE / "skills"
REGISTERED_DIR = SKILLS_DIR / "registered"
AGENTS_DIR = QUALITYFORGE / "agents"

AGENTS = ("requirements", "architecture", "coding", "testing", "debugging", "quality")

# The spec wiring matrix — the KB document's role matrix resolved onto the six
# factory agents (pinned decision 2): existing skills unchanged, the five new
# skills added per role. A hand-edited yaml drift fails test 5, not review.
WIRED_SKILLS: dict[str, set[str]] = {
    "requirements": {
        "completeness-criteria",
        "synthetic-data",
        "acceptance-criteria",
        "soap-note-completeness",
    },
    "architecture": {
        "completeness-criteria",
        "in-process-testing",
        "synthetic-data",
        "soap-note-completeness",
    },
    "coding": {"synthetic-data", "soap-note-completeness"},
    "testing": {
        "completeness-criteria",
        "in-process-testing",
        "test-integrity",
        "synthetic-data",
        "criterion-tests",
        "run-evidence",
    },
    "debugging": {
        "test-integrity",
        "completeness-criteria",
        "synthetic-data",
        "bounded-repair",
    },
    "quality": {
        "test-integrity",
        "completeness-criteria",
        "synthetic-data",
        "run-evidence",
    },
}

# Prompts name skills in the established phrase: "- QualityForge skill `slug` (...)".
_SKILL_LINE = re.compile(r"QualityForge skill `([a-z0-9-]+)`")


def _skill_dirs() -> set[str]:
    """Slugs with a SKILL.md on disk (``registered/`` holds none, so it excludes itself)."""
    return {p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}


def _registered_slugs() -> set[str]:
    return {p.stem for p in REGISTERED_DIR.glob("*.json")}


def _yaml_skills(agent: str) -> list[str]:
    """The agent's ``agent.yaml`` skills list, read straight from the file."""
    config = yaml.safe_load((AGENTS_DIR / agent / "agent.yaml").read_text(encoding="utf-8"))
    skills = config.get("skills", [])
    assert isinstance(skills, list), f"{agent}/agent.yaml has no skills list"
    return [str(slug) for slug in skills]


def _prompt_skills(agent: str) -> set[str]:
    """Slugs named in the prompt's ``## Skills`` section."""
    text = (AGENTS_DIR / agent / "prompt.md").read_text(encoding="utf-8")
    if "## Skills" not in text:
        return set()
    section = text.split("## Skills", 1)[1]
    section = section.split("\n## ", 1)[0]
    return set(_SKILL_LINE.findall(section))


def _headings(skill_md: Path) -> list[str]:
    return re.findall(r"^## .+$", skill_md.read_text(encoding="utf-8"), re.MULTILINE)


# --- 1. skill directories <-> registration records -----------------------------


def test_every_skill_directory_has_a_registration_record_and_vice_versa() -> None:
    """A skill on disk without a registration (or an orphan record) is wiring drift."""
    assert _skill_dirs() == _registered_slugs()


@pytest.mark.parametrize(
    "record_path",
    sorted(REGISTERED_DIR.glob("*.json")),
    ids=lambda p: p.stem,
)
def test_registration_record_is_a_successful_sdk_response(record_path: Path) -> None:
    """Each record is a raw successful ``obvious skills create`` response (Run 1 precedent:
    an errored registration is recorded as a blocker, never fabricated)."""
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record.get("id", "").startswith("skl_"), record_path
    assert record.get("status") == "completed", record_path
    assert record.get("name") == f"qualityforge-{record_path.stem}", record_path


# --- 2. agent.yaml skills resolve to registered skill files ---------------------


@pytest.mark.parametrize("agent", AGENTS)
def test_every_agent_yaml_skill_resolves_to_a_registered_skill_file(agent: str) -> None:
    for slug in _yaml_skills(agent):
        assert (SKILLS_DIR / slug / "SKILL.md").is_file(), (
            f"{agent} lists unresolvable skill {slug}"
        )


# --- 3. prompts and agent.yaml stay in lockstep ---------------------------------


@pytest.mark.parametrize("agent", AGENTS)
def test_prompt_names_exactly_the_skills_its_yaml_lists(agent: str) -> None:
    assert _prompt_skills(agent) == set(_yaml_skills(agent)), (
        f"{agent}/prompt.md ## Skills section vs {agent}/agent.yaml skills list"
    )


# --- 4. every SKILL.md follows the file convention -------------------------------


@pytest.mark.parametrize(
    "skill_md",
    sorted(SKILLS_DIR.glob("*/SKILL.md")),
    ids=lambda p: p.parent.name,
)
def test_every_skill_file_follows_the_file_convention(skill_md: Path) -> None:
    """Header block (Spec / Consumed by) plus the three required sections."""
    text = skill_md.read_text(encoding="utf-8")
    assert "**Spec:**" in text, skill_md
    assert "**Consumed by:**" in text, skill_md
    headings = _headings(skill_md)
    assert "## Purpose" in headings, skill_md
    assert any(h.startswith("## Workflow steps") for h in headings), skill_md
    assert "## Non-negotiable rules" in headings, skill_md


# --- 5. the six agents match the spec wiring matrix exactly ----------------------


@pytest.mark.parametrize("agent", AGENTS)
def test_agent_skill_set_matches_the_spec_wiring_matrix(agent: str) -> None:
    assert set(_yaml_skills(agent)) == WIRED_SKILLS[agent], agent
