import { useEffect, useState } from "react";

export type Theme = "light" | "dark";
type Area = "consumer" | "business" | "admin" | "public";

// Dark is the default for the consumer area; light for the table-heavy business and admin areas.
const DEFAULTS: Record<Area, Theme> = { consumer: "dark", business: "light", admin: "light", public: "dark" };

function stored(area: Area): Theme | null {
  try { const v = localStorage.getItem(`theme:${area}`); return v === "light" || v === "dark" ? v : null; }
  catch { return null; }
}

export function useAreaTheme(area: Area): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => stored(area) ?? DEFAULTS[area]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#071A13" : "#FAF7F0");
  }, [theme]);
  const toggle = () => setTheme((t) => {
    const next = t === "dark" ? "light" : "dark";
    try { localStorage.setItem(`theme:${area}`, next); } catch { /* storage unavailable */ }
    return next;
  });
  return [theme, toggle];
}
