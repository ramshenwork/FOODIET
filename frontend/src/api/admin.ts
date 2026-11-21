// Admin-area API. The server checks the admin role and logs every call.
import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

export interface Flag { id: string; rule: string; message: string | null; resolution: string; resolution_note: string | null }
export interface Values { version_id: string | null; version_number: number | null; energy_100g: string | null; protein_100g: string | null; fat_100g: string | null; cooked_yield_g: number | null; raw_total_g: number | null }
export interface Dispute { id: string; business_id: string; business_name: string | null; flag_id: string | null; report_id: string | null; detail: string; status: string; resolution_note: string | null; created_at: string }
export interface QueueItem {
  version_id: string; recipe_id: string; recipe_name: string; business_id: string; business_name: string; version_number: number;
  declared_at: string; flags: Flag[]; new: Values; previous: Values | null; lines: string[]; disputes: Dispute[];
}
export interface Report { id: string; type: "allergen_concern" | "menu_changed" | "portion_wrong"; status: string; detail: string | null; menu_item_id: string; menu_item_name: string | null; business_name: string | null; branch_name: string | null; created_at: string; resolution_note: string | null }
export interface VerifiedRow { version_id: string; recipe_name: string; business_name: string; version_number: number; label: string; expires_at: string | null; evidence: { kind: string; reference: string; notes: string | null } | null }
export interface VersionHit { version_id: string; recipe_name: string; business_name: string; version_number: number; label: string; note: string | null }
export interface Profile { energy_kcal: number | null; protein_g: number | null; carbs_g: number | null; fat_g: number | null; fibre_g: number | null; sodium_mg: number | null; source: string; source_version: string | null; licence_status: "pending" | "cleared" | "reference_only" }
export interface IngredientRow { id: string; name: string; category: string | null; state: "raw" | "cooked"; allergens: string[]; profile: Profile | null }
export interface DishRow {
  id: string; name: string; cuisine: string | null; region: string | null; diet_class: string | null; expected_kcal_100g_low: number | null;
  expected_kcal_100g_high: number | null; aliases: { alias: string; language: string | null; transliteration: string | null }[];
  variants: { region: string; name: string }[]; reference_recipes: number;
}
export interface RefLine { ingredient_id?: string; sub_reference_id?: string; quantity_g: number; oil_retained_g?: number }
export interface ReferenceRow {
  id: string; name: string; canonical_dish_id: string | null; region: string | null; cooking_method: string | null; cooked_yield_g: number;
  serving_weight_g: number | null; spread: number | null; notes: string | null; lines: RefLine[]; energy_100g: string | null;
  checks: { rule: string; message: string }[]; licence_cleared: boolean;
}
export interface UserRow { id: string; email: string | null; role: string; status: string; access_level: string; created_at: string }
export interface BusinessRow { id: string; name: string; plan: string; branches: number; members: number; owner_email: string | null }
export interface AuditItem { id: string; at: string; actor: string; action: string; target_type: string | null; target_id: string | null; detail: Record<string, unknown> | null }
export interface Health {
  database: boolean; environment: string; payments_mode: string; email_configured: boolean; storage: string;
  ai: { configured: boolean; monthly_budget_inr: number | null; spent_this_month_inr: number };
  job_runs: { name: string; started_at: string; finished_at: string | null; status: string; detail: Record<string, unknown> | null }[];
}

