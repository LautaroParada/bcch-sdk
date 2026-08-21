from __future__ import annotations

import csv
import gzip
import json
import subprocess
import sys
from importlib import resources
from pathlib import Path

import pytest

from bcch import SeriesCatalog
from scripts.update_catalog import (
    OUTPUT_COLUMNS,
    compute_statistics,
    validate_statistics,
    write_outputs,
)

PIB_EXAMPLE = "F032.PIB.FLU.R.CLP.EP18.Z.Z.0.T"


@pytest.fixture(scope="module")
def catalog() -> SeriesCatalog:
    return SeriesCatalog()


def test_catalog_load_and_unique_series_count(catalog: SeriesCatalog) -> None:
    assert len(catalog) == 24_980


def test_catalog_preserves_all_source_rows(catalog: SeriesCatalog) -> None:
    assert sum(len(entry.contexts) for entry in catalog) == 30_272


def test_catalog_metadata(catalog: SeriesCatalog) -> None:
    metadata = catalog.metadata

    assert metadata["source"] == "Banco Central de Chile - Base de Datos Estadísticos"
    assert metadata["snapshot_date"] == "2026-08-21"
    assert metadata["rows"] == 30_272
    assert metadata["unique_series"] == 24_980
    assert metadata["duplicated_codes"] == 3_704
    assert metadata["duplicate_context_rows"] == 5_292
    assert metadata["missing_api"] == 5
    assert metadata["missing_first_value_date"] == 5


def test_duplicate_contexts_are_preserved(catalog: SeriesCatalog) -> None:
    duplicated = next(entry for entry in catalog if len(entry.contexts) > 1)

    assert len(duplicated.contexts) > 1
    assert all(context.name for context in duplicated.contexts)


def test_pib_example_has_all_ten_contexts(catalog: SeriesCatalog) -> None:
    entry = catalog.get(PIB_EXAMPLE)

    assert entry is not None
    assert len(entry.contexts) == 10
    assert {context.chapter for context in entry.contexts} == {
        "Cuentas Nacionales",
        "Indicadores Mercado de la Vivienda",
        "Principales Estadísticas Macro",
        "Regionales",
    }


def test_catalog_missing_values_are_preserved(catalog: SeriesCatalog) -> None:
    contexts = [context for entry in catalog for context in entry.contexts]

    assert sum(context.api_url is None for context in contexts) == 5
    assert sum(context.first_value_date is None for context in contexts) == 5


def test_catalog_search_filters_and_spanish_aliases(catalog: SeriesCatalog) -> None:
    results = catalog.search(
        "inflación",
        frecuencia="Mensual",
        vigencia="Vigente",
        capítulo="Derivados",
        fuente="Banco Central de Chile",
        unidad="Millones de dólares",
        limit=10,
    )

    assert results
    assert len(results) <= 10
    assert all(
        any(
            context.frequency == "Mensual"
            and context.status == "Vigente"
            and "Derivados" in context.chapter
            and "Banco Central de Chile" in context.source
            and "Millones de dólares" in context.unit
            for context in result.contexts
        )
        for result in results
    )


def test_catalog_frequency_accepts_english_alias(catalog: SeriesCatalog) -> None:
    results = catalog.search("inflación", frequency="monthly", limit=5)

    assert results
    assert all(any(context.frequency == "Mensual" for context in item.contexts) for item in results)


def test_catalog_search_is_case_insensitive(catalog: SeriesCatalog) -> None:
    lower = [item.code for item in catalog.search("dólar observado", limit=25)]
    upper = [item.code for item in catalog.search("DÓLAR OBSERVADO", limit=25)]

    assert lower
    assert lower == upper


def test_catalog_search_is_accent_insensitive(catalog: SeriesCatalog) -> None:
    accented = [item.code for item in catalog.search("inflación", limit=100)]
    plain = [item.code for item in catalog.search("inflacion", limit=100)]

    assert accented
    assert accented == plain


def test_catalog_get_unknown_and_validation(catalog: SeriesCatalog) -> None:
    assert catalog.get("NOT.A.REAL.CODE") is None
    assert catalog.search("inflación", limit=0) == []
    with pytest.raises(ValueError):
        catalog.get("")


def test_package_data_is_available() -> None:
    data = resources.files("bcch.data")

    assert data.joinpath("catalog.csv.gz").is_file()
    assert data.joinpath("catalog_metadata.json").is_file()


def test_packaged_catalog_statistics_match_generation_invariants() -> None:
    resource = resources.files("bcch.data").joinpath("catalog.csv.gz")
    with resource.open("rb") as raw:
        with gzip.open(raw, "rt", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

    statistics = compute_statistics(rows)
    validate_statistics(statistics)


def test_catalog_generation_is_byte_reproducible(tmp_path: Path) -> None:
    row = dict.fromkeys(OUTPUT_COLUMNS, "")
    row.update(
        {
            "chapter": "Precios",
            "table": "IPC",
            "code": "SERIES",
            "name": "Índice",
            "frequency": "Mensual",
            "unit": "Índice",
            "source": "Banco Central de Chile",
            "first_value_date": "2025-01-01",
            "status": "Vigente",
            "api_url": "https://example.invalid/?token=TOKEN",
        }
    )
    metadata = {"rows": 1, "snapshot_date": "2026-08-21"}
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_paths = write_outputs([row], metadata, first)
    second_paths = write_outputs([row], metadata, second)

    assert first_paths[0].read_bytes() == second_paths[0].read_bytes()
    assert first_paths[1].read_bytes() == second_paths[1].read_bytes()
    assert json.loads(first_paths[1].read_text(encoding="utf-8")) == metadata


def test_generation_validation_fails_on_changed_invariants() -> None:
    with pytest.raises(ValueError, match="Catalog invariants"):
        validate_statistics({"rows": 1})


def test_core_import_does_not_import_pandas() -> None:
    command = [
        sys.executable,
        "-c",
        "import sys; import bcch; assert 'pandas' not in sys.modules",
    ]

    completed = subprocess.run(command, check=False, capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
