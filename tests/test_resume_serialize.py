import pytest

import resume_serialize


def test_sections_are_serialized_in_provided_order():
    content = {
        "sections": [
            {"heading": "Summary", "items": ["Backend developer."]},
            {"heading": "Experience", "items": ["Built things."]},
            {"heading": "Education", "items": ["BSc Computer Science."]},
        ]
    }

    result = resume_serialize.sections_to_plain_text(content)

    assert result.index("Summary") < result.index("Experience")
    assert result.index("Experience") < result.index("Education")


def test_items_keep_input_order():
    content = {
        "sections": [
            {
                "heading": "Experience",
                "items": ["Zebra role", "Alpha role", "Middle role"],
            }
        ]
    }

    result = resume_serialize.sections_to_plain_text(content)

    assert result.index("Zebra role") < result.index("Alpha role")
    assert result.index("Alpha role") < result.index("Middle role")


def test_entry_fields_render_in_canonical_order():
    content = {
        "sections": [
            {
                "heading": "Experience",
                "items": [
                    {
                        "organization": "Acme",
                        "end": "Present",
                        "title": "Software Engineer",
                        "start": "Jan 2022",
                        "location": "Remote",
                    }
                ],
            }
        ]
    }

    line = resume_serialize.sections_to_plain_text(
        content
    ).splitlines()[1]

    assert line == (
        "Software Engineer, Acme, Remote, Jan 2022 - Present"
    )


def test_bullets_render_below_the_entry_header():
    content = {
        "sections": [
            {
                "heading": "Experience",
                "items": [
                    {
                        "title": "Engineer",
                        "bullets": ["First", "Second"],
                    }
                ],
            }
        ]
    }

    lines = resume_serialize.sections_to_plain_text(
        content
    ).splitlines()

    assert lines[1] == "Engineer"
    assert lines[2] == "- First"
    assert lines[3] == "- Second"


@pytest.mark.parametrize(
    "content",
    [
        None,
        "",
        0,
        [],
        {},
        {"sections": None},
        {"sections": []},
        {"sections": "not-a-list"},
    ],
)
def test_empty_input_produces_empty_string(content):
    assert resume_serialize.sections_to_plain_text(
        content
    ) == ""


def test_sections_without_usable_content_are_dropped():
    content = {
        "sections": [
            {"heading": "Empty", "items": []},
            {"heading": "", "items": []},
            {"items": []},
            {"heading": "Real", "items": ["Kept."]},
        ]
    }

    result = resume_serialize.sections_to_plain_text(content)

    assert result == "Real\nKept."


def test_missing_and_none_fields_are_skipped_not_rendered():
    content = {
        "sections": [
            {
                "heading": "Experience",
                "items": [
                    {
                        "title": "Engineer",
                        "organization": None,
                        "location": "",
                        "start": None,
                        "end": None,
                    }
                ],
            }
        ]
    }

    result = resume_serialize.sections_to_plain_text(
        content
    )

    assert result == "Experience\nEngineer"
    assert "None" not in result


def test_whitespace_is_collapsed_and_trimmed():
    content = {
        "sections": [
            {
                "heading": "  Experience  ",
                "items": [
                    {
                        "title": "Engineer",
                        "summary": "Line one\n\n   Line two",
                    }
                ],
            }
        ]
    }

    lines = resume_serialize.sections_to_plain_text(
        content
    ).splitlines()

    assert lines[0] == "Experience"
    assert lines[2] == "Line one Line two"


def test_empty_bullets_are_dropped():
    content = {
        "sections": [
            {
                "heading": "Experience",
                "items": [
                    {
                        "title": "Engineer",
                        "bullets": ["Real", "", "   ", None, 42],
                    }
                ],
            }
        ]
    }

    lines = resume_serialize.sections_to_plain_text(
        content
    ).splitlines()

    assert lines == ["Experience", "Engineer", "- Real", "- 42"]


def test_string_items_and_section_text_are_supported():
    content = {
        "sections": [
            {
                "heading": "Skills",
                "text": "Languages",
                "items": ["Python", "Go"],
            }
        ]
    }

    result = resume_serialize.sections_to_plain_text(content)

    assert result == "Skills\nLanguages\nPython\nGo"


def test_single_bullet_string_is_accepted():
    content = {
        "sections": [
            {
                "heading": "Experience",
                "items": [{"title": "Engineer", "bullets": "Only one"}],
            }
        ]
    }

    assert resume_serialize.sections_to_plain_text(
        content
    ).splitlines()[-1] == "- Only one"


@pytest.mark.parametrize(
    "bad_item",
    [None, 7, ["nested", "list"], {"bullets": {"a": 1}}],
)
def test_malformed_items_do_not_raise(bad_item):
    content = {
        "sections": [
            {"heading": "Experience", "items": [bad_item, "Real"]}
        ]
    }

    result = resume_serialize.sections_to_plain_text(content)

    assert "Real" in result


def test_malformed_sections_do_not_raise():
    content = {
        "sections": [
            None,
            "not-a-section",
            {"heading": "Experience", "items": ["Real"]},
        ]
    }

    assert "Real" in resume_serialize.sections_to_plain_text(
        content
    )


def test_serialization_is_deterministic():
    content = {
        "sections": [
            {"heading": "Skills", "items": ["Python", "Go", "Rust"]}
        ]
    }

    first = resume_serialize.sections_to_plain_text(content)
    second = resume_serialize.sections_to_plain_text(content)

    assert first == second


def test_plain_text_keeps_technology_names_intact():
    content = {
        "sections": [
            {
                "heading": "Skills",
                "items": ["C++", "C#", "Node.js", "CI/CD"],
            }
        ]
    }

    result = resume_serialize.sections_to_plain_text(content)

    assert "C++" in result
    assert "C#" in result
    assert "Node.js" in result
    assert "CI/CD" in result