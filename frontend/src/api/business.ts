// Business-area API: types and hooks. Everything shown comes from these responses.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { NutrientValue, TrustLabelKind } from "./types";

export interface Branch {
  id: string; name: string; code: string; address: string | null; region: string | null;
  latitude: number | null; longitude: number | null; fssai_number: string | null; cost_for_one_inr: number | null;
}
export interface Business { id: string; name: string; plan: "free" | "paid"; plan_label: string; billing: boolean; my_role: string; branches: Branch[] }
export interface BranchInput {
  name: string; address?: string | null; region?: string | null; latitude?: number | null; longitude?: number | null;
  fssai_number?: string | null; cost_for_one_inr?: number | null;
}

export interface ItemNutrition {
  trust: { label: TrustLabelKind; note: string | null }; display_mode: string | null;
  energy: NutrientValue | null; protein: NutrientValue | null; carbs: NutrientValue | null; fat: NutrientValue | null;
  serving_label: string | null; allergens: { status: string; display: string; allergens: string[] };
}
export interface MenuItem {
  id: string; branch_id: string; category_id: string | null; display_name: string; description: string | null;
  price_inr: number | null; diet_class: "veg" | "egg" | "non_veg" | null; diet_tags: string[]; status: "draft" | "published" | "hidden";
  canonical_dish_id: string | null; canonical_dish_name: string | null; recipe_id: string | null; recipe_name: string | null;
  current_recipe_version_id: string | null; nutrition: ItemNutrition;
}
export interface Category { id: string; name: string; position: number; items: MenuItem[] }
export interface Menu { id: string; branch_id: string; name: string; categories: Category[]; uncategorised: MenuItem[] }

export interface Dashboard {
  menu_items: number; published_dishes: number; awaiting_recipes: number; with_declared_recipe: number;
  menu_completion_pct: number; recipes_expiring_soon: number; open_flags: number; held_versions: number;
  most_viewed: { name: string; views: number }[];
}

export interface Recipe {
  id: string; name: string; is_sub_recipe: boolean; scope: "brand" | "branch"; branch_id: string | null;
  overrides_recipe_id: string | null; latest_version: number | null; latest_status: string | null;
  published_version_id: string | null; used_by_items: number;
}
export type Unit = "g" | "kg" | "ml" | "l" | "tsp" | "tbsp" | "cup" | "katori";
export interface LineInput {
  ingredient_id?: string | null; sub_recipe_id?: string | null; quantity: number; unit: Unit; oil_retained_g?: number | null;
}
export interface VersionInput { cooking_method: string | null; cooked_yield_g: number; servings_per_batch?: number | null; lines: LineInput[] }
export type NutrientMap = Record<string, NutrientValue | null>;
export interface NutritionBlock {
  per_batch: NutrientMap; per_100g: NutrientMap; per_serving: NutrientMap | null; serving_weight_g: number | null;
  trust: { label: TrustLabelKind; note: string | null }; display_mode: string; allergens: string[];
}
export interface Check { rule: string; message: string; id?: string | null; resolution?: string | null; resolution_note?: string | null }
export interface Preview { nutrition: NutritionBlock; checks: Check[]; licence_cleared: boolean; can_publish: boolean }
export interface VersionLine {
  ingredient_id: string | null; sub_recipe_version_id: string | null; sub_recipe_id: string | null; name: string;
  quantity_g: number; entered_quantity: number | null; entered_unit: Unit | null; oil_retained_g: number | null;
}
export interface Version {
  id: string; recipe_id: string; version_number: number; status: "published" | "held" | "returned";
  cooking_method: string | null; cooked_yield_g: number; servings_per_batch: number | null; declared_at: string;
  lines: VersionLine[]; checks: Check[]; nutrition: NutritionBlock | null;
}
export interface Serving { id: string; label: string; weight_g: number; unit: string; is_default: boolean }
export interface Modifier {
  id: string; label: string; kind: "delta" | "method_swap"; deltas: { ingredient_id: string; delta_g: number }[];
  cooking_method: string | null; oil_retained_g: number | null; cooked_yield_g: number | null; energy_change_display: string | null;
}
export interface ModifierGroup { id: string; name: string; exclusive: boolean; modifiers: Modifier[] }
export interface IngredientHit { id: string; name: string; state: string; category: string | null; allergens: string[]; data_complete: boolean; licence_cleared: boolean }
export interface DishHit { id: string; name: string; cuisine: string | null; region: string | null; diet_class: string | null; matched_alias: string | null }
export interface ImportRow {
  include: boolean; name: string; price_inr: number | null; category: string | null; diet_class: string | null;
  description: string | null; canonical_dish_id: string | null; canonical_dish_name: string | null;
}
export interface MenuImport { id: string; branch_id: string; file_type: string; review_status: string; status: "ready" | "needs_ai" | "confirmed"; message: string | null; rows: ImportRow[] }
export interface Member { user_id: string; email: string | null; role: string }

