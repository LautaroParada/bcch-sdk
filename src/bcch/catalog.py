"""Offline access to the packaged BDE series catalog snapshot."""

from __future__ import annotations

import csv
import gzip
import json
import unicodedata
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from importlib import resources
from typing import Any


def _fold(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


_LOCAL_FREQUENCIES = {
    "daily": "diaria",
    "diaria": "diaria",
    "monthly": "mensual",
    "mensual": "mensual",
    "quarterly": "trimestral",
    "trimestral": "trimestral",
    "annual": "anual",
    "anual": "anual",
}


@dataclass(frozen=True, slots=True)
class SeriesCatalogContext:
    """One source row describing where a series appears in the BDE catalog."""

    chapter: str
    table: str
    name: str
    frequency: str
    unit: str
    source: str
    first_value_date: date | None
    status: str
    api_url: str | None


@dataclass(frozen=True, slots=True)
class SeriesCatalogEntry:
    """A unique series code with every catalog context retained."""

    code: str
    contexts: tuple[SeriesCatalogContext, ...]


class SeriesCatalog:
    """Lazy, network-free reader for the packaged catalog snapshot."""

    def __init__(self) -> None:
        self._entries: dict[str, SeriesCatalogEntry] | None = None
        self._metadata: dict[str, Any] | None = None

    @property
    def metadata(self) -> dict[str, Any]:
        if self._metadata is None:
            metadata_resource = resources.files("bcch.data").joinpath("catalog_metadata.json")
            with metadata_resource.open("r", encoding="utf-8") as handle:
                metadata = json.load(handle)
            if not isinstance(metadata, dict):
                raise ValueError("Packaged catalog metadata must be a JSON object")
            self._metadata = metadata
        return dict(self._metadata)

    def get(self, code: str) -> SeriesCatalogEntry | None:
        """Return a series and all of its source contexts, or None if absent."""
        if not isinstance(code, str) or not code.strip():
            raise ValueError("code must be a non-empty string")
        return self._load().get(code.strip())

    def search(
        self,
        text: str | None = None,
        *,
        frequency: str | None = None,
        status: str | None = None,
        chapter: str | None = None,
        source: str | None = None,
        unit: str | None = None,
        limit: int | None = None,
        **aliases: str,
    ) -> list[SeriesCatalogEntry]:
        """Search the local snapshot using case- and accent-insensitive matching."""
        frequency = _resolve_alias(frequency, aliases, "frecuencia")
        status = _resolve_alias(status, aliases, "vigencia")
        chapter = _resolve_alias(chapter, aliases, "capítulo", "capitulo")
        source = _resolve_alias(source, aliases, "fuente")
        unit = _resolve_alias(unit, aliases, "unidad")
        if aliases:
            unexpected = ", ".join(sorted(aliases))
            raise TypeError(f"Unexpected catalog search parameter(s): {unexpected}")
        if limit is not None and limit < 0:
            raise ValueError("limit cannot be negative")
        if limit == 0:
            return []

        folded_text = _fold(text)
        folded_frequency = _fold(frequency)
        folded_frequency = _LOCAL_FREQUENCIES.get(folded_frequency, folded_frequency)
        folded_status = _fold(status)
        folded_chapter = _fold(chapter)
        folded_source = _fold(source)
        folded_unit = _fold(unit)

        results: list[SeriesCatalogEntry] = []
        for entry in self._load().values():
            if folded_text and not _entry_contains(entry, folded_text):
                continue
            if not any(
                _context_matches(
                    context,
                    frequency=folded_frequency,
                    status=folded_status,
                    chapter=folded_chapter,
                    source=folded_source,
                    unit=folded_unit,
                )
                for context in entry.contexts
            ):
                continue
            results.append(entry)
            if limit is not None and len(results) >= limit:
                break
        return results

    def __len__(self) -> int:
        return len(self._load())

    def __iter__(self) -> Iterator[SeriesCatalogEntry]:
        return iter(self._load().values())

    def _load(self) -> dict[str, SeriesCatalogEntry]:
        if self._entries is not None:
            return self._entries
        grouped: defaultdict[str, list[SeriesCatalogContext]] = defaultdict(list)
        catalog_resource = resources.files("bcch.data").joinpath("catalog.csv.gz")
        with catalog_resource.open("rb") as raw_handle:
            with gzip.open(raw_handle, mode="rt", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    grouped[row["code"]].append(_context_from_row(row))
        self._entries = {
            code: SeriesCatalogEntry(code=code, contexts=tuple(contexts))
            for code, contexts in grouped.items()
        }
        return self._entries


def _context_from_row(row: dict[str, str]) -> SeriesCatalogContext:
    raw_date = row["first_value_date"]
    return SeriesCatalogContext(
        chapter=row["chapter"],
        table=row["table"],
        name=row["name"],
        frequency=row["frequency"],
        unit=row["unit"],
        source=row["source"],
        first_value_date=date.fromisoformat(raw_date) if raw_date else None,
        status=row["status"],
        api_url=row["api_url"] or None,
    )


def _resolve_alias(
    current: str | None, aliases: dict[str, str], *names: str
) -> str | None:
    for name in names:
        if name not in aliases:
            continue
        candidate = aliases.pop(name)
        if current is not None and candidate != current:
            raise TypeError(f"Conflicting values for {name}")
        current = candidate
    return current


def _entry_contains(entry: SeriesCatalogEntry, query: str) -> bool:
    if query in _fold(entry.code):
        return True
    return any(
        query
        in _fold(
            " ".join(
                (
                    context.chapter,
                    context.table,
                    context.name,
                    context.frequency,
                    context.unit,
                    context.source,
                    context.status,
                )
            )
        )
        for context in entry.contexts
    )


def _context_matches(
    context: SeriesCatalogContext,
    *,
    frequency: str,
    status: str,
    chapter: str,
    source: str,
    unit: str,
) -> bool:
    return (
        (not frequency or _fold(context.frequency) == frequency)
        and (not status or _fold(context.status) == status)
        and (not chapter or chapter in _fold(context.chapter))
        and (not source or source in _fold(context.source))
        and (not unit or unit in _fold(context.unit))
    )
