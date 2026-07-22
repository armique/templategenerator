"""Tests for bounded CSV and XLSX sales readers."""

from pathlib import Path

import pytest
from openpyxl import Workbook

from marktwert.application.imports import SalesFileError
from marktwert.infrastructure.imports import TabularSalesFileReaderFactory


def test_csv_reader_detects_semicolon_and_normalizes_headers(tmp_path: Path) -> None:
    path = tmp_path / "sales.csv"
    path.write_text(
        "Artikelnummer;Titel;Verkaufspreis;Verkauft am\n"
        "123;RTX 3070;299,99 €;21.07.2026\n",
        encoding="utf-8",
    )

    reader = TabularSalesFileReaderFactory().create(path)
    rows = tuple(reader.read_rows(path))

    assert len(rows) == 1
    assert rows[0].row_number == 2
    assert rows[0].values == {
        "artikelnummer": "123",
        "titel": "RTX 3070",
        "verkaufspreis": "299,99 €",
        "verkauft_am": "21.07.2026",
    }


def test_xlsx_reader_streams_first_worksheet(tmp_path: Path) -> None:
    path = tmp_path / "sales.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["Item ID", "Title", "Sold Price", "Sold At"])
    worksheet.append(["123", "RTX 3070", 299.99, "2026-07-21"])
    workbook.save(path)
    workbook.close()

    reader = TabularSalesFileReaderFactory().create(path)
    rows = tuple(reader.read_rows(path))

    assert rows[0].values["item_id"] == "123"
    assert rows[0].values["sold_price"] == 299.99


def test_factory_rejects_unsupported_or_missing_files(tmp_path: Path) -> None:
    unsupported = tmp_path / "sales.txt"
    unsupported.write_text("data", encoding="utf-8")
    factory = TabularSalesFileReaderFactory()

    with pytest.raises(SalesFileError, match="CSV and XLSX"):
        factory.create(unsupported)
    with pytest.raises(SalesFileError, match="does not exist"):
        factory.create(tmp_path / "missing.csv")


def test_reader_rejects_duplicate_normalized_headers(tmp_path: Path) -> None:
    path = tmp_path / "sales.csv"
    path.write_text("Item ID,item-id\n1,2\n", encoding="utf-8")
    reader = TabularSalesFileReaderFactory().create(path)

    with pytest.raises(SalesFileError, match="unique"):
        tuple(reader.read_rows(path))


def test_factory_rejects_invalid_xlsx_archive(tmp_path: Path) -> None:
    path = tmp_path / "sales.xlsx"
    path.write_bytes(b"not a zip archive")

    with pytest.raises(SalesFileError, match="valid Office archive"):
        TabularSalesFileReaderFactory().create(path)
