"""The clean TK export.

These tests pin the things that silently break: the header row is 22 and not 1, openpyxl
drops the template's x14 dropdowns on load so they must be rebuilt, and copying the
template means inheriting its column C fills unless every written row is cleared first.
"""

from __future__ import annotations

import io

from openpyxl import load_workbook

from app.excel import clean_export
from app.excel.clean_export import (
    FIRST_DATA_ROW,
    GROUP_ROW,
    HEADER_ROW,
    SHEET_REQUIREMENTS,
    SHEET_START,
    TEMPLATE_DATA_ROWS,
    ExportRow,
)

EXPECTED_HEADERS = {
    "A": "Nõude kategooria",
    "B": "Kirjeldus (miinimumnõuded)",
    "C": "Nõuete klassifikatsioon M/N/I/OP",
    "D": "Verifitseerimine koos pakkumuse esitamisega (Jah/ei + kirjeldus)",
    "E": "Verifitseerimis-meetod",
    "F": "Verifitseerimis-etapp ja valimi suurus",
    "G": "Verifitseerimise kirjeldus",
    "H": "Kommentaarid",
    "I": "Vastavuse klassifikatsioon (FC/NC) ja arenduse hetkeseisu hinnang (EX/MD/DV)",
    "J": "Pakkuja märkused ja dokumendi/lisa nimi/number ning peatüki nimi/number",
}

FILLS = {"M": "FF00B0F0", "I": "FFFFE699", "N": "", "OP": ""}


def rows(count: int = 3) -> list[ExportRow]:
    return [
        ExportRow(
            category="1. Üldine",
            description=f"Nõue {i}.",
            classification="I" if i == 0 else "M",
            verif_with_bid="jah, sertifikaat",
            verif_method="Test",
            verif_stage="SAT kõik",
            comments="",
        )
        for i in range(count)
    ]


def _load(payload: bytes):
    return load_workbook(io.BytesIO(payload))


def test_sheet_order_matches_the_template():
    wb = _load(clean_export.to_bytes(rows()))
    assert wb.sheetnames[0] == SHEET_START
    assert SHEET_REQUIREMENTS in wb.sheetnames


def test_header_strings_are_exact_and_on_row_22():
    ws = _load(clean_export.to_bytes(rows()))[SHEET_REQUIREMENTS]
    for column, expected in EXPECTED_HEADERS.items():
        assert ws[f"{column}{HEADER_ROW}"].value == expected


def test_data_starts_on_row_24():
    ws = _load(clean_export.to_bytes(rows()))[SHEET_REQUIREMENTS]
    assert ws[f"B{FIRST_DATA_ROW}"].value == "Nõue 0."
    assert ws[f"B{FIRST_DATA_ROW + 1}"].value == "Nõue 1."


def test_group_row_holds_only_a_label_in_column_b():
    ws = _load(clean_export.to_bytes(rows(), group_label="1. Üldine"))[SHEET_REQUIREMENTS]
    assert ws[f"B{GROUP_ROW}"].value == "1. Üldine"
    assert ws[f"A{GROUP_ROW}"].value is None
    assert ws[f"C{GROUP_ROW}"].value is None


def test_classification_fill_is_applied_to_column_c_only():
    ws = _load(clean_export.to_bytes(rows(), class_fills=FILLS))[SHEET_REQUIREMENTS]
    informative = ws[f"C{FIRST_DATA_ROW}"]
    mandatory = ws[f"C{FIRST_DATA_ROW + 1}"]
    assert informative.fill.start_color.rgb == "FFFFE699"
    assert mandatory.fill.start_color.rgb == "FF00B0F0"
    # Nothing else in the row gets painted.
    assert ws[f"B{FIRST_DATA_ROW}"].fill.fill_type in (None, "none")


def test_empty_fill_setting_paints_nothing():
    data = rows(2)
    data[1].classification = "N"  # N has no colour until a real filled TK is opened
    ws = _load(clean_export.to_bytes(data, class_fills=FILLS))[SHEET_REQUIREMENTS]
    assert ws[f"C{FIRST_DATA_ROW + 1}"].fill.fill_type in (None, "none")


def test_inherited_template_fills_are_cleared():
    """Row 25 in the template carries a blue fill. A written N row must not inherit it."""
    data = rows(3)
    for row in data:
        row.classification = "N"
    ws = _load(clean_export.to_bytes(data, class_fills=FILLS))[SHEET_REQUIREMENTS]
    for offset in range(3):
        assert ws[f"C{FIRST_DATA_ROW + offset}"].fill.fill_type in (None, "none")


