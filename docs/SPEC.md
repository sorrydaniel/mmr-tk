# MMR → TK Converter — agreed specification

Single source of truth for the build. Every decision below was settled explicitly.
Companion documents: [tk_template_reference.md](tk_template_reference.md) (the real RKIK
template, extracted) and [BACKLOG.md](BACKLOG.md) (phases and deferred work).

---

## 1. What this is

A web app that turns a prose **MMR** (Military Minimum Requirements, written by the Defence
Forces) into a draft **TK** (technical specification — one testable requirement per row),
lets a product engineer correct it, and records everything needed to measure how well the
LLM did.

It is a **research instrument first**, a course deliverable second, and not a production
procurement tool.

### Study context (drives most design decisions)

- **Part 1** — a counterbalanced paired design run by the author alone. For each MMR, a TK is
  produced twice: **arm A** by hand in Excel, **arm B** by the app. Half the MMRs are done
  A-first, half B-first, with **at least 7 days** between the two arms on the same MMR.
- The accuracy reference is a **separate answer key**, written while sanitising the MMR,
  **before either arm**. Not arm A.
- Scoring happens **outside the app**, on **blinded** clean exports, against that key.
- **Part 2** — three product engineers (anonymous codes R1/R2/R3) review a draft and flag rows
  that are wrong or need changing. They do not use the answer key; their flags are the data.
- Set size: ~10 MMRs; realistically 5–8 simpler ones at 2–3 pages / 20–40 TK rows, largest
  ~10 pages. Design limit: ~150 segments / ~80 rows.

### Non-goals

- Not usable on real classified MMRs. See §3.
- No per-user accounts, no roles, no multi-tenancy.
- No automatic scoring against the answer key inside the app.
- No TK versioning beyond the raw-vs-final snapshot.

---

## 2. Scope and phases

| Phase | Contents | Why this order |
|---|---|---|
| **1** | Login, segmentation, conversion (background, mock + LLM), raw snapshot, Paranda mode with edit diff, classification rules, I block, categories, verification mapping, clean TK export with classification colours, run log + CSV, Settings, tests, DB error page, `/health` | Must deploy and work; it is the course deliverable |
| **2** | Research export, blinded packet + key CSV, manual TK import, answer-key artefact, order flags | Part 1 research tooling |
| **3** | Hinda mode, `RequirementFlag`, `MissingNote`, per-reviewer timers, missing-aspects panel | Part 2 cannot start until Part 1 drafts exist |

**All tables for phases 1–3 are created, empty, in the initial Alembic migration**, so later
phases are code-only and never migrate against a database holding real study data.

Phase 1 must be committed, pushed and **confirmed working on Railway** before Phase 2 starts.

---

## 3. Data policy

- Real MMRs are under classified protection. This app only ever sees **invented** or
  **sanitised** documents.
- **Nothing MMR/TK-shaped is ever committed to git.** Sanitised is not permission to commit.
  Study documents exist only as runtime uploads in the Railway database.
- Only **invented** fixtures live in the repo.
- `inputs/`, `uploads/`, `*.docx`, `*.pdf` are gitignored.
- One deliberate exception: the **blank** official template `TK_mall_RKIK_tuhi.xlsx`, which
  contains no requirement content, is committed as the export base.

---

## 4. Stack and deployment

- Python 3.12, FastAPI, Uvicorn
- Jinja2 server-rendered templates, HTMX for partial updates, Tailwind via CDN (no Node build)
- SQLAlchemy 2 + Alembic, PostgreSQL
- `anthropic` SDK, `pydantic` validation, `openpyxl`, `python-docx`, `pypdf`
- `pytest`; tests never touch a real database or a real API key (SQLite in-memory + mock converter)
- Railway, auto-deploy from `main`. `railway.json` start command:
  `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- `DATABASE_URL` arrives as `postgresql://`; rewrite to `postgresql+psycopg://`, use `psycopg[binary]`
- Nothing runs on the developer's machine; there is no local database

