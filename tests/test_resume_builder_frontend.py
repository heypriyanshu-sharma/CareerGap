"""
Regression tests for the Resume Builder frontend.

The Add Skill bug lived entirely in the browser event-delegation
layer, so the primary regression test runs the real handler source
extracted from frontend/script.js against a minimal fake DOM that
mirrors the structure buildSectionFields produces. The Python tests
cover the underlying skills data model and the save/refresh
serialization path the feature depends on.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from resume_builder import build_plain_text, normalize_content

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
SCRIPT_JS = FRONTEND_DIR / "script.js"


# ============================================================
# SOURCE EXACTION
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
            i += 2
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
# NODE-BASED ADD SKILL REGRESSION TEST
# ============================================================

_NODE_TEST_TEMPLATE = r"""
'use strict';

// ---- Minimal fake DOM mirroring the real Resume Builder ----
class FakeElement {
    constructor(classes, dataset) {
        this.classList = new Set(classes || []);
        this.dataset = dataset || {};
        this.children = [];
        this.parent = null;
        this.insertedHTML = [];
        this.value = '';
        this.name = '';
    }

    appendChild(child) {
        child.parent = this;
        this.children.push(child);
        return child;
    }

    matches(selector) {
        if (selector.startsWith('.')) {
            return this.classList.has(selector.slice(1));
        }
        const match = selector.match(/^\[([a-zA-Z-]+)(?:="([^"]*)")?\]$/);
        if (match) {
            const attr = match[1];
            const expected = match[2];
            if (attr.startsWith('data-')) {
                const key = attr.slice(5).replace(
                    /-([a-z])/g,
                    (_, c) => c.toUpperCase()
                );
                if (expected === undefined) {
                    return key in this.dataset;
                }
                return this.dataset[key] === expected;
            }
            if (attr === 'name') {
                return this.name === expected;
            }
            return false;
        }
        return false;
    }

    closest(selector) {
        let node = this;
        while (node) {
            if (node.matches(selector)) {
                return node;
            }
            node = node.parent;
        }
        return null;
    }

    querySelector(selector) {
        for (const child of this.children) {
            if (child.matches(selector)) {
                return child;
            }
            const found = child.querySelector(selector);
            if (found) {
                return found;
            }
        }
        return null;
    }

    querySelectorAll(selector) {
        const results = [];
        for (const child of this.children) {
            if (child.matches(selector)) {
                results.push(child);
            }
            results.push(...child.querySelectorAll(selector));
        }
        return results;
    }

    insertAdjacentHTML(position, html) {
        this.insertedHTML.push({ position, html });
    }
}

function el(classes, dataset) {
    return new FakeElement(classes, dataset);
}

// ---- Real source extracted verbatim from frontend/script.js ----
__ESCAPE_HTML__

__BUILD_SKILL_ROW__

// The real Add Skill click-delegation branch.
function runAddSkillHandler(target) {
__ADD_SKILL_HANDLER__
}

// ---- Build two skills sections exactly as buildSectionFields
//      renders them: the Add Skill button is a sibling of the
//      .resume-bullets container, both inside .resume-section-fields.
function buildSkillsSection(existingSkills) {
    const sectionItem = el(
        ['resume-section-item', 'section-skills'],
        { sectionType: 'skills' }
    );
    const header = el(['resume-section-item-header']);
    const fields = el(['resume-section-fields']);

    const headingField = el(['resume-field', 'full-width']);
    const headingInput = el([]);
    headingInput.name = 'heading';
    headingInput.value = 'Technical Skills';
    headingField.appendChild(headingInput);

    const skillsList = el(['resume-bullets']);
    for (const skill of existingSkills) {
        const row = el(['resume-bullet-row']);
        const input = el([]);
        input.name = 'skill[]';
        input.value = skill;
        const removeBtn = el(
            ['resume-section-item-btn', 'danger'],
            { removeSkill: '' }
        );
        row.appendChild(input);
        row.appendChild(removeBtn);
        skillsList.appendChild(row);
    }

    const addBtn = el(['resume-bullet-add'], { addSkill: '' });

    fields.appendChild(headingField);
    fields.appendChild(skillsList);
    fields.appendChild(addBtn);
    sectionItem.appendChild(header);
    sectionItem.appendChild(fields);

    return { sectionItem, skillsList, addBtn };
}

const sectionA = buildSkillsSection(['Python', 'JavaScript']);
const sectionB = buildSkillsSection(['Go']);

// ---- Simulate clicking Add Skill inside section A ----
runAddSkillHandler(sectionA.addBtn);

// ---- Assertions ----
function fail(message) {
    console.error('ASSERTION FAILED: ' + message);
    process.exit(1);
}

if (sectionA.skillsList.insertedHTML.length !== 1) {
    fail(
        'expected exactly one insertion into section A skills list, got ' +
        sectionA.skillsList.insertedHTML.length
    );
}

const inserted = sectionA.skillsList.insertedHTML[0];

if (inserted.position !== 'beforeend') {
    fail('expected insertion at beforeend, got ' + inserted.position);
}

if (!inserted.html.includes('name="skill[]"')) {
    fail('inserted row is not a skill input row: ' + inserted.html);
}

if (sectionB.skillsList.insertedHTML.length !== 0) {
    fail('section B skills list was modified unexpectedly');
}

const existingA = sectionA.skillsList.querySelectorAll('[name="skill[]"]');

if (existingA.length !== 2) {
    fail('expected 2 existing skill inputs to remain, got ' + existingA.length);
}

if (existingA[0].value !== 'Python' || existingA[1].value !== 'JavaScript') {
    fail('existing skills in section A were overwritten');
}

const existingB = sectionB.skillsList.querySelectorAll('[name="skill[]"]');

if (existingB.length !== 1 || existingB[0].value !== 'Go') {
    fail('section B skills were modified');
}

console.log('add skill handler OK');
"""


def _run_node_add_skill_test() -> subprocess.CompletedProcess:
    source = _read_script_js()

    escape_html = _extract_braced_block(
        source, "function escapeHTML(value)"
    )
    build_skill_row = _extract_braced_block(
        source, "function buildResumeSkillRowHtml(skill)"
    )
    add_skill_handler = _extract_braced_block(
        source, 'if (target.closest("[data-add-skill]"))'
    )

    node_script = (
        _NODE_TEST_TEMPLATE
        .replace("__ESCAPE_HTML__", escape_html)
        .replace("__BUILD_SKILL_ROW__", build_skill_row)
        .replace("__ADD_SKILL_HANDLER__", add_skill_handler)
    )

    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(node_script)
        tmp_path = handle.name

    try:
        return subprocess.run(
            ["node", tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is required to run the frontend handler test",
)
def test_add_skill_button_inserts_row_into_correct_skills_section():
    """Clicking Add Skill must insert one editable skill row into
    the clicked section's .resume-bullets container.

