import pytest
from ats_match import calculate_ats_scorecard, extract_job_keywords


def test_ats_scorecard_complete_resume():
    """A complete resume with all sections should score well."""
    resume = """
    John Doe
    john@example.com | +1-555-123-4567 | linkedin.com/in/johndoe | github.com/johndoe

    SUMMARY
    Experienced Python developer with 5 years building scalable web applications.

    SKILLS
    Python, FastAPI, PostgreSQL, Docker, AWS, React, TypeScript, SQL, Git

    EXPERIENCE
    Senior Software Engineer at TechCorp (2021-Present)
    - Built REST APIs with FastAPI handling 1M+ requests/day
    - Improved API latency by 40%
    - Mentored 3 junior engineers

    EDUCATION
    B.S. Computer Science, Stanford University (2015-2019)

    PROJECTS
    Open Source API Tool - CLI tool for API testing with 500+ GitHub stars
    Personal Website - Portfolio site built with Next.js and Tailwind, deployed on Vercel

    CERTIFICATIONS
    AWS Solutions Architect (2022)
    Kubernetes Administrator (2021)
    """

    job = """
    We are looking for a Senior Backend Engineer with strong Python and FastAPI skills.
    Required: Python, FastAPI, PostgreSQL, Docker, AWS
    Preferred: React, TypeScript, Kubernetes, GraphQL
    """

    projects = [
        {'name': 'Open Source API Tool', 'description': 'CLI tool for API testing', 'bullets': ['Built with Python', '500+ stars']},
        {'name': 'Personal Website', 'description': 'Portfolio site', 'bullets': ['Next.js', 'Deployed on Vercel']}
    ]

    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, projects)

    assert scorecard["score"] >= 80
    assert scorecard["label"] in ["Strong", "Excellent"]
    assert "breakdown" in scorecard
    assert len(scorecard["breakdown"]) == 4
    assert all("dimension" in d and "awarded" in d and "max" in d for d in scorecard["breakdown"])
    assert "reasons" in scorecard
    assert "improvements" in scorecard
    assert "disclaimer" in scorecard
    assert "heuristic" in scorecard["disclaimer"].lower()


def test_ats_scorecard_missing_required_keywords():
    """Resume missing required keywords should score lower."""
    resume = """
    Jane Smith
    jane@example.com | linkedin.com/in/janesmith
    SUMMARY
    Developer with 3 years experience.
    SKILLS
    Python, React
    EXPERIENCE
    Developer at Corp (2020-Present)
    - Built web applications
    EDUCATION
    B.S. Computer Science, University (2018-2022)
    """

    job = """
    Required: Python, FastAPI, PostgreSQL, Docker
    Preferred: React, AWS
    """

    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, None)

    assert scorecard["score"] < 70
    assert any("required" in r.lower() for r in scorecard["reasons"])
    assert any("required" in i.lower() for i in scorecard["improvements"])


def test_ats_scorecard_student_with_projects():
    """Student resume with projects but no professional experience."""
    resume = """
    Alex Student
    alex@university.edu | github.com/alexstudent
    SUMMARY
    Computer Science student seeking internship.
    EDUCATION
    B.S. Computer Science, University (2022-2026), GPA: 3.8
    SKILLS
    Python, Java, JavaScript, SQL, Git
    PROJECTS
    Task Manager - Full-stack app with React and Node.js, deployed on AWS
    Data Visualizer - Python backend with D3.js frontend
    """

    job = """
    Required: Python, JavaScript
    Preferred: React, AWS, Docker
    """

    projects = [
        {"name": "Task Manager", "description": "Full-stack app", "bullets": ["React + Node.js", "Deployed on AWS"]},
        {"name": "Data Visualizer", "description": "Python backend with D3.js", "bullets": ["Python backend", "React frontend"]}
    ]

    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, projects)

    assert scorecard["score"] >= 60
    assert scorecard["label"] in ["Fair", "Strong", "Excellent"]
    # Should not penalize for lack of professional experience when projects exist
    assert not any("experience" in r.lower() for r in scorecard["reasons"])