### Environment variables

| Name | Required | Behaviour |
|---|---|---|
| `DATABASE_URL` | yes | Rewritten to the psycopg driver at startup |
| `ANTHROPIC_API_KEY` | no | Absent → **mock converter** + yellow banner "Mock mode – no API key" |
| `ANTHROPIC_MODEL` | no | Default `claude-sonnet-5-5` |
| `APP_PASSWORD` | no | Set → whole app behind one shared password, session cookie |

---

## 5. Domain model

Created in full in the initial migration. Phase in brackets.

**Conversion** [1] — `id, title, mmr_id, mmr_text, status(draft|converted|failed|reviewed), procurement_profile(COTS|MOTS|ARENDUS), assigned_order(A_FIRST|B_FIRST|null), arm_a_imported_at, first_llm_run_at, order_gap_days, order_violation, created_at, updated_at`

**Segment** [1] — `id, conversion_id, sid (S1, S2 …), text, segment_type(HEADING|BULLET|TABLE_ROW|SENTENCE), list_level, order`

**Requirement** [1] — `id, conversion_id, order, category, category_source(MMR_HEADING|DEFAULT_LIST|NEW), description, classification(M|N|I|OP), classification_signal, requirement_type, verif_with_bid, verif_method, verif_stage, verif_source(MAPPING|MMR_EXPLICIT), verif_quote, verif_description, comments, source_segments (JSON list of sid), uncertain, uncertain_reason, edited_by_user, added_by_hand, deleted (soft), deleted_at`

**RequirementSnapshot** [1] — immutable raw LLM output per requirement, written once at
creation, never updated. Same payload fields as `Requirement`.

**Run** [1] — `id, conversion_id, mmr_id, created_at, model, input_tokens, output_tokens, processing_seconds (model time only), queue_seconds, rows_generated, schema_valid, uncertain_rows, retry_used, mock, status(queued|splitting|calling|validating|done|failed), error`

**Setting** [1] — `key, value`

**Review** [3] — `id, conversion_id, reviewer_code, mode(PARANDA|HINDA), started_at, ended_at, minutes`

**RequirementFlag** [3] — `id, requirement_id, reviewer_code, flag(null|VALE|VAJAB_MUUTMIST), note, created_at`

**MissingNote** [3] — `id, conversion_id, reviewer_code, text, created_at`

**ManualImport** [2] — `id, conversion_id, filename, imported_at, rows_parsed, warnings`

**AnswerKey** [2] — `id, conversion_id, filename, uploaded_at, locked, rows_parsed`

### Seeding on empty database

Default system prompt, default category list, verification mapping table, classification
fill colours, and **one invented sample MMR** (see §13).

---

## 6. Segmentation

Runs before the LLM. Segments, not sentences — the document contains headings, bullets and
tables, and a naive period split destroys traceability.

- Every segment gets an id `S1, S2, …` and a `segment_type`: `HEADING`, `BULLET`, `TABLE_ROW`, `SENTENCE`.
- **`.docx`** — use the document structure directly: Word heading styles → `HEADING`, list
  paragraphs → `BULLET` (python-docx does not expose auto-numbering text; store `list_level`
  instead), table rows → one `TABLE_ROW` per row with cells joined by `" | "`.
- **`.pdf` / `.txt` / pasted text** — split on line structure first, then sentence-split
  paragraph text only.
- Sentence splitter: period-based, with an Estonian abbreviation exception list —
  `nt, jne, jt, sh, s.h, k.a, min, max, vt, u, ca, lk, nr, tk, mm, cm, kg, jm, st, s.o, vms, vmt`.
  Never split inside numbers (`1,5 m`, `1.5`, `± 2 °C`) and never after `digit+period` at line start.
- `HEADING` segments get ids but are **never TK rows**; they are category hints.
- Numbered MMR shown in a collapsible panel.
- Over the design limit (~150 segments) → explicit warning, never silent truncation.

---

## 7. LLM contract

