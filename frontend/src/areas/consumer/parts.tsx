import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Leaf, Drumstick, Egg } from "lucide-react";
import type { DishCard, RestaurantCard } from "../../api/consumer";
import { TrustLabel } from "../../ui";

export function DietMark({ diet }: { diet: string | null }) {
  if (diet === "veg") return <Leaf size={14} className="text-green-text" aria-label="Veg" />;
  if (diet === "egg") return <Egg size={14} className="text-orange-text" aria-label="Egg" />;
  if (diet === "non_veg") return <Drumstick size={14} className="text-danger-text" aria-label="Non-veg" />;
  return null;
}

export function RestaurantCardView({ r }: { r: RestaurantCard }) {
  return (
    <motion.div layoutId={`restaurant-${r.id}`} className="card overflow-hidden">
      <Link to={`/restaurants/${r.id}`} className="block">
        <div className="mesh-lite h-24" aria-hidden />
        <div className="space-y-1 p-4">
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="font-display text-lg font-bold">{r.name}</h3>
            <span className="shrink-0 text-sm text-muted">{r.distance_display}</span>
          </div>
          <p className="text-sm text-muted">
            {[r.cost_for_one_inr != null && `₹${r.cost_for_one_inr.toLocaleString("en-IN")} for one`,
              r.typical_meal && `typical meal ${r.typical_meal.display}`].filter(Boolean).join(" · ")}
          </p>
          <span className="mt-2 inline-flex rounded-full bg-chip-green px-3 py-1 text-xs font-semibold text-green-text">{r.fit_display}</span>
        </div>
      </Link>
    </motion.div>
  );
}

export function DishRow({ d, showRestaurant }: { d: DishCard; showRestaurant?: boolean }) {
  return (
    <Link to={`/dishes/${d.id}`} className="card flex items-center justify-between gap-3 p-4 transition-transform duration-200 active:scale-[0.99]">
      <div className="min-w-0 space-y-1">
        <p className="flex items-center gap-1.5 font-medium"><DietMark diet={d.diet_class} /><span className="truncate">{d.name}</span></p>
        {showRestaurant && <p className="truncate text-xs text-muted">{d.restaurant_name}{d.distance_display ? ` · ${d.distance_display}` : ""}</p>}
        <div className="flex flex-wrap items-center gap-2">
          <TrustLabel kind={d.trust.label} note={d.trust.note ?? undefined} />
          {d.fits && <span className="rounded-full bg-chip-green px-2 py-0.5 text-xs font-semibold text-green-text">Fits you</span>}
          {d.allergen_warning && <span className="text-xs text-danger-text">{d.allergen_warning}</span>}
        </div>
      </div>
      <div className="shrink-0 text-right">
        <p className="font-display font-bold text-orange-text">{d.energy?.display ?? "No data"}</p>
        {d.protein && <p className="text-xs text-muted">Protein {d.protein.display}</p>}
        {d.price_inr != null && <p className="text-xs text-muted">₹{d.price_inr.toLocaleString("en-IN")}</p>}
      </div>
    </Link>
  );
}

/** A plate that fills to the chosen share. The share itself is sent to the server for the numbers. */
export function SharePicker({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const options: [number, string][] = [[1, "Whole"], [0.5, "Half"], [1 / 3, "A third"], [0.25, "A quarter"]];
  const r = 26, c = 2 * Math.PI * r;
  return (
    <div className="flex items-center gap-4">
      <svg width="64" height="64" viewBox="0 0 64 64" aria-hidden className="shrink-0">
        <circle cx="32" cy="32" r="30" fill="var(--card)" stroke="var(--line)" strokeWidth="2" />
        <motion.circle cx="32" cy="32" r={r / 2} fill="none" stroke="var(--orange-500)" strokeWidth={r} transform="rotate(-90 32 32)"
          strokeDasharray={`${Math.PI * r}`} animate={{ strokeDashoffset: Math.PI * r * (1 - value) }} transition={{ type: "spring", stiffness: 200, damping: 26 }} />
        <circle cx="32" cy="32" r="30" fill="none" stroke="var(--line)" strokeWidth="2" strokeDasharray={c} opacity="0" />
      </svg>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="How much did you eat">
        {options.map(([v, label]) => (
          <button key={label} type="button" role="radio" aria-checked={Math.abs(value - v) < 0.001} onClick={() => onChange(v)}
            className={`min-h-11 rounded-full px-4 text-sm font-medium ${Math.abs(value - v) < 0.001 ? "bg-orange text-ink" : "border border-line"}`}>{label}</button>
        ))}
      </div>
    </div>
  );
}
