import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { admin, useDishesAdmin, useIngredientsAdmin, useReferences, type DishRow, type IngredientRow, type Profile, type RefLine, type ReferenceRow } from "../../../api/admin";
import { searchDishes, searchIngredients, useAction } from "../../../api/business";
import { Autocomplete, Banner, Button, ErrorState, Field, Select, Sheet, Skeleton } from "../../../ui";
import { ActionError, DIET_OPTIONS, PageHeader } from "../../business/shared";
import { Pill, Tabs, TextArea } from "../shared";

const NUTRIENTS: [keyof Profile, string][] = [["energy_kcal", "Energy (kcal)"], ["protein_g", "Protein (g)"], ["carbs_g", "Carbs (g)"],
  ["fat_g", "Fat (g)"], ["fibre_g", "Fibre (g)"], ["sodium_mg", "Sodium (mg)"]];
const LICENCE = { pending: "Pending", cleared: "Cleared", reference_only: "Reference only" } as const;
const numOrNull = (s: string) => (s.trim() === "" ? null : Number(s));

function Ingredients() {
  const [q, setQ] = useState("");
  const [licence, setLicence] = useState("");
  const list = useIngredientsAdmin(q || undefined, licence || undefined);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [edit, setEdit] = useState<{ id?: string; name: string; category: string; state: "raw" | "cooked"; allergens: string; values: Record<string, string>; source: string; source_version: string; licence_status: Profile["licence_status"] } | null>(null);
  const keys = [["admin", "ingredients"], ["admin", "references"]];
  const bulk = useAction((status: string) => admin.setLicence([...selected], status), keys);
  const save = useAction(() => admin.saveIngredient({
    name: edit!.name, category: edit!.category || null, state: edit!.state,
    allergens: edit!.allergens.split(",").map((a) => a.trim()).filter(Boolean),
    profile: { ...Object.fromEntries(NUTRIENTS.map(([k]) => [k, numOrNull(edit!.values[k] ?? "")])) as Omit<Profile, "source" | "source_version" | "licence_status">,
      source: edit!.source, source_version: edit!.source_version || null, licence_status: edit!.licence_status },
  }, edit!.id), keys);
  const open = (i?: IngredientRow) => setEdit(i ? {
    id: i.id, name: i.name, category: i.category ?? "", state: i.state, allergens: i.allergens.join(", "),
    values: Object.fromEntries(NUTRIENTS.map(([k]) => [k, i.profile?.[k] == null ? "" : String(i.profile[k])])),
    source: i.profile?.source ?? "", source_version: i.profile?.source_version ?? "", licence_status: i.profile?.licence_status ?? "pending",
  } : { name: "", category: "", state: "raw", allergens: "", values: {}, source: "", source_version: "", licence_status: "pending" });
  const toggle = (id: string) => setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  return (
    <>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="w-64"><Field label="Search" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <div className="w-48"><Select label="Licence" value={licence} onChange={(e) => setLicence(e.target.value)}
          options={[{ value: "", label: "All" }, ...Object.entries(LICENCE).map(([v, l]) => ({ value: v, label: l }))]} /></div>
        <Button onClick={() => open()}><Plus size={18} /> Ingredient</Button>
        {selected.size > 0 && <>
          <Button variant="secondary" loading={bulk.isPending} onClick={() => bulk.mutate("cleared", { onSuccess: () => setSelected(new Set()) })}>Mark {selected.size} cleared</Button>
          <Button variant="ghost" onClick={() => bulk.mutate("pending", { onSuccess: () => setSelected(new Set()) })}>Mark pending</Button>
        </>}
      </div>
      <Banner tone="note" title="Only cleared data is used in published nutrition">Clear a source only once you have its licence or permission in writing.</Banner>
      <ActionError error={bulk.error} />
      {list.isPending ? <Skeleton className="mt-4 h-64" /> : list.isError ? <ErrorState error={list.error} /> : (
        <div className="card mt-4 max-h-[70vh] overflow-auto">
          <table className="dtable">
            <thead><tr><th><span className="sr-only">Select</span></th><th>Name</th><th>State</th><th>kcal/100 g</th><th>Allergens</th><th>Source</th><th>Licence</th></tr></thead>
            <tbody>{list.data.map((i) => (
              <tr key={i.id}>
                <td><input type="checkbox" aria-label={`Select ${i.name}`} className="size-5 accent-[var(--green-500)]" checked={selected.has(i.id)} onChange={() => toggle(i.id)} /></td>
                <td><button className="text-left font-medium hover:underline" onClick={() => open(i)}>{i.name}</button></td>
                <td>{i.state}</td><td>{i.profile?.energy_kcal ?? <span className="text-muted">unknown</span>}</td>
                <td className="text-sm">{i.allergens.join(", ") || "–"}</td>
                <td className="text-sm">{i.profile?.source}{i.profile?.source_version ? ` · ${i.profile.source_version}` : ""}</td>
                <td><Pill tone={i.profile?.licence_status === "cleared" ? "green" : "neutral"}>{LICENCE[i.profile?.licence_status ?? "pending"]}</Pill></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      <Sheet open={edit !== null} onOpenChange={(o) => { if (!o) { setEdit(null); save.reset(); } }} title={edit?.id ? "Edit ingredient" : "New ingredient"}>
        {edit && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); save.mutate(undefined, { onSuccess: () => setEdit(null) }); }}>
            <Field label="Name" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Category" value={edit.category} onChange={(e) => setEdit({ ...edit, category: e.target.value })} hint="e.g. pulse, poultry, fat" />
              <Select label="State" value={edit.state} onChange={(e) => setEdit({ ...edit, state: e.target.value as "raw" | "cooked" })} options={[{ value: "raw", label: "Raw" }, { value: "cooked", label: "Cooked" }]} />
            </div>
            <Field label="Allergens" hint="Comma separated: milk, egg, fish, crustacean, tree_nut, peanut, gluten, soy, sesame, mustard…" value={edit.allergens} onChange={(e) => setEdit({ ...edit, allergens: e.target.value })} />
            <p className="text-sm font-medium">Per 100 g. Leave blank when unknown; blank is never treated as zero.</p>
            <div className="grid grid-cols-2 gap-3">{NUTRIENTS.map(([k, l]) => (
              <Field key={k} label={l} inputMode="decimal" value={edit.values[k] ?? ""} onChange={(e) => setEdit({ ...edit, values: { ...edit.values, [k]: e.target.value } })} />
            ))}</div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Source" value={edit.source} onChange={(e) => setEdit({ ...edit, source: e.target.value })} hint="e.g. IFCT 2017" />
              <Field label="Source version" value={edit.source_version} onChange={(e) => setEdit({ ...edit, source_version: e.target.value })} />
            </div>
            <Select label="Licence status" value={edit.licence_status} onChange={(e) => setEdit({ ...edit, licence_status: e.target.value as Profile["licence_status"] })}
              options={Object.entries(LICENCE).map(([v, l]) => ({ value: v, label: l }))} />
            <ActionError error={save.error} />
            <Button type="submit" block loading={save.isPending} disabled={!edit.name.trim() || !edit.source.trim()}>Save</Button>
          </form>
        )}
      </Sheet>
    </>
  );
}

function Dishes() {
  const [q, setQ] = useState("");
  const list = useDishesAdmin(q || undefined);
  const [edit, setEdit] = useState<(Omit<DishRow, "id" | "reference_recipes"> & { id?: string }) | null>(null);
  const save = useAction(() => { const { id, ...body } = edit!; return admin.saveDish(body, id); }, [["admin", "dishes"]]);
  return (
    <>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="w-64"><Field label="Search" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <Button onClick={() => setEdit({ name: "", cuisine: null, region: null, diet_class: null, expected_kcal_100g_low: null, expected_kcal_100g_high: null, aliases: [], variants: [] })}><Plus size={18} /> Dish</Button>
      </div>
      {list.isPending ? <Skeleton className="h-64" /> : list.isError ? <ErrorState error={list.error} /> : (
        <div className="card max-h-[70vh] overflow-auto">
          <table className="dtable">
            <thead><tr><th>Dish</th><th>Cuisine</th><th>Expected kcal/100 g</th><th>Aliases</th><th>Reference recipes</th></tr></thead>
            <tbody>{list.data.map((d) => (
              <tr key={d.id}>
                <td><button className="text-left font-medium hover:underline" onClick={() => setEdit(d)}>{d.name}</button></td>
                <td>{d.cuisine ?? "–"}</td><td>{d.expected_kcal_100g_low ?? "?"} to {d.expected_kcal_100g_high ?? "?"}</td>
                <td className="text-sm">{d.aliases.map((a) => a.alias).join(", ") || "–"}</td><td>{d.reference_recipes}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      <Sheet open={edit !== null} onOpenChange={(o) => { if (!o) { setEdit(null); save.reset(); } }} title={edit?.id ? "Edit dish" : "New dish"}>
        {edit && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); save.mutate(undefined, { onSuccess: () => setEdit(null) }); }}>
            <Field label="Name" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Cuisine" value={edit.cuisine ?? ""} onChange={(e) => setEdit({ ...edit, cuisine: e.target.value || null })} />
              <Select label="Diet" value={edit.diet_class ?? ""} onChange={(e) => setEdit({ ...edit, diet_class: e.target.value || null })} options={DIET_OPTIONS} />
              <Field label="Expected kcal/100 g, low" inputMode="decimal" value={edit.expected_kcal_100g_low ?? ""} onChange={(e) => setEdit({ ...edit, expected_kcal_100g_low: numOrNull(e.target.value) })} />
              <Field label="Expected kcal/100 g, high" inputMode="decimal" value={edit.expected_kcal_100g_high ?? ""} onChange={(e) => setEdit({ ...edit, expected_kcal_100g_high: numOrNull(e.target.value) })} />
            </div>
            <p className="text-xs text-muted">The expected range is used only for plausibility checks; a dish holds no nutrition.</p>
            <p className="text-sm font-medium">Aliases</p>
            {edit.aliases.map((a, i) => (
              <div key={i} className="flex gap-2">
                <input aria-label="Alias" value={a.alias} onChange={(e) => setEdit({ ...edit, aliases: edit.aliases.map((x, j) => (j === i ? { ...x, alias: e.target.value } : x)) })} className="min-h-11 flex-1 rounded-xl border border-line bg-card px-3" />
                <input aria-label="Language" value={a.language ?? ""} placeholder="hi" onChange={(e) => setEdit({ ...edit, aliases: edit.aliases.map((x, j) => (j === i ? { ...x, language: e.target.value || null } : x)) })} className="min-h-11 w-16 rounded-xl border border-line bg-card px-2" />
                <button type="button" aria-label="Remove alias" className="grid size-11 place-items-center rounded-full text-muted hover:bg-chip-green" onClick={() => setEdit({ ...edit, aliases: edit.aliases.filter((_, j) => j !== i) })}><Trash2 size={16} /></button>
              </div>
            ))}
            <Button type="button" variant="ghost" onClick={() => setEdit({ ...edit, aliases: [...edit.aliases, { alias: "", language: null, transliteration: null }] })}><Plus size={16} /> Alias</Button>
            <ActionError error={save.error} />
            <Button type="submit" block loading={save.isPending} disabled={!edit.name.trim()}>Save</Button>
          </form>
        )}
      </Sheet>
    </>
  );
}

type RefEdit = Omit<ReferenceRow, "energy_100g" | "checks" | "licence_cleared" | "id"> & { id?: string; dishName: string; names: Record<number, string> };

function References() {
  const list = useReferences();
  const [edit, setEdit] = useState<RefEdit | null>(null);
  const save = useAction(() => {
    const { id, dishName: _d, names: _n, ...body } = edit!;
    return admin.saveReference(body, id);
  }, [["admin", "references"]]);
  const subs = list.data ?? [];
  const nameOf = (l: RefLine) => (l.sub_reference_id ? `Sub-recipe: ${subs.find((s) => s.id === l.sub_reference_id)?.name ?? "?"}` : undefined);
  return (
    <>
      <div className="mb-4"><Button onClick={() => setEdit({ name: "", canonical_dish_id: null, region: null, cooking_method: null, cooked_yield_g: 1000, serving_weight_g: null, spread: null, notes: null, lines: [], dishName: "", names: {} })}><Plus size={18} /> Reference recipe</Button></div>
      {list.isPending ? <Skeleton className="h-64" /> : list.isError ? <ErrorState error={list.error} /> : (
        <div className="card max-h-[70vh] overflow-auto">
          <table className="dtable">
            <thead><tr><th>Name</th><th>Region</th><th>Energy</th><th>Checks</th><th>Data</th></tr></thead>
            <tbody>{list.data.map((r) => (
              <tr key={r.id}>
                <td><button className="text-left font-medium hover:underline" onClick={() => setEdit({ ...r, dishName: "", names: {} })}>{r.name}</button></td>
                <td>{r.region ?? "All regions"}</td><td>{r.energy_100g ?? "–"}</td>
                <td>{r.checks.length ? <Pill tone="red">{r.checks.length} to check</Pill> : <Pill tone="green">OK</Pill>}</td>
                <td><Pill tone={r.licence_cleared ? "green" : "neutral"}>{r.licence_cleared ? "Cleared" : "Not cleared"}</Pill></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      <Sheet open={edit !== null} onOpenChange={(o) => { if (!o) { setEdit(null); save.reset(); } }} title={edit?.id ? "Edit reference recipe" : "New reference recipe"}>
        {edit && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); save.mutate(undefined, { onSuccess: () => setEdit(null) }); }}>
            <Field label="Name" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
            <Autocomplete label="Dish" placeholder="Leave empty for a base (sub-recipe)" value={edit.dishName} search={searchDishes} onPick={(h) => setEdit({ ...edit, canonical_dish_id: h.id, dishName: h.name })} />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Region" hint="Blank = all regions" value={edit.region ?? ""} onChange={(e) => setEdit({ ...edit, region: e.target.value || null })} />
              <Field label="Cooking method" value={edit.cooking_method ?? ""} onChange={(e) => setEdit({ ...edit, cooking_method: e.target.value || null })} />
              <Field label="Cooked yield (g)" inputMode="decimal" value={edit.cooked_yield_g} onChange={(e) => setEdit({ ...edit, cooked_yield_g: Number(e.target.value) })} />
              <Field label="Typical serving (g)" inputMode="decimal" value={edit.serving_weight_g ?? ""} onChange={(e) => setEdit({ ...edit, serving_weight_g: numOrNull(e.target.value) })} />
              <Field label="Own spread (0 to 1)" hint="Only if wider than the default" inputMode="decimal" value={edit.spread ?? ""} onChange={(e) => setEdit({ ...edit, spread: numOrNull(e.target.value) })} />
            </div>
            <p className="text-sm font-medium">Ingredients (grams)</p>
            {edit.lines.map((l, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className="flex-1">{l.sub_reference_id ? <span className="text-sm">{nameOf(l)}</span> :
                  <Autocomplete value={edit.names[i] ?? (l.ingredient_id ? "(saved ingredient)" : "")} search={searchIngredients}
                    onPick={(h) => setEdit({ ...edit, names: { ...edit.names, [i]: h.name }, lines: edit.lines.map((x, j) => (j === i ? { ...x, ingredient_id: h.id } : x)) })} />}</div>
                <input aria-label="Grams" inputMode="decimal" value={l.quantity_g} onChange={(e) => setEdit({ ...edit, lines: edit.lines.map((x, j) => (j === i ? { ...x, quantity_g: Number(e.target.value) } : x)) })} className="min-h-11 w-20 rounded-xl border border-line bg-card px-2" />
                <button type="button" aria-label="Remove line" className="grid size-11 place-items-center rounded-full text-muted hover:bg-chip-green" onClick={() => setEdit({ ...edit, lines: edit.lines.filter((_, j) => j !== i) })}><Trash2 size={16} /></button>
              </div>
            ))}
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="ghost" onClick={() => setEdit({ ...edit, lines: [...edit.lines, { quantity_g: 100 }] })}><Plus size={16} /> Ingredient</Button>
              <select aria-label="Add a reference sub-recipe" className="min-h-11 rounded-xl border border-line bg-card px-2 text-sm" value=""
                onChange={(e) => e.target.value && setEdit({ ...edit, lines: [...edit.lines, { sub_reference_id: e.target.value, quantity_g: 100 }] })}>
                <option value="">+ Sub-recipe…</option>{subs.filter((s) => s.id !== edit.id).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <TextArea label="Notes" value={edit.notes ?? ""} onChange={(notes) => setEdit({ ...edit, notes: notes || null })} />
            <ActionError error={save.error} />
            <Button type="submit" block loading={save.isPending} disabled={!edit.name.trim() || edit.lines.length === 0}>Save</Button>
          </form>
        )}
      </Sheet>
    </>
  );
}

export default function ReferenceData() {
  const [tab, setTab] = useState<"dishes" | "ingredients" | "references">("ingredients");
  return (
    <>
      <PageHeader title="Reference data" subtitle="Canonical dishes, ingredients with their nutrient sources, and the reference recipes behind Estimated values." />
      <Tabs value={tab} onChange={setTab} tabs={[["ingredients", "Ingredients"], ["dishes", "Dishes"], ["references", "Reference recipes"]]} />
      {tab === "ingredients" ? <Ingredients /> : tab === "dishes" ? <Dishes /> : <References />}
    </>
  );
}
