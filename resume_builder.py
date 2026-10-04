"""
ATS-FRIENDLY RESUME BUILDER DOMAIN
==================================
Validates and normalizes structured resume content, serializes it to
plain text for ATS parsing, and compares that text against a job
description using the existing CareerGap keyword logic.

Design rules:
- Pure and deterministic: no I/O, no clock, no randomness, no network.
- Never invents content. Missing, empty, or malformed fields are dropped
  rather than filled in, so this module cannot fabricate a skill, a role,
  a date, or an achievement.
- Reuses `resume_serialize` for plain text and `ats_match` for keyword
  extraction, so the builder cannot drift from the rest of CareerGap.
- Keyword comparison only reports whether a keyword already present in a
  job description also appears in the candidate's own text. It never
  suggests inserting a keyword and never claims an ATS outcome.
"""

from __future__ import annotations

from ats_match import extract_job_keywords, normalize_text
from resume_serialize import sections_to_plain_text


# ============================================================
# LIMITS
# ============================================================

MAX_TITLE_LENGTH = 120

MAX_NAME_LENGTH = 120

MAX_EMAIL_LENGTH = 254

MAX_PHONE_LENGTH = 40

MAX_LOCATION_LENGTH = 120

MAX_URL_LENGTH = 500

MAX_LINK_LABEL_LENGTH = 80

MAX_LINKS = 10

MAX_SUMMARY_LENGTH = 2_000

MAX_SECTIONS = 15

MAX_ITEMS_PER_SECTION = 40

MAX_ITEM_TITLE_LENGTH = 200

MAX_ITEM_ORGANIZATION_LENGTH = 200

MAX_ITEM_LOCATION_LENGTH = 200

MAX_ITEM_DATE_LENGTH = 40

MAX_ITEM_TEXT_LENGTH = 4_000

MAX_BULLETS_PER_ITEM = 20

MAX_BULLET_LENGTH = 1_000

MAX_SKILL_LENGTH = 80

# Guards the whole document so a single resume cannot become an
# unbounded payload in the database or an ATS parser.
MAX_PLAIN_TEXT_LENGTH = 60_000


# ============================================================
# SECTION TYPES
# ============================================================

SKILLS_SECTION = "skills"

DICT_ITEM_SECTION_TYPES = (
    "education",
    "experience",
    "projects",
    "certifications",
    "custom",
)

SECTION_TYPES = (
    SKILLS_SECTION,
) + DICT_ITEM_SECTION_TYPES


# Item fields kept for ATS text. Anything else a client sends is
# discarded so unknown keys cannot reach storage or rendering.
ITEM_TEXT_FIELDS = (
    "title",
    "organization",
    "location",
    "start",
    "end",
    "text",
    "url",
)

ITEM_BULLET_FIELD = "bullets"


class ResumeValidationError(ValueError):
    """Raised when resume content fails validation."""


# ============================================================
# VALUE HELPERS
# ============================================================

def _clean_string(
    value,
    field_name: str,
    max_length: int,
) -> str:
    """Return trimmed text, or raise when it exceeds its limit."""

    if value is None:

        return ""

    if not isinstance(value, str):

        raise ResumeValidationError(
            f"{field_name} must be text."
        )

    cleaned = value.strip()

    if len(cleaned) > max_length:

        raise ResumeValidationError(
            f"{field_name} is too long "
            f"(max {max_length} characters)."
        )

    return cleaned


def _optional_string(
    item: dict,
    key: str,
    field_name: str,
    max_length: int,
) -> str:
    """Return a trimmed field, defaulting to empty when absent."""

    return _clean_string(
        item.get(key),
        field_name,
        max_length,
    )


# ============================================================
# CONTACT
# ============================================================

