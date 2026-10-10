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


def _heading_style(name: str, font_size: int, space_after: int = 6, space_before: int = 12, color: HexColor = REF_GREEN_DARK) -> ParagraphStyle:
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


def _body_style(name: str, font_size: int = 9, leading: int = 12, color: HexColor = OLIVE_DARK, space_after: int = 2, space_before: int = 0) -> ParagraphStyle:
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


def _link_style(name: str, font_size: int = 9, leading: int = 12) -> ParagraphStyle:
    """Create a link style."""
    return ParagraphStyle(
        name,
        fontName="Helvetica",
        fontSize=font_size,
        leading=leading,
        textColor=REF_GREEN_PRIMARY,
        spaceAfter=2,
        spaceBefore=0,
        alignment=TA_LEFT,
    )


def _bullet_style(name: str, font_size: int = 9, leading: int = 12) -> ParagraphStyle:
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


# Pre-defined styles
STYLES = {
    "name": _heading_style("ResumeName", 18, space_after=2, space_before=0),
    "contact": _body_style("ResumeContact", 9, leading=11, space_after=8),
    "section_heading": _heading_style("SectionHeading", 11, space_after=6, space_before=14),
    "item_title": _heading_style("ItemTitle", 10, space_after=1, space_before=4),
    "item_subtitle": _body_style("ItemSubtitle", 9, leading=11, color=OLIVE_SOFT, space_after=0),
    "item_meta": _body_style("ItemMeta", 8, leading=10, color=OLIVE_SOFT, space_after=4),
    "item_text": _body_style("ItemText", 9, leading=12, space_after=4),
    "bullet": _bullet_style("Bullet"),
    "link": _link_style("Link"),
    "summary": _body_style("Summary", 9, leading=13, space_after=10),
}


def _section_divider():
    """Create a thin horizontal divider line."""
    return Table(
        [[""]],
        colWidths=[6.5 * inch],
        style=TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 1, REF_GREEN_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )


def _contact_link_row(label: str, url: str):
    """Create a contact link as a clickable paragraph."""
    if label and url:
        return Paragraph(f'<link href="{url}" color="{REF_GREEN_PRIMARY}">{label}: {url}</link>', STYLES["link"])
    elif url:
        return Paragraph(f'<link href="{url}" color="{REF_GREEN_PRIMARY}">{url}</link>', STYLES["link"])
    elif label:
        return Paragraph(label, STYLES["contact"])
    return None


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
    # Data / ML
    "sql": "Data & ML", "pandas": "Data & ML", "numpy": "Data & ML",
    "scikit-learn": "Data & ML", "machine learning": "Data & ML",
    "deep learning": "Data & ML", "tensorflow": "Data & ML",
    "pytorch": "Data & ML", "keras": "Data & ML",
    "matplotlib": "Data & ML", "seaborn": "Data & ML",
    "power bi": "Data & ML", "tableau": "Data & ML", "excel": "Data & ML",
    # Backend / APIs
    "fastapi": "Backend & APIs", "flask": "Backend & APIs", "django": "Backend & APIs",
    "rest api": "Backend & APIs", "graphql": "Backend & APIs",
    # Databases
    "postgresql": "Databases", "mysql": "Databases", "mongodb": "Databases",
    "sqlite": "Databases", "redis": "Databases",
    # Cloud / DevOps
    "docker": "Cloud & DevOps", "kubernetes": "Cloud & DevOps",
    "aws": "Cloud & DevOps", "azure": "Cloud & DevOps", "google cloud": "Cloud & DevOps",
    "git": "Cloud & DevOps", "github": "Cloud & DevOps", "linux": "Cloud & DevOps",
    "github actions": "Cloud & DevOps",
    # Web / Frontend
    "html": "Frontend", "css": "Frontend", "react": "Frontend", "node.js": "Frontend",
    # Core CS
    "data structures": "Core CS", "algorithms": "Core CS",
    "object-oriented programming": "Core CS", "oop": "Core CS",
}

