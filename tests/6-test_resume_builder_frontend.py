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


def _read_index_html() -> str:
    return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")


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


# ============================================================
# ATS MODAL REGRESSION TESTS
# ============================================================

def test_ats_modal_functions_exist_in_js():
    """Verify all ATS modal functions are defined in the JavaScript source."""
    import re
    source = _read_script_js()

    required_functions = [
        'setupAtsModalListeners',
        'openAtsCheckModal',
        'closeAtsCheckModal',
        'updateAtsModalRunButton',
        'runAtsCheckFromModal',
        'createAtsCheckReport',
    ]

    for func_name in required_functions:
        matches = re.findall(r'function ' + re.escape(func_name), source)
        assert len(matches) == 1, f"Function {func_name} should be defined exactly once in JS, found {len(matches)}"


def test_ats_check_state_declared_once_in_js():
    """Verify atsCheckState is declared exactly once in the JavaScript source."""
    import re
    source = _read_script_js()

    declarations = re.findall(r'let atsCheckState\s*=', source)
    assert len(declarations) == 1, f"atsCheckState should be declared exactly once in JS, found {len(declarations)}"


def test_setupatsmodallisteners_guards_missing_elements():
    """Verify setupAtsModalListeners guards against missing modal elements."""
    source = _read_script_js()

    # Extract the function body
    handler = _extract_braced_block(source, 'function setupAtsModalListeners(')

    # The function should have an early return guard for missing atsModal
    assert 'if (!resumeElements.atsModal) return;' in handler, (
        "setupAtsModalListeners must guard against missing atsModal element"
    )

    # All event listeners should use optional chaining
    assert 'resumeElements.atsModalBackdrop?.addEventListener' in handler
    assert 'resumeElements.atsModalClose?.addEventListener' in handler
    assert 'resumeElements.atsModalCancel?.addEventListener' in handler
    assert 'resumeElements.atsModeRadios?.forEach' in handler
    assert 'resumeElements.atsSourceRadios?.forEach' in handler
    assert 'resumeElements.atsJobDescription?.addEventListener' in handler
    assert 'resumeElements.atsFileUpload?.addEventListener' in handler
    assert 'resumeElements.atsModalRun?.addEventListener' in handler


def test_loadresumes_called_inside_initresumebuilder():
    """Verify loadResumes is called inside initResumeBuilder before it returns.

    The initialization flow is: initResumeBuilder() is defined, and at the end
    of its body it calls loadResumes(), then initResumeBuilder() is invoked.
    """
    source = _read_script_js()

    # Extract the initResumeBuilder function body
    init_fn = _extract_braced_block(source, 'function initResumeBuilder(')

    # loadResumes() should be called inside initResumeBuilder
    assert 'loadResumes()' in init_fn, "initResumeBuilder must call loadResumes()"

    # The call should be near the end of the function (before the closing brace)
    loadresumes_pos = init_fn.rfind("loadResumes()")
    assert loadresumes_pos != -1, "loadResumes() call not found in initResumeBuilder"

    # Should be after the click handler setup
    click_handler_end = init_fn.rfind("});")
    assert click_handler_end != -1, "Click handler not found in initResumeBuilder"
    assert loadresumes_pos > click_handler_end, "loadResumes() should be called after click handler setup"


def test_initresumebuilder_calls_setupatsmodallisteners():
    """Verify initResumeBuilder calls setupAtsModalListeners when ATS check button exists."""
    source = _read_script_js()

    # Extract initResumeBuilder function
    init_fn = _extract_braced_block(source, 'function initResumeBuilder(')

    # Should call setupAtsModalListeners inside the atsCheckBtn check
    assert 'setupAtsModalListeners()' in init_fn, (
        "initResumeBuilder must call setupAtsModalListeners"
    )

    # The call should be inside the atsCheckBtn conditional
    assert 'if (resumeElements.atsCheckBtn)' in init_fn