    The Add Skill button is a sibling of .resume-bullets, so the
    handler must resolve the container from the enclosing
    .resume-section-item. Before the fix it called
    target.closest(".resume-bullets"), which returned null and
    made the button a no-op.
    """
    result = _run_node_add_skill_test()

    assert result.returncode == 0, (
        "Add Skill handler test failed:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "add skill handler OK" in result.stdout


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is required to run the frontend handler test",
)
def test_add_skill_handler_is_scoped_to_the_section_item():
    """The Add Skill handler must resolve .resume-bullets from the
    enclosing .resume-section-item, not from the button itself."""
    source = _read_script_js()
    handler = _extract_braced_block(
        source, 'if (target.closest("[data-add-skill]"))'
    )

    # The source is line-wrapped, so compare with all
    # whitespace removed.
    compact = re.sub(r"\s+", "", handler)

    assert 'target.closest(".resume-section-item")' in compact, (
        "handler must scope the search to the section item"
    )
    assert (
        'sectionItem.querySelector(".resume-bullets")' in compact
    ), (
        "handler must query .resume-bullets within the "
        "section item"
    )
    assert 'target.closest(".resume-bullets")' not in compact, (
        "handler must not look for .resume-bullets as an ancestor "
        "of the button (the button is a sibling, not a descendant)"
    )


# ============================================================
# UNDERLYING DATA MODEL + SAVE/REFRESH PATH
# ============================================================

def test_skills_survive_save_refresh_cycle():
    """Skills entered in the builder are plain strings and must
    survive the normalize (save) -> normalize (refresh) round-trip
    that the API performs, with every skill preserved."""
    raw = {
        "contact": {"full_name": "Jane Doe"},
        "summary": "",
        "sections": [
            {
                "type": "skills",
                "heading": "Technical Skills",
                "items": ["Python", "JavaScript", "Go"],
            }
        ],
    }

    # Save: the API normalizes content before storing it.
    stored = normalize_content(raw)

    # Refresh: the stored content is normalized again on read.
    reloaded = normalize_content(stored)

    assert len(reloaded["sections"]) == 1
    section = reloaded["sections"][0]
    assert section["type"] == "skills"
    assert section["items"] == ["Python", "JavaScript", "Go"]

    # The serialized text (used by the preview and the PDF) keeps
    # every skill.
    text = build_plain_text(reloaded)
    for skill in ("Python", "JavaScript", "Go"):
        assert skill in text


def test_multiple_skills_sections_coexist():
    """Multiple skills sections keep their own skills without
    overwriting each other."""
    raw = {
        "contact": {"full_name": "Jane Doe"},
        "summary": "",
        "sections": [
            {"type": "skills", "heading": "Languages", "items": ["Python", "Go"]},
            {"type": "skills", "heading": "Frameworks", "items": ["React", "Django"]},
        ],
    }

    normalized = normalize_content(raw)

    assert len(normalized["sections"]) == 2
    assert normalized["sections"][0]["items"] == ["Python", "Go"]
    assert normalized["sections"][1]["items"] == ["React", "Django"]


def test_section_type_dropdown_markup():
    """The section-type picker must expose an accessible
    listbox with all six section types, and the Add button
    must start disabled until a type is chosen."""
    html = (FRONTEND_DIR / "index.html").read_text(
        encoding="utf-8"
    )

    # Trigger button with listbox semantics.
    assert 'id="add-section-type"' in html
    assert 'aria-haspopup="listbox"' in html
    assert 'aria-expanded="false"' in html
    assert 'aria-controls="add-section-type-menu"' in html

    # Listbox with one option per section type plus the
    # placeholder.
    assert 'id="add-section-type-menu"' in html
    assert 'role="listbox"' in html
    assert html.count('role="option"') == 7

    for value in (
        "skills",
        "education",
        "experience",
        "projects",
        "certifications",
        "custom",
    ):
        assert f'data-value="{value}"' in html

    # The Add button starts disabled until a type is chosen.
    assert 'id="add-section-btn"' in html
    assert re.search(r'id="add-section-btn"[^>]*disabled', html)
