import { Suspense, lazy, useMemo } from "react";
import { setTheme, useTheme } from "@/lib/theme";
import { Section, Note } from "@/components/Section";
import { StatGrid } from "@/components/StatGrid";
import { LineChart, type Series } from "@/components/charts/LineChart";
import { SmallMultiples } from "@/components/charts/SmallMultiples";

// Lazy so MapLibre and its stylesheet stay out of the initial bundle. The
// library alone is roughly four times the size of the rest of the site.
const StationMap = lazy(() =>
  import("@/components/StationMap").then((m) => ({ default: m.StationMap })),
);
import { FLOW_STOPS, FLOW_DOMAIN } from "@/lib/flowScale";
import { SYSTEM_ORDER, SYSTEMS, seriesColor, cityOf } from "@/lib/systems";
import { compact, full, percent, duration, longDate, MONTH_SHORT, monthLabel } from "@/lib/format";
import {
  meta, tripsMonthly, seasonality, stationsYearly, ebikeShare, durations,
  exclusions, incompleteMonths, monthIndex, monthKeyFromIndex, commonWindow,
  stationsMeta, omittedFor, flows, flowsFor, concentration,
} from "@/lib/data";

const NAV = [
  ["overview", "Overview"],
  ["trips", "Trips"],
  ["seasons", "Seasons"],
  ["stations", "Stations"],
  ["ebikes", "E-bikes"],
  ["maps", "Maps"],
  ["flows", "Flows"],
  ["method", "Method"],
] as const;

