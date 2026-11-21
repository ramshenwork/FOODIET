import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Plus } from "lucide-react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { useQueryClient } from "@tanstack/react-query";
import { consumer, feedback, useDish, useSwaps, type DishNutrition } from "../../../api/consumer";
import { useAction } from "../../../api/business";
import { Banner, Button, Card, Chip, ErrorState, RangeBar, Select, Sheet, Skeleton, TrustLabel } from "../../../ui";
import { ActionError } from "../../business/shared";
import { DietMark, SharePicker } from "../parts";

const MACROS = [["protein_g", "Protein"], ["carbs_g", "Carbs"], ["fat_g", "Fat"], ["fibre_g", "Fibre"], ["sodium_mg", "Sodium"]] as const;

export default function DishScreen() {
  const { id = "" } = useParams();
  const dish = useDish(id);
  const swaps = useSwaps(id);
  const nav = useNavigate();
  const qc = useQueryClient();
  const [serving, setServing] = useState<string | null>(null);
  const [share, setShare] = useState(1);
  const [mods, setMods] = useState<string[]>([]);
  const [live, setLive] = useState<DishNutrition | null>(null);
  const [calcError, setCalcError] = useState<unknown>(null);
  const [adding, setAdding] = useState(false);
  const [meal, setMeal] = useState("lunch");
  const [reporting, setReporting] = useState(false);
  const [reportType, setReportType] = useState("menu_changed");
  const [reportText, setReportText] = useState("");
  const report = useAction(() => feedback.report({ menu_item_id: id, type: reportType, detail: reportText || null }), []);
  const seq = useRef(0);
  const add = useAction(() => consumer.log({ meal_type: meal, items: [{ menu_item_id: id, serving_option_id: serving, share_fraction: share, modifier_ids: mods }] },
    crypto.randomUUID()), []);

  // Recalculate on the server whenever the serving, share or options change.
  useEffect(() => {
    if (!dish.data) return;
    const changed = serving !== null || share !== 1 || mods.length > 0;
    if (!changed) { setLive(null); return; }
    const n = ++seq.current;
    consumer.calculate(id, { serving_option_id: serving, share_fraction: share, modifier_ids: mods })
      .then((r) => { if (n === seq.current) { setLive(r); setCalcError(null); } })
      .catch((e) => { if (n === seq.current) setCalcError(e); });
  }, [serving, share, mods, id, dish.data]);

  if (dish.isPending) return <Skeleton className="h-[480px]" />;
  if (dish.isError) return <ErrorState error={dish.error} onRetry={() => dish.refetch()} />;
  const d = dish.data;
  const n = live ?? d.nutrition;
  const e = n.nutrients.energy_kcal;
  const toggleMod = (groupMods: string[], modId: string, exclusive: boolean) =>
    setMods((m) => m.includes(modId) ? m.filter((x) => x !== modId) : [...(exclusive ? m.filter((x) => !groupMods.includes(x)) : m), modId]);

  return (
    <div className="space-y-5 pb-24">
      <div className="mesh-lite -mx-4 -mt-6 px-4 pb-6 pt-4 sm:mx-0 sm:rounded-[24px]">
        <Link to={`/restaurants/${d.restaurant_id}`} className="inline-flex min-h-11 items-center gap-1 text-sm text-muted"><ArrowLeft size={16} /> {d.restaurant_name}</Link>
        <h1 className="mt-2 flex items-center gap-2 text-3xl font-extrabold"><DietMark diet={d.diet_class} />{d.name}</h1>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Tooltip.Provider><TrustLabel kind={n.trust.label} note={n.trust.note ?? undefined} /></Tooltip.Provider>
          <span className="text-sm text-muted">{n.trust.meaning}</span>
        </div>
        {/* The server's display text, split only for typography: "430 kcal" large, "give or take 60" below. */}
        <p className={`mt-4 font-display font-extrabold leading-none tracking-tight text-orange-text ${e?.display_mode === "range" ? "text-[40px] sm:text-[56px]" : "text-[56px] sm:text-[72px]"}`}>
          {e ? e.display.split(", ")[0] : "Nutrition not available"}
        </p>
        {e?.display_mode === "band" && <p className="mt-1 font-medium text-orange-text">{e.display.split(", ").slice(1).join(", ")}</p>}
        <p className="text-sm text-muted">{n.serving_label}{share !== 1 ? ` · your share` : ""}</p>
      </div>

      {d.allergy_conflict.length > 0 && <Banner tone="problem" title={`Contains ${d.allergy_conflict.join(", ")}`}>You told us you're allergic to this.</Banner>}
      {n.fit && <Banner tone={n.fit.fits ? "success" : "note"} title={n.fit.display} />}
      {calcError ? <ActionError error={calcError} /> : null}

      <Card className="space-y-4">
        <RangeBar label="Energy" value={e} />
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
          {MACROS.map(([k, label]) => (
            <div key={k}><dt className="text-muted">{label}</dt><dd className="font-semibold">{n.nutrients[k]?.display ?? "Not available"}</dd></div>
          ))}
        </dl>
        {n.protein_per_100_inr && <p className="text-sm text-green-text">{n.protein_per_100_inr}</p>}
      </Card>

      {d.servings.length > 1 && (
        <Card className="space-y-2"><p className="font-medium">Serving</p>
          <div className="flex flex-wrap gap-2">{d.servings.map((s) => s.id && (
            <Chip key={s.id} tone="neutral" selected={(serving ?? d.servings.find((x) => x.selected)?.id) === s.id} onClick={() => setServing(s.id)}>{s.label} · {s.weight_g} g</Chip>
          ))}</div>
        </Card>
      )}
      <Card className="space-y-2"><p className="font-medium">How much are you having?</p><SharePicker value={share} onChange={setShare} /></Card>
      {d.modifier_groups.map((g) => (
        <Card key={g.id} className="space-y-2"><p className="font-medium">{g.name}</p>
          <div className="flex flex-wrap gap-2">{g.modifiers.map((m) => (
            <Chip key={m.id} tone="green" selected={mods.includes(m.id)} onClick={() => toggleMod(g.modifiers.map((x) => x.id), m.id, g.exclusive)}>{m.label}</Chip>
          ))}</div>
        </Card>
      ))}

      <Card className="space-y-2">
        <p className="font-medium">Ingredients <span className="text-sm font-normal text-muted">· {d.ingredients_label}</span></p>
        <p className="text-sm text-muted">{d.ingredients.length ? d.ingredients.join(", ") : "Not available"}</p>
        <p className={`text-sm ${d.allergens.status === "unknown" ? "text-muted" : "text-danger-text"}`}>{d.allergens.display}</p>
      </Card>
      <p className="text-xs text-muted">{d.last_updated ? `Recipe last confirmed ${new Date(d.last_updated).toLocaleDateString("en-IN", { dateStyle: "medium" })}` : "Estimated from a typical recipe"}{d.price_inr != null ? ` · ₹${d.price_inr}` : ""}</p>
      <button className="min-h-11 text-sm font-medium text-muted underline" onClick={() => setReporting(true)}>Report a problem with this dish</button>
      {swaps.data && swaps.data.swaps.length > 0 && (
        <Card className="space-y-3">
          <p className="font-medium">Healthier swaps</p>
          {swaps.data.swaps.map((s) => s.kind === "option" ? (
            <button key={s.title} onClick={() => s.modifier_id && !mods.includes(s.modifier_id) && setMods([...mods, s.modifier_id])}
              className="flex w-full items-center justify-between gap-3 rounded-2xl bg-chip-green p-3 text-left">
              <span className="font-medium">{s.title}</span><span className="text-sm text-green-text">{s.display}</span>
            </button>
          ) : (
            <Link key={s.title} to={`/dishes/${s.dish_id}`} className="flex items-center justify-between gap-3 rounded-2xl border border-line p-3">
              <span className="font-medium">{s.title}</span><span className="text-right text-sm text-muted">{s.display}</span>
            </Link>
          ))}
          <p className="text-xs text-muted">{swaps.data.note}</p>
        </Card>
      )}

      <div className="glass fixed inset-x-0 bottom-[calc(64px+env(safe-area-inset-bottom))] z-20 border-t border-line p-3 sm:static sm:border-0 sm:bg-transparent sm:p-0">
        <Button block disabled={!e} onClick={() => setAdding(true)}><Plus size={18} /> Add to diary</Button>
      </div>
      <Sheet open={reporting} onOpenChange={(o) => { setReporting(o); if (!o) report.reset(); }} title="Report a problem">
        {report.isSuccess ? <Banner tone="success" title={report.data.message} /> : (
          <div className="space-y-4">
            <Select label="What's wrong?" value={reportType} onChange={(ev) => setReportType(ev.target.value)} options={[
              { value: "allergen_concern", label: "Possible allergen not listed" },
              { value: "menu_changed", label: "The dish or menu has changed" },
              { value: "portion_wrong", label: "The portion looked different" }]} />
            <label className="block"><span className="mb-1.5 block text-sm font-medium">Details (optional)</span>
              <textarea rows={3} value={reportText} onChange={(ev) => setReportText(ev.target.value)} maxLength={1000}
                className="w-full rounded-[var(--radius-control)] border border-line bg-card p-3 outline-none focus:border-green" /></label>
            <p className="text-xs text-muted">If you have a severe allergy, always check with the restaurant before ordering.</p>
            <ActionError error={report.error} />
            <Button block loading={report.isPending} onClick={() => report.mutate(undefined)}>Send report</Button>
          </div>
        )}
      </Sheet>
      <Sheet open={adding} onOpenChange={setAdding} title="Add to diary">
        <div className="space-y-4">
          <Select label="Meal" value={meal} onChange={(ev) => setMeal(ev.target.value)} options={["breakfast", "lunch", "dinner", "snack"].map((m) => ({ value: m, label: m[0].toUpperCase() + m.slice(1) }))} />
          <p className="text-sm">{d.name} · {e?.display}</p>
          <ActionError error={add.error} />
          <Button block loading={add.isPending} onClick={() => add.mutate(undefined, { onSuccess: () => { qc.invalidateQueries({ queryKey: ["diary"] }); setAdding(false); nav("/diary"); } })}>Add</Button>
        </div>
      </Sheet>
    </div>
  );
}
