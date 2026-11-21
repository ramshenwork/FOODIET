import { motion, useReducedMotion } from "framer-motion";
import { CountUp } from "./CountUp";

/** `fraction` (0..1+) and the labels come from the API; the rings only draw them. */
export interface RingDatum { label: string; display: string; fraction: number | null }

function Ring({ size, stroke, fraction, gradient, color }: { size: number; stroke: number; fraction: number | null; gradient?: boolean; color?: string }) {
  const reduce = useReducedMotion();
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const f = fraction === null ? 0 : Math.min(fraction, 1);
  const id = gradient ? "energy-grad" : undefined;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
      {gradient && (
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--green-500)" />
            <stop offset="100%" stopColor="var(--orange-500)" />
          </linearGradient>
        </defs>
      )}
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--ring-track)" strokeWidth={stroke} />
      <motion.circle
        cx={size / 2} cy={size / 2} r={r} fill="none" strokeLinecap="round" strokeWidth={stroke}
        stroke={gradient ? `url(#${id})` : color} strokeDasharray={c}
        initial={reduce ? { strokeDashoffset: c * (1 - f), opacity: 0 } : { strokeDashoffset: c }}
        animate={{ strokeDashoffset: c * (1 - f), opacity: 1 }}
        transition={{ duration: reduce ? 0.15 : 0.9, ease: [0.22, 1, 0.36, 1] }}
      />
    </svg>
  );
}

export function MacroRings({ energy, energyValue, energyCaption, macros }: {
  energy: RingDatum; energyValue: number | null; energyCaption: string; macros: [RingDatum, RingDatum, RingDatum];
}) {
  const colors = ["var(--green-500)", "var(--orange-300)", "var(--green-300)"];
  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:gap-8">
      <div className="relative">
        <Ring size={188} stroke={16} fraction={energy.fraction} gradient />
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-4xl font-extrabold text-orange-text">
            {energyValue === null ? "–" : <CountUp value={energyValue} />}
          </span>
          <span className="text-xs text-muted">{energyCaption}</span>
        </div>
      </div>
      <ul className="grid grid-cols-3 gap-4 sm:grid-cols-1">
        {macros.map((m, i) => (
          <li key={m.label} className="flex flex-col items-center gap-1 sm:flex-row sm:gap-3">
            <Ring size={56} stroke={7} fraction={m.fraction} color={colors[i]} />
            <div className="text-center sm:text-left">
              <p className="text-xs text-muted">{m.label}</p>
              <p className="font-display text-sm font-semibold">{m.display}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