def test_ats_scorecard_keyword_stuffing_penalty():
    """Excessive repetition of the same skill should be penalized."""
    resume = """
    John Doe
    john@example.com | linkedin.com/in/johndoe
    SUMMARY
    Python developer with Python Python Python Python Python Python Python Python experience.
    SKILLS
    Python Python Python Python Python Python Python Python
    EXPERIENCE
    Python developer doing Python Python Python Python Python Python Python Python
    """

    job = """
    Required: Python
    """

    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, None)

    assert scorecard["score"] < 100
    assert any("stuffing" in r.lower() for r in scorecard["reasons"])


def test_ats_scorecard_git_not_stuffed_in_github():
    """Git keyword should not be flagged as stuffed when only appearing in GitHub."""
    resume = """
    Jane Doe
    jane@example.com | github.com/janedoe
    SKILLS
    Python, Git
    EXPERIENCE
    Developer at Corp
    """

    job = """
    Required: Python, Git
    """

    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, None)

    assert not any("stuffing" in r.lower() for r in scorecard["reasons"])
    assert "Git" not in " ".join(scorecard["reasons"]) or "stuffing" not in " ".join(scorecard["reasons"])


def test_ats_scorecard_short_resume_penalty():
    """Very short resume should be penalized."""
    resume = "John Doe\njohn@example.com\nSKILLS\nPython"
    job = "Required: Python"
    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, None)
    assert scorecard["score"] < 100
    assert any("short" in r.lower() for r in scorecard["reasons"])


def test_ats_scorecard_missing_contact_info():
    """Missing contact info should be penalized."""
    resume = "John Doe\nSKILLS\nPython, FastAPI"
    job = "Required: Python, FastAPI"
    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, None)
    assert any("contact" in r.lower() for r in scorecard["reasons"])


def test_ats_scorecard_deterministic():
    """Identical inputs should produce identical results."""
    resume = "John Doe\njohn@example.com\nSKILLS\nPython, FastAPI\nEXPERIENCE\nDeveloper"
    job = "Required: Python, FastAPI"
    projects = [{"name": "Project", "description": "Desc", "bullets": ["bullet"]}]

    job_keywords = extract_job_keywords("Required: Python, FastAPI")

    scorecard1 = calculate_ats_scorecard(resume, "Required: Python, FastAPI", extract_job_keywords("Required: Python, FastAPI"), projects)
    scorecard2 = calculate_ats_scorecard(resume, "Required: Python, FastAPI", extract_job_keywords("Required: Python, FastAPI"), projects)

    assert scorecard1["score"] == scorecard2["score"]
    assert scorecard1["label"] == scorecard2["label"]
    assert scorecard1["reasons"] == scorecard2["reasons"]
    assert scorecard1["improvements"] == scorecard2["improvements"]


def test_ats_scorecard_handles_empty_job_keywords():
    """Empty job keywords should not crash."""
    resume = "John Doe\njohn@example.com\nSKILLS\nPython"
    job_keywords = []
    scorecard = calculate_ats_scorecard(resume, "Job", job_keywords, None)
    assert "score" in scorecard
    assert "label" in scorecard
    assert "breakdown" in scorecard


def test_ats_scorecard_score_bands():
    """Verify score band labels are correct."""
    # High score - complete resume with all required keywords
    high_score_resume = """
    John Doe
    john@example.com | +1-555-123-4567 | linkedin.com/in/johndoe | github.com/johndoe

    SUMMARY
    Experienced Python developer with 5 years building scalable web applications.

    SKILLS
    Python, FastAPI, PostgreSQL, Docker, AWS

    EXPERIENCE
    Senior Software Engineer at TechCorp (2021-Present)
    - Built REST APIs with FastAPI handling 1M+ requests/day
    - Improved API latency by 40%

    EDUCATION
    B.S. Computer Science, Stanford University (2015-2019)

    PROJECTS
    Open Source API Tool - CLI tool for API testing with 500+ GitHub stars

    CERTIFICATIONS
    AWS Solutions Architect (2022)
    """
    high_score_job = "Required: Python, FastAPI, PostgreSQL, Docker, AWS"
    high_score_job_keywords = extract_job_keywords(high_score_job)
    scorecard = calculate_ats_scorecard(high_score_resume, high_score_job, high_score_job_keywords, None)
    assert scorecard["label"] in ["Strong", "Excellent"], f"Expected Strong/Excellent, got {scorecard['label']} (score: {scorecard['score']})"

    # Very low score
    scorecard = calculate_ats_scorecard("John\nSKILLS\nPython", "Required: Python, FastAPI, PostgreSQL, Docker, AWS, React, Kubernetes", extract_job_keywords("Required: Python, FastAPI, PostgreSQL, Docker, AWS, React, Kubernetes"), None)
    assert scorecard["label"] in ["Needs Improvement", "Weak"]


