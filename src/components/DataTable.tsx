import { useId } from "react";

import type { Series } from "@/components/charts/LineChart";

interface Props {
  /** The very array handed to the chart above it. Not a second query, not a
   *  recomputation — the same points, printed instead of drawn. */
  series: Series[];
  /** Header for the x column: "Month", "Year", "Hour". */
  xHeader: string;
  xLabel: (x: number) => string;
  /** How a value is printed. At least as precise as the chart's own axis: the
   *  table exists to give the number, and an axis that reads "2.3M" is
   *  abbreviating the same value the artifact holds exactly. */
  yLabel: (y: number) => string;
  /** Sentence describing the table, rendered as its `<caption>`. */
  caption: string;
}

/**
 * The numbers behind a chart, as a table.
 *
 * ONE pattern, used for every chart on the site: a `<details>` disclosure whose
 * summary is a tab stop, holding a `<table>` with a visible `<caption>`, column
 * headers for the systems and a row header per x value. Chosen over a
 * visually-hidden table because the SVG charts are pointer-only — the value at a
 * given month is available by hovering and no other way — and a sighted
 * keyboard or touch reader has exactly the same problem an assistive-technology
 * reader does. A sr-only table would answer one of them and not the other.
 * (The spec-026 legends already carry each series' latest value without hover;
 * this is the rest of the series.)
 *
 * Closed by default: the tables are long, and the chart is the thing the
 * section is about. A closed `<details>` hides its contents from the accessible
 * tree as well as the screen, so this is a disclosure to open, not a table
 * that is quietly always there — which is why the summary states how many rows
 * are behind it rather than saying only "data table".
 *
 * A cell with no point is an em dash. Gaps on this site are real — a system
 * that published nothing that month, a metric a system does not support — and
 * the chart draws them as breaks rather than joining across them, so the table
 * leaves them empty rather than printing a zero nobody measured.
 */
export function SeriesTable({ series, xHeader, xLabel, yLabel, caption }: Props) {
  const xs = [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort(
    (a, b) => a - b,
  );
  const byX = series.map((s) => new Map(s.points.map((p) => [p.x, p.y])));

  const captionId = useId();

  if (xs.length === 0 || series.length === 0) return null;

  return (
    <details className="mt-6 border-t border-rule-2 pt-3">
      <summary className="eyebrow cursor-pointer select-none marker:text-muted-foreground hover:text-foreground">
        Data table · {xs.length} {xs.length === 1 ? "row" : "rows"}
      </summary>
      {/* tabIndex + region + a name: a max-height scroll container must be
          keyboard-focusable (Safari never auto-focuses scrollable divs, and
          axe flags scrollable-region-focusable as serious — found in review
          with the tables OPEN, which the first audit never exercised). */}
      <div
        className="mt-3 max-h-[22rem] overflow-auto border border-border"
        tabIndex={0}
        role="region"
        aria-labelledby={captionId}
      >
        <table className="w-full border-collapse text-[12px]">
          <caption
            id={captionId}
            className="border-b border-border px-3 py-2 text-left text-[12px] leading-snug text-muted-foreground"
          >
            {caption}
          </caption>
          <thead>
            <tr className="border-b border-border">
              <th
                scope="col"
                className="sticky top-0 bg-background px-3 py-1.5 text-left font-mono text-[11px] font-normal uppercase tracking-[0.14em] text-muted-foreground"
              >
                {xHeader}
              </th>
              {series.map((s) => (
                <th
                  key={s.id}
                  scope="col"
                  className="sticky top-0 bg-background px-3 py-1.5 text-right font-mono text-[11px] font-normal uppercase tracking-[0.14em] text-muted-foreground"
                >
                  {s.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {xs.map((x) => (
              <tr key={x} className="border-t border-rule-2">
                <th
                  scope="row"
                  className="whitespace-nowrap px-3 py-1 text-left font-mono text-[11px] font-normal tabular-nums text-muted-foreground"
                >
                  {xLabel(x)}
                </th>
                {byX.map((m, i) => {
                  const y = m.get(x);
                  return (
                    <td
                      key={series[i].id}
                      className="whitespace-nowrap px-3 py-1 text-right font-mono tabular-nums"
                    >
                      {y === undefined ? "—" : yLabel(y)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
