import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, ListPlus } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { consumer, useRestaurant } from "../../../api/consumer";
import { useAction } from "../../../api/business";
import { Banner, Button, Card, ErrorState, Select, Sheet, Skeleton } from "../../../ui";
import { ActionError } from "../../business/shared";
import { useLocationCtx } from "../location";
import { DishRow, SharePicker } from "../parts";

/** Restaurant page, plus logging a thali or shared meal component by component. */
export default function RestaurantScreen() {
  const { id = "" } = useParams();
  const { coords } = useLocationCtx();
  const q = useRestaurant(id, coords);
  const nav = useNavigate();
  const qc = useQueryClient();
  const [logging, setLogging] = useState(false);
  const [picked, setPicked] = useState<Record<string, number>>({});
  const [meal, setMeal] = useState("lunch");
  const log = useAction(() => consumer.log({ meal_type: meal, items: Object.entries(picked).map(([menu_item_id, share_fraction]) => ({ menu_item_id, share_fraction })) },
    crypto.randomUUID()), []);

  if (q.isPending) return <Skeleton className="h-96" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const r = q.data;
  const all = [...r.dishes, ...r.other_dishes].filter((d) => d.energy);
  return (
    <motion.div layoutId={`restaurant-${r.id}`} className="space-y-5">
      <div className="mesh-lite -mx-4 -mt-6 px-4 pb-6 pt-4 sm:mx-0 sm:rounded-[24px]">
        <Link to="/" className="inline-flex min-h-11 items-center gap-1 text-sm text-muted"><ArrowLeft size={16} /> Back</Link>
        <h1 className="mt-2 text-3xl font-extrabold">{r.name}</h1>
        <p className="text-sm text-muted">{[r.distance_display, r.cost_for_one_inr != null && `₹${r.cost_for_one_inr} for one`].filter(Boolean).join(" · ")}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {r.typical_meal && <Card><p className="text-sm text-muted">Typical meal</p><p className="font-display text-xl font-bold text-orange-text">{r.typical_meal.display}</p><p className="text-xs text-muted">{r.typical_meal.label}</p></Card>}
        {r.personal && <Card><p className="text-sm text-muted">For you</p><p className="font-medium">{r.personal.display}</p></Card>}
      </div>
      <p className="text-sm text-muted">{r.declared_share}{r.recommend_rate ? ` · ${r.recommend_rate}` : ""}</p>
      <div className="flex items-center justify-between">
        <h2 className="font-display text-xl font-bold">Ranked for you</h2>
        <Button variant="secondary" onClick={() => setLogging(true)}><ListPlus size={18} /> Log a meal here</Button>
      </div>
      <div className="space-y-3">{r.dishes.map((d) => <DishRow key={d.id} d={d} />)}</div>
      {r.other_dishes.length > 0 && (
        <details className="card p-4">
          <summary className="cursor-pointer font-medium">Other dishes ({r.other_dishes.length})</summary>
          <p className="mt-1 text-xs text-muted">Not ranked: no reliable numbers, too wide a range, or allergen status unknown.</p>
          <div className="mt-3 space-y-3">{r.other_dishes.map((d) => <DishRow key={d.id} d={d} />)}</div>
        </details>
      )}
      <Sheet open={logging} onOpenChange={setLogging} title="What did you eat?">
        <div className="space-y-4">
          <Select label="Meal" value={meal} onChange={(e) => setMeal(e.target.value)} options={["breakfast", "lunch", "dinner", "snack"].map((m) => ({ value: m, label: m[0].toUpperCase() + m.slice(1) }))} />
          <p className="text-sm text-muted">Pick each dish and how much of it you ate. Sharing? Choose your part.</p>
          {all.map((d) => (
            <div key={d.id} className="space-y-2 rounded-2xl border border-line p-3">
              <label className="flex items-center gap-3">
                <input type="checkbox" className="size-5 accent-[var(--green-500)]" checked={d.id in picked}
                  onChange={(e) => { const p = { ...picked }; if (e.target.checked) p[d.id] = 1; else delete p[d.id]; setPicked(p); }} />
                <span className="font-medium">{d.name}</span><span className="ml-auto text-sm text-orange-text">{d.energy?.display}</span>
              </label>
              {d.id in picked && <SharePicker value={picked[d.id]} onChange={(v) => setPicked({ ...picked, [d.id]: v })} />}
            </div>
          ))}
          {all.length === 0 && <Banner tone="note" title="No dishes with nutrition to log here yet" />}
          <ActionError error={log.error} />
          <Button block disabled={!Object.keys(picked).length} loading={log.isPending}
            onClick={() => log.mutate(undefined, { onSuccess: () => { qc.invalidateQueries({ queryKey: ["diary"] }); setLogging(false); nav("/diary"); } })}>
            Add {Object.keys(picked).length || ""} to diary</Button>
        </div>
      </Sheet>
    </motion.div>
  );
}
