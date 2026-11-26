"""Startup seeding.

The sample MMR is **invented**, not sanitised. It lives in the repository, so it must
contain nothing real -- and it is built to exercise the hard cases, which makes it a test
fixture as well as a demo:

  * two headings, and one requirement that sits above the first heading
  * one compound sentence hiding three requirements
  * one vague sentence ("piisavalt vastupidav")
  * a bullet list and a table row
  * one explicit verification instruction (exercises MMR_EXPLICIT)
  * three context sentences, which must produce no rows at all
  * one informative intent sentence, one N signal, one OP signal
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import settings_store
from app.models import Conversion

SAMPLE_MMR_ID = "mmr_naidis_01"
SAMPLE_TITLE = "Näidis: satelliitterminali transpordikohver"

SAMPLE_MMR_TEXT = """Kohver tarnitakse komplektis eestikeelse kasutusjuhendiga.

1. Üldine

Käesoleva dokumendi eesmärk on kirjeldada satelliitterminali välitingimustes \
transportimiseks vajaliku kohvri miinimumnõudeid.
Üksus kasutab satelliitterminali välilaagrites ja liikuvatel positsioonidel. \
Terminali teisaldavad tavaliselt kaks inimest maastikul. Praegu kasutusel olevad \
kohvrid on amortiseerunud ning neid ei ole enam võimalik parandada.

Kohver peab olema valmistatud löögikindlast polümeerist, kaaluma tühjana kuni 12 kg \
ja mahutama terminali koos kaablikomplektiga.
Kohver peaks võimalusel olema piisavalt vastupidav välitingimustes.

2. Kaitse ja keskkond

Kohver peab taluma temperatuurivahemikku -30 °C kuni +50 °C.
Kohvri kaitseaste peab olema vähemalt IP65.
Löögitaluvust tuleb tõendada katsearuandega.

Kohver peab sisaldama järgmisi elemente:
- eemaldatav vahtplastist sisu terminali jaoks
- eraldi lahter kaablikomplekti jaoks
- rõhutasakaalustusklapp

Lisavarustusena võib optsioonina pakkuda ratastega transpordialust.

Mõõt | Nõue | Ühik
Välismõõt | kuni 900 x 600 x 400 | mm

Kohvri välispinnale tuleb kanda üksuse tähistus vastavalt hankija juhendile.
"""


def seed_sample_conversion(session: Session) -> Conversion | None:
    """Only when the database has no conversions at all."""
    count = session.scalar(select(func.count()).select_from(Conversion)) or 0
    if count:
        return None
    conversion = Conversion(
        title=SAMPLE_TITLE,
        mmr_id=SAMPLE_MMR_ID,
        mmr_text=SAMPLE_MMR_TEXT.strip(),
        status="draft",
        procurement_profile="COTS",
    )
    session.add(conversion)
    session.flush()
    return conversion


def seed_all(session: Session) -> dict[str, int | bool]:
    added = settings_store.seed_defaults(session)
    conversion = seed_sample_conversion(session)
    session.commit()
    return {"settings_added": added, "sample_created": conversion is not None}
