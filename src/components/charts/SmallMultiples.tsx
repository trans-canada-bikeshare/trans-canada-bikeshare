import { useId, useMemo, useState } from "react";
import { compact } from "@/lib/format";
import type { Series } from "@/components/charts/LineChart";

interface Props {
  series: Series[];
  xLabel: (x: number) => string;
  yLabel?: (y: number) => string;
  /** Height of each panel. Three panels stack, so keep this modest. */
  panelHeight?: number;
  xTicks?: number;
  caption?: string;
}

const PAD = { top: 10, right: 12, bottom: 6, left: 52 };
const AXIS_H = 20;

/**
 * One panel per series, stacked, sharing an x axis but each with its own y
 * scale — and each panel states its own maximum.
 *
 * A single shared axis is arithmetically honest and visually useless here.
 * Montreal peaks near 2.3M trips a month, Vancouver near 200k; on one axis
 * Vancouver's whole nine-year series occupies about 19 pixels of a 222-pixel
 * plot, and its real growth of roughly 12x reads as a flat line along the
 * baseline. The site exists to compare these cities, so an encoding that
 * renders the smallest one meaningless fails its own purpose.
 *
 * The absolute-scale story is not lost: it is carried by the overview's stat
 * grid and stated in the section lede. What this recovers is each system's
 * SHAPE, which is what a reader can actually compare across panels.
 */
export function SmallMultiples({
  series,
  xLabel,
  yLabel = compact,
  panelHeight = 96,
  xTicks = 7,
  caption,
}: Props) {
  const titleId = useId();
  const [hover, setHover] = useState<number | null>(null);
  const W = 720;

  const { xs, xMin, xMax } = useMemo(() => {
    const all = series.flatMap((s) => s.points);
    const set = [...new Set(all.map((p) => p.x))].sort((a, b) => a - b);
    return { xs: set, xMin: set[0] ?? 0, xMax: set[set.length - 1] ?? 1 };
  }, [series]);

  const step = xs.length > 1 ? Math.min(...xs.slice(1).map((x, i) => x - xs[i])) : 1;
  const px = (x: number) =>
    PAD.left + ((x - xMin) / Math.max(1, xMax - xMin)) * (W - PAD.left - PAD.right);
  const tickEvery = Math.max(1, Math.round(xs.length / xTicks));
  const ticks = xs.filter((_, i) => i % tickEvery === 0);

  const nearest =
    hover === null
      ? null
      : xs.reduce((a, b) => (Math.abs(b - hover) < Math.abs(a - hover) ? b : a), xs[0]);

  const H = series.length * panelHeight + AXIS_H;

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
          {caption ??
            `Separate panels, one per system, each with its own vertical scale: ${series
              .map((s) => s.label)
              .join(", ")}`}
        </title>

        {series.map((s, i) => {
          const top = i * panelHeight;
          const yMax = Math.max(1, ...s.points.map((p) => p.y));
          const py = (y: number) =>
            top + panelHeight - PAD.bottom - (y / yMax) * (panelHeight - PAD.top - PAD.bottom);

          const sorted = [...s.points].sort((a, b) => a.x - b.x);
          let d = "";
          sorted.forEach((p, j) => {
            const prev = sorted[j - 1];
            const broken = !prev || p.x - prev.x > step * 1.5;
            d += `${broken ? "M" : "L"}${px(p.x).toFixed(1)} ${py(p.y).toFixed(1)}`;
          });

          const at = nearest === null ? null : s.points.find((q) => q.x === nearest);

          return (
            <g key={s.id}>
              <line
                x1={PAD.left} x2={W - PAD.right}
                y1={top + panelHeight - PAD.bottom} y2={top + panelHeight - PAD.bottom}
                stroke="hsl(var(--rule-2))" strokeWidth={1}
              />
              {/* Each panel declares its own ceiling, so a reader is never
                  invited to compare heights across panels by eye. */}
              <text
                x={PAD.left - 8} y={top + PAD.top + 2} textAnchor="end"
                className="fill-muted-foreground font-mono text-[10px]"
              >
                {yLabel(yMax)}
              </text>
              <text
                x={PAD.left - 8} y={top + panelHeight - PAD.bottom} textAnchor="end"
                className="fill-muted-foreground font-mono text-[10px]"
              >
                0
              </text>
              <text
                x={PAD.left + 4} y={top + PAD.top + 2}
                className="font-mono text-[10px] uppercase tracking-[0.14em]"
                fill={s.color}
              >
                {s.label}
              </text>

              {nearest !== null && (
                <line
                  x1={px(nearest)} x2={px(nearest)}
                  y1={top + PAD.top - 4} y2={top + panelHeight - PAD.bottom}
                  stroke="hsl(var(--border))" strokeWidth={1}
                />
              )}

              <path d={d} fill="none" stroke={s.color} strokeWidth={1.5}
                    strokeLinejoin="round" strokeLinecap="round" />

              {at && <circle cx={px(at.x)} cy={py(at.y)} r={2.5} fill={s.color} />}
            </g>
          );
        })}

        {ticks.map((x) => (
          <text
            key={x} x={px(x)} y={H - 4} textAnchor="middle"
            className="fill-muted-foreground font-mono text-[10px]"
          >
            {xLabel(x)}
          </text>
        ))}
      </svg>

      <figcaption className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1">
        {series.map((s) => {
          const sorted = [...s.points].sort((a, b) => a.x - b.x);
          const point =
            nearest === null ? sorted[sorted.length - 1] : s.points.find((q) => q.x === nearest);
          return (
            <span key={s.id} className="flex items-center gap-1.5">
              <span aria-hidden="true" className="inline-block h-[2px] w-3.5 shrink-0"
                    style={{ background: s.color }} />
              <span className="eyebrow">{s.label}</span>
              <span className="font-mono text-[11px] tabular-nums text-foreground">
                {point ? yLabel(point.y) : "—"}
              </span>
              {nearest === null && point && (
                <span className="font-mono text-[10px] text-muted-foreground">
                  {xLabel(point.x)}
                </span>
              )}
            </span>
          );
        })}
        <span className="font-mono text-[11px] text-muted-foreground">
          {nearest === null ? "latest published · each panel scaled to itself" : xLabel(nearest)}
        </span>
      </figcaption>
    </figure>
  );
}
