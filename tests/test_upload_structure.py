"""An uploaded .docx must keep the structure Word already gave us.

It did not. The upload parsed the document correctly and then threw the result away:
only flattened text was stored, and the run re-derived the split from punctuation. Two
bullets lost their markers, got glued onto the end of the preceding sentence, and three
separate requirements became one segment.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from sqlalchemy import select

from app.segmentation import BULLET, HEADING, SENTENCE, TABLE_ROW, render_text, segment_text

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _para(text, style=None, numbered=False):
    pr = ""
    if style:
        pr += f'<w:pStyle w:val="{style}"/>'
    if numbered:
        pr += '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
    pr = f"<w:pPr>{pr}</w:pPr>" if pr else ""
    return f"<w:p>{pr}<w:r><w:t xml:space='preserve'>{text}</w:t></w:r></w:p>"


def _cell(t):
    return f"<w:tc><w:tcPr/><w:p><w:r><w:t>{t}</w:t></w:r></w:p></w:tc>"


@pytest.fixture
def docx_bytes() -> bytes:
    body = (
        _para("Seade tarnitakse koos kasutusjuhendiga.")
        + _para("1. Üldine", style="Heading1")
        + _para("Valgusti peab kaaluma kuni 3 kg.")
        + _para("Kaitseastet tuleb tõendada katsearuandega.")
        + _para("laadimiskaabel", style="ListParagraph", numbered=True)
        + _para("varuaku", style="ListParagraph", numbered=True)
        + _para("Lisavarustusena võib optsioonina pakkuda statiivi.")
        + f"<w:tbl><w:tblPr/><w:tblGrid/><w:tr>{_cell('Parameeter')}{_cell('Nõue')}</w:tr></w:tbl>"
    )
    parts = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/_rels/document.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        "word/styles.xml":
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {W}>'
            '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>'
            '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/></w:style></w:styles>',
        "word/document.xml":
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W}><w:body>{body}</w:body></w:document>',
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_docx_parses_into_structured_segments(docx_bytes):
    from app.segmentation import segment_docx

    segments = segment_docx(docx_bytes)
    types = [s.segment_type for s in segments]
    assert types.count(HEADING) == 1
    assert types.count(BULLET) == 2
    assert types.count(TABLE_ROW) == 1
    assert [s.text for s in segments if s.segment_type == BULLET] == [
        "laadimiskaabel",
        "varuaku",
    ]


def test_bullets_are_not_swallowed_by_the_sentence_above(docx_bytes):
    """The exact failure seen on the deployment."""
    from app.segmentation import segment_docx

    segments = segment_docx(docx_bytes)
    glued = [s for s in segments if "katsearuandega" in s.text and "laadimiskaabel" in s.text]
    assert glued == [], f"bullet merged into the preceding sentence: {glued}"


def test_rendered_text_round_trips_back_to_the_same_structure(docx_bytes):
    """mmr_text is what a reader sees, so it must degrade gracefully too."""
    from app.segmentation import segment_docx

    original = segment_docx(docx_bytes)
    reparsed = segment_text(render_text(original))

    assert [s.segment_type for s in reparsed].count(BULLET) == 2
    assert [s.segment_type for s in reparsed].count(HEADING) == 1
    assert not any(
        "katsearuandega" in s.text and "laadimiskaabel" in s.text for s in reparsed
    )


def test_upload_stores_the_structured_split(client, docx_bytes, engine):
    from sqlalchemy.orm import Session

    from app.models import Conversion, Segment

    response = client.post(
        "/uus",
        data={"title": "Docx test", "mmr_id": "mmr_docx", "procurement_profile": "COTS"},
        files={
            "upload": (
                "mmr.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with Session(engine) as session:
        conversion = session.scalars(
            select(Conversion).order_by(Conversion.id.desc()).limit(1)
        ).first()
        rows = session.scalars(
            select(Segment).where(Segment.conversion_id == conversion.id)
        ).all()

    types = [s.segment_type for s in rows]
    assert types.count(BULLET) == 2, types
    assert types.count(HEADING) == 1, types
    assert types.count(TABLE_ROW) == 1, types


def test_pasted_text_also_gets_its_segments_stored(client, engine):
    from sqlalchemy.orm import Session

    from app.models import Conversion, Segment

    client.post(
        "/uus",
        data={
            "title": "Paste test",
            "mmr_id": "mmr_paste",
            "procurement_profile": "COTS",
            "mmr_text": "1. Üldine\n\nSeade peab olema kerge.\n- esimene punkt",
        },
        follow_redirects=True,
    )
    with Session(engine) as session:
        conversion = session.scalars(
            select(Conversion).order_by(Conversion.id.desc()).limit(1)
        ).first()
        types = [
            row.segment_type
            for row in session.scalars(
                select(Segment).where(Segment.conversion_id == conversion.id)
            )
        ]
    assert HEADING in types and BULLET in types and SENTENCE in types
