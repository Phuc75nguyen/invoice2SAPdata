"""
Low‑level utilities for working with PDF files.

This module wraps pymupdf (also known as fitz) to provide a simple
interface for extracting text from PDF documents. If a document
contains a text layer, the extracted string will include all visible
text. If the document is purely scanned images and no text is
embedded, the returned string may be empty. In such cases the caller
may opt to perform OCR using an external library such as Tesseract,
but that is outside the scope of this helper.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def extract_text(pdf_path: str | Path) -> str:
    """Read all text from a PDF document.

    Parameters
    ----------
    pdf_path : str or Path
        The path to the PDF file to read.

    Returns
    -------
    str
        Concatenated text of all pages in the document. Page boundaries
        are separated by a newline character. If the document has no
        embedded text (e.g. scanned images), this string may be empty.
    """
    pdf_path = Path(pdf_path)
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.error("Failed to open PDF %s: %s", pdf_path, e)
        raise
    text_parts: list[str] = []
    for page_num in range(doc.page_count):
        try:
            page = doc.load_page(page_num)
            # `get_text()` returns the text layer of the page. The default
            # format is plain text. We append an explicit newline to
            # delineate page breaks.
            page_text = page.get_text()
            text_parts.append(page_text)
        except Exception as e:
            logger.warning(
                "Failed to extract text from page %s of %s: %s",
                page_num,
                pdf_path,
                e,
            )
    doc.close()
    return "\n".join(text_parts)