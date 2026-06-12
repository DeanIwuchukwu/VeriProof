# TTB Label Verification — Specification & Requirements Traceability

> **Product:** A standalone tool that ingests a TTB COLA record (the application data + the
> affixed label artwork, which travel together), automatically extracts the label's fields,
> compares them to what the application claims, checks the label against TTB regulations, and
> returns a fast, clear, field-by-field PASS / FLAG / FAIL report. Assistive — it flags for human
> review; it never auto-approves or auto-rejects.

This document is the source of truth for *what* we build and *why*. Every requirement traces to a
line from the discovery interviews, the TTB regulations, or the **real COLA records** in
`/ColaData`, plus the test that proves we met it. Nothing in the interviews or the data is allowed
to slip through silently.

---

## 1. Problem & goal

The TTB reviews ~150,000 label applications/year with 47 agents. Much of the work is rote
*matching* — confirming the value on the form equals the value on the label. The goal is to
automate that matching so agents spend their judgment on the cases that need it.

This is an explicitly **standalone proof-of-concept**. No COLA integration. It exists to inform
future procurement, not to ship to production. But it must *work*, be *fast*, and be *usable by a
non-technical agent* — because the last vendor pilot failed on exactly those points.

**Definition of "verification":** given claimed field values + one or more label images — supplied
either as a COLA record or entered manually — extract each field from the label image(s), compare it
to the application's claim using
the correct per-field strategy, check the label against the regulations that need no claim
(government warning, required-field presence), and report PASS / FLAG / FAIL per field with a
plain-English reason and a confidence.

---

## 2. The data: real COLA records drive the design

`/ColaData` contains five real, public COLA records exported from TTB COLA Online
(`ttbonline.gov/colasonline/viewColaDetails.do?action=publicFormDisplay&ttbid=…`). Each is a Form
5100.31 that **bundles the structured application data and the affixed label images in one
document.** This is the single most important fact about the project: the two sides of every
comparison already travel together. The agent does not retype anything.

The five records span the real variety we must handle:

| TTB ID | Product | Source | Notable for |
|---|---|---|---|
| 11038001000725 | Bärenjäger Honey Liqueur | Imported | Tiny dense warning on back; 50 ML; "35" vs "35% ALC. BY VOL." |
| 03211001000018 | Cascade Val (table red wine) | Domestic | Warning rotated 90° vertical; DBA "Cascade Winery (Used on label)" |
| 11262001000022 | Jacques Cardin Jasmin VSOP (cognac) | Imported | Multi-size net contents (375/750/1 L); French; warning on back |
| 11364001000181 | Stillwater Artisanal Debutante (flavored ale) | Domestic | **Radial warning on a circular keg collar**; brand vs fanciful; DBA "Twelve Percent" |
| 13100001000426 | Gekkeikan "Suzaku" Junmai Ginjo (sake) | Imported | Fanciful name dominates label; Japanese text; gluten qualification |

These records double as our **test corpus** (real ground truth), expandable from the public registry
(see §8).

---

## 3. Users & their constraints

| Persona | What they tell us | Design consequence |
|---|---|---|
| **Sarah Chen** (Deputy Director) | Speed killed the last pilot; UX must suit a 73-yr-old; batch uploads "would be huge" | Latency budget, radical simplicity, batch mode |
| **Marcus Williams** (IT) | Azure/FedRAMP; firewall blocks outbound ML endpoints; no sensitive storage for prototype | Swappable AI provider; stateless; document the production path |
| **Dave Morrison** (28-yr agent, skeptic) | "STONE'S THROW" = "Stone's Throw"; needs judgment; don't make life harder | Fuzzy/semantic matching; assistive framing; never auto-reject |
| **Jenny Park** (junior agent) | Warning must be exact, all-caps, bold; people game it; bad image quality is painful | Strict warning matching; image robustness |

---

## 4. The core insight: form-field semantics + per-field matching strategies

The interviews pull in opposite directions (Dave wants leniency; Jenny wants zero tolerance), and
the real records prove that **a single string comparator fails on every one of them.** Each field
gets the strategy its regulation *and the data* demand. The rules below are read directly off
`/ColaData`.