def test_deterministic_output():
    """Identical inputs should produce identical results."""
    resume = "John Doe\njohn@example.com\nSKILLS\nPython, FastAPI\nEXPERIENCE\nDeveloper"
    job = "Required: Python, FastAPI"
    projects = [{"name": "Project", "description": "Desc", "bullets": ["bullet"]}]
    job_keywords = extract_job_keywords("Required: Python, FastAPI")
    
    scorecard1 = calculate_ats_scorecard(resume, "Required: Python, FastAPI", extract_job_keywords("Required: Python, FastAPI"), projects)
    scorecard2 = calculate_ats_scorecard(resume, "Required: Python, FastAPI", extract_job_keywords("Required: Python, FastAPI"), projects)
    
    assert scorecard1["score"] == scorecard2["score"]
    assert scorecard1["label"] == scorecard2["label"]
    assert scorecard1["reasons"] == scorecard2["reasons"]
    assert scorecard1["improvements"] == scorecard2["improvements"]
    assert scorecard1["breakdown"] == scorecard2["breakdown"]


# ============================================================
# REGRESSION TESTS FOR NEW FIXES
# ============================================================

def test_job_keywords_varied_required_headings():
    """Job descriptions with varied required heading formats should be recognized."""
    job_descriptions = [
        "Required: Python, FastAPI",
        "Requirements: Python, FastAPI",
        "Required Skills: Python, FastAPI",
        "Must Have: Python, FastAPI",
        "Must-Haves: Python, FastAPI",
        "Mandatory: Python, FastAPI",
        "Essential: Python, FastAPI",
        "Qualifications: Python, FastAPI",
        "Required: Python, FastAPI\nPreferred: React",
    ]
    
    for job in job_descriptions:
        job_keywords = extract_job_keywords(job)
        required_terms = {kw["term"] for kw in job_keywords if kw["importance"] == "Required"}
        assert "Python" in required_terms, f"Failed for job: {job}"
        assert "FastAPI" in required_terms, f"Failed for job: {job}"


def test_job_keywords_varied_preferred_headings():
    """Job descriptions with varied preferred heading formats should be recognized."""
    job_descriptions = [
        "Preferred: React, TypeScript",
        "Preferred Skills: React, TypeScript",
        "Nice to Have: React, TypeScript",
        "Nice-to-Have: React, TypeScript",
        "Desired: React, TypeScript",
        "Bonus: React, TypeScript",
        "Good to Have: React, TypeScript",
        "Preferred Qualifications: React, TypeScript",
        "Desired Qualifications: React, TypeScript",
    ]
    
    for job in job_descriptions:
        job_keywords = extract_job_keywords(job)
        preferred_terms = {kw["term"] for kw in job_keywords if kw["importance"] == "Preferred"}
        assert "React" in preferred_terms, f"Failed for job: {job}"
        assert "TypeScript" in preferred_terms, f"Failed for job: {job}"


def test_job_keywords_inline_required_preferred():
    """Inline Required:/Preferred: markers in job text should be recognized."""
    job = """
    We are looking for a Senior Backend Engineer with strong Python and FastAPI skills.
    Required: Python, FastAPI, PostgreSQL, Docker, AWS
    Preferred: React, TypeScript, Kubernetes, GraphQL
    Experience with CI/CD pipelines and mentoring junior engineers is a plus.
    """
    job_keywords = extract_job_keywords(job)
    
    required_terms = {kw["term"] for kw in job_keywords if kw["importance"] == "Required"}
    preferred_terms = {kw["term"] for kw in job_keywords if kw["importance"] == "Preferred"}
    
    # Required skills from inline markers should be detected
    assert "Python" in required_terms
    assert "FastAPI" in required_terms
    assert "PostgreSQL" in required_terms
    assert "Docker" in required_terms
    assert "AWS" in required_terms
    
    # Preferred skills from inline markers should be detected
    assert "React" in preferred_terms
    assert "TypeScript" in preferred_terms
    assert "Kubernetes" in preferred_terms
    assert "GraphQL" in preferred_terms


