import pytest

from ats_readiness import MAX_SCORES, score_ats_readiness, _date


def doc(sections=None, contact=None, summary="A concise summary of relevant engineering work."):
    return {
        "contact": contact if contact is not None else {
            "full_name": "Test Candidate", "email": "candidate@example.com",
            "phone": "+1 555 123 4567", "location": "Remote",
            "links": [{"label": "GitHub", "url": "https://github.com/example"}],
        },
        "summary": summary,
        "sections": sections if sections is not None else [
            {"type": "education", "heading": "Education", "items": [
                {"title": "BTech Computer Science", "organization": "Example University", "start": "2022", "end": "2026"}
            ]},
            {"type": "skills", "heading": "Skills", "items": ["Python", "FastAPI", "PostgreSQL", "Docker"]},
            {"type": "projects", "heading": "Projects", "items": [
                {"title": "CareerGap", "organization": "Python, FastAPI", "text": "Built a resume tool that enabled clearer skill-gap analysis.",
                 "bullets": ["Built API endpoints using FastAPI and PostgreSQL.", "Improved maintainability through focused tests."]}
            ]},
            {"type": "experience", "heading": "Experience", "items": [
                {"title": "Developer Intern", "organization": "Example Co", "start": "Jan 2025", "end": "Present",
                 "bullets": ["Built API endpoints using FastAPI and PostgreSQL.", "Improved authentication reliability with token validation.",
                             "Automated regression tests, reducing manual verification by 30 percent."]}
            ]},
        ],
    }


def test_weights_total_100_and_category_caps():
    result = score_ats_readiness(doc())
    assert sum(MAX_SCORES.values()) == 100
    assert result["max_score"] == 100 and 0 <= result["score"] <= 100
    assert set(result["categories"]) == set(MAX_SCORES)
    for key, maximum in MAX_SCORES.items():
        assert result["categories"][key]["max_score"] == maximum
        assert 0 <= result["categories"][key]["score"] <= maximum


def test_missing_contact_has_actionable_fixes():
    category = score_ats_readiness(doc(contact={}))["categories"]["contact_completeness"]
    assert category["score"] == 0
    assert category["fixes"]


def test_student_projects_without_experience_get_structure_credit():
    result = score_ats_readiness(doc(sections=[
        {"type": "education", "heading": "Education", "items": [{"title": "BTech", "organization": "University", "end": "2026"}]},
        {"type": "skills", "heading": "Skills", "items": ["Python", "FastAPI", "SQL"]},
        {"type": "projects", "heading": "Projects", "items": [
            {"title": "One", "organization": "Python", "text": "Built an API that enabled reliable access.", "bullets": ["Implemented API endpoints."]},
            {"title": "Two", "organization": "SQL", "text": "Automated data processing and reduced manual work.", "bullets": ["Automated processing using SQL."]},
        ]},
    ]))
    assert result["categories"]["resume_structure"]["score"] == 16


def test_duplicate_skills_are_reported():
    category = score_ats_readiness(doc(sections=[{"type": "skills", "heading": "Skills", "items": ["Python", "python", "FastAPI"]}]))["categories"]["skills_quality_organization"]
    assert any("duplicate" in x.lower() for x in category["issues"])


def test_qualitative_outcome_counts_without_number():
    result = score_ats_readiness(doc(sections=[{"type": "projects", "heading": "Projects", "items": [
        {"title": "API", "bullets": ["Improved deployment reliability using Docker and FastAPI."]}
    ]}]))
    assert result["categories"]["content_quality"]["score"] > 0


def test_jd_match_is_separate():
    result = score_ats_readiness(doc())
    assert result["jd_match"] is None
    assert "separate" in result["jd_match_note"]


@pytest.mark.parametrize(("value", "expected"), [
    ("present", "Present"), ("current", "Present"), ("jan 2022", "Jan 2022"),
    ("January 2022", "Jan 2022"), ("2022", "2022"), ("unknown date", "unknown date"),
])
def test_date_normalization(value, expected):
    assert _date(value) == expected


def test_empty_input_is_safe():
    result = score_ats_readiness(None)
    assert 0 <= result["score"] <= 100
    assert result["categories"]["contact_completeness"]["score"] == 0
