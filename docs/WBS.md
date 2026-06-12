# Work Breakdown Structure (WBS)

Hierarchical decomposition of all work into deliverable-oriented tasks. Each leaf task names the
requirement(s) it satisfies (see [TRACEABILITY.md](TRACEABILITY.md)) and the test(s) (TC-xx, defined
in [SPEC.md §8](SPEC.md)) that verify it. Top-level packages follow the build order in
[SPEC.md §10](SPEC.md).

**Status key:** `[ ]` not started · `[~]` in progress · `[x]` done.

---

## 1.0 Project foundation
- **1.1** `[x]` Initialize git repo (`main`); `.gitignore`, branch strategy — *F-deliverable* (GitLab remote pending)
- **1.2** `[x]` Repo layout: `backend/` (app/cola, tests), `docs/`, `ColaData/` — *code quality*
- **1.3** `[x]` Stateless config + secrets via env (`.gitignore`, `.env.example`, `app/config.py` pydantic-settings) — *N4, N5*
- **1.4** `[x]` Backend toolchain (FastAPI, Pydantic, PyMuPDF, pytest, ruff) on Python 3.14 — frontend toolchain pending
- **1.5** `[ ]` CI: lint + unit tests on push — *code quality*

## 2.0 COLA record ingest (ColaParser)
- **2.1** `[x]` PDF form-layer parser — claimed fields by **label keyword** (brand, fanciful, net
  contents, ABV, class/type, applicant, DBA, serial, TTB ID) + **checkbox detection** via vector
  drawings for type/source — *F1* → TC-01 ✓
- **2.2** `[x]` Embedded label-image extraction (front/back/other, page-spanning) via PyMuPDF — *F1, F3* → TC-01 ✓
- **2.3** `[ ]` LLM fallback when keyword parse is low-confidence — *deferred: deterministic parser reads all 5 real records cleanly; revisit if odd form versions appear* — *F1, N5*
- **2.4** `[x]` Parser unit tests against all 5 real `/ColaData` records (11 tests green) — *F1* → TC-01 ✓

## 3.0 Verification core (Extractor + MatchEngine + RulesEngine)
- **3.1** `[x]` `VisionProvider` interface + Anthropic provider (default `claude-sonnet-4-6`, swappable) + Fake provider for offline/tests — *F3, N1, N5* (image downscale preprocessing deferred — COLA images are small)
- **3.2** `[x]` `Extractor`: label image(s) → structured `ExtractedLabel` via `messages.parse`, multi-image aggregation — *F3*
- **3.3** `[x]` Brand matcher — normalize + fuzzy vs {brand ∪ fanciful} — *F4.1* → TC-02 ✓
- **3.4** `[x]` Producer/bottler matcher — vs {legal name ∪ DBA/tradename} — *F4.2* → TC-03 ✓
- **3.5** `[x]` Class/type — semantic/advisory consistency (no string-equality) — *F4.3* → TC-04 ✓
- **3.6** `[x]` ABV matcher — numeric parse + tolerance + proof = 2×ABV cross-check — *F4.4* → TC-08, TC-09 ✓
- **3.7** `[x]` Net-contents matcher — unit normalize + allowed-set membership — *F4.5* → TC-10 ✓
- **3.8** `[x]` Country-of-origin matcher — required iff Imported — *F4.6* → TC-11 ✓
- **3.9** `[x]` Government-warning matcher — strict §16.21 text, ALL-CAPS prefix, across images — *F4.7* → TC-05, TC-06, TC-07 ✓
- **3.10** `[x]` `RulesEngine` — beverage-type required-field rules (beer/wine/spirits/sake) — *F4.8* → TC-12 ✓
- **3.11** `[x]` Verdict model (PASS/FLAG/FAIL + reason + confidence + source image) + low-image-quality guard — *F7* → TC-13 ✓
- **3.12** `[x]` Engine unit-test suite (20 tests, TC-02…TC-13 + extras) — *F4* ✓
- **3.13** `[x]` `/verify/cola` + `/verify/manual` endpoints (both modes), friendly error layer, processing-time — *F1, F2, N6* ✓

