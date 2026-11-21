import { Moon, Sun } from "lucide-react";
import type { Theme } from "../../app/theme";

export function ThemeToggle({ theme, toggle }: { theme: Theme; toggle: () => void }) {
  return (
    <button type="button" onClick={toggle} aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      className="grid size-11 place-items-center rounded-full text-muted hover:bg-chip-green hover:text-text">
      {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
    </button>
  );
}
