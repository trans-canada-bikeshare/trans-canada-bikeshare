import { useId, useMemo, useState } from "react";
import { compact } from "@/lib/format";

export interface Series {
  id: string;
  label: string;
  color: string;
  /** Points may be sparse; gaps are drawn as gaps, never interpolated across. */
  points: { x: number; y: number }[];
}

interface Props {
  series: Series[];
  /** Formats an x value for ticks and the readout. */
  xLabel: (x: number) => string;
  yLabel?: (y: number) => string;
  height?: number;
  /** Roughly how many x ticks to aim for; actual count snaps to the data. */
  xTicks?: number;
  caption?: string;
  /**
   * Open the y domain below zero and draw the zero line as the axis.
   *
   * Off by default, and the default keeps the original behaviour exactly: the
   * domain runs 0..max and negative values would be clipped below the plot.
   * Every series on this site was non-negative until net flow by hour of day,
   * where the sign is the entire signal — the hours a system's docks are
   * emptying read as negative and the hours they refill read as positive, and a
   * chart that could not draw the sign would be showing the wrong quantity.
   */
  signed?: boolean;
}

const PAD = { top: 12, right: 12, bottom: 26, left: 46 };

/**
 * A hairline line chart in the house language: no gridlines, no fills, mono
 * micro-labels, one colour per series.
 *
 * Gaps are honest. A series with no point for an x renders a break rather than
 * a line drawn straight across it — on this site a missing month usually means
 * the system was closed for winter or the data was never published, and
 * interpolating would invent ridership that did not happen.
 */