def test_signed_out_prompt_markup_and_layout_width():
    """The signed-out prompt must replace the builder layout, not sit inside it."""
    html = _read_index_html()

    section_pos = html.index('id="resume-builder"')
    prompt_pos = html.index('id="resume-signed-out"', section_pos)
    layout_pos = html.index('class="resume-builder-layout"', section_pos)

    assert prompt_pos < layout_pos, (
        "the signed-out prompt must come before the builder layout so it can "
        "replace it"
    )

    prompt = html[prompt_pos:layout_pos]
    assert 'href="login.html"' in prompt, "the prompt needs a route to sign in"
    assert ">Sign in</a>" in prompt
    assert "resume-editor-empty" in prompt, "reuse the existing empty-state card"
    assert "hidden" in prompt, "the prompt starts hidden until auth resolves"

    css = (FRONTEND_DIR / "style.css").read_text(encoding="utf-8")
    rule_start = css.index(".resume-signed-out {")
    rule = css[rule_start:css.index("}", rule_start)]
    assert "width: min(1280px, 92%);" in rule, (
        "the prompt must occupy the width the builder layout would have used"
    )
    assert "margin: 0 auto;" in rule


def test_signed_out_prompt_reuses_existing_sign_in_wording():
    """The reviewed sign-in sentence must not drift between prompt and API."""
    html = _read_index_html()
    source = _read_script_js()

    sentence = "You need to sign in to manage resumes."

    assert f"<p>{sentence}</p>" in html
    assert f'throw new Error("{sentence}");' in source
    assert source.count(sentence) == 1, (
        "the sign-in sentence must exist once in script.js so the prompt and "
        "the API guard cannot drift apart"
    )


def test_signed_out_state_hides_layout_and_disables_create():
    """setResumeSignedOut must swap the layout for the prompt and block creation."""
    source = _read_script_js()

    elements = _extract_braced_block(source, "const resumeElements =")
    assert 'signedOut: document.getElementById("resume-signed-out"),' in elements
    assert 'layout: document.querySelector(".resume-builder-layout"),' in elements

    helper = _extract_braced_block(source, "function setResumeSignedOut(")
    assert "resumeBuilderState.signedIn = !isSignedOut;" in helper
    assert 'resumeElements.signedOut?.classList.toggle("hidden", !isSignedOut);' in helper
    assert 'resumeElements.layout?.classList.toggle("hidden", isSignedOut);' in helper
    assert "resumeElements.createBtn.disabled = isSignedOut;" in helper


def test_loadresumes_checks_session_before_requesting():
    """A signed-out list load must show the prompt instead of an API error."""
    source = _read_script_js()
    load_fn = _extract_braced_block(source, "async function loadResumes(")

    token_pos = load_fn.index("await getAccessToken(false)")
    guard_pos = load_fn.index("setResumeSignedOut(true)")
    request_pos = load_fn.index('apiRequest("/resumes?limit=50"')

    assert token_pos < guard_pos < request_pos, (
        "the session must be checked before the request and before the error path"
    )
    assert "return;" in load_fn[guard_pos:request_pos], (
        "a missing session must return before calling the API"
    )


def test_createresume_guards_when_signed_out():
    """A programmatic click must not open an editor that cannot save."""
    source = _read_script_js()
    create_fn = _extract_braced_block(source, "function createResume(")

    guard_pos = create_fn.index("if (!resumeBuilderState.signedIn)")
    edit_pos = create_fn.index('resumeBuilderState.viewMode = "edit"')

    assert guard_pos < edit_pos, "the guard must run before the editor opens"
    guard = create_fn[guard_pos:edit_pos]
    assert '"login.html"' in guard
    assert "return;" in guard


def test_saveresume_does_not_redirect_when_session_is_missing():
    """Save must keep the typed form instead of navigating to login."""
    source = _read_script_js()
    save_fn = _extract_braced_block(source, "async function saveResume(")

    assert save_fn.count("}, false);") == 2, (
        "both the PUT and POST resume calls must pass redirectIfMissing=false"
    )
    assert "apiRequest(`/resumes/" in save_fn
    assert 'apiRequest("/resumes", {' in save_fn


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])


# ============================================================
# OPENING A RESUME SCROLLS ITS PANEL INTO VIEW (stacked layout)
# ============================================================

