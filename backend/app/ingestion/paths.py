"""Upload path handling.

Uploaded archives and folders carry attacker-controlled paths, so every path is
reduced to a normalised POSIX relative path before it touches the filesystem.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from app.core.exceptions import InvalidUploadError

MAX_RELATIVE_PATH_CHARS = 512


def safe_relative_path(raw: str) -> str:
    """Return a normalised relative path, or raise :class:`InvalidUploadError`.

    Rejects absolute paths, drive letters, UNC paths, ``..`` segments, control
    characters and NUL bytes — the shapes used for path traversal (zip-slip).
    """
    if not raw or "\x00" in raw:
        raise InvalidUploadError("A file path is empty or contains a NUL byte")

    candidate = raw.replace("\\", "/").strip()
    while candidate.startswith("./"):
        candidate = candidate[2:]

    if not candidate:
        raise InvalidUploadError("A file path is empty")
    if len(candidate) > MAX_RELATIVE_PATH_CHARS:
        raise InvalidUploadError(
            f"A file path is longer than {MAX_RELATIVE_PATH_CHARS} characters"
        )
    if candidate.startswith("/") or candidate.startswith("//"):
        raise InvalidUploadError(f"Absolute paths are not allowed: {raw!r}")
    if ":" in candidate.split("/", 1)[0]:
        raise InvalidUploadError(f"Drive-qualified paths are not allowed: {raw!r}")
    if any(ord(character) < 32 for character in candidate):
        raise InvalidUploadError(f"A file path contains control characters: {raw!r}")

    # Reject Windows-invalid characters and NTFS alternate data stream syntax
    # in every segment, not just the first (drive-qualified) segment.
    windows_invalid = set('<>:\\"|?*')
    reserved_names = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    raw_parts = candidate.split("/")
    for part in raw_parts:
        if any(character in windows_invalid for character in part):
            raise InvalidUploadError(f"A file path contains a Windows-reserved character: {raw!r}")
        if part.endswith((".", " ")):
            raise InvalidUploadError(f"A file path segment cannot end in a dot or space: {raw!r}")
        device_name = part.split(".", 1)[0].upper()
        if device_name in reserved_names:
            raise InvalidUploadError(f"A file path contains a reserved Windows device name: {raw!r}")

    parts = [part for part in PurePosixPath(candidate).parts if part not in ("", ".")]
    if not parts:
        raise InvalidUploadError(f"A file path has no name: {raw!r}")
    if any(part == ".." for part in parts):
        raise InvalidUploadError(f"Path traversal is not allowed: {raw!r}")

    return "/".join(parts)


def filename_of(relative_path: str) -> str:
    """Last path segment, used for the ``documents.filename`` column."""
    return relative_path.rsplit("/", 1)[-1]
