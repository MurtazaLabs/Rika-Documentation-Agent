"""Supported upload formats.

Every accepted extension maps to a parser family and to the content type stored
on its chunks. Formats whose parsing arrives later (images, OCR) are
deliberately absent so an upload is rejected up front instead of producing an
empty document.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from app.database.models.enums import ContentType


@dataclass(frozen=True, slots=True)
class FileFormat:
    """How one extension is parsed and how its chunks are labelled."""

    file_type: str
    content_type: ContentType
    language: str | None = None


def _plain(file_type: str, content_type: ContentType = ContentType.DOCUMENT) -> FileFormat:
    return FileFormat(file_type=file_type, content_type=content_type)


def _code(language: str) -> FileFormat:
    return FileFormat(
        file_type="code", content_type=ContentType.CODE, language=language
    )


BY_EXTENSION: dict[str, FileFormat] = {}


def _add(format_: FileFormat, *extensions: str) -> None:
    for extension in extensions:
        BY_EXTENSION[extension] = format_


_add(_plain("text"), ".txt", ".text", ".log", ".rst")
_add(_plain("markdown"), ".md", ".markdown", ".mdx")
_add(_plain("json"), ".json", ".ndjson")
_add(_plain("yaml"), ".yaml", ".yml")
_add(_plain("toml"), ".toml")
_add(_plain("xml"), ".xml")
_add(_plain("csv"), ".csv", ".tsv")
_add(_plain("html"), ".html", ".htm")
_add(_plain("pdf"), ".pdf")
_add(_plain("docx"), ".docx")
_add(_plain("pptx"), ".pptx")
_add(_plain("xlsx"), ".xlsx")

_add(_code("python"), ".py", ".pyi")
_add(_code("javascript"), ".js", ".mjs", ".cjs", ".jsx")
_add(_code("typescript"), ".ts", ".tsx")
_add(_code("java"), ".java")
_add(_code("kotlin"), ".kt", ".kts")
_add(_code("swift"), ".swift")
_add(_code("go"), ".go")
_add(_code("rust"), ".rs")
_add(_code("ruby"), ".rb")
_add(_code("php"), ".php")
_add(_code("csharp"), ".cs")
_add(_code("c"), ".c", ".h")
_add(_code("cpp"), ".cc", ".cpp", ".cxx", ".hpp", ".hh")
_add(_code("sql"), ".sql")
_add(_code("css"), ".css", ".scss", ".sass", ".less")
_add(_code("shell"), ".sh", ".bash", ".zsh")
_add(_code("powershell"), ".ps1", ".psm1")
_add(_code("vue"), ".vue")
_add(_code("svelte"), ".svelte")


# Templates are indexable; a real ``.env`` is not, so a secret can never be
# stored in the project index by accident.
ENV_TEMPLATES = {".env.example", ".env.sample", ".env.template"}

# Credentials that must never reach the index. Extensions alone do not catch
# these: ``credentials.json`` and ``id_rsa`` are otherwise ordinary files.
SECRET_NAMES = frozenset(
    {
        ".envrc",
        ".netrc",
        ".npmrc",
        ".pypirc",
        ".htpasswd",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
        "credentials.json",
        "secrets.json",
        "secrets.yaml",
        "secrets.yml",
        "terraform.tfstate",
    }
)
SECRET_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"})


def is_secret_path(filename: str) -> bool:
    """True when a filename is a credentials container rather than content."""
    name = PurePosixPath(filename).name.lower()
    if name in ENV_TEMPLATES:
        return False
    if name == ".env" or name.startswith(".env."):
        return True
    if name.startswith("service-account") and name.endswith(".json"):
        return True
    return name in SECRET_NAMES or PurePosixPath(name).suffix in SECRET_SUFFIXES


def format_for(filename: str) -> FileFormat | None:
    """Return the format for a filename, or ``None`` when unsupported."""
    path = PurePosixPath(filename)
    if path.name.lower() in ENV_TEMPLATES:
        return _plain("config")
    return BY_EXTENSION.get(path.suffix.lower())


def supported_extensions() -> list[str]:
    return sorted(BY_EXTENSION)
