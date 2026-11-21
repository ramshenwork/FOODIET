import type { ReactNode } from "react";
import { ApiError } from "../../api/client";
import type { ItemNutrition } from "../../api/business";
import { Banner, Select, TrustLabel } from "../../ui";
import { useBiz } from "./context";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-extrabold">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function BranchPicker() {
  const { business, branchId, setBranchId } = useBiz();
  if (business.branches.length < 2) return null;
  return (
    <div className="w-56">
      <Select aria-label="Branch" value={branchId} onChange={(e) => setBranchId(e.target.value)}
        options={business.branches.map((b) => ({ value: b.id, label: b.name }))} />
    </div>
  );
}

/** Shows an API error from a mutation, including plan limits (402). */
export function ActionError({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error instanceof ApiError ? error : null;
  const title = e?.code === "plan_required" ? "Needs the paid plan" : "That didn't work";
  return <Banner tone="problem" title={title}>{e?.fields?.length ? e.fields.map((f) => f.message).join(" ") : e?.message ?? "Try again."}</Banner>;
}

export function NutritionCell({ n }: { n: ItemNutrition }) {
  return (
    <div className="flex flex-col items-start gap-1">
      {n.energy ? <span className="font-medium text-orange-text">{n.energy.display}</span> : <span className="text-muted">No nutrition yet</span>}
      <TrustLabel kind={n.trust.label} note={n.trust.note ?? undefined} />
    </div>
  );
}

export const DIET_LABEL: Record<string, string> = { veg: "Veg", egg: "Egg", non_veg: "Non-veg" };
export const DIET_OPTIONS = [{ value: "", label: "Not set" }, { value: "veg", label: "Veg" }, { value: "egg", label: "Egg" }, { value: "non_veg", label: "Non-veg" }];
export const METHOD_OPTIONS = ["simmer", "boil", "steam", "tawa", "saute", "deep_fry", "shallow_fry", "tandoor", "grill", "bake", "dum", "raw"]
  .map((m) => ({ value: m, label: m.replace("_", " ").replace(/^./, (c) => c.toUpperCase()) }));
