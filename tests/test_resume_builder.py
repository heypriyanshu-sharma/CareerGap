"""Tests for the ATS-friendly resume builder domain logic.

These cover content validation, plain-text serialization, and job
description comparison. They are pure and need no database or
environment variables.
"""

import pytest

import resume_builder
from resume_builder import (
    ResumeValidationError,
    build_plain_text,
    compare_with_job_description,
    empty_document,
    normalize_content,
)


# ============================================================
# FIXTURES
# ============================================================

def sample_content() -> dict:
    return {
        "contact": {
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "+44 20 7946 0000",
            "location": "London, UK",
            "links": [
                {
                    "label": "GitHub",
                    "url": "https://github.com/ada",
                }
            ],
        },
        "summary": "Backend engineer focused on data platforms.",
        "sections": [
            {
                "type": "skills",
                "heading": "Skills",
                "items": [
                    "Python",
                    "PostgreSQL",
                ],
            },
            {
                "type": "experience",
                "heading": "Experience",
                "items": [
                    {
                        "title": "Backend Engineer",
                        "organization": "Analytical Engines",
                        "location": "London",
                        "start": "2022",
                        "end": "Present",
                        "bullets": [
                            "Built a reporting API in Python."
                        ],
                    }
                ],
            },
        ],
    }


# ============================================================
# CONTENT VALIDATION
# ============================================================

def test_empty_content_is_valid():
    document = normalize_content({})

    assert document == empty_document()


def test_none_content_is_valid():
    assert normalize_content(None) == empty_document()


def test_contact_is_normalized():
    document = normalize_content(sample_content())

    assert document["contact"]["full_name"] == "Ada Lovelace"
    assert document["contact"]["links"] == [
        {
            "label": "GitHub",
            "url": "https://github.com/ada",
        }
    ]


def test_unknown_contact_fields_are_discarded():
    document = normalize_content(
        {
            "contact": {
                "full_name": "Ada",
                "secret_token": "do-not-store",
            }
        }
    )

    assert "secret_token" not in document["contact"]


def test_unknown_item_fields_are_discarded():
    document = normalize_content(
        {
            "sections": [
                {
                    "type": "experience",
                    "items": [
                        {
                            "title": "Engineer",
                            "unverified_claim": "invented",
                        }
                    ],
                }
            ]
        }
    )

    item = document["sections"][0]["items"][0]

    assert item == {"title": "Engineer"}


def test_summary_alias_is_stored_as_text():
    document = normalize_content(
        {
            "sections": [
                {
                    "type": "custom",
                    "items": [
                        {
                            "title": "Project",
                            "summary": "Did the thing.",
                        }
                    ],
                }
            ]
        }
    )

    item = document["sections"][0]["items"][0]

    assert item["text"] == "Did the thing."


def test_blank_entries_are_dropped_not_filled_in():
    document = normalize_content(
        {
            "sections": [
                {
                    "type": "skills",
                    "items": [
                        "Python",
                        "   ",
                        None,
                    ],
                }
            ]
        }
    )

    assert document["sections"][0]["items"] == ["Python"]


def test_heading_only_section_is_kept_but_not_serialized():
    """The editor keeps the heading; the ATS text never gains a
    dangling label with no body under it."""
    document = normalize_content(
        {
            "sections": [
                {
                    "type": "education",
                    "heading": "Education",
                    "items": [],
                }
            ]
        }
    )

    assert document["sections"][0]["heading"] == "Education"

    assert "Education" not in build_plain_text(document)


def test_section_order_is_preserved():
    document = normalize_content(
        {
            "sections": [
                {
                    "type": "projects",
                    "items": [{"title": "A"}],
                },
                {
                    "type": "skills",
                    "items": ["Python"],
                },
                {
                    "type": "experience",
                    "items": [{"title": "B"}],
                },
            ]
        }
    )

    assert [
        section["type"]
        for section in document["sections"]
    ] == ["projects", "skills", "experience"]


def test_bullet_string_is_accepted_as_one_bullet():
    document = normalize_content(
        {
            "sections": [
                {
                    "type": "custom",
                    "items": [
                        {
                            "title": "Project",
                            "bullets": "Shipped it.",
                        }
                    ],
                }
            ]
        }
    )

    assert document["sections"][0]["items"][0]["bullets"] == [
        "Shipped it."
    ]


def test_non_object_content_is_rejected():
    with pytest.raises(ResumeValidationError):

        normalize_content("resume text")


def test_non_list_sections_are_rejected():
    with pytest.raises(ResumeValidationError):

        normalize_content({"sections": "skills"})


