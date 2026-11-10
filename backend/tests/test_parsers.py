"""Document parsers: extracted text, structure and per-segment metadata."""

from __future__ import annotations

from pathlib import Path

import docx
import pymupdf
import pytest
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches

from app.ingestion.formats import format_for
from app.ingestion.parsers import ParsedContent, ParsingError, parse_file


def parse(path: Path, filename: str | None = None) -> ParsedContent:
    format_ = format_for(filename or path.name)
    assert format_ is not None, f"no format registered for {path.name}"
    return parse_file(path, format_)


def write_pdf(path: Path, pages: list[str]) -> Path:
    document = pymupdf.open()
    try:
        for text in pages:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        document.save(path)
    finally:
        document.close()
    return path


def test_pdf_keeps_page_numbers_without_text_markers(tmp_path: Path) -> None:
    path = write_pdf(tmp_path / "manual.pdf", ["First page", "Second page", ""])

    parsed = parse(path)

    assert parsed.metadata["pages"] == 3
    assert [segment.metadata["page_number"] for segment in parsed.segments] == [1, 2]
    assert "First page" in parsed.text and "Second page" in parsed.text
    assert "[page" not in parsed.text.lower()
    # The empty page is skipped, so page two starts after a blank separator line.
    assert parsed.segments[1].start_line == 3
    assert any("1 page" in warning for warning in parsed.warnings)


def test_pdf_without_extractable_text_raises(tmp_path: Path) -> None:
    path = write_pdf(tmp_path / "scan.pdf", [""])

    with pytest.raises(ParsingError, match="OCR"):
        parse(path)


def test_docx_tracks_headings_sections_and_tables(tmp_path: Path) -> None:
    document = docx.Document()
    document.add_heading("Architecture", level=1)
    document.add_paragraph("The ingestion pipeline parses files.")
    document.add_heading("Parsing", level=2)
    document.add_paragraph("PDF and Office parsers preserve metadata.")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Parser"
    table.cell(0, 1).text = "Library"
    table.cell(1, 0).text = "PDF"
    table.cell(1, 1).text = "PyMuPDF"
    path = tmp_path / "design.docx"
    document.save(path)

    parsed = parse(path)

    assert parsed.metadata["headings"] == 2
    assert parsed.metadata["tables"] == 1
    assert parsed.metadata["table_rows"] == 2
    assert [segment.metadata["section"] for segment in parsed.segments] == [
        "Architecture",
        "Parsing",
    ]
    assert (
        parsed.segments[1].metadata["section_path"] == "Architecture > Parsing"
    )
    assert "Parser | Library" in parsed.text
    assert "PDF | PyMuPDF" in parsed.text
    assert parsed.segments[0].start_line == 1


def test_pptx_tracks_slides_titles_and_tables(tmp_path: Path) -> None:
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "Architecture"
    slide.placeholders[1].text = "Ingestion pipeline\nStorage layer"
    table = slide.shapes.add_table(
        2, 2, Inches(1), Inches(4), Inches(4), Inches(1)
    ).table
    table.cell(0, 0).text = "Component"
    table.cell(0, 1).text = "Owner"
    table.cell(1, 0).text = "API"
    table.cell(1, 1).text = "Rika"
    second = presentation.slides.add_slide(presentation.slide_layouts[5])
    second.shapes.title.text = "Second slide"
    presentation.slides.add_slide(presentation.slide_layouts[6])  # blank
    path = tmp_path / "deck.pptx"
    presentation.save(path)

    parsed = parse(path)

    assert parsed.metadata["slides"] == 3
    assert parsed.metadata["tables"] == 1
    assert [segment.metadata["slide_number"] for segment in parsed.segments] == [1, 2]
    assert parsed.segments[0].metadata["title"] == "Architecture"
    assert parsed.segments[0].metadata["section"] == "Architecture"
    assert "Ingestion pipeline" in parsed.text
    assert "Component | Owner" in parsed.text
    assert "API | Rika" in parsed.text
    assert any("1 slide" in warning for warning in parsed.warnings)


