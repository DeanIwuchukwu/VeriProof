# Requirements Traceability Matrix (RTM)

Every requirement traces **backward** to its source (an interview line, a TTB regulation, the real
COLA data, or the PRD) and **forward** to the design component that implements it, the WBS task that
builds it, and the test case (TC) that proves it. This is the single auditable view of "did we
cover everything the stakeholders asked for?"

- **Source key:** `INT:<person>` = discovery interview; `CFR:<part>` = TTB regulation;
  `DATA:<ttbid|all>` = a real COLA record in `/ColaData`; `PRD` = take-home brief.
- **Status key:** `Planned` · `In progress` · `Built` · `Tested` · `Deployed`.
- Test IDs (TC-xx) are defined in [SPEC.md §8](SPEC.md). WBS IDs map to [WBS.md](WBS.md).
- Requirement IDs (F#, N#) match [SPEC.md §5–§6](SPEC.md).

---

## Functional requirements

| Req | Requirement | Source | Design component (SPEC §7) | WBS | Test (SPEC §8) | Status |
|---|---|---|---|---|---|---|
| **F1** | COLA-record ingest (input mode 1): parse claimed fields + extract label images from a 5100.31 PDF/HTML | PRD; DATA:all; INT:Marcus (no COLA integration → ingest the record itself) | ColaParser | 2.1, 2.2 | TC-01 | **Tested** (parser + /verify/cola endpoint) |
| **F2** | Manual-entry verification mode (input mode 2): text field per claimed value + label-image upload → full comparison or extract-only | PRD (Example Label Fields map 1:1); INT:Dave (spot-check/trust) | Manual-entry form, Extractor, MatchEngine | 4.3 | TC-01, TC-02, TC-05, TC-08, TC-09, TC-10, TC-13 | **Tested** (UI form + /verify/manual, browser-verified) |
| **F3** | Vision extraction → structured JSON (schema-validated), aggregated across all label images | DATA:all (front/back/capsule); PRD | VisionProvider, Extractor | 2.3, 3.1, 3.2 | TC-01, TC-07 | **Built** (provider+extractor; real-model e2e pending) |
| **F4** | Matching engine: per-field strategies (brand∪fanciful, name∪DBA, numeric ABV+proof, net-contents allowed-set, country-iff-import, strict warning, semantic class/type) + beverage-type rules | INT:Dave (judgment), INT:Jenny (strict warning); CFR:16; DATA:all | MatchEngine, RulesEngine | 3.3–3.10 | TC-02…TC-12 | **Tested** |
| **F4.1** | Brand = match label vs {brand ∪ fanciful name} | DATA:13100001000426 (Suzaku) | MatchEngine | 3.3 | TC-02 | **Tested** |
| **F4.2** | Producer = match vs {legal name ∪ approved DBA/tradename} | DATA:11364001000181 (Twelve Percent); DATA:03211001000018 | MatchEngine | 3.4 | TC-03 | **Tested** |
| **F4.3** | Class/Type = semantic/advisory consistency, never string-equality | DATA:all (internal TTB codes) | MatchEngine | 3.5 | TC-04 | **Tested** |
| **F4.4** | ABV numeric parse + tolerance + proof = 2×ABV cross-check | DATA:all; CFR:5 | MatchEngine | 3.6 | TC-08, TC-09 | **Tested** |
| **F4.5** | Net contents: unit-normalize; label value ∈ form's allowed-size set | DATA:11262001000022 (375/750/1L), DATA:11364001000181 (keg gal.) | MatchEngine | 3.7 | TC-10 | **Tested** |
| **F4.6** | Country of origin required iff Source = Imported | DATA:all (imported vs domestic) | MatchEngine, RulesEngine | 3.8 | TC-11 | **Tested** |
| **F4.7** | Government Warning: strict 27 CFR §16.21 text, `GOVERNMENT WARNING:` present + ALL-CAPS, across all images | INT:Jenny; CFR:16.21; DATA:all | MatchEngine | 3.9 | TC-05, TC-06, TC-07 | **Tested** |
| **F4.8** | Beverage-type-aware required-field rules (beer/wine/spirits/sake) | PRD (varies by type); DATA:all | RulesEngine | 3.10 | TC-12 | **Tested** |
| **F5** | Batch verification: many records, concurrent, sortable table, CSV export | INT:Sarah/Janet (200–300 at peak) | Batch endpoint, dashboard | 4.3, 5.x | TC-14 | Planned |
| **F6** | Image robustness (angle/glare/rotation/radial/multilingual); low-confidence → friendly rescan message, never false PASS | INT:Jenny; DATA:11364001000181 (radial), DATA:13100001000426 (JP) | VisionProvider, Extractor, Report UI | 3.1, 4.5 | TC-07, TC-13 | **Built** (engine low-quality guard + report notice; real-image robustness at e2e) |
| **F7** | Assistive framing: flags-for-review, confidence shown, reasoning visible, never auto-approve/reject | INT:Dave (judgment, don't make life harder) | MatchEngine output, Report UI | 3.3–3.10, 4.5 | TC-01, TC-09 | **Tested** (engine + UI: status pill, reason, read-confidence shown) |

## Non-functional requirements

| Req | Requirement | Source | Design component | WBS | Test | Status |
|---|---|---|---|---|---|---|
| **N1** | Single-record latency < 5 s end-to-end, displayed | INT:Sarah (vendor died at 30–40s) | Fast vision model, async | 3.1, 6.x | TC-15 | Planned |
| **N2** | Usability for non-technical / 73-yr-old benchmark; large targets; no hunting | INT:Sarah | Frontend UX | 4.1, 4.5 | Manual UX review | **Built** (large targets, clean 2-mode flow, browser-verified) |
| **N3** | Section 508 / WCAG 2.1 AA accessibility | Federal law; INT:Sarah | Frontend (a11y) | 4.1, 5.4 | a11y audit | **Built** (semantic HTML, ARIA tabs/live, visible focus, icon+text status; formal audit 6.7) |
| **N4** | Stateless; no persistence of records/images/PII | INT:Marcus | All backend (in-memory) | 1.3, 3.x | Code review | **Built** (in-memory; nothing written to disk/db) |
| **N5** | Network resilience: swappable provider; documented on-prem/Azure path | INT:Marcus (firewall) | VisionProvider interface | 2.3, 3.1 | Provider-swap test | **Tested** (anthropic/fake swap via env; provider-factory tests) |
| **N6** | Robust, friendly errors; no blank screens or raw stack traces | PRD (UX & error handling) | API error layer, Report UI | 3.x, 4.4, 4.5 | TC-13 | **Built** (API error layer; UI pending) |

## Scope-boundary items (explicitly NOT built — traced so reviewers see they were considered)

| Item | Decision | Rationale / source |
|---|---|---|
| COLA system integration | Out | INT:Marcus (separate auth; "years away") |
| Persistent storage / audit DB | Out | INT:Marcus (no sensitive storage for prototype) → N4 |
| Auth / SSO | Out | Prototype scope |
| Type size / CPI / contrast certification | Advisory only | DATA: records' own qualification — TTB does not review this at COLA |
| Production FedRAMP hardening | Documented, not built | INT:Marcus (18-mo paperwork) |

---

## Deliverables checklist (PRD)

| Deliverable | WBS | Status |
|---|---|---|
| Source repo on GitLab — all source | 1.1 | Planned |
| README — setup & run instructions | 6.2 | Planned |
| Approach / tools / assumptions doc | 6.3 | Planned |
| Deployed application URL | 6.1 | Planned |
| Working prototype to test | 4.x, 5.x | Planned |
| SPEC + RTM + WBS (beyond ask; completeness) | — | **Built** |

---

## Evaluation-criteria coverage (PRD)

| Criterion | Where addressed |
|---|---|
| Correctness & completeness of core | F1–F7, TC-01…TC-15 |
| Code quality & organization | §7 architecture; pure unit-tested engine; WBS 3.x |
| Appropriate technical choices for scope | Fast model (N1), swappable provider (N5), deterministic parser w/ LLM fallback |
| UX & error handling | N2, N3, N6 |
| Attention to requirements | This RTM + WBS |
| Creative problem-solving | Proof↔ABV check, brand∪fanciful & DBA semantics, real+adversarial corpus, Section 508 |
