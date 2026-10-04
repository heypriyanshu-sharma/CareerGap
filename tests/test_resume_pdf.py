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
    SkillsPills,
    STYLES,
    _heading_block,
    _skills_pills,
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
# SKILLS PILL RENDERING TESTS
# ============================================================

def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract whitespace-normalized text from a PDF."""
    reader = PdfReader(BytesIO(pdf_bytes))
    raw = "\n".join(page.extract_text() for page in reader.pages)
    return re.sub(r"\s+", " ", raw).strip()


def test_skills_render_as_individual_pills():
    """Each skill should be its own pill, not a concatenated paragraph."""
    skills = ["Python", "JavaScript", "SQL"]
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
    # Skills must not be joined into one concatenated paragraph
    assert "Python • JavaScript" not in text
    # Each pill is a rounded rectangle drawn with 4 bezier
    # curves, so one pill per skill must be present.
    reader = PdfReader(BytesIO(pdf_bytes))
    content = reader.pages[0].get_contents().get_data().decode("latin-1")
    assert content.count(" c\n") >= 4 * len(skills)


def test_skills_pills_wrap_into_multiple_rows():
    """Many skills should wrap into rows that fit the available width."""
    skills = [f"Skill {i}" for i in range(60)]
    pills = SkillsPills(skills)
    width, height = pills.wrap(468, 10000)
    assert width == 468
    assert height > 0
    # 60 skills cannot fit on one row, so they must wrap
    assert len(pills._rows) > 1
    for row in pills._rows:
        row_width = sum(w for _, w in row) + pills.gap_x * (len(row) - 1)
        assert row_width <= 468 + 1e-6


def test_skills_pills_single_wide_skill_does_not_crash():
    """A single skill wider than the frame must still render."""
    pills = SkillsPills(["Very long skill name that exceeds the frame width"])
    width, height = pills.wrap(100, 10000)
    assert height > 0
    assert len(pills._rows) == 1


def test_skills_pills_empty():
    """Empty or blank skills produce no flowables."""
    assert _skills_pills([]) == []
    assert _skills_pills(["", "   "]) == []


def test_skills_pills_draw_does_not_raise():
    """Drawing pills on a canvas should not raise."""
    from reportlab.pdfgen import canvas as pdf_canvas

    pills = SkillsPills(["Python", "JavaScript", "SQL"])
    pills.wrap(468, 1000)
    buffer = BytesIO()
    canvas = pdf_canvas.Canvas(buffer)
    pills.canv = canvas
    pills.draw()
    canvas.save()
    assert buffer.tell() > 0


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


# ============================================================
# FILENAME ENCODING TESTS (RFC 5987)
# ============================================================

def test_content_disposition_filename_ascii_only():
    """ASCII-only filenames should use simple format."""
    from backend import _content_disposition_filename

    result = _content_disposition_filename("resume.pdf")
    assert result == 'attachment; filename="resume.pdf"'


def test_content_disposition_filename_unicode_em_dash():
    """Em dash in filename should use RFC 5987 encoding."""
    from backend import _content_disposition_filename

    filename = "Senior Engineer \u2014 2024.pdf"
    result = _content_disposition_filename(filename)

    # Should have both ASCII fallback and UTF-8 encoded
    assert 'attachment; filename="Senior Engineer _ 2024.pdf"' in result
    assert "filename*=UTF-8''Senior%20Engineer%20%E2%80%94%202024.pdf" in result


def test_content_disposition_filename_accented_chars():
    """Accented characters should use RFC 5987 encoding."""
    from backend import _content_disposition_filename

    filename = "Jos\u00e9 Mar\u00eda \u2014 R\u00e9sum\u00e9.pdf"
    result = _content_disposition_filename(filename)

    assert 'attachment; filename="Jos_ Mar_a _ R_sum_.pdf"' in result
    assert "filename*=UTF-8''Jos%C3%A9%20Mar%C3%ADa%20%E2%80%94%20R%C3%A9sum%C3%A9.pdf" in result


def test_content_disposition_filename_cjk_chars():
    """CJK characters should use RFC 5987 encoding."""
    from backend import _content_disposition_filename

    filename = "\u7b80\u5386 \u2014 \u5de5\u7a0b\u5e08.pdf"
    result = _content_disposition_filename(filename)

    # Should contain UTF-8 encoded filename*
    assert "filename*=UTF-8''%E7%AE%80%E5%8E%86%20%E2%80%94%20%E5%B7%A5%E7%A8%8B%E5%B8%88.pdf" in result
    # ASCII fallback should only contain underscores, spaces, dots, and ASCII chars
    assert result.startswith('attachment; filename="')
    assert 'filename*=' in result


def test_content_disposition_filename_unsafe_ascii_chars():
    """Unsafe ASCII chars (quotes, semicolons, backslash) should be escaped in fallback."""
    from backend import _content_disposition_filename

    filename = 'Resume"with;bad\\chars.pdf'
    result = _content_disposition_filename(filename)

    # Unsafe chars replaced with underscore in fallback
    assert 'filename="Resume_with_bad_chars.pdf"' in result
    assert "filename*=UTF-8''Resume%22with%3Bbad%5Cchars.pdf" in result


def test_content_disposition_filename_empty():
    """Empty filename should still produce valid header."""
    from backend import _content_disposition_filename

    result = _content_disposition_filename("")
    assert result == 'attachment; filename=""'


def test_content_disposition_filename_mixed():
    """Mixed ASCII and Unicode should handle both correctly."""
    from backend import _content_disposition_filename

    filename = "Resume \u2014 2024 \u2014 Jos\u00e9.pdf"
    result = _content_disposition_filename(filename)

    assert 'attachment; filename="Resume _ 2024 _ Jos_.pdf"' in result
    assert "filename*=UTF-8''Resume%20%E2%80%94%202024%20%E2%80%94%20Jos%C3%A9.pdf" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])