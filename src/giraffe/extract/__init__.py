"""Extraction entry points: e-invoice first, text fallback."""
import subprocess

from .models import PaymentData
from .text import extract_from_text
from .zugferd import extract_from_pdf as _einvoice

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000


class InputError(Exception):
    pass


def pdf_text(path: str) -> str:
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", "-q", path, "-"],
            capture_output=True, timeout=30, stdin=subprocess.DEVNULL, check=False,
        )
    except FileNotFoundError:
        raise InputError("pdftotext is not installed (package poppler-utils).")
    except subprocess.TimeoutExpired:
        raise InputError("Reading the PDF took too long.")
    if proc.returncode != 0:
        raise InputError("The PDF could not be read.")
    return proc.stdout[:MAX_TEXT_CHARS * 4].decode("utf-8", "replace")[:MAX_TEXT_CHARS]


def from_text(text: str) -> PaymentData:
    return extract_from_text(text[:MAX_TEXT_CHARS])


def from_file(path: str) -> PaymentData:
    import os
    path = os.path.abspath(path)
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(5)
    except OSError as e:
        raise InputError(f"Cannot open file: {e.strerror}")
    if size > MAX_FILE_BYTES:
        raise InputError("File is too large.")
    if head != b"%PDF-":
        if size > 5 * 1024 * 1024:
            raise InputError("Not a PDF file.")
        with open(path, "rb") as f:
            return from_text(f.read().decode("utf-8", "replace"))
    data = _einvoice(path)
    if data is not None:
        return data
    text = pdf_text(path)
    if not text.strip():
        raise InputError("No text found. Scanned PDFs are not supported in v1.")
    return extract_from_text(text)
