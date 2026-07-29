import type { ReactNode } from "react";

interface SectionProps {
  id: string;
  eyebrow: string;
  title: string;
  lede?: ReactNode;
  children: ReactNode;
}

/**
 * One ruled block: mono eyebrow, Inter Tight heading, optional lede, content.
 * Sections are separated by a hairline rule rather than boxed in cards —
 * boxes are reserved for data surfaces.
 */
export function Section({ id, eyebrow, title, lede, children }: SectionProps) {
  return (
    <section id={id} className="scroll-mt-20 border-t border-border pt-10 md:pt-14">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-3xl text-[clamp(28px,2.6vw,40px)] font-medium leading-[1.08] tracking-[-0.02em]">
        {title}
      </h2>
      {lede && (
        <div className="mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground">
          {lede}
        </div>
      )}
      <div className="mt-8">{children}</div>
    </section>
  );
}

interface NoteProps {
  children: ReactNode;
}

/**
 * A stated caveat sitting with the thing it qualifies. Used wherever a number
 * needs a condition attached — an excluded share, a window, a system that does
 * not publish a field. Deliberately not a footnote: a caveat a reader has to go
 * looking for is one the chart is hiding.
 */
export function Note({ children }: NoteProps) {
  return (
    <p className="mt-4 border-l border-border pl-3 text-[13px] leading-relaxed text-muted-foreground">
      {children}
    </p>
  );
}