## 4.0 Single-record UI (both input modes) — React/Vite, plain CSS design system
- **4.1** `[x]` App shell: navy masthead, high-contrast, large targets, visible focus, semantic HTML, ARIA tabs/live regions — *N2, N3* (formal 508 audit = 6.7)
- **4.2** `[x]` Input mode 1 — COLA-record upload flow (drag-drop/picker → parse + verify) — *F1* ✓ browser-verified
- **4.3** `[x]` Input mode 2 — manual-entry form (field per claimed value + image upload; comparison & extract-only sub-modes) — *F2* ✓ renders; engine path shared with mode 1
- **4.4** `[x]` Wire both modes to `/verify` (api.ts), loading + friendly error states — *N6* ✓
- **4.5** `[x]` Report view: per-field rows (claimed vs label, verdict pill, reason, **read confidence**), overall banner, **processing-time badge**, low-quality notice, assistive disclaimer — *F6, F7, N1, N6* ✓ browser-verified

## 5.0 Batch verification
- **5.1** `[x]` `/verify/batch` endpoint — concurrent (`asyncio.to_thread` + semaphore), per-record failure isolation, summary — *F5* → TC-14 ✓
- **5.2** `[x]` Multi-record upload (multi-select) — *F5* ✓
- **5.3** `[x]` Results dashboard: summary chips + status filter, sortable table, per-row drill-in (reuses Report), CSV export — *F5* → TC-14 ✓ browser-verified
- **5.4** `[x]` Batch UI accessibility — semantic table, `aria-sort`, `aria-expanded`, `aria-pressed`, sr-only caption — *N3*

## 6.0 Test corpus, hardening, delivery
- **6.1** `[ ]` Deploy to Render/Railway/Fly; public URL; env config — *deliverable*
- **6.2** `[x]` README — setup & run instructions (`README.md`) — *deliverable*
- **6.3** `[x]` Approach / tools / assumptions / trade-offs (README + `docs/SPEC.md`) — *deliverable*
- **6.4** `[~]` Adversarial test corpus — hostile-variant **unit tests** done (TC-02…TC-13); generated hostile **image** set still pending — *F4, F6*
- **6.5** `[x]` Low-quality-image handling — engine low-quality guard + warning FLAG for unverifiable text — *F6* → TC-13
- **6.6** `[~]` Latency: raw read ~2.5s; local ~8–9s is TLS-proxy-inflated; <5s to verify on deploy — *N1* → TC-15
- **6.7** `[ ]` Section 508 / WCAG formal audit (built accessible; audit pending) — *N3*
- **6.8** `[~]` End-to-end run on all 5 real records — done locally (4 PASS, 1 correct FLAG); deployed run + PRD manual-entry example pending — *all*

---

## Critical path

1.x foundation → **2.x ColaParser** (unblocks real-data testing) → **3.x verification core**
(the intellectual heart; gated by unit tests 3.12) → 4.x single UI → 5.x batch → 6.x deploy &
verify. The parser and engine are the riskiest/highest-value packages and come first; UI and batch
build on a proven core.

## Milestones

- **M1 — Reads real records:** ✅ **DONE** — parser extracts claimed fields (incl. checkbox type/source) + label images from all 5 real records; 11 unit tests green, ruff clean.
- **M2 — Verifies correctly:** ✅ **DONE (engine)** — 3.x complete; engine passes TC-02…TC-13 on hostile variants (41 tests green, ruff clean); both API modes working with Fake provider. Real-image vision pass deferred to M5/e2e (needs API key).
- **M3 — Usable single-record app:** ✅ **DONE (UI)** — both input modes + color-coded report browser-verified end-to-end (parse→extract→match→report), processing-time badge, read confidence, friendly errors, accessible by construction. Real-vision <5s latency (TC-15) + formal 508 audit (6.7) at M5.
- **M4 — Batch:** ✅ **DONE** — 5.x complete; concurrent `/verify/batch`, sortable/filterable dashboard + drill-in + CSV export, browser-verified on 3 real records (all PASS, processed in parallel). 46 tests green.
- **M5 — Delivered:** 6.x done; deployed URL, README, docs; full real-record + PRD-example pass.
