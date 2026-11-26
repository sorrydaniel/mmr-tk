# Backlog

Phases, in build order. Full detail for every item is in [SPEC.md](SPEC.md).

All tables for phases 1–3 are created, empty, in the **initial** Alembic migration, so phases 2
and 3 ship as code only and never migrate a database that by then holds real study data.

---

## Phase 1 — course deliverable, must deploy and work

Done when the app is live on its Railway URL, a sample MMR converts end to end in both mock and
LLM mode, and the clean TK downloads in the real template layout.

- [ ] Project skeleton: `requirements.txt`, `.python-version`, `.env.example`, `railway.json`
- [ ] `DATABASE_URL` rewrite to `postgresql+psycopg://`, engine, session
- [ ] All models for phases 1–3 + initial Alembic migration
- [ ] Startup seeding: system prompt, category list, verification mapping, classification fills, invented sample MMR
- [ ] Login: `APP_PASSWORD` + session cookie, whole app protected when set
- [ ] `/health` returns 200
- [ ] Friendly Estonian DB-unreachable error page
- [ ] Layout: sidebar (conversions, delete with confirm, `Uus konversioon`, `Käivituste logi`, `Seaded`), mobile hamburger
- [ ] New conversion: title, `mmr_id`, `procurement_profile`, paste or upload `.docx` / `.pdf` / `.txt`, max 5 MB
- [ ] Segmentation: HEADING / BULLET / TABLE_ROW / SENTENCE, Estonian abbreviation list, docx structure, numbered MMR panel
- [ ] Background conversion task with HTMX polling, progress states, streaming, ≥16k output
- [ ] Orphaned-run recovery on startup + `Proovi uuesti`
- [ ] Mock converter + yellow "Mock mode – no API key" banner
- [ ] Pydantic validation, one retry with the error message, failed run on second failure
- [ ] Immutable `RequirementSnapshot` written at creation
- [ ] Classification signal rules, `classification_signal`
- [ ] Category resolution (MMR heading → default list → new) with `category_source`
- [ ] Verification mapping `(requirement_type, procurement_profile)`, `MMR_EXPLICIT` override
- [ ] Row ordering: I block first, then category order, then original order
- [ ] Paranda mode: inline edit, immediate save, dropdowns, soft delete, add row, move up/down, uncertain purple, I greyed, source hover
- [ ] Clean TK export by filling the committed blank template; row insertion, dropdown re-add, fills cleared then classification fill applied
- [ ] Run log page + `Ekspordi CSV`
- [ ] Settings: model, temperature, system prompt with `Taasta vaikimisi`, category list, mapping table, classification fills with colour preview
- [ ] Tests per SPEC §21
- [ ] Commit, push, **confirm the Railway deploy works**

---

## Phase 2 — Part 1 research tooling

- [ ] Research copy export (segment ids, uncertain, raw vs final, changed fields)
- [ ] Comparison CSV: raw, final, changed fields, flag, note, deleted/added
- [ ] Clean export for the raw snapshot, the final version and the manual arm, identical format
- [ ] Blinded filenames `TK_<mmr_id>_<6-char code>.xlsx`, workbook metadata stripped
- [ ] `Pimehindamise pakett`: shuffled zip + separate key CSV
- [ ] `Impordi käsitsi TK (.xlsx)` — parse a filled RKIK template, store as arm A, normalise through the same exporter
- [ ] Answer-key upload per conversion: locked artefact, own timestamp, flagged if not earlier than both arms
- [ ] `assigned_order`, arm timestamps, 7-day gap, `order_violation`, override recording

---

## Phase 3 — Part 2, three engineers

- [ ] Hinda mode: read-only cells, anonymous reviewer code in session
- [ ] `RequirementFlag` keyed `(requirement, reviewer_code)`; each reviewer sees only their own
- [ ] Flag UI: empty / `vale` / `vajab muutmist` + optional short note
- [ ] `Puuduv nõue` → `MissingNote` per reviewer, never a TK row
- [ ] Timer per `(conversion, reviewer_code)`, minutes to one decimal
- [ ] `hinda_show_hints` (default true): shows numbered MMR, source links, uncertain highlight; hides `category_source`, `classification_signal`, missing-aspects, run metadata, other reviewers
- [ ] Missing-aspects panel: red (MMR mentions, TK does not — labelled `heuristiline`, matching segment stored) vs grey (neither)
- [ ] Research export: one line per `(requirement, reviewer)` + missing notes + minutes per reviewer, for inter-rater agreement

---

## Future studies

- **Hints vs no hints** — does the uncertain highlight plus source links actually help a human
  reviewer find errors faster? Flip `hinda_show_hints` to false for a second condition. Not
  feasible with three engineers; needs a larger panel.
- **Classification accuracy as its own question** — column C is a procurement policy decision,
  so measure it separately from comprehension and report it separately.
- **Mapping table vs model choice** — does the deterministic `(requirement_type,
  procurement_profile)` mapping beat letting the model pick method and stage directly?

---

## Deferred / open

- `class_fill_N` and `class_fill_OP` hex values — unknown until a real filled TK is opened.
- Per-user accounts. Nothing hard-codes a single user, so this is a migration plus a login
  change, not a rewrite.
- Whether `MOTS` needs its own verification mapping column (currently copies `COTS`).
