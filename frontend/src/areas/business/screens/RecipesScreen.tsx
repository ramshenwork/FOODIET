import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GitBranch, Plus } from "lucide-react";
import { calls, useAction, useRecipes, type Recipe } from "../../../api/business";
import { Button, Chip, EmptyState, ErrorState, Field, Select, Sheet, Skeleton } from "../../../ui";
import { useBiz } from "../context";
import { ActionError, PageHeader } from "../shared";

export default function RecipesScreen() {
  const { business } = useBiz();
  const nav = useNavigate();
  const q = useRecipes(business.id);
  const [creating, setCreating] = useState<{ name: string; sub: boolean } | null>(null);
  const [overriding, setOverriding] = useState<{ recipe: Recipe; branch: string } | null>(null);
  const create = useAction((v: { name: string; sub: boolean }) => calls.createRecipe(business.id, { name: v.name, is_sub_recipe: v.sub }), [["recipes", business.id]]);
  const override = useAction((v: { recipe: Recipe; branch: string }) => calls.override(business.id, v.recipe.id, v.branch),
    [["recipes", business.id], ["menu"]]);
  const branchName = (id: string | null) => business.branches.find((b) => b.id === id)?.name;

  const table = (list: Recipe[], title: string, empty: string) => (
    <section className="card overflow-x-auto">
      <h2 className="px-4 pt-4 font-display text-lg font-bold">{title}</h2>
      {list.length === 0 ? <p className="p-4 text-sm text-muted">{empty}</p> : (
        <table className="dtable mt-2">
          <thead><tr><th>Name</th><th>Applies to</th><th>Version</th><th>Status</th><th>Dishes using it</th><th className="sr-only">Actions</th></tr></thead>
          <tbody>
            {list.map((r) => (
              <tr key={r.id}>
                <td><Link className="font-medium hover:underline" to={`/business/recipes/${r.id}`}>{r.name}</Link></td>
                <td>{r.scope === "branch" ? <span className="inline-flex items-center gap-1"><GitBranch size={14} /> {branchName(r.branch_id)} only</span> : "All branches"}</td>
                <td>{r.latest_version ?? "–"}</td>
                <td>{r.latest_status ? <Chip tone={r.latest_status === "published" ? "green" : "neutral"} selected={r.latest_status === "published"}>
                  {r.latest_status === "held" ? "Held for review" : r.latest_status}</Chip> : <span className="text-muted">Not published</span>}</td>
                <td>{r.used_by_items}</td>
                <td className="text-right">{r.scope === "brand" && business.branches.length > 1 && r.published_version_id && (
                  <Button variant="ghost" onClick={() => setOverriding({ recipe: r, branch: business.branches[0].id })}><GitBranch size={16} /> Branch version</Button>)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );

  return (
    <>
      <PageHeader title="Recipes" subtitle="Your recipes are where the nutrition comes from. Each publish is a new version."
        actions={<>
          <Button variant="secondary" onClick={() => setCreating({ name: "", sub: true })}><Plus size={18} /> Sub-recipe</Button>
          <Button onClick={() => setCreating({ name: "", sub: false })}><Plus size={18} /> Recipe</Button>
        </>} />
      {q.isPending ? <Skeleton className="h-64" /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> :
        q.data.length === 0 ? <EmptyState title="No recipes yet" body="Start with your best-selling dish. Sub-recipes are reusable bases such as a gravy."
          action={<Button onClick={() => setCreating({ name: "", sub: false })}><Plus size={18} /> New recipe</Button>} /> : (
          <div className="space-y-6">
            {table(q.data.filter((r) => !r.is_sub_recipe), "Dish recipes", "No dish recipes yet.")}
            {table(q.data.filter((r) => r.is_sub_recipe), "Sub-recipes", "No sub-recipes yet. Use them for bases such as a makhani gravy.")}
          </div>
        )}

      <Sheet open={creating !== null} onOpenChange={(o) => !o && setCreating(null)} title={creating?.sub ? "New sub-recipe" : "New recipe"}>
        {creating && (
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); create.mutate(creating, { onSuccess: (r) => nav(`/business/recipes/${r.id}`) }); }}>
            <Field label="Name" value={creating.name} onChange={(e) => setCreating({ ...creating, name: e.target.value })} autoFocus
              placeholder={creating.sub ? "e.g. Makhani gravy" : "e.g. Paneer Butter Masala"} />
            <ActionError error={create.error} />
            <Button type="submit" block loading={create.isPending} disabled={!creating.name.trim()}>Create and open the builder</Button>
          </form>
        )}
      </Sheet>

      <Sheet open={overriding !== null} onOpenChange={(o) => !o && setOverriding(null)} title="Branch version">
        {overriding && (
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); override.mutate(overriding, { onSuccess: (r) => nav(`/business/recipes/${r.id}`) }); }}>
            <p className="text-sm text-muted">Creates a separate copy of “{overriding.recipe.name}” for one branch. The shared recipe and other branches don't change.</p>
            <Select label="Branch" value={overriding.branch} onChange={(e) => setOverriding({ ...overriding, branch: e.target.value })}
              options={business.branches.map((b) => ({ value: b.id, label: b.name }))} />
            <ActionError error={override.error} />
            <Button type="submit" block loading={override.isPending}>Create branch version</Button>
          </form>
        )}
      </Sheet>
    </>
  );
}