| Field | Strategy | Evidence / source |
|---|---|---|
| **Brand name** | Match label against **{brand name ∪ fanciful name}**, normalized + fuzzy; report which matched | Gekkeikan: brand "GEKKEIKAN" small, fanciful "SUZAKU" dominant on label |
| **Bottler / producer name** | Compare label producer against **{applicant legal name ∪ approved DBA/tradename}**, normalized + fuzzy | Stillwater: label "Brewed by Twelve Percent" = form's "TWELVE PERCENT (Used on label)" DBA |
| **Class/Type designation** | **Not** a string match. Form's CLASS/TYPE DESCRIPTION is a TTB internal code, never verbatim on label → semantic/advisory consistency check only | "TABLE RED WINE" vs label "Red Wine"; "SAKE - IMPORTED" vs "Junmai Ginjo" |
| **Alcohol content (ABV)** | Parse to a number; tolerance-aware; **cross-check proof = 2 × ABV** for spirits | Form "35"/"40"/"11.5" vs label "35% ALC. BY VOL." etc. |
| **Net contents** | Parse value + unit; normalize (mL/L/fl oz/gal); **label value must be ∈ the form's allowed-size set** | "375 ML / 750 ML / 1 LITER"; keg "5.17/5.4/10.8/15.5 gal." |
| **Country of origin** | Required **iff Source = Imported**; check label carries a country statement | "IMPORTED FROM FRANCE", "PRODUCT OF JAPAN"; domestics carry none |
| **Government Warning** | **STRICT.** Read across the **full multi-image set**; exact 27 CFR §16.21 text; `GOVERNMENT WARNING:` present + ALL-CAPS; flag paraphrase/omission/casing games | Warning lives on the back, rotated, radial, or tiny across the records |

Two structural consequences:

1. **Extraction aggregates across all label images in a record** (front / back / capsule). A
   required element present on *any* label counts; the report says which image it came from.
2. **The engine understands form-field semantics** (brand vs fanciful, legal name vs DBA, internal
   class code vs label designation) rather than naive equality. This *is* Dave's "judgment,"
   encoded.

### The Government Warning — exact mandated text (27 CFR §16.21)

> **GOVERNMENT WARNING:** (1) According to the Surgeon General, women should not drink alcoholic
> beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic
> beverages impairs your ability to drive a car or operate machinery, and may cause health problems.

Checks: prefix `GOVERNMENT WARNING:` present **and** in capital letters; both numbered statements
present and word-for-word; flag paraphrase, omission, and title-case ("Government Warning").

### Scope line on type size / contrast / bold (handed to us by the data)

The newer records carry a TTB qualification: *"TTB has **not** reviewed this label for type size,
characters per inch or contrasting background…"* So **TTB itself does not verify type-size /
CPI / contrast at the COLA stage.** We mirror that: we verify the warning's **text, capitalization,
and presence** (content, which TTB enforces), and we offer type-size/contrast only as a clearly
labeled **best-effort advisory** marked *"outside COLA certification scope (per TTB qualification)."*
Bold detection from a photo is likewise best-effort and labeled as such.

### Beverage-type-aware required fields

Requirements differ by class (beer / wine / distilled spirits / sake), keyed on the form's TYPE OF
PRODUCT + SOURCE. E.g. ABV mandatory for spirits with exceptions for some beer/wine; country of
origin only for imports. Missing-but-required → FAIL; missing-but-optional → informational.

---

## 5. Functional requirements

The tool has **two co-equal input modes** (F1, F2) that feed one shared engine (F3–F4).

### F1 — COLA record ingest (bulk / realistic path)
- Upload one COLA record (PDF or the COLA Online HTML page).
- **Parse the form layer** into claimed field values (by label keyword — "BRAND NAME", "NET
  CONTENTS", "ALCOHOL CONTENT", "TYPE OF PRODUCT", "SOURCE OF PRODUCT", "CLASS/TYPE DESCRIPTION",
  applicant block, DBA — since field *numbers* vary across form versions but labels are stable).
- **Extract the embedded label image(s)** (front / back / other).
- Verify label(s) against claims + regulations → field-by-field report.

### F2 — Manual-entry verification mode (demo / ad-hoc / PRD-sample path)
- A guided form with a **text field per claimed field** (Brand, Fanciful name, Class/Type, ABV,
  Net contents, Producer/bottler) plus a **Source = domestic/imported** selector **+ a label-image
  upload** (one or more: front / back). Country of origin is *not* a manual field — it is a
  regulatory, label-only check driven by Source (imported → the label must state a country).
