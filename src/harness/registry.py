"""Version registry: persist every scored version, mark current, roll back.

Design constraints (see CLAUDE.md / docs/architecture.md):
- Unlike scoring/gate, this module does I/O by design -- it IS the durable
  audit trail (v1=0.81, v2=0.86, ...). No LLM calls.
- Append-only history: registering a version never deletes or rewrites a
  prior record's score or timestamp -- only the `is_current` flag ever
  changes, to preserve the "at most one current version" invariant.
- Storage is a JSON-lines file; each line is one `VersionRecord`.
"""

from __future__ import annotations

import json
from pathlib import Path

from schema.models import VersionRecord

DEFAULT_REGISTRY_PATH = Path("data/registry/failure_vs_suspension_versions.jsonl")


class RegistryError(RuntimeError):
    """Raised when a registry operation refers to an unknown version."""


def _read_all(path: Path) -> list[VersionRecord]:
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(VersionRecord.model_validate(json.loads(line)))
    return records


def _write_all(path: Path, records: list[VersionRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [record.model_dump_json() for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def register_version(record: VersionRecord, *, path: Path | None = None) -> None:
    """Append `record` to the registry history.

    If `record.is_current` is True, every previously-registered record has its
    `is_current` flag cleared first, so at most one record is ever current.
    """
    registry_path = path if path is not None else DEFAULT_REGISTRY_PATH
    records = _read_all(registry_path)
    if record.is_current:
        records = [r.model_copy(update={"is_current": False}) for r in records]
    records.append(record)
    _write_all(registry_path, records)


def current_version(path: Path | None = None) -> VersionRecord | None:
    """Return the record currently marked `is_current`, if any."""
    registry_path = path if path is not None else DEFAULT_REGISTRY_PATH
    for record in reversed(_read_all(registry_path)):
        if record.is_current:
            return record
    return None


def history(path: Path | None = None) -> list[VersionRecord]:
    """Return every registered record, in registration order."""
    registry_path = path if path is not None else DEFAULT_REGISTRY_PATH
    return _read_all(registry_path)


def rollback(version: str, *, path: Path | None = None) -> VersionRecord:
    """Mark the most recently registered record for `version` as current.

    Does not re-score anything; it only flips which already-registered
    version is current. Raises `RegistryError` if `version` was never
    registered.
    """
    registry_path = path if path is not None else DEFAULT_REGISTRY_PATH
    records = _read_all(registry_path)

    target_index: int | None = None
    for i, record in enumerate(records):
        if record.skill_version == version:
            target_index = i  # keep the last (most recent) match

    if target_index is None:
        raise RegistryError(f"cannot roll back to unknown version: {version!r}")

    updated = [
        r.model_copy(update={"is_current": i == target_index}) for i, r in enumerate(records)
    ]
    _write_all(registry_path, updated)
    return updated[target_index]