def test_bidder_columns_stay_yellow_and_empty():
    ws = _load(clean_export.to_bytes(rows(), class_fills=FILLS))[SHEET_REQUIREMENTS]
    for column in ("I", "J"):
        cell = ws[f"{column}{FIRST_DATA_ROW}"]
        assert cell.value is None
        assert cell.fill.start_color.rgb == "FFFFFF00"


def test_dropdowns_survive_the_round_trip():
    payload = clean_export.to_bytes(rows(4))
    ws = _load(payload)[SHEET_REQUIREMENTS]
    sources = {dv.formula1 for dv in ws.data_validations.dataValidation}
    assert f"{SHEET_START}!$A$18:$A$26" in sources
    assert f"{SHEET_START}!$D$18:$D$26" in sources


def test_dropdown_ranges_cover_every_written_row():
    payload = clean_export.to_bytes(rows(40))
    ws = _load(payload)[SHEET_REQUIREMENTS]
    ranges = " ".join(str(dv.sqref) for dv in ws.data_validations.dataValidation)
    assert f"E{FIRST_DATA_ROW}:E{FIRST_DATA_ROW + 39}" in ranges
    assert f"F{FIRST_DATA_ROW}:F{FIRST_DATA_ROW + 39}" in ranges


def test_more_rows_than_the_template_holds_are_inserted():
    count = TEMPLATE_DATA_ROWS + 25
    ws = _load(clean_export.to_bytes(rows(count)))[SHEET_REQUIREMENTS]
    assert ws[f"B{FIRST_DATA_ROW + count - 1}"].value == f"Nõue {count - 1}."


def test_surplus_template_rows_are_removed():
    ws = _load(clean_export.to_bytes(rows(3)))[SHEET_REQUIREMENTS]
    # Nothing yellow hanging below the last written row.
    assert ws[f"I{FIRST_DATA_ROW + 3}"].fill.fill_type in (None, "none")


def test_segment_ids_never_reach_the_clean_file():
    data = rows(2)
    data[0].comments = ""
    ws = _load(clean_export.to_bytes(data))[SHEET_REQUIREMENTS]
    assert ws[f"H{FIRST_DATA_ROW}"].value is None


def test_comments_are_kept_when_they_are_real():
    data = rows(1)
    data[0].comments = "Tootja kinnitus piisab."
    ws = _load(clean_export.to_bytes(data))[SHEET_REQUIREMENTS]
    assert ws[f"H{FIRST_DATA_ROW}"].value == "Tootja kinnitus piisab."


def test_workbook_metadata_is_stripped():
    """Checked in the raw XML: openpyxl invents a creator of "openpyxl" on *load*,
    so reading it back through the object model would hide a leak rather than catch it."""
    import zipfile

    payload = clean_export.to_bytes(rows())
    core = zipfile.ZipFile(io.BytesIO(payload)).read("docProps/core.xml").decode()
    assert "dc:creator" not in core
    assert "lastModifiedBy" not in core
    assert "dc:title" not in core
    assert "2000-01-01T00:00:00Z" in core


def test_export_is_byte_stable():
    """A blinded packet must not carry the moment each file was produced."""
    first = clean_export.to_bytes(rows())
    second = clean_export.to_bytes(rows())
    assert first == second


def test_start_sheet_definitions_survive():
    ws = _load(clean_export.to_bytes(rows()))[SHEET_START]
    assert ws["A12"].value == "M"
    assert ws["D3"].value == "FC"
    assert ws["A18"].value == "Funktsionaalne kontroll"
    assert ws["D23"].value == "FAT kõik"


def test_instruction_preamble_survives():
    ws = _load(clean_export.to_bytes(rows()))[SHEET_REQUIREMENTS]
    assert ws["A2"].value == "ÜLDISED DOKUMENDI TÄITMISE JUHISED"
    assert ws["A12"].value.startswith("NORMATIIVID")


def test_rows_from_requirements_skips_soft_deleted():
    class Fake:
        def __init__(self, deleted):
            self.deleted = deleted
            self.category = "x"
            self.description = "y"
            self.classification = "M"
            self.verif_with_bid = ""
            self.verif_method = "Test"
            self.verif_stage = "SAT kõik"
            self.verif_description = ""
            self.comments = ""

    out = clean_export.rows_from_requirements([Fake(False), Fake(True), Fake(False)])
    assert len(out) == 2
