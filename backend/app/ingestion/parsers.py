"""Text extraction.

Parsers only ever read bytes: uploaded code is never imported, executed or
evaluated. Anything that cannot be turned into text raises
:class:`ParsingError`, which the ingestion job records on the document.

Document parsers return :class:`ParsedSegment` objects alongside the flat
text. A segment carries the metadata that belongs on every chunk cut from it
(page, slide, sheet, heading/section), so the pipeline can preserve the
document's structure without embedding page markers into the text itself.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from app.ingestion.formats import FileFormat

# Bytes inspected for binary content before treating a file as text.
BINARY_SNIFF_BYTES = 8192

_ATX_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_SETEXT_UNDERLINE = re.compile(r"^[ \t]{0,3}(=+|-+)[ \t]*$")
_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")


class ParsingError(Exception):
    """The file could not be turned into usable text."""


@dataclass(slots=True)
class ParsedSegment:
    """A contiguous piece of extracted text with its structural metadata."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    # 1-based line range in the parsed text. Parsers that split a source text
    # (Markdown, HTML) set these to the source lines themselves.
    start_line: int = 1
    end_line: int = 1


@dataclass(slots=True)
class ParsedContent:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    segments: list[ParsedSegment] = field(default_factory=list)


def parse_file(path: Path, format_: FileFormat) -> ParsedContent:
    """Extract text from ``path`` according to its detected format."""
    file_type = format_.file_type
    if file_type == "pdf":
        parsed = _parse_pdf(path)
    elif file_type == "docx":
        parsed = _parse_docx(path)
    elif file_type == "pptx":
        parsed = _parse_pptx(path)
    elif file_type == "xlsx":
        parsed = _parse_xlsx(path)
    elif file_type == "html":
        parsed = _parse_html(path)
    elif file_type == "markdown":
        parsed = _parse_markdown(path)
    elif file_type == "json":
        parsed = _parse_json(path)
    elif file_type == "csv":
        parsed = _parse_csv(path)
    else:
        text = _read_text_bytes(path)
        parsed = ParsedContent(text=text)

    parsed.metadata.setdefault("file_type", file_type)
    if format_.language:
        parsed.metadata.setdefault("language", format_.language)
    return parsed


def _read_text_bytes(path: Path) -> str:
    data = path.read_bytes()
    if b"\x00" in data[:BINARY_SNIFF_BYTES]:
        raise ParsingError("File appears to be binary, not text")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _finalize_segments(
    segments: list[ParsedSegment],
    *,
    metadata: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    separator: str = "\n\n",
) -> ParsedContent:
    """Drop empty segments, assign line ranges and join the flat text."""
    kept: list[ParsedSegment] = []
    parts: list[str] = []
    cursor = 1
    for segment in segments:
        body = segment.text.strip("\n")
        if not body.strip():
            continue
        line_count = body.count("\n") + 1
        segment.text = body
        segment.start_line = cursor
        segment.end_line = cursor + line_count - 1
        kept.append(segment)
        parts.append(body)
        cursor = segment.end_line + separator.count("\n")

    return ParsedContent(
        text=separator.join(parts),
        metadata=dict(metadata or {}),
        warnings=list(warnings or []),
        segments=kept,
    )


def _parse_json(path: Path) -> ParsedContent:
    raw = _read_text_bytes(path)
    warnings: list[str] = []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        warnings.append("not valid JSON; indexed as plain text")
        return ParsedContent(text=raw, warnings=warnings)
    # Keep the source text (and its line numbers) rather than re-serialising.
    return ParsedContent(
        text=raw,
        metadata={"json_root": type(parsed).__name__},
    )


def _parse_csv(path: Path) -> ParsedContent:
    raw = _read_text_bytes(path)
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    rows: list[str] = []
    columns = 0
    try:
        reader = csv.reader(io.StringIO(raw), delimiter=delimiter)
        for row in reader:
            columns = max(columns, len(row))
            rows.append(" | ".join(cell.strip() for cell in row))
    except csv.Error as error:
        return ParsedContent(
            text=raw, warnings=[f"CSV parsing failed ({error}); indexed as plain text"]
        )
    return ParsedContent(
        text="\n".join(rows),
        metadata={"rows": max(len(rows) - 1, 0), "columns": columns},
    )


# ---------------------------------------------------------------------------
# Markdown and HTML