def normalize_link(
    link,
    position: int,
) -> dict:
    """Validate one contact link."""

    if not isinstance(link, dict):

        raise ResumeValidationError(
            f"Link {position + 1} must be an object."
        )

    label = _clean_string(
        link.get("label"),
        f"Link {position + 1} label",
        MAX_LINK_LABEL_LENGTH,
    )

    url = _clean_string(
        link.get("url"),
        f"Link {position + 1} URL",
        MAX_URL_LENGTH,
    )

    if not label and not url:

        return {}

    return {
        "label": label,
        "url": url,
    }


def normalize_contact(
    contact,
) -> dict:
    """Validate the contact block of a resume."""

    if contact is None:

        contact = {}

    if not isinstance(contact, dict):

        raise ResumeValidationError(
            "Contact details must be an object."
        )

    raw_links = contact.get("links")

    if raw_links is None:

        raw_links = []

    if not isinstance(raw_links, list):

        raise ResumeValidationError(
            "Contact links must be a list."
        )

    if len(raw_links) > MAX_LINKS:

        raise ResumeValidationError(
            f"Too many links (max {MAX_LINKS})."
        )

    links = []

    for position, link in enumerate(raw_links):

        normalized = normalize_link(
            link,
            position,
        )

        if normalized:

            links.append(normalized)

    return {
        "full_name": _clean_string(
            contact.get("full_name"),
            "Full name",
            MAX_NAME_LENGTH,
        ),
        "email": _clean_string(
            contact.get("email"),
            "Email",
            MAX_EMAIL_LENGTH,
        ),
        "phone": _clean_string(
            contact.get("phone"),
            "Phone",
            MAX_PHONE_LENGTH,
        ),
        "location": _clean_string(
            contact.get("location"),
            "Location",
            MAX_LOCATION_LENGTH,
        ),
        "links": links,
    }


# ============================================================
# SECTION ITEMS
# ============================================================

def normalize_bullets(
    bullets,
    field_name: str,
) -> list[str]:
    """Validate a bullet list, dropping empty bullets."""

    if bullets is None:

        return []

    if isinstance(bullets, str):

        bullets = [bullets]

    if not isinstance(bullets, list):

        raise ResumeValidationError(
            f"{field_name} bullets must be a list."
        )

    if len(bullets) > MAX_BULLETS_PER_ITEM:

        raise ResumeValidationError(
            f"{field_name} has too many bullets "
            f"(max {MAX_BULLETS_PER_ITEM})."
        )

    cleaned = []

    for position, bullet in enumerate(bullets):

        text = _clean_string(
            bullet,
            f"{field_name} bullet {position + 1}",
            MAX_BULLET_LENGTH,
        )

        if text:

            cleaned.append(text)

    return cleaned


def normalize_dict_item(
    item,
    section_type: str,
    position: int,
) -> dict:
    """Validate one experience/education/project style entry."""

    if not isinstance(item, dict):

        raise ResumeValidationError(
            f"{section_type} entry {position + 1} "
            "must be an object."
        )

    label = f"{section_type} entry {position + 1}"

    normalized = {}

    for field in ITEM_TEXT_FIELDS:

        max_length = {
            "title": MAX_ITEM_TITLE_LENGTH,
            "organization": MAX_ITEM_ORGANIZATION_LENGTH,
            "location": MAX_ITEM_LOCATION_LENGTH,
            "start": MAX_ITEM_DATE_LENGTH,
            "end": MAX_ITEM_DATE_LENGTH,
            "text": MAX_ITEM_TEXT_LENGTH,
            "url": MAX_URL_LENGTH,
        }[field]

        value = _optional_string(
            item,
            field,
            f"{label} {field}",
            max_length,
        )

        if value:

            normalized[field] = value

    # "summary" is accepted as an alias so clients can use either name.
    if "text" not in normalized:

        summary = _optional_string(
            item,
            "summary",
            f"{label} summary",
            MAX_ITEM_TEXT_LENGTH,
        )

        if summary:

            normalized["text"] = summary

    bullets = normalize_bullets(
        item.get(ITEM_BULLET_FIELD),
        label,
    )

    if bullets:

        normalized[ITEM_BULLET_FIELD] = bullets

    return normalized


