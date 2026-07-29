import { beforeEach, describe, expect, it } from "vitest";
import { setTheme } from "@/lib/theme";

describe("theme", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark");
    localStorage.clear();
  });

  it("flips the dark class on <html>", () => {
    setTheme("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    setTheme("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("persists the choice so the pre-paint script can read it back", () => {
    setTheme("dark");
    expect(localStorage.getItem("theme")).toBe("dark");
  });

  it("still applies the class when storage throws", () => {
    const setItem = Storage.prototype.setItem;
    Storage.prototype.setItem = () => {
      throw new Error("private mode");
    };
    try {
      expect(() => setTheme("dark")).not.toThrow();
      expect(document.documentElement.classList.contains("dark")).toBe(true);
    } finally {
      Storage.prototype.setItem = setItem;
    }
  });
});