export default function App() {
  const theme = useTheme();
  const window = commonWindow();

  const tripSeries: Series[] = useMemo(
    () =>
      SYSTEM_ORDER.map((id) => ({
        id,
        label: SYSTEMS[id].city,
        color: seriesColor(id),
        points: tripsMonthly
          .filter((r) => r.system_id === id)
          .map((r) => ({ x: monthIndex(r.month), y: r.trips })),
      })),
    [],
  );

  const seasonSeries: Series[] = useMemo(
    () =>
      SYSTEM_ORDER.map((id) => ({
        id,
        label: SYSTEMS[id].city,
        color: seriesColor(id),
        points: (() => {
          const rows = seasonality.series.filter((r) => r.system_id === id);
          // Share of that system's own year. Absolute means put Vancouver on
          // the floor and hid the shape, which is the whole point here.
          const total = rows.reduce((n, r) => n + r.mean_trips, 0) || 1;
          return rows.map((r) => ({
            x: r.month_of_year,
            y: (100 * r.mean_trips) / total,
          }));
        })(),
      })),
    [],
  );

  const stationSeries: Series[] = useMemo(
    () =>
      SYSTEM_ORDER.map((id) => ({
        id,
        label: SYSTEMS[id].city,
        color: seriesColor(id),
        points: stationsYearly
          .filter((r) => r.system_id === id)
          .map((r) => ({ x: r.year, y: r.stations })),
      })),
    [],
  );

  const ebikeSeries: Series[] = useMemo(() => {
    const ids = [...new Set(ebikeShare.series.map((r) => r.system_id))];
    return SYSTEM_ORDER.filter((id) => ids.includes(id)).map((id) => ({
      id,
      label: SYSTEMS[id].city,
      color: seriesColor(id),
      points: ebikeShare.series
        .filter((r) => r.system_id === id && r.classified_trips > 0)
        .map((r) => ({ x: monthIndex(r.month), y: (100 * r.ebike_trips) / r.classified_trips })),
    }));
  }, []);

  const totalTrips = meta.systems.reduce((n, s) => n + s.trips, 0);
  // Derived, so the sentence cannot rot when the data updates.
  const peaks = SYSTEM_ORDER.map((id) =>
    Math.max(0, ...tripsMonthly.filter((r) => r.system_id === id).map((r) => r.trips)),
  ).filter((n) => n > 0);
  const scaleRatio = Math.round(Math.max(...peaks) / Math.min(...peaks));

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-border bg-background/85 backdrop-blur">
        <div className="container flex h-14 items-center justify-between gap-4">
          <a href="#top" className="flex shrink-0 items-center gap-2.5">
            <img src="/logo.svg" alt="" aria-hidden="true" width={44} height={18} />
            <span className="text-[15px] font-medium tracking-[-0.01em]">
              Trans-Canada Bikeshare
            </span>
          </a>
          {/* lg, not md: at 768px the seven links plus the wordmark push the
              theme toggle past the viewport edge. Adding "Flows" as a seventh
              item is what tipped it over. */}
          <nav className="hidden items-center gap-5 lg:flex" aria-label="Sections">
            {NAV.map(([id, label]) => (
              <a
                key={id}
                href={`#${id}`}
                className="text-[14px] text-muted-foreground transition-colors hover:text-foreground"
              >
                {label}
              </a>
            ))}
          </nav>
          <button
            type="button"
            className="eyebrow shrink-0 border-b border-muted-2 pb-0.5 transition-colors hover:border-foreground hover:text-foreground"
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            aria-pressed={theme === "dark"}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? "Light" : "Dark"}
          </button>
        </div>
      </header>

      <main id="top" className="container pb-24">
        <div className="pt-20 md:pt-28">
          <p className="eyebrow">Canada · three systems · one method</p>
          <h1 className="mt-6 max-w-4xl text-[clamp(40px,7vw,92px)] font-medium leading-[0.95] tracking-[-0.024em]">
            Canada's bike share systems, measured the same way.
          </h1>
          <p className="mt-8 max-w-2xl text-base leading-relaxed text-muted-foreground">
            {full(totalTrips)} trips from Vancouver, Montreal and Toronto, computed
            from each system's published open data through one pipeline, with one
            set of definitions — and with every place they cannot be compared
            said out loud.
          </p>
        </div>

        <div className="mt-20 space-y-16 md:space-y-20">
          <Section
            id="overview"
            eyebrow="Overview"
            title="Three systems, side by side"
            lede={
              <>
                Each system covers a different span, and the charts below show
                each one's full range rather than cropping it. All three publish
                from {meta.common_window_first_year} onward — {longDate(window.first)}{" "}
                to {longDate(window.last)} — which is the window the seasonality
                comparison uses, and the only stretch where a three-way
                like-for-like reading is available.
              </>
            }
          >
            <StatGrid
              stats={meta.systems
                .slice()
                .sort(
                  (a, b) =>
                    SYSTEM_ORDER.indexOf(a.system_id) - SYSTEM_ORDER.indexOf(b.system_id),
                )
                .map((s) => ({
                  label: s.city,
                  value: compact(s.trips),
                  accent: seriesColor(s.system_id),
                  detail: (
                    <>
                      {s.system} · {full(s.active_stations)} active stations
                      <br />
                      {s.first_trip.slice(0, 7)} to {s.last_trip.slice(0, 7)}
                    </>
                  ),
                }))}
            />
            <div className="mt-12">
              <StatGrid
                stats={durations
                  .slice()
                  .sort(
                    (a, b) =>
                      SYSTEM_ORDER.indexOf(a.system_id) - SYSTEM_ORDER.indexOf(b.system_id),
                  )
                  .map((d) => ({
                    label: `${cityOf(d.system_id)} · median trip`,
                    value: duration(d.median_s),
                    accent: seriesColor(d.system_id),
                    detail: `middle half ${duration(d.p25_s)} to ${duration(d.p75_s)}`,
                  }))}
              />
            </div>
            {incompleteMonths.length > 0 && (
              <Note>
                {incompleteMonths.length} partial month
                {incompleteMonths.length === 1 ? " is" : "s are"} excluded from
                every chart — months the sources have not finished publishing, and{" "}
                {"van-mobi 2022-10"}, whose file fails to download. Listing them
                rather than plotting them keeps a three-day stub from reading as a
                collapse.
              </Note>
            )}
            <Note>
              Durations exclude trips with no recorded end, and trips whose
              duration is zero, negative, or over 24 hours. Those are real
              departures and are counted in the trip totals above, but a duration
              cannot be computed without an ending.
            </Note>
          </Section>

          <Section
            id="trips"
            eyebrow="Trips"
            title="Every month each system has published"
            lede={
              <>
                Monthly trip counts, on the same definition for all three: a
                departure with a parseable time and a resolvable station. Gaps
                are gaps — a line breaks where a system published nothing.{" "}
                <strong className="font-medium text-foreground">
                  Each panel is scaled to itself
                </strong>
                , because Montreal runs roughly {scaleRatio}× Vancouver's monthly
                volume and a shared axis flattens the smaller systems into the
                baseline. The absolute figures are in the overview above.
              </>
            }
          >
            <SmallMultiples
              series={tripSeries}
              // Axis ticks want the year; the hover readout must name the
              // month, or a monthly value reads as an annual one.
              xLabel={(x) => monthLabel(monthKeyFromIndex(Math.round(x)))}
              xTicks={8}
              caption="Monthly trips, one panel per system, each scaled to itself"
            />
            <Note>
              Montreal's line breaks each winter through 2023 because BIXI closed
              for the season — those months were never published, which is why
              the line breaks rather than dropping to zero.{" "}
              <strong className="font-medium text-foreground">
                BIXI has run year-round since December 2023
              </strong>
              , so recent winters are low but continuous.
            </Note>
          </Section>

          <Section
            id="seasons"
            eyebrow="Seasons"
            title="The shape of a Canadian riding year"
            lede={`Each month's share of that system's own year, across ${seasonality.first_year} onward and averaging whole months only. Plotted as shares rather than counts so the three shapes can actually be compared — in absolute terms Vancouver sits on the floor and its seasonality is invisible.`}
          >
            <LineChart
              series={seasonSeries}
              xLabel={(x) => MONTH_SHORT[Math.max(0, Math.min(11, Math.round(x) - 1))]}
              yLabel={(y) => `${y.toFixed(0)}%`}
              xTicks={12}
              caption="Each month's share of the system's own year"
            />
          </Section>

          <Section
            id="stations"
            eyebrow="Stations"
            title="Networks, growing at different rates"
            lede="Distinct stations seen in each year's trips. Active counts in the overview use each system's own most recent six months, not a shared cutoff — that would penalise whichever system publishes least often."
          >
            <LineChart
              series={stationSeries}
              xLabel={(x) => String(Math.round(x))}
              yLabel={(y) => String(Math.round(y))}
              caption="Distinct stations seen per year"
            />
          </Section>

          <Section
            id="ebikes"
            eyebrow="E-bikes"
            title="Two cities, because only two publish it"
            lede="Share of trips taken on an electric bike, monthly. This is not a three-city comparison and is not presented as one."
          >
            <LineChart
              series={ebikeSeries}
              xLabel={(x) => monthLabel(monthKeyFromIndex(Math.round(x)))}
              yLabel={(y) => `${Math.round(y)}%`}
              caption="Share of trips on an electric bike"
            />
            {Object.entries(ebikeShare.unsupported).map(([id, info]) => (
              <Note key={id}>
                <strong className="font-medium text-foreground">
                  {cityOf(id)} — {info.display ?? "not published"}.
                </strong>{" "}
                {info.reason}
              </Note>
            ))}
          </Section>

          <Section
            id="maps"
            eyebrow="Maps"
            title="Three networks, three shapes"
            lede={
              <>
                Every station with a position and at least{" "}
                {stationsMeta.min_lifetime_events} lifetime events — a departure
                or a return, so a round trip counts twice. Counting stations
                says nothing about a network's shape: Montreal's is dense and
                radial, Toronto's runs along the lake and up the subway lines,
                Vancouver's is the most concentrated of the three — dense on
                the downtown peninsula and thinning outward from it. Dot size
                is lifetime events on{" "}
                <strong className="font-medium text-foreground">
                  one scale shared by all three maps
                </strong>
                , so a dot means the same thing in each. Hollow dots are
                dormant — no trips in the last six months of that system's own
                data, which is not the same as decommissioned.
              </>
            }
          >
            <div className="grid gap-10 lg:grid-cols-3">
              {SYSTEM_ORDER.map((id) => (
                <Suspense
                  key={id}
                  fallback={
                    <div className="h-[300px] border border-border md:h-[380px]" />
                  }
                >
                  <StationMap system={id} theme={theme} />
                </Suspense>
              ))}
            </div>
            <Note>
              {SYSTEM_ORDER.map((id) => {
                const o = omittedFor(id);
                if (!o || (o.no_coordinates === 0 && o.below_threshold === 0)) return null;
                return (
                  <span key={id} className="mr-4 inline-block">
                    <strong className="font-medium text-foreground">{cityOf(id)}</strong>{" "}
                    omits {full(o.no_coordinates)} station
                    {o.no_coordinates === 1 ? "" : "s"} with no known position
                    {o.below_threshold > 0 && <> and {full(o.below_threshold)} below the trip threshold</>}.
                  </span>
                );
              })}{" "}
              A station without coordinates is left off the map and counted here
              rather than placed at a guess. Most are dormant identities the
              current live feed no longer lists; the rest are identities that
              could not be matched to it, which is why a few recently used
              stations are missing too.{" "}
              <strong className="font-medium text-foreground">
                BIXI is also not only Montreal
              </strong>{" "}
              — it runs stations in Sherbrooke and several South Shore towns,
              about 0.1% of its positioned activity. This site labels the system
              by its home city, which is how BIXI brands it. Those outliers are
              drawn but sit outside the opening frame, which is fitted to each
              network's core so its shape stays legible; pan east to reach them.
            </Note>
          </Section>

          <Section
            id="flows"
            eyebrow="Flows"
            title="Where the bikes pile up, and where they run out"
            lede={
              <>
                A station's net flow is what it takes in minus what it gives
                out, as a share of everything that touched it — so a dock with
                20,000 events and one with 900,000 are read on the same scale.
                Dot size is lifetime events, on the same shared scale as the
                maps above; colour is net flow.{" "}
                <strong className="font-medium text-foreground">
                  Amber gives out more bikes than it takes in; indigo takes in
                  more.
                </strong>{" "}
                Colour saturates at 15% in either direction, so a fully
                saturated dot means <em>at least</em> that imbalanced — the
                great majority of stations sit well inside it, and stretching
                the scale to the few that do not would flatten everything else
                to grey. Only trips with both ends recorded are counted, so
                across every station in a system the flows cancel to zero —
                though not across the dots drawn here, because the stations
                these maps cannot place hold the remainder.
              </>
            }
          >
            {/* The scale is described in the lede, but a reader scanning the
                maps needs the swatch beside them, not a paragraph above. */}
            <div className="mb-6 flex flex-wrap items-center gap-x-3 gap-y-2 text-[12px] text-muted-foreground">
              <span className="font-mono tabular-nums">−15%</span>
              <span
                aria-hidden="true"
                className="h-2 w-40 max-w-[45vw]"
                style={{
                  // Positioned by the map's OWN domain, not spaced evenly.
                  // Five unpositioned CSS stops sit at 0/25/50/75/100%, which
                  // put the -4% stop where the scale means -7.5% — a 1.9x
                  // overstatement across the middle, in the one element built
                  // for decoding the colour.
                  background: `linear-gradient(to right, ${FLOW_DOMAIN.map(
                    (d, i) =>
                      `${FLOW_STOPS[theme][i]} ${((100 * (d - FLOW_DOMAIN[0])) /
                        (FLOW_DOMAIN[FLOW_DOMAIN.length - 1] - FLOW_DOMAIN[0])).toFixed(1)}%`,
                  ).join(", ")})`,
                }}
              />
              <span className="font-mono tabular-nums">+15%</span>
              <span>
                gives out more <span aria-hidden="true">→</span> takes in more
                <span className="sr-only">
                  , from amber at minus fifteen percent through neutral grey to
                  indigo at plus fifteen percent
                </span>
              </span>
            </div>

            <div className="grid gap-10 lg:grid-cols-3">
              {SYSTEM_ORDER.map((id) => (
                <Suspense
                  key={id}
                  fallback={
                    <div className="h-[300px] border border-border md:h-[380px]" />
                  }
                >
                  <StationMap system={id} theme={theme} mode="flow" />
                </Suspense>
              ))}
            </div>

            <div className="mt-12 grid gap-8 lg:grid-cols-3">
              {SYSTEM_ORDER.map((id) => {
                const f = flowsFor(id);
                if (!f) return null;
                const pairs = flows.pairs.filter((p) => p.s === id);
                return (
                  <div key={id}>
                    <p className="eyebrow flex items-center gap-1.5">
                      <span
                        aria-hidden="true"
                        className="inline-block h-2 w-2 shrink-0"
                        style={{ backgroundColor: seriesColor(id) }}
                      />
                      {cityOf(id)} · busiest pairs
                    </p>
                    <ul className="mt-3 space-y-1.5">
                      {pairs.map((p, i) => (
                        <li key={i} className="text-[13px] leading-snug">
                          <span className="font-mono tabular-nums text-muted-foreground">
                            {compact(p.n)}
                          </span>{" "}
                          {p.r ? (
                            <>
                              <span className="text-foreground">{p.a}</span>{" "}
                              <span className="text-muted-foreground">
                                and back
                              </span>
                            </>
                          ) : (
                            <>
                              <span className="text-foreground">{p.a}</span>{" "}
                              <span className="text-muted-foreground">→</span>{" "}
                              <span className="text-foreground">{p.b}</span>
                            </>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>

            <Note>
              <strong className="font-medium text-foreground">
                The single busiest pair in every system is a loop
              </strong>{" "}
              —{" "}
              {SYSTEM_ORDER.map((id, i) => {
                const top = flows.pairs.find((x) => x.s === id);
                return (
                  <span key={id}>
                    {i > 0 ? ", " : ""}
                    {top?.a}
                  </span>
                );
              })}{" "}
              — a bike taken out and brought back to the same dock. Loops among
              each city&rsquo;s busiest pairs:{" "}
              {SYSTEM_ORDER.map((id, i) => {
                const p = flows.pairs.filter((x) => x.s === id);
                const loops = p.filter((x) => x.r).length;
                return (
                  <span key={id}>
                    {i > 0 ? ", " : ""}
                    {loops} of {cityOf(id)}&rsquo;s {p.length}
                  </span>
                );
              })}
              . What differs is where the rest go: all{" "}
              {flows.pairs.filter((x) => x.s === "mtl-bixi" && !x.r).length} of
              Montreal&rsquo;s non-loop pairs run to or from a Métro station,
              while Vancouver&rsquo;s stay inside Stanley Park and
              Toronto&rsquo;s single one crosses between ferry docks. Round
              trips are{" "}
              {SYSTEM_ORDER.map((id, i) => {
                const f = flowsFor(id);
                if (!f) return null;
                return (
                  <span key={id}>
                    {i > 0 ? ", " : ""}
                    {percent(f.round_trips / f.trips, 1)} of {cityOf(id)}
                    &rsquo;s trips
                  </span>
                );
              })}
              . They cancel in net flow, because they are a departure and a
              return at the same dock.{" "}
              <strong className="font-medium text-foreground">
                A top-N list is not a comparison.
              </strong>{" "}
              The 1,000 busiest pairs carry{" "}
              {SYSTEM_ORDER.map((id, i) => (
                <span key={id}>
                  {i > 0 ? ", " : ""}
                  {percent(concentration(id, 1000) ?? 0, 1)} in {cityOf(id)}
                </span>
              ))}
              , so the same &ldquo;top 1,000&rdquo; describes much of one
              network and a sliver of another. That concentration is the
              comparable figure; the lists above are per-city detail.{" "}
              {SYSTEM_ORDER.map((id, i) => {
                const f = flowsFor(id);
                if (!f) return null;
                return (
                  <span key={id}>
                    {i > 0 ? " " : ""}
                    {cityOf(id)} has {full(f.pairs_total)} distinct pairs;
                    the {flows.top_pairs_shown} shown carry{" "}
                    {percent(f.shown_trips / f.linked_trips, 2)} of its linked
                    trips. {full(f.no_return_station)} trips have no recorded
                    return station: they are excluded from the pairs and from
                    net flow, but their departure still counts toward the
                    station&rsquo;s lifetime events, so it is in the dot size.
                  </span>
                );
              })}
            </Note>
          </Section>

          <Section
            id="method"
            eyebrow="Method"
            title="What was dropped, and what rests on a weaker claim"
            lede="Every row this pipeline drops or flags is accounted for. The full generated report lives in the repository; these are the two figures that qualify what you have just read."
          >
            <StatGrid
              stats={exclusions
                .slice()
                .sort(
                  (a, b) =>
                    SYSTEM_ORDER.indexOf(a.system_id) - SYSTEM_ORDER.indexOf(b.system_id),
                )
                .map((e) => ({
                  label: `${cityOf(e.system_id)} · station matched by name`,
                  value: percent(e.station_matched_by_name / e.total, 1),
                  accent: seriesColor(e.system_id),
                  detail: `${full(e.unterminated)} trips with no recorded end`,
                }))}
            />
            <Note>
              A station resolved by name is a weaker claim than one resolved by a
              published id. Montreal's share is high because BIXI stopped
              publishing station identifiers entirely in 2022 — from then on only
              the station name is available.
            </Note>
            <Note>
              Sources: Mobi by Rogers, BIXI Montréal, and Bike Share Toronto open
              data. Contains information licensed under the Open Government
              Licence – Toronto. BIXI's open data page states no licence terms;
              that is unresolved and recorded as such in the repository. Daily
              climate data is{" "}
              <strong className="font-medium text-foreground">
                based on Environment and Climate Change Canada data
              </strong>
              , used under a licence whose redistribution restrictions are
              recorded in the repository.
            </Note>
          </Section>
        </div>
      </main>

      <footer className="border-t border-border">
        <div className="container flex flex-col gap-2 py-8 text-[13px] text-muted-foreground">
          <p>
            Data generated {longDate(meta.generated_at)}. Built by Adnan Reza.
            Sister project to Mobi Transit Explorer.
          </p>
          <p>Not affiliated with or endorsed by the Government of Canada.</p>
        </div>
      </footer>
    </div>
  );
}
