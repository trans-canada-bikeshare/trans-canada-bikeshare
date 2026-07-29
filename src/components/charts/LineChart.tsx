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
}: Props) {
  const titleId = useId();
  const [hover, setHover] = useState<number | null>(null);
  const W = 720;
  const H = height;

  const { xs, xMin, xMax, yMax } = useMemo(() => {
    const all = series.flatMap((s) => s.points);
    const xsSet = [...new Set(all.map((p) => p.x))].sort((a, b) => a - b);
    return {
      xs: xsSet,
      xMin: xsSet[0] ?? 0,
      xMax: xsSet[xsSet.length - 1] ?? 1,
      yMax: Math.max(1, ...all.map((p) => p.y)),
    };
  }, [series]);

  const px = (x: number) =>
    PAD.left + ((x - xMin) / Math.max(1, xMax - xMin)) * (W - PAD.left - PAD.right);
  const py = (y: number) => H - PAD.bottom - (y / yMax) * (H - PAD.top - PAD.bottom);

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
  const yTicks = [0, yMax / 2, yMax];

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
            <line
              x1={PAD.left} x2={W - PAD.right} y1={py(y)} y2={py(y)}
              stroke="hsl(var(--rule-2))" strokeWidth={1}
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

        {nearest !== null &&
          series.map((s) => {
            const p = s.points.find((q) => q.x === nearest);
            return p ? (
              <circle key={s.id} cx={px(p.x)} cy={py(p.y)} r={3} fill={s.color} />
            ) : null;
          })}
      </svg>

      <figcaption className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1">
        {series.map((s) => {
          const p = nearest === null ? null : s.points.find((q) => q.x === nearest);
          return (
            <span key={s.id} className="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className="inline-block h-[2px] w-3.5 shrink-0"
                style={{ background: s.color }}
              />
              <span className="eyebrow">{s.label}</span>
              <span className="font-mono text-[11px] tabular-nums text-foreground">
                {p ? yLabel(p.y) : ""}
              </span>
            </span>
          );
        })}
        {nearest !== null && (
          <span className="font-mono text-[11px] text-muted-foreground">
            {xLabel(nearest)}
          </span>
        )}
      </figcaption>
    </figure>
  );
}
