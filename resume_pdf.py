"""
PDF EXPORT FOR RESUME BUILDER
=============================
Generates professional, ATS-friendly PDF resumes from structured data.

Uses ReportLab for server-side PDF generation with:
- Single-column layout for ATS compatibility
- Selectable text (no rasterization)
- Clean typography with consistent spacing
- Professional section headings and dividers
- Multi-page support with sensible margins
"""
from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Table,
    TableStyle,
)


# Color palette matching the CareerGap design system
REF_GREEN_DARK = HexColor("#315D3B")
REF_GREEN_PRIMARY = HexColor("#2E6038")
REF_GREEN_PALE = HexColor("#EDF0E5")
REF_GREEN_BORDER = HexColor("#D7DCCB")
OLIVE_DARK = HexColor("#354832")
OLIVE_SOFT = HexColor("#65775D")
PISTACHIO = HexColor("#C6D8A7")
WHITE = HexColor("#FFFFFF")


def _heading_style(name: str, font_size: int, space_after: int = 4, space_before: int = 10, color: HexColor = REF_GREEN_DARK) -> ParagraphStyle:
    """Create a heading style."""
    return ParagraphStyle(
        name,
        fontName="Helvetica-Bold",
        fontSize=font_size,
        leading=font_size + 2,
        textColor=color,
        spaceAfter=space_after,
        spaceBefore=space_before,
        alignment=TA_LEFT,
    )


def _body_style(name: str, font_size: int = 9, leading: int = 11, color: HexColor = OLIVE_DARK, space_after: int = 1, space_before: int = 0) -> ParagraphStyle:
    """Create a body text style."""
    return ParagraphStyle(
        name,
        fontName="Helvetica",
        fontSize=font_size,
        leading=leading,
        textColor=color,
        spaceAfter=space_after,
        spaceBefore=space_before,
        alignment=TA_LEFT,
    )


def _link_style(name: str, font_size: int = 9, leading: int = 11) -> ParagraphStyle:
    """Create a link style."""
    return ParagraphStyle(
        name,
        fontName="Helvetica",
        fontSize=font_size,
        leading=leading,
        textColor=REF_GREEN_PRIMARY,
        spaceAfter=1,
        spaceBefore=0,
        alignment=TA_LEFT,
    )


def _bullet_style(name: str, font_size: int = 9, leading: int = 11) -> ParagraphStyle:
    """Create a bullet point style."""
    return ParagraphStyle(
        name,
        fontName="Helvetica",
        fontSize=font_size,
        leading=leading,
        textColor=OLIVE_DARK,
        spaceAfter=2,
        spaceBefore=0,
        leftIndent=18,
        bulletIndent=6,
        alignment=TA_LEFT,
    )


def _skill_category_style(name: str, font_size: int = 9, leading: int = 11) -> ParagraphStyle:
    """Create a skill category label style."""
    return ParagraphStyle(
        name,
        fontName="Helvetica-Bold",
        fontSize=font_size,
        leading=leading,
        textColor=OLIVE_SOFT,
        spaceAfter=0,
        spaceBefore=3,
        alignment=TA_LEFT,
    )


def _skill_list_style(name: str, font_size: int = 9, leading: int = 11) -> ParagraphStyle:
    """Create a skill list style."""
    return ParagraphStyle(
        name,
        fontName="Helvetica",
        fontSize=font_size,
        leading=leading,
        textColor=OLIVE_DARK,
        spaceAfter=0,
        spaceBefore=0,
        alignment=TA_LEFT,
    )


# Pre-defined styles
STYLES = {
    "name": _heading_style("ResumeName", 16, space_after=2, space_before=0),
    "contact": _body_style("ResumeContact", 9, leading=11, space_after=4),
    "section_heading": _heading_style("SectionHeading", 11, space_after=4, space_before=10),
    "item_title": _heading_style("ItemTitle", 10, space_after=1, space_before=3),
    "item_subtitle": _body_style("ItemSubtitle", 9, leading=11, color=OLIVE_SOFT, space_after=0),
    "item_meta": _body_style("ItemMeta", 8, leading=10, color=OLIVE_SOFT, space_after=3),
    "item_text": _body_style("ItemText", 9, leading=11, space_after=3),
    "bullet": _bullet_style("Bullet"),
    "link": _link_style("Link"),
    "summary": _body_style("Summary", 9, leading=12, space_after=8),
    "skill_category": _skill_category_style("SkillCategory"),
    "skill_list": _skill_list_style("SkillList"),
}