def _split_markdown_sections(text: str) -> list[ParsedSegment]:
    """Split Markdown into heading-delimited sections.

    Headings are recognised outside fenced code blocks, including setext
    headings. Segments cover every source line exactly once, so the line
    ranges stored on chunks point at the original file.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    total = len(lines)
    if total == 1 and not lines[0]:
        return []

    sections: list[ParsedSegment] = []
    section_start = 1
    section_meta: dict[str, Any] = {}
    heading_stack: list[tuple[int, str]] = []
    heading_count = 0
    fence: str | None = None
    index = 0

    def flush(end_line: int) -> None:
        nonlocal section_start
        if end_line >= section_start:
            body = "\n".join(lines[section_start - 1 : end_line])
            if body.strip():
                sections.append(
                    ParsedSegment(
                        text=body,
                        metadata=dict(section_meta),
                        start_line=section_start,
                        end_line=end_line,
                    )
                )
        section_start = end_line + 1

    while index < total:
        line = lines[index]
        line_number = index + 1

        fence_match = _FENCE.match(line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            index += 1
            continue
        if fence is not None:
            index += 1
            continue

        level = 0
        title = ""
        heading_lines = 1
        atx = _ATX_HEADING.match(line)
        if atx:
            level = len(atx.group(1))
            title = atx.group(2).strip()
        elif (
            line.strip()
            and index + 1 < total
            and _SETEXT_UNDERLINE.match(lines[index + 1])
            and not line.lstrip().startswith(("-", "*", "+", ">", "|"))
        ):
            level = 1 if lines[index + 1].strip().startswith("=") else 2
            title = line.strip()
            heading_lines = 2

        if level:
            flush(line_number - 1)
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            heading_count += 1
            section_meta = {
                "heading": title,
                "heading_level": level,
                "section": title,
                "section_path": " > ".join(item[1] for item in heading_stack),
            }
            section_start = line_number
            index += heading_lines
            continue

        index += 1

    flush(total)
    if not sections:
        return []
    sections[0].metadata.setdefault("_heading_count", heading_count)
    return sections


def _parse_markdown(path: Path) -> ParsedContent:
    text = _read_text_bytes(path)
    if not text.strip():
        raise ParsingError("The Markdown file contains no text")
    segments = _split_markdown_sections(text)
    headings = max(
        (int(segment.metadata.get("_heading_count", 0)) for segment in segments),
        default=0,
    )
    for segment in segments:
        segment.metadata.pop("_heading_count", None)
    return ParsedContent(
        text=text,
        metadata={"headings": headings, "sections": len(segments)},
        segments=segments,
    )


class _HtmlSectionExtractor(HTMLParser):
    """Collect visible text as Markdown-like lines, keeping headings/tables."""

    BLOCK_TAGS = {
        "br",
        "div",
        "p",
        "li",
        "tr",
        "section",
        "article",
        "header",
        "footer",
        "pre",
        "blockquote",
        "dl",
        "dt",
        "dd",
        "hr",
    }
    SKIP_TAGS = {"script", "style", "noscript", "template"}
    HEADING_TAGS = {
        "h1": 1,
        "h2": 2,
        "h3": 3,
        "h4": 4,
        "h5": 5,
        "h6": 6,
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._heading_level = 0
        self._row_has_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in self.HEADING_TAGS:
            self.parts.append("\n" + "#" * self.HEADING_TAGS[tag] + " ")
            self._heading_level = self.HEADING_TAGS[tag]
        elif tag in ("td", "th"):
            if self._row_has_cell:
                self.parts.append(" | ")
            self._row_has_cell = True
        elif tag == "tr":
            self.parts.append("\n")
            self._row_has_cell = False
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self.HEADING_TAGS:
            self.parts.append("\n")
            self._heading_level = 0
        elif tag == "tr":
            self.parts.append("\n")
            self._row_has_cell = False
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        lines: list[str] = []
        for raw_line in "".join(self.parts).splitlines():
            line = " ".join(raw_line.split())
            if line:
                lines.append(line)
        return "\n".join(lines)


def _parse_html(path: Path) -> ParsedContent:
    raw = _read_text_bytes(path)
    extractor = _HtmlSectionExtractor()
    extractor.feed(raw)
    extractor.close()
    text = extractor.text()
    if not text:
        raise ParsingError("No visible text found in the HTML document")
    segments = _split_markdown_sections(text)
    headings = 0
    for segment in segments:
        headings += 1 if segment.metadata.get("heading") else 0
    for segment in segments:
        segment.metadata.pop("_heading_count", None)
    return ParsedContent(
        text=text,
        metadata={"headings": headings, "sections": max(len(segments), 1)},
        segments=segments,
    )


# ---------------------------------------------------------------------------
# PDF


def _parse_pdf(path: Path) -> ParsedContent:
    try:
        import pymupdf  # PyMuPDF
    except ImportError as error:  # pragma: no cover - dependency is pinned
        raise ParsingError("PDF parsing requires PyMuPDF") from error

    segments: list[ParsedSegment] = []
    warnings: list[str] = []
    with pymupdf.open(path) as document:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if text:
                segments.append(
                    ParsedSegment(
                        text=text,
                        metadata={"page_number": page_number},
                    )
                )
        page_count = document.page_count

    if not segments:
        raise ParsingError(
            "No extractable text; the PDF is probably scanned (OCR is not enabled)"
        )
    if len(segments) < page_count:
        warnings.append(f"{page_count - len(segments)} page(s) contained no text")
    parsed = _finalize_segments(
        segments,
        metadata={"pages": page_count},
        warnings=warnings,
    )
    # Every page keeps its 1-based page number in the segment metadata.
    return parsed


# ---------------------------------------------------------------------------
# DOCX


def _docx_heading_level(paragraph: Any) -> int | None:
    style = getattr(paragraph, "style", None)
    name = (getattr(style, "name", "") or "").strip()
    if not name:
        return None
    title = name.lower()
    if title == "title":
        return 1
    match = re.match(r"heading\s*(\d+)", title)
    if match:
        return max(1, min(6, int(match.group(1))))
    return None


def _parse_docx(path: Path) -> ParsedContent:
    try:
        import docx  # python-docx
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as error:  # pragma: no cover - dependency is pinned
        raise ParsingError("DOCX parsing requires python-docx") from error

    try:
        document = docx.Document(str(path))
    except Exception as error:  # noqa: BLE001 - library raises many types
        raise ParsingError(f"DOCX could not be opened: {error}") from error

    segments: list[ParsedSegment] = []
    warnings: list[str] = []
    heading_stack: list[tuple[int, str]] = []
    section_lines: list[str] = []
    section_meta: dict[str, Any] = {}
    paragraph_count = 0
    table_rows = 0
    table_count = 0
    heading_count = 0

    def flush() -> None:
        nonlocal section_lines, section_meta
        if section_lines:
            segments.append(
                ParsedSegment(text="\n".join(section_lines), metadata=dict(section_meta))
            )
        section_lines = []
        section_meta = {}

    body = document.element.body
    for child in body.iterchildren():
        if child.tag.endswith("}p"):
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            if not text:
                continue
            paragraph_count += 1
            level = _docx_heading_level(paragraph)
            if level:
                flush()
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, text))
                heading_count += 1
                section_meta = {
                    "heading": text,
                    "heading_level": level,
                    "section": text,
                    "section_path": " > ".join(item[1] for item in heading_stack),
                }
                section_lines = [text]
            else:
                section_lines.append(text)
        elif child.tag.endswith("}tbl"):
            table = Table(child, document)
            table_count += 1
            for row in table.rows:
                cells = [" ".join(cell.text.split()) for cell in row.cells]
                if any(cells):
                    section_lines.append(" | ".join(cells))
                    table_rows += 1
    flush()

    if not any(segment.text.strip() for segment in segments):
        raise ParsingError("The DOCX file contains no text")

    parsed = _finalize_segments(
        segments,
        metadata={
            "paragraphs": paragraph_count,
            "tables": table_count,
            "table_rows": table_rows,
            "headings": heading_count,
            "sections": max(len(segments), 1),
        },
        warnings=warnings,
    )
    return parsed


# ---------------------------------------------------------------------------
# PowerPoint


def _pptx_shape_lines(shape: Any, warnings: list[str]) -> list[str]:
    """Flatten one shape (including grouped shapes) into text lines."""
    try:
        from pptx.enum.shapes import MSO_SHAPE_TYPE
    except ImportError as error:  # pragma: no cover - dependency is pinned
        raise ParsingError("PPTX parsing requires python-pptx") from error

    lines: list[str] = []
    if getattr(shape, "shape_type", None) == MSO_SHAPE_TYPE.GROUP:
        for child in shape.shapes:
            lines.extend(_pptx_shape_lines(child, warnings))
        return lines

    if getattr(shape, "has_table", False):
        for row in shape.table.rows:
            cells = [" ".join(cell.text.split()) for cell in row.cells]
            if any(cells):
                lines.append(" | ".join(cells))
        return lines

    if getattr(shape, "has_text_frame", False):
        for paragraph in shape.text_frame.paragraphs:
            text = " ".join(paragraph.text.split())
            if text:
                lines.append(text)
    return lines


def _parse_pptx(path: Path) -> ParsedContent:
    try:
        from pptx import Presentation
    except ImportError as error:  # pragma: no cover - dependency is pinned
        raise ParsingError("PPTX parsing requires python-pptx") from error

    try:
        presentation = Presentation(str(path))
    except Exception as error:  # noqa: BLE001 - library raises many types
        raise ParsingError(f"PPTX could not be opened: {error}") from error

    segments: list[ParsedSegment] = []
    warnings: list[str] = []
    table_count = 0
    empty_slides = 0

    for slide_number, slide in enumerate(presentation.slides, start=1):
        lines: list[str] = []
        title_shape = slide.shapes.title
        title = " ".join(title_shape.text.split()) if title_shape is not None else ""

        for shape in slide.shapes:
            if title_shape is not None and shape is title_shape:
                continue
            if getattr(shape, "has_table", False):
                table_count += 1
            lines.extend(_pptx_shape_lines(shape, warnings))

        if title and title not in lines:
            lines.insert(0, title)
        elif title and not lines:
            lines = [title]

        if not lines:
            empty_slides += 1
            continue

        metadata: dict[str, Any] = {"slide_number": slide_number}
        if title:
            metadata.update({"title": title, "section": title})
        segments.append(ParsedSegment(text="\n".join(lines), metadata=metadata))

    if not segments:
        raise ParsingError(
            "The PPTX file contains no extractable text (OCR is not enabled)"
        )
    if empty_slides:
        warnings.append(f"{empty_slides} slide(s) contained no extractable text")
    return _finalize_segments(
        segments,
        metadata={
            "slides": len(presentation.slides),
            "tables": table_count,
        },
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Excel


def _parse_xlsx(path: Path) -> ParsedContent:
    try:
        from openpyxl import load_workbook
    except ImportError as error:  # pragma: no cover - dependency is pinned
        raise ParsingError("XLSX parsing requires openpyxl") from error

    try:
        workbook = load_workbook(filename=str(path), read_only=True, data_only=True)
    except Exception as error:  # noqa: BLE001 - library raises many types
        raise ParsingError(f"XLSX could not be opened: {error}") from error

    segments: list[ParsedSegment] = []
    warnings: list[str] = []
    sheet_names = list(workbook.sheetnames)
    total_rows = 0
    total_columns = 0
    empty_sheets = 0

    try:
        for sheet in workbook.worksheets:
            rows: list[str] = []
            sheet_rows = 0
            sheet_columns = 0
            for row in sheet.iter_rows(values_only=True):
                cells = ["" if value is None else str(value).strip() for value in row]
                if not any(cells):
                    continue
                # Trim trailing empty cells; keep interior gaps so columns line up.
                while cells and not cells[-1]:
                    cells.pop()
                if not cells:
                    continue
                rows.append(" | ".join(cells))
                sheet_rows += 1
                sheet_columns = max(sheet_columns, len(cells))

            total_rows += sheet_rows
            total_columns = max(total_columns, sheet_columns)
            if not rows:
                empty_sheets += 1
                continue

            title = sheet.title
            segments.append(
                ParsedSegment(
                    text="\n".join([title, *rows]),
                    metadata={
                        "sheet_name": title,
                        "section": title,
                        "heading": title,
                        "heading_level": 1,
                        "rows": sheet_rows,
                        "columns": sheet_columns,
                    },
                )
            )
    finally:
        workbook.close()

    if not segments:
        raise ParsingError("The XLSX file contains no cell text")
    if empty_sheets:
        warnings.append(f"{empty_sheets} sheet(s) contained no data")
    return _finalize_segments(
        segments,
        metadata={
            "sheets": len(sheet_names),
            "sheet_names": sheet_names,
            "rows": total_rows,
            "columns": total_columns,
        },
        warnings=warnings,
    )


__all__ = [
    "ParsedContent",
    "ParsedSegment",
    "ParsingError",
    "parse_file",
]
