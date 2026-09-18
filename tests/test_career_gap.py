import json

import pytest

import career_gap


def test_extract_skills_handles_aliases():
    text = "I build RESTful APIs with Fast API and PostgreSQL."
    skills = career_gap.extract_skills(text)

    assert "REST API" in skills
    assert "FastAPI" in skills
    assert "PostgreSQL" in skills


def test_analyze_skills_finds_matched_and_missing():
    resume = ["Python", "Git"]
    job = ["Python", "FastAPI", "Git"]

    matched, missing = career_gap.analyze_skills(resume, job)

    assert matched == ["Python", "Git"]
    assert missing == ["FastAPI"]


def test_score_is_deterministic():
    assert career_gap.calculate_score(
        ["Python", "Git"],
        ["Python", "FastAPI", "Git", "Docker"]
    ) == 50.0


def test_required_skill_gets_high_priority_without_market_data():
    job = """
    We are looking for a backend developer.

    Required:
    FastAPI
    PostgreSQL

    Preferred:
    Docker
    """

    result = career_gap.calculate_skill_priority(
        "FastAPI",
        job,
        {}
    )

    assert result["importance"] == "Required"
    assert result["market_demand"] is None
    assert result["priority"] == "HIGH"


def test_missing_market_data_is_not_zero():
    assert career_gap.get_market_demand(
        "FastAPI",
        {"python": 66}
    ) is None


def test_preferred_skill_uses_market_evidence_when_available():
    job = """
    Required:
    Python

    Preferred:
    Docker
    """

    result = career_gap.calculate_skill_priority(
        "Docker",
        job,
        {"docker": 60}
    )

    assert result["importance"] == "Preferred"
    assert result["market_demand"] == 60
    assert result["priority"] == "HIGH"


def test_project_skill_is_already_demonstrated():
    project = {
        "name": "Student Management API",
        "description": (
            "A Python backend using FastAPI and PostgreSQL "
            "to manage student records through a REST API."
        ),
    }

    result = career_gap.check_project_compatibility(
        project,
        "FastAPI"
    )

    assert result["compatibility"] == "ALREADY DEMONSTRATED"
    assert result["upgrade"] is None


def test_docker_is_high_for_api_and_database_project():
    project = {
        "name": "Student Management API",
        "description": (
            "A Python backend application using FastAPI and "
            "PostgreSQL to manage student records through a REST API."
        ),
    }

    result = career_gap.check_project_compatibility(
        project,
        "Docker"
    )

    assert result["compatibility"] == "HIGH"
    assert result["upgrade"] is not None


def test_docker_is_low_for_unrelated_project():
    project = {
        "name": "Java Library System",
        "description": (
            "A Java application demonstrating Object-Oriented "
            "Programming, classes, inheritance and data structures."
        ),
    }

    result = career_gap.check_project_compatibility(
        project,
        "Docker"
    )

    assert result["compatibility"] == "LOW"
    assert result["upgrade"] is None
    assert result["resume_evidence"] == []


def test_generate_project_recommendations_covers_projects():
    projects = [
        {
            "name": "API Project",
            "description": "A FastAPI backend with PostgreSQL."
        },
        {
            "name": "Java Project",
            "description": "A Java OOP application."
        },
    ]

    recommendations = career_gap.generate_project_upgrade_recommendations(
        projects,
        ["Docker"]
    )

    assert len(recommendations) == 2
    assert {item["project"] for item in recommendations} == {
        "API Project",
        "Java Project",
    }


def test_run_careergap_produces_core_result(monkeypatch):
    # External services are deliberately mocked.
    monkeypatch.setattr(
        career_gap,
        "get_market_data",
        lambda: {"python": 66, "docker": 3}
    )
    monkeypatch.setattr(
        career_gap,
        "get_github_recommendations",
        lambda *args, **kwargs: []
    )

    resume = "I know Python and Git."
    job = """
    Backend Developer

    Required:
    Python
    FastAPI

    Preferred:
    Docker
    """
    projects = [
        {
            "name": "API Project",
            "description": (
                "A Python backend using FastAPI and PostgreSQL."
            )
        }
    ]

    result = career_gap.run_careergap(
        resume,
        job,
        projects
    )

    assert result["score"] == 33.33
    assert "Python" in result["matched_skills"]
    assert "FastAPI" in result["missing_skills"]
    assert "Docker" in result["missing_skills"]
    assert result["github_recommendations"] == []


def test_validate_projects_rejects_empty_list():
    with pytest.raises(ValueError):
        career_gap.validate_projects([])


def test_validate_projects_rejects_invalid_project():
    bad_projects = [
        {
            "name": "Missing Description"
        }
    ]

    with pytest.raises(ValueError):
        career_gap.validate_projects(bad_projects)


def test_validate_projects_accepts_valid_projects():
    projects = [
        {
            "name": "Test Project",
            "description": "A Python project."
        }
    ]

    career_gap.validate_projects(projects)


def test_validate_text_file_rejects_empty_file(tmp_path):
    file_path = tmp_path / "resume.txt"
    file_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError):
        career_gap.validate_text_file(
            file_path,
            "Resume"
        )


def test_validate_text_file_reads_valid_file(tmp_path):
    file_path = tmp_path / "resume.txt"
    file_path.write_text(
        "Python developer",
        encoding="utf-8"
    )

    result = career_gap.validate_text_file(
        file_path,
        "Resume"
    )

    assert result == "Python developer"


def test_load_input_uses_demo_mode_when_no_user_files_exist(
    monkeypatch,
    tmp_path
):
    resume = tmp_path / "resume.txt"
    job = tmp_path / "job_description.txt"
    projects = tmp_path / "projects.json"

    monkeypatch.setattr(career_gap, "RESUME_FILE", resume)
    monkeypatch.setattr(career_gap, "JOB_FILE", job)
    monkeypatch.setattr(career_gap, "PROJECTS_FILE", projects)

    _, _, _, mode = career_gap.load_careergap_input()

    assert mode == "DEMO"


def test_load_input_rejects_partial_user_input(
    monkeypatch,
    tmp_path
):
    resume = tmp_path / "resume.txt"
    job = tmp_path / "job_description.txt"
    projects = tmp_path / "projects.json"

    resume.write_text(
        "Python developer",
        encoding="utf-8"
    )

    monkeypatch.setattr(career_gap, "RESUME_FILE", resume)
    monkeypatch.setattr(career_gap, "JOB_FILE", job)
    monkeypatch.setattr(career_gap, "PROJECTS_FILE", projects)

    with pytest.raises(FileNotFoundError):
        career_gap.load_careergap_input()


def test_load_input_rejects_invalid_projects_json(
    monkeypatch,
    tmp_path
):
    resume = tmp_path / "resume.txt"
    job = tmp_path / "job_description.txt"
    projects = tmp_path / "projects.json"

    resume.write_text(
        "Python developer",
        encoding="utf-8"
    )
    job.write_text(
        "Required:\nPython",
        encoding="utf-8"
    )
    projects.write_text(
        "{invalid json",
        encoding="utf-8"
    )

    monkeypatch.setattr(career_gap, "RESUME_FILE", resume)
    monkeypatch.setattr(career_gap, "JOB_FILE", job)
    monkeypatch.setattr(career_gap, "PROJECTS_FILE", projects)

    with pytest.raises(ValueError):
        career_gap.load_careergap_input()
