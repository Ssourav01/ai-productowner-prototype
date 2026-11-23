
from pathlib import Path

import fitz
from docx import Document


def extract_text_from_pdf(file_path: Path) -> str:
    """Extract text from a PDF document."""

    extracted_pages = []

    with fitz.open(file_path) as pdf:
        for page in pdf:
            page_text = page.get_text()

            if page_text.strip():
                extracted_pages.append(page_text)

    return "\n".join(extracted_pages)


def extract_text_from_docx(file_path: Path) -> str:
    """Extract text from a DOCX document."""

    document = Document(file_path)

    paragraphs = [
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]

    return "\n".join(paragraphs)


def extract_document_text(file_path: str) -> str:
    """Extract readable text from an uploaded PDF or DOCX."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    extension = path.suffix.lower()

    if extension == ".pdf":
        extracted_text = extract_text_from_pdf(path)

    elif extension == ".docx":
        extracted_text = extract_text_from_docx(path)

    else:
        raise ValueError(
            "Unsupported file format. Please upload PDF or DOCX."
        )

    if not extracted_text.strip():
        raise ValueError("No readable text found in the document.")

    return extracted_text