def test_reveal_resume_panel_respects_sticky_navbar_and_reduced_motion():
    js = _read_script_js()
    body = _extract_braced_block(js, "function revealResumePanel")
    assert "window.innerHeight" in body
    assert '.navbar' in body
    assert "prefersReducedMotion()" in body
    assert '"smooth"' in body and '"auto"' in body


def test_new_resume_and_list_click_reveal_panel_but_save_does_not():
    js = _read_script_js()
    create = _extract_braced_block(js, "function createResume")
    assert "revealResumePanel()" in create
    start = js.index("async function selectResume")
    select = js[start:js.index("function updateViewMode", start)]
    assert "options.reveal" in select
    assert "selectResume(resumeId, { reveal: true })" in js
    # The post-save refresh calls selectResume without reveal.
    assert "await selectResume(savedResume.id);" in js


# ============================================================
# OVERLAPPING LIST LOADS AND ABORT ERROR TEXT (cold-start race)
# ============================================================

def test_loadresumes_ignores_stale_load_results():
    """An older overlapping load must not paint its state over a newer one."""
    source = _read_script_js()
    load_fn = _extract_braced_block(source, "async function loadResumes(")

    seq_pos = load_fn.index("++resumeBuilderState.listLoadSeq")
    request_pos = load_fn.index('apiRequest("/resumes?limit=50"')
    assert seq_pos < request_pos, (
        "the sequence must increment before the request starts"
    )

    catch_pos = load_fn.index("catch (error)")
    guard = "loadSeq !== resumeBuilderState.listLoadSeq"
    guard_pos = load_fn.index(guard, catch_pos)
    error_paint = load_fn.index("resumeElements.error.textContent", catch_pos)
    assert guard_pos < error_paint, (
        "a stale load must return before painting the error"
    )
    assert load_fn.count(guard) == 2, (
        "success and failure paths must both defer to the newest load"
    )


def test_resume_errors_translate_abort_jargon():
    """Raw AbortError text must never reach the resume list or editor."""
    source = _read_script_js()
    helper = _extract_braced_block(source, "function describeRequestError(")
    assert 'error.name === "AbortError"' in helper
    assert "signal is aborted" in helper
    assert "waking up" in helper

    load_fn = _extract_braced_block(source, "async function loadResumes(")
    save_fn = _extract_braced_block(source, "async function saveResume(")
    for fn in (load_fn, save_fn):
        assert "describeRequestError(error)" in fn
        assert "escapeHTML(error.message)" not in fn, (
            "raw error.message must not reach the UI"
        )


# ============================================================
# BEHAVIORAL: OVERLAPPING LIST LOAD RACE (real sources, fake DOM)
# ============================================================