- **Verify** runs the same Extractor + MatchEngine + RulesEngine as F1 → identical field-by-field report.
- Two sub-modes: values entered → full **comparison**; left blank → **extract-only** + the
  label-only regulatory checks (warning, required-field presence, proof).
- Maps **1:1 to the PRD's "Example Distilled Spirits Label Fields"**; it is the primary path for an
  evaluator with no COLA PDF, for one-off/ad-hoc checks, and for spot-checking / trust-building (Dave).

### F3 — Extraction (vision)
- Vision model returns **structured JSON** against a strict schema (field, raw text, normalized
  value, source image, confidence). Aggregated across all label images.
- Provider behind an interface; default = fast cloud vision LLM; swappable to Azure OpenAI or local OCR.

### F4 — Matching engine
- Per-field strategies from §4. Pure, unit-tested, deterministic given extraction output.
- Brand∪fanciful, legal-name∪DBA, numeric ABV + proof cross-check, net-contents allowed-set,
  country-iff-imported, strict warning, semantic class/type. Beverage-type required-field rules.

### F5 — Batch verification
- Upload many COLA records (multi-select / zip). Concurrent processing (respect provider rate
  limits). Sortable/filterable results table; export (CSV). The "200–300 at once" peak-season case.

### F6 — Image robustness
- Tolerate angle/glare/poor lighting/rotation/radial/multilingual (vision-model strength; validated
  by the real keg-collar and rotated-warning records).
- Low extraction confidence → explicit "image quality low — consider rescanning" message, **not** a
  silent failure or false PASS.

### F7 — Assistive framing
- Output is "flags for review." Confidence shown. Reasoning visible. Never auto-approve/reject.

---

## 6. Non-functional requirements

| # | Requirement | Target | Source |
|---|---|---|---|
| N1 | Single-record latency | **< 5 s** end-to-end, displayed to user | Sarah (vendor failed at 30–40s) |
| N2 | Usability | Non-technical, 50+/73-yr-old benchmark; large targets; no hunting for buttons | Sarah |
| N3 | Accessibility | **Section 508 / WCAG 2.1 AA** — keyboard nav, screen-reader labels, contrast | Federal requirement + N2 |
| N4 | Statelessness / privacy | No persistence of records, images, or PII; process in memory, discard | Marcus |
| N5 | Network resilience | Swappable provider; document on-prem/Azure path for firewalled prod | Marcus |
| N6 | Robust errors | Clear, friendly messages; never a blank screen or raw stack trace | Eval: "UX and error handling" |

---

## 7. Architecture

```
React/Vite SPA  ──HTTP──>  FastAPI (async)
  - mode 1: COLA record upload     - /verify        (single record)
  - mode 2: manual form + image
  - report view                    - /verify/batch  (concurrent)
  - batch dashboard                ├─ ColaParser   (PDF/HTML form layer -> claimed fields; extract images)
  - a11y by construction           ├─ VisionProvider (interface) -> default cloud vision LLM
                                    │     (swap: Azure OpenAI / local OCR)
                                    ├─ Extractor    (label image(s) -> structured JSON, schema-validated, multi-image)
                                    ├─ MatchEngine  (per-field strategies, pure + unit-tested)
                                    └─ RulesEngine  (beverage-type required fields)
  Stateless: nothing written to disk/db.
```

- **Backend:** Python + FastAPI, async (batch concurrency). Pydantic schemas for the vision contract
  and API responses.
- **ColaParser:** deterministic parse of the PDF/HTML form layer by **label keyword** (robust across
  form versions); embedded-image extraction (PyMuPDF). **LLM fallback** if keyword parse is
  low-confidence. *Trade-off (documented): deterministic-by-keyword is fast/free but mildly brittle
  across form versions; LLM extraction is robust but adds a call — we default to deterministic with
  LLM fallback.*
- **Vision:** `VisionProvider` interface; default = low-latency `gpt-5.4-mini` via env config.
  Swapping providers = one class + one env var. This answers Marcus's firewall problem in *design*.
- **Frontend:** React + Vite. Minimal, high-contrast, large-target, accessible.
- **Deploy:** Render/Railway/Fly. Secrets via env. Repo on **GitLab**.

---

## 8. Test strategy (adversarial — break it, don't confirm it)