def normalize_skills_item(
    item,
    position: int,
) -> str:
    """Validate one skill entry."""

    return _clean_string(
        item,
        f"Skill {position + 1}",
        MAX_SKILL_LENGTH,
    )


def normalize_section(
    section,
    position: int,
) -> dict:
    """Validate one repeatable resume section."""

    if not isinstance(section, dict):

        raise ResumeValidationError(
            f"Section {position + 1} must be an object."
        )

    section_type = section.get("type")

    if not isinstance(section_type, str):

        raise ResumeValidationError(
            f"Section {position + 1} is missing a type."
        )

    if section_type not in SECTION_TYPES:

        raise ResumeValidationError(
            f"Section {position + 1} has an unsupported "
            f"type: {section_type}"
        )

    heading = _clean_string(
        section.get("heading"),
        f"Section {position + 1} heading",
        MAX_TITLE_LENGTH,
    )

    text = _clean_string(
        section.get("text"),
        f"Section {position + 1} text",
        MAX_ITEM_TEXT_LENGTH,
    )

    raw_items = section.get("items")

    if raw_items is None:

        raw_items = []

    if not isinstance(raw_items, list):

        raise ResumeValidationError(
            f"Section {position + 1} items must be a list."
        )

    if len(raw_items) > MAX_ITEMS_PER_SECTION:

        raise ResumeValidationError(
            f"Section {position + 1} has too many entries "
            f"(max {MAX_ITEMS_PER_SECTION})."
        )

    items = []

    if section_type == SKILLS_SECTION:

        for item_position, item in enumerate(raw_items):

            skill = normalize_skills_item(
                item,
                item_position,
            )

            if skill:

                items.append(skill)

    else:

        for item_position, item in enumerate(raw_items):

            normalized = normalize_dict_item(
                item,
                section_type,
                item_position,
            )

            if normalized:

                items.append(normalized)

    return {
        "type": section_type,
        "heading": heading,
        "text": text,
        "items": items,
    }


# ============================================================
# DOCUMENT
# ============================================================

def normalize_content(
    content,
) -> dict:
    """
    Validate structured resume content and return a canonical document.

    Unknown keys are discarded. Empty values are dropped rather than
    filled in, so a normalized document never claims experience the
    candidate did not enter.

    Raises ResumeValidationError for invalid structure or oversized
    input. This function is pure and performs no I/O.
    """

    if content is None:

        content = {}

    if not isinstance(content, dict):

        raise ResumeValidationError(
            "Resume content must be an object."
        )

    contact = normalize_contact(
        content.get("contact")
    )

    summary = _clean_string(
        content.get("summary"),
        "Summary",
        MAX_SUMMARY_LENGTH,
    )

    raw_sections = content.get("sections")

    if raw_sections is None:

        raw_sections = []

    if not isinstance(raw_sections, list):

        raise ResumeValidationError(
            "Resume sections must be a list."
        )

    if len(raw_sections) > MAX_SECTIONS:

        raise ResumeValidationError(
            f"Too many sections (max {MAX_SECTIONS})."
        )

    sections = []

    for position, section in enumerate(raw_sections):

        normalized = normalize_section(
            section,
            position,
        )

        if (
            normalized["heading"]
            or normalized["text"]
            or normalized["items"]
        ):

            sections.append(normalized)

    document = {
        "contact": contact,
        "summary": summary,
        "sections": sections,
    }

    if len(build_plain_text(document)) > MAX_PLAIN_TEXT_LENGTH:

        raise ResumeValidationError(
            "Resume is too long to export or parse."
        )

    return document