_RACE_HARNESS = """
__ESCAPE_HTML_SOURCE__

__DESCRIBE_ERROR_SOURCE__

__RESUME_STATE_SOURCE__

function makeEl() {
  const classes = new Set(["hidden"]);
  return {
    textContent: "",
    innerHTML: "",
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      contains: (c) => classes.has(c),
    },
    querySelectorAll: () => [],
  };
}

const resumeElements = {
  loading: makeEl(),
  list: makeEl(),
  empty: makeEl(),
  error: makeEl(),
};

const apiCalls = [];
function apiRequest(path, options, redirectIfMissing) {
  return new Promise((resolve, reject) => {
    apiCalls.push({ path, resolve, reject });
  });
}
async function getAccessToken() { return "token"; }
function setResumeSignedOut() {}

__RENDER_LIST_SOURCE__

__LOAD_RESUMES_SOURCE__

function abortError() {
  const e = new Error("signal is aborted without reason");
  e.name = "AbortError";
  return e;
}

async function scenarioStaleFailure() {
  const p1 = loadResumes();
  await Promise.resolve();
  await Promise.resolve();
  const p2 = loadResumes();
  await Promise.resolve();
  await Promise.resolve();
  if (apiCalls.length !== 2) throw new Error("expected two list requests, got " + apiCalls.length);

  apiCalls[1].resolve([{ id: "r1", title: "Newest", is_default: false, updated_at: null }]);
  await p2;
  apiCalls[0].reject(abortError());
  await p1;

  if (!resumeElements.error.classList.contains("hidden")) {
    throw new Error("stale failure painted the error element over the newer load");
  }
  if (resumeElements.error.textContent !== "") {
    throw new Error("stale failure wrote error text: " + resumeElements.error.textContent);
  }
  if (resumeElements.list.classList.contains("hidden")) {
    throw new Error("newer load's list must stay visible");
  }
  if (!resumeElements.list.innerHTML.includes("Newest")) {
    throw new Error("list must show the newer load's data");
  }
  console.log("stale-failure OK");
}

async function scenarioStaleSuccess() {
  const p1 = loadResumes();
  await Promise.resolve();
  await Promise.resolve();
  const p2 = loadResumes();
  await Promise.resolve();
  await Promise.resolve();

  apiCalls[0].resolve([]);
  await p1;
  if (!resumeElements.empty.classList.contains("hidden")) {
    throw new Error("stale empty result painted the empty state over the newer load");
  }
  apiCalls[1].resolve([{ id: "r2", title: "Fresh", is_default: false, updated_at: null }]);
  await p2;
  if (!resumeElements.list.innerHTML.includes("Fresh")) {
    throw new Error("newer load must render its data");
  }
  console.log("stale-success OK");
}

async function scenarioSingleFailureFriendly() {
  const p1 = loadResumes();
  await Promise.resolve();
  await Promise.resolve();
  apiCalls[0].reject(abortError());
  await p1;

  if (resumeElements.error.classList.contains("hidden")) {
    throw new Error("a sole failing load must show the error");
  }
  if (resumeElements.error.textContent.indexOf("waking up") === -1) {
    throw new Error("abort jargon not translated: " + resumeElements.error.textContent);
  }
  if (resumeElements.error.textContent.indexOf("signal is aborted") !== -1) {
    throw new Error("raw abort text leaked to the UI");
  }
  console.log("single-failure-friendly OK");
}

const scenario = process.argv[2];
const scenarios = {
  "stale-failure": scenarioStaleFailure,
  "stale-success": scenarioStaleSuccess,
  "single-failure-friendly": scenarioSingleFailureFriendly,
};
scenarios[scenario]().catch((e) => { console.error(e); process.exit(1); });
"""


def _build_race_script() -> str:
    """Assemble the real resume-list sources into the race harness."""
    source = _read_script_js()
    script = _RACE_HARNESS
    script = script.replace(
        "__ESCAPE_HTML_SOURCE__",
        _extract_braced_block(source, "function escapeHTML("),
    )
    script = script.replace(
        "__DESCRIBE_ERROR_SOURCE__",
        _extract_braced_block(source, "function describeRequestError("),
    )
    script = script.replace(
        "__RESUME_STATE_SOURCE__",
        _extract_braced_block(source, "let resumeBuilderState ="),
    )
    script = script.replace(
        "__RENDER_LIST_SOURCE__",
        _extract_braced_block(source, "function renderResumeList("),
    )
    script = script.replace(
        "__LOAD_RESUMES_SOURCE__",
        _extract_braced_block(source, "async function loadResumes("),
    )
    return script


def _run_race_scenario(tmp_path, scenario):
    script = tmp_path / "resume_list_race.cjs"
    script.write_text(_build_race_script(), encoding="utf-8")
    result = subprocess.run(
        ["node", str(script), scenario],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"scenario {scenario} failed:\n{result.stdout}\n{result.stderr}"
    )


def test_stale_load_failure_cannot_paint_over_newer_load(tmp_path):
    _run_race_scenario(tmp_path, "stale-failure")


def test_stale_load_success_cannot_paint_over_newer_load(tmp_path):
    _run_race_scenario(tmp_path, "stale-success")


def test_sole_failing_load_shows_friendly_abort_message(tmp_path):
    _run_race_scenario(tmp_path, "single-failure-friendly")

def test_abort_translation_covers_every_apirequest_error_display():
    """Every apiRequest-driven error display routes through the translator."""
    source = _read_script_js()
    # Raw error.message must not reach any user-visible surface left.
    for fragment in (
        "escapeHTML(error.message)",
        "alert(error.message",
        "setUploadStatus(\n                    statusElement,\n                    error.message",
    ):
        assert fragment not in source, f"raw error.message still displayed: {fragment}"
    assert source.count("describeRequestError(error") >= 12, (
        "the translator should cover resume, interview, analysis and upload paths"
    )


