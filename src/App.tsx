import { setTheme, useTheme } from "@/lib/theme";

// Scaffold surface only. The real shell — nav, scrollspy, sections — is spec
// 015. This exists to prove the design language renders and the theme flips.
export default function App() {
  const theme = useTheme();

  return (
    <div className="min-h-screen">
      <header className="border-b border-border">
        <div className="container flex h-14 items-center justify-between">
          <span className="flex items-center gap-2.5">
            <img
              src="/logo.svg"
              alt=""
              aria-hidden="true"
              width={44}
              height={18}
              className="shrink-0"
            />
            <span className="text-[15px] font-medium tracking-[-0.01em]">
              Trans-Canada Bikeshare
            </span>
          </span>
          <button
            type="button"
            className="eyebrow border-b border-muted-2 pb-0.5 transition-colors hover:border-foreground hover:text-foreground"
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            aria-pressed={theme === "dark"}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? "Light" : "Dark"}
          </button>
        </div>
      </header>

      <main className="container pt-24">
        <p className="eyebrow">Scaffold · spec 002</p>
        <h1 className="mt-7 max-w-3xl text-[clamp(40px,7vw,96px)] font-medium leading-[0.95] tracking-[-0.024em]">
          Canada's bike share systems, measured the same way.
        </h1>
        {/* text-base is the 17px portfolio reading size, not the browser's 16 —
            Tailwind only applies it where asked, so prose opts in explicitly. */}
        <p className="mt-9 max-w-xl text-base text-muted-foreground">
          Vancouver, Montreal, and Toronto — one pipeline, one set of
          definitions, computed from each system's published open data and
          compared like for like.
        </p>

        <hr className="mt-16 border-t border-rule-2" />

        {/* SCAFFOLD DATA — hardcoded, and it must not stay that way. These years
            are audit-verified (docs/source-audit.md) but the project's rule is
            that copy derives from the data window, not from a literal. Spec 014
            emits meta.json and spec 016 replaces this surface entirely; until
            then this is the one place in the repo making a data claim no
            pipeline backs. */}
        <dl className="mt-8 grid gap-6 sm:grid-cols-3">
          {[
            { city: "Vancouver", system: "Mobi by Rogers", since: "2017" },
            { city: "Montreal", system: "BIXI", since: "2014" },
            { city: "Toronto", system: "Bike Share Toronto", since: "2014" },
          ].map((s) => (
            <div key={s.city} className="border-t border-border pt-4">
              <dt className="eyebrow">{s.city}</dt>
              <dd className="mt-2 text-[15px]">{s.system}</dd>
              <dd className="mt-1 text-[13px] tabular-nums text-muted-foreground">
                open data since {s.since}
              </dd>
            </div>
          ))}
        </dl>
      </main>

      <footer className="container mt-24 border-t border-border py-8">
        {/* The mark carries the National Flag's maple leaf. Saying plainly that
            this is not a government site costs one line and removes any
            implied endorsement — see docs/features/002b-brand-identity.md. */}
        <p className="text-[13px] text-muted-foreground">
          Not affiliated with or endorsed by the Government of Canada.
        </p>
      </footer>
    </div>
  );
}
