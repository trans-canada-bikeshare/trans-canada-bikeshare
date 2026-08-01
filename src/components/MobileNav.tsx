import { useEffect, useId, useRef, useState } from "react";

interface Props {
  /** The same `[anchor, label]` list the desktop nav renders. One source, so a
   *  section can never exist on one breakpoint and not the other. */
  items: readonly (readonly [string, string])[];
}

/**
 * The section list below the `lg` breakpoint.
 *
 * Until spec 032 the nav was `hidden … lg:flex` with no alternative, so a
 * phone-width viewport had no navigation of any kind — every section reachable
 * only by scrolling past all the others. This is the same list behind a
 * disclosure button.
 *
 * A disclosure, not a dialog: it is a menu of in-page links, so it takes
 * `aria-expanded` / `aria-controls` on the button rather than `role="dialog"`,
 * which would promise a modal this is not. What it does borrow from a dialog is
 * the behaviour a keyboard user expects once focus has moved into it — Escape
 * closes and returns focus to the button that opened it, Tab cycles inside the
 * open menu rather than walking the page behind it, an outside click closes it,
 * and the body does not scroll underneath while it is open.
 */
export function MobileNav({ items }: Props) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Escape closes and hands focus back; a click anywhere else closes without
  // stealing focus, because the click has already chosen where focus goes.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      buttonRef.current?.focus();
    };
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node | null;
      if (!t) return;
      if (panelRef.current?.contains(t) || buttonRef.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open]);

  // Focus moves into the menu on open, so the next Tab is inside it rather than
  // on whatever followed the button in source order.
  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLAnchorElement>("a")?.focus();
  }, [open]);

  // The page behind an open menu must not scroll: on a phone the menu can be
  // taller than the viewport, and scrolling the document instead of the panel
  // is the failure that makes the last sections unreachable again.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  // Crossing to the desktop breakpoint with the menu open hid the wrapper via
  // CSS while `open` (and the scroll lock) stayed true — an unscrollable page
  // whose closing control is display:none. Found in review; the menu closes
  // itself the moment the desktop nav takes over.
  useEffect(() => {
    if (!open) return;
    const mq = window.matchMedia("(min-width: 1024px)");
    const onChange = () => {
      if (mq.matches) setOpen(false);
    };
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [open]);

  /** Tab wraps around the button and the links, in both directions. */
  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (!open || e.key !== "Tab") return;
    const stops = ([] as (HTMLElement | null)[])
      .concat(buttonRef.current)
      .concat(
        panelRef.current
          ? Array.from(panelRef.current.querySelectorAll<HTMLAnchorElement>("a[href]"))
          : [],
      )
      .filter((n): n is HTMLElement => n !== null);
    if (stops.length === 0) return;
    const first = stops[0];
    const last = stops[stops.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && active === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  };

  return (
    <div className="lg:hidden" onKeyDown={onKeyDown}>
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        className="eyebrow border-b border-muted-2 pb-0.5 transition-colors hover:border-foreground hover:text-foreground"
        onClick={() => setOpen((o) => !o)}
      >
        {/* The label does not change to "Close" when it opens. `aria-expanded`
            already carries the state to assistive technology, and a control
            whose accessible name moves under the reader is one they cannot
            refer to — by voice, or in a test. */}
        Sections
      </button>

      {/* Always in the DOM, `hidden` when closed: the button's aria-controls
          must reference an id that exists, and a conditional render left it
          dangling whenever the menu was shut — found by the 032 DOM audit. */}
      <div
        id={panelId}
        ref={panelRef}
        hidden={!open}
        // Anchored to the sticky header, which is a positioned ancestor.
        className="absolute inset-x-0 top-full max-h-[calc(100vh-3.5rem)] overflow-y-auto border-b border-border bg-background shadow-sm"
      >
          <nav aria-label="Sections" className="container grid grid-cols-2 gap-x-6 py-4 sm:grid-cols-3">
            {items.map(([id, label]) => (
              <a
                key={id}
                href={`#${id}`}
                className="border-b border-rule-2 py-2.5 text-[15px] text-muted-foreground transition-colors hover:text-foreground"
                // A chosen section is the reason the menu was opened; leaving it
                // over the heading the reader just jumped to would be its own
                // small bug.
                onClick={() => setOpen(false)}
              >
                {label}
              </a>
            ))}
          </nav>
        </div>
    </div>
  );
}