System prompt in `prompts/system_prompt.md`, editable in Settings, restorable to default.
The model receives the system prompt and the numbered MMR, and returns **JSON only**: a list
of row objects.

| Field | Type |
|---|---|
| `category` | text |
| `category_source` | `MMR_HEADING` / `DEFAULT_LIST` / `NEW` |
| `description` | one testable minimum requirement, Estonian TK wording |
| `classification` | `M` / `N` / `I` / `OP` |
| `classification_signal` | the triggering word, or null |
| `requirement_type` | see §10 |
| `verif_method` | enum, §10 — only when `verif_source = MMR_EXPLICIT` |
| `verif_stage` | enum, §10 — only when `verif_source = MMR_EXPLICIT` |
| `verif_source` | `MAPPING` / `MMR_EXPLICIT` |
| `verif_quote` | the MMR text that stated the verification, or null |
| `verif_description` | text, may be empty |
| `comments` | text, may be empty |
| `source_segments` | list of segment ids; **each must exist** |
| `uncertain` | bool |
| `uncertain_reason` | text or null |

Validated with pydantic. On failure, **retry once** with the error message appended. Still
failing → run saved as `failed`, clear Estonian error shown. Temperature from Settings.

### Prompt rules

- One testable requirement per row; compound sentences must be split.
- Nothing may be added that is not in the MMR — no invented values, standards or tolerances.
- Vague or ambiguous requirements → `uncertain = true` with a reason.
- **Context segments produce no rows at all** (background, operational concept). Rows
  generated from context segments are measurable false positives.
- Two or three worked examples (MMR sentence → JSON row), using the column semantics in
  [tk_template_reference.md](tk_template_reference.md), fictional content only.
- Output JSON only.

---

## 8. Classification (column C)

Whether a requirement is mandatory or negotiable is an RKIK procurement decision, not MMR
content. So: **default to M**, deviate only on explicit lexical signals. Column C is scored
separately from the comprehension columns, because a wrong M/N is a policy disagreement and a
wrong description is a comprehension failure.

| Class | Signals |
|---|---|
| `M` | `peab`, `tuleb`, `on kohustuslik`, or no modal at all |
| `N` | `peaks`, `võimalusel`, `eelistatavalt`, `soovitavalt`, `soovituslik`, `võiks`, `kui võimalik`; also reference/example items (`näidistoode`, `näiteks nagu …`) and desirable-but-not-mandatory tests |
| `OP` | `optsioon`, `valikuliselt`, `lisavõimalusena`, `pakkuda eraldi hinnaga` |
| `I` | intent, purpose and scope statements only |

Mixed or ambiguous signal → keep `M`, set `uncertain = true`, reason
`"klassifikatsioon ebaselge"`. The triggering word is stored in `classification_signal`.

---

## 9. Categories

Hybrid, with a strong preference for the MMR:

1. **Default** — the MMR's own `HEADING` segments, verbatim, in order of first appearance.
   Every requirement goes under the heading it appears under, unless that clearly does not fit.
2. **No heading available** — a category from the editable default list in Settings:
   `Üldine`, `Mahutavus/Jõudlus`, `Kaitse/Keskkond`, `Liidesed`, `Toide`, `Logistika`,
   `Koolitus ja dokumentatsioon`, `Direktiivid ja standardid`.
3. **Neither fits** — invent a short product-level category (1–3 words), reused consistently,
   no near-duplicates.

`category_source` is stored per row and tagged visibly in the app for `DEFAULT_LIST` and `NEW`.

For ordering and matching, the category key is normalised (strip leading `3.` numbering, trim,
casefold); the original string is always what is displayed and exported.

---

## 10. Verification (columns D, E, F)

Verification is house practice, not MMR content, so the model does not choose it. The model
outputs a **`requirement_type`** — a reading task — and an editable mapping table keyed by
**`(requirement_type, procurement_profile)`** fills `verif_with_bid`, `verif_method`, `verif_stage`.

`procurement_profile` is set per conversion: `COTS` / `MOTS` / `ARENDUS`.

