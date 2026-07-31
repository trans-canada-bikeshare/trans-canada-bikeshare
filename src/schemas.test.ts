/** Every committed artifact against its published contract.
 *
 * The pipeline validates each artifact before writing it, but that check runs
 * on the one machine holding the 20 GB archive. This is the same contract
 * asked of the bytes that are actually in git, by a different validator, on a
 * runner that has never downloaded a trip file — which is the only place a
 * drift between "what publish.py produced" and "what the site imports" can be
 * caught before a browser meets it.
 *
 * The schemas live in `pipeline/schemas/*.schema.json` and are read from disk
 * rather than imported, so a schema that stops being valid JSON, or an
 * artifact with no schema at all, fails here rather than being skipped
 * quietly. Ajv is configured for draft 2020-12 and for the schemas' own
 * strictness: `additionalProperties: false` and a `required` list per object,
 * so a key added, removed, renamed or retyped upstream fails.
 */

import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020";
import type { AnySchema, ValidateFunction } from "ajv";
import { describe, expect, it } from "vitest";

const here = path.dirname(fileURLToPath(import.meta.url));
const SCHEMA_DIR = path.resolve(here, "../pipeline/schemas");
const ARTIFACT_DIR = path.resolve(here, "data/generated");
const SUFFIX = ".schema.json";

function read(file: string): unknown {
  return JSON.parse(readFileSync(file, "utf-8"));
}

const schemaNames = readdirSync(SCHEMA_DIR)
  .filter((f) => f.endsWith(SUFFIX))
  .map((f) => f.slice(0, -SUFFIX.length))
  .sort();

const artifactNames = readdirSync(ARTIFACT_DIR)
  .filter((f) => f.endsWith(".json"))
  .map((f) => f.slice(0, -".json".length))
  .sort();

// One Ajv instance for the whole file: compiling a schema twice under the same
// $id is an error, and it is a useful one — two schemas claiming the same
// identity would mean one of them was never checking anything.
const ajv = new Ajv2020({ allErrors: true, strict: true });
const validators = new Map<string, ValidateFunction>();
for (const name of schemaNames) {
  const schema = read(path.join(SCHEMA_DIR, `${name}${SUFFIX}`)) as AnySchema;
  validators.set(name, ajv.compile(schema));
}

function artifact(name: string): unknown {
  return read(path.join(ARTIFACT_DIR, `${name}.json`));
}

function errorsFor(name: string, payload: unknown): string {
  const validate = validators.get(name)!;
  return validate(payload) ? "" : ajv.errorsText(validate.errors, { separator: "; " });
}

describe("artifact schemas", () => {
  it("has exactly one schema per published artifact", () => {
    // Both directions. A schema with no artifact reads as a check and is not
    // one; an artifact with no schema is the case this whole file exists for.
    expect(schemaNames).toEqual(artifactNames);
  });

  it.each(artifactNames)("%s.json matches its schema", (name) => {
    expect(validators.has(name), `no schema for ${name}`).toBe(true);
    expect(errorsFor(name, artifact(name))).toBe("");
  });
});

/** A gate nobody has watched fail is a gate nobody knows works. Each test here
 *  breaks a real committed artifact in a way a publisher change plausibly
 *  would, and asserts the schema rejects it. */
describe("planted drift", () => {
  const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

  it("rejects a renamed key", () => {
    const trips = clone(artifact("trips_monthly")) as Record<string, unknown>[];
    trips[0].trip_count = trips[0].trips;
    delete trips[0].trips;
    expect(errorsFor("trips_monthly", trips)).not.toBe("");
  });

  it("rejects an extra key the site would silently ignore", () => {
    const seasonality = clone(artifact("seasonality")) as {
      series: Record<string, unknown>[];
    };
    seasonality.series[0].experimental_mean = 1;
    expect(errorsFor("seasonality", seasonality)).not.toBe("");
  });

  it("rejects a count that became a string", () => {
    const duration = clone(artifact("duration")) as Record<string, unknown>[];
    duration[0].median_s = String(duration[0].median_s);
    expect(errorsFor("duration", duration)).not.toBe("");
  });

  it("rejects a null where a number is published", () => {
    const stations = clone(artifact("stations")) as {
      stations: Record<string, unknown>[];
    };
    stations.stations[0].f = null;
    expect(errorsFor("stations", stations)).not.toBe("");
  });

  it("rejects a month key that is not a month", () => {
    const incomplete = clone(artifact("incomplete_months")) as Record<
      string,
      unknown
    >[];
    incomplete[0].month = "2026-13";
    expect(errorsFor("incomplete_months", incomplete)).not.toBe("");
  });

  it("rejects a system id no city maps to", () => {
    const meta = clone(artifact("meta")) as { systems: Record<string, unknown>[] };
    meta.systems[0].system_id = "cal-bikeshare";
    expect(errorsFor("meta", meta)).not.toBe("");
  });

  it("rejects a forecast coefficient that is not a number", () => {
    const forecast = clone(artifact("forecast")) as {
      models: { coefficients: Record<string, unknown> }[];
    };
    forecast.models[0].coefficients.temp_max_c = "0.03";
    expect(errorsFor("forecast", forecast)).not.toBe("");
  });

  it("rejects a withheld-month basis the page has no wording for", () => {
    const membership = clone(artifact("membership")) as {
      label_lost: Record<string, unknown>[];
    };
    membership.label_lost[0].basis = "looked wrong";
    expect(errorsFor("membership", membership)).not.toBe("");
  });

  it("rejects an hour outside the day", () => {
    const rebalancing = clone(artifact("rebalancing")) as {
      hourly: Record<string, unknown>[];
    };
    rebalancing.hourly[0].hour = 24;
    expect(errorsFor("rebalancing", rebalancing)).not.toBe("");
  });

  it("rejects a dropped required key", () => {
    const flows = clone(artifact("flows")) as {
      systems: Record<string, unknown>[];
    };
    delete flows.systems[0].linked_trips;
    expect(errorsFor("flows", flows)).not.toBe("");
  });
});
