import sys
from io import BytesIO
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from docx import Document
from reportlab.pdfgen import canvas

from document_parser import extract_text_from_upload, UnsupportedFileTypeError


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _build_pdf_bytes(text: str) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, text)
    c.save()
    return buf.getvalue()


def test_extract_from_txt():
    result = extract_text_from_upload("policy.txt", b"Employees may work remotely.")
    assert result == "Employees may work remotely."


def test_extract_from_docx():
    file_bytes = _build_docx_bytes(["First paragraph.", "Second paragraph."])
    result = extract_text_from_upload("policy.docx", file_bytes)
    assert "First paragraph." in result
    assert "Second paragraph." in result


def test_extract_from_docx_skips_blank_paragraphs():
    file_bytes = _build_docx_bytes(["Real content.", "", "   "])
    result = extract_text_from_upload("policy.docx", file_bytes)
    assert result == "Real content."


def test_extract_from_pdf():
    file_bytes = _build_pdf_bytes("Hello PDF policy text")
    result = extract_text_from_upload("policy.pdf", file_bytes)
    assert "Hello PDF policy text" in result


def test_unsupported_file_type_raises():
    with pytest.raises(UnsupportedFileTypeError):
        extract_text_from_upload("policy.exe", b"junk")


def test_filename_extension_is_case_insensitive():
    result = extract_text_from_upload("POLICY.TXT", b"Uppercase extension content.")
    assert result == "Uppercase extension content."