Seeded from real RKIK practice for **COTS** (from the reference TK): almost everything is
verified at `SAT kõik`; documents/standards/directives → `Sertifikaat`; dimensions, weight,
colour, markings → `Funktsionaalne kontroll`; capacity, fit, operation → `Funktsionaalne
demonstratsioon`; measurable lab parameters (vibration, shock, temperature) → `Test` or
`Sertifikaat` (MIL-STD report); informative → `N/A`. `verif_with_bid` mostly
`"jah, sertifikaat"` for M rows, `"ei"` for N rows and directives.
**ARENDUS** uses `FAFAT` / `Disainietapid` / `Analüüs` where sensible. **MOTS** = COTS for now.
The table is tuned in Settings, not in code.

The model may **override** the mapped method/stage only when the MMR explicitly states how
verification is done (e.g. `tõendada katsearuandega`). Then `verif_source = MMR_EXPLICIT` with
the quote stored; otherwise `verif_source = MAPPING`.

### Allowed values (confirmed against the template's dropdowns)

- **`verif_method`** — `Funktsionaalne kontroll`, `Funktsionaalne demonstratsioon`, `Test`,
  `Analüüs`, `Sertifikaat`, `N/A`
- **`verif_stage`** — `Lepingu sõlmimine`, `Lepingu täitmine`, `Disainietapid`, `FAFAT`,
  `FAFAT + suvaline FAT`, `FAT kõik`, `SAT kõik`, `Viimane tarne`, `N/A`

---

## 11. Row ordering

RKIK house style: a TK opens with the informative rows describing what the Contracting
Authority wants (purpose, intended use, scope) before any testable requirement.

Sort key: **(I block first, then category order, then original order)**.

The I block is placed under the first category — the MMR's general/introductory heading if
there is one, otherwise `Üldine`. Then all categories in order of first appearance with their
M/N/OP rows. **The same rule applies to both arms**, so ordering carries no signal about
which arm produced a file.

---

## 12. Paranda mode (phase 1)

The author's own editing mode.

- Table columns: Kategooria, Kirjeldus, Klass, Verif. koos pakkumusega, Meetod, Etapp,
  Verif. kirjeldus, Kommentaarid, Allikas. `Klass`, `Meetod`, `Etapp` are dropdowns.
- Cells editable inline, **every edit saved immediately**, row marked `edited_by_user`.
- `uncertain` rows highlighted **light purple `FFE4DFEC`** with the reason shown.
  Purple was chosen because it appears nowhere in the template — orange now means `I`.
- `I` rows greyed out.
- Add row, delete row (**soft delete**, counted), move up/down.
- Hovering `Allikas` shows the MMR segment text.

### What the diff measures

The **immutable raw snapshot** is the accuracy source. The edit diff is **review effort**, a
secondary metric — not accuracy.

- Soft-deleted rows count as LLM **over-generation**.
- Rows added by hand count as LLM **misses**.
- Whitespace-only and capitalisation-only edits are **ignored** in the change rate.

---

## 13. Seeded sample MMR

One invented satellite-terminal rugged transport case, ~15 segments, deliberately containing
the hard cases so it doubles as a test fixture:

- two headings
- one compound sentence hiding three requirements
- one vague sentence (`piisavalt vastupidav`)
- one bullet list
- one table row
- one requirement with no heading above it
- one explicit verification instruction (exercises `MMR_EXPLICIT`)
- three context sentences (background / operational concept, not requirements)
- one informative intent sentence
- one `N` signal (`peaks` / `võimalusel`)
- one `OP` signal (`optsioon`)

Invented, not sanitised — it is committed, so it must contain nothing real.

---

## 14. Missing aspects (phase 3)

Two distinct outcomes per aspect, because the prompt forbids inventing anything not in the MMR:

- **Red** — the MMR mentions the aspect but the TK does not. A genuine omission; counted in the
  research export, with the matching segment stored. Labelled **`heuristiline`**: it is a
  keyword heuristic, not an accuracy measure (a stem can appear in a context segment).
