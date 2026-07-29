# Spec 023 — Forecast

## Status

**Not built.** Blocked on [spec 013](013-weather.md).

## Context

A ridership model per system trained on weather and calendar features, with the
out-of-range guard the Vancouver project already proved it needs — a model
asked to predict outside the conditions it was trained on should refuse, not
extrapolate.

## Intended scope

- **Sources:** ECCC weather via spec 013.
- **Cities:** all three. **Tier:** 1.
- **Published artifacts change:** yes — model coefficients and fit statistics,
  not predictions. The site computes the prediction in the browser so a reader
  can move the inputs.

## Intended changes

1. One model per system. A single pooled model would hide exactly the
   differences the project exists to show.
2. Features and their transformations stated on the page, not only in the
   methodology section.
3. An explicit refusal outside the training envelope, and a statement of what
   that envelope is.
4. Fit quality reported honestly, including where it is poor.

## Depends On

- [Spec 013](013-weather.md) — not built.
