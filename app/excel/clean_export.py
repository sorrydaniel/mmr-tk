"""The clean TK export.

This fills a copy of the real blank RKIK template rather than building a workbook from
scratch, so the instruction preamble, the NORMATIIVID block, the START sheet, the print
settings and the dropdowns all survive. A lookalike workbook would have to be pasted into
the real template by hand, which defeats the point of the export.

Nothing the app invented appears in this file: no segment ids, no uncertainty colouring.
The yellow on columns I-J is kept because it belongs to the template -- it tells the bidder
which cells are theirs.

See docs/tk_template_reference.md for where every number here comes from.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "tk_template.xlsx"

SHEET_REQUIREMENTS = "Tehnilised nõuded"
SHEET_START = "START"

HEADER_ROW = 22
GROUP_ROW = 23
FIRST_DATA_ROW = 24
TEMPLATE_LAST_DATA_ROW = 55
TEMPLATE_DATA_ROWS = TEMPLATE_LAST_DATA_ROW - FIRST_DATA_ROW + 1  # 32

# A..H are written by the app, I..J belong to the bidder.
APP_COLUMNS = "ABCDEFGH"
BIDDER_COLUMNS = "IJ"
CLASSIFICATION_COLUMN = "C"

# Dropdown sources, exactly as the template defines them. openpyxl drops the x14
# extension validations on load, so they are rebuilt on save.
METHOD_SOURCE = f"{SHEET_START}!$A$18:$A$26"
STAGE_SOURCE = f"{SHEET_START}!$D$18:$D$26"
METHOD_COLUMN = "E"
STAGE_COLUMN = "F"

_FIXED_TIMESTAMP = datetime(2000, 1, 1, tzinfo=timezone.utc).replace(tzinfo=None)


@dataclass
class ExportRow:
    """One TK row, already in order, already resolved. Plain data by design: the exporter
    must not care whether it came from the model, the engineer or an imported manual TK."""

    category: str = ""
    description: str = ""
    classification: str = "M"
    verif_with_bid: str = ""
    verif_method: str = ""
    verif_stage: str = ""
    verif_description: str = ""
    comments: str = ""

    def values(self) -> list[str]:
        return [
            self.category or "",
            self.description or "",
            self.classification or "",
            self.verif_with_bid or "",
            self.verif_method or "",
            self.verif_stage or "",
            self.verif_description or "",
            self.comments or "",
        ]


def _copy_row_style(ws: Worksheet, source_row: int, target_row: int) -> None:
    for column in APP_COLUMNS + BIDDER_COLUMNS:
        source = ws[f"{column}{source_row}"]
        target = ws[f"{column}{target_row}"]
        target._style = source._style  # noqa: SLF001 - openpyxl's own copy idiom
    height = ws.row_dimensions[source_row].height
    if height:
        ws.row_dimensions[target_row].height = height


def _clear_inherited_fills(ws: Worksheet, row: int) -> None:
    """The template's column C fills are meaningful but belong to its old rows.

    Copying the template means inheriting them, so every written row is wiped first and
    then painted from the classification.
    """
    for column in APP_COLUMNS:
        ws[f"{column}{row}"].fill = PatternFill(fill_type=None)


def _apply_validations(ws: Worksheet, last_row: int) -> None:
    ws.data_validations.dataValidation = []
    for column, source in ((METHOD_COLUMN, METHOD_SOURCE), (STAGE_COLUMN, STAGE_SOURCE)):
        validation = DataValidation(
            type="list",
            formula1=source,
            allow_blank=True,
            showDropDown=False,
            showInputMessage=True,
            showErrorMessage=True,
        )
        ws.add_data_validation(validation)
        validation.add(f"{column}{FIRST_DATA_ROW}:{column}{max(last_row, FIRST_DATA_ROW)}")


def _strip_metadata(wb) -> None:
    """A blinded file must not say who made it or when."""
    props = wb.properties
    props.creator = None
    props.lastModifiedBy = None
    props.title = None
    props.subject = None
    props.description = None
    props.keywords = None
    props.category = None
    props.company = None
    props.manager = None
    props.identifier = None
    props.language = None
    props.revision = None
    props.contentStatus = None
    props.created = _FIXED_TIMESTAMP
    props.modified = _FIXED_TIMESTAMP
    try:
        wb.custom_doc_props.props = []
    except AttributeError:  # pragma: no cover - depends on openpyxl version
        pass


def build_workbook(
    rows: Iterable[ExportRow],
    *,
    class_fills: dict[str, str] | None = None,
    group_label: str | None = None,
    template_path: Path | None = None,
    strip_metadata: bool = True,
):
    """Return an openpyxl workbook: the real template with these rows written into it."""
    rows = list(rows)
    path = template_path or TEMPLATE_PATH
    wb = load_workbook(path)
    ws = wb[SHEET_REQUIREMENTS]

    needed = max(len(rows), 1)
    if needed > TEMPLATE_DATA_ROWS:
        extra = needed - TEMPLATE_DATA_ROWS
        ws.insert_rows(TEMPLATE_LAST_DATA_ROW + 1, extra)
        for offset in range(extra):
            _copy_row_style(ws, TEMPLATE_LAST_DATA_ROW, TEMPLATE_LAST_DATA_ROW + 1 + offset)
    elif needed < TEMPLATE_DATA_ROWS:
        # Leaving spare template rows behind would ship a TK with empty yellow bidder
        # cells hanging off the bottom.
        ws.delete_rows(FIRST_DATA_ROW + needed, TEMPLATE_DATA_ROWS - needed)

    last_row = FIRST_DATA_ROW + needed - 1

    if group_label is not None:
        ws[f"B{GROUP_ROW}"] = group_label

    fills = {k: (v or "").strip() for k, v in (class_fills or {}).items()}

    for index, row in enumerate(rows):
        target = FIRST_DATA_ROW + index
        _clear_inherited_fills(ws, target)
        for offset, value in enumerate(row.values()):
            ws.cell(row=target, column=offset + 1, value=value or None)
        colour = fills.get(row.classification or "", "")
        if colour:
            ws[f"{CLASSIFICATION_COLUMN}{target}"].fill = PatternFill(
                fill_type="solid", start_color=colour, end_color=colour
            )

    if not rows:
        _clear_inherited_fills(ws, FIRST_DATA_ROW)

    _apply_validations(ws, last_row)
    if strip_metadata:
        _strip_metadata(wb)
    return wb


FIXED_CORE_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    b'<cp:coreProperties '
    b'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
    b'xmlns:dcterms="http://purl.org/dc/terms/" '
    b'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    b'<dcterms:created xsi:type="dcterms:W3CDTF">2000-01-01T00:00:00Z</dcterms:created>'
    b'<dcterms:modified xsi:type="dcterms:W3CDTF">2000-01-01T00:00:00Z</dcterms:modified>'
    b"</cp:coreProperties>"
)


def _normalise_archive(payload: bytes) -> bytes:
    """Make the file byte-stable.

    openpyxl rewrites `modified` to the save time, and the zip container stores a
    timestamp per entry. Both reveal when a file was produced, which is noise in a
    blinded packet, so they are pinned to a fixed date.
    """
    source = zipfile.ZipFile(io.BytesIO(payload))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            data = FIXED_CORE_XML if name == "docProps/core.xml" else source.read(name)
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            target.writestr(info, data)
    source.close()
    return out.getvalue()


def to_bytes(
    rows: Iterable[ExportRow],
    *,
    class_fills: dict[str, str] | None = None,
    group_label: str | None = None,
    template_path: Path | None = None,
    strip_metadata: bool = True,
) -> bytes:
    wb = build_workbook(
        rows,
        class_fills=class_fills,
        group_label=group_label,
        template_path=template_path,
        strip_metadata=strip_metadata,
    )
    buffer = io.BytesIO()
    wb.save(buffer)
    payload = buffer.getvalue()
    return _normalise_archive(payload) if strip_metadata else payload


def rows_from_requirements(requirements: Iterable) -> list[ExportRow]:
    """Map stored requirements onto the export shape.

    Column H carries the requirement's own comment and nothing else: it is a bidder-facing
    column, so segment ids would change what the delivered document says. They go in the
    research copy instead.
    """
    out = []
    for requirement in requirements:
        if getattr(requirement, "deleted", False):
            continue
        out.append(
            ExportRow(
                category=requirement.category,
                description=requirement.description,
                classification=requirement.classification,
                verif_with_bid=requirement.verif_with_bid,
                verif_method=requirement.verif_method,
                verif_stage=requirement.verif_stage,
                verif_description=requirement.verif_description,
                comments=requirement.comments,
            )
        )
    return out


def column_letters() -> list[str]:
    return [get_column_letter(i) for i in range(1, 11)]
