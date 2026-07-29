import type { ReactNode } from "react";

export interface Stat {
  label: string;
  value: string;
  detail?: ReactNode;
  accent?: string;
}

/**
 * The headline numbers. Hairline-ruled columns, mono label above an Inter Tight
 * figure — no cards, no fills, tabular numerals so columns align.
 */
export function StatGrid({ stats }: { stats: Stat[] }) {
  return (
    <dl className="grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
      {stats.map((s) => (
        <div key={s.label} className="border-t border-border pt-4">
          <dt className="eyebrow flex items-center gap-2">
            {s.accent && (
              <span
                aria-hidden="true"
                className="inline-block h-[2px] w-3.5 shrink-0"
                style={{ background: s.accent }}
              />
            )}
            {s.label}
          </dt>
          <dd className="mt-2 text-[clamp(24px,2vw,32px)] font-medium tabular-nums tracking-[-0.02em]">
            {s.value}
          </dd>
          {s.detail && (
            <dd className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
              {s.detail}
            </dd>
          )}
        </div>
      ))}
    </dl>
  );
}
