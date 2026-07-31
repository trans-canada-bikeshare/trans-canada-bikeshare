# Spec 027 — Deploy

## Status

Complete. Deployed and verified against production 2026-07-30.

Until today this file read "**Not built, deliberately**" — the instruction for
the overnight autonomous build was to stop before deployment, so that deploying
would be a decision someone makes, not something that happened. On 2026-07-30
the owner made it: proceed, on Cloudflare Pages, at
**https://bikeshare.adnanreza.com**.

## Context

The site is a static Vite build reading committed aggregates; the pipeline,
gates, and monthly-refresh runbook all exist and pass. Deployment was blocked
on three owner decisions (`docs/runbook.md`), now resolved or accepted:

1. **BIXI licence** — decided 2026-07-28 (`docs/decisions.md`): publish
   Montreal and state plainly that the terms are unknown. Deploying makes that
   public; the recorded escape hatch stands (one publish run drops Montreal if
   terms arrive that forbid this).
2. **Trademark clearance** on the marks — the owner proceeds without a formal
   search; `docs/features/002b-brand-identity.md` records the reasoning and it
   remains not legal advice. Open item, accepted.
3. **Canonical URL** — settled 2026-07-30: `bikeshare.adnanreza.com`, chosen
   over the full project-name subdomain (long) and over a path on
   adnanreza.com (would need a proxy Worker, reintroducing metered requests).
   Future expansion, if ever, is by path (`/ca`), never a deeper subdomain —
   fourth-level names fall outside Universal SSL's wildcard.

Cloudflare Pages serves static assets unmetered on the free tier; this project
ships no Pages Functions, so the deploy consumes nothing from the owner's paid
Workers plan.

## Depends On

Every shipped spec, 001–026 — nothing new is built here. Specifically load-
bearing: 011 (artifact freshness gate), 021 (the MapLibre worker-asset and
headed-verification lessons), 025 (attribution on the site).

## Scope

- **Sources touched:** none.
- **Cities touched:** all three, published unchanged.
- **Tier:** neither — no metric changes.
- **Published artifacts change:** **No.** `src/data/generated/` is untouched.
  `index.html` gains `og:url` and `rel=canonical`; `README.md` and
  `docs/runbook.md` change from "not deployed" to the live link. The
  freshness gate still runs at complete, as always.

## Changes

1. `index.html`: add `<link rel="canonical">` and `og:url`, both
   `https://bikeshare.adnanreza.com/`. Nothing else in the head moves.
2. Create the Cloudflare Pages project `trans-canada-bikeshare` and deploy
   `dist/` from a fresh `npm run build` with `npx wrangler pages deploy`.
3. Attach the custom domain `bikeshare.adnanreza.com` to the Pages project
   (CNAME in the adnanreza.com zone; Pages provisions the certificate).
4. Verify the production URL in a **headed** browser, driven directly
   (decision 2026-07-29): all three maps draw dots, the forecast dials
   operate, attribution is visible.
5. Update the record: README status paragraph and live link, runbook deploy
   section marked executed with date and commands, spec index row 027,
   `docs/decisions.md` entry for the deploy decisions.

## Acceptance Criteria

- [x] `https://bikeshare.adnanreza.com` serves the site over HTTPS with a
      valid certificate, and the `*.pages.dev` URL serves the same build.
- [x] The served `index.html` carries `rel=canonical` and `og:url`, both
      reading `https://bikeshare.adnanreza.com/`.
- [x] Every file under `dist/assets/` and every JSON artifact, rebuilt locally
      at the deployed commit, hashes identical to the bytes served at the
      production URL.
- [x] The MapLibre worker chunk the production site requests returns
      JavaScript with HTTP 200 — not the SPA fallback serving HTML, the
      spec-021 failure, checked live by content-type and body.
- [x] An unknown path (`/no-such-page`) returns the app shell — the SPA
      fallback is active.
- [x] In a headed browser against the production URL, each station map draws
      exactly as many dots as the deployed `stations.json` holds stations
      with coordinates for that system, and the forecast dials move and
      refuse outside the envelope.
- [x] Attribution is visible on the production site: the Toronto OGL
      sentence, the ECCC acknowledgement, the BIXI unknown-terms statement,
      and the basemap's own attribution control on the maps.
- [x] The deployment contains static assets only — no Pages Functions — so
      site traffic consumes no Workers-plan quota.
- [x] `make check`, both test suites, typecheck and build are green at the
      deployed commit.
- [x] `README.md` no longer says "not yet deployed" and links the production
      URL; `docs/runbook.md`'s deploy section records the date and the exact
      commands run; the spec index marks 027 complete.

## Data Integrity Checklist

- ~~Manifest entry with checksum and licence for every new source file~~ — no
  new sources.
- ~~Schema drift mapped explicitly~~ — no pipeline changes.
- ~~Row accounting closes~~ — no pipeline changes.
- ~~Metrics defined identically across tier-1 cities~~ — no metric changes.
- [x] Committed artifacts reproduce byte-for-byte from a fresh run — and,
      new here, the *served* files match the committed build's bytes.
- [x] Site copy derives from the data window — the README/runbook edits state
      deployment facts only, no data claims.
- ~~New encodings explained~~ — no new encodings.
- [x] Source licence attribution present in manifest and on the site —
      verified on the production URL, not localhost.
- [x] No raw trip data committed — nothing in `dist/` may contain anything
      absent from `src/data/generated/`.

## Testing

The existing suites unchanged (146 vitest, 96 pytest, typecheck, build,
`make check`). New verification is live-URL: a hash comparison of local
`dist/` against served bytes, the worker-chunk content check, and the headed
browser pass — the one class of check (decision 2026-07-29) no test suite can
substitute for.

## Out of Scope

- Making the GitHub repository public — the owner flips visibility; the site
  does not depend on it.
- Analytics, Search Console, sitemap submission — later, if ever, once the
  canonical URL has been live.
- Monthly-refresh automation; the runbook stays manual by design.
- A formal trademark search — remains open, accepted by the owner.
- Performance work; the Rollup chunk-size warning on the MapLibre bundle is
  cosmetic and known.

## Rollback

No artifact changes, so rollback is small: `npx wrangler pages deployment
list` and roll back to the prior deployment (or delete the Pages project),
remove the `bikeshare` CNAME, and revert the docs commit. The site has no
server state; nothing else depends on the deployment existing.