const b = (id: string) => `/business/${id}`;

export const useBusinesses = () => useQuery({ queryKey: ["businesses"], queryFn: () => api<Business[]>("/business") });
export const useDashboard = (bid: string) => useQuery({ queryKey: ["dashboard", bid], queryFn: () => api<Dashboard>(`${b(bid)}/insights`) });
export const useMenu = (bid: string, branchId: string | undefined) =>
  useQuery({ queryKey: ["menu", bid, branchId], enabled: !!branchId, queryFn: () => api<Menu>(`${b(bid)}/menus?branch_id=${branchId}`) });
export const useRecipes = (bid: string) => useQuery({ queryKey: ["recipes", bid], queryFn: () => api<Recipe[]>(`${b(bid)}/recipes`) });
export const useRecipe = (bid: string, rid: string) => useQuery({ queryKey: ["recipe", rid], queryFn: () => api<Recipe>(`${b(bid)}/recipes/${rid}`) });
export const useVersions = (bid: string, rid: string) => useQuery({ queryKey: ["versions", rid], queryFn: () => api<Version[]>(`${b(bid)}/recipes/${rid}/versions`) });
export const useServings = (bid: string, iid: string) => useQuery({ queryKey: ["servings", iid], queryFn: () => api<Serving[]>(`${b(bid)}/menu-items/${iid}/servings`) });
export const useGroups = (bid: string, iid: string) => useQuery({ queryKey: ["groups", iid], queryFn: () => api<ModifierGroup[]>(`${b(bid)}/menu-items/${iid}/modifier-groups`) });
export const useTeam = (bid: string) => useQuery({ queryKey: ["team", bid], queryFn: () => api<Member[]>(`${b(bid)}/team`) });
export const useQr = (branchId: string) => useQuery({ queryKey: ["qr", branchId], queryFn: () => api<{ branch_code: string; url: string; svg: string }>(`/branches/${branchId}/qr`) });

export const searchIngredients = (q: string) => api<IngredientHit[]>(`/ingredients?q=${encodeURIComponent(q)}&limit=12`);
export const searchDishes = (q: string) => api<DishHit[]>(`/canonical-dishes?q=${encodeURIComponent(q)}&limit=12`);

/** One generic mutation hook: call the API, then refresh the listed query keys. */
export function useAction<TVars, TOut = unknown>(fn: (v: TVars) => Promise<TOut>, invalidate: unknown[][]) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => invalidate.forEach((k) => qc.invalidateQueries({ queryKey: k })) });
}

