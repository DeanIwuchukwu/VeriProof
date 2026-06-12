# Accessibility — Section 508 / WCAG 2.1 AA

Section 508 of the Rehabilitation Act adopts **WCAG 2.1 Level AA** as its technical
baseline. This document records the conformance audit of the label-verification UI
and the remediation applied.

## Method
- **Automated:** axe-core (WCAG 2.0/2.1 A + AA rulesets) run against the Upload,
  Manual entry, and Batch screens in a live browser.
- **Contrast:** every text/UI color token computed against its background using the
  WCAG relative-luminance formula.
- **Manual:** code review of semantics, keyboard operation, focus management, and ARIA.

## Result
All three screens report **0 axe violations** after remediation (down from 2 / 1 / 2).

### Fixed
| Issue | Criterion | Fix |
|---|---|---|
| File inputs had no accessible name | 4.1.2 Name, Role, Value | `aria-label` on each file input |
| Secondary text below 4.5:1 (read-confidence, captions, `muted-3`) | 1.4.3 Contrast (Minimum) | darkened `faint` family + `muted-3` to ≥4.5:1 |
| FLAG / amber badge text 4.42:1 | 1.4.3 | darkened `--amber-text` to 4.61:1 |
| Form input/select border 1.5:1 | 1.4.11 Non-text Contrast | darkened to 3.15:1 |
| Preview dialogs didn't trap or restore focus | 2.4.3 Focus Order | focus-in on open, Tab cycle, restore focus to trigger on close (image + PDF lightboxes) |
| No top-level heading | 1.3.1 / 2.4.6 | page title is now `<h1>` |
| Mode tabs lacked panel association | 4.1.2 (WAI-ARIA APG) | `role="tabpanel"` + `aria-labelledby` / `aria-controls` |
| Motion not reducible | 2.3.3 (advisory) | `prefers-reduced-motion: reduce` honored |
| Icon-only "remove file" button | 4.1.2 | `aria-label` added (was `title` only) |

### Already conformant
`lang="en"`; visible `:focus-visible` outline; visually-hidden labels (`.sr-only`);
live regions (`role="status"` for the result banner, `role="alert"` for errors);
status is **never** conveyed by color alone (every badge carries PASS / FLAG / FAIL /
INFO text); form `<label>`s associated via `htmlFor` / `id`.

## Known limitations / next steps
- The field-by-field results grid is built from styled `div`s. It reads correctly in
  linear order but does not expose row/column **table semantics**; a `role="table"`
  pass (or a semantic `<table>`) would improve screen-reader navigation (1.3.1).
- The density switch (Table / Cards / Triage) uses `role="tab"` without panel
  association — cosmetic, low priority.
- The **structural screen-reader pass** is complete: the accessibility tree of all
  three screens exposes correct roles + accessible names, with an `<h1>`, landmark
  structure (banner / main / regions), and `tablist → tab[selected] → tabpanel`
  verified; every form field (including the `SOURCE` combobox) and file input carries
  a programmatic label. A final **audio listen-through** with a live screen reader
  (NVDA / VoiceOver) is recommended before formal sign-off, to confirm live-region
  announcement timing — the one check automated tooling and the a11y tree can't make.

## How to re-run the audit
- Automated: load axe-core in the running app and call
  `axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa'] } })`
  on each screen.
- Contrast: recompute token pairs with the WCAG luminance formula (4.5:1 normal text,
  3:1 large text / UI components).