_SKILL_CATEGORY_ORDER = [
    "Languages", "Frontend", "Backend & APIs", "Databases",
    "Cloud & DevOps", "Data & ML", "Core CS", "Other"
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


class SkillsPills(Flowable):
    """Renders each skill as an individual pill chip that wraps.

    Mirrors the web preview's `.resume-preview-skill` chips: a
    pistachio pill with olive text, one pill per skill, so skills
    never blend into a single concatenated paragraph.

    Now supports grouped rendering by category with subtle labels.
    """

    def __init__(
        self,
        skills: list[str],
        font_name: str = "Helvetica-Bold",
        font_size: int = 8,
        text_color: HexColor = OLIVE_DARK,
        background: HexColor = PISTACHIO,
        padding_x: int = 8,
        padding_y: int = 4,
        gap_x: int = 6,
        gap_y: int = 5,
    ):
        super().__init__()
        self.skills = [skill for skill in skills if skill and skill.strip()]
        self.groups = _group_skills_by_category(self.skills)
        self.font_name = font_name
        self.font_size = font_size
        self.text_color = text_color
        self.background = background
        self.padding_x = padding_x
        self.padding_y = padding_y
        self.gap_x = gap_x
        self.gap_y = gap_y
        self._rows: list[list[tuple[str, float]]] = []
        self._pill_height = 0.0

    def _pill_width(self, skill: str) -> float:
        return (
            pdfmetrics.stringWidth(skill, self.font_name, self.font_size)
            + 2 * self.padding_x
        )

    def _category_label_width(self, label: str) -> float:
        return pdfmetrics.stringWidth(label, self.font_name, self.font_size - 1) + 6

    def wrap(self, availWidth, availHeight):
        """Pack pills into rows that fit the available width, with category labels."""
        self._rows = []

        for cat, cat_skills in self.groups:
            # Category label row
            label = cat
            label_width = self._category_label_width(label)
            self._rows.append([("__CAT__", label_width, label)])

            row: list[tuple[str, float]] = []
            row_width = 0.0

            for skill in cat_skills:
                pill_width = self._pill_width(skill)
                if row and row_width + self.gap_x + pill_width > availWidth:
                    self._rows.append(row)
                    row = []
                    row_width = 0.0
                if row:
                    row_width += self.gap_x
                row.append((skill, pill_width))
                row_width += pill_width

            if row:
                self._rows.append(row)

        self._pill_height = self.font_size + 2 * self.padding_y
        if not self._rows:
            return (availWidth, 0)

        height = (
            len(self._rows) * self._pill_height
            + (len(self._rows) - 1) * self.gap_y
        )
        return (availWidth, height)

    def draw(self):
        """Draw the pill rows from the top of the flowable down."""
        if not self._rows:
            return

        canvas = self.canv
        canvas.saveState()

        for row_index, row in enumerate(self._rows):
            row_top = self.height - row_index * (self._pill_height + self.gap_y)
            row_bottom = row_top - self._pill_height
            x = 0.0

            # Check if this is a category label row
            if row and row[0][0] == "__CAT__":
                _, _, label = row[0]
                canvas.setFillColor(OLIVE_SOFT)
                canvas.setFont(self.font_name, self.font_size - 1)
                canvas.drawString(
                    x + 3,
                    row_bottom + self.padding_y - 1,
                    label.upper()
                )
            else:
                for skill, pill_width in row:
                    radius = self._pill_height / 2
                    canvas.setFillColor(self.background)
                    canvas.roundRect(
                        x,
                        row_bottom,
                        pill_width,
                        self._pill_height,
                        radius=radius,
                        stroke=0,
                        fill=1,
                    )
                    canvas.setFillColor(self.text_color)
                    canvas.setFont(self.font_name, self.font_size)
                    canvas.drawString(
                        x + self.padding_x,
                        row_bottom + self.padding_y,
                        skill,
                    )
                    x += pill_width + self.gap_x

        canvas.restoreState()


def _skills_pills(skills: list[str]):
    """Create one pill chip per skill, wrapping across rows."""
    cleaned = [skill for skill in skills if skill and skill.strip()]
    if not cleaned:
        return []
    return [SkillsPills(cleaned)]


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
                    f'<link href="{url}" color="{REF_GREEN_DARK}">{title_text}</link>',
                    STYLES["item_title"],
                )
            )
        else:
            flowables.append(Paragraph(title_text, STYLES["item_title"]))

    # Subtitle (organization / institution / issuer / context)
    org = item.get("organization", "").strip()
    if org:
        flowables.append(Paragraph(org, STYLES["item_subtitle"]))

    # Meta line: location | dates
    meta_parts = []
    loc = item.get("location", "").strip()
    if loc:
        meta_parts.append(loc)
    start = item.get("start", "").strip()
    end = item.get("end", "").strip()
    if start or end:
        if start and end:
            meta_parts.append(f"{start} – {end}")
        elif start:
            meta_parts.append(start)
        elif end:
            meta_parts.append(end)
    if meta_parts:
        flowables.append(Paragraph(" | ".join(meta_parts), STYLES["item_meta"]))

    # Description text
    text_val = item.get("text", "").strip()
    if text_val:
        flowables.append(Paragraph(text_val, STYLES["item_text"]))

    # URL link. Projects with a title already carry the link on
    # the title itself, so the URL is not repeated below.
    if url and not (sec_type == "projects" and title_text):
        flowables.append(
            Paragraph(
                f'<link href="{url}" color="{REF_GREEN_PRIMARY}">{url}</link>',
                STYLES["link"],
            )
        )

    # Bullets
    bullets = item.get("bullets", [])
    for bullet in bullets:
        if bullet and bullet.strip():
            flowables.append(Paragraph(f"• {bullet.strip()}", STYLES["bullet"]))

    return flowables


