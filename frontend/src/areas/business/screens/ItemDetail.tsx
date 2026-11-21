import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Plus, RefreshCw, Trash2 } from "lucide-react";
import { calls, searchIngredients, useAction, useGroups, useMenu, useServings } from "../../../api/business";
import { Autocomplete, Banner, Button, Card, Chip, ErrorState, Field, Select, Sheet, Skeleton } from "../../../ui";
import { useBiz } from "../context";
import { ActionError, METHOD_OPTIONS, NutritionCell, PageHeader } from "../shared";

type ModDraft = { group: string; label: string; kind: "delta" | "method_swap"; ingredient_id: string; ingredient: string;
  delta_g: string; cooking_method: string; oil_retained_g: string; cooked_yield_g: string };

export default function ItemDetail() {
  const { itemId = "" } = useParams();
  const { business, branchId } = useBiz();
  const menu = useMenu(business.id, branchId);
  const servings = useServings(business.id, itemId);
  const groups = useGroups(business.id, itemId);
  const keys = [["servings", itemId], ["groups", itemId], ["menu", business.id, branchId]];
  const [serving, setServing] = useState({ label: "", weight_g: "", unit: "plate" });
  const [groupName, setGroupName] = useState<string | null>(null);
  const [mod, setMod] = useState<ModDraft | null>(null);
  const [confirmed, setConfirmed] = useState<string | null>(null);
  const addServing = useAction(() => calls.addServing(business.id, itemId, { label: serving.label, weight_g: Number(serving.weight_g), unit: serving.unit, is_default: false }), keys);
  const delServing = useAction((id: string) => calls.deleteServing(business.id, id), keys);
  const addGroup = useAction((name: string) => calls.addGroup(business.id, itemId, { name, exclusive: true }), keys);
  const addMod = useAction((m: ModDraft) => calls.addModifier(business.id, m.group, m.kind === "delta"
    ? { label: m.label, kind: "delta", deltas: [{ ingredient_id: m.ingredient_id, delta_g: Number(m.delta_g) }] }
    : { label: m.label, kind: "method_swap", cooking_method: m.cooking_method, oil_retained_g: m.oil_retained_g === "" ? null : Number(m.oil_retained_g),
        cooked_yield_g: m.cooked_yield_g === "" ? null : Number(m.cooked_yield_g) }), keys);
  const delMod = useAction((id: string) => calls.deleteModifier(business.id, id), keys);
  const reconfirm = useAction(() => calls.reconfirm(itemId), keys);

  const item = menu.data && [...menu.data.categories.flatMap((c) => c.items), ...menu.data.uncategorised].find((i) => i.id === itemId);
  if (menu.isPending) return <Skeleton className="h-96" />;
  if (menu.isError) return <ErrorState error={menu.error} onRetry={() => menu.refetch()} />;
  if (!item) return <ErrorState error={new Error("not found")} />;

  return (
    <>
      <Link to="/business/menu" className="mb-2 inline-flex min-h-11 items-center gap-1 text-sm text-muted hover:text-text"><ArrowLeft size={16} /> Menu</Link>
      <PageHeader title={item.display_name} subtitle={item.recipe_name ? `Recipe: ${item.recipe_name}` : "No recipe linked yet"}
        actions={item.current_recipe_version_id ? <Button variant="secondary" loading={reconfirm.isPending}
          onClick={() => reconfirm.mutate(undefined, { onSuccess: (r) => setConfirmed(new Date(r.expires_at).toLocaleDateString("en-IN", { dateStyle: "medium" })) })}>
          <RefreshCw size={18} /> Recipe unchanged: reconfirm</Button> : undefined} />
      {confirmed && <div className="mb-4"><Banner tone="success" title="Reconfirmed">Next reminder before {confirmed}.</Banner></div>}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="space-y-4">
          <h2 className="font-display text-lg font-bold">What diners see</h2>
          <NutritionCell n={item.nutrition} />
          <p className="text-sm text-muted">{item.nutrition.serving_label ?? "Add a serving size to show per-serving values."}</p>
          <p className="text-sm text-danger-text">{item.nutrition.allergens.display}</p>
        </Card>

        <Card className="space-y-4">
          <h2 className="font-display text-lg font-bold">Servings</h2>
          {servings.data?.length ? (
            <ul className="divide-y divide-line">
              {servings.data.map((s) => (
                <li key={s.id} className="flex items-center justify-between py-2 text-sm">
                  <span>{s.label} · {s.weight_g} g · {s.unit}{s.is_default && <span className="ml-2 text-green-text">default</span>}</span>
                  <button aria-label={`Remove ${s.label}`} className="grid size-11 place-items-center rounded-full text-muted hover:bg-chip-green"
                    onClick={() => delServing.mutate(s.id)}><Trash2 size={18} /></button>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-muted">No servings yet. Weigh a typical portion.</p>}
          <form className="grid grid-cols-[1fr_96px_120px] items-end gap-2" onSubmit={(e) => { e.preventDefault(); addServing.mutate(undefined, { onSuccess: () => setServing({ label: "", weight_g: "", unit: "plate" }) }); }}>
            <Field label="Label" placeholder="Full plate" value={serving.label} onChange={(e) => setServing({ ...serving, label: e.target.value })} />
            <Field label="Grams" inputMode="decimal" value={serving.weight_g} onChange={(e) => setServing({ ...serving, weight_g: e.target.value })} />
            <Select label="Unit" value={serving.unit} onChange={(e) => setServing({ ...serving, unit: e.target.value })}
              options={["plate", "piece", "katori", "bowl", "glass", "portion"].map((u) => ({ value: u, label: u }))} />
            <Button type="submit" className="col-span-3" variant="secondary" loading={addServing.isPending} disabled={!serving.label || !(Number(serving.weight_g) > 0)}><Plus size={18} /> Add serving</Button>
          </form>
          <ActionError error={addServing.error} />
        </Card>
      </div>

      <Card className="mt-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg font-bold">Options diners can pick</h2>
          <Button variant="secondary" onClick={() => setGroupName("")}><Plus size={18} /> Option group</Button>
        </div>
        {groups.data?.length ? groups.data.map((g) => (
          <div key={g.id} className="rounded-2xl border border-line p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="font-semibold">{g.name} <span className="text-xs font-normal text-muted">{g.exclusive ? "pick one" : "pick any"}</span></p>
              <Button variant="ghost" onClick={() => setMod({ group: g.id, label: "", kind: "delta", ingredient_id: "", ingredient: "", delta_g: "", cooking_method: "grill", oil_retained_g: "0", cooked_yield_g: "" })}><Plus size={16} /> Option</Button>
            </div>
            {g.modifiers.length === 0 ? <p className="text-sm text-muted">No options yet, e.g. “No butter” or “Grilled instead of fried”.</p> : (
              <ul className="flex flex-wrap gap-2">
                {g.modifiers.map((m) => (
                  <li key={m.id} className="inline-flex items-center gap-1 rounded-full border border-line py-1 pl-3 pr-1 text-sm">
                    {m.label}{m.energy_change_display && <span className="text-orange-text"> · {m.energy_change_display}</span>}
                    <button aria-label={`Remove ${m.label}`} className="grid size-9 place-items-center rounded-full text-muted hover:bg-chip-green" onClick={() => delMod.mutate(m.id)}><Trash2 size={14} /></button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )) : <p className="text-sm text-muted">Options change the nutrition live for diners, such as less oil or no butter.</p>}
      </Card>

      <Sheet open={groupName !== null} onOpenChange={(o) => !o && setGroupName(null)} title="New option group">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); addGroup.mutate(groupName ?? "", { onSuccess: () => setGroupName(null) }); }}>
          <Field label="Group name" placeholder="e.g. Butter" value={groupName ?? ""} onChange={(e) => setGroupName(e.target.value)} autoFocus />
          <p className="text-sm text-muted">Diners can pick one option from a group.</p>
          <Button type="submit" block loading={addGroup.isPending} disabled={!groupName?.trim()}>Add group</Button>
        </form>
      </Sheet>

      <Sheet open={mod !== null} onOpenChange={(o) => { if (!o) { setMod(null); addMod.reset(); } }} title="New option">
        {mod && (
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); addMod.mutate(mod, { onSuccess: () => setMod(null) }); }}>
            <Field label="Label diners see" placeholder="No butter" value={mod.label} onChange={(e) => setMod({ ...mod, label: e.target.value })} autoFocus />
            <div className="flex gap-2">
              <Chip tone="neutral" selected={mod.kind === "delta"} onClick={() => setMod({ ...mod, kind: "delta" })}>Change an ingredient</Chip>
              <Chip tone="neutral" selected={mod.kind === "method_swap"} onClick={() => setMod({ ...mod, kind: "method_swap" })}>Change cooking method</Chip>
            </div>
            {mod.kind === "delta" ? (
              <>
                <Autocomplete label="Ingredient" value={mod.ingredient} search={searchIngredients} onPick={(h) => setMod({ ...mod, ingredient_id: h.id, ingredient: h.name })} />
                <Field label="Grams per serving" hint="Negative removes, e.g. -10 for no butter" inputMode="decimal" value={mod.delta_g} onChange={(e) => setMod({ ...mod, delta_g: e.target.value })} />
              </>
            ) : (
              <>
                <Select label="New method" value={mod.cooking_method} onChange={(e) => setMod({ ...mod, cooking_method: e.target.value })} options={METHOD_OPTIONS} />
                <Field label="Oil kept in the food, per frying line (g)" inputMode="decimal" value={mod.oil_retained_g} onChange={(e) => setMod({ ...mod, oil_retained_g: e.target.value })} />
                <Field label="New cooked yield for the batch (g)" hint="Optional" inputMode="decimal" value={mod.cooked_yield_g} onChange={(e) => setMod({ ...mod, cooked_yield_g: e.target.value })} />
              </>
            )}
            <ActionError error={addMod.error} />
            <Button type="submit" block loading={addMod.isPending} disabled={!mod.label.trim()}>Add option</Button>
          </form>
        )}
      </Sheet>
    </>
  );
}