def _escape_markup(text: str) -> str:
    """Escape ReportLab markup special characters."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _section_divider():
    """Create a thin horizontal divider line."""
    return Table(
        [[""]],
        colWidths=[6.5 * inch],
        style=TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, REF_GREEN_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )


def _contact_link_text(label: str, url: str) -> str:
    """Create clickable link text for contact info.

    Shows only the label as the link text. If no label is provided,
    falls back to showing the URL.
    """
    if label and url:
        return f'<link href="{_escape_markup(url)}" color="{REF_GREEN_PRIMARY}">{_escape_markup(label)}</link>'
    elif url:
        return f'<link href="{_escape_markup(url)}" color="{REF_GREEN_PRIMARY}">{_escape_markup(url)}</link>'
    elif label:
        return _escape_markup(label)
    return ""


# ============================================================
# SKILL CATEGORIZATION (Presentation-only)
# Derived from CANONICAL_SKILL_RESOURCES in career_gap.py.
# Does not affect stored schema — skills remain a flat string list.
# ============================================================

_SKILL_CATEGORIES = {
    # Programming languages
    "python": "Languages", "c": "Languages", "c++": "Languages", "java": "Languages",
    "javascript": "Languages", "typescript": "Languages", "go": "Languages",
    "rust": "Languages", "r": "Languages",
    # Frontend
    "html": "Frontend", "css": "Frontend", "react": "Frontend", "node.js": "Frontend",
    "vue": "Frontend", "svelte": "Frontend", "angular": "Frontend",
    # Backend & APIs
    "fastapi": "Backend & APIs", "flask": "Backend & APIs", "django": "Backend & APIs",
    "rest api": "Backend & APIs", "rest apis": "Backend & APIs", "graphql": "Backend & APIs",
    "express": "Backend & APIs", "spring": "Backend & APIs",
    # Databases
    "sql": "Databases", "postgresql": "Databases", "mysql": "Databases",
    "mongodb": "Databases", "sqlite": "Databases", "redis": "Databases",
    "supabase": "Databases", "firebase": "Databases", "dynamodb": "Databases",
    # Tools & Version Control
    "git": "Tools & Version Control", "github": "Tools & Version Control",
    "gitlab": "Tools & Version Control", "bitbucket": "Tools & Version Control",
    "svn": "Tools & Version Control", "mercurial": "Tools & Version Control",
    # Testing
    "pytest": "Testing", "jest": "Testing", "mocha": "Testing", "junit": "Testing",
    "cypress": "Testing", "playwright": "Testing", "selenium": "Testing",
    "unittest": "Testing", "vitest": "Testing",
    # Cloud / DevOps
    "docker": "Cloud & DevOps", "kubernetes": "Cloud & DevOps",
    "aws": "Cloud & DevOps", "azure": "Cloud & DevOps", "google cloud": "Cloud & DevOps",
    "linux": "Cloud & DevOps", "github actions": "Cloud & DevOps",
    "terraform": "Cloud & DevOps", "ansible": "Cloud & DevOps",
    "ci/cd": "Cloud & DevOps", "jenkins": "Cloud & DevOps",
    # Data / ML
    "pandas": "Data & ML", "numpy": "Data & ML",
    "scikit-learn": "Data & ML", "machine learning": "Data & ML",
    "deep learning": "Data & ML", "tensorflow": "Data & ML",
    "pytorch": "Data & ML", "keras": "Data & ML",
    "matplotlib": "Data & ML", "seaborn": "Data & ML",
    "power bi": "Data & ML", "tableau": "Data & ML", "excel": "Data & ML",
    # Core CS
    "data structures": "Core CS", "algorithms": "Core CS",
    "object-oriented programming": "Core CS", "oop": "Core CS",
}

_SKILL_CATEGORY_ORDER = [
    "Languages", "Frontend", "Backend & APIs", "Databases",
    "Tools & Version Control", "Testing", "Cloud & DevOps", "Data & ML", "Core CS", "Other"
]


def _categorize_skill(skill: str) -> str:
    if not skill:
        return "Other"
    return _SKILL_CATEGORIES.get(skill.strip().lower(), "Other")


def _group_skills_by_category(skills: list[str]) -> list[tuple[str, list[str]]]:
    groups: dict[str, list[str]] = {}
    for skill in skills:
        cat = _categorize_skill(skill)
        groups.setdefault(cat, []).append(skill)
    result = []
    for cat in _SKILL_CATEGORY_ORDER:
        if cat in groups:
            result.append((cat, groups.pop(cat)))
    for cat, skill_list in groups.items():
        result.append((cat, skill_list))
    return result


def _skills_categorized(skills: list[str]) -> list:
    """Render skills as categorized, comma-separated text rows."""
    cleaned = [skill for skill in skills if skill and skill.strip()]
    if not cleaned:
        return []

    groups = _group_skills_by_category(cleaned)
    flowables = []

    for cat, cat_skills in groups:
        # Category label
        flowables.append(Paragraph(_escape_markup(cat.upper()), STYLES["skill_category"]))
        # Comma-separated skills
        skills_text = ", ".join(_escape_markup(s) for s in cat_skills)
        flowables.append(Paragraph(skills_text, STYLES["skill_list"]))

    return flowables


def _render_item(item: dict, sec_type: str) -> list:
    """Render one dictionary-style entry (education, experience,
    project, certification, custom) as a list of flowables."""
    flowables: list = []

    title_text = item.get("title", "").strip()
    url = item.get("url", "").strip()

    # Title line. A project title links to the project URL, which
    # is the conventional resume presentation for projects.
    if title_text:
        if sec_type == "projects" and url:
            flowables.append(
                Paragraph(
                    f'<link href="{_escape_markup(url)}" color="{REF_GREEN_DARK}">{_escape_markup(title_text)}</link>',
                    STYLES["item_title"],
                )
            )
        else:
            flowables.append(Paragraph(_escape_markup(title_text), STYLES["item_title"]))

    # Subtitle (organization / institution / issuer / context)
    org = item.get("organization", "").strip()
    if org:
        flowables.append(Paragraph(_escape_markup(org), STYLES["item_subtitle"]))

    # Meta line: location | dates
    meta_parts = []
    loc = item.get("location", "").strip()
    if loc:
        meta_parts.append(_escape_markup(loc))
    start = item.get("start", "").strip()
    end = item.get("end", "").strip()
    if start or end:
        if start and end:
            meta_parts.append(f"{_escape_markup(start)} \u2013 {_escape_markup(end)}")
        elif start:
            meta_parts.append(_escape_markup(start))
        elif end:
            meta_parts.append(_escape_markup(end))
    if meta_parts:
        flowables.append(Paragraph(" | ".join(meta_parts), STYLES["item_meta"]))

    # Description text
    text_val = item.get("text", "").strip()
    if text_val:
        flowables.append(Paragraph(_escape_markup(text_val), STYLES["item_text"]))

    # URL link. Projects with a title already carry the link on
    # the title itself, so the URL is not repeated below.
    if url and not (sec_type == "projects" and title_text):
        flowables.append(
            Paragraph(
                f'<link href="{_escape_markup(url)}" color="{REF_GREEN_PRIMARY}">{_escape_markup(url)}</link>',
                STYLES["link"],
            )
        )

    # Bullets
    bullets = item.get("bullets", [])
    for bullet in bullets:
        if bullet and bullet.strip():
            flowables.append(Paragraph(f"\u2022 {_escape_markup(bullet.strip())}", STYLES["bullet"]))

    return flowables


def _heading_block(heading_text: str, content: list) -> list:
    """Return story fragments for a section heading and its content.

    The heading is bound to the first content block with
    KeepTogether so a heading is never orphaned at the
    bottom of a page while its content starts the next one.
    """
    heading_paragraph = Paragraph(_escape_markup(heading_text), STYLES["section_heading"])
    if content:
        return [KeepTogether([heading_paragraph, content[0]])] + content[1:]
    return [heading_paragraph]


def build_resume_pdf(resume_data: dict[str, Any]) -> bytes:
    """
    Generate a professional PDF from normalized resume data.

    Args:
        resume_data: Normalized resume document from resume_builder.normalize_content
                     or a database row containing title, content, etc.

    Returns:
        PDF bytes ready for download.
    """
    # Extract content from either normalized content or database row
    content = resume_data.get("content", resume_data)
    title = resume_data.get("title", "Resume")

    contact = content.get("contact", {})
    summary = content.get("summary", "")
    sections = content.get("sections", [])

    buffer = BytesIO()

    # Document with custom margins
    doc = BaseDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title=title,
        author=contact.get("full_name", ""),
    )

    # Single column frame
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="normal",
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame])])

    story = []

    # ---- NAME ----
    name = contact.get("full_name", "").strip()
    if name:
        story.append(Paragraph(_escape_markup(name), STYLES["name"]))

    # ---- CONTACT LINE ----
    contact_parts = []
    for key in ("email", "phone", "location"):
        val = contact.get(key, "").strip()
        if val:
            contact_parts.append(_escape_markup(val))

    links = contact.get("links", [])
    for link in links:
        if isinstance(link, dict):
            label = link.get("label", "").strip()
            url = link.get("url", "").strip()
            link_text = _contact_link_text(label, url)
            if link_text:
                contact_parts.append(link_text)

    if contact_parts:
        contact_text = " | ".join(contact_parts)
        story.append(Paragraph(contact_text, STYLES["contact"]))

    story.append(_section_divider())

    # ---- SUMMARY ----
    if summary and summary.strip():
        story.extend(
            _heading_block(
                "Professional Summary",
                [Paragraph(_escape_markup(summary.strip()), STYLES["summary"])],
            )
        )

    # ---- SECTIONS ----
    for section in sections:
        if not isinstance(section, dict):
            continue

        sec_type = section.get("type", "")
        heading = section.get("heading", "").strip()
        text = section.get("text", "").strip()
        items = section.get("items", [])

        # Determine display heading
        if heading:
            display_heading = heading
        elif sec_type:
            type_labels = {
                "skills": "Skills",
                "education": "Education",
                "experience": "Experience",
                "projects": "Projects",
                "certifications": "Certifications",
                "custom": "Additional Information",
            }
            display_heading = type_labels.get(sec_type, sec_type.title())
        else:
            display_heading = "Section"

        section_flowables: list = []

        # Section text (for custom sections with narrative text)
        if text:
            section_flowables.append(Paragraph(_escape_markup(text), STYLES["item_text"]))

        # Section items
        if sec_type == "skills":
            # Skills are a flat list of strings, rendered as categorized rows
            section_flowables.extend(_skills_categorized(items))
        elif sec_type == "certifications":
            # Keep each certification entry together to avoid splitting across pages
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_flowables = _render_item(item, sec_type)
                if item_flowables:
                    section_flowables.extend(item_flowables)  # No KeepTogether - let flow naturally
        else:
            # Dictionary-style items (education, experience, projects, etc.)
            for item in items:
                if not isinstance(item, dict):
                    continue
                section_flowables.extend(_render_item(item, sec_type))

        # Bind the heading to its first content block so a
        # heading is never orphaned at the bottom of a page.
        story.extend(_heading_block(display_heading, section_flowables))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.read()


class ResumePDFError(Exception):
    """Raised when PDF generation fails."""
    pass


def generate_resume_pdf(resume_data: dict[str, Any]) -> bytes:
    """
    Public API to generate resume PDF with error handling.

    Args:
        resume_data: Resume data from database (includes title, content, etc.)

    Returns:
        PDF bytes

    Raises:
        ResumePDFError: If PDF generation fails
    """
    try:
        return build_resume_pdf(resume_data)
    except Exception as e:
        raise ResumePDFError(f"Failed to generate PDF: {e}") from e