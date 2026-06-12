# TTB Label Verification

An assistive tool for TTB compliance agents: it reads an alcohol-beverage **label**,
compares it to the **COLA application**, checks it against the **regulations**, and returns a
fast, field-by-field **PASS / FLAG / FAIL** report. It flags items for human review — it never
auto-approves or auto-rejects.

> Built for the take-home described in [`docs/TTB_Label_Verification_Project.pdf`](docs/TTB_Label_Verification_Project.pdf).
> The detailed spec, requirements-traceability matrix, and work breakdown live in [`docs/`](docs/).

---

## What it does

- **Reads a real COLA record.** Drop a TTB Form 5100.31 PDF; the app parses the *application* fields
  (brand, ABV, net contents, type, source, applicant/DBA…) **and** extracts the affixed *label images*
  from the same document — no typing.
- **Verifies intelligently, field by field.** Each field uses the matching strategy its regulation
  actually requires (see [The core idea](#the-core-idea) below) — not one dumb string compare.
- **Two co-equal input modes + batch:**
  1. **COLA record** — upload the 5100.31 PDF.
  2. **Manual entry** — type the claimed values + upload label image(s) (maps to the brief's sample fields).
  3. **Batch** — upload many records at once (the peak-season case), with a sortable/filterable
     results table, per-row drill-in, and CSV export.
- **Assistive & accessible.** Color-coded results (status by icon **+** text **+** color), read
  confidence, processing-time badge, plain-English reasons, keyboard/screen-reader friendly
  (Section 508-minded).
- **Saved verifications & reviewer decisions.** Each verification (claimed fields, results, and the
  original COLA PDF) is stored in PostgreSQL, and reviewers can Accept/Reject with a note —
  recorded append-only as an audit trail. Optional: with no `DATABASE_URL` configured the app runs
  fully stateless (nothing persisted).

### Verified on the real sample records

Run end-to-end against the five public COLA records in [`ColaData/`](ColaData/):

| Record | Beverage | Verdict | Why it's a good test |
|---|---|---|---|
| Cascade Winery | Table wine (domestic) | ✅ PASS | DBA "Cascade Winery", rotated back-label warning |
| Bärenjäger | Honey liqueur (imported) | ✅ PASS | diacritics (`Bärenjäger`=`BARENJAGER`); separate importer (Sidney Frank) vs German bottler |
| Jacques Cardin | Cognac (imported) | ✅ PASS | multi-size net contents (375/750/1 L); French text |
| Stillwater Artisanal | Flavored ale (domestic) | ⚠ FLAG | **radial keg-collar warning** flagged for human review |
| Gekkeikan "Suzaku" | Sake (imported) | ✅ PASS | fanciful name dominates label; Japanese text |

The single FLAG is intentional: the radial keg-collar warning is the hardest text in the set, so it's
**flagged for review** rather than falsely failed.

---

## The core idea

Different fields need **opposite** matching strategies — this is what separates a useful tool from a
naive string comparator (see `docs/SPEC.md §4`):

| Field | Strategy |
|---|---|
| Brand / Fanciful name | normalize + **accent-fold** + fuzzy; match the label against {brand ∪ fanciful} |
| Producer / Importer | match the applicant against {legal name ∪ DBA ∪ importer} on **distinctive company tokens** (ignores "Imported by" and address noise) |
| Alcohol content | numeric parse + tolerance, **and a proof = 2 × ABV cross-check** |
| Net contents | unit-normalized; label value must be **in the form's allowed-size set** |
| Class / Type | **advisory** — the TTB code is never printed verbatim on the label, so it's never a hard fail |
| Country of origin | required **iff** the product is imported |
| **Government warning** | **strict** — exact 27 CFR §16.21 text, `GOVERNMENT WARNING:` present & ALL-CAPS; a confidently-read altered warning FAILs, an unreadable/stylized one FLAGs |

Type-size / characters-per-inch / contrasting-background are **out of scope** — TTB itself does not
review those at the COLA stage (per the records' own qualification text); they're noted as advisory.

---

## Architecture

```
React/Vite SPA  ──HTTP──>  FastAPI (async)
  • COLA upload              • /api/verify/cola     (single record)
  • manual form + image      • /api/verify/manual   (claimed fields + images)
  • batch dashboard          • /api/verify/batch    (concurrent, many records)
                             ├─ ColaParser    PDF form-layer fields + label images (PyMuPDF)
                             ├─ VisionProvider  swappable: OpenAI (default) | Anthropic | Fake (offline)
                             ├─ Extractor      label image(s) -> structured fields
                             ├─ MatchEngine    per-field strategies (pure, unit-tested)
                             └─ RulesEngine    beverage-type required-field rules
                             └─ db (PostgreSQL)  verifications (+ original PDF) & reviewer decisions
  Persistence is optional: without DATABASE_URL the app runs fully stateless.
```

The **vision provider is swappable behind an interface** (one env var). This is the design answer to
the real-world firewall constraint in the brief: the AI can be pointed at Anthropic, an in-tenant
Azure OpenAI deployment, or a local OCR model without touching the matching engine.

---

## Setup & run

**Prerequisites:** Python 3.12+ (tested on 3.14), Node 18+, and an `OPENAI_API_KEY`
(or run fully offline with the Fake provider — see below).

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt # macOS/Linux

cp .env.example .env        # then put your key in OPENAI_API_KEY
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

Backend runs at `http://127.0.0.1:8000` (interactive API docs at `/docs`).

> **Offline / no key:** set `TTB_VISION_PROVIDER=fake` to run with a deterministic stub reading —
> the whole pipeline and UI work without any network or key (used by the test suite).

### 2. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (proxies /api to the backend)
```

Open `http://localhost:5173`, choose a mode, and verify a record from [`ColaData/`](ColaData/).

### 3. Tests

```bash
cd backend
TTB_VISION_PROVIDER=fake .venv/Scripts/python.exe -m pytest   # 47 tests, no network
.venv/Scripts/python.exe -m ruff check app tests              # lint
cd ../frontend && npx tsc --noEmit                            # frontend typecheck
```

---

## Configuration (env)

| Variable | Default | Purpose |
|---|---|---|
| `TTB_VISION_PROVIDER` | `openai` | `openai`, `anthropic`, or `fake` (offline) |
| `TTB_VISION_MODEL` | `gpt-5.4-mini` | low-latency default; can also point at `gpt-5.4`, `claude-haiku-4-5`, or `claude-sonnet-4-6` |
| `OPENAI_API_KEY` | — | required when provider is `openai` |
| `ANTHROPIC_API_KEY` | — | required when provider is `anthropic` |
| `TTB_BATCH_CONCURRENCY` | `5` | records verified in parallel per batch |
| `TTB_REQUEST_TIMEOUT` | `60` | per-call timeout (seconds) |

---

## Tools used

- **Backend:** Python · FastAPI · Pydantic · PyMuPDF (PDF text + image extraction) · OpenAI SDK · Anthropic SDK ·
  `truststore` (use the OS trust store for TLS) · pytest · ruff.
- **Frontend:** React · Vite · TypeScript · hand-written CSS design system (no UI framework).
- **Vision:** a low-latency vision model via structured prompt + Pydantic validation, defaulting to `gpt-5.4-mini`.

---

## Assumptions, trade-offs & limitations

- **The COLA record carries both sides of the comparison.** Application fields and label images travel
  together in the 5100.31, so agents type nothing in the primary flow. Manual entry is the secondary
  path for ad-hoc checks and the brief's sample fields.
- **Persistence is opt-in; no auth.** With `DATABASE_URL` set, verifications (incl. the original
  PDF) and reviewer decisions are stored (PostgreSQL); without it the app is fully stateless.
  Decisions are anonymous (no login system) and append-only. COLA-system integration remains out
  of scope per the brief.
- **Latency.** The raw vision read is ~2.5s; end-to-end on a normal network targets the brief's <5s.
  On a machine behind a **TLS-inspecting proxy** (as the dev machine was) times are inflated to ~8–9s
  — an environment artifact, not the product. `truststore` is included so such proxies don't break TLS.
- **Government warning on stylized text.** Curved/rotated/tiny warnings (e.g. a radial keg collar) are
  hard to OCR exactly; rather than false-fail a compliant label, the tool **flags it for human review**.
  A confidently-read *altered* warning still fails.
- **Bold / exact type-size detection** is best-effort and clearly labeled — it is outside TTB's own
  COLA review scope.
- **Model choice.** Sonnet is the default (accuracy); Haiku was measured ~2× faster on simple labels
  but repeatably garbled small back-label text, so it's opt-in via env.

---

## Project docs

- [`docs/SPEC.md`](docs/SPEC.md) — specification, the per-field matching rules, test strategy.
- [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) — requirements traceability matrix (every requirement → source → component → test).
- [`docs/WBS.md`](docs/WBS.md) — work breakdown structure and milestones.

## Repository layout

```
backend/    FastAPI app (cola parser, extraction, matching engine), tests
frontend/   React/Vite SPA
ColaData/   real public COLA records used as the test corpus
docs/        spec, traceability matrix, WBS, the project brief
```
