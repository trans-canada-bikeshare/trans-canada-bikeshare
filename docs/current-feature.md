# Current Feature: 002 Repo scaffold and design system port

## Status

Not Started

## Lifecycle

<!-- Each action stamps its own line with the date it ran. `/feature complete`
     refuses to proceed while `review` is unstamped. -->

- [x] load — 2026-07-28
- [x] start — 2026-07-28
- [x] test — 2026-07-28
- [x] review — 2026-07-28

## Goals

- `.venv/bin/python -m pytest pipeline/tests` runs and passes
- `npm test`, `npm run typecheck`, and `npm run build` all exit 0
- `npm run dev` serves a page that renders the project name, a mono eyebrow, and
  a hairline rule, in the ported type and colour
- Toggling the theme flips light to dark, persists across a reload, and applies
  the correct class before first paint on a stored-dark hard reload
- A first visit with no stored preference follows `prefers-color-scheme`
- Both variable fonts are active at runtime, confirmed via `document.fonts.check`
- Every design token in `src/index.css` matches the Vancouver project's value
  exactly — verified by diffing the two `:root` and `.dark` blocks
- `make check-artifacts`, `make check-manifest`, and `make check-metrics` each
  exit 0 and print which spec will make them real
- No shadow utilities and no filled buttons anywhere in the scaffold
- Zero horizontal overflow at 320px in both themes

## Notes

**Depends on:** spec 001 (sequencing only — nothing here uses its findings).
Complete as of `5425262`.

**Sources:** none. No data downloaded or read.

**Cities:** none. Tier: neither.

**Published artifacts change:** No — none exist. This spec creates
`src/data/generated/` and the stub gates that will guard it.

**Design language is settled, not invented here.** Tokens come verbatim from the
Vancouver project's spec 038, which measured them from adnanreza.com: paper
`#f7f9fb`/`#0b0b0b`, ink `#090e11`/`#ededed`, accent `#196ea9`/`#5fa5de`,
hairline rules instead of cards and shadows, Inter Tight + JetBrains Mono, the
mono uppercase eyebrow, `fade-up 650ms cubic-bezier(.22,.61,.36,1)`.

**Deviation from the spec as written:** spec 002 calls for a
`ThemeProvider`/`useTheme` pair. The Vancouver project actually implements theme
state with `useSyncExternalStore` reading the `dark` class off `<html>` — no
provider, no context. Porting the real implementation rather than the spec's
guess, since it is simpler and is what "same as the mobi project" means.

**Also porting** the boot skeleton from `index.html` — a dependency-free inline
skeleton that paints the theme's paper tone and hero shape from the first byte,
so a stored-dark reload never flashes white. Not in the spec text, but it is
part of the design language and costs nothing.

### Test (2026-07-28)

**32 vitest** (3 files) · **7 pytest** · `typecheck` 0 · `build` 0 · `make check` 0.
Browser-verified at 320px and 1200px in both themes:

| Criterion | Result |
| --- | --- |
| Fonts active | Inter Tight Variable + JetBrains Mono Variable both `true` |
| Eyebrow | JetBrains Mono, 11px, letter-spacing 1.54px (= 0.14em), uppercase |
| Prose size | 17px |
| Theme toggle | flips class, persists to `localStorage` |
| Pre-paint | stored-dark reload applied `dark` **before React mounted** |
| No stored preference | class matches `prefers-color-scheme` |
| Horizontal overflow @320px | none, light and dark |
| Shadows in the DOM | 0 |
| Console | clean |

**Three fixes made during test:**

1. **Build was broken and `tail` hid it.** Vitest 2.1 bundles its own Vite 5,
   which collided with the top-level Vite 6 in `vite.config.ts`'s types.
   Upgraded to vitest 3 and reinstalled; the tree now resolves one Vite.
2. **favicon 404** in the console — added `public/favicon.svg` in the design
   language and linked it.
3. **Prose inherited 16px.** Tailwind's `fontSize.base` only redefines the
   `text-base` utility; it does not restyle `body`. Prose now opts in
   explicitly for the 17px reading size.

**Deviations recorded:** `useSyncExternalStore` instead of a ThemeProvider (the
real mobi implementation); boot skeleton ported; vitest 3 rather than 2;
favicon added.

### Review (2026-07-28)

Gate items derived from Scope — no sources, no cities, no artifact change:

| Item | Verdict |
| --- | --- |
| No raw data in the diff | **pass** — no data touched; a stray `scaffold-320-dark.png` was caught and removed |
| Tier boundary intact | **pass** — `SYSTEMS` registers only the three docked systems, with a comment pointing at the v2 decision |
| Nothing guessed silently | **pass** — `detect_format` returns `unknown` rather than guessing, and is pinned by test |
| Copy derives from the data window | **⚠️ flagged, accepted** — see below |
| Provenance / row accounting / artifacts reproduce / like-for-like / encodings / attribution | n/a — no data, no ETL, no artifacts, no metrics, no visuals yet |

**⚠️ The one flag.** `App.tsx` hardcodes "open data since 2017 / 2014 / 2014".
The values are audit-verified, but the project's rule is that copy derives from
the data window, and nothing derives it yet. Accepted for the scaffold because
no pipeline exists to derive from, and marked in the source with the spec that
replaces it. **It must not survive spec 016.**

**Inherited nit, deliberately not fixed.** `--background: 210 33% 97%` renders
as `#f5f7fa`, not the `#f7f9fb` its comment claims — about two units per
channel. The triplet is byte-identical to the Vancouver project's, so the two
sites render the same. Correcting it here would break the parity that is the
actual requirement. Worth fixing in both repos together, or not at all.

**Verdict: ready to complete.**

## History

<!-- Appended by `/feature complete`, oldest first. ONE LINE per feature:
     `YYYY-MM-DD` `<sha>` — what shipped. Spec path.
     The detail lives in the merge commit; `git show <sha>` is the record.
     Keep this file cheap to load — it enters context every session. -->

- 2026-07-28 `5425262` — spec 001: source column audit across all three systems.
  E-bike share and membership mix confirmed **not** three-city comparable;
  BIXI and Toronto era maps and the BIXI station bridge established.
  `docs/features/001-source-column-audit.md` → `docs/source-audit.md`
