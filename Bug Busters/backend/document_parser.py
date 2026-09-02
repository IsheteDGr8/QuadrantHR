from io import BytesIO

from docx import Document
from pypdf import PdfReader


class UnsupportedFileTypeError(Exception):
    pass


def extract_text_from_upload(filename: str, file_bytes: bytes) -> str:
    """Extract plain text from an uploaded policy file (.docx, .pdf, .txt)."""

    lower_name = filename.lower()

    if lower_name.endswith(".docx"):
        return _extract_from_docx(file_bytes)

    if lower_name.endswith(".pdf"):
        return _extract_from_pdf(file_bytes)

    if lower_name.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="ignore").strip()

    raise UnsupportedFileTypeError(
        f"Unsupported file type for '{filename}'. Use .docx, .pdf, or .txt."
    )


def _extract_from_docx(file_bytes: bytes) -> str:
    doc = Document(BytesIO(file_bytes))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def _extract_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    pages_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages_text.append(text.strip())
    return "\n\n".join(pages_text)