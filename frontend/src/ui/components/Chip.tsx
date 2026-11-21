import type { ButtonHTMLAttributes, ReactNode } from "react";
import clsx from "clsx";

export function Chip({ tone = "green", selected, icon, children, className, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { tone?: "green" | "orange" | "neutral"; selected?: boolean; icon?: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={clsx(
        "inline-flex min-h-11 items-center gap-1.5 rounded-full px-4 text-sm font-medium transition-colors duration-200",
        tone === "green" && (selected ? "bg-green text-ink" : "bg-chip-green text-green-text"),
        tone === "orange" && (selected ? "bg-orange text-ink" : "bg-chip-orange text-orange-chip-text"),
        tone === "neutral" && (selected ? "bg-text text-surface" : "border border-line text-text"),
        className,
      )}
      {...rest}
    >
      {icon}{children}
    </button>
  );
}