Ground truth is **real**: the five `/ColaData` records (known-good matches), expandable from the
public COLA registry. We then derive **hostile variants** and assert verdicts, not just "it ran."

| TC | Test case | Expected verdict | Proves |
|---|---|---|---|
| TC-01 | Each real record, unmodified | All PASS (or correct advisory) | Happy path on real data |
| TC-02 | Gekkeikan: brand "GEKKEIKAN" vs dominant label "SUZAKU" | Brand PASS via fanciful-name match | Brand∪fanciful rule |
| TC-03 | Stillwater: label "Twelve Percent" vs applicant "Pub Dog Brewing" | Producer PASS via DBA match | Legal-name∪DBA rule |
| TC-04 | Cascade class "TABLE RED WINE" vs label "Red Wine" | No FAIL on class/type | Class/type is semantic, not equality |
| TC-05 | Warning forced to title case ("Government Warning") | Warning FAIL | Jenny's rejection |
| TC-06 | Warning paraphrased / one clause missing | Warning FAIL | Strict matching |
| TC-07 | Radial keg-collar warning (Stillwater) read correctly | Warning PASS | Multi-image + rotation robustness |
| TC-08 | Label "(80 Proof)" with "45% ABV" (proof≠2×ABV) | ABV FLAG | Proof cross-check |
| TC-09 | App ABV 40% vs label 45% | ABV FAIL | Real mismatch caught |
| TC-10 | Net contents "750 ML" against allowed set {375,750,1 L} | PASS | Allowed-set rule |
| TC-11 | Import (Jacques Cardin) with country statement removed | FAIL | Country-iff-imported |
| TC-12 | Domestic beer missing ABV (if optional for type) | Informational, not FAIL | Beverage-type rules |
| TC-13 | Unreadable / blank image | Friendly "image quality low," no false PASS | N6 + F6 |
| TC-14 | Batch of N records incl. seeded failures | Each correct; table sortable; export works | F5 |
| TC-15 | Single-record latency | < 5 s, measured | N1 |

Matching engine: unit tests (pure functions). Parser: tested against all five real records.
End-to-end: the live deployed app against every grader-relevant scenario + the literal PRD example.

A small dev-time utility may fetch additional **public** COLA records to enlarge the corpus (public
data; not a runtime dependency — respects Marcus's firewall note).

---

## 9. Scope

**In scope (core):** F1, F2, F3, F4, F6 (basic), F7; N1–N6.
**In scope (high-value extras, stakeholder-requested / beneficial):** F5 batch, proof↔ABV
cross-check, beverage-type rules, brand∪fanciful & DBA semantics, real+adversarial test corpus,
Section 508, processing-time badge.
**Out of scope:** COLA system integration; persistent storage / audit DB; auth/SSO; type-size /
CPI / contrast certification (explicitly outside TTB's own COLA review — offered as advisory only);
production FedRAMP hardening (documented as the production path, not built).

---

## 10. Build order

1. **ColaParser + extraction contract** (claimed fields from form layer; images out; vision JSON schema).
2. **MatchEngine + RulesEngine** with the §4 semantics + **unit tests** (pure).
3. **Single-record UI** — both input modes (COLA-record upload + manual-entry form & image) →
   color-coded report + processing-time badge, accessible by construction.
4. **Batch UI** (results table + export).
5. **Real + adversarial test corpus**, low-quality-image handling, Section 508 pass.
6. **Deploy + README + approach/assumptions doc.**

---

## 11. Assumptions

1. Two co-equal input modes feed one engine: (a) a COLA record (claimed values + label images
   travel as one document — the at-scale path, no typing); (b) manual entry of claimed fields +
   image upload (the demo / ad-hoc / PRD-sample path). Both reduce to the same logical input.
2. Form-field *labels* (BRAND NAME, NET CONTENTS, …) are stable across form versions even though
   field *numbers* differ; the parser keys on labels, with an LLM fallback for odd layouts.
3. For the prototype demo, outbound access to the chosen vision provider is available; the swappable
   interface + documented Azure/local-OCR path covers the firewalled production reality.
4. Type-size / contrast / bold are best-effort advisories, explicitly outside TTB's COLA review
   scope (per the records' own qualification text); exact text + capitalization are checked reliably.
5. Class/Type DESCRIPTION is a TTB internal classification and is not expected to match the label
   verbatim; it is checked for semantic consistency only.
6. No real PII is persisted; the public COLA records used are already public.