def test_missing_section_type_is_rejected():
    with pytest.raises(ResumeValidationError):

        normalize_content(
            {
                "sections": [
                    {"heading": "Skills"}
                ]
            }
        )


def test_unsupported_section_type_is_rejected():
    with pytest.raises(ResumeValidationError):

        normalize_content(
            {
                "sections": [
                    {"type": "references"}
                ]
            }
        )


def test_non_string_skill_is_rejected():
    with pytest.raises(ResumeValidationError):

        normalize_content(
            {
                "sections": [
                    {
                        "type": "skills",
                        "items": [{"name": "Python"}],
                    }
                ]
            }
        )


def test_non_object_entry_is_rejected():
    with pytest.raises(ResumeValidationError):

        normalize_content(
            {
                "sections": [
                    {
                        "type": "experience",
                        "items": ["Engineer"],
                    }
                ]
            }
        )


# ============================================================
# OVERSIZED INPUT
# ============================================================

def test_oversized_name_is_rejected():
    with pytest.raises(ResumeValidationError):

        normalize_content(
            {
                "contact": {
                    "full_name": "A" * 500
                }
            }
        )


def test_oversized_summary_is_rejected():
    with pytest.raises(ResumeValidationError):

        normalize_content(
            {"summary": "A" * 5000}
        )


def test_too_many_sections_are_rejected():
    with pytest.raises(ResumeValidationError):

        normalize_content(
            {
                "sections": [
                    {"type": "skills", "items": ["Python"]}
                    for _ in range(20)
                ]
            }
        )


def test_too_many_items_are_rejected():
    with pytest.raises(ResumeValidationError):

        normalize_content(
            {
                "sections": [
                    {
                        "type": "skills",
                        "items": [
                            f"Skill {index}"
                            for index in range(50)
                        ],
                    }
                ]
            }
        )


def test_too_many_bullets_are_rejected():
    with pytest.raises(ResumeValidationError):

        normalize_content(
            {
                "sections": [
                    {
                        "type": "custom",
                        "items": [
                            {
                                "title": "Project",
                                "bullets": [
                                    f"Bullet {index}"
                                    for index in range(30)
                                ],
                            }
                        ],
                    }
                ]
            }
        )


def test_too_many_links_are_rejected():
    with pytest.raises(ResumeValidationError):

        normalize_content(
            {
                "contact": {
                    "links": [
                        {"label": "L", "url": "https://x"}
                        for _ in range(20)
                    ]
                }
            }
        )


def test_oversized_bullet_is_rejected():
    with pytest.raises(ResumeValidationError):

        normalize_content(
            {
                "sections": [
                    {
                        "type": "custom",
                        "items": [
                            {
                                "title": "Project",
                                "bullets": ["A" * 2000],
                            }
                        ],
                    }
                ]
            }
        )


def test_whole_document_length_is_capped():
    within_limit = {
        "sections": [
            {
                "type": "custom",
                "items": [
                    {
                        "title": f"Entry {index}",
                        "text": "B" * 1000,
                    }
                    for index in range(40)
                ]
            }
        ]
    }

    assert len(build_plain_text(normalize_content(within_limit))) < 60_000

    oversized = {
        "sections": [
            {
                "type": "custom",
                "items": [
                    {
                        "title": f"Entry {index}",
                        "text": "B" * 4000,
                        "bullets": [
                            "C" * 1000
                            for _ in range(20)
                        ],
                    }
                    for index in range(40)
                ]
            }
        ]
    }

    with pytest.raises(ResumeValidationError):

        normalize_content(oversized)


# ============================================================
# PLAIN TEXT SERIALIZATION
# ============================================================

def test_plain_text_starts_with_contact_details():
    text = build_plain_text(
        normalize_content(sample_content())
    )

    lines = text.splitlines()

    # resume_serialize collapses whitespace, so the header is a single
    # ATS-friendly line rather than a stacked contact block.
    assert lines[0] == (
        "Ada Lovelace ada@example.com | +44 20 7946 0000 | "
        "London, UK | GitHub: https://github.com/ada"
    )


def test_plain_text_includes_summary_and_sections():
    text = build_plain_text(
        normalize_content(sample_content())
    )

    assert "Backend engineer focused on data platforms." in text
    assert "Skills" in text
    assert "Experience" in text
    assert "Analytical Engines" in text


def test_plain_text_omits_empty_fields():
    text = build_plain_text(
        normalize_content(
            {
                "contact": {"full_name": "Ada"},
            }
        )
    )

    assert text == "Ada"


def test_plain_text_of_empty_document_is_empty():
    assert build_plain_text(empty_document()) == ""


