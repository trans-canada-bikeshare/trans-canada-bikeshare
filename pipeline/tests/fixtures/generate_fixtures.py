"""Regenerate the synthetic fixture archive under pipeline/tests/fixtures/.

EVERY VALUE THIS WRITES IS INVENTED. No byte of it comes from BIXI, Mobi, Bike
Share Toronto or ECCC. Station names are prefixed `FIXTURE`, station ids sit
outside every real id range, coordinates are plausible-but-fake points inside
each city's bounding box, and the whole window is the single calendar year 2024.
See README.md in this directory for what that buys and what it does not.

The output is committed, so this script exists to say how the bytes were made
and to let them be remade — not to run in CI. `make check-fixture` reads the
committed files and would fail on a checksum if they had drifted from the
manifests this writes.

    .venv/bin/python pipeline/tests/fixtures/generate_fixtures.py

Determinism: one seeded `random.Random` per system, drawn in a fixed order, and
every float rounded before it is written. Re-running produces byte-identical
files on the same CPython minor version.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "archive"
MANIFESTS = HERE / "manifests"

YEAR = 2024
FIRST = date(YEAR, 1, 1)
LAST = date(YEAR, 12, 31)

# A marker every licence field carries, so nothing downstream can mistake this
# tree for acquired data. `make check-fixture` never touches the real archive,
# but a manifest is a claim about provenance and this one has to make the right
# one.
SYNTHETIC = "SYNTHETIC FIXTURE DATA — invented for testing, no source, no licence"

FIXTURE_LICENCE = {
    "name": "none — synthetic fixture",
    "url": None,
    "checked": "2026-07-31",
    "attribution": "None required. Every value was invented by "
                   "pipeline/tests/fixtures/generate_fixtures.py.",
    "note": SYNTHETIC,
}

TZ = {
    "van-mobi": ZoneInfo("America/Vancouver"),
    "mtl-bixi": ZoneInfo("America/Montreal"),
    "tor-bikeshare": ZoneInfo("America/Toronto"),
}


# --- stations ---------------------------------------------------------------
# `key` is what the trip files publish, `gbfs` is what the pinned feed calls the
# same dock. For Vancouver and Toronto they are the same string; for Montreal
# they are deliberately different, because that gap is the whole reason
# 35_bridge.sql exists — era A publishes a four-digit code, era D publishes the
# name, and only the feed carries both beside the id.

STATIONS: dict[str, list[dict]] = {
    "van-mobi": [
        {"key": "0901", "gbfs": "0901", "name": "FIXTURE Cambie & 2nd",
         "lat": 49.26805, "lon": -123.11504},
        {"key": "0902", "gbfs": "0902", "name": "FIXTURE Yaletown Roundhouse",
         "lat": 49.27448, "lon": -123.12153},
        {"key": "0903", "gbfs": "0903", "name": "FIXTURE Kits Beach Loop",
         "lat": 49.27352, "lon": -123.15402},
        {"key": "0904", "gbfs": "0904", "name": "FIXTURE Main & Terminal",
         "lat": 49.27351, "lon": -123.10011},
        {"key": "0905", "gbfs": "0905", "name": "FIXTURE Stanley Park Gate",
         "lat": 49.29352, "lon": -123.13455},
        {"key": "0906", "gbfs": "0906", "name": "FIXTURE Commercial & Broadway",
         "lat": 49.26251, "lon": -123.06903},
    ],
    "mtl-bixi": [
        {"key": "6501", "gbfs": "9101", "name": "FIXTURE Sherbrooke / Fixture",
         "lat": 45.50412, "lon": -73.57611, "borough": "FIXTURE Ville-Nord"},
        {"key": "6502", "gbfs": "9102", "name": "FIXTURE Rachel / Fixture",
         "lat": 45.52618, "lon": -73.58402, "borough": "FIXTURE Ville-Nord"},
        {"key": "6503", "gbfs": "9103", "name": "FIXTURE Peel / Fixture",
         "lat": 45.49803, "lon": -73.57221, "borough": "FIXTURE Centre-Ville"},
        {"key": "6504", "gbfs": "9104", "name": "FIXTURE Mont-Royal / Fixture",
         "lat": 45.52411, "lon": -73.59005, "borough": "FIXTURE Ville-Nord"},
        {"key": "6505", "gbfs": "9105", "name": "FIXTURE Berri / Fixture",
         "lat": 45.51502, "lon": -73.56304, "borough": "FIXTURE Centre-Ville"},
        {"key": "6506", "gbfs": "9106", "name": "FIXTURE Laurier / Fixture",
         "lat": 45.53008, "lon": -73.59902, "borough": "FIXTURE Ville-Est"},
    ],
    "tor-bikeshare": [
        {"key": "9301", "gbfs": "9301", "name": "FIXTURE Queen St W / Fixture Ave",
         "lat": 43.64712, "lon": -79.40011},
        {"key": "9302", "gbfs": "9302", "name": "FIXTURE Union Fixture Station",
         "lat": 43.64502, "lon": -79.38055},
        {"key": "9303", "gbfs": "9303", "name": "FIXTURE Bloor St W / Fixture St",
         "lat": 43.66551, "lon": -79.41003},
        {"key": "9304", "gbfs": "9304", "name": "FIXTURE College St / Fixture Rd",
         "lat": 43.65803, "lon": -79.39504},
        {"key": "9305", "gbfs": "9305", "name": "FIXTURE Harbourfront Fixture Quay",
         "lat": 43.63902, "lon": -79.38401},
        {"key": "9306", "gbfs": "9306", "name": "FIXTURE Danforth / Fixture Ave",
         "lat": 43.67704, "lon": -79.34902},
    ],
}

# Fake ECCC stations, one per city. `climate_id` is checked against the CSV by
# etl.load_weather, so the two must agree; both are invented.
WEATHER_STATION = {
    "van-mobi": {"station_id": 990001, "climate_id": "FIXTURE01",
                 "name": "FIXTURE VANCOUVER A", "lat": 49.19, "lon": -123.18,
                 "temp_base": 11.0, "temp_amp": 8.0, "snow_days": 4},
    "mtl-bixi": {"station_id": 990002, "climate_id": "FIXTURE02",
                 "name": "FIXTURE MONTREAL A", "lat": 45.47, "lon": -73.74,
                 "temp_base": 7.0, "temp_amp": 16.0, "snow_days": 10},
    "tor-bikeshare": {"station_id": 990003, "climate_id": "FIXTURE03",
                      "name": "FIXTURE TORONTO A", "lat": 43.68, "lon": -79.63,
                      "temp_base": 9.0, "temp_amp": 14.0, "snow_days": 8},
}

# Labels that exist in pipeline/mappings/membership_groups.csv. A label the map
# does not carry stops publish.py, which is the point of picking from it here
# rather than inventing one more plausible string.
MEMBERSHIP = {
    "van-mobi": ["365 Day Pass Standard", "24 Hour"],
    "tor-bikeshare": {"h1": ["Member", "Casual"],
                      "h2": ["Annual Member", "Casual Member"]},
}


def days() -> list[date]:
    return [FIRST + timedelta(days=n) for n in range((LAST - FIRST).days + 1)]


# --- weather ----------------------------------------------------------------

def weather_for(system_id: str) -> dict[date, dict]:
    """One synthetic ECCC year per city.

    Shape matters more than realism. The forecast fits ln(trips) on five weather
    features plus eleven month levels, and `forecast._ols` refuses a
    rank-deficient design — so snow has to be non-zero on SOME winter days and
    zero on others, precipitation has to vary inside a month, and the daily high
    must not be the daily low plus a constant. A tidier climate would produce a
    singular design and an abort nobody could read.
    """
    cfg = WEATHER_STATION[system_id]
    rng = random.Random(f"weather:{system_id}")
    out: dict[date, dict] = {}
    for d in days():
        doy = d.timetuple().tm_yday
        seasonal = cfg["temp_base"] + cfg["temp_amp"] * math.sin(
            2 * math.pi * (doy - 105) / 366)
        mean = round(seasonal + rng.uniform(-3.5, 3.5), 1)
        spread_hi = round(rng.uniform(2.0, 6.0), 1)
        spread_lo = round(rng.uniform(2.0, 6.0), 1)
        wet = rng.random() < 0.34
        precip = round(rng.uniform(0.2, 18.0), 1) if wet else 0.0
        cold = d.month in (1, 2, 3, 11, 12)
        snows = cold and mean < 2.0 and rng.random() < 0.45
        snow = round(rng.uniform(0.4, 14.0), 1) if snows else 0.0
        on_ground = round(rng.uniform(1.0, 22.0), 1) if (cold and rng.random() < 0.4) else 0.0
        out[d] = {
            "mean": mean,
            "max": round(mean + spread_hi, 1),
            "min": round(mean - spread_lo, 1),
            "precip": precip,
            "snow": snow,
            "ground": on_ground,
        }
    return out


ECCC_HEADER = [
    "Longitude (x)", "Latitude (y)", "Station Name", "Climate ID", "Date/Time",
    "Year", "Month", "Day", "Data Quality",
    "Max Temp (°C)", "Max Temp Flag", "Min Temp (°C)", "Min Temp Flag",
    "Mean Temp (°C)", "Mean Temp Flag",
    "Total Snow (cm)", "Total Snow Flag",
    "Total Precip (mm)", "Total Precip Flag",
    "Snow on Grnd (cm)", "Snow on Grnd Flag",
]


def write_weather(system_id: str, wx: dict[date, dict]) -> Path:
    cfg = WEATHER_STATION[system_id]
    rows = []
    for d, w in wx.items():
        rows.append([
            f"{cfg['lon']}", f"{cfg['lat']}", cfg["name"], cfg["climate_id"],
            d.isoformat(), f"{d.year}", f"{d.month:02d}", f"{d.day:02d}", "",
            f"{w['max']}", "", f"{w['min']}", "", f"{w['mean']}", "",
            f"{w['snow']}", "", f"{w['precip']}", "", f"{w['ground']}", "",
        ])
    path = ARCHIVE / system_id / "reference" / "weather_2024.csv"
    return write_csv(path, ECCC_HEADER, rows, quote_all=True)


# --- trip volume ------------------------------------------------------------

def trips_per_day(system_id: str, d: date, w: dict, rng: random.Random) -> int:
    """1 to 4 trips. Weather- and season-shaped so the model has signal.

    Every day of the year carries at least one trip on purpose: the forecast's
    reference year needs twelve months of at least twenty usable days in every
    system, and the incomplete-month rule needs the trailing month observed on
    every one of its days. A gap anywhere in December would cost the whole
    artifact.
    """
    warmth = max(0.0, min(1.0, (w["max"] + 5) / 35))
    wet_penalty = 0.75 if w["precip"] > 6 else 1.0
    weekend = 1.15 if d.weekday() >= 5 else 1.0
    expected = (0.9 + 2.6 * warmth) * wet_penalty * weekend
    n = int(round(expected + rng.uniform(-0.5, 0.5)))
    return max(1, min(4, n))


class BikeFleet:
    """Bikes that stay where they were left.

    Dwell is the interval between a bike arriving at a dock and departing from
    the SAME dock; a fleet that teleported between trips would publish a dwell
    series of zero intervals and nothing but `relocated` counts. Bikes here
    depart from wherever they last arrived, which is also what a dock sees.
    """

    def __init__(self, system_id: str, size: int, rng: random.Random):
        stations = STATIONS[system_id]
        self.ids = [f"F{n:03d}" for n in range(1, size + 1)]
        self.at = {b: stations[i % len(stations)] for i, b in enumerate(self.ids)}
        self.rng = rng
        self.cursor = 0

    def take(self) -> tuple[str, dict]:
        bike = self.ids[self.cursor % len(self.ids)]
        self.cursor += 1
        return bike, self.at[bike]

    def park(self, bike: str, station: dict) -> None:
        self.at[bike] = station


def generate_trips(system_id: str, wx: dict[date, dict], with_bikes: bool = True):
    """A year of trips for one system, ordered by departure time."""
    rng = random.Random(f"trips:{system_id}")
    stations = STATIONS[system_id]
    fleet = BikeFleet(system_id, 12, rng) if with_bikes else None
    out = []
    for d in days():
        w = wx[d]
        n = trips_per_day(system_id, d, w, rng)
        # Departure hours stay inside 06:00-21:00. Montreal's era D publishes
        # epoch milliseconds, so a departure inside a DST transition would be
        # ambiguous or non-existent in local time; keeping to daylight hours
        # means the round trip through the zone is exact.
        hours = sorted(rng.sample(range(6, 21), n))
        for h in hours:
            if fleet is not None:
                bike, origin = fleet.take()
            else:
                bike, origin = None, rng.choice(stations)
            if rng.random() < 0.12:
                dest = origin                       # round trip, same dock
            else:
                dest = rng.choice([s for s in stations if s is not origin])
            if fleet is not None:
                fleet.park(bike, dest)
            duration = rng.choice([420, 540, 660, 780, 900, 1140, 1380, 1620,
                                   1860, 2220, 2580, 3060])
            minute = rng.randrange(0, 60)
            dep = datetime(d.year, d.month, d.day, h, minute)
            out.append({
                "dep": dep,
                "ret": dep + timedelta(seconds=duration),
                "from": origin,
                "to": dest,
                "bike": bike,
                "duration": duration,
                "rng": rng.random(),
            })
    return out


# --- writers ----------------------------------------------------------------

def write_csv(path: Path, header: list[str], rows: list[list[str]],
              quote_all: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n",
                        quoting=csv.QUOTE_ALL if quote_all else csv.QUOTE_MINIMAL)
    writer.writerow(header)
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")
    return path


# Vancouver ships a new column vocabulary every couple of years. Two of the
# real variants are used verbatim, including the misspelling Mobi actually
# publishes, because `etl.plan` aborts on any header the era map does not carry
# and a fixture that used a tidied-up name would prove nothing about the map.
VAN_HEADER_A = [
    "Departure", "Return", "Departure station", "Return station", "Bike",
    "Electric bike", "Membership type", "Covered distance (m)",
    "Duration (sec.)", "Departure temperature (°C)", "Return temperature (°C)",
    "Stopover duration (sec.)", "Number of stopovers",
]
VAN_HEADER_B = [
    "Departure", "Return", "Departure station", "Return station", "Bike",
    "Electric Bike", "Memebership type", "Covered distance (m)",
    "Duration (sec.)", "Departure temperature (deg C)",
    "Return temperature (deg C)", "Lock duration (sec.)",
    "Number of bike locks",
]


def van_station_label(s: dict) -> str:
    """Mobi publishes the id as a prefix of the name and nothing else."""
    return f"{s['key']} {s['name']}"


def write_vancouver(wx, trips) -> dict[str, Path]:
    """Twelve monthly CSVs, two header eras, timestamps on the hour.

    `data-raw/van-mobi/2025-01.csv` has 62,518 rows and 24 distinct
    time-of-day strings: Mobi publishes the hour and nothing finer. The fixture
    reproduces that exactly — both timestamps land on :00 — so anything built on
    a Vancouver time-of-day keeps meeting the resolution the real source has.
    """
    by_month: dict[int, list[list[str]]] = {m: [] for m in range(1, 13)}
    rng = random.Random("van:rows")
    for t in trips:
        dep = t["dep"].replace(minute=0, second=0)
        ret = t["ret"].replace(minute=0, second=0)
        if ret < dep:
            ret = dep
        member = MEMBERSHIP["van-mobi"][0 if t["rng"] < 0.72 else 1]
        electric = "true" if rng.random() < 0.34 else "false"
        w = wx[t["dep"].date()]
        by_month[dep.month].append([
            dep.strftime("%Y-%m-%d %H:%M"),
            ret.strftime("%Y-%m-%d %H:%M"),
            van_station_label(t["from"]),
            van_station_label(t["to"]),
            t["bike"],
            electric,
            member,
            str(int(t["duration"] * 3.1)),
            str(t["duration"]),
            f"{w['max']}",
            f"{w['min']}",
            "0",
            "0",
        ])

    # The planted defects. One exact duplicate pair — Vancouver is the only
    # system 20_clean.sql deduplicates, so this is where the funnel's duplicate
    # reason can be made non-zero at all.
    by_month[3].append(list(by_month[3][0]))

    paths = {}
    for month in range(1, 13):
        header = VAN_HEADER_A if month <= 6 else VAN_HEADER_B
        period = f"{YEAR}-{month:02d}"
        paths[period] = write_csv(
            ARCHIVE / "van-mobi" / f"{period}.csv", header, by_month[month])
    return paths


MTL_HEADER_A = ["start_date", "end_date", "start_station_code",
                "end_station_code", "duration_sec", "is_member"]
MTL_HEADER_D = ["STARTSTATIONNAME", "STARTSTATIONARRONDISSEMENT",
                "STARTSTATIONLATITUDE", "STARTSTATIONLONGITUDE",
                "ENDSTATIONNAME", "ENDSTATIONARRONDISSEMENT",
                "ENDSTATIONLATITUDE", "ENDSTATIONLONGITUDE",
                "STARTTIMEMS", "ENDTIMEMS"]


def epoch_ms(dt: datetime, system_id: str) -> str:
    return str(int(dt.replace(tzinfo=TZ[system_id]).timestamp() * 1000))


def write_montreal(trips) -> dict[str, Path]:
    """Two files, two eras, two ways of naming the same six docks.

    Era A (January-June) is the 2014-2020 layout: four-digit station codes,
    minute-precision local text, `is_member`. Era D (July-December) is the 2022+
    layout: no key at all, the station NAME with inline coordinates, epoch
    milliseconds in UTC, and no membership field. They join only through the
    pinned GBFS feed, which carries the code as `short_name` and the name beside
    the id — which is what makes this fixture a test of 35_bridge.sql rather
    than a test of one era.
    """
    era_a, era_d = [], []
    rng = random.Random("mtl:rows")
    for t in trips:
        if t["dep"].month <= 6:
            era_a.append([
                t["dep"].strftime("%Y-%m-%d %H:%M"),
                t["ret"].strftime("%Y-%m-%d %H:%M"),
                t["from"]["key"],
                t["to"]["key"],
                str(t["duration"]),
                "1" if t["rng"] < 0.66 else "0",
            ])
        else:
            # ~1 in 60 era-D trips never records a return. BIXI's own 2022+
            # files carry these in quantity and 20_clean.sql keeps them
            # deliberately, so the fixture has to contain some or the
            # `unterminated` flag is never exercised.
            unterminated = rng.random() < 0.017
            era_d.append([
                t["from"]["name"], t["from"]["borough"],
                f"{t['from']['lat']}", f"{t['from']['lon']}",
                "" if unterminated else t["to"]["name"],
                "" if unterminated else t["to"]["borough"],
                "" if unterminated else f"{t['to']['lat']}",
                "" if unterminated else f"{t['to']['lon']}",
                epoch_ms(t["dep"], "mtl-bixi"),
                "" if unterminated else epoch_ms(t["ret"], "mtl-bixi"),
            ])

    # Planted: a departure with no station of any kind. The clean stage must
    # drop it under `rows_dropped_no_departure_station` — a row that cannot say
    # WHERE it started — and the funnel must count it there and nowhere else.
    orphan = list(era_d[10])
    orphan[0] = ""
    orphan[1] = ""
    orphan[2] = ""
    orphan[3] = ""
    era_d.append(orphan)

    return {
        f"{YEAR}-A": write_csv(ARCHIVE / "mtl-bixi" / f"{YEAR}-A.csv",
                               MTL_HEADER_A, era_a),
        f"{YEAR}-D": write_csv(ARCHIVE / "mtl-bixi" / f"{YEAR}-D.csv",
                               MTL_HEADER_D, era_d),
    }


TOR_HEADER_SNAKE = ["Trip_Id", "Trip_Duration", "Start_Station_Id", "Start_Time",
                    "Start_Station_Name", "End_Station_Id", "End_Time",
                    "End_Station_Name", "Bike_Id", "User_Type", "Bike_Model"]
# 'Trip  Duration' really does carry two spaces in the published files.
TOR_HEADER_TITLE = ["Trip Id", "Trip  Duration", "Start Station Id", "Start Time",
                    "Start Station Name", "End Station Id", "End Time",
                    "End Station Name", "Bike Id", "User Type"]


def write_toronto(trips) -> dict[str, Path]:
    """Two files: the Title_Snake era with ISO timestamps and `Bike_Model`, and
    the Title Case era with MONTH-FIRST slash dates and no e-bike signal.

    The second half is the one that matters to 15_dates.sql. Every first field
    is a month (never above 12) and second fields run past 12, so the file
    PROVES month-first from its own values and needs no declaration — which is
    the behaviour spec 029 wants a fixture to keep honest.
    """
    h1, h2 = [], []
    rng = random.Random("tor:rows")
    trip_id = 900000
    for t in trips:
        trip_id += 1
        if t["dep"].month <= 6:
            h1.append([
                str(trip_id), str(t["duration"]), t["from"]["key"],
                t["dep"].strftime("%Y-%m-%d %H:%M:%S"), t["from"]["name"],
                t["to"]["key"], t["ret"].strftime("%Y-%m-%d %H:%M:%S"),
                t["to"]["name"], t["bike"],
                MEMBERSHIP["tor-bikeshare"]["h1"][0 if t["rng"] < 0.78 else 1],
                "EFIT" if rng.random() < 0.22 else "ICONIC",
            ])
        else:
            h2.append([
                str(trip_id), str(t["duration"]), t["from"]["key"],
                t["dep"].strftime("%m/%d/%Y %H:%M"), t["from"]["name"],
                t["to"]["key"], t["ret"].strftime("%m/%d/%Y %H:%M"),
                t["to"]["name"], t["bike"],
                MEMBERSHIP["tor-bikeshare"]["h2"][0 if t["rng"] < 0.78 else 1],
            ])

    # Planted: a trip with no departure time. It has a station, so the funnel
    # must count it under `rows_dropped_no_departure_time` and not under the
    # station reason — the two are disjoint by construction and this is what
    # demonstrates it.
    timeless = list(h2[20])
    timeless[0] = str(trip_id + 1)
    timeless[3] = ""
    h2.append(timeless)

    return {
        f"{YEAR}-H1": write_csv(ARCHIVE / "tor-bikeshare" / f"{YEAR}-H1.csv",
                                TOR_HEADER_SNAKE, h1),
        f"{YEAR}-H2": write_csv(ARCHIVE / "tor-bikeshare" / f"{YEAR}-H2.csv",
                                TOR_HEADER_TITLE, h2),
    }


def write_gbfs(system_id: str) -> Path:
    """A minimal station_information feed, shaped like the real one per city.

    Mobi's feed carries no `short_name`; BIXI's does, and that field is the only
    thing that connects a 2014-era station code to a 2022-era station name. The
    fixture keeps that difference because 35_bridge.sql depends on it.
    """
    stations = []
    for s in STATIONS[system_id]:
        entry = {
            "station_id": s["gbfs"],
            "name": s["name"],
            "lat": s["lat"],
            "lon": s["lon"],
            "capacity": 16,
        }
        if system_id == "mtl-bixi":
            entry["short_name"] = s["key"]
        stations.append(entry)
    payload = {
        "last_updated": 1735689600,
        "ttl": 60,
        "version": "2.2",
        "_note": SYNTHETIC,
        "data": {"stations": stations},
    }
    path = ARCHIVE / system_id / "reference" / "gbfs_station_information.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


# --- manifests --------------------------------------------------------------

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pin(path: Path, url: str) -> dict:
    return {
        "url": url,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "content_format": "csv" if path.suffix == ".csv" else "json",
        "downloaded_at": "2026-07-31T00:00:00+00:00",
    }


def write_manifest(system_id: str, sources: dict[str, Path],
                   reference: dict[str, Path]) -> None:
    """A real manifest over fake bytes.

    Every checksum here is the true sha256 of the file beside it — `etl.py`
    aborts on an entry without one and `inventory.py` recomputes them, so a
    placeholder would fail the first gate the fixture run reaches. What is
    synthetic is the provenance, and it says so in every licence field.
    """
    entries = {}
    for period, path in sorted(sources.items()):
        entries[period] = pin(path, f"synthetic://fixture/{system_id}/{path.name}")
    ref = {}
    for name, path in sorted(reference.items()):
        entry = pin(path, f"synthetic://fixture/{system_id}/reference/{path.name}")
        entry.pop("content_format")
        ref[name] = entry

    manifest = {
        "system_id": system_id,
        "source_page": f"synthetic://fixture/{system_id}",
        "data_terms": (
            f"{SYNTHETIC}. Nothing in this tree was published by any transit "
            "agency or by Environment and Climate Change Canada; the real "
            "archive's terms are in DATA-LICENSES.md and do not reach here."
        ),
        "licence": FIXTURE_LICENCE,
        "weather_station": {**{k: v for k, v in WEATHER_STATION[system_id].items()
                               if k in ("station_id", "climate_id", "name", "lat", "lon")},
                            "licence": FIXTURE_LICENCE},
        "sources": entries,
        "reference": ref,
    }
    path = MANIFESTS / f"{system_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def main() -> int:
    written = {}
    for system_id in ("van-mobi", "mtl-bixi", "tor-bikeshare"):
        wx = weather_for(system_id)
        # Montreal publishes no bike identifier in any era, so its fixture has
        # no fleet — which is also what makes `bike_dwell` correctly refuse it.
        trips = generate_trips(system_id, wx, with_bikes=system_id != "mtl-bixi")
        if system_id == "van-mobi":
            sources = write_vancouver(wx, trips)
        elif system_id == "mtl-bixi":
            sources = write_montreal(trips)
        else:
            sources = write_toronto(trips)
        reference = {
            "gbfs_station_information": write_gbfs(system_id),
            "weather_2024": write_weather(system_id, wx),
        }
        write_manifest(system_id, sources, reference)
        rows = sum(sum(1 for _ in p.open(encoding="utf-8")) - 1
                   for p in sources.values())
        written[system_id] = (len(sources), rows)

    for system_id, (files, rows) in written.items():
        print(f"{system_id}: {files} trip file(s), {rows:,} rows")
    print(f"\narchive:   {ARCHIVE}")
    print(f"manifests: {MANIFESTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