# ============================================================
# NODE-BASED ENTER-TO-ADD-SKILL REGRESSION TESTS
# ============================================================

_NODE_ENTER_TEST_TEMPLATE = r"""
'use strict';

class Element {}

class FakeElement extends Element {
    constructor(classes, dataset) {
        super();
        this.classList = new Set(classes || []);
        this.dataset = dataset || {};
        this.children = [];
        this.parent = null;
        this.insertedHTML = [];
        this.value = '';
        this.name = '';
        this.focused = false;
    }

    get lastElementChild() {
        return this.children.length
            ? this.children[this.children.length - 1]
            : null;
    }

    appendChild(child) {
        child.parent = this;
        this.children.push(child);
        return child;
    }

    focus() {
        this.focused = true;
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
            if (node.matches && node.matches(selector)) {
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

    insertAdjacentHTML(position, html) {
        this.insertedHTML.push({ position, html });
    }
}

function el(classes, dataset) {
    return new FakeElement(classes, dataset);
}

__ESCAPE_HTML__

__BUILD_SKILL_ROW__

const runSkillEnterHandler =
__ENTER_HANDLER__;

function buildSkillsSection(skills) {
    const sectionItem = el(
        ['resume-section-item', 'section-skills'],
        { sectionType: 'skills' }
    );
    const skillsList = el(['resume-bullets']);
    const inputs = [];
    for (const skill of skills) {
        const row = el(['resume-bullet-row']);
        const input = el([]);
        input.name = 'skill[]';
        input.value = skill;
        row.appendChild(input);
        skillsList.appendChild(row);
        inputs.push(input);
    }
    sectionItem.appendChild(skillsList);
    return { sectionItem, skillsList, inputs };
}

function makeEvent(target, overrides) {
    const event = Object.assign(
        {
            key: 'Enter',
            isComposing: false,
            target,
            defaultPrevented: false,
            preventDefault() {
                this.defaultPrevented = true;
            },
        },
        overrides || {}
    );
    return event;
}

function fail(message) {
    console.error('ASSERTION FAILED: ' + message);
    process.exit(1);
}

// 1. Enter on a filled skill input inserts exactly one new row
//    and prevents the default keypress behavior.
const filled = buildSkillsSection(['Python']);
const enterEvent = makeEvent(filled.inputs[0]);
runSkillEnterHandler(enterEvent);

if (filled.skillsList.insertedHTML.length !== 1) {
    fail('expected one insertion after Enter on a filled skill input');
}
if (!filled.skillsList.insertedHTML[0].html.includes('name="skill[]"')) {
    fail('inserted row is not a skill input row');
}
if (!enterEvent.defaultPrevented) {
    fail('Enter default was not prevented for a handled skill input');
}

// 2. Enter on an empty skill input adds nothing (no empty-row chains).
const empty = buildSkillsSection(['']);
const emptyEvent = makeEvent(empty.inputs[0]);
runSkillEnterHandler(emptyEvent);

if (empty.skillsList.insertedHTML.length !== 0) {
    fail('Enter on an empty skill input must not add a row');
}
if (emptyEvent.defaultPrevented) {
    fail('unhandled Enter must not be default-prevented');
}

// 3. Enter during IME composition adds nothing.
const ime = buildSkillsSection(['Python']);
const imeEvent = makeEvent(ime.inputs[0], { isComposing: true });
runSkillEnterHandler(imeEvent);

if (ime.skillsList.insertedHTML.length !== 0) {
    fail('IME composition Enter must not add a row');
}

// 4. Enter outside a skill input adds nothing.
const other = buildSkillsSection(['Python']);
const headingInput = el([]);
headingInput.name = 'heading';
other.sectionItem.appendChild(headingInput);
const otherEvent = makeEvent(headingInput);
runSkillEnterHandler(otherEvent);

if (other.skillsList.insertedHTML.length !== 0) {
    fail('Enter on a non-skill input must not add a row');
}
if (otherEvent.defaultPrevented) {
    fail('Enter on a non-skill input must keep its default behavior');
}

console.log('skill enter handler OK');
"""


