from pathlib import Path

import pytest

from file_upload import (
    MAX_EXTRACTED_TEXT,
    MAX_FILE_SIZE,
    process_uploaded_file,
)


def test_txt_file_is_extracted():
    file_data = b"Python developer with FastAPI experience."

    result = process_uploaded_file(
        "resume.txt",
        file_data,
    )

    assert result == (
        "Python developer with FastAPI experience."
    )


def test_extension_is_case_insensitive():
    file_data = b"Python developer."

    result = process_uploaded_file(
        "resume.TXT",
        file_data,
    )

    assert result == "Python developer."


def test_unsupported_extension_is_rejected():
    with pytest.raises(ValueError, match="Unsupported file type"):
        process_uploaded_file(
            "resume.exe",
            b"malicious content",
        )


def test_file_size_limit_is_enforced():
    oversized_file = b"x" * (MAX_FILE_SIZE + 1)

    with pytest.raises(
        ValueError,
        match="File is too large",
    ):
        process_uploaded_file(
            "resume.txt",
            oversized_file,
        )


def test_invalid_pdf_signature_is_rejected():
    with pytest.raises(
        ValueError,
        match="valid PDF",
    ):
        process_uploaded_file(
            "resume.pdf",
            b"not actually a PDF",
        )


def test_invalid_docx_signature_is_rejected():
    with pytest.raises(
        ValueError,
        match="valid DOCX",
    ):
        process_uploaded_file(
            "resume.docx",
            b"not actually a DOCX",
        )


def test_invalid_utf8_txt_is_rejected():
    invalid_utf8 = b"\xff\xfe\xfa"

    with pytest.raises(UnicodeDecodeError):
        process_uploaded_file(
            "resume.txt",
            invalid_utf8,
        )


def test_extracted_text_limit_is_enforced():
    oversized_text = (
        "Python developer. "
        * (MAX_EXTRACTED_TEXT // 18 + 1)
    ).encode("utf-8")

    with pytest.raises(
        ValueError,
        match="Extracted text is too large",
    ):
        process_uploaded_file(
            "resume.txt",
            oversized_text,
        )