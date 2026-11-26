# RKIK TK template — reference

Extracted from the blank official template `TK_mall_RKIK_tuhi.xlsx`
(source: `C:/projects/tk-draft-assistant/inputs/`). The template file itself is blank —
no requirement content, nothing protected. This document is the single source of truth for
the `.xlsx` export and for the worked examples in `prompts/system_prompt.md`.

## 1. Workbook structure

| | |
|---|---|
| Sheet 1 | `START` |
| Sheet 2 | `Tehnilised nõuded` |

**START comes first.** The requirements sheet is the *second* sheet.

### Sheet `Tehnilised nõuded` layout

The header row is **row 22**, not row 1. Rows 1-21 are a preamble that is part of the
official document:

| Rows | Content |
|---|---|
| 2 | `ÜLDISED DOKUMENDI TÄITMISE JUHISED` (section title) |
| 4-10 | Seven numbered instructions to the bidder, `No. 1` .. `No. 7`, label in A, text merged across B:G |
| 12 | `NORMATIIVID` (section title) |
| 14 | Normatiivid table header: A `Normatiivi kõrgeim salastatuse tase`, B `Normatiivi number`, C `Normatiivi pealkiri (ENG)` (merged C:G) |
| 15-20 | Empty normatiivid rows |
| 22 | Requirements header row (height 45, bold, wrapped) |
| 23 | Group/section row — only column B is filled, here `Konfiguratsiooni kogus` |
| 24-55 | 32 blank requirement rows |

### Preamble instruction texts (rows 4-10)

- **No. 1** — Pakkuja täidab kollaselt tähistatud väljad
- **No. 2** — Tulpa I peab pakkuja kirjutama nõudele vastavuse hinnangu (FC/NC)
- **No. 3** — Tulpa I peab pakkuja kirjutama nõuet täitva omaduse arenduse hetkeseisu hinnangu (EX/MD/DV)
- **No. 4** — Tulpa J peab pakkuja kirjutama märkused või dokumendi/lisa nime/numbri ning peatüki nime/numbri selles dokumendis, kus nõude täidetus on tõendatud/kirjeldatud. Lahtris ei tohi olla muud peale viite dokumendile, st lahter ei ole vastavuse tõendusmaterjali esitamiseks
- **No. 5** — Pakkuja ei tohi muuta dokumendi ülesehitust ega sõnastust (välja arvatud kollastes lahtrites) ja tagastama täidetud faili xlsx-formaadis
- **No. 6** — Pakkuja peab esitama kõik tulbas D mainitud dokumendid (Verifitseerimine koos pakkumuse esitamisega) osana esialgsest pakkumusest
- **No. 7** — Pikkuse, laiuse ja kõrguse mõõtmete osas on pakkujal lubatud tooteid pakkuda, kui erinevus jääb +/-1% piiresse.

## 2. Requirement columns (header row 22) — exact strings

| Col | Header text | Width | Filled by |
|---|---|---|---|
| A | `Nõude kategooria` | 22.3 | app |
| B | `Kirjeldus (miinimumnõuded)` | 68.3 | app |
| C | `Nõuete klassifikatsioon M/N/I/OP` | 32.7 | app |
| D | `Verifitseerimine koos pakkumuse esitamisega (Jah/ei + kirjeldus)` | 24.0 | app |
| E | `Verifitseerimis-meetod` | 25.3 | app |
| F | `Verifitseerimis-etapp ja valimi suurus` | 20.7 | app |
| G | `Verifitseerimise kirjeldus` | 28.1 | app |
| H | `Kommentaarid` | 16.9 | app |
| I | `Vastavuse klassifikatsioon (FC/NC) ja arenduse hetkeseisu hinnang (EX/MD/DV)` | 38.0 | bidder (yellow) |
| J | `Pakkuja märkused ja dokumendi/lisa nimi/number ning peatüki nimi/number` | 32.7 | bidder (yellow) |

Columns K and L exist in the used range (`A1:L55`) but are empty and unstyled.

## 3. Colours actually used in the template

| ARGB | Where | Meaning in the official document |
|---|---|---|
| `FFFFFF00` | `I24:J55` | bidder-fill columns |
| `FFC6EFCE` | START A29 legend | `Lahter on lisatud võrreldes dokumendi eelmise versiooniga` |
| `FFFFEB9C` | START A30 legend | `Lahtri sisu on muudetud võrreldes dokumendi eelmise versiooniga` |
| `FFFFC7CE` | START A31 legend | `Lahtri sisu on muudetud kehtetuks võrreldes dokumendi eelmise versiooniga` |
| `FF00B0F0` | column C, 26 of 32 rows | **classification fill: M (mandatory)** |
| `FFFFE699` | column C, row 24 | **classification fill: I (informative)** — row 24 is the opening I row |