def test_section_detection_variants():
    """Resume section detection should recognize common variants."""
    from ats_match import (
        _has_skills_section, _has_summary_section, _has_experience_section,
        _has_education_section, _has_projects_section, _has_certifications_section,
        _count_resume_sections
    )
    
    resume = """
    John Doe
    john@example.com | +1-555-123-4567 | linkedin.com/in/johndoe | github.com/johndoe

    PROFESSIONAL SUMMARY
    Experienced Python developer with 5 years building scalable web applications.

    TECHNICAL SKILLS
    Python, FastAPI, PostgreSQL, Docker, AWS, React, TypeScript, SQL, Git

    WORK EXPERIENCE
    Senior Software Engineer at TechCorp (2021-Present)
    - Built REST APIs with FastAPI handling 1M+ requests/day
    - Improved API latency by 40%
    - Mentored 3 junior engineers

    EDUCATION & CERTIFICATIONS
    B.S. Computer Science, Stanford University (2015-2019)

    SELECTED PROJECTS
    Open Source API Tool - CLI tool for API testing with 500+ GitHub stars
    Personal Website - Portfolio site built with Next.js and Tailwind, deployed on Vercel

    CERTIFICATIONS & LICENSES
    AWS Solutions Architect (2022)
    Kubernetes Administrator (2021)
    """
    
    sections = _count_resume_sections(resume)
    
    # All sections should be detected
    assert sections["summary"], "Professional Summary not detected"
    assert sections["skills"], "Technical Skills not detected"
    assert sections["experience"], "Work Experience not detected"
    assert sections["education"], "Education & Certifications not detected"
    assert sections["projects"], "Selected Projects not detected"
    assert sections["certifications"], "Certifications & Licenses not detected"
    assert sections["contact"], "Contact not detected"
    
    # All 7 sections should be found
    assert sum(1 for v in sections.values() if v) == 7, "Not all sections detected"


def test_keyword_stuffing_common_tech_skills_not_flagged():
    """Common tech skills appearing many times should not be flagged as stuffing."""
    resume = """
    John Doe
    john@example.com | +1-555-123-4567 | linkedin.com/in/johndoe | github.com/johndoe

    SUMMARY
    Experienced Python developer with 5 years building scalable web applications using Python, SQL, and React.

    SKILLS
    Python, SQL, React, Docker, AWS, Git, GitHub, Linux, JavaScript, TypeScript

    EXPERIENCE
    Senior Software Engineer at TechCorp (2021-Present)
    - Built REST APIs with Python and FastAPI handling 1M+ requests/day
    - Improved API latency by 40% using Python and SQL optimizations
    - Mentored 3 junior engineers in Python and React best practices
    - Designed SQL schemas and optimized React components

    EDUCATION
    B.S. Computer Science, Stanford University (2015-2019)

    PROJECTS
    Open Source API Tool - CLI tool for API testing with 500+ GitHub stars
    Personal Website - Portfolio site built with Next.js and Tailwind, deployed on Vercel

    CERTIFICATIONS
    AWS Solutions Architect (2022)
    Kubernetes Administrator (2021)
    """
    
    job = "Required: Python, SQL, React, Docker, AWS"
    job_keywords = extract_job_keywords(job)
    projects = [
        {'name': 'Project A', 'description': 'Desc', 'bullets': ['Built with Python']},
    ]
    
    scorecard = calculate_ats_scorecard(
        "John Doe\njohn@example.com | +1-555-123-4567 | linkedin.com/in/johndoe | github.com/johndoe\n\nSUMMARY\nExperienced Python developer.\n\nSKILLS\nPython, SQL, React, Docker, AWS, Git, GitHub\n\nEXPERIENCE\nSenior Engineer at TechCorp (2021-Present)\n- Built REST APIs with Python and FastAPI\n- Used SQL for database optimization\n- Worked with React and TypeScript\n\nEDUCATION\nB.S. CS, Stanford\n\nPROJECTS\nProject A\n\nCERTIFICATIONS\nAWS Cert (2022)",
        "Required: Python, SQL, React, Docker, AWS",
        extract_job_keywords("Required: Python, SQL, React, Docker, AWS"),
        projects
    )
    
    # Should not have stuffing warning for common tech skills
    stuffing_reasons = [r for r in scorecard["reasons"] if "stuffing" in r.lower()]
    assert not stuffing_reasons, f"Common tech skills flagged as stuffing: {stuffing_reasons}"