def test_plain_text_of_non_document_is_empty():
    assert build_plain_text("not a document") == ""


def test_plain_text_matches_resume_serialize_shape():
    """The builder must reuse the existing serializer's ordering."""
    from resume_serialize import sections_to_plain_text

    document = normalize_content(sample_content())

    expected = sections_to_plain_text(
        {
            "sections": [
                {
                    "text": (
                        "Ada Lovelace\n"
                        "ada@example.com | +44 20 7946 0000 | "
                        "London, UK | GitHub: https://github.com/ada"
                    )
                },
                {
                    "heading": "Summary",
                    "text": document["summary"],
                },
                *document["sections"],
            ]
        }
    )

    assert build_plain_text(document) == expected


# ============================================================
# JOB DESCRIPTION COMPARISON
# ============================================================

JOB_DESCRIPTION = """
We are hiring a backend engineer.
Requirements:
- Strong Python experience
- PostgreSQL
- Docker
Nice to have: Kubernetes
"""


def test_comparison_reports_supported_and_missing_keywords():
    document = normalize_content(sample_content())

    result = compare_with_job_description(
        build_plain_text(document),
        JOB_DESCRIPTION,
    )

    supported_terms = [
        entry["term"].lower()
        for entry in result["supported"]
    ]

    assert "python" in supported_terms
    assert "postgresql" in supported_terms
    assert result["has_job_description"] is True
    assert result["has_resume_text"] is True
    assert result["total"] == (
        len(result["supported"])
        + len(result["missing"])
    )


def test_comparison_does_not_invent_matches():
    document = normalize_content(
        {"contact": {"full_name": "Ada"}}
    )

    result = compare_with_job_description(
        build_plain_text(document),
        JOB_DESCRIPTION,
    )

    assert result["supported"] == []
    assert result["missing"]
    assert all(
        "term" in entry
        for entry in result["missing"]
    )


def test_comparison_matches_whole_tokens_only():
    document = normalize_content(
        {
            "sections": [
                {
                    "type": "skills",
                    "items": ["Go"],
                }
            ]
        }
    )

    result = compare_with_job_description(
        build_plain_text(document),
        "Experience with Go and Django required.",
    )

    supported_terms = [
        entry["term"].lower()
        for entry in result["supported"]
    ]

    assert "go" in supported_terms
    assert "django" not in supported_terms


def test_comparison_is_case_and_punctuation_insensitive():
    document = normalize_content(
        {
            "sections": [
                {
                    "type": "skills",
                    "items": ["Node.js"],
                }
            ]
        }
    )

    result = compare_with_job_description(
        build_plain_text(document),
        "We use node.js on the backend.",
    )

    assert result["supported"]


def test_comparison_with_empty_job_description_is_empty():
    document = normalize_content(sample_content())

    result = compare_with_job_description(
        build_plain_text(document),
        "",
    )

    assert result["total"] == 0
    assert result["has_job_description"] is False
    assert result["supported"] == []


def test_comparison_with_empty_resume_is_empty():
    result = compare_with_job_description(
        "",
        JOB_DESCRIPTION,
    )

    assert result["total"] == 0
    assert result["has_resume_text"] is False
    assert result["supported"] == []


def test_comparison_with_job_description_without_keywords():
    result = compare_with_job_description(
        "Some resume text.",
        "Apply today.",
    )

    assert result["has_job_description"] is True
    assert result["total"] == 0
    assert result["supported"] == []
    assert result["missing"] == []


def test_comparison_with_non_string_input_is_safe():
    result = compare_with_job_description(
        None,
        None,
    )

    assert result["total"] == 0


def test_comparison_respects_keyword_limit():
    result = compare_with_job_description(
        "Python and PostgreSQL and Docker.",
        JOB_DESCRIPTION,
        limit=1,
    )

    assert result["total"] <= 1


def test_comparison_uses_existing_ats_extraction():
    from ats_match import extract_job_keywords

    result = compare_with_job_description(
        "Python PostgreSQL",
        JOB_DESCRIPTION,
    )

    expected_terms = {
        keyword["term"]
        for keyword in extract_job_keywords(
            JOB_DESCRIPTION
        )
    }

    reported_terms = {
        entry["term"]
        for entry in (
            result["supported"]
            + result["missing"]
        )
    }

    assert reported_terms == expected_terms


def test_limits_are_documented_constants():
    assert resume_builder.MAX_SECTIONS > 0
    assert resume_builder.MAX_ITEMS_PER_SECTION > 0
    assert resume_builder.MAX_PLAIN_TEXT_LENGTH > 0