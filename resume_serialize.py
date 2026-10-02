"""
STRUCTURED RESUME SERIALIZATION
================================

Converts a structured resume (JSON-like sections) into clean, ordered
plain text suitable for keyword matching and ATS parsing.

Design rules:
- Pure and deterministic: no I/O, no clock, no randomness, no network.
- Order follows the caller's section order. Nothing is sorted or reordered.
- Missing, empty, or malformed fields are skipped rather than rendered
  as "None" or empty placeholders.
- This module only serializes. It never infers, invents, or recommends
  anything, so it cannot fabricate experience.
"""

from __future__ import annotations


# ============================================================
# FORMATTING CONSTANTS
# ============================================================

META_SEPARATOR = " - "

FIELD_SEPARATOR = ", "

BULLET_PREFIX = "-"

SUMMARY_FIELDS = ("summary", "text")

HEADER_FIELDS = ("title", "organization", "location")

DATE_FIELDS = ("start", "end")


# ============================================================
# VALUE CLEANING
# ============================================================

def clean_value(value) -> str:
    """
    Normalize a single field into trimmed, single-spaced text.

    Returns an empty string for None, booleans, and unsupported types so
    that callers can simply test the result for truthiness.
    """

    if isinstance(value, str):

        return " ".join(value.split())

    if isinstance(value, bool) or value is None:

        return ""

    if isinstance(value, (int, float)):

        return str(value)

    return ""


def _clean_first(item, fields) -> str:
    """Return the first non-empty cleaned value among `fields`."""

    for field in fields:

        value = clean_value(item.get(field))

        if value:

            return value

    return ""


def _format_date_range(item) -> str:
    """Build a date range from start/end without inventing values."""

    parts = []

    for field in DATE_FIELDS:

        value = clean_value(item.get(field))

        if value:

            parts.append(value)

    return META_SEPARATOR.join(parts)


# ============================================================
# ITEM RENDERING
# ============================================================

def render_item(item) -> list[str]:
    """
    Render one resume item into ordered text lines.

    Supports a plain string item, or a mapping using:
      title, organization, location, start, end, summary/text, bullets.
    """

    if isinstance(item, str):

        cleaned = clean_value(item)

        return [cleaned] if cleaned else []

    if not isinstance(item, dict):

        return []

    lines = []

    header_parts = []

    for field in HEADER_FIELDS:

        value = clean_value(item.get(field))

        if value:

            header_parts.append(value)

    date_range = _format_date_range(item)

    if date_range:

        header_parts.append(date_range)

    if header_parts:

        lines.append(
            FIELD_SEPARATOR.join(header_parts)
        )

    summary = _clean_first(item, SUMMARY_FIELDS)

    if summary:

        lines.append(summary)

    bullets = item.get("bullets")

    if isinstance(bullets, str):

        bullets = [bullets]

    if isinstance(bullets, list):

        for bullet in bullets:

            cleaned = clean_value(bullet)

            if cleaned:

                lines.append(
                    f"{BULLET_PREFIX} {cleaned}"
                )

    return lines


def render_items(section) -> list[str]:
    """Render a section's optional prose plus its ordered items."""

    lines = []

    section_text = clean_value(
        section.get("text")
    )

    if section_text:

        lines.append(section_text)

    items = section.get("items")

    if not isinstance(items, list):

        return lines

    for item in items:

        lines.extend(render_item(item))

    return lines


def render_section(section) -> str:
    """Render one section into a heading followed by its body lines."""

    if not isinstance(section, dict):

        return ""

    heading = clean_value(
        section.get("heading")
    )

    lines = render_items(section)

    # A heading with no body would render as a dangling label, so the
    # whole section is dropped instead.
    if not lines:

        return ""

    if heading:

        lines.insert(0, heading)

    return "\n".join(lines)


# ============================================================
# PUBLIC API
# ============================================================

def sections_to_plain_text(content) -> str:
    """
    Serialize structured resume sections into ordered plain text.

    `content` is expected to look like:
        {"sections": [{"heading": str, "items": [...]}, ...]}

    Returns an empty string for None, non-mappings, missing keys,
    an empty section list, or sections that contain no usable content.
    Section order is always preserved exactly as provided.
    """

    if not isinstance(content, dict):

        return ""

    sections = content.get("sections")

    if not isinstance(sections, list):

        return ""

    blocks = []

    for section in sections:

        block = render_section(section)

        if block:

            blocks.append(block)

    return "\n\n".join(blocks)