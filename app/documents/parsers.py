import csv
from pathlib import Path

import fitz

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt", ".csv"}


def parse_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_csv_file(path: Path) -> str:
    rows: list[str] = []
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        for row in reader:
            rows.append(" | ".join(cell.strip() for cell in row))
    return "\n".join(rows)


def parse_pdf_file(path: Path) -> str:
    with fitz.open(path) as document:
        return "\n".join(page.get_text() for page in document)


def parse_document(path: Path) -> str:
    extension = path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported document type '{extension}'. Supported: {supported}")
    if extension == ".csv":
        return parse_csv_file(path)
    if extension == ".pdf":
        return parse_pdf_file(path)
    return parse_text_file(path)