export const calls = {
  createBusiness: (v: { name: string; first_branch: BranchInput }) => api<Business>("/business", { method: "POST", body: v }),
  addBranch: (bid: string, v: BranchInput) => api<Branch>(`${b(bid)}/branches`, { method: "POST", body: v }),
  updateBranch: (bid: string, id: string, v: BranchInput) => api<Branch>(`${b(bid)}/branches/${id}`, { method: "PUT", body: v }),
  addCategory: (bid: string, branchId: string, name: string) => api(`${b(bid)}/menus/categories?branch_id=${branchId}`, { method: "POST", body: { name } }),
  addItem: (bid: string, v: Record<string, unknown>) => api<MenuItem>(`${b(bid)}/menu-items`, { method: "POST", body: v }),
  updateItem: (bid: string, id: string, v: Record<string, unknown>) => api<MenuItem>(`${b(bid)}/menu-items/${id}`, { method: "PUT", body: v }),
  deleteItem: (bid: string, id: string) => api(`${b(bid)}/menu-items/${id}`, { method: "DELETE" }),
  createRecipe: (bid: string, v: { name: string; is_sub_recipe: boolean }) => api<Recipe>(`${b(bid)}/recipes`, { method: "POST", body: v }),
  preview: (bid: string, v: VersionInput & { serving_weight_g?: number | null; canonical_dish_id?: string | null }, rid?: string) =>
    api<Preview>(`${b(bid)}/recipes/preview${rid ? `?recipe_id=${rid}` : ""}`, { method: "POST", body: v }),
  publish: (bid: string, rid: string, v: VersionInput) => api<Version>(`${b(bid)}/recipes/${rid}/versions`, { method: "POST", body: v }),
  override: (bid: string, rid: string, branchId: string) => api<Recipe>(`${b(bid)}/recipes/${rid}/override`, { method: "POST", body: { branch_id: branchId } }),
  reconfirm: (itemId: string) => api<{ expires_at: string }>(`/menu-items/${itemId}/reconfirm`, { method: "POST" }),
  addServing: (bid: string, iid: string, v: Omit<Serving, "id">) => api<Serving>(`${b(bid)}/menu-items/${iid}/servings`, { method: "POST", body: v }),
  deleteServing: (bid: string, id: string) => api(`${b(bid)}/servings/${id}`, { method: "DELETE" }),
  addGroup: (bid: string, iid: string, v: { name: string; exclusive: boolean }) => api<ModifierGroup>(`${b(bid)}/menu-items/${iid}/modifier-groups`, { method: "POST", body: v }),
  addModifier: (bid: string, gid: string, v: Record<string, unknown>) => api<Modifier>(`${b(bid)}/modifier-groups/${gid}/modifiers`, { method: "POST", body: v }),
  deleteModifier: (bid: string, id: string) => api(`${b(bid)}/modifiers/${id}`, { method: "DELETE" }),
  uploadImport: (bid: string, branchId: string, file: File) => {
    const form = new FormData();
    form.append("branch_id", branchId);
    form.append("file", file);
    return api<MenuImport>(`${b(bid)}/menu-imports`, { method: "POST", form });
  },
  updateImport: (bid: string, id: string, rows: ImportRow[]) => api<MenuImport>(`${b(bid)}/menu-imports/${id}`, { method: "PUT", body: { rows } }),
  confirmImport: (bid: string, id: string) => api<{ created: number }>(`${b(bid)}/menu-imports/${id}/confirm`, { method: "POST" }),
  dispute: (bid: string, flagId: string, detail: string) => api(`${b(bid)}/disputes`, { method: "POST", body: { flag_id: flagId, detail } }),
  addMember: (bid: string, v: { email: string; role: string }) => api<Member>(`${b(bid)}/team`, { method: "POST", body: v }),
};

export interface FeedbackInsights {
  plan: string; detailed: boolean; total_views_7d: number; checkins_30d: string; recommend_rate: string | null;
  dishes: { menu_item_id: string; name: string; views_7d: number; recommend: string | null; felt: string | null }[];
  unmet_demand: { display: string; searches: number }[]; unmet_summary: string; minimum_note: string;
}
export const useFeedbackInsights = (bid: string) =>
  useQuery({ queryKey: ["insights", bid], queryFn: () => api<FeedbackInsights>(`/business/${bid}/insights/feedback`) });

export interface PlanInfo { plan: "free" | "paid"; mode: string; subscription_id: string | null; checkout: Record<string, unknown> | null; renews_until: string | null }
export const usePlan = (bid: string, enabled = true) => useQuery({ queryKey: ["plan", bid], queryFn: () => api<PlanInfo>(`/business/${bid}/plan`), enabled });
export const planCalls = {
  subscribe: (bid: string) => api<PlanInfo>(`/business/${bid}/plan/subscribe`, { method: "POST" }),
  cancel: (bid: string) => api<PlanInfo>(`/business/${bid}/plan/cancel`, { method: "POST" }),
};
