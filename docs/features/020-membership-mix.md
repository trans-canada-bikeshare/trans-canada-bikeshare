# Spec 020 — Membership mix

## Status

**Not built.** Planned, as a two-city comparison.

## Context

Spec 001 established that Montreal carries `is_member` until the 2022 format
break and loses it after. The registry already marks `membership_mix` as
`comparable: false` with `mtl-bixi` unsupported.

## Intended scope

- **Sources:** none new.
- **Cities:** Vancouver and Toronto as a comparison; Montreal labelled "not
  published", the same treatment [spec 019](019-ebike-share.md) gives e-bike
  share.
- **Published artifacts change:** yes — a membership series.

## Intended changes

1. Member versus casual per system per month.
2. Raw labels mapped explicitly through a committed mapping. `dim_membership`
   already exists with 93 mapped values and zero unmapped; an unmapped label
   must stop the pipeline, not default to a bucket.
3. Montreal's partial coverage stated on the chart — it has the field for part
   of its range, which is a third case beyond "supported" and "not supported"
   and needs its own labelling.

## Depends On

Nothing outstanding. `dim_membership` shipped with spec 008.
