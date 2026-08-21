#!/usr/bin/env python3
"""Convert the official BDE XLSX catalog into deterministic package data."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

SHEET_NAME = "Series BDE"
SOURCE_COLUMNS = (
    "CAPÍTULO",
    "NOMBRE CUADRO",
    "CODIGO_SERIE",
    "NOMBRE_SERIE",
    "FRECUENCIA",
    "UNIDAD",
    "FUENTE",
    "FECHA_PRIMER_VALOR",
    "VIGENCIA",
    "API",
)
OUTPUT_COLUMNS = (
    "chapter",
    "table",
    "code",
    "name",
    "frequency",
    "unit",
    "source",
    "first_value_date",
    "status",
    "api_url",
)
EXPECTED = {
    "rows": 30_272,
    "unique_series": 24_980,
    "duplicated_codes": 3_704,
    "duplicate_context_rows": 5_292,
    "missing_api": 5,
    "missing_first_value_date": 5,
    "frequency_counts": {
        "Anual": 7_287,
        "Diaria": 2_101,
        "Mensual": 10_563,
        "Trimestral": 10_321,
    },
    "status_counts": {
        "Descontinuado": 195,
        "Histórico": 10_806,
        "Vigente": 19_271,
    },
    "pib_example_contexts": 10,
}
PIB_EXAMPLE = "F032.PIB.FLU.R.CLP.EP18.Z.Z.0.T"


def read_workbook(path: Path) -> list[dict[str, str]]:
    """Read and normalize all source rows without deduplicating them."""
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("openpyxl is required; install the dev extra") from exc

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    if SHEET_NAME not in workbook.sheetnames:
        raise ValueError(f"Required worksheet is missing: {SHEET_NAME}")
    worksheet = workbook[SHEET_NAME]
    values = worksheet.iter_rows(values_only=True)
    try:
        header = tuple(next(values))
    except StopIteration as exc:
        raise ValueError("Catalog workbook is empty") from exc
    if header != SOURCE_COLUMNS:
        raise ValueError(
            "Catalog schema changed. "
            f"Expected columns {SOURCE_COLUMNS!r}; received {header!r}"
        )

    rows: list[dict[str, str]] = []
    for source_row in values:
        if len(source_row) != len(SOURCE_COLUMNS):
            raise ValueError("Catalog row has an unexpected number of columns")
        normalized = [_normalize_value(value) for value in source_row]
        rows.append(dict(zip(OUTPUT_COLUMNS, normalized, strict=True)))
    workbook.close()
    return rows


def compute_statistics(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Compute the source invariants used to detect upstream changes."""
    code_counts = Counter(row["code"] for row in rows)
    return {
        "rows": len(rows),
        "unique_series": len(code_counts),
        "duplicated_codes": sum(count > 1 for count in code_counts.values()),
        "duplicate_context_rows": sum(count - 1 for count in code_counts.values()),
        "missing_api": sum(not row["api_url"] for row in rows),
        "missing_first_value_date": sum(not row["first_value_date"] for row in rows),
        "frequency_counts": dict(
            sorted(Counter(row["frequency"] for row in rows).items())
        ),
        "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
        "pib_example_contexts": code_counts[PIB_EXAMPLE],
    }


def validate_statistics(statistics: dict[str, Any]) -> None:
    """Fail loudly when the supplied catalog does not match the approved snapshot."""
    if statistics == EXPECTED:
        return
    differences = {
        key: {"expected": EXPECTED[key], "actual": statistics.get(key)}
        for key in EXPECTED
        if statistics.get(key) != EXPECTED[key]
    }
    raise ValueError(
        "Catalog invariants do not match the approved source: "
        + json.dumps(differences, ensure_ascii=False, sort_keys=True)
    )


def build_metadata(statistics: dict[str, Any], snapshot_date: str) -> dict[str, Any]:
    """Build portable metadata without local paths or generation timestamps."""
    return {
        "source": "Banco Central de Chile - Base de Datos Estadísticos",
        "snapshot_date": snapshot_date,
        **statistics,
    }


def write_outputs(
    rows: list[dict[str, str]], metadata: dict[str, Any], output_dir: Path
) -> tuple[Path, Path]:
    """Write deterministic gzip CSV and JSON artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = output_dir / "catalog.csv.gz"
    metadata_path = output_dir / "catalog_metadata.json"
    catalog_path.write_bytes(_gzip_csv(rows))
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return catalog_path, metadata_path


def _gzip_csv(rows: list[dict[str, str]]) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as compressed:
        with io.TextIOWrapper(
            compressed, encoding="utf-8", newline="", write_through=True
        ) as text:
            writer = csv.DictWriter(
                text,
                fieldnames=OUTPUT_COLUMNS,
                lineterminator="\n",
                extrasaction="raise",
            )
            writer.writeheader()
            writer.writerows(rows)
    return buffer.getvalue()


def _normalize_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", type=Path, help="Path to the official BDE XLSX catalog")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src" / "bcch" / "data",
    )
    parser.add_argument("--snapshot-date", default="2026-08-21")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = read_workbook(args.xlsx)
    statistics = compute_statistics(rows)
    validate_statistics(statistics)
    metadata = build_metadata(statistics, args.snapshot_date)
    catalog_path, metadata_path = write_outputs(rows, metadata, args.output_dir)
    print(f"Wrote {catalog_path.name} and {metadata_path.name}")
    print(json.dumps(statistics, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
