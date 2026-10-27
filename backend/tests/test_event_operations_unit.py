"""Bounded, deterministic checks for untrusted import files and CSV exports."""

import io
import zipfile

import pytest

from app.operations.service import EventOperationsService, OperationDenied, csv_safe, parse_import


def test_csv_import_rejects_ambiguous_headers_and_overwide_rows() -> None:
    with pytest.raises(OperationDenied, match="unique"):
        parse_import("attendees.csv", b"email,email\na@example.test,b@example.test\n")
    with pytest.raises(OperationDenied, match="more values"):
        parse_import("attendees.csv", b"email\na@example.test,extra\n")
    with pytest.raises(OperationDenied, match="no participant rows"):
        parse_import("attendees.csv", b"email\n")


def test_csv_import_accepts_utf8_and_preserves_header_mapping() -> None:
    columns, rows = parse_import(
        "attendees.csv",
        b" full_name ,email,phone\nAda Lovelace, ADA@example.test ,+2348012345678\n",
    )
    assert columns == ["full_name", "email", "phone"]
    assert rows == [
        {
            "full_name": "Ada Lovelace",
            "email": "ADA@example.test",
            "phone": "+2348012345678",
        }
    ]


def test_import_mapping_accepts_a_true_email_only_export() -> None:
    columns, rows = parse_import("attendees.csv", b"email\nfirst@example.test\n")
    assert columns == ["email"] and rows == [{"email": "first@example.test"}]
    assert EventOperationsService._mapping({"email": "email"})[:2] == ("", "email")


def test_xlsx_import_rejects_formula_cells() -> None:
    sheet = b'''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>email</t></is></c></row>
      <row r="2"><c r="A2"><f>HYPERLINK("https://example.test")</f><v>0</v></c></row>
      </sheetData></worksheet>'''
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    with pytest.raises(OperationDenied, match="formulas"):
        parse_import("attendees.xlsx", output.getvalue())


def test_xlsx_import_rejects_values_outside_mapped_columns() -> None:
    sheet = b'''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>email</t></is></c></row>
      <row r="2"><c r="A2" t="inlineStr"><is><t>ada@example.test</t></is></c>
      <c r="B2" t="inlineStr"><is><t>unmapped</t></is></c></row>
      </sheetData></worksheet>'''
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    with pytest.raises(OperationDenied, match="beyond the header"):
        parse_import("attendees.xlsx", output.getvalue())


@pytest.mark.parametrize("value", ["=1+1", "+SUM(A1)", "-2+3", "@SUM(A1)"])
def test_csv_export_escapes_formula_prefixes(value: str) -> None:
    assert csv_safe(value) == "'" + value
