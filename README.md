# TTB Label Verification

An assistive tool for TTB compliance agents. It reads an alcohol-beverage label, compares it to the COLA application, checks the relevant requirements, and returns a fast field-by-field `PASS / FLAG / FAIL` report. It flags items for human review; it never auto-approves or auto-rejects.


## What It Does

- Reads a real COLA record. Upload a TTB Form 5100.31 PDF and the app parses the application fields and extracts the affixed label images from the same document.
- Verifies field by field. Each field uses the matching strategy its rule actually needs, not a single generic string compare.
- Supports three workflows:
  1. COLA record upload
  2. Manual entry plus label image upload
  3. Batch verification for many records at once
- Saves verifications and reviewer decisions when `DATABASE_URL` is configured. Without a database the app runs stateless.
- Includes a History assistant for saved verifications. It answers questions across saved records and shortlisted PDFs. Chat is ephemeral and is not stored in the database.

## Core Verification Logic

Different fields need different matching strategies:

| Field | Strategy |
|---|---|
| Brand / Fanciful name | Normalize, accent-fold, and fuzzy match against brand or fanciful name |
| Producer / Importer | Match applicant against legal name, DBA, or importer using distinctive company tokens |
| Alcohol content | Numeric parse with tolerance plus proof = 2 x ABV cross-check |
| Net contents | Unit-normalized comparison against the application's allowed-size set |
| Class / Type | Advisory only; the TTB code is not printed verbatim on labels |
| Country of origin | Required only if the product is imported |
| Government warning | Strict check against 27 CFR 16.21 wording and all-caps `GOVERNMENT WARNING:` prefix |

Type size, characters-per-inch, and contrasting background are out of scope for this prototype.

## Architecture

```text
React/Vite SPA  -->  FastAPI
  - COLA upload        - /api/verify/cola
  - manual entry       - /api/verify/manual
  - batch dashboard    - /api/verify/batch
  - history assistant

FastAPI backend
  - ColaParser: PDF form-layer fields + embedded label images
  - VisionProvider: OpenAI (default) | Anthropic
  - Extractor: label image(s) -> structured extracted fields
  - MatchEngine: deterministic comparison logic
  - RulesEngine: beverage-type required-field rules
  - db: optional PostgreSQL persistence for verifications and reviewer decisions
```

The provider is swappable behind an interface so the matching engine stays independent from the model choice.

## Setup

Prerequisites:

- Python 3.12+ for the backend
- Node 18+ for the frontend
- `OPENAI_API_KEY` if using the default OpenAI provider

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
copy .env.example .env
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

Backend runs at `http://127.0.0.1:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`.

## Tests

```bash
cd backend
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m ruff check app tests
cd ../frontend
npx tsc --noEmit
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `TTB_VISION_PROVIDER` | `openai` | `openai` or `anthropic` |
| `TTB_VISION_MODEL` | `gpt-5.4-mini` | Vision model name |
| `TTB_VISION_MAX_TOKENS` | `2048` | Max output tokens for model calls |
| `TTB_REQUEST_TIMEOUT` | `60` | Per-call timeout in seconds |
| `TTB_MAX_RETRIES` | `1` | Retry count for provider calls |
| `OPENAI_API_KEY` | none | Required when provider is `openai` |
| `ANTHROPIC_API_KEY` | none | Required when provider is `anthropic` |
| `DATABASE_URL` | unset | Enables PostgreSQL persistence when provided |
| `TTB_BATCH_CONCURRENCY` | `5` | Records verified in parallel in batch mode |

## Production Deployment

For Railway:

- Root directory: `backend`
- Start command: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Optional variable: `DATABASE_URL` if you want saved history and reviewer decisions

## Tools Used

- Backend: Python, FastAPI, Pydantic, PyMuPDF, OpenAI SDK, Anthropic SDK, SQLAlchemy, psycopg, pytest, ruff
- Frontend: React, Vite, TypeScript
- Persistence: PostgreSQL when configured

## Assumptions And Trade-Offs

- The COLA record contains both sides of the comparison: form claims and label images.
- Persistence is an added feature, not a PRD requirement.
- The History assistant is ephemeral. It can search saved history and inspect shortlisted PDFs, but chat itself is not persisted.
- `gpt-5.4-mini` is the default because it best fits the sub-5-second target for normal runs.
- Stylized or low-quality warning text is flagged for human review rather than falsely failed.

## Project Docs

- [`Overview.md`](Overview.md) - brief documentation of approach, tools used, and assumptions made

## Repository Layout

```text
backend/    FastAPI app, parser, extraction, matching engine, tests
frontend/   React/Vite SPA
docs/       project brief
```