def build_plain_text(
    document,
) -> str:
    """
    Serialize a normalized resume document into ordered plain text.

    Contact details come first, then the summary, then each section in
    the order the user arranged them. Delegates to
    `resume_serialize.sections_to_plain_text` so the builder produces
    exactly the text shape the rest of CareerGap already parses.
    """

    if not isinstance(document, dict):

        return ""

    contact = document.get("contact")

    if not isinstance(contact, dict):

        contact = {}

    blocks = []

    name = contact.get("full_name") or ""

    if isinstance(name, str) and name.strip():

        blocks.append(name.strip())

    contact_line_parts = []

    for key in ("email", "phone", "location"):

        value = contact.get(key)

        if isinstance(value, str) and value.strip():

            contact_line_parts.append(value.strip())

    links = contact.get("links")

    if isinstance(links, list):

        for link in links:

            if not isinstance(link, dict):

                continue

            label = link.get("label") or ""
            url = link.get("url") or ""

            label = label.strip() if isinstance(label, str) else ""
            url = url.strip() if isinstance(url, str) else ""

            if not url and not label:

                continue

            if label and url:

                contact_line_parts.append(f"{label}: {url}")

            else:

                contact_line_parts.append(url or label)

    if contact_line_parts:

        blocks.append(" | ".join(contact_line_parts))

    sections_for_text = []

    if blocks:

        sections_for_text.append(
            {
                "text": "\n".join(blocks),
            }
        )

    summary = document.get("summary")

    if isinstance(summary, str) and summary.strip():

        sections_for_text.append(
            {
                "heading": "Summary",
                "text": summary.strip(),
            }
        )

    document_sections = document.get("sections")

    if isinstance(document_sections, list):

        for section in document_sections:

            if not isinstance(section, dict):

                continue

            sections_for_text.append(section)

    return sections_to_plain_text(
        {
            "sections": sections_for_text,
        }
    )


def empty_document() -> dict:
    """Return an empty, valid resume document."""

    return {
        "contact": {
            "full_name": "",
            "email": "",
            "phone": "",
            "location": "",
            "links": [],
        },
        "summary": "",
        "sections": [],
    }


# ============================================================
# JOB DESCRIPTION COMPARISON
# ============================================================

def _resume_contains_keyword(
    haystack: str,
    keyword: str,
) -> bool:
    """
    Report whether a keyword appears in the candidate's own text.

    Matching is whole-token on normalized text, so "go" does not match
    inside "google" and punctuation differences do not matter.
    """

    if not keyword:

        return False

    return f" {keyword} " in haystack


def compare_with_job_description(
    plain_text,
    job_description,
    limit: int = 25,
) -> dict:
    """
    Compare resume text against the keywords in a job description.

    Reuses `extract_job_keywords` for extraction, so this reports the
    same keywords the ATS panel already shows for an analysis.

    Only evidence already present in the resume is reported as
    supported. Nothing is added to the resume and no ATS outcome is
    claimed: an unsupported keyword means the resume does not mention
    it, not that the candidate lacks the skill.

    Returns an empty, well-formed result for empty input on either side.
    """

    result = {
        "supported": [],
        "missing": [],
        "total": 0,
        "has_job_description": False,
        "has_resume_text": False,
    }

    if not isinstance(plain_text, str) or not plain_text.strip():

        return result

    result["has_resume_text"] = True

    if not isinstance(job_description, str) or not job_description.strip():

        return result

    result["has_job_description"] = True

    haystack = f" {normalize_text(plain_text)} "

    for keyword in extract_job_keywords(
        job_description,
        limit=limit,
    ):

        if not isinstance(keyword, dict):

            continue

        term = keyword.get("term") or ""

        normalized = (
            keyword.get("normalized")
            or normalize_text(term)
        )

        entry = {
            "term": term,
            "importance": keyword.get("importance") or "",
            "frequency": keyword.get("frequency") or 0,
        }

        if _resume_contains_keyword(
            haystack,
            normalized,
        ):

            result["supported"].append(entry)

        else:

            result["missing"].append(entry)

    result["total"] = (
        len(result["supported"])
        + len(result["missing"])
    )

    return result