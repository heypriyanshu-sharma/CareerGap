from pathlib import Path
import tempfile

from pypdf import PdfReader
from docx import Document


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
}

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_EXTRACTED_TEXT = 50_000
CHUNK_SIZE = 64 * 1024


def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def validate_extension(filename: str) -> None:
    extension = get_file_extension(filename)

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Only PDF, DOCX, and TXT files are allowed."
        )


def validate_file_size(file_size: int) -> None:
    if file_size > MAX_FILE_SIZE:
        raise ValueError(
            "File is too large. Maximum allowed size is 5 MB."
        )


def validate_file_signature(file_path: Path, extension: str) -> None:
    with file_path.open("rb") as file:
        header = file.read(8)

    if extension == ".pdf":
        if not header.startswith(b"%PDF-"):
            raise ValueError("The uploaded file is not a valid PDF.")

    elif extension == ".docx":
        if header[:4] != b"PK\x03\x04":
            raise ValueError("The uploaded file is not a valid DOCX file.")

    elif extension == ".txt":
        # TXT files don't have a universal magic number.
        # Their content is validated while decoding.
        return


def extract_text(file_path: Path, extension: str) -> str:
    if extension == ".txt":
        return file_path.read_text(
            encoding="utf-8",
            errors="strict",
        )

    if extension == ".pdf":
        reader = PdfReader(str(file_path))

        text_parts = []

        for page in reader.pages:
            text = page.extract_text() or ""
            text_parts.append(text)

            current_length = sum(
                len(part) for part in text_parts
            )

            if current_length > MAX_EXTRACTED_TEXT:
                raise ValueError(
                    "Extracted text is too large."
                )

        return "\n".join(text_parts)

    if extension == ".docx":
        document = Document(str(file_path))

        text_parts = []

        for paragraph in document.paragraphs:
            text_parts.append(paragraph.text)

            current_length = sum(
                len(part) for part in text_parts
            )

            if current_length > MAX_EXTRACTED_TEXT:
                raise ValueError(
                    "Extracted text is too large."
                )

        return "\n".join(text_parts)

    raise ValueError("Unsupported file type.")


def process_uploaded_file(
    filename: str,
    file_data: bytes,
) -> str:
    validate_extension(filename)
    validate_file_size(len(file_data))

    extension = get_file_extension(filename)

    with tempfile.TemporaryDirectory() as temp_directory:
        temporary_path = (
            Path(temp_directory) / "uploaded_file"
        )

        temporary_path.write_bytes(file_data)

        validate_file_signature(
            temporary_path,
            extension,
        )

        extracted_text = extract_text(
            temporary_path,
            extension,
        )

    if len(extracted_text) > MAX_EXTRACTED_TEXT:
        raise ValueError(
            "Extracted text is too large."
        )

    return extracted_text.strip()