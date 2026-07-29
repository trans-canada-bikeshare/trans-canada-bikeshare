import { useSyncExternalStore } from "react";

// Theme state lives on <html> itself: the inline script in index.html sets the
// `dark` class before first paint, and everything here just reads or flips that
// class. No provider needed — useTheme() subscribes any component (nav toggle,
// charts, map) to the same source of truth.
//
// Ported from mobi-transit-explorer so the two projects behave identically.

export type Theme = "light" | "dark";

const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function snapshot(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function setTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
  try {
    localStorage.setItem("theme", theme);
  } catch {
    // Storage may be unavailable (private mode); the class still applies.
  }
  listeners.forEach((listener) => listener());
}

export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, snapshot, () => "light");
}
