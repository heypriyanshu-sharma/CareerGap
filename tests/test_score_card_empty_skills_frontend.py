"""
Regression tests for the score card's empty-skills state.

When the job description yields no recognized skills the backend
returns ``job_skills: []``. That is not the same as a 0% match: the
report must say the score is unavailable instead of rendering a 0%
ring with an encouraging score message. Normal scoring (including a
genuine 0% when skills were recognized) must be unchanged.

The primary tests run the real helpers, extracted verbatim from
frontend/script.js together with the real escapeHTML, through Node.
Python-side pins cover the source structure.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
SCRIPT_JS = FRONTEND_DIR / "script.js"


# ============================================================
# SOURCE EXTRACTION
# ============================================================

def _extract_braced_block(source: str, start_marker: str) -> str:
    """Return the source block that opens with the first ``{``
    after ``start_marker`` and closes with its matching brace.

    Skips string literals, template literals (including nested
    ``${...}`` expressions) and comments so braces inside them do
    not confuse the matching.
    """
    start = source.index(start_marker)
    open_idx = source.index("{", start)

    depth = 0
    i = open_idx
    n = len(source)

    while i < n:
        char = source[i]

        if char in "\"'`":
            quote = char
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue
                if (
                    quote == "`"
                    and source[i] == "$"
                    and i + 1 < n
                    and source[i + 1] == "{"
                ):
                    i += 2
                    nested = 1
                    while i < n and nested > 0:
                        if source[i] == "{":
                            nested += 1
                        elif source[i] == "}":
                            nested -= 1
                        i += 1
                    continue
                if source[i] == quote:
                    break
                i += 1
            i += 1
            continue

        if char == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue

        if char == "/" and i + 1 < n and source[i + 1] == "*":
            while i + 1 < n and not (
                source[i] == "*" and source[i + 1] == "/"
            ):
                i += 1
            i += 2
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]

        i += 1

    raise ValueError(f"unbalanced braces for {start_marker!r}")


def _read_script_js() -> str:
    return SCRIPT_JS.read_text(encoding="utf-8")


# ============================================================
# NODE-BASED SCORE CARD REGRESSION TEST
# ============================================================

_NODE_TEST_TEMPLATE = r"""
'use strict';

// ---- Real source extracted verbatim from frontend/script.js ----
__ESCAPE_HTML__

__GET_SCORE_MESSAGE__

__CREATE_SCORE_CARD__

// ---- Assertions against the real helpers ----
(function () {
    let failures = [];

    function expect(name, condition) {
        if (!condition) {
            failures.push(name);
        }
    }

    // 1. No recognized skills: say so, and never render a 0% ring.
    const unavailable = createScoreCard({
        job_skills: [],
        score: 0,
    });
    expect(
        "unavailable heading",
        unavailable.includes("Score unavailable")
    );
    expect(
        "unavailable explanation",
        unavailable.includes("No recognizable skills were")
    );
    expect(
        "unavailable has no 0.0%",
        !unavailable.includes("0.0%")
    );
    expect(
        "unavailable has no score ring",
        !unavailable.includes("score-ring")
    );
    expect(
        "unavailable has no Skill Match label",
        !unavailable.includes("Skill Match")
    );
    expect(
        "unavailable reuses the score card shell",
        unavailable.includes("dashboard-card score-card")
    );
    expect(
        "unavailable reuses score-copy",
        unavailable.includes("score-copy")
    );
    expect(
        "unavailable guidance is role-neutral",
        !unavailable.includes("tools and technologies") &&
        !unavailable.toLowerCase().includes("technical")
    );

    // 2. A genuine 0% (skills were recognized, none matched) keeps
    //    the normal ring and score message.
    const genuineZero = createScoreCard({
        job_skills: ["Docker"],
        score: 0,
    });
    expect(
        "genuine zero renders 0.0%",
        genuineZero.includes("0.0%")
    );
    expect(
        "genuine zero renders the ring",
        genuineZero.includes("score-ring")
    );
    expect(
        "genuine zero keeps the label",
        genuineZero.includes("Skill Match")
    );
    expect(
        "genuine zero is not the unavailable state",
        !genuineZero.includes("Score unavailable")
    );

    // 3. Normal scoring is unchanged.
    const normal = createScoreCard({
        job_skills: ["Python", "FastAPI"],
        score: 50,
    });
    expect("normal renders 50.0%", normal.includes("50.0%"));
    expect(
        "normal renders its score message",
        normal.includes("You&#039;re finding your direction.")
    );

    // 4. A missing / non-array job_skills list (older saved rows)
    //    falls through to normal rendering instead of claiming the
    //    score is unavailable.
    const legacyMissing = createScoreCard({ score: 72 });
    expect(
        "legacy row renders its score",
        legacyMissing.includes("72.0%")
    );
    expect(
        "legacy row is not unavailable",
        !legacyMissing.includes("Score unavailable")
    );

    const legacyNull = createScoreCard({
        job_skills: null,
        score: 80,
    });
    expect(
        "null job_skills renders its score",
        legacyNull.includes("80.0%")
    );

    if (failures.length > 0) {
        console.log("FAILED: " + failures.join(", "));
        process.exit(1);
    }

    console.log("score card empty-skills handlers OK");
})();
"""


def _run_node_score_card_test() -> subprocess.CompletedProcess:
    source = _read_script_js()

    escape_html = _extract_braced_block(source, "function escapeHTML(value)")
    get_score_message = _extract_braced_block(
        source, "function getScoreMessage("
    )
    create_score_card = _extract_braced_block(
        source, "function createScoreCard("
    )

    program = (
        _NODE_TEST_TEMPLATE
        .replace("__ESCAPE_HTML__", escape_html)
        .replace("__GET_SCORE_MESSAGE__", get_score_message)
        .replace("__CREATE_SCORE_CARD__", create_score_card)
    )

    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".js",
        delete=False,
    )

    try:
        handle.write(program)
        handle.close()

        tmp_path = handle.name

        return subprocess.run(
            ["node", tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        Path(handle.name).unlink(missing_ok=True)


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is required to run the frontend handler test",
)
def test_empty_job_skills_render_the_unavailable_state():
    """No recognized skills must render the unavailable explanation,
    not a 0% ring or a score message."""

    result = _run_node_score_card_test()

    assert result.returncode == 0, (
        "Score card handler test failed:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "FAILED" not in result.stdout
    assert "score card empty-skills handlers OK" in result.stdout


# ============================================================
# SOURCE PINS
# ============================================================

def test_score_card_guards_on_an_explicitly_empty_job_skills_list():
    """Only an explicit empty list triggers the unavailable state,
    so older saved rows without job_skills keep normal rendering."""

    helper = _extract_braced_block(
        _read_script_js(),
        "function createScoreCard(",
    )
    compact = re.sub(r"\s+", "", helper)

    assert "Array.isArray(result.job_skills)" in compact
    assert "jobSkills.length===0" in compact
    assert "Scoreunavailable" in compact
    assert "Norecognizableskillswere" in compact

    # The guidance must stay role-neutral: not every role is a
    # technical role, so the copy may not assume tools or
    # technologies.
    assert "toolsandtechnologies" not in compact
    assert "skillsorrequirementstherolecallsfor" in compact


def test_score_card_still_renders_the_score_ring_for_recognized_skills():
    """The guarded branch must return before the ring; the normal
    path is untouched."""

    helper = _extract_braced_block(
        _read_script_js(),
        "function createScoreCard(",
    )
    compact = re.sub(r"\s+", "", helper)

    # The empty-skills return precedes the score computation.
    assert compact.index("jobSkills.length===0") < compact.index(
        "constscore="
    )
    assert "constscore=Number(result.score||0)" in compact
    assert "getScoreMessage(score)" in compact
    assert "score-ring" in compact
