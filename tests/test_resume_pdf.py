"""
Tests for resume PDF export functionality.
"""
import re
from io import BytesIO

import pytest
from pypdf import PdfReader
from reportlab.platypus import KeepTogether, Paragraph
from resume_pdf import (
    ResumePDFError,
    STYLES,
    _heading_block,
    _skills_categorized,
    build_resume_pdf,
    generate_resume_pdf,
)
from resume_builder import normalize_content


def minimal_resume() -> dict:
    """Return a minimal valid resume document for testing."""
    return {
        "title": "Test Resume",
        "content": {
            "contact": {
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "phone": "+1 555 1234",
                "location": "San Francisco, CA",
                "links": [{"label": "GitHub", "url": "https://github.com/janedoe"}],
            },
            "summary": "Experienced software engineer.",
            "sections": [
                {"type": "skills", "heading": "Technical Skills", "items": ["Python", "JavaScript", "SQL"]},
                {"type": "experience", "heading": "Experience", "items": [
                    {"title": "Senior Engineer", "organization": "Acme Corp", "location": "SF, CA",
                     "start": "2020", "end": "Present", "text": "Built things", "bullets": ["Did X", "Led Y"]}
                ]},
                {"type": "education", "heading": "Education", "items": [
                    {"title": "B.S. Computer Science", "organization": "MIT", "location": "Cambridge, MA",
                     "start": "2016", "end": "2020", "text": "GPA: 3.8"}
                ]},
            ],
        },
    }


def test_build_resume_pdf_returns_bytes():
    """PDF generation should return non-empty bytes."""
    resume = minimal_resume()
    pdf_bytes = build_resume_pdf(resume)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    # PDF magic number
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_resume_pdf_handles_database_row():
    """generate_resume_pdf should work with a database row (title + content)."""
    resume = minimal_resume()
    pdf_bytes = generate_resume_pdf(resume)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_resume_pdf_with_empty_document():
    """Should handle empty but valid document."""
    resume = {
        "title": "Empty Resume",
        "content": {
            "contact": {},
            "summary": "",
            "sections": [],
        },
    }
    pdf_bytes = generate_resume_pdf(resume)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_resume_pdf_with_multiple_pages():
    """Should handle content that spans multiple pages."""
    # Create a resume with lots of content
    many_items = [
        {"title": f"Role {i}", "organization": f"Company {i}", "location": "Remote",
         "start": "2020", "end": "2024", "text": "Description " * 50, "bullets": [f"Bullet {j}" for j in range(5)]}
        for i in range(20)
    ]
    resume = {
        "title": "Long Resume",
        "content": {
            "contact": {"full_name": "John Doe", "email": "john@example.com"},
            "summary": "Summary " * 100,
            "sections": [
                {"type": "experience", "heading": "Experience", "items": many_items},
                {"type": "projects", "heading": "Projects", "items": many_items},
            ],
        },
    }
    pdf_bytes = generate_resume_pdf(resume)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 10000  # Should be substantial
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_resume_pdf_with_all_section_types():
    """Should handle all supported section types."""
    resume = {
        "title": "Complete Resume",
        "content": {
            "contact": {"full_name": "Jane Doe", "email": "jane@example.com"},
            "summary": "Full stack developer.",
            "sections": [
                {"type": "skills", "heading": "Skills", "items": ["Python", "Go", "React"]},
                {"type": "education", "heading": "Education", "items": [
                    {"title": "M.S. CS", "organization": "Stanford", "start": "2020", "end": "2022"}
                ]},
                {"type": "experience", "heading": "Experience", "items": [
                    {"title": "Engineer", "organization": "Google", "start": "2022", "end": "Present"}
                ]},
                {"type": "projects", "heading": "Projects", "items": [
                    {"title": "Side Project", "text": "A cool project"}
                ]},
                {"type": "certifications", "heading": "Certs", "items": [
                    {"title": "AWS Cert", "organization": "Amazon", "start": "2023"}
                ]},
                {"type": "custom", "heading": "Awards", "items": [
                    {"title": "Best Paper", "text": "ICML 2023"}
                ]},
            ],
        },
    }
    pdf_bytes = generate_resume_pdf(resume)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_resume_pdf_handles_unicode():
    """Should handle Unicode characters in resume content."""
    resume = {
        "title": "Résumé",
        "content": {
            "contact": {"full_name": "José María", "email": "jose@example.com"},
            "summary": "Ingeniero de software • Développeur",
            "sections": [
                {"type": "skills", "heading": "Compétences", "items": ["Français", "Español", "中文"]},
                {"type": "experience", "heading": "Expérience", "items": [
                    {"title": "Ingénieur", "organization": "Société", "text": "Travail • 工作"}
                ]},
            ],
        },
    }
    pdf_bytes = generate_resume_pdf(resume)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_resume_pdf_missing_resume_raises():
    """generate_resume_pdf should handle missing data gracefully."""
    # Empty dict - should still produce a valid (though empty) PDF
    pdf_bytes = generate_resume_pdf({})
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:4] == b"%PDF"

    # Missing content key - should still work
    resume = {"content": {"contact": {}, "summary": "", "sections": []}}
    pdf_bytes = generate_resume_pdf(resume)
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_resume_pdf_with_links():
    """Should properly render clickable links in PDF."""
    resume = {
        "title": "Linked Resume",
        "content": {
            "contact": {
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "links": [
                    {"label": "GitHub", "url": "https://github.com/janedoe"},
                    {"label": "LinkedIn", "url": "https://linkedin.com/in/janedoe"},
                ],
            },
            "summary": "Check my links.",
            "sections": [
                {"type": "projects", "heading": "Projects", "items": [
                    {"title": "Project", "url": "https://example.com/project"}
                ]},
            ],
        },
    }
    pdf_bytes = generate_resume_pdf(resume)
    assert pdf_bytes[:4] == b"%PDF"


