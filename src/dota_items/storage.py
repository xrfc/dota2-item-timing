"""Portable JSON files, immutable directory publication, and writer locks."""

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(UTC).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(json_bytes(value)).hexdigest()


def file_hash(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def inside(root: Path, relative: str) -> Path:
    """Resolve portable relative paths without accepting traversal or symlinks."""
    if not relative or "\\" in relative or ":" in relative:
        raise ValueError(f"Invalid relative artifact path: {relative}")
    part = Path(relative)
    if part.is_absolute() or any(p in (".", "..") for p in part.parts):
        raise ValueError(f"Invalid relative artifact path: {relative}")
    path = root / part
    if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root.parent):
        raise ValueError(f"Artifact symlinks are unsupported: {relative}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Artifact is outside its directory: {relative}")
    return path


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValueError("Invalid ID; use letters, digits, hyphens, or underscores")
    return value


def hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): file_hash(
            inside(root, path.relative_to(root).as_posix())
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def verify_files(root: Path, expected: dict[str, str]) -> None:
    for relative, sha in expected.items():
        path = inside(root, relative)
        if not path.is_file() or file_hash(path) != sha:
            raise ValueError(f"Missing or changed artifact: {path}")


@contextmanager
def writer_lock(root: Path) -> Iterator[None]:
    lock = root / ".writer.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise ValueError(
            f"Workspace writer is busy: {lock}. After a crash, remove it only after "
            "confirming no import or dataset build is running."
        ) from error
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(f"pid={os.getpid()} started={now()}\n")
        yield
    finally:
        lock.unlink(missing_ok=True)