export function LineChart({
  series,
  xLabel,
  yLabel = compact,
  height = 260,
  xTicks = 6,
  caption,
  signed = false,
}: Props) {
  const titleId = useId();
  const [hover, setHover] = useState<number | null>(null);
  const W = 720;
  const H = height;

  const { xs, xMin, xMax, yMax, yMin } = useMemo(() => {
    const all = series.flatMap((s) => s.points);
    const xsSet = [...new Set(all.map((p) => p.x))].sort((a, b) => a - b);
    return {
      xs: xsSet,
      xMin: xsSet[0] ?? 0,
      xMax: xsSet[xsSet.length - 1] ?? 1,
      yMax: Math.max(1, ...all.map((p) => p.y)),
      // Symmetric about zero when signed, so equal imbalance in either
      // direction is equally far from the axis. An asymmetric domain would
      // make a -0.6 look larger than a +0.6.
      yMin: signed ? -Math.max(1, ...all.map((p) => Math.abs(p.y))) : 0,
    };
  }, [series, signed]);

  const yTop = signed ? Math.max(yMax, -yMin) : yMax;
  const px = (x: number) =>
    PAD.left + ((x - xMin) / Math.max(1, xMax - xMin)) * (W - PAD.left - PAD.right);
  const py = (y: number) =>
    H - PAD.bottom - ((y - yMin) / (yTop - yMin)) * (H - PAD.top - PAD.bottom);

  // A break in `points` becomes an `M` rather than an `L`, so gaps stay gaps.
  const path = (pts: { x: number; y: number }[], step: number) => {
    const sorted = [...pts].sort((a, b) => a.x - b.x);
    let d = "";
    sorted.forEach((p, i) => {
      const prev = sorted[i - 1];
      const broken = !prev || p.x - prev.x > step * 1.5;
      d += `${broken ? "M" : "L"}${px(p.x).toFixed(1)} ${py(p.y).toFixed(1)}`;
    });
    return d;
  };

  const step = xs.length > 1 ? Math.min(...xs.slice(1).map((x, i) => x - xs[i])) : 1;
  const tickEvery = Math.max(1, Math.round(xs.length / xTicks));
  const ticks = xs.filter((_, i) => i % tickEvery === 0);
  const yTicks = signed ? [yMin, 0, yTop] : [0, yMax / 2, yMax];

  const nearest = hover === null ? null : xs.reduce((a, b) =>
    Math.abs(b - hover) < Math.abs(a - hover) ? b : a, xs[0]);

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-labelledby={titleId}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const rel = ((e.clientX - r.left) / r.width) * W;
          const frac = (rel - PAD.left) / (W - PAD.left - PAD.right);
          setHover(xMin + frac * (xMax - xMin));
        }}
        onMouseLeave={() => setHover(null)}
      >
        <title id={titleId}>
          {caption ?? `Line chart comparing ${series.map((s) => s.label).join(", ")}`}
        </title>

        {yTicks.map((y) => (
          <g key={y}>
            {/* On a signed chart the zero line is not one gridline among
                three — it is the boundary the reader is decoding sign
                against, so it is drawn at full rule weight. */}
            <line
              x1={PAD.left} x2={W - PAD.right} y1={py(y)} y2={py(y)}
              stroke={signed && y === 0 ? "hsl(var(--border))" : "hsl(var(--rule-2))"}
              strokeWidth={1}
            />
            <text
              x={PAD.left - 8} y={py(y)} textAnchor="end" dominantBaseline="middle"
              className="fill-muted-foreground font-mono text-[10px]"
            >
              {yLabel(y)}
            </text>
          </g>
        ))}

        {ticks.map((x) => (
          <text
            key={x} x={px(x)} y={H - 8} textAnchor="middle"
            className="fill-muted-foreground font-mono text-[10px]"
          >
            {xLabel(x)}
          </text>
        ))}

        {nearest !== null && (
          <line
            x1={px(nearest)} x2={px(nearest)} y1={PAD.top} y2={H - PAD.bottom}
            stroke="hsl(var(--border))" strokeWidth={1}
          />
        )}

        {series.map((s) => (
          <path
            key={s.id} d={path(s.points, step)} fill="none" stroke={s.color}
            strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round"
          />
        ))}

        {/* An isolated point emits a bare M and draws nothing — it would simply
            vanish from the chart. Give any unconnected point a dot. */}
        {series.flatMap((s) => {
          const sorted = [...s.points].sort((a, b) => a.x - b.x);
          return sorted
            .filter((p, i) => {
              const prev = sorted[i - 1];
              const next = sorted[i + 1];
              const far = (q?: { x: number }) => !q || Math.abs(q.x - p.x) > step * 1.5;
              return far(prev) && far(next);
            })
            .map((p) => (
              <circle key={`${s.id}-${p.x}`} cx={px(p.x)} cy={py(p.y)} r={2} fill={s.color} />
            ));
        })}

        {nearest !== null &&
          series.map((s) => {
            const p = s.points.find((q) => q.x === nearest);
            return p ? (
              <circle key={s.id} cx={px(p.x)} cy={py(p.y)} r={3} fill={s.color} />
            ) : null;
          })}
      </svg>

      {/* The legend doubles as the readout. With no pointer it shows each
          series' most recent value, so the numbers are available without
          hovering — which matters for keyboard and touch users, and is simply
          more useful than an empty legend. */}
      <figcaption className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1">
        {series.map((s) => {
          const sorted = [...s.points].sort((a, b) => a.x - b.x);
          const point =
            nearest === null
              ? sorted[sorted.length - 1]
              : s.points.find((q) => q.x === nearest);
          return (
            <span key={s.id} className="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className="inline-block h-[2px] w-3.5 shrink-0"
                style={{ background: s.color }}
              />
              <span className="eyebrow">{s.label}</span>
              <span className="font-mono text-[11px] tabular-nums text-foreground">
                {point ? yLabel(point.y) : "—"}
              </span>
              {/* Each series ends at its own date — Toronto publishes further
                  behind than the other two. A single shared label asserted a
                  month/value pairing that was false for every series but one. */}
              {nearest === null && point && (
                <span className="font-mono text-[10px] text-muted-foreground">
                  {xLabel(point.x)}
                </span>
              )}
            </span>
          );
        })}
        <span className="font-mono text-[11px] text-muted-foreground">
          {nearest === null ? "latest published" : xLabel(nearest)}
        </span>
      </figcaption>
    </figure>
  );
}
