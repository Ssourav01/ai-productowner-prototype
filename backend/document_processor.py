
from pathlib import Path

import pymupdf
from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.text.paragraph import Paragraph
from docx.table import Table


def extract_text_from_pdf(file_path: Path) -> str:
    """Extract text from a PDF while preserving page boundaries."""

    extracted_pages = []

    with pymupdf.open(file_path) as pdf:

        for page_number, page in enumerate(pdf, start=1):

            page_text = page.get_text("text").strip()

            if page_text:
                extracted_pages.append(
                    f"\n--- PAGE {page_number} ---\n{page_text}"
                )

    return "\n".join(extracted_pages)


def extract_text_from_docx(file_path: Path) -> str:
    """
    Extract DOCX paragraphs and tables in their original document order.
    Preserve heading styles and table contents.
    """

    document = Document(file_path)
    extracted_content = []

    for element in document.element.body.iterchildren():

        # -----------------------------------------------------
        # Extract paragraphs
        # -----------------------------------------------------

        if isinstance(element, CT_P):

            paragraph = Paragraph(element, document)

            text = paragraph.text.strip()

            if not text:
                continue

            style_name = (
                paragraph.style.name
                if paragraph.style
                else ""
            )

            if style_name.startswith("Heading"):
                extracted_content.append(
                    f"\n## {text}\n"
                )
            else:
                extracted_content.append(text)

        # -----------------------------------------------------
        # Extract tables
        # -----------------------------------------------------

        elif isinstance(element, CT_Tbl):

            table = Table(element, document)

            extracted_content.append("\n[TABLE START]")

            for row in table.rows:

                cells = [
                    " ".join(cell.text.split())
                    for cell in row.cells
                ]

                extracted_content.append(
                    " | ".join(cells)
                )

            extracted_content.append("[TABLE END]\n")

    return "\n".join(extracted_content)


def extract_document_text(file_path: str) -> str:
    """Extract readable text from an uploaded PDF or DOCX."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

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
        raise ValueError(
            "No readable text found in the document."
        )

    return extracted_text