const A = "/admin";
const qs = (o: Record<string, string | undefined>) => {
  const p = Object.entries(o).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(v!)}`).join("&");
  return p ? `?${p}` : "";
};

export const useQueue = () => useQuery({ queryKey: ["admin", "queue"], queryFn: () => api<QueueItem[]>(`${A}/review-queue`) });
export const useReports = (status?: string) => useQuery({ queryKey: ["admin", "reports", status], queryFn: () => api<Report[]>(`${A}/reports${qs({ status })}`) });
export const useDisputes = (status?: string) => useQuery({ queryKey: ["admin", "disputes", status], queryFn: () => api<Dispute[]>(`${A}/disputes${qs({ status })}`) });
export const useVerified = () => useQuery({ queryKey: ["admin", "verified"], queryFn: () => api<VerifiedRow[]>(`${A}/trust`) });
export const useIngredientsAdmin = (q?: string, licence?: string) => useQuery({ queryKey: ["admin", "ingredients", q, licence], queryFn: () => api<IngredientRow[]>(`${A}/ingredients${qs({ q, licence })}`) });
export const useDishesAdmin = (q?: string) => useQuery({ queryKey: ["admin", "dishes", q], queryFn: () => api<DishRow[]>(`${A}/ontology${qs({ q })}`) });
export const useReferences = () => useQuery({ queryKey: ["admin", "references"], queryFn: () => api<ReferenceRow[]>(`${A}/reference-recipes`) });
export const useUsers = (q?: string, role?: string) => useQuery({ queryKey: ["admin", "users", q, role], queryFn: () => api<UserRow[]>(`${A}/accounts/users${qs({ q, role })}`) });
export const useBusinessesAdmin = (q?: string) => useQuery({ queryKey: ["admin", "businesses", q], queryFn: () => api<BusinessRow[]>(`${A}/accounts/businesses${qs({ q })}`) });
export const useBilling = () => useQuery({ queryKey: ["admin", "billing"], queryFn: () => api<{ trial_claims: number; subscriptions: { id: string; plan: string; status: string; provider: string; current_period_end: string | null }[] }>(`${A}/accounts/billing`) });
export const useHealth = () => useQuery({ queryKey: ["admin", "health"], queryFn: () => api<Health>(`${A}/health`) });
export const auditPage = (cursor?: string) => api<{ items: AuditItem[]; next_cursor: string | null }>(`${A}/audit${qs({ cursor, limit: "50" })}`);
export const findVersions = (q: string) => api<VersionHit[]>(`${A}/versions${qs({ q })}`);

export const admin = {
  resolve: (versionId: string, decision: "approve" | "return", note: string) => api(`${A}/versions/${versionId}/resolve`, { method: "POST", body: { decision, note: note || null } }),
  updateReport: (id: string, status: string, note: string) => api(`${A}/reports/${id}`, { method: "POST", body: { status, note: note || null } }),
  resolveDispute: (id: string, status: "upheld" | "rejected", note: string) => api(`${A}/disputes/${id}`, { method: "POST", body: { status, note } }),
  verify: (versionId: string, kind: string, reference: string, notes: string) => api(`${A}/trust/${versionId}/verify`, { method: "POST", body: { kind, reference, notes: notes || null } }),
  revoke: (versionId: string, reason: string) => api(`${A}/trust/${versionId}/revoke`, { method: "POST", body: { reason } }),
  saveIngredient: (body: Omit<IngredientRow, "id">, id?: string) => api<IngredientRow>(`${A}/ingredients${id ? `/${id}` : ""}`, { method: id ? "PUT" : "POST", body }),
  setLicence: (ids: string[], status: string) => api<{ updated: number }>(`${A}/ingredients/licence`, { method: "POST", body: { ingredient_ids: ids, licence_status: status } }),
  saveDish: (body: Omit<DishRow, "id" | "reference_recipes">, id?: string) => api<DishRow>(`${A}/ontology${id ? `/${id}` : ""}`, { method: id ? "PUT" : "POST", body }),
  saveReference: (body: Omit<ReferenceRow, "id" | "energy_100g" | "checks" | "licence_cleared">, id?: string) =>
    api<ReferenceRow>(`${A}/reference-recipes${id ? `/${id}` : ""}`, { method: id ? "PUT" : "POST", body }),
  setUserStatus: (id: string, status: "active" | "suspended", reason: string) => api<UserRow>(`${A}/accounts/users/${id}/status`, { method: "POST", body: { status, reason } }),
};