def test_common_tech_skills_not_stuffed_in_github():
    """GitHub URL should not cause Git to be flagged as stuffed."""
    resume = """
    Jane Doe
    jane@example.com | github.com/janedoe
    SKILLS
    Python, Git
    EXPERIENCE
    Developer at Corp
    """
    
    job = "Required: Python, Git"
    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, None)
    
    assert not any("stuffing" in r.lower() for r in scorecard["reasons"])
    assert "Git" not in " ".join(scorecard["reasons"]) or "stuffing" not in " ".join(scorecard["reasons"])


def test_section_detection_student_resume():
    """Student resume with projects but no work experience should not be penalized for missing experience section."""
    resume = """
    Alex Student
    alex@university.edu | github.com/alexstudent
    SUMMARY
    Computer Science student seeking internship.
    EDUCATION
    B.S. Computer Science, University (2022-2026), GPA: 3.8
    SKILLS
    Python, Java, JavaScript, SQL, Git
    PROJECTS
    Task Manager - Full-stack app with React and Node.js, deployed on AWS
    Data Visualizer - Python backend with D3.js frontend
    CERTIFICATIONS
    AWS Cloud Practitioner (2024)
    Python Certification (2023)
    """
    
    # Experience is not required when projects are present
    # The completeness score should not penalize missing experience when projects exist
    from ats_match import _count_resume_sections
    sections = _count_resume_sections(resume)
    assert not sections["experience"], "Experience section should not be detected"
    assert sections["projects"], "Projects section should be detected"
    
    # Verify the scorecard doesn't penalize for missing experience
    job = "Required: Python, JavaScript"
    job_keywords = extract_job_keywords(job)
    projects = [
{"name": "Task Manager", "description": "Full-stack app", "bullets": ["React + Node.js", "Deployed on AWS"]},
        {"name": "Data Visualizer", "description": "Python backend", "bullets": ["Python backend", "React frontend"]}
    ]
    scorecard = calculate_ats_scorecard(resume, "Required: Python, JavaScript", extract_job_keywords("Required: Python, JavaScript"), projects)
    # Should not have "experience" as a weakness
    assert not any("experience" in r.lower() for r in scorecard["reasons"])


# ============================================================
# REGRESSION TESTS FOR RESTORED SECTION HEADINGS
# ============================================================

def test_education_section_restored_headings():
    """Test that restored education section headings (university, college) are recognized."""
    from ats_match import _has_education_section
    
    # Test old headings that should still work
    resume = "Education: B.S. Computer Science, University of Technology (2022-2026)"
    assert _has_education_section(resume.lower()), "Failed for 'Education:'"
    
    resume = "University: B.S. Computer Science, Stanford (2020-2024)"
    assert _has_education_section(resume.lower()), "Failed for 'University:'"
    
    resume = "College: B.A. English, Harvard (2018-2022)"
    assert _has_education_section(resume.lower()), "Failed for 'College:'"
    
    # Test prefix variants
    resume = "University of California, Berkeley - B.S. CS"
    assert _has_education_section(resume.lower()), "Failed for 'University ' prefix"
    
    resume = "College of Engineering - B.S. CS"
    assert _has_education_section(resume.lower()), "Failed for 'College ' prefix"


def test_education_section_colon_variants():
    """Test colon variants of restored education headings."""
    from ats_match import _has_education_section
    
    resume = "University: B.S. Computer Science"
    assert _has_education_section(resume.lower()), "Failed for 'University:'"
    
    resume = "College: B.A. English"
    assert _has_education_section(resume.lower()), "Failed for 'College:'"


def test_projects_section_restored_headings():
    """Test that restored projects section headings are recognized."""
    from ats_match import _has_projects_section
    
    # Test restored headings
    resume = "Portfolio: github.com/user"
    assert _has_projects_section(resume.lower()), "Failed for 'Portfolio:'"
    
    resume = "Personal Project: Open source library"
    assert _has_projects_section(resume.lower()), "Failed for 'Personal Project:'"
    
    resume = "Side Project: Mobile app"
    assert _has_projects_section(resume.lower()), "Failed for 'Side Project:'"
    
    # Test prefix variants
    resume = "Portfolio website at github.com/user"
    assert _has_projects_section(resume.lower()), "Failed for 'Portfolio ' prefix"
    
    resume = "Personal project: Open source library"
    assert _has_projects_section(resume.lower()), "Failed for 'Personal project ' prefix"
    
    resume = "Side project: Mobile app"
    assert _has_projects_section(resume.lower()), "Failed for 'Side project ' prefix"


