from pathlib import Path

import fitz
import pytest

from app.documents.parsers import parse_csv_file, parse_document, parse_pdf_file, parse_text_file


def test_parse_text_file_reads_utf8_text(tmp_path: Path) -> None:
    path = tmp_path / "policy.txt"
    path.write_text("Refunds are available within 30 days.", encoding="utf-8")

    assert parse_text_file(path) == "Refunds are available within 30 days."
    assert parse_document(path) == "Refunds are available within 30 days."


def test_parse_markdown_file_uses_text_parser(tmp_path: Path) -> None:
    path = tmp_path / "handbook.md"
    path.write_text("# Refund policy\n\nRefunds require receipt proof.", encoding="utf-8")

    parsed = parse_document(path)

    assert "# Refund policy" in parsed
    assert "Refunds require receipt proof." in parsed


def test_parse_csv_file_joins_cells_and_trims_whitespace(tmp_path: Path) -> None:
    path = tmp_path / "support.csv"
    path.write_text(
        "topic, response\n"
        " refunds , available within 30 days \n"
        "billing, contact support\n",
        encoding="utf-8",
    )

    parsed = parse_csv_file(path)

    assert parsed.splitlines() == [
        "topic | response",
        "refunds | available within 30 days",
        "billing | contact support",
    ]
    assert parse_document(path) == parsed


def test_parse_pdf_file_extracts_page_text(tmp_path: Path) -> None:
    path = tmp_path / "policy.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "PDF refund policy text")
    document.save(path)
    document.close()

    parsed = parse_pdf_file(path)

    assert "PDF refund policy text" in parsed
    assert parse_document(path) == parsed


def test_parse_document_rejects_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "policy.exe"
    path.write_text("not a supported document", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported document type"):
        parse_document(path)