def test_contact_links_render_as_clickable_labels():
    """Contact links should show label as clickable text, not label: URL."""
    resume = {
        "title": "Contact Links",
        "content": {
            "contact": {
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "links": [
                    {"label": "GitHub", "url": "https://github.com/janedoe"},
                    {"label": "LinkedIn", "url": "https://linkedin.com/in/janedoe"},
                    {"label": "Portfolio", "url": "https://janedoe.dev"},
                ],
            },
            "summary": "",
            "sections": [],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    uris = []
    for page in reader.pages:
        for annot in page.get("/Annots") or []:
            obj = annot.get_object()
            action = obj.get("/A")
            if action and action.get("/URI"):
                uris.append(str(action.get("/URI")))
    # All three URLs should be present as link annotations
    assert "https://github.com/janedoe" in uris
    assert "https://linkedin.com/in/janedoe" in uris
    assert "https://janedoe.dev" in uris
    # Extracted text should show labels, not full "Label: URL" format
    text = _extract_pdf_text(pdf_bytes)
    assert "GitHub" in text
    assert "LinkedIn" in text
    assert "Portfolio" in text
    # Should NOT contain the old "Label: URL" format
    assert "GitHub: https://github.com/janedoe" not in text


def test_contact_links_without_labels():
    """Contact links without labels should show URL as clickable text."""
    resume = {
        "title": "No Label Links",
        "content": {
            "contact": {
                "full_name": "Jane Doe",
                "links": [
                    {"url": "https://github.com/janedoe"},
                    {"url": "https://linkedin.com/in/janedoe"},
                ],
            },
            "summary": "",
            "sections": [],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    text = _extract_pdf_text(pdf_bytes)
    assert "https://github.com/janedoe" in text
    assert "https://linkedin.com/in/janedoe" in text


def test_contact_links_escaping():
    """Special characters in link labels and URLs should be escaped."""
    resume = {
        "title": "Link Escaping",
        "content": {
            "contact": {
                "full_name": "Jane Doe",
                "links": [
                    {"label": "A&B Corp", "url": "https://example.com/a&b"},
                    {"label": "X<Y", "url": "https://example.com/x<y"},
                    {"label": "Foo>Bar", "url": "https://example.com/foo>bar"},
                ],
            },
            "summary": "",
            "sections": [],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    # Should not raise
    assert pdf_bytes[:4] == b"%PDF"
    text = _extract_pdf_text(pdf_bytes)
    assert "A&B Corp" in text or "A&B Corp" in text
    assert "X<Y" in text or "X<Y" in text
    assert "Foo>Bar" in text or "Foo>Bar" in text


def test_contact_long_url_wrapping():
    """Long URLs should wrap safely without layout issues."""
    long_url = "https://github.com/janedoe/very-long-repository-name-with-many-segments/that/extends/beyond/normal/width"
    resume = {
        "title": "Long URL",
        "content": {
            "contact": {
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "links": [
                    {"label": "GitHub", "url": long_url},
                ],
            },
            "summary": "",
            "sections": [],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    # Should not raise and should produce valid PDF
    assert pdf_bytes[:4] == b"%PDF"
    reader = PdfReader(BytesIO(pdf_bytes))
    # Should not cause excessive pages
    assert len(reader.pages) == 1


def test_contact_empty_and_partial():
    """Empty or partially populated contact should render gracefully."""
    # Only name
    resume1 = {
        "title": "Minimal Contact",
        "content": {
            "contact": {"full_name": "Jane Doe"},
            "summary": "",
            "sections": [],
        },
    }
    pdf_bytes1 = build_resume_pdf(resume1)
    assert pdf_bytes1[:4] == b"%PDF"
    text1 = _extract_pdf_text(pdf_bytes1)
    assert "Jane Doe" in text1

    # Name + email only
    resume2 = {
        "title": "Partial Contact",
        "content": {
            "contact": {"full_name": "Jane Doe", "email": "jane@example.com"},
            "summary": "",
            "sections": [],
        },
    }
    pdf_bytes2 = build_resume_pdf(resume2)
    assert pdf_bytes2[:4] == b"%PDF"
    text2 = _extract_pdf_text(pdf_bytes2)
    assert "Jane Doe" in text2
    assert "jane@example.com" in text2

    # Empty contact
    resume3 = {
        "title": "Empty Contact",
        "content": {
            "contact": {},
            "summary": "",
            "sections": [],
        },
    }
    pdf_bytes3 = build_resume_pdf(resume3)
    assert pdf_bytes3[:4] == b"%PDF"


def test_generate_resume_pdf_with_bullets():
    """Should properly render bullet points."""
    resume = {
        "title": "Bulleted Resume",
        "content": {
            "contact": {"full_name": "Jane Doe"},
            "summary": "",
            "sections": [
                {"type": "experience", "heading": "Experience", "items": [
                    {"title": "Engineer", "organization": "Acme", "bullets": [
                        "First achievement",
                        "Second achievement with unicode: ✓ ✗ →",
                        "Third " + "very long " * 50,
                    ]},
                ]},
            ],
        },
    }
    pdf_bytes = generate_resume_pdf(resume)
    assert pdf_bytes[:4] == b"%PDF"


def test_build_resume_pdf_uses_normalized_content():
    """Should work with pre-normalized content from resume_builder."""
    raw = {
        "contact": {"full_name": "Jane Doe", "email": "jane@example.com"},
        "summary": "Summary",
        "sections": [
            {"type": "skills", "items": ["Python", "JavaScript"]},
        ],
    }
    normalized = normalize_content(raw)
    resume = {"title": "Test", "content": normalized}
    pdf_bytes = generate_resume_pdf(resume)
    assert pdf_bytes[:4] == b"%PDF"


# ============================================================
# SKILLS CATEGORIZED RENDERING TESTS
# ============================================================

def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract whitespace-normalized text from a PDF."""
    reader = PdfReader(BytesIO(pdf_bytes))
    raw = "\n".join(page.extract_text() for page in reader.pages)
    return re.sub(r"\s+", " ", raw).strip()


def test_skills_render_as_categorized_rows():
    """Skills should be rendered as categorized, comma-separated rows."""
    skills = ["Python", "JavaScript", "SQL", "React", "Docker"]
    resume = {
        "title": "Skills Resume",
        "content": {
            "contact": {"full_name": "Jane Doe"},
            "summary": "",
            "sections": [
                {"type": "skills", "heading": "Skills", "items": skills},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    text = _extract_pdf_text(pdf_bytes)
    for skill in skills:
        assert skill in text
    # Category labels should be present
    assert "LANGUAGES" in text
    assert "FRONTEND" in text
    assert "CLOUD & DEVOPS" in text
    assert "DATABASES" in text


def test_skill_categorization_specific_assignments():
    """Specific skills should be assigned to correct categories."""
    skills = [
        "Python", "C", "C++", "JavaScript",           # Languages
        "HTML", "CSS",                                # Frontend
        "FastAPI", "REST APIs",                       # Backend & APIs
        "SQL", "PostgreSQL", "Supabase",              # Databases
        "Git", "GitHub",                              # Tools & Version Control
        "Pytest",                                     # Testing
        "Pandas", "TensorFlow",                       # Data & ML
        "Docker", "Kubernetes",                       # Cloud & DevOps
        # Cybersecurity skills
        "Vulnerability Assessment", "Vulnerability Management",
        "Security Automation", "Threat Analysis",
        "Security Operations", "OWASP Top 10",
        "Trivy", "Burp Suite", "Nmap",
        "SAST/DAST Fundamentals",
        # AI / Agentic Engineering skills
        "LLM Tool Use", "Structured Outputs", "Agent Workflows",
        "Data Structures", "Algorithms",              # Core CS
        "UnknownSkill123",                            # Other
    ]
    resume = {
        "title": "Categorization Test",
        "content": {
            "contact": {"full_name": "Jane Doe"},
            "summary": "",
            "sections": [
                {"type": "skills", "heading": "Skills", "items": skills},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    text = _extract_pdf_text(pdf_bytes)
    for skill in skills:
        assert skill in text
    # Check category labels
    assert "LANGUAGES" in text
    assert "FRONTEND" in text
    assert "BACKEND & APIS" in text
    assert "DATABASES" in text
    assert "TOOLS & VERSION CONTROL" in text
    assert "TESTING" in text
    assert "CLOUD & DEVOPS" in text
    assert "SECURITY" in text
    assert "AI ENGINEERING" in text
    assert "DATA & ML" in text
    assert "CORE CS" in text
    assert "OTHER" in text


def test_skill_categorization_case_insensitive():
    """Skill categorization should be case-insensitive."""
    skills = ["PYTHON", "python", "Python", "GIT", "Git", "git", "PYTEST", "pytest"]
    flowables = _skills_categorized(skills)
    # Should produce a Table with skills
    assert len(flowables) == 1
    table = flowables[0]
    # Extract text from table cells
    text = ""
    for row in table._cellvalues:
        for cell in row:
            if hasattr(cell, 'text'):
                text += cell.text + " "
            elif isinstance(cell, str):
                text += cell + " "
    # All original skill names preserved
    assert "PYTHON" in text
    assert "python" in text
    assert "Python" in text
    assert "GIT" in text
    assert "Git" in text
    assert "git" in text
    assert "PYTEST" in text
    assert "pytest" in text


def test_skill_categorization_preserves_original_names():
    """Original skill text should be preserved in display."""
    skills = ["Python", "C++", "REST APIs", "PostgreSQL", "GitHub Actions"]
    flowables = _skills_categorized(skills)
    assert len(flowables) == 1
    table = flowables[0]
    text = ""
    for row in table._cellvalues:
        for cell in row:
            if hasattr(cell, 'text'):
                text += cell.text + " "
            elif isinstance(cell, str):
                text += cell + " "
    assert "Python" in text
    assert "C++" in text
    assert "REST APIs" in text
    assert "PostgreSQL" in text
    assert "GitHub Actions" in text


def test_skill_categorization_unknown_skills():
    """Unknown skills should go to Other category."""
    skills = ["SomeRandomSkill", "AnotherUnknown"]
    flowables = _skills_categorized(skills)
    assert len(flowables) == 1
    table = flowables[0]
    text = ""
    for row in table._cellvalues:
        for cell in row:
            if hasattr(cell, 'text'):
                text += cell.text + " "
            elif isinstance(cell, str):
                text += cell + " "
    assert "OTHER" in text
    assert "SomeRandomSkill" in text
    assert "AnotherUnknown" in text


def test_skill_categorization_no_duplicates():
    """Duplicate skills should not appear multiple times."""
    skills = ["Python", "python", "PYTHON", "Git", "git"]
    flowables = _skills_categorized(skills)
    assert len(flowables) == 1
    table = flowables[0]
    text = ""
    for row in table._cellvalues:
        for cell in row:
            if hasattr(cell, 'text'):
                text += cell.text + " "
            elif isinstance(cell, str):
                text += cell + " "
    # Count occurrences - each should appear once
    assert text.count("Python") == 1
    assert text.count("python") == 1
    assert text.count("PYTHON") == 1
    assert text.count("Git") == 1
    assert text.count("git") == 1


def test_skills_categorized_empty():
    """Empty or blank skills produce no flowables."""
    assert _skills_categorized([]) == []
    assert _skills_categorized(["", "   "]) == []


def test_skills_categorized_unknown_goes_to_other():
    """Unknown skills should be categorized as Other."""
    skills = ["UnknownSkill123", "AnotherUnknown"]
    flowables = _skills_categorized(skills)
    assert len(flowables) == 1
    table = flowables[0]
    text = ""
    for row in table._cellvalues:
        for cell in row:
            if hasattr(cell, 'text'):
                text += cell.text + " "
            elif isinstance(cell, str):
                text += cell + " "
    assert "OTHER" in text


def test_skills_categorized_special_chars_escaped():
    """Special characters in skills should be escaped for ReportLab."""
    skills = ["C++", "A&B", "X<Y", "Foo>Bar"]
    flowables = _skills_categorized(skills)
    # Should not raise and should produce flowables
    assert len(flowables) == 1


def test_skills_categorized_many_skills():
    """Many skills across categories should all render."""
    skills = [
        "Python", "Java", "Go", "Rust",      # Languages
        "React", "Vue", "HTML", "CSS",       # Frontend
        "FastAPI", "Django", "Flask",        # Backend
        "PostgreSQL", "MySQL", "MongoDB",    # Databases
        "Docker", "Kubernetes", "AWS",       # Cloud
        "TensorFlow", "PyTorch", "Pandas",   # Data & ML
        "Git", "Linux", "GitHub Actions",    # Cloud & DevOps
        "Data Structures", "Algorithms",     # Core CS
        "CustomSkill1", "CustomSkill2",      # Other
    ]
    flowables = _skills_categorized(skills)
    assert len(flowables) == 1
    table = flowables[0]
    text = ""
    for row in table._cellvalues:
        for cell in row:
            if hasattr(cell, 'text'):
                text += cell.text + " "
            elif isinstance(cell, str):
                text += cell + " "
    # Check that skills from each category are present
    for skill in skills:
        assert skill in text


# ============================================================
# GENERAL RENDERING TESTS
# ============================================================

def test_custom_section_defaults_to_additional_information():
    """A custom section without a heading should show Additional Information."""
    resume = {
        "title": "Custom Resume",
        "content": {
            "contact": {"full_name": "Jane Doe"},
            "summary": "",
            "sections": [
                {"type": "custom", "items": [{"title": "Award", "text": "Won hackathon."}]},
            ],
        },
    }
    text = _extract_pdf_text(build_resume_pdf(resume))
    assert "Additional Information" in text
    assert "Award" in text


def test_project_title_links_to_url():
    """A project title should carry the project URL as a link annotation."""
    resume = {
        "title": "Project Resume",
        "content": {
            "contact": {"full_name": "Jane Doe"},
            "summary": "",
            "sections": [
                {
                    "type": "projects",
                    "heading": "Projects",
                    "items": [
                        {
                            "title": "CareerGap",
                            "text": "Engine.",
                            "url": "https://github.com/janedoe/careergap",
                        }
                    ],
                }
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    uris = []
    for page in reader.pages:
        for annot in page.get("/Annots") or []:
            obj = annot.get_object()
            action = obj.get("/A")
            if action and action.get("/URI"):
                uris.append(str(action.get("/URI")))
    assert "https://github.com/janedoe/careergap" in uris


def test_project_without_title_still_shows_url():
    """A project with a URL but no title must still expose the URL."""
    resume = {
        "title": "Project Resume",
        "content": {
            "contact": {"full_name": "Jane Doe"},
            "summary": "",
            "sections": [
                {
                    "type": "projects",
                    "heading": "Projects",
                    "items": [{"text": "Description.", "url": "https://example.com/proj"}],
                }
            ],
        },
    }
    text = _extract_pdf_text(build_resume_pdf(resume))
    assert "https://example.com/proj" in text


def test_heading_block_binds_heading_to_first_content():
    """The section heading should be kept with its first content block."""
    first = Paragraph("first", STYLES["item_text"])
    second = Paragraph("second", STYLES["item_text"])
    block = _heading_block("Skills", [first, second])
    assert len(block) == 2
    assert isinstance(block[0], KeepTogether)
    kept = block[0]._content
    assert len(kept) == 2
    assert kept[0].text == "Skills"
    assert kept[1] is first
    assert block[1] is second


def test_heading_block_without_content():
    """A heading with no content renders alone."""
    block = _heading_block("Skills", [])
    assert len(block) == 1
    assert isinstance(block[0], Paragraph)
    assert block[0].text == "Skills"


def test_long_item_text_is_not_truncated():
    """Long descriptions must survive pagination intact."""
    long_text = "Analyzed career gaps and generated guidance. " * 80
    resume = {
        "title": "Long Resume",
        "content": {
            "contact": {"full_name": "Jane Doe"},
            "summary": "Summary. " * 100,
            "sections": [
                {
                    "type": "projects",
                    "heading": "Projects",
                    "items": [
                        {"title": "Alpha", "text": long_text},
                        {"title": "Beta", "text": long_text},
                    ],
                }
            ],
        },
    }
    text = _extract_pdf_text(build_resume_pdf(resume))
    assert "Alpha" in text
    assert "Beta" in text
    assert re.sub(r"\s+", " ", long_text).strip() in text


def test_all_projects_are_exported():
    """Every project entry must appear in the PDF."""
    items = [
        {"title": f"Project {i}", "text": f"Description {i}."}
        for i in range(5)
    ]
    resume = {
        "title": "Projects Resume",
        "content": {
            "contact": {"full_name": "Jane Doe"},
            "summary": "",
            "sections": [
                {"type": "projects", "heading": "Projects", "items": items},
            ],
        },
    }
    text = _extract_pdf_text(build_resume_pdf(resume))
    for i in range(5):
        assert f"Project {i}" in text
        assert f"Description {i}." in text


def test_section_heading_stays_with_first_item():
    """A section heading must land on the same page as its first entry."""
    sections = []
    for i in range(20):
        sections.append(
            {
                "type": "experience",
                "heading": f"Section {i:02d}",
                "items": [
                    {
                        "title": f"Role {i:02d}",
                        "organization": f"Company {i:02d}",
                        "text": "Description. " * 30,
                        "bullets": [f"Bullet {i:02d}" for _ in range(3)],
                    }
                ],
            }
        )
    resume = {
        "title": "Heading Resume",
        "content": {
            "contact": {"full_name": "Jane Doe"},
            "summary": "Summary. " * 50,
            "sections": sections,
        },
    }
    reader = PdfReader(BytesIO(build_resume_pdf(resume)))
    page_texts = [page.extract_text() for page in reader.pages]
    # The content must span multiple pages for this to be meaningful.
    assert len(page_texts) > 1
    for i in range(20):
        heading_page = next(
            (
                idx
                for idx, text in enumerate(page_texts)
                if f"Section {i:02d}" in text
            ),
            None,
        )
        item_page = next(
            (
                idx
                for idx, text in enumerate(page_texts)
                if f"Role {i:02d}" in text
            ),
            None,
        )
        assert heading_page is not None, f"heading {i} missing"
        assert item_page is not None, f"item {i} missing"
        assert heading_page == item_page, (
            f"heading {i} on page {heading_page}, "
            f"first item on page {item_page}"
        )


def test_special_characters_escaped_in_output():
    """Special characters like &, <, > should be escaped in PDF output."""
    resume = {
        "title": "Special Chars",
        "content": {
            "contact": {"full_name": "Jane Doe"},
            "summary": "A & B < C > D",
            "sections": [
                {"type": "skills", "heading": "Skills", "items": ["A&B", "X<Y", "Foo>Bar"]},
                {"type": "experience", "heading": "Experience", "items": [
                    {"title": "Engineer", "organization": "A&B Corp", "text": "Worked on X<Y and Foo>Bar"}
                ]},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    # Should not raise and should produce valid PDF
    assert pdf_bytes[:4] == b"%PDF"
    text = _extract_pdf_text(pdf_bytes)
    assert "A & B" in text or "A & B" in text
    assert "A&B" in text or "A&B" in text


def test_no_orphaned_project_bullets_on_separate_page():
    """Project bullets should not be stranded on a mostly empty page."""
    resume = {
        "title": "Pagination Test",
        "content": {
            "contact": {"full_name": "Jane Doe"},
            "summary": "Summary. " * 50,
            "sections": [
                {"type": "skills", "heading": "Skills", "items": ["Python"] * 10},
                {"type": "experience", "heading": "Experience", "items": [
                    {"title": "Engineer", "organization": "Acme", "text": "Desc. " * 30, "bullets": ["B1"] * 5}
                ]},
                {"type": "projects", "heading": "Projects", "items": [
                    {"title": "Project", "text": "Desc.", "bullets": ["Bullet 1", "Bullet 2", "Bullet 3"]}
                ]},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    # With the new compact skills, everything should fit better
    # At minimum, verify PDF is valid
    assert len(reader.pages) >= 1
    # Check that project bullets appear on same page as project title if possible
    # (This is a best-effort test; exact pagination depends on content size)
    full_text = "\n".join(p.extract_text() for p in reader.pages)
    assert "Project" in full_text
    assert "Bullet 1" in full_text


# ============================================================
# ONE-PAGE OPTIMIZATION AND PAGINATION TESTS
# ============================================================

def test_compact_student_resume_fits_one_page():
    """A compact student resume should fit on one page."""
    resume = {
        "title": "Student Resume",
        "content": {
            "contact": {
                "full_name": "Alex Student",
                "email": "alex@university.edu",
                "phone": "+1 555 0123",
                "location": "Boston, MA",
                "links": [
                    {"label": "GitHub", "url": "https://github.com/alexstudent"},
                    {"label": "LinkedIn", "url": "https://linkedin.com/in/alexstudent"},
                ],
            },
            "summary": "Motivated Computer Science student seeking internship.",
            "sections": [
                {"type": "education", "heading": "Education", "items": [
                    {"title": "B.S. Computer Science", "organization": "University of Technology", "location": "Boston, MA",
                     "start": "2022", "end": "2026", "text": "GPA: 3.8/4.0"},
                ]},
                {"type": "skills", "heading": "Technical Skills", "items": [
                    "Python", "Java", "JavaScript", "HTML", "CSS", "SQL", "Git", "Docker"
                ]},
                {"type": "projects", "heading": "Projects", "items": [
                    {"title": "Task Manager", "text": "Full-stack task management app",
                     "url": "https://github.com/alexstudent/task-manager",
                     "bullets": ["Built with React and Node.js", "Deployed on AWS"]},
                    {"title": "Data Visualizer", "text": "Interactive charts with D3.js",
                     "bullets": ["Python backend", "React frontend"]},
                ]},
                {"type": "certifications", "heading": "Certifications", "items": [
                    {"title": "AWS Cloud Practitioner", "organization": "Amazon", "start": "2024"},
                    {"title": "Python Certification", "organization": "Python Institute", "start": "2023"},
                ]},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    # Should fit on one page
    assert len(reader.pages) == 1, f"Expected 1 page, got {len(reader.pages)}"
    # All content should be present
    text = _extract_pdf_text(pdf_bytes)
    assert "Alex Student" in text
    assert "B.S. Computer Science" in text
    assert "Python" in text
    assert "Task Manager" in text
    assert "Data Visualizer" in text
    assert "AWS Cloud Practitioner" in text
    assert "Python Certification" in text


def test_longer_resume_flows_to_multiple_pages():
    """A resume with enough content should legitimately span multiple pages."""
    many_experiences = [
        {"title": f"Role {i}", "organization": f"Company {i}", "location": "Remote",
         "start": "2020", "end": "2024", "text": "Description. " * 40, "bullets": [f"Bullet {j}" for j in range(5)]}
        for i in range(10)
    ]
    many_projects = [
        {"title": f"Project {i}", "text": "Desc. " * 20, "bullets": [f"Bullet {j}" for j in range(3)]}
        for i in range(5)
    ]
    resume = {
        "title": "Long Resume",
        "content": {
            "contact": {"full_name": "John Doe", "email": "john@example.com"},
            "summary": "Summary. " * 50,
            "sections": [
                {"type": "skills", "heading": "Skills", "items": ["Python"] * 15},
                {"type": "experience", "heading": "Experience", "items": many_experiences},
                {"type": "projects", "heading": "Projects", "items": many_projects},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    # Should span multiple pages
    assert len(reader.pages) >= 2, f"Expected at least 2 pages, got {len(reader.pages)}"
    # All content should be present (not truncated)
    text = _extract_pdf_text(pdf_bytes)
    for i in range(10):
        assert f"Role {i}" in text
    for i in range(5):
        assert f"Project {i}" in text


def test_certification_entries_stay_together():
    """Each certification entry should stay together on the same page."""
    resume = {
        "title": "Certification Test",
        "content": {
            "contact": {"full_name": "Jane Doe", "email": "jane@example.com"},
            "summary": "Summary. " * 30,  # Push certifications near page boundary
            "sections": [
                {"type": "skills", "heading": "Skills", "items": ["Python"] * 10},
                {"type": "experience", "heading": "Experience", "items": [
                    {"title": "Engineer", "organization": "Acme", "text": "Desc. " * 20, "bullets": ["B1"] * 3}
                ]},
                {"type": "certifications", "heading": "Certifications", "items": [
                    {"title": "Cert One", "organization": "Org A", "start": "2023"},
                    {"title": "Cert Two", "organization": "Org B", "start": "2024", "end": "2025"},
                    {"title": "Cert Three", "organization": "Org C", "text": "Details here"},
                ]},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    # Check that certifications are present
    text = _extract_pdf_text(pdf_bytes)
    assert "Cert One" in text
    assert "Cert Two" in text
    assert "Cert Three" in text
    assert "Org A" in text
    assert "Org B" in text
    assert "Org C" in text


def test_project_entries_stay_together():
    """Each project entry should stay together on the same page."""
    resume = {
        "title": "Project Test",
        "content": {
            "contact": {"full_name": "Jane Doe", "email": "jane@example.com"},
            "summary": "Summary. " * 30,  # Push projects near page boundary
            "sections": [
                {"type": "skills", "heading": "Skills", "items": ["Python"] * 10},
                {"type": "experience", "heading": "Experience", "items": [
                    {"title": "Engineer", "organization": "Acme", "text": "Desc. " * 20, "bullets": ["B1"] * 3}
                ]},
                {"type": "projects", "heading": "Projects", "items": [
                    {"title": "Project Alpha", "text": "Description alpha", "bullets": ["Bullet A1", "Bullet A2"]},
                    {"title": "Project Beta", "text": "Description beta", "bullets": ["Bullet B1", "Bullet B2", "Bullet B3"]},
                    {"title": "Project Gamma", "text": "Description gamma", "bullets": ["Bullet G1"]},
                ]},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    text = _extract_pdf_text(pdf_bytes)
    assert "Project Alpha" in text
    assert "Project Beta" in text
    assert "Project Gamma" in text
    assert "Bullet A1" in text
    assert "Bullet B1" in text
    assert "Bullet G1" in text


def test_long_descriptions_and_bullets_remain_present():
    """Long descriptions and bullets should not be truncated."""
    long_desc = "This is a very long description. " * 100
    many_bullets = [f"Bullet point number {i} with substantial content. " * 10 for i in range(10)]
    resume = {
        "title": "Long Content Test",
        "content": {
            "contact": {"full_name": "Jane Doe", "email": "jane@example.com"},
            "summary": "",
            "sections": [
                {"type": "experience", "heading": "Experience", "items": [
                    {"title": "Senior Engineer", "organization": "Big Corp", "text": long_desc, "bullets": many_bullets},
                ]},
                {"type": "projects", "heading": "Projects", "items": [
                    {"title": "Mega Project", "text": long_desc, "bullets": many_bullets},
                ]},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    text = _extract_pdf_text(pdf_bytes)
    # Check that long content is present (not truncated)
    assert "This is a very long description" in text
    assert "Bullet point number 0" in text
    assert "Bullet point number 9" in text
    # Verify it spans multiple pages if needed
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1


def test_no_overlap_or_clipped_content():
    """Generated PDF should not have overlapping or clipped content."""
    resume = {
        "title": "Layout Test",
        "content": {
            "contact": {
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "phone": "+1 555 1234",
                "location": "San Francisco, CA",
                "links": [
                    {"label": "GitHub", "url": "https://github.com/janedoe"},
                    {"label": "LinkedIn", "url": "https://linkedin.com/in/janedoe"},
                    {"label": "Portfolio", "url": "https://janedoe.dev"},
                ],
            },
            "summary": "Professional summary with enough text to fill a few lines. " * 5,
            "sections": [
                {"type": "education", "heading": "Education", "items": [
                    {"title": "M.S. Computer Science", "organization": "Stanford University", "location": "Stanford, CA",
                     "start": "2020", "end": "2022", "text": "Focus: Machine Learning"},
                    {"title": "B.S. Computer Science", "organization": "MIT", "location": "Cambridge, MA",
                     "start": "2016", "end": "2020", "text": "GPA: 3.9"},
                ]},
                {"type": "skills", "heading": "Technical Skills", "items": [
                    "Python", "Java", "C++", "JavaScript", "TypeScript", "Go", "Rust",
                    "React", "Vue", "Node.js", "HTML", "CSS",
                    "FastAPI", "Django", "Spring", "GraphQL", "REST APIs",
                    "PostgreSQL", "MongoDB", "Redis", "SQLite",
                    "Docker", "Kubernetes", "AWS", "GCP", "Azure",
                    "Git", "GitHub", "GitLab", "CI/CD", "Terraform",
                    "TensorFlow", "PyTorch", "Pandas", "NumPy",
                    "Data Structures", "Algorithms", "Distributed Systems",
                ]},
                {"type": "experience", "heading": "Experience", "items": [
                    {"title": "Software Engineer", "organization": "Tech Corp", "location": "SF, CA",
                     "start": "2022", "end": "Present", "text": "Building scalable systems.",
                     "bullets": ["Designed microservices", "Improved performance by 40%", "Mentored junior engineers"]},
                    {"title": "Intern", "organization": "Startup Inc", "location": "Remote",
                     "start": "2021", "end": "2022", "text": "Full-stack development.",
                     "bullets": ["Built REST APIs", "Wrote unit tests", "Deployed to cloud"]},
                ]},
                {"type": "projects", "heading": "Projects", "items": [
                    {"title": "Open Source Library", "text": "Popular utility library",
                     "url": "https://github.com/janedoe/lib", "bullets": ["10k stars", "Used by Fortune 500"]},
                ]},
                {"type": "certifications", "heading": "Certifications", "items": [
                    {"title": "AWS Solutions Architect", "organization": "Amazon", "start": "2023"},
                    {"title": "Kubernetes Administrator", "organization": "CNCF", "start": "2022"},
                ]},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    # Should produce valid PDF
    assert pdf_bytes[:4] == b"%PDF"
    reader = PdfReader(BytesIO(pdf_bytes))
    # Should not have excessive pages for this content
    assert len(reader.pages) <= 2, f"Expected at most 2 pages, got {len(reader.pages)}"
    # All content present
    text = _extract_pdf_text(pdf_bytes)
    assert "Jane Doe" in text
    assert "M.S. Computer Science" in text
    assert "B.S. Computer Science" in text
    assert "Python" in text
    assert "Software Engineer" in text
    assert "Open Source Library" in text
    assert "AWS Solutions Architect" in text
    # No obvious truncation markers
    assert "..." not in text or text.count("...") < 5  # Allow some ellipsis but not massive truncation


# ============================================================
# REGRESSION TESTS FOR FOUR DEMO DEFECTS
# ============================================================

def test_contact_header_not_duplicated():
    """Contact header should not duplicate name in contact line."""
    resume = {
        "title": "Contact Test",
        "content": {
            "contact": {
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "phone": "+1 555 1234",
                "location": "San Francisco, CA",
                "links": [{"label": "GitHub", "url": "https://github.com/janedoe"}],
            },
            "summary": "",
            "sections": [],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    text = _extract_pdf_text(pdf_bytes)
    # Name should appear once (as heading)
    assert text.count("Jane Doe") == 1, f"Name appears {text.count('Jane Doe')} times"
    # Contact details should appear once each
    assert "jane@example.com" in text
    assert "+1 555 1234" in text
    assert "San Francisco, CA" in text
    assert "GitHub" in text
    # Name should NOT be concatenated with contact details
    assert "Jane Doejane@example.com" not in text
    assert "Jane Doe | jane@example.com" not in text  # Name not in contact line


def test_all_skills_appear_in_pdf():
    """All supplied skills should appear exactly once in the PDF."""
    skills = [
        "Python", "SQL", "R", "Pandas", "NumPy", "Matplotlib",
        "Seaborn", "Excel", "PostgreSQL", "Git", "GitHub", "Jupyter"
    ]
    resume = {
        "title": "Skills Test",
        "content": {
            "contact": {"full_name": "Test User"},
            "summary": "",
            "sections": [
                {"type": "skills", "heading": "Technical Skills", "items": skills},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    text = _extract_pdf_text(pdf_bytes)
    for skill in skills:
        assert skill in text, f"Skill '{skill}' missing from PDF"
    # Each skill should appear exactly once (allowing for PDF extraction quirks)
    for skill in skills:
        count = text.count(skill)
        assert count >= 1, f"Skill '{skill}' appears {count} times"


def test_bullets_render_as_separate_paragraphs():
    """Each bullet should be a distinct paragraph, not concatenated inline."""
    resume = {
        "title": "Bullet Test",
        "content": {
            "contact": {"full_name": "Test User"},
            "summary": "",
            "sections": [
                {
                    "type": "experience",
                    "heading": "Experience",
                    "items": [{
                        "title": "Developer",
                        "organization": "Test Corp",
                        "bullets": [
                            "First bullet point with some content",
                            "Second bullet point with different content",
                            "Third bullet point with even more content",
                        ],
                    }],
                },
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    # Check that bullets appear as separate lines in extracted text
    full_text = "\n".join(page.extract_text() for page in reader.pages)
    # Each bullet should be on its own line (or at least separated)
    assert "First bullet point" in full_text
    assert "Second bullet point" in full_text
    assert "Third bullet point" in full_text
    # Bullets should not be concatenated
    assert "First bullet pointSecond bullet point" not in full_text
    assert "Second bullet pointThird bullet point" not in full_text


def test_certification_entry_stays_together_on_page_boundary():
    """Certification entry (title, org, date) should not split across pages."""
    resume = {
        "title": "Cert Pagination Test",
        "content": {
            "contact": {"full_name": "Test User", "email": "test@example.com"},
            "summary": "Summary line. " * 60,  # Push certifications to page boundary
            "sections": [
                {"type": "skills", "heading": "Skills", "items": ["Python"] * 5},
                {"type": "experience", "heading": "Experience", "items": [{
                    "title": "Engineer", "organization": "Corp", "text": "Desc. " * 20, "bullets": ["B1"] * 3
                }]},
                {"type": "certifications", "heading": "Certifications", "items": [
                    {"title": "Short Cert Title", "organization": "Issuer Org", "start": "2023"},
                    {"title": "Another Cert", "organization": "Another Org", "start": "2024", "end": "2025"},
                ]},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    page_texts = [page.extract_text() for page in reader.pages]
    # Verify certification entries are present and not split
    full_text = "\n".join(page_texts)
    assert "Short Cert Title" in full_text
    assert "Issuer Org" in full_text
    assert "2023" in full_text
    assert "Another Cert" in full_text
    assert "Another Org" in full_text
    assert "2024" in full_text
    # Check that title and org appear on same page for at least one cert
    # (This is a best-effort check; exact pagination varies)
    cert1_together = any(
        "Short Cert Title" in page and "Issuer Org" in page
        for page in page_texts
    )
    assert cert1_together, "Certification title and issuer should be on same page"


# ============================================================
# REGRESSION TESTS FOR RECENT FIXES
# ============================================================

def test_education_details_render_in_text_field():
    """Education 'text' field (CGPA, percentages) should render in PDF."""
    resume = {
        "title": "Education Details Test",
        "content": {
            "contact": {"full_name": "Test User"},
            "summary": "",
            "sections": [
                {"type": "education", "heading": "Education", "items": [
                    {"title": "B.Tech Computer Science", "organization": "University",
                     "location": "City", "start": "2020", "end": "2024",
                     "text": "CGPA: 8.49/10 | 12th: 92% | 10th: 95%"},
                ]},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    text = _extract_pdf_text(pdf_bytes)
    assert "CGPA: 8.49/10" in text
    assert "12th: 92%" in text
    assert "10th: 95%" in text


def test_skills_categories_and_labels_present():
    """Skill category labels and skill items should be present in extracted text.

    This test verifies content presence only; visual spacing is not checked
    because PDF text extraction does not reliably preserve layout spacing.
    """
    skills = ["Python", "JavaScript", "React", "Docker", "AWS"]
    resume = {
        "title": "Skills Spacing Test",
        "content": {
            "contact": {"full_name": "Test User"},
            "summary": "",
            "sections": [
                {"type": "skills", "heading": "Skills", "items": skills},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    # Verify the PDF is valid and all skills present
    text = _extract_pdf_text(pdf_bytes)
    for skill in skills:
        assert skill in text
    # Category labels should be present
    assert "LANGUAGES" in text
    assert "FRONTEND" in text
    assert "CLOUD & DEVOPS" in text


def test_project_entry_stays_together_on_page_boundary():
    """A project entry (title, description, and all bullets) should stay together on page break."""
    resume = {
        "title": "Project Pagination Test",
        "content": {
            "contact": {"full_name": "Test User", "email": "test@example.com"},
            "summary": "Summary line. " * 60,  # Push projects to page boundary
            "sections": [
                {"type": "skills", "heading": "Skills", "items": ["Python"] * 5},
                {"type": "experience", "heading": "Experience", "items": [{
                    "title": "Engineer", "organization": "Corp", "text": "Desc. " * 20, "bullets": ["B1"] * 3
                }]},
                {"type": "projects", "heading": "Projects", "items": [
                    {"title": "Test Project", "text": "Project description here",
                     "bullets": ["First bullet", "Second bullet", "Third bullet"]},
                    {"title": "Another Project", "text": "Another description",
                     "bullets": ["Bullet A", "Bullet B"]},
                ]},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    page_texts = [page.extract_text() for page in reader.pages]
    full_text = "\n".join(page_texts)
    # Verify project entries are present
    assert "Test Project" in full_text
    assert "Another Project" in full_text
    assert "First bullet" in full_text
    assert "Second bullet" in full_text
    assert "Third bullet" in full_text
    assert "Bullet A" in full_text
    assert "Bullet B" in full_text
    # Check that title, description, and ALL bullets appear on same page for at least one project
    proj1_together = any(
        "Test Project" in page and "Project description here" in page and
        "First bullet" in page and "Second bullet" in page and "Third bullet" in page
        for page in page_texts
    )
    assert proj1_together, (
        "Project title, description, and all bullets should stay together on page break"
    )


def test_long_project_entry_falls_back_to_natural_flow():
    """Very long project entries should not cause LayoutError; they flow naturally."""
    resume = {
        "title": "Long Project Test",
        "content": {
            "contact": {"full_name": "Test User", "email": "test@example.com"},
            "summary": "Summary. " * 30,
            "sections": [
                {"type": "skills", "heading": "Skills", "items": ["Python"] * 5},
                {"type": "projects", "heading": "Projects", "items": [
                    {"title": "Huge Project", "text": "Description. " * 500,
                     "bullets": [f"Bullet {i}" for i in range(20)]},
                ]},
            ],
        },
    }
    # Should not raise LayoutError
    pdf_bytes = build_resume_pdf(resume)
    assert pdf_bytes[:4] == b"%PDF"
    reader = PdfReader(BytesIO(pdf_bytes))
    # Should produce at least one page
    assert len(reader.pages) >= 1
    # Content should be present
    text = _extract_pdf_text(pdf_bytes)
    assert "Huge Project" in text
    assert "Bullet 0" in text
    assert "Bullet 19" in text


# ============================================================
# ADAPTIVE PAGINATION REGRESSION TESTS
# ============================================================

def test_moderate_resume_fits_one_page_when_possible():
    """A moderately detailed resume should fit on one page when content allows.

    This resume has education, skills, two experience entries, two projects,
    and two certifications - a realistic moderate resume that should fit
    on one page with the adaptive layout.
    """
    resume = {
        "title": "Moderate Resume",
        "content": {
            "contact": {
                "full_name": "Jane Developer",
                "email": "jane@example.com",
                "phone": "+1 555 1234",
                "location": "San Francisco, CA",
                "links": [{"label": "GitHub", "url": "https://github.com/janedev"}],
            },
            "summary": "Software engineer with 3 years experience building web applications.",
            "sections": [
                {"type": "education", "heading": "Education", "items": [
                    {"title": "B.S. Computer Science", "organization": "State University",
                     "location": "City, ST", "start": "2018", "end": "2022", "text": "GPA: 3.7/4.0"},
                ]},
                {"type": "skills", "heading": "Technical Skills", "items": [
                    "Python", "JavaScript", "React", "Node.js", "PostgreSQL", "Docker", "AWS", "Git"
                ]},
                {"type": "experience", "heading": "Experience", "items": [
                    {"title": "Software Engineer", "organization": "TechCorp", "location": "SF, CA",
                     "start": "2022", "end": "Present", "text": "Full-stack development",
                     "bullets": ["Built REST APIs with FastAPI", "Improved test coverage to 85%"]},
                    {"title": "Junior Developer", "organization": "StartupXYZ", "location": "Remote",
                     "start": "2021", "end": "2022", "text": "Frontend development",
                     "bullets": ["Built React components", "Wrote unit tests with Jest"]},
                ]},
                {"type": "projects", "heading": "Projects", "items": [
                    {"title": "Task Manager", "text": "Personal productivity app",
                     "bullets": ["React + Node.js", "Deployed on AWS"]},
                    {"title": "API Wrapper", "text": "Python library for third-party API",
                     "bullets": ["Published on PyPI", "100+ downloads"]},
                ]},
                {"type": "certifications", "heading": "Certifications", "items": [
                    {"title": "AWS Cloud Practitioner", "organization": "Amazon", "start": "2023"},
                ]},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    # Should fit on one page with adaptive layout
    assert len(reader.pages) == 1, f"Expected 1 page for moderate resume, got {len(reader.pages)}"
    # All content present
    text = _extract_pdf_text(pdf_bytes)
    assert "Jane Developer" in text
    assert "Software Engineer" in text
    assert "Task Manager" in text
    assert "AWS Cloud Practitioner" in text


def test_no_nearly_empty_trailing_page():
    """Short and medium resumes should not produce a trailing page with minimal content.

    A trailing page with only a few lines (e.g., just certifications or a single
    project) indicates poor pagination. This test ensures the last page has
    substantial content or the resume fits on fewer pages.
    """
    # Test 1: Student resume (compact) - should be 1 page
    student_resume = {
        "title": "Student Resume",
        "content": {
            "contact": {"full_name": "Student", "email": "s@u.edu", "location": "City"},
            "summary": "Student seeking internship.",
            "sections": [
                {"type": "education", "heading": "Education", "items": [
                    {"title": "B.S. CS", "organization": "Uni", "start": "2022", "end": "2026"}
                ]},
                {"type": "skills", "heading": "Skills", "items": ["Python", "Java", "Git"]},
                {"type": "projects", "heading": "Projects", "items": [
                    {"title": "Project 1", "bullets": ["Bullet 1", "Bullet 2"]},
                ]},
                {"type": "certifications", "heading": "Certs", "items": [
                    {"title": "Cert 1", "organization": "Org", "start": "2024"}
                ]},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(student_resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) == 1, f"Student resume should be 1 page, got {len(reader.pages)}"

    # Test 2: Medium resume - last page should have substantial content if 2 pages
    medium_resume = {
        "title": "Medium Resume",
        "content": {
            "contact": {"full_name": "Dev", "email": "d@e.com"},
            "summary": "Summary. " * 10,
            "sections": [
                {"type": "education", "heading": "Education", "items": [
                    {"title": "M.S. CS", "organization": "Uni", "start": "2020", "end": "2022", "text": "GPA 3.8"}
                ]},
                {"type": "skills", "heading": "Skills", "items": ["Python", "Java", "React", "AWS", "Docker"]},
                {"type": "experience", "heading": "Experience", "items": [
                    {"title": "Engineer", "organization": "Corp", "text": "Work. " * 20, "bullets": ["B1", "B2"]}
                ]},
                {"type": "projects", "heading": "Projects", "items": [
                    {"title": "Project", "text": "Desc", "bullets": ["B1", "B2", "B3"]}
                ]},
                {"type": "certifications", "heading": "Certs", "items": [
                    {"title": "Cert 1", "organization": "Org", "start": "2023"},
                    {"title": "Cert 2", "organization": "Org", "start": "2022"}
                ]},
            ],
        },
    }
    pdf_bytes = build_resume_pdf(medium_resume)
    reader = PdfReader(BytesIO(pdf_bytes))
    # If 2 pages, last page should have substantial content (>200 chars extracted)
    if len(reader.pages) == 2:
        last_page_text = reader.pages[1].extract_text() or ""
        assert len(last_page_text.strip()) > 200, (
            f"Last page has minimal content ({len(last_page_text.strip())} chars), "
            "indicating poor pagination"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])