def test_projects_section_colon_variants():
    """Test colon variants of restored project headings."""
    from ats_match import _has_projects_section
    
    resume = "Portfolio: github.com/user"
    assert _has_projects_section(resume.lower()), "Failed for 'Portfolio:'"
    
    resume = "Personal project: Open source library"
    assert _has_projects_section(resume.lower()), "Failed for 'Personal project:'"
    
    resume = "Side project: Mobile app"
    assert _has_projects_section(resume.lower()), "Failed for 'Side project:'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ============================================================
# REGRESSION TESTS FOR SPECIFIC ISSUES
# ============================================================

def test_github_in_project_not_counted_as_contact():
    """GitHub mentioned in project text should not count as contact info."""
    resume = """
    Jane Smith
    SKILLS
    Python, Git
    PROJECTS
    Open Source Project - hosted on github.com/janesmith/project
    """
    job = "Required: Python"
    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, None)
    # Should not have contact info since no email/phone/LinkedIn/profile URL
    assert any("contact" in r.lower() for r in scorecard["reasons"])
    # GitHub link in project text should not count as contact
    assert not any("github" in r.lower() for r in scorecard["reasons"] if "contact" in r.lower())


def test_no_quantitative_results_no_impact_points():
    """'Built and designed applications' without quantitative results should not get metrics points."""
    resume = """
    John Doe
    john@example.com
    SKILLS
    Python, React
    EXPERIENCE
    Developer at Corp
    - Built applications
    - Designed systems
    - Delivered projects
    """
    job = "Required: Python, React"
    projects = [{"name": "Project", "description": "Built and designed applications", "bullets": ["Built applications", "Designed systems"]}]
    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, projects)
    # Should not have metrics points since no quantitative results
    assert any("metric" in r.lower() or "impact" in r.lower() for r in scorecard["reasons"])
    # Project & Impact Evidence should not be maxed out
    impact_dim = next(d for d in scorecard["breakdown"] if d["dimension"] == "Project & Impact Evidence")
    assert impact_dim["awarded"] < impact_dim["max"]


def test_job_only_required_keywords():
    """Job with only required keywords should work correctly."""
    resume = "John Doe\njohn@example.com\nSKILLS\nPython, FastAPI\nEXPERIENCE\nDeveloper"
    job = "Required: Python, FastAPI"
    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, None)
    # Should not crash and should have valid score
    assert 0 <= scorecard["score"] <= 100
    assert "reasons" in scorecard
    assert "improvements" in scorecard
    # Keyword alignment should work with only required keywords
    kw_dim = next(d for d in scorecard["breakdown"] if d["dimension"] == "Keyword Alignment")
    assert kw_dim["awarded"] <= kw_dim["max"]
    assert kw_dim["awarded"] == 35


def test_job_only_required_keywords_partial_match():
    """Missing one of two required keywords should score 18/35."""
    resume = "John Doe\njohn@example.com\nSKILLS\nPython\nEXPERIENCE\nDeveloper"
    job = "Required: Python, FastAPI"
    job_keywords = extract_job_keywords(job)

    scorecard = calculate_ats_scorecard(resume, job, job_keywords, None)
    kw_dim = next(
        d for d in scorecard["breakdown"]
        if d["dimension"] == "Keyword Alignment"
    )

    assert kw_dim["awarded"] == 18
    assert kw_dim["max"] == 35



def test_job_only_preferred_keywords():
    """Job with only preferred keywords should work correctly."""
    resume = "John Doe\njohn@example.com\nSKILLS\nReact, TypeScript\nEXPERIENCE\nDeveloper"
    job = "Preferred: React, TypeScript"
    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, None)
    assert 0 <= scorecard["score"] <= 100
    assert "reasons" in scorecard
    assert "improvements" in scorecard