> **Column C is semantic, not residue.** RKIK colour-codes the classification column:
> M = dark blue, N = light blue, I = orange, OP = no fill. The blank template contains only
> two of the four (`FF00B0F0` for M, `FFFFE699` for I) because the TK it was emptied from had
> no N rows; the bare cells at `C36-C37` and `C45-C47` are OP. The remaining two hex values
> are editable Settings (`class_fill_N`, `class_fill_OP`), to be set from a real filled TK.
> Because an export *copies* this template, it must clear inherited fills on every written
> row before applying the classification fill, or rows inherit whatever the template had.

> **Colour conflict to respect.** The yellow/orange/red family is already spoken for by the
> official change legend on START (added / changed / invalidated), and pure yellow
> `FFFFFF00` means "bidder fills this", and orange now means `I`. The app's `uncertain`
> highlight is therefore light purple `FFE4DFEC`, which appears nowhere in the template —
> and it is never applied in the clean TK at all.

## 4. Data validation (dropdowns)

The template's dropdowns live in an `x14` extension list (openpyxl drops them on load —
relevant if the export is built by copying the template).

| Range | Source |
|---|---|
| `E24:E55` (Verifitseerimis-meetod) | `START!$A$18:$A$26` |
| `F24:F55` (Verifitseerimis-etapp) | `START!$D$18:$D$26` |

There is **no** dropdown on column C (M/N/I/OP) in the template.
The validation source ranges are 9 cells tall but only the first rows are populated,
so the live option lists are:

- **Verifitseerimismeetodid (6):** `Funktsionaalne kontroll`, `Funktsionaalne demonstratsioon`, `Test`, `Analüüs`, `Sertifikaat`, `N/A`
- **Verifitseerimisetapid (9):** `Lepingu sõlmimine`, `Lepingu täitmine`, `Disainietapid`, `FAFAT`, `FAFAT + suvaline FAT`, `FAT kõik`, `SAT kõik`, `Viimane tarne`, `N/A`

## 5. START sheet content (verbatim)

### Mõisted ja lühendid (`A3`)

| Nimetus | Kirjeldus |
|---|---|
| `STTE` | Special tools and test equipment - Eritööriistad ning testseadmed |
| `MOTS` | Military off-the-shelf - Sõjaline valmistoode |
| `COTS` | Commercial off-the-shelf - Tsiviilkäibes olev valmistoode |
| `CA` | Contracting Authority - Hankija |

### Nõuete klassifikatsioon (`A12`)

| Klassifikatsiooni tähis | Kirjeldus |
|---|---|
| `M` | Mandatory - Kohustuslik nõue - Pakkuja peab täitma kõik kohustuslikud nõuded. Juhul, kui mõni kohustuslik nõue on täitmata, eemaldatakse Pakkuja pakkumus hankeprotsessist. Juhul, kui Pakkuja ei vasta kohustuslikule nõudele, peab see olema selgelt näidatud (NC). |
| `N` | Negotiable requirement - läbiräägitav nõue - pakkuja peaks täitma kõik läbiräägitavad nõuded. Antud nõuded võivad jääda läbiräägitavaks hankija ja pakkuja vahel, kui on vajalik hangitava toote hinda alandada või tarnekiirust suurendada. Kui nõue ei ole peale läbirääkimisi täidetud, kõrvaldatakse pakkumine protsessist. Kui vastaja nõuet ei täida, tuleb sellest RKIK-le selgelt teada anda. |
| `OP` | Requirement for option - Valikuvõimalusega nõue – pakkuja peaks pakkuma välja lahenduse nõud täitmiseks ja märkima vastava hinnatõusu eelarvet kirjeldavas lisas. Valikuvõimaluse kasutamise otsustab RKIK pakkumismenetluse käigus. |
| `I` | Informative requirement - Informatiivne nõue – lisateave esitatakse nõude vormis. Selle eesmärk on täpsustada hankija kavatsust ning sellise nõude puhul ei tehta vastavushindamist ega kontrolli. |

### Vastavuse klassifikatsioon (`D3`)

| Klassifikatsiooni tähis | Kirjeldus |
|---|---|
| `FC` | Fully compliant - Täielikult vastav - pakutav toode vastab täielikult nõudele ja vastav tõendusmaterjal on esitatud koos pakkumusega |
| `NC` | Not compliant - Mittevastav - pakutav toode ei vasta nõudele |
| `PC` | Partially compliant - osaliselt vastav - pakutav toode vastab osaliselt nõuetele, osaliselt mitte - vajalik kirjeldada lahti, millisel määral on nõue täidetud. |

### Arenduse hetkeseisu klassifikatsioon (`D12`)

| Klassifikatsiooni tähis | Kirjeldus |
|---|---|
| `EX` | Existing feature - Olemasolev omadus - omadus on välja arendatud ja kasutusel pakutaval baastootel |
| `MD` | Modification required - Vajalik on kohandamine - pakutav lahendus on olemas kas funktsionaalse prototüübina või on sarnane lahendus saadaval ning seda saab näidata, kuid see vajab väiksemahulist kohandamist |
| `DV` | Development required - Vajalik on arendus - pakutavat lahendust ei ole baastootel ning see vajab väljaarendamist |

