import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { ApiError } from "../../../api/client";
import { calls, searchDishes, searchIngredients, useRecipe, useRecipes, useVersions, useAction,
  type LineInput, type NutrientMap, type Preview, type Unit, type Version, type VersionInput } from "../../../api/business";
import { Autocomplete, Banner, Button, Card, Chip, ErrorState, Field, Select, Skeleton, TrustLabel } from "../../../ui";
import { useBiz } from "../context";
import { ActionError, METHOD_OPTIONS, PageHeader } from "../shared";

interface Row {
  key: number; kind: "ingredient" | "sub"; ingredient_id: string | null; sub_recipe_id: string | null; name: string;
  quantity: string; unit: Unit; fried: boolean; oil_retained: string;
}
const UNITS: Unit[] = ["g", "kg", "ml", "l", "tsp", "tbsp", "cup", "katori"];
let seq = 1;
const newRow = (kind: Row["kind"] = "ingredient"): Row =>
  ({ key: seq++, kind, ingredient_id: null, sub_recipe_id: null, name: "", quantity: "", unit: "g", fried: false, oil_retained: "" });

function fromVersion(v: Version): Row[] {
  return v.lines.map((l) => ({
    key: seq++, kind: l.sub_recipe_id ? "sub" : "ingredient", ingredient_id: l.ingredient_id, sub_recipe_id: l.sub_recipe_id,
    name: l.name, quantity: String(l.entered_quantity ?? l.quantity_g), unit: l.entered_unit ?? "g",
    fried: l.oil_retained_g != null, oil_retained: l.oil_retained_g != null ? String(l.oil_retained_g) : "",
  }));
}

/** Builds the request body; returns null while the form is incomplete. No nutrition is calculated here. */
function toInput(rows: Row[], method: string, yieldG: string, servings: string): VersionInput | null {
  const lines: LineInput[] = [];
  for (const r of rows) {
    const q = Number(r.quantity);
    if (!(q > 0) || (r.kind === "ingredient" ? !r.ingredient_id : !r.sub_recipe_id)) return null;
    if (r.fried && r.oil_retained.trim() === "") return null;
    lines.push(r.kind === "ingredient"
      ? { ingredient_id: r.ingredient_id, quantity: q, unit: r.unit, oil_retained_g: r.fried ? Number(r.oil_retained) : null }
      : { sub_recipe_id: r.sub_recipe_id, quantity: q, unit: r.unit });
  }
  const y = Number(yieldG);
  if (!lines.length || !(y > 0)) return null;
  return { cooking_method: method || null, cooked_yield_g: y, servings_per_batch: servings ? Number(servings) : null, lines };
}

const SHOWN = [["energy_kcal", "Energy"], ["protein_g", "Protein"], ["carbs_g", "Carbs"], ["fat_g", "Fat"], ["fibre_g", "Fibre"], ["sodium_mg", "Sodium"]] as const;

function NutritionTable({ values }: { values: NutrientMap | null }) {
  if (!values) return <p className="text-sm text-muted">Add a serving weight to see per-serving values.</p>;
  return (
    <dl className="divide-y divide-line text-sm">
      {SHOWN.map(([k, label]) => (
        <div key={k} className="flex justify-between gap-3 py-2">
          <dt className="text-muted">{label}</dt>
          <dd className={k === "energy_kcal" ? "font-semibold text-orange-text" : "font-medium"}>{values[k]?.display ?? "Not available"}</dd>
        </div>
      ))}
    </dl>
  );
}