- **Grey** — neither mentions it. Advice to the engineer: the MMR is incomplete and a row may
  be added by hand.

Aspects and stems live in Settings, matched on **stems** because Estonian inflection wrecks
exact-word matching: `garantii`, `koolit`, `väljaõp`, `hooldu`, `dokumentatsioon`, `varuosa`,
`tähist`, `markeer`, `silt`, `märgis`, `pakend`, `pakk`, `paigald`, `tarn`.

Hidden in Hinda mode.

---

## 15. Hinda mode (phase 3)

Flag-only review for the three Part 2 engineers.

- Reviewer enters an **anonymous code** (R1, R2, R3) held in the session. **No names stored.**
- **Cells are read-only.** Editing is Paranda mode only, or reviewers would overwrite each
  other and destroy the diff.
- One optional flag per row, one click, three states: empty / `vale` / `vajab muutmist`, plus
  an optional short note. Stored in `RequirementFlag`, keyed `(requirement, reviewer_code)`.
- **Each reviewer sees only their own flags.** Three independent judgements per row gives
  inter-rater agreement; three contaminated ones give nothing.
- `Puuduv nõue` creates a per-reviewer `MissingNote`, **not** a new TK row, so reviewers never
  affect the draft or each other.
- Timer per `(conversion, reviewer_code)`; minutes stored per reviewer, one decimal.

### What Hinda shows and hides

`hinda_show_hints` (Setting, **default true**) controls the first group.

- **Shown** — the numbered MMR, source-segment links per row, the `uncertain` highlight with
  its reason. These are part of what Part 2 tests.
- **Hidden** — `category_source` tags, `classification_signal`, missing-aspects panel, run
  metadata, anything about other reviewers.

---

## 16. Exports

Two different files, because one file cannot be both the deliverable and the research artefact.

### Clean TK

Exact RKIK template layout. Produced by **filling a committed copy of the blank template**,
not by building a workbook from scratch — so the instruction preamble, the `NORMATIIVID`
block, the dropdowns, the print settings and the START sheet all survive.

- Header row **22**, data from **row 24**; row 23 is a group row with only column B.
- The template ships 32 data rows (24–55). More rows → insert rows **and extend the
  `E`/`F` validation ranges**.
- openpyxl **drops the `x14` extension dropdowns on load** — they must be re-added on save.
  One test pins this.
- **Clear all inherited fills on every written row first**, then apply the classification fill
  to column C only.
- Yellow `FFFFFF00` on supplier columns I–J is kept: that is part of the real template, not an
  app marker.
- **No segment ids, no uncertain colours.** Column H only if there is a real comment.
- Available for the **raw snapshot**, the **final reviewed version** and the **manual arm**, in
  an identical neutral format — same fonts, column widths, sheet names, row order, metadata
  stripped.

### Research copy

Everything: segment ids, uncertain highlighting and reasons, raw vs final, changed fields,
flags, notes, reviewer codes.

### Blinded packet (phase 2)

- Clean files named `TK_<mmr_id>_<6-char code>.xlsx`; `code → (conversion, arm, raw|final)`
  stored only in the research data.
- **Workbook metadata stripped** on save — openpyxl writes a creator/modified stamp, and the
  template carries `docProps` and `customXml` from its origin.
- `Pimehindamise pakett` exports all clean files of the selected conversions in **shuffled
  order** as one zip, plus a **separate key CSV** kept closed until scoring is finished.

### Comparison CSV

One line per row: raw values, final values, list of changed fields, flag, note,
deleted/added flags.

### Classification fills (editable Settings, with a colour preview)

| Setting | Value | Source |
|---|---|---|
| `class_fill_M` | `FF00B0F0` | 26 mandatory rows in the reference TK |
| `class_fill_I` | `FFFFE699` | first data row of the reference TK |
| `class_fill_N` | *(empty)* | to be set from a real filled TK |
| `class_fill_OP` | *(empty)* | no fill unless set |