def _heading_block(heading_text: str, content: list) -> list:
    """Return story fragments for a section heading and its content.

    The heading is bound to the first content block with
    KeepTogether so a heading is never orphaned at the
    bottom of a page while its content starts the next one.
    """
    heading_paragraph = Paragraph(heading_text, STYLES["section_heading"])
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
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
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
        story.append(Paragraph(name, STYLES["name"]))

    # ---- CONTACT LINE ----
    contact_parts = []
    for key in ("email", "phone", "location"):
        val = contact.get(key, "").strip()
        if val:
            contact_parts.append(val)

    links = contact.get("links", [])
    for link in links:
        if isinstance(link, dict):
            label = link.get("label", "").strip()
            url = link.get("url", "").strip()
            if label and url:
                contact_parts.append(f'{label}: <link href="{url}" color="{REF_GREEN_PRIMARY}">{url}</link>')
            elif url:
                contact_parts.append(f'<link href="{url}" color="{REF_GREEN_PRIMARY}">{url}</link>')
            elif label:
                contact_parts.append(label)

    if contact_parts:
        contact_text = " | ".join(contact_parts)
        story.append(Paragraph(contact_text, STYLES["contact"]))

    story.append(_section_divider())

    # ---- SUMMARY ----
    if summary and summary.strip():
        story.extend(
            _heading_block(
                "Professional Summary",
                [Paragraph(summary.strip(), STYLES["summary"])],
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

        content: list = []

        # Section text (for custom sections with narrative text)
        if text:
            content.append(Paragraph(text, STYLES["item_text"]))

        # Section items
        if sec_type == "skills":
            # Skills are a flat list of strings, each rendered
            # as its own pill chip.
            content.extend(_skills_pills(items))
        else:
            # Dictionary-style items (education, experience, etc.)
            for item in items:
                if not isinstance(item, dict):
                    continue
                content.extend(_render_item(item, sec_type))

        # Bind the heading to its first content block so a
        # heading is never orphaned at the bottom of a page.
        story.extend(_heading_block(display_heading, content))

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