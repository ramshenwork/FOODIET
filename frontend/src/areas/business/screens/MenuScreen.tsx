import { useState } from "react";
import { Link } from "react-router-dom";
import { FolderPlus, Plus, Settings2, Trash2, Upload } from "lucide-react";
import { calls, searchDishes, useAction, useMenu, useRecipes, type MenuItem } from "../../../api/business";
import { Autocomplete, Button, Chip, EmptyState, ErrorState, Field, Select, Sheet, Skeleton } from "../../../ui";
import { useBiz } from "../context";
import { ActionError, BranchPicker, DIET_LABEL, DIET_OPTIONS, NutritionCell, PageHeader } from "../shared";

type Draft = {
  id?: string; display_name: string; price_inr: string; diet_class: string; category_id: string; canonical_dish_id: string | null;
  canonical_dish_name: string; recipe_id: string; status: string; description: string; diet_tags: string[];
};
const blank: Draft = { display_name: "", price_inr: "", diet_class: "", category_id: "", canonical_dish_id: null, canonical_dish_name: "", recipe_id: "", status: "draft", description: "", diet_tags: [] };

export default function MenuScreen() {
  const { business, branchId } = useBiz();
  const menu = useMenu(business.id, branchId);
  const recipes = useRecipes(business.id);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [newCat, setNewCat] = useState<string | null>(null);
  const keys = [["menu", business.id, branchId], ["dashboard", business.id], ["recipes", business.id]];
  const save = useAction((d: Draft) => {
    const body = {
      display_name: d.display_name, price_inr: d.price_inr === "" ? null : Number(d.price_inr), diet_class: d.diet_class || null,
      category_id: d.category_id || null, canonical_dish_id: d.canonical_dish_id, recipe_id: d.recipe_id || null,
      description: d.description || null, diet_tags: d.diet_tags,
    };
    return d.id ? calls.updateItem(business.id, d.id, { ...body, status: d.status }) : calls.addItem(business.id, { ...body, branch_id: branchId });
  }, keys);
  const del = useAction((id: string) => calls.deleteItem(business.id, id), keys);
  const addCat = useAction((name: string) => calls.addCategory(business.id, branchId, name), keys);
  const toggle = useAction((i: MenuItem) => calls.updateItem(business.id, i.id, {
    display_name: i.display_name, price_inr: i.price_inr, diet_class: i.diet_class, category_id: i.category_id,
    canonical_dish_id: i.canonical_dish_id, recipe_id: i.recipe_id, description: i.description, diet_tags: i.diet_tags,
    status: i.status === "published" ? "hidden" : "published",
  }), keys);

  const edit = (i: MenuItem) => setDraft({
    id: i.id, display_name: i.display_name, price_inr: i.price_inr?.toString() ?? "", diet_class: i.diet_class ?? "",
    category_id: i.category_id ?? "", canonical_dish_id: i.canonical_dish_id, canonical_dish_name: i.canonical_dish_name ?? "",
    recipe_id: i.recipe_id ?? "", status: i.status, description: i.description ?? "", diet_tags: i.diet_tags ?? [],
  });

  const sections = menu.data ? [...menu.data.categories.map((c) => ({ id: c.id, name: c.name, items: c.items })),
    ...(menu.data.uncategorised.length ? [{ id: "", name: menu.data.categories.length ? "No category" : "Dishes", items: menu.data.uncategorised }] : [])] : [];
  const dishRecipes = (recipes.data ?? []).filter((r) => !r.is_sub_recipe && (!r.branch_id || r.branch_id === branchId));

  return (
    <>
      <PageHeader title="Menu" subtitle="Dishes, prices and what each one is linked to."
        actions={<>
          <BranchPicker />
          <Link to="/business/import"><Button variant="secondary"><Upload size={18} /> Import</Button></Link>
          <Button variant="secondary" onClick={() => setNewCat("")}><FolderPlus size={18} /> Category</Button>
          <Button onClick={() => setDraft({ ...blank })}><Plus size={18} /> Dish</Button>
        </>} />
      {menu.isPending ? <Skeleton className="h-64" /> : menu.isError ? <ErrorState error={menu.error} onRetry={() => menu.refetch()} /> :
        sections.length === 0 ? (
          <EmptyState title="No dishes yet" body="Add dishes one by one, or import a CSV of your menu."
            action={<div className="flex gap-2"><Button onClick={() => setDraft({ ...blank })}><Plus size={18} /> Add a dish</Button>
              <Link to="/business/import"><Button variant="secondary"><Upload size={18} /> Import</Button></Link></div>} />
        ) : (
          <div className="space-y-6">
            {sections.map((s) => (
              <section key={s.id || "none"} className="card overflow-x-auto">
                <h2 className="px-4 pt-4 font-display text-lg font-bold">{s.name}</h2>
                <table className="dtable mt-2">
                  <thead><tr><th>Dish</th><th>Price</th><th>Diet</th><th>Nutrition</th><th>Recipe</th><th>Status</th><th className="sr-only">Actions</th></tr></thead>
                  <tbody>
                    {s.items.map((i) => (
                      <tr key={i.id}>
                        <td><button className="text-left font-medium hover:underline" onClick={() => edit(i)}>{i.display_name}</button>
                          {i.canonical_dish_name && <p className="text-xs text-muted">{i.canonical_dish_name}</p>}</td>
                        <td>{i.price_inr != null ? `₹${i.price_inr.toLocaleString("en-IN")}` : "–"}</td>
                        <td>{i.diet_class ? DIET_LABEL[i.diet_class] : "–"}</td>
                        <td><NutritionCell n={i.nutrition} /></td>
                        <td>{i.recipe_id ? <Link className="text-green-text hover:underline" to={`/business/recipes/${i.recipe_id}`}>{i.recipe_name}</Link> : <span className="text-muted">None</span>}</td>
                        <td><Chip tone={i.status === "published" ? "green" : "neutral"} selected={i.status === "published"} onClick={() => toggle.mutate(i)}
                          aria-label={`${i.display_name}: ${i.status}. Toggle published.`}>{i.status === "published" ? "Published" : i.status === "hidden" ? "Hidden" : "Draft"}</Chip></td>
                        <td className="whitespace-nowrap text-right">
                          <Link to={`/business/menu/${i.id}`} aria-label={`Servings and options for ${i.display_name}`}
                            className="inline-grid size-11 place-items-center rounded-full text-muted hover:bg-chip-green"><Settings2 size={18} /></Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            ))}
          </div>
        )}
      <ActionError error={toggle.error} />

      <Sheet open={newCat !== null} onOpenChange={(o) => !o && setNewCat(null)} title="New category">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); addCat.mutate(newCat ?? "", { onSuccess: () => setNewCat(null) }); }}>
          <Field label="Name" value={newCat ?? ""} onChange={(e) => setNewCat(e.target.value)} placeholder="e.g. Mains" autoFocus />
          <ActionError error={addCat.error} />
          <Button type="submit" block loading={addCat.isPending} disabled={!newCat?.trim()}>Add category</Button>
        </form>
      </Sheet>

      <Sheet open={draft !== null} onOpenChange={(o) => { if (!o) { setDraft(null); save.reset(); } }} title={draft?.id ? "Edit dish" : "New dish"}>
        {draft && (
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); save.mutate(draft, { onSuccess: () => setDraft(null) }); }}>
            <Field label="Name on the menu" value={draft.display_name} onChange={(e) => setDraft({ ...draft, display_name: e.target.value })} autoFocus />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Price (₹)" inputMode="decimal" value={draft.price_inr} onChange={(e) => setDraft({ ...draft, price_inr: e.target.value })} />
              <Select label="Diet" value={draft.diet_class} onChange={(e) => setDraft({ ...draft, diet_class: e.target.value })} options={DIET_OPTIONS} />
            </div>
            <div>
              <p className="mb-1.5 text-sm font-medium">Suitable for</p>
              <div className="flex flex-wrap gap-2">
                {([["jain", "Jain"], ["no_onion_garlic", "No onion or garlic"], ["vrat", "Vrat"], ["halal", "Halal"]] as const).map(([v, l]) => (
                  <Chip key={v} tone="neutral" selected={draft.diet_tags.includes(v)}
                    onClick={() => setDraft({ ...draft, diet_tags: draft.diet_tags.includes(v) ? draft.diet_tags.filter((x) => x !== v) : [...draft.diet_tags, v] })}>{l}</Chip>
                ))}
              </div>
              <p className="mt-1 text-xs text-muted">Diners who need these only see dishes you mark here. Mark only what you're sure of.</p>
            </div>
            <Select label="Category" value={draft.category_id} onChange={(e) => setDraft({ ...draft, category_id: e.target.value })}
              options={[{ value: "", label: "No category" }, ...(menu.data?.categories ?? []).map((c) => ({ value: c.id, label: c.name }))]} />
            <Autocomplete label="Which dish is this?" placeholder="Search, e.g. dal tadka" value={draft.canonical_dish_name} search={searchDishes}
              onPick={(h) => setDraft({ ...draft, canonical_dish_id: h.id, canonical_dish_name: h.name })}
              render={(h) => <span>{h.name}{h.matched_alias && <span className="text-muted"> · {h.matched_alias}</span>}{h.region && <span className="text-muted"> · {h.region}</span>}</span>} />
            <p className="-mt-2 text-xs text-muted">Used for search and comparison. Without your own recipe, diners see an Estimated value for this dish.</p>
            <Select label="Your recipe" value={draft.recipe_id} onChange={(e) => setDraft({ ...draft, recipe_id: e.target.value })}
              options={[{ value: "", label: "No recipe yet" }, ...dishRecipes.map((r) => ({ value: r.id, label: `${r.name}${r.scope === "branch" ? " (this branch)" : ""}` }))]} />
            {draft.id && (
              <Select label="Status" value={draft.status} onChange={(e) => setDraft({ ...draft, status: e.target.value })}
                options={[{ value: "draft", label: "Draft" }, { value: "published", label: "Published" }, { value: "hidden", label: "Hidden" }]} />
            )}
            <ActionError error={save.error} />
            <div className="flex flex-wrap gap-2">
              <Button type="submit" loading={save.isPending} disabled={!draft.display_name.trim()}>{draft.id ? "Save" : "Add dish"}</Button>
              {draft.id && <Button type="button" variant="ghost" loading={del.isPending}
                onClick={() => del.mutate(draft.id!, { onSuccess: () => setDraft(null) })}><Trash2 size={18} /> Remove from menu</Button>}
            </div>
          </form>
        )}
      </Sheet>
    </>
  );
}
