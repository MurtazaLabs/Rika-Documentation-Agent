"""Safe ZIP extraction.

Uploaded archives are attacker-controlled: entries may be absolute paths, climb
with ``..``, point at symlinks, lie about their size, or expand enormously. All
of that is checked here before anything is written.
"""

from __future__ import annotations

import shutil
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import InvalidUploadError, PayloadTooLargeError
from app.ingestion.paths import safe_relative_path

# Decompression-bomb guard: an entry small on disk may not expand absurdly.
RATIO_CHECK_MIN_BYTES = 10 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200

_COPY_BLOCK = 1024 * 1024


@dataclass(slots=True)
class ExtractedEntry:
    relative_path: str
    size: int


def extract_zip(
    zip_path: Path,
    destination: Path,
    *,
    max_files: int,
    max_expanded_bytes: int,
) -> list[ExtractedEntry]:
    """Extract ``zip_path`` into ``destination`` within the given limits."""
    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as error:
        raise InvalidUploadError("The uploaded file is not a valid ZIP archive") from error

    extracted: list[ExtractedEntry] = []
    total = 0
    seen: set[str] = set()

    with archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        if len(members) > max_files:
            raise PayloadTooLargeError(
                f"The archive contains {len(members)} files; the limit is {max_files}"
            )

        for info in members:
            relative_path = safe_relative_path(info.filename)
            if info.flag_bits & 0x1:
                raise InvalidUploadError(
                    f"Encrypted archive entries are not supported: {relative_path}"
                )
            if _is_symlink(info):
                raise InvalidUploadError(
                    f"Symbolic links are not allowed in archives: {relative_path}"
                )
            if relative_path in seen:
                raise InvalidUploadError(
                    f"The archive contains the same path twice: {relative_path}"
                )
            seen.add(relative_path)

            size = info.file_size
            if size > max_expanded_bytes:
                raise PayloadTooLargeError(
                    f"{relative_path} expands to {size} bytes, which exceeds the limit"
                )
            if (
                size > RATIO_CHECK_MIN_BYTES
                and info.compress_size > 0
                and size / info.compress_size > MAX_COMPRESSION_RATIO
            ):
                raise PayloadTooLargeError(
                    f"{relative_path} has a suspicious compression ratio "
                    f"({size}/{info.compress_size}); refusing to extract"
                )

            total += size
            if total > max_expanded_bytes:
                raise PayloadTooLargeError(
                    f"The archive expands beyond {max_expanded_bytes} bytes"
                )

            target = destination / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            written = _copy_member(archive, info, target, max_expanded_bytes)
            if written != size:
                raise InvalidUploadError(
                    f"{relative_path} did not match its declared size "
                    f"({written} of {size} bytes); the archive may be corrupt"
                )
            extracted.append(ExtractedEntry(relative_path=relative_path, size=written))

    if not extracted:
        raise InvalidUploadError("The archive contains no files")
    return extracted


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return stat.S_ISLNK(mode)


def _copy_member(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, target: Path, limit: int
) -> int:
    """Copy one member, aborting if the real output exceeds the limit."""
    written = 0
    try:
        with archive.open(info) as source, target.open("wb") as destination:
            while True:
                block = source.read(_COPY_BLOCK)
                if not block:
                    break
                written += len(block)
                if written > limit:
                    raise PayloadTooLargeError(
                        f"{info.filename} expands beyond the {limit}-byte limit"
                    )
                destination.write(block)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return written
