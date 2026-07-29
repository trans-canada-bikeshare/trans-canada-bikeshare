# Spec 002 — Repo scaffold and design system port

## Status

Draft — do not start before 001 completes. Nothing here depends on 001's
findings, but 001 is cheap and may change what the pipeline needs to parse.

## Context

The repo is currently a README, a licence, and docs. Everything in phases 1
through 8 needs somewhere to live. This spec builds the two halves — an offline
Python pipeline and a static React site — and ports the Vancouver project's
design language so no later spec has to invent visual decisions.

The design language is settled and measured: it came from adnanreza.com into
the Vancouver project in its spec 038, and this project inherits it verbatim.
Quiet-editorial — cool paper and near-black ink, hairline rules instead of cards
and shadows, Inter Tight for display and body, JetBrains Mono for uppercase
micro-labels, one restrained blue reserved for links and data marks. Porting the
tokens now means every later component has a correct default.

## Depends On

- Spec 001 — sequencing only, not content.

## Scope

- **Sources touched:** none. No data is downloaded or read.
- **Cities touched:** none.
- **Tier:** neither.
- **Published artifacts change:** No — there are none yet. This spec creates the
  directory they will live in and the size budget that will guard it.

## Changes

1. **Python pipeline skeleton.** `pipeline/` with `common.py` (repo paths,
   SHA-256, manifest load/save, format detection by magic bytes),
   `requirements.txt` (`requests`, `openpyxl`, `duckdb`, `pytest`,
   `scikit-learn`, `numpy`), a `tests/` package with `conftest.py`, and a
   `README.md` documenting the command order as it grows. `.venv/` is already
   gitignored.
2. **Site skeleton.** Vite + React 19 + TypeScript + Tailwind, Vitest with
   jsdom and Testing Library, `tsconfig` path alias `@/`, and the standard
   `dev` / `build` / `preview` / `test` / `typecheck` scripts.
3. **Design tokens — `src/index.css`.** Port the `:root` and `.dark` blocks
   verbatim from the Vancouver project: paper `#f7f9fb` / `#0b0b0b`, ink
   `#090e11` / `#ededed`, paper-2, ink-2, muted, muted-2, rule, rule-2, accent
   `#196ea9` / `#5fa5de`, accent-ink. Stored as HSL triplets behind the
   `hsl(var(--x))` plumbing, with the hex kept in a comment as the source of
   truth. `color-scheme` set per theme.
4. **Tailwind theme.** Inter Tight and JetBrains Mono via `@fontsource-variable`,
   latin subsets only. Base font size 17px. Container max-width 1240px with the
   `clamp(24px, 4.5vw, 56px)` gutter. `fade-up 650ms cubic-bezier(.22,.61,.36,1)`
   with `both` fill. `darkMode: ["class"]`.
5. **Base layer.** The `.eyebrow` utility (mono, 11px, uppercase, tracking
   .14em, muted). Focus treatment `outline: 2px solid ink; outline-offset: 3px`.
   `font-feature-settings` with `tnum` on for tabular data.
   `prefers-reduced-motion` gating on scroll behaviour and reveals.
6. **Theme plumbing.** `ThemeProvider` / `useTheme` reading `localStorage`
   then `prefers-color-scheme`, toggling `dark` on `<html>`, plus the inline
   pre-hydration script in `index.html` that applies the class before first
   paint so there is no flash.
7. **`Makefile`** with the gate targets the workflow expects, each currently a
   stub that exits 0 with a message saying what it will check once its spec
   lands: `check-artifacts` (spec 011), `check-manifest` (003), `check-metrics`
   (009). Wiring them now means `/feature review` has real commands to run from
   the first data spec onward, rather than prose to self-attest against.
8. **`src/data/generated/.gitkeep`** and the size budget constant that spec 014
   will enforce.

## Acceptance Criteria

- [ ] `.venv/bin/python -m pytest pipeline/tests` runs and passes with zero
      tests collected failing — the harness works even though there is nothing
      to test yet
- [ ] `npm test`, `npm run typecheck`, and `npm run build` all exit 0
- [ ] `npm run dev` serves a page that renders the project name, a mono eyebrow,
      and a hairline rule, in the ported type and colour
- [ ] Toggling the theme flips light to dark, persists across a reload, and
      applies the correct class before first paint on a stored-dark hard reload
- [ ] A first visit with no stored preference follows `prefers-color-scheme`
- [ ] Both variable fonts are active at runtime, confirmed via
      `document.fonts.check`
- [ ] Every design token in `src/index.css` matches the Vancouver project's
      value exactly — verified by diffing the two `:root` and `.dark` blocks
- [ ] `make check-artifacts`, `make check-manifest`, and `make check-metrics`
      each exit 0 and print which spec will make them real
- [ ] No shadow utilities and no filled buttons anywhere in the scaffold
- [ ] Zero horizontal overflow at 320px in both themes

## Data Integrity Checklist

- ~~Manifest entry with checksum~~ — n/a, no source files are read
- ~~Schema drift mapped~~ — n/a, no extraction yet
- ~~Row accounting~~ — n/a, no ETL yet
- ~~Metrics defined identically~~ — n/a, no metrics yet
- ~~Artifacts reproduce~~ — n/a, no artifacts yet; this spec creates the empty
  directory and the stub gate that will guard them
- ~~Copy derives from the data window~~ — n/a, no data-derived copy yet
- [ ] Encodings explained — n/a for the scaffold, but the `.eyebrow` and
      hairline conventions are documented in the spec so later specs inherit
      them rather than reinventing
- ~~Attribution~~ — n/a, no data shipped
- [ ] No raw data committed — nothing is downloaded

## Testing

- Vitest: one smoke test that the app renders and the theme provider toggles.
- pytest: one smoke test that `common.sha256_file` matches a known digest and
  that `detect_format` classifies xlsx, csv, and html correctly from magic
  bytes. These two helpers are load-bearing for spec 003 and cheap to pin now.
- Manual: the 320px and theme-toggle checks in the acceptance criteria.

## Out of Scope

- Any component beyond what the smoke test needs — nav, scrollspy, and sections
  are spec 015
- Any downloading, parsing, or warehouse code — specs 003 onward
- Deployment configuration — spec 027
- Chart theming — comes with the first chart, in phase 6

## Rollback

Single revert of the merge commit. Nothing depends on this spec until 003
starts, and no data or artifacts exist to become inconsistent.
