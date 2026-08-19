"""
text_extractor.py
-----------------
Handles extraction of raw text from PDF, DOCX, TXT files and plain text input.
"""

import os
import logging
import pdfplumber
from docx import Document
import chardet

logger = logging.getLogger(__name__)


def extract_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file using pdfplumber for accurate layout parsing."""
    text_parts = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                    logger.debug(f"Extracted text from page {page_num}")
        full_text = "\n".join(text_parts)
        logger.info(f"PDF extraction complete: {len(full_text)} characters from {len(pdf.pages)} pages")
        return full_text
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise ValueError(f"Could not extract text from PDF: {e}")


def extract_from_docx(file_path: str) -> str:
    """Extract text from a DOCX file using python-docx."""
    try:
        doc = Document(file_path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        full_text = "\n".join(paragraphs)
        logger.info(f"DOCX extraction complete: {len(full_text)} characters")
        return full_text
    except Exception as e:
        logger.error(f"DOCX extraction failed: {e}")
        raise ValueError(f"Could not extract text from DOCX: {e}")


def extract_from_txt(file_path: str) -> str:
    """Extract text from a plain text file with auto encoding detection."""
    try:
        with open(file_path, "rb") as f:
            raw = f.read()
        detected = chardet.detect(raw)
        encoding = detected.get("encoding", "utf-8") or "utf-8"
        text = raw.decode(encoding, errors="replace")
        logger.info(f"TXT extraction complete: {len(text)} characters (encoding: {encoding})")
        return text
    except Exception as e:
        logger.error(f"TXT extraction failed: {e}")
        raise ValueError(f"Could not read text file: {e}")


def extract_text(source, file_extension: str = None) -> str:
    """
    Unified extraction entry point.
    
    Args:
        source: File path (str) or raw text (str) with file_extension=None
        file_extension: One of 'pdf', 'docx', 'txt', or None for raw text

    Returns:
        Extracted text string
    """
    if file_extension is None:
        # Treat source as raw text input
        return source

    ext = file_extension.lower().strip(".")

    if not os.path.exists(source):
        raise FileNotFoundError(f"File not found: {source}")

    if ext == "pdf":
        return extract_from_pdf(source)
    elif ext == "docx":
        return extract_from_docx(source)
    elif ext == "txt":
        return extract_from_txt(source)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported: pdf, docx, txt")
