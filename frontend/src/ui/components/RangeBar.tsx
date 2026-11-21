import { motion, useReducedMotion } from "framer-motion";
import type { NutrientValue } from "../../api/types";

/**
 * Shows a server-computed value. The text is the API's own `display` string; the bar only
 * positions what it was given. `null` means unknown and is shown as such, never as zero.
 * `scaleMax` is supplied by the caller from the API response (e.g. the day's budget).
 */
export function RangeBar({ value, scaleMax, label }: { value: NutrientValue | null; scaleMax?: number; label: string }) {
  const reduce = useReducedMotion();
  if (value === null) {
    return <p className="text-sm text-muted"><span className="sr-only">{label}: </span>Not available</p>;
  }
  if (value.display_mode === "single") {
    return <p className="font-display text-lg font-semibold text-orange-text">{value.display}</p>;
  }
  const max = scaleMax ?? value.high * 1.25;   // drawing scale only: leave headroom to the right of the range
  const pct = (n: number) => `${Math.max(0, Math.min(100, (n / max) * 100))}%`;
  return (
    <div>
      <p className="mb-2 font-display text-lg font-semibold text-orange-text">{value.display}</p>
      <div className="relative h-3 rounded-full" style={{ background: "var(--ring-track)" }} role="img"
           aria-label={`${label}: ${value.display}`}>
        <motion.div
          className="absolute inset-y-0 rounded-full bg-orange/80"
          style={{ left: pct(value.low), right: `calc(100% - ${pct(value.high)})`, originX: 0 }}
          initial={reduce ? { opacity: 0 } : { scaleX: 0, opacity: 0 }}
          animate={reduce ? { opacity: 1 } : { scaleX: 1, opacity: 1 }}
          transition={{ duration: 0.3, ease: "easeOut" }}
        />
        {value.display_mode === "band" && (
          <div className="absolute -top-1 h-5 w-1 -translate-x-1/2 rounded-full bg-text" style={{ left: pct(value.mid) }} />
        )}
      </div>
    </div>
  );
}
