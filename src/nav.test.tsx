import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import App from "@/App";

/**
 * Reaching the page, and moving around it, without a pointer.
 *
 * Both gaps these cover were verified on production before the spec was
 * written: the section nav was `hidden … lg:flex` with no alternative, so a
 * phone-width viewport had no navigation at all, and there was no skip link.
 */

/** Everything that takes focus, in document order. */
function focusables(): HTMLElement[] {
  return Array.from(
    document.querySelectorAll<HTMLElement>(
      'a[href], button, input, select, textarea, summary, [tabindex]:not([tabindex="-1"])',
    ),
  );
}

describe("skip link", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark");
    localStorage.clear();
  });

  it("is the first focusable element and points at the main landmark", () => {
    render(<App />);
    const first = focusables()[0];
    expect(first.tagName).toBe("A");
    expect(first).toHaveAttribute("href", "#main");
    expect(first).toHaveTextContent(/skip to content/i);
  });

  it("has a target that exists, is the main landmark, and can hold focus", () => {
    render(<App />);
    const main = document.getElementById("main");
    expect(main).not.toBeNull();
    expect(main!.tagName).toBe("MAIN");
    // Without this the browser scrolls but leaves focus in the header, and the
    // next Tab walks the nav the reader just asked to skip.
    expect(main).toHaveAttribute("tabindex", "-1");
  });

  it("is hidden until focused rather than removed from the page", () => {
    render(<App />);
    const link = focusables()[0];
    expect(link.className).toMatch(/\bsr-only\b/);
    expect(link.className).toMatch(/focus:not-sr-only/);
  });
});

describe("mobile section menu", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark");
    document.body.style.overflow = "";
    localStorage.clear();
  });

  const button = () => screen.getByRole("button", { name: /^sections$/i });

  it("is a closed disclosure that names the element it controls", () => {
    render(<App />);
    const b = button();
    expect(b).toHaveAttribute("aria-expanded", "false");
    const controls = b.getAttribute("aria-controls");
    expect(controls).toBeTruthy();
    expect(document.getElementById(controls!)).toBeNull();
  });

  it("opens the same section list the desktop nav carries", async () => {
    const user = userEvent.setup({ delay: null });
    render(<App />);
    const desktop = document.querySelector<HTMLElement>('nav[aria-label="Sections"]')!;
    const expected = within(desktop)
      .getAllByRole("link")
      .map((a) => [a.textContent, a.getAttribute("href")]);

    await user.click(button());
    const panel = document.getElementById(button().getAttribute("aria-controls")!)!;
    expect(button()).toHaveAttribute("aria-expanded", "true");

    const inMenu = within(panel)
      .getAllByRole("link")
      .map((a) => [a.textContent, a.getAttribute("href")]);
    // Identical, because both render the same NAV constant. A section that
    // exists on one breakpoint and not the other is the bug this replaces.
    expect(inMenu).toEqual(expected);
    expect(inMenu.length).toBeGreaterThan(1);
  });

  it("moves focus into the menu and locks the page behind it", async () => {
    const user = userEvent.setup({ delay: null });
    render(<App />);
    await user.click(button());
    const panel = document.getElementById(button().getAttribute("aria-controls")!)!;
    expect(document.activeElement).toBe(within(panel).getAllByRole("link")[0]);
    expect(document.body.style.overflow).toBe("hidden");
  });

  it("closes on Escape and gives focus back to the button", async () => {
    const user = userEvent.setup({ delay: null });
    render(<App />);
    await user.click(button());
    await user.keyboard("{Escape}");
    expect(button()).toHaveAttribute("aria-expanded", "false");
    expect(document.activeElement).toBe(button());
    expect(document.body.style.overflow).toBe("");
  });

  it("closes on a click outside it", async () => {
    const user = userEvent.setup({ delay: null });
    render(<App />);
    await user.click(button());
    await user.click(document.getElementById("main")!);
    expect(button()).toHaveAttribute("aria-expanded", "false");
    expect(document.body.style.overflow).toBe("");
  });

  it("closes when a section is chosen, rather than covering it", async () => {
    const user = userEvent.setup({ delay: null });
    render(<App />);
    await user.click(button());
    const panel = document.getElementById(button().getAttribute("aria-controls")!)!;
    await user.click(within(panel).getAllByRole("link")[2]);
    expect(button()).toHaveAttribute("aria-expanded", "false");
  });

  it("keeps Tab inside the open menu instead of walking the page behind it", async () => {
    const user = userEvent.setup({ delay: null });
    render(<App />);
    await user.click(button());
    const panel = document.getElementById(button().getAttribute("aria-controls")!)!;
    const links = within(panel).getAllByRole("link");
    links[links.length - 1].focus();
    await user.tab();
    expect(document.activeElement).toBe(button());
    await user.tab({ shift: true });
    expect(document.activeElement).toBe(links[links.length - 1]);
  });
});
