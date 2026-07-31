# Security policy

## Reporting a vulnerability

Report privately, through GitHub's **private vulnerability reporting**:

> [Report a vulnerability](https://github.com/trans-canada-bikeshare/trans-canada-bikeshare/security/advisories/new)
> — repository **Security** tab → **Report a vulnerability**.

That channel is private between you and the maintainer, is the only reporting
channel this project offers, and exists so a finding does not have to be
disclosed in a public issue to be received. There is no published email
address; a non-security matter that should not be public can go through
[adnanreza.com](https://adnanreza.com).

Please include what you did, what happened, and what you expected — enough for
the behaviour to be reproduced. If it is a web finding, the URL and the browser
are part of the report.

**Expect a first response within seven days.** This is a personal project with
one maintainer, so that is a realistic commitment rather than an ambitious one.
If a week passes with no answer, open a public issue saying only that a private
report is outstanding — no details.

There is **no bounty programme** and no payment of any kind. Nothing here is
conditional on that; reports are welcome regardless.

## Scope

In scope:

- **This repository** — the pipeline (`pipeline/`), the site source (`src/`),
  the workflows in `.github/`, and the pinned toolchains
  (`pipeline/requirements.lock`, `package-lock.json`). Supply-chain findings
  are in scope: a dependency this project pins to a compromised version, or a
  workflow that leaks a token.
- **The deployed site** — <https://bikeshare.adnanreza.com>. It is a static
  build on Cloudflare Pages: no server, no database, no authentication, no user
  accounts, no cookies set by this project and no data collected from visitors.
  That narrows the surface considerably, and findings in it are still in scope.

Out of scope:

- **Cloudflare's own infrastructure.** Report those to Cloudflare.
- **The source open-data portals** — Mobi, BIXI, Bike Share Toronto, ECCC. This
  project downloads their published files and has no access to their systems.
- **Automated scanner output with no demonstrated impact**, missing headers on
  a static site with no session to steal, and denial of service by volume.

## What this project treats as a security matter and you might not

A wrong number is not a vulnerability, but **a way to make this repository
publish a wrong number without the gates noticing is one.** The gates
(`make check`, the fixture pipeline, the schema and completeness contracts) are
what the published figures rest on, and a demonstrated bypass — a gate that can
be made to pass over a defect, a way to reach `src/data/generated/` outside
`publish.py` — is worth reporting through this channel.

A number you believe is simply wrong is worth even more, and it goes in the
open: use the **Data quality report** issue template, which asks for the query
you computed it with.