def test_job_no_extractable_keywords():
    """Job with no extractable keywords should return 0 for keyword alignment."""
    resume = "John Doe\njohn@example.com\nSKILLS\nPython"
    job = "We are looking for a motivated individual."
    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, None)
    # Should handle gracefully
    assert "score" in scorecard
    assert "breakdown" in scorecard
    kw_dim = next(d for d in scorecard["breakdown"] if d["dimension"] == "Keyword Alignment")
    assert kw_dim["awarded"] == 0

def test_determine_importance_does_not_misclassify_similar_headings():
    """Ordinary headings that start similarly should not change skill importance."""
    from career_gap import determine_importance

    job = (
        "Requirements Engineering\n"
        "Python is used for backend development."
    )

    assert determine_importance(job, "Python") == "Mentioned"

def test_breakdown_points_sum_to_score():
    """Breakdown awarded points should sum exactly to total score."""
    resume = """
    John Doe
    john@example.com | linkedin.com/in/johndoe | github.com/johndoe
    SUMMARY
    Experienced developer.
    SKILLS
    Python, FastAPI, PostgreSQL
    EXPERIENCE
    Developer at Corp
    EDUCATION
    B.S. CS, University
    PROJECTS
    Project A - Description
    """
    job = "Required: Python, FastAPI"
    projects = [{"name": "Project", "description": "Desc", "bullets": ["Built with Python"]}]
    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, projects)
    
    total_awarded = sum(d["awarded"] for d in scorecard["breakdown"])
    assert total_awarded == scorecard["score"], f"Breakdown sum {total_awarded} != score {scorecard['score']}"
    total_max = sum(d["max"] for d in scorecard["breakdown"])
    assert total_max == 100, f"Dimension maxima sum to {total_max}, expected 100"


def test_dimension_scores_within_maxima():
    """Each dimension score should not exceed its maximum."""
    resume = "John Doe\njohn@example.com\nSKILLS\nPython\nEXPERIENCE\nDeveloper"
    job = "Required: Python"
    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, None)
    
    for dim in scorecard["breakdown"]:
        assert dim["awarded"] <= dim["max"], f"{dim['dimension']}: {dim['awarded']} > {dim['max']}"
        assert dim["awarded"] >= 0, f"{dim['dimension']}: negative score"


def test_reasons_and_improvements_relevant():
    """Reasons and improvements should be relevant, not fabricated."""
    resume = "John Doe\njohn@example.com\nSKILLS\nPython, FastAPI\nEXPERIENCE\nDeveloper at Corp"
    job = "Required: Python, FastAPI, PostgreSQL, Docker\nPreferred: React, AWS"
    job_keywords = extract_job_keywords(job)
    scorecard = calculate_ats_scorecard(resume, job, job_keywords, None)
    
    # Reasons should be based on actual deductions
    for reason in scorecard["reasons"]:
        assert len(reason) > 0
        # Should not contain fabricated skills
        assert "Java" not in reason  # Not in job or resume
        assert "Ruby" not in reason
    
    # Improvements should be relevant
    for imp in scorecard["improvements"]:
        assert len(imp) > 0
        # Should be actionable guidance
        assert any(word in imp.lower() for word in ["add", "include", "organize", "document", "avoid", "review", "tailor", "incorporate"])


def test_deterministic_output():
    """Identical inputs should produce identical results."""
    resume = "John Doe\njohn@example.com\nSKILLS\nPython, FastAPI\nEXPERIENCE\nDeveloper"
    job = "Required: Python, FastAPI"
    projects = [{"name": "Project", "description": "Desc", "bullets": ["bullet"]}]
    job_keywords = extract_job_keywords("Required: Python, FastAPI")
    
    scorecard1 = calculate_ats_scorecard(resume, "Required: Python, FastAPI", extract_job_keywords("Required: Python, FastAPI"), projects)
    scorecard2 = calculate_ats_scorecard(resume, "Required: Python, FastAPI", extract_job_keywords("Required: Python, FastAPI"), projects)
    
    assert scorecard1["score"] == scorecard2["score"]
    assert scorecard1["label"] == scorecard2["label"]
    assert scorecard1["reasons"] == scorecard2["reasons"]
    assert scorecard1["improvements"] == scorecard2["improvements"]
    assert scorecard1["breakdown"] == scorecard2["breakdown"]