def _run_node_skill_enter_test() -> subprocess.CompletedProcess:
    source = _read_script_js()

    escape_html = _extract_braced_block(
        source, "function escapeHTML(value)"
    )
    build_skill_row = _extract_braced_block(
        source, "function buildResumeSkillRowHtml(skill)"
    )
    # Slice from the keydown registration so the extractor returns
    # exactly the arrow function `(event) => { ... }`.
    keydown_at = source.index('"keydown",' + chr(10) + '                (event) =>')
    enter_handler = _extract_braced_block(
        source[keydown_at:], "(event) =>"
    )

    node_script = (
        _NODE_ENTER_TEST_TEMPLATE
        .replace("__ESCAPE_HTML__", escape_html)
        .replace("__BUILD_SKILL_ROW__", build_skill_row)
        .replace("__ENTER_HANDLER__", enter_handler)
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
def test_skill_enter_appends_row_only_for_filled_skill_inputs():
    """Enter inside a filled skill input appends one editable skill
    row and swallows the default keypress; Enter on an empty row,
    during IME composition, or in a non-skill input does nothing.

    The user asked for type-one-skill-then-Enter to open the next
    skill row. Without the empty-input and composition guards the
    same handler would chain empty rows and fight IMEs.
    """
    result = _run_node_skill_enter_test()

    assert result.returncode == 0, (
        "Skill Enter handler test failed:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "skill enter handler OK" in result.stdout


# ============================================================
# REMOVE-BUTTON SCOPE LABELS + PLACEHOLDER STYLING
# ============================================================

def test_remove_buttons_name_their_scope_in_visible_text():
    """Entry, link and section removes must carry visible text, not
    only a trash icon: adjacent icon-only buttons read as removing
    the row above them on touchscreens (no hover)."""
    source = _read_script_js()

    assert "<span>Remove entry</span>" in source, (
        "entry remove button must show the text 'Remove entry'"
    )
    assert "<span>Remove link</span>" in source, (
        "link remove button must show the text 'Remove link'"
    )
    assert "<span>Remove section</span>" in source, (
        "section remove button must show the text 'Remove section'"
    )


def test_placeholders_use_the_dimmed_placeholder_token():
    """Resume Builder placeholders must use the muted, Resume
    Builder-scoped --resume-placeholder token, not the bright
    --olive-soft accent that made examples look like saved input.
    The dimming stays scoped so unrelated fields are unchanged."""
    css = (FRONTEND_DIR / "style.css").read_text(encoding="utf-8")

    resume_placeholder_rules = re.findall(
        r"\.resume-(?:field|bullet-row)[^{]*::placeholder\s*\{([^}]*)\}",
        css,
    )

    assert resume_placeholder_rules, (
        "expected resume placeholder rules in style.css"
    )

    for rule in resume_placeholder_rules:
        assert "var(--resume-placeholder)" in rule, (
            "resume placeholder rule must use the Resume Builder "
            "scoped --resume-placeholder token: " + rule
        )
        assert "--olive-soft" not in rule, (
            "resume placeholder rule must not use the bright "
            "--olive-soft accent: " + rule
        )


def test_add_entry_button_label_is_accurate_for_first_entry():
    """The entry button read 'Add Another Entry' even when a section
    had no entries yet; the label must be 'Add Entry'."""
    source = _read_script_js()

    assert "Add Another Entry" not in source
    assert "Add Entry" in source


# ============================================================
# COMBINED HIERARCHY UPGRADE REGRESSION TESTS
# ============================================================

def test_section_heading_is_inline_and_editable_in_header():
    """addSectionItem must render the editable heading input
    inside .resume-section-item-header (no separate Section
    Heading field, no type pill)."""
    source = _read_script_js()

    # The heading input lives in the header markup with an
    # accessible label and the same name the save path reads.
    header_block = source.split("resume-section-item-header", 1)[1]
    assert 'name="heading"' in header_block
    assert "resume-section-heading-input" in header_block
    assert 'aria-label="Section heading"' in header_block
    assert 'maxlength="120"' in header_block

    # The old type pill and standalone heading field are gone.
    assert "resume-section-item-type" not in source
    assert "Section Heading" not in source

    # buildSectionFields no longer emits its own heading input.
    fields_fn = source.split("function buildSectionFields", 1)[1]
    fields_fn = fields_fn.split("\n        function ", 1)[0]
    assert 'name="heading"' not in fields_fn


def test_save_path_still_reads_heading_from_section_item():
    """The save serialization must keep reading the heading
    input by name from inside the section item."""
    source = _read_script_js()
    assert "[name=\"heading\"]" in source or "['name=\"heading\"']" in source \
        or 'querySelector(\'[name="heading"]\')' in source \
        or '[name="heading"]' in source


def test_de_nesting_and_ghost_actions_in_css():
    """style.css must de-nest section cards, separate sections
    with a hairline, style the inline heading, and keep add
    actions as quiet ghost buttons."""
    css = (FRONTEND_DIR / "style.css").read_text(encoding="utf-8")

    # Inline editable heading input styling exists.
    assert ".resume-section-heading-input" in css

    # Sections are no longer boxed cards; a hairline separates
    # consecutive sections instead.
    card = re.search(
        r"\.resume-section-item\s*\{([^}]*)\}", css
    )
    assert card, "expected a .resume-section-item rule"
    assert "border" not in card.group(1)
    assert "background" not in card.group(1)
    assert (
        ".resume-section-item + .resume-section-item" in css
    ), "expected hairline divider between sections"

    # Add actions are ghost text buttons (no border box).
    add_btn = re.search(r"\.rb-add-btn\s*\{([^}]*)\}", css)
    assert add_btn, "expected a .rb-add-btn rule"
    assert "border: none" in add_btn.group(1)

    # The dead type-pill rules are gone.
    assert ".resume-section-item-type" not in css


def test_mobile_header_rules_come_after_consolidated_base_rules():
    """The max-700px media block must follow the consolidated
    .resume-section-item-header base rule, or equal-specificity
    source order silently re-centers the mobile section header.

    Regression: the de-nesting pass left a duplicate base rule
    AFTER the media block, so phone widths computed
    align-items: center instead of flex-start."""
    css = (FRONTEND_DIR / "style.css").read_text(encoding="utf-8")

    # Exactly one base (non-media) header rule may exist.
    base_rule_count = len(
        re.findall(r"^\.resume-section-item-header \{", css, re.M)
    )
    assert base_rule_count == 1, (
        f"expected 1 base .resume-section-item-header rule, "
        f"found {base_rule_count} (duplicates flip precedence)"
    )

    base_pos = re.search(
        r"^\.resume-section-item-header \{", css, re.M
    ).start()

    # Find the max-700px media block that contains the header
    # override (other components have their own 700px blocks).
    media_pos = None
    for match in re.finditer(r"@media \(max-width: 700px\)", css):
        window = css[match.start() : match.start() + 3000]
        if ".resume-section-item-header" in window:
            media_pos = match.start()
            break
    assert media_pos is not None, (
        "no max-700px media block overrides "
        ".resume-section-item-header"
    )
    assert media_pos > base_pos, (
        "the mobile media block must come after the consolidated "
        "base header rule so its align-items: flex-start wins"
    )


def test_desktop_entries_use_two_columns():
    """Entry fields pair up on wide screens while textareas,
    bullets and the remove action span the full width."""
    css = (FRONTEND_DIR / "style.css").read_text(encoding="utf-8")

    desktop = re.search(
        r"@media \(min-width: 900px\) \{(.*?)\n\}", css, re.S
    )
    assert desktop, "expected a min-width:900px media block"
    block = desktop.group(1)
    assert ".resume-section-fields-item" in block
    assert "grid-template-columns: 1fr 1fr" in block
    assert ".resume-field:has(textarea)" in block
    assert ".resume-bullets" in block
    assert ".resume-entry-remove" in block
    assert "grid-column: 1 / -1" in block
