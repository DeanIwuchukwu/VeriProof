# Overview

## Approach

This project was built as a standalone proof of concept for TTB label verification. The core idea is to compare what the COLA application claims against what appears on the label, then return a field-by-field assistive result for a compliance agent.

The implementation is split into clear stages:

1. Parse the COLA record.
   The backend reads the PDF form layer to extract claimed application fields such as brand name, fanciful name, product type, source, alcohol content, applicant, and net contents. It also extracts the affixed label images from the same record.

2. Read the label.
   A model-backed provider reads the label images and returns a structured extraction. The provider is swappable so the matching layer is not tied to one vendor.

3. Compare deterministically.
   The matching engine applies rule-specific comparisons rather than one generic string compare. For example, ABV is numeric, net contents are unit-normalized, producer matching is token-based, and the government warning is checked strictly.

4. Present an assistive result.
   The API and frontend show a per-field report with reasons, confidence, and an overall status. The tool flags records for review; it does not make approval decisions.

The project also includes optional persistence for saved verifications and reviewer decisions, plus an ephemeral History assistant that can answer questions across saved records and shortlisted PDFs.

## Tools Used

- Python
- FastAPI
- Pydantic
- PyMuPDF
- OpenAI SDK
- Anthropic SDK
- SQLAlchemy
- psycopg
- React
- Vite
- TypeScript
- pytest
- ruff

## Assumptions Made

- The uploaded COLA record is the primary source because it contains both the application data and the label images.
- The system is assistive, not autonomous. PASS / FLAG / FAIL is meant to support a compliance reviewer, not replace one.
- Model-backed label reading is acceptable for the prototype because the main goal is usable and fast comparison rather than full on-premises deployment.
- Optional persistence is an extra capability beyond the PRD, so the app can still run fully stateless without a database.
- The History assistant should be useful but lightweight, so chat memory is ephemeral and not stored.
- Some label checks, especially stylized or curved warning text, are better flagged for manual review than over-automated into false failures.

## Known Limitations

- The label-reading step depends on a model provider when using the real verification path.
- Exact typography checks such as type size and boldness are out of scope for this prototype.