---

## 17. Study-order enforcement (phase 2)

No strict A-first rule — the design is counterbalanced.

- Per conversion: `assigned_order` (`A_FIRST` / `B_FIRST`), `arm_a_imported_at`,
  `first_llm_run_at`, gap in days.
- Second arm starting **less than 7 days** after the first → warning shown and
  `order_violation = true` recorded. **Not blocked.**
- `B_FIRST` → arm A cannot be imported before an LLM run exists.
  `A_FIRST` → the LLM cannot run before arm A is imported. Any override is recorded.
- The **answer key** is uploaded per conversion as a separate **locked** artefact with its own
  timestamp, which must be **earlier than both arms**; flagged if not.
- All timestamps, the gap, the assigned order and the flags go into the research export.

Per-field columns are scored against written criteria in the author's scoring guide, never
against identity with the author's wording — otherwise "different but equally valid" counts as
an LLM error.

---

## 18. Run log

Page `Käivituste logi`, with `Ekspordi CSV`.

Per run: `mmr_id`, timestamp, model, input/output tokens, **model time** (`processing_seconds`)
kept separate from **queue time**, rows generated, schema valid, uncertain rows, retry used,
mock, status, error.

Conversions run as a **background task** with HTMX status polling, never a blocking request —
a Railway proxy will cut a three-minute request regardless of what the code does.

- Progress states: `queued → splitting → calling model → validating → done/failed`.
- Response **streamed**; max output tokens **≥ 16k** for ~80 rows.
- **On startup, any run still running is marked `failed`** (Railway restarts kill in-process
  tasks), with a `Proovi uuesti` button.

---

## 19. Settings

Stored in the DB, seeded on first run.

Model name · temperature slider 0.0–1.0 step 0.1 · editable system prompt with
`Taasta vaikimisi` · default category list · verification mapping table
`(requirement_type, procurement_profile)` · classification fill colours with preview ·
missing-aspect stems · `hinda_show_hints`.

---

## 20. Access, errors, limits

- `APP_PASSWORD` set → whole app behind one shared password and a session cookie. The public
  Railway URL must not let strangers spend API credits.
- Nothing hard-codes "there is exactly one user": accounts later are a migration, not a rewrite.
- Database unreachable → friendly Estonian error page, never a stack trace.
- LLM errors, timeouts and invalid uploads → clear Estonian messages.
- Max upload **5 MB**. `/health` returns 200.

---

## 21. Tests

pytest, SQLite in-memory, mock converter, no real key.

Segmentation (including the tricky Estonian cases: abbreviations, decimal commas,
`digit+period` at line start, bullets, table rows) · pydantic schema validation, valid and
invalid · `source_segments` referencing a non-existent id · mock converter · classification
signal rules · verification mapping · row ordering with the I block · xlsx export columns,
header row 22, data from row 24, classification fills, cleared inherited fills, surviving
dropdowns · login protection when `APP_PASSWORD` is set · `/health`.

---

## 22. Design

Modern, minimal, professional. Slate/Zinc neutrals with a dark navy accent, rounded corners,
subtle borders. Readable on mobile; the table scrolls horizontally. Sidebar ~260px with a
hamburger on mobile: `Konversioonid` list (title, date, status), trash icon on hover with
confirm, sticky `Uus konversioon`, and `Käivituste logi` / `Seaded` at the bottom.

**UI language is Estonian throughout.**

---

## 23. Known risks

- **Accuracy on real MMR language is never measured.** Only invented and sanitised documents
  ever enter the app, so the numbers describe performance on sanitised prose.
- **The author is tool author, reviewer and scorer.** Mitigated by the pre-written locked
  answer key, blinded exports and the shuffled packet — not eliminated.
- **N and OP fill colours are unknown** until a real filled TK is opened.
- **The red missing-aspect count is heuristic**, not an accuracy measure.
- `n = 3` in Part 2 supports inter-rater agreement, not statistical significance.