def test_xlsx_tracks_sheets_and_rows(tmp_path: Path) -> None:
    workbook = Workbook()
    users = workbook.active
    users.title = "Users"
    users.append(["id", "name"])
    users.append([1, "Ada"])
    users.append([2, "Grace"])
    workbook.create_sheet("Empty")
    path = tmp_path / "book.xlsx"
    workbook.save(path)

    parsed = parse(path)

    assert parsed.metadata["sheets"] == 2
    assert parsed.metadata["sheet_names"] == ["Users", "Empty"]
    assert parsed.metadata["rows"] == 3
    assert parsed.metadata["columns"] == 2
    assert [segment.metadata["sheet_name"] for segment in parsed.segments] == [
        "Users"
    ]
    assert parsed.segments[0].metadata["section"] == "Users"
    assert parsed.segments[0].metadata["rows"] == 3
    assert "Users\nid | name\n1 | Ada\n2 | Grace" in parsed.text
    assert any("1 sheet" in warning for warning in parsed.warnings)


def test_markdown_sections_ignore_fenced_headings(tmp_path: Path) -> None:
    markdown = (
        "# Title\n"
        "\n"
        "Intro text.\n"
        "\n"
        "## Section A\n"
        "\n"
        "Body A.\n"
        "\n"
        "```python\n"
        "# not a heading\n"
        "```\n"
        "\n"
        "Setext\n"
        "------\n"
        "\n"
        "Body B.\n"
    )
    path = tmp_path / "guide.md"
    path.write_text(markdown, encoding="utf-8")

    parsed = parse(path)

    assert parsed.metadata["headings"] == 3
    assert parsed.metadata["sections"] == 3
    assert [segment.metadata["heading"] for segment in parsed.segments] == [
        "Title",
        "Section A",
        "Setext",
    ]
    assert parsed.segments[1].metadata["heading_level"] == 2
    assert parsed.segments[1].metadata["section_path"] == "Title > Section A"
    assert parsed.segments[1].start_line == 5
    assert parsed.segments[2].start_line == 13
    assert "# not a heading" in parsed.segments[1].text
    assert "Body B." in parsed.text


def test_html_keeps_headings_tables_and_skips_scripts(tmp_path: Path) -> None:
    html = (
        "<html><body>"
        "<h1>Guide</h1>"
        "<p>Hello <b>world</b>.</p>"
        "<h2>Table</h2>"
        "<table>"
        "<tr><th>Name</th><th>Value</th></tr>"
        "<tr><td>A</td><td>1</td></tr>"
        "</table>"
        "<script>ignore_me()</script>"
        "</body></html>"
    )
    path = tmp_path / "guide.html"
    path.write_text(html, encoding="utf-8")

    parsed = parse(path)

    assert parsed.metadata["headings"] == 2
    assert parsed.metadata["sections"] == 2
    assert [segment.metadata["heading"] for segment in parsed.segments] == [
        "Guide",
        "Table",
    ]
    assert parsed.segments[1].metadata["section_path"] == "Guide > Table"
    assert "Hello world." in parsed.text
    assert "Name | Value" in parsed.text
    assert "A | 1" in parsed.text
    assert "ignore_me" not in parsed.text
    assert parsed.segments[1].start_line >= parsed.segments[0].end_line


def test_json_preserves_source_lines(tmp_path: Path) -> None:
    raw = '{\n  "name": "Rika",\n  "enabled": true\n}\n'
    path = tmp_path / "config.json"
    path.write_bytes(raw.encode("utf-8"))

    parsed = parse(path)

    assert parsed.text == raw
    assert parsed.metadata["json_root"] == "dict"


def test_csv_rows_and_columns(tmp_path: Path) -> None:
    path = tmp_path / "users.csv"
    path.write_text("id,name\n1,Ada\n2,Grace\n", encoding="utf-8")

    parsed = parse(path)

    assert parsed.metadata["rows"] == 2
    assert parsed.metadata["columns"] == 2
    assert parsed.text == "id | name\n1 | Ada\n2 | Grace"