### Verifitseerimismeetodid (`A18`)

| Verifitseerimismeetodid | Verifitseerimismeetodi kirjeldus |
|---|---|
| `Funktsionaalne kontroll` | Nõude täitmist kontrollib lõppkasutaja testitavat süsteemi käitamata, kaasa arvatud visuaalselt. Kohese subjektiivse „OK“ otsuse korral täiendavaid andmeid ei salvestata. Kahtluse korral mõõdetakse vastav mõõde ja „OK“/„NOK“ otsus tehakse mõõtmistulemuse põhjal. |
| `Funktsionaalne demonstratsioon` | Nõude täitmist kontrollib lõppkasutaja, käitades testitavat süsteemi kasutus-, hooldus- ja muudes käsiraamatutes kirjeldatud viisil. Kohese subjektiivse „OK“ otsuse korral täiendavaid andmeid ei salvestata. Kahtluse korral viiakse läbi täiendavad mõõtmised ja „OK“/„NOK“ otsus tehakse mõõtmistulemuse põhjal. |
| `Test` | Testitavat süsteemi käitatakse vastavalt kasutus-, hooldus- ja muudele juhenditele. Testi ajal registreeritakse testitav parameeter ja mõõtmistulemuste võrdluse põhjal etteantud lävendiga tehakse otsus „OK/NOK”. |
| `Analüüs` | Pakkuja esitab vastava analüüsi nõude täitmise tõendamiseks. |
| `Sertifikaat` | Pakkuja esitab vastava andmelehe või sertifikaadi nõude täitmise tõendamiseks. |
| `N/A` | Nõude täitmist täiendavalt ei kontrollita, vajalik pakkuja poolne kinnitus |

### Verifitseerimisetapp ja valimi suurus (`D18`)

| Verifitseerimisetapp ja valimi suurus | Verifitseerimisetapi ja valimi suuruse kirjeldus |
|---|---|
| `Lepingu sõlmimine` | Nõue kontrollitakse lepingu allkirjastamisel |
| `Lepingu täitmine` | Nõue kontrollitakse lepingu täitmise perioodil enne lõplikku tarnet. |
| `Disainietapid` | Nõude täitmise kontrollimine põhineb projekteerimisdokumentidel, füüsiliste seadmete kontrollimist ega katsetamist ei teostata. |
| `FAFAT` | Nõude täitmist kontrollitakse prototüübi või esimese seeriatootmisest tulnud masina vastuvõtmise kontrolli raames |
| `FAFAT + suvaline FAT` | Nõude täitmist kontrollitakse prototüübi või esimese seeriatootmisest tulnud masina vastuvõtmise kontrolli raames, lisaks võetakse tehase vastuvõtukatse ajal seeriatootmises olevatest artiklitest juhuslikke proove kontrollimiseks. |
| `FAT kõik` | Nõude täitmist kontrollitakse Factory Acceptance Test raames - tootja tehases vastuvõtmise kontrolli käigus |
| `SAT kõik` | Nõude täitmist kontrollitakse Site Acceptance Test raames - kohapealse vastuvõtmise kontrolli käigus |
| `Viimane tarne` | Nõude täitmist kontrollitakse viimaste toodete üleandmisel. |
| `N/A` | Nõude täitmist täiendavalt ei kontrollita, vajalik pakkuja poolne kinnitus |

### Tehniliste tingimuste muudatuste legend

- `FFC6EFCE` — Lahter on lisatud võrreldes dokumendi eelmise versiooniga
- `FFFFEB9C` — Lahtri sisu on muudetud võrreldes dokumendi eelmise versiooniga
- `FFFFC7CE` — Lahtri sisu on muudetud kehtetuks võrreldes dokumendi eelmise versiooniga
## 6. What this means for the export

1. Header row is **22**, data starts at **row 24**; row 23 is a group row with only column B.
2. The template ships 32 data rows (24-55). A TK of ~80 rows needs rows inserted, and the
   `E`/`F` validation ranges extended to match.
3. START must be sheet 1 and must carry all six definition blocks above plus the change legend.
4. Exact header strings for D, I and J are longer than commonly abbreviated — use the strings
   in section 2 verbatim.
5. Column `H Kommentaarid` is a bidder-facing content column, so writing app metadata
   (source segment IDs) into it changes the meaning of the delivered document. Segment IDs
   go in the research copy only — see [SPEC.md](SPEC.md) §16.
6. Clear inherited fills on every written row, then apply the column C classification fill.
7. openpyxl drops the `x14` dropdowns on load; re-add them on save and extend their ranges
   when the TK exceeds 32 rows.

## 7. Worked examples for prompts/system_prompt.md

Use the column semantics above; keep examples to 2-3 rows, fictional content only.