function VersionChecks({ version }: { version: Version }) {
  const { business } = useBiz();
  const [text, setText] = useState("");
  const [sent, setSent] = useState(false);
  const flag = version.checks.find((c) => c.id && c.resolution === "open");
  const send = useAction(() => calls.dispute(business.id, flag!.id!, text), []);
  return (
    <div className="mt-2 space-y-2">
      {version.checks.map((c) => (
        <Banner key={c.id ?? c.rule} tone={version.status === "returned" ? "problem" : "note"} title={c.message}>
          {c.resolution_note ? <>Reviewer: {c.resolution_note}</> : version.status === "held" ? "Waiting for review." : null}
        </Banner>
      ))}
      {version.status === "held" && flag && (sent ? <p className="text-green-text">Sent to the reviewer.</p> : (
        <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); send.mutate(undefined, { onSuccess: () => setSent(true) }); }}>
          <div className="min-w-60 flex-1"><Field label="Explain to the reviewer" value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. We really use 300 g ghee per batch" /></div>
          <Button type="submit" variant="secondary" loading={send.isPending} disabled={text.trim().length < 5}>Send</Button>
          <ActionError error={send.error} />
        </form>
      ))}
    </div>
  );
}

export default function RecipeBuilder() {
  const { recipeId = "" } = useParams();
  const { business } = useBiz();
  const recipe = useRecipe(business.id, recipeId);
  const versions = useVersions(business.id, recipeId);
  const allRecipes = useRecipes(business.id);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [method, setMethod] = useState("simmer");
  const [yieldG, setYieldG] = useState("");
  const [servings, setServings] = useState("");
  const [servingG, setServingG] = useState("");
  const [dish, setDish] = useState<{ id: string | null; name: string }>({ id: null, name: "" });
  const [view, setView] = useState<"per_serving" | "per_100g" | "per_batch">("per_100g");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewError, setPreviewError] = useState<unknown>(null);
  const [result, setResult] = useState<Version | null>(null);
  const pending = useRef(0);
  const publish = useAction((v: VersionInput) => calls.publish(business.id, recipeId, v),
    [["versions", recipeId], ["recipe", recipeId], ["recipes", business.id], ["menu"], ["dashboard", business.id]]);

  // Start from the latest version, if any.
  useEffect(() => {
    if (rows !== null || !versions.data) return;
    const last = versions.data[versions.data.length - 1];
    if (last) {
      setRows(fromVersion(last)); setMethod(last.cooking_method ?? ""); setYieldG(String(last.cooked_yield_g));
      setServings(last.servings_per_batch ? String(last.servings_per_batch) : "");
      if (last.nutrition?.serving_weight_g) setServingG(String(last.nutrition.serving_weight_g));
    } else setRows([newRow()]);
  }, [versions.data, rows]);

  const input = useMemo(() => (rows ? toInput(rows, method, yieldG, servings) : null), [rows, method, yieldG, servings]);

  // Live preview: the server calculates after a short pause in typing.
  useEffect(() => {
    if (!input) { setPreview(null); return; }
    const n = ++pending.current;
    const t = setTimeout(() => {
      calls.preview(business.id, { ...input, serving_weight_g: servingG ? Number(servingG) : null, canonical_dish_id: dish.id }, recipeId)
        .then((p) => { if (n === pending.current) { setPreview(p); setPreviewError(null); } })
        .catch((e) => { if (n === pending.current) { setPreview(null); setPreviewError(e); } });
    }, 450);
    return () => clearTimeout(t);
  }, [input, servingG, dish.id, business.id, recipeId]);

  if (recipe.isPending || versions.isPending || rows === null) return <Skeleton className="h-96" />;
  if (recipe.isError) return <ErrorState error={recipe.error} onRetry={() => recipe.refetch()} />;
  const r = recipe.data;
  const subRecipes = (allRecipes.data ?? []).filter((x) => x.is_sub_recipe && x.id !== r.id && x.published_version_id);
  const update = (key: number, patch: Partial<Row>) => setRows((rs) => rs!.map((x) => (x.key === key ? { ...x, ...patch } : x)));
  const values = preview ? (view === "per_serving" ? preview.nutrition.per_serving : preview.nutrition[view]) : null;
  const versionList = versions.data ?? [];

  return (
    <>
      <Link to="/business/recipes" className="mb-2 inline-flex min-h-11 items-center gap-1 text-sm text-muted hover:text-text"><ArrowLeft size={16} /> Recipes</Link>
      <PageHeader title={r.name}
        subtitle={`${r.is_sub_recipe ? "Sub-recipe" : "Dish recipe"} · ${r.scope === "branch" ? "Branch override" : "Shared by all branches"}${r.latest_version ? ` · version ${r.latest_version} (${r.latest_status})` : " · not published yet"}`} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-6">
          <Card className="grid gap-4 sm:grid-cols-4">
            <Select label="Cooking method" value={method} onChange={(e) => setMethod(e.target.value)} options={[{ value: "", label: "Not set" }, ...METHOD_OPTIONS]} />
            <Field label="Cooked yield (g)" hint="Whole batch, after cooking" inputMode="decimal" value={yieldG} onChange={(e) => setYieldG(e.target.value)} />
            <Field label="Servings per batch" inputMode="decimal" value={servings} onChange={(e) => setServings(e.target.value)} />
            <Field label="Serving weight (g)" hint="For the preview" inputMode="decimal" value={servingG} onChange={(e) => setServingG(e.target.value)} />
          </Card>

          <Card className="overflow-x-auto p-0">
            <div className="flex items-center justify-between px-5 pt-5">
              <h2 className="font-display text-lg font-bold">Ingredients</h2>
              <p className="text-xs text-muted">Household measures are converted to grams on our side (approximate).</p>
            </div>
            <table className="dtable mt-3 min-w-[640px]">
              <thead><tr><th className="w-[42%]">Ingredient</th><th>Quantity</th><th>Unit</th><th>Frying oil</th><th className="sr-only">Remove</th></tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.key}>
                    <td>
                      {row.kind === "ingredient" ? (
                        <Autocomplete value={row.name} placeholder="Search, e.g. ghee" search={searchIngredients}
                          onPick={(h) => update(row.key, { ingredient_id: h.id, name: h.name })}
                          render={(h) => <span>{h.name} <span className="text-xs text-muted">{h.state}{h.allergens.length ? ` · ${h.allergens.join(", ")}` : ""}{h.data_complete ? "" : " · some values unknown"}</span></span>} />
                      ) : (
                        <Select aria-label="Sub-recipe" value={row.sub_recipe_id ?? ""} onChange={(e) => update(row.key, { sub_recipe_id: e.target.value || null })}
                          options={[{ value: "", label: subRecipes.length ? "Choose a sub-recipe" : "No published sub-recipes yet" }, ...subRecipes.map((s) => ({ value: s.id, label: s.name }))]} />
                      )}
                    </td>
                    <td><input aria-label="Quantity" inputMode="decimal" value={row.quantity} onChange={(e) => update(row.key, { quantity: e.target.value })}
                      className="min-h-11 w-24 rounded-[var(--radius-control)] border border-line bg-card px-3 outline-none focus:border-green" /></td>
                    <td><select aria-label="Unit" value={row.unit} onChange={(e) => update(row.key, { unit: e.target.value as Unit })}
                      className="min-h-11 rounded-[var(--radius-control)] border border-line bg-card px-2 outline-none focus:border-green">
                      {(row.kind === "sub" ? ["g", "kg"] : UNITS).map((u) => <option key={u}>{u}</option>)}</select></td>
                    <td>{row.kind === "ingredient" && (
                      <div className="flex items-center gap-2">
                        <input type="checkbox" aria-label="This is frying oil" className="size-5 accent-[var(--green-500)]" checked={row.fried}
                          onChange={(e) => update(row.key, { fried: e.target.checked })} />
                        {row.fried && <input aria-label="Grams of oil that stay in the food" placeholder="g kept" inputMode="decimal" value={row.oil_retained}
                          onChange={(e) => update(row.key, { oil_retained: e.target.value })}
                          className="min-h-11 w-20 rounded-[var(--radius-control)] border border-line bg-card px-2 outline-none focus:border-green" />}
                      </div>)}
                    </td>
                    <td className="text-right"><button aria-label="Remove line" onClick={() => setRows(rows.filter((x) => x.key !== row.key))}
                      className="grid size-11 place-items-center rounded-full text-muted hover:bg-chip-green"><Trash2 size={18} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex flex-wrap gap-2 p-4">
              <Button variant="secondary" onClick={() => setRows([...rows, newRow()])}><Plus size={18} /> Ingredient</Button>
              {!r.is_sub_recipe && <Button variant="ghost" onClick={() => setRows([...rows, newRow("sub")])}><Plus size={18} /> Sub-recipe</Button>}
            </div>
          </Card>

          <Card>
            <Autocomplete label="Dish type, for checks" placeholder="e.g. Dal Tadka" value={dish.name} search={searchDishes}
              onPick={(h) => setDish({ id: h.id, name: h.name })} />
            <p className="mt-2 text-xs text-muted">Optional. If a menu item linked to this recipe already names its dish, that is used.</p>
          </Card>

          <Card>
            <h2 className="font-display text-lg font-bold">Version history</h2>
            {versionList.length === 0 ? <p className="mt-2 text-sm text-muted">No versions yet. Every publish creates a new version; old ones are kept.</p> : (
              <ul className="mt-3 divide-y divide-line">
                {[...versionList].reverse().map((v) => (
                  <li key={v.id} className="py-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">Version {v.version_number}</span>
                      <span className="text-muted">{new Date(v.declared_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</span>
                      <span>{v.nutrition?.per_100g.energy_kcal?.display ?? "–"} per 100 g</span>
                      <Chip tone={v.status === "published" ? "green" : "neutral"} selected={v.status === "published"}>
                        {v.status === "held" ? "Held for review" : v.status === "returned" ? "Returned" : v.status}</Chip>
                    </div>
                    {v.status !== "published" && v.checks.length > 0 && <VersionChecks version={v} />}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <Card>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-display text-lg font-bold">Live nutrition</h2>
              {preview && <TrustLabel kind={preview.nutrition.trust.label} />}
            </div>
            <div className="mb-3 flex gap-1" role="tablist">
              {([["per_serving", "Serving"], ["per_100g", "100 g"], ["per_batch", "Batch"]] as const).map(([k, l]) => (
                <Chip key={k} role="tab" aria-selected={view === k} selected={view === k} tone="neutral" onClick={() => setView(k)}>{l}</Chip>
              ))}
            </div>
            {preview ? <NutritionTable values={values} /> : previewError ? <ActionError error={previewError} /> :
              <p className="text-sm text-muted">Add ingredients with quantities and the cooked yield to see nutrition.</p>}
            {preview && preview.nutrition.allergens.length > 0 && <p className="mt-3 text-sm text-danger-text">Contains: {preview.nutrition.allergens.join(", ")}</p>}
          </Card>

          {preview?.checks.map((c) => <Banner key={c.rule} tone="problem" title="Check this before publishing">{c.message}</Banner>)}
          {preview && !preview.licence_cleared && <Banner tone="note" title="Some ingredient data isn't cleared yet">You can preview, but publishing will be held until the data is cleared.</Banner>}

          {result && (result.status === "published"
            ? <Banner tone="success" title={`Version ${result.version_number} published`}>Diners now see the Restaurant-declared label on dishes using this recipe.</Banner>
            : <Banner tone="problem" title={`Version ${result.version_number} held for review`}>{result.checks.map((c) => c.message).join(" ")}</Banner>)}
          <ActionError error={publish.error instanceof ApiError ? publish.error : null} />
          <Button block loading={publish.isPending} disabled={!input}
            onClick={() => input && publish.mutate(input, { onSuccess: (v) => setResult(v) })}>
            Publish version {(r.latest_version ?? 0) + 1}
          </Button>
          <p className="text-xs text-muted">Publishing creates a new version and never changes earlier ones. If a check fails, the version is held for review instead.</p>
        </aside>
      </div>
    </>
  );
}
