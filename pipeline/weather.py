"""Discover and pin ECCC daily climate data, one station per city.

Environment and Climate Change Canada serves daily climate observations from a
bulk endpoint, one request per station-year. Those years land in each city's
manifest as ordinary `reference` entries, so they inherit spec 003's checksum
pinning and drift refusal without the downloader needing to know what weather
is.

Airport stations, decided with the owner 2026-07-29: they carry the longest
continuous records and are the conventional choice. A downtown station sits
closer to the riding but has shorter and patchier coverage, and a gap here is
more damaging than a kilometre of distance — 0 °C is a legitimate, common
value, so a missing day that became a zero would be indistinguishable from an
observation.

Usage: python pipeline/weather.py [--system SYSTEM] [--accept-changes]
"""

from __future__ import annotations

import argparse
import sys

import common

# One station per city. `station_id` drives the bulk endpoint; `climate_id` is
# ECCC's stable identifier and is recorded so the station can be re-found if
# the internal id ever moves. Both were verified against a live download before
# this file was written — see docs/features/013-weather.md.
STATIONS: dict[str, dict[str, object]] = {
    "van-mobi": {
        "station_id": 51442,
        "climate_id": "1108395",
        "name": "VANCOUVER INTL A",
        "lat": 49.19,
        "lon": -123.18,
    },
    "mtl-bixi": {
        "station_id": 51157,
        "climate_id": "7025251",
        "name": "MONTREAL INTL A",
        "lat": 45.47,
        "lon": -73.74,
    },
    "tor-bikeshare": {
        "station_id": 51459,
        "climate_id": "6158731",
        "name": "TORONTO INTL A",
        "lat": 43.68,
        "lon": -79.63,
    },
}

# Read off the licence page itself, not recalled. An earlier version of this
# block named the "Environment and Climate Change Canada Data Servers End-use
# Licence" — a real instrument, but a different one: it governs MSC
# Datamart/GeoMet at eccc-msc.github.io, not climate.weather.gc.ca bulk
# historical data. That name appears nowhere on the page linked below, and the
# attribution string invented alongside it matched neither instrument.
#
# The error mattered in one direction: the licence actually in force carries
# redistribution restrictions the misnamed one does not.
LICENCE = {
    "name": "Licence Agreement for Use of Environment and Climate Change Canada Data",
    "heading": "LIMITED USE SOFTWARE AND DATA PRODUCT LICENCE AGREEMENT",
    "url": "https://climate.weather.gc.ca/prods_servs/attachment1_e.html",
    "checked": "2026-07-30",
    # Verbatim from the page: "you have the obligation to acknowledge the
    # source of the Environment and Climate Change Canada Data with the
    # following layout or something similar".
    "attribution": "based on Environment and Climate Change Canada data",
    "redistribution": (
        "Redistribution is permitted only if no fee is charged explicitly for "
        "the ECCC product, and any party it is redistributed to must agree to "
        "the same redistribution restrictions before use. Charges for "
        "value-added services are permitted."
    ),
}

BULK = (
    "https://climate.weather.gc.ca/climate_data/bulk_data_e.html"
    "?format=csv&stationID={station_id}&Year={year}&Month=1&Day=1"
    "&timeframe=2&submit=Download+Data"
)


def trip_years(manifest: dict) -> list[int]:
    """The years this city publishes trips for, from the manifest itself.

    Derived rather than listed, so a new trip year pulls its weather without
    anyone remembering to extend a literal. Toronto's earliest key is the range
    "2014-2015"; the leading four characters are the year in every format any
    system uses.
    """
    years = {int(period[:4]) for period in manifest.get("sources", {})}
    if not years:
        return []
    return list(range(min(years), max(years) + 1))


def discover(system_id: str) -> int:
    """Add a pinned reference entry per year. Does not download."""
    station = STATIONS.get(system_id)
    if station is None:
        print(f"  {system_id}: no weather station configured", file=sys.stderr)
        return 1

    manifest = common.load_manifest(system_id)
    years = trip_years(manifest)
    if not years:
        print(f"  {system_id}: no trip periods yet; run discover.py first")
        return 1

    manifest["weather_station"] = {**station, "licence": LICENCE}
    reference = manifest.setdefault("reference", {})

    # ECCC is still writing the current year, so its export gains a row every
    # day and its checksum cannot be stable. Marking it `volatile` lets
    # download.py repin it without refusing, so --accept-changes stays rare
    # and keeps its meaning for the closed years, which genuinely must not
    # move. Reproducibility holds exactly where it can: every completed year
    # is immutable and verified.
    from datetime import date
    current_year = date.today().year

    added = 0
    for year in years:
        name = f"weather_{year}"
        url = BULK.format(station_id=station["station_id"], year=year)
        entry = reference.get(name)
        volatile = year >= current_year
        if entry is None:
            # No checksum yet — download.py fills it on first fetch and
            # refuses any later change unless the year is still open.
            reference[name] = {"url": url, **({"volatile": True} if volatile else {})}
            added += 1
        elif entry.get("url") != url:
            # A changed URL for an existing year is reported, never applied
            # silently: a source that repoints under us makes the archive
            # unreproducible. Same rule as discover.py.
            print(
                f"  {system_id} {name}: URL CHANGED, not applied\n"
                f"    was {entry['url']}\n    now {url}",
                file=sys.stderr,
            )

        else:
            # A year that has closed since the last run stops being volatile
            # and becomes immutable from here on.
            if volatile:
                entry["volatile"] = True
            else:
                entry.pop("volatile", None)

    common.save_manifest(system_id, manifest)
    span = f"{years[0]}-{years[-1]}" if years else "none"
    print(f"  {system_id}: {len(years)} years ({span}), {added} newly added")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", help="one system id; default all")
    args = parser.parse_args()

    systems = [args.system] if args.system else list(STATIONS)
    failures = 0
    for system_id in systems:
        failures += discover(system_id)
    if failures:
        print(f"\n{failures} system(s) failed", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
