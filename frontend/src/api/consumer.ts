// Consumer API: types and hooks. Every value, label, fit and ranking arrives from the server.
import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { NutrientValue, TrustLabelKind } from "./types";

export type Nutrients = Record<"energy_kcal" | "protein_g" | "carbs_g" | "fat_g" | "fibre_g" | "sodium_mg", NutrientValue | null>;
export interface Targets { energy_kcal: number; protein_g: number; carbs_g: number; fat_g: number; floor_applied: boolean; note: string }
export interface Profile {
  complete: boolean; birth_year: number | null; sex_for_energy_estimate: string | null; height_cm: number | null; weight_kg: number | null;
  activity_level: string | null; goal: string | null; diet_type: string | null; restrictions: string[]; allergies: string[]; cuisines: string[];
  spice_level: string | null; budget_per_meal_inr: number | null; suggested: Targets | null; targets: Targets | null;
  calorie_floor_kcal: number | null; consents: Record<string, boolean>;
}
export interface ProfileInput {
  birth_year: number; sex_for_energy_estimate: string; height_cm: number; weight_kg: number; activity_level: string; goal: string;
  diet_type: string; restrictions: string[]; allergies: string[]; cuisines: string[]; spice_level: string | null;
  budget_per_meal_inr: number | null; calorie_target?: number | null; protein_target_g?: number | null; health_data_consent: boolean;
}
export interface Trust { label: TrustLabelKind; note: string | null; meaning?: string }
export interface Band { display: string; label: string; source: "logged" | "modelled" }
export interface RestaurantCard { id: string; name: string; distance_km: number; distance_display: string; cost_for_one_inr: number | null; typical_meal: Band | null; fit_count: number; fit_display: string }
export interface DishCard {
  id: string; name: string; restaurant_id: string; restaurant_name: string; distance_display: string | null; price_inr: number | null;
  diet_class: string | null; trust: Trust; energy: NutrientValue | null; protein: NutrientValue | null; fits: boolean;
  allergen_warning: string | null; ranked: boolean;
}
export interface RestaurantPage {
  id: string; name: string; address: string | null; distance_display: string | null; cost_for_one_inr: number | null;
  typical_meal: Band | null; personal: { display: string; fit_count: number } | null; recommend_rate: string | null;
  declared_share: string; dishes: DishCard[]; other_dishes: DishCard[];
}
export interface DishNutrition {
  trust: Trust; display_mode: string | null; nutrients: Nutrients; serving_label: string | null; share_fraction: number;
  modifier_ids: string[]; fit: { fits: boolean; display: string } | null; protein_per_100_inr: string | null; excluded_from_ranking: boolean;
}
export interface DishPage {
  id: string; name: string; description: string | null; price_inr: number | null; diet_class: string | null; diet_tags: string[];
  restaurant_id: string; restaurant_name: string; nutrition: DishNutrition;
  servings: { id: string | null; label: string; weight_g: number | null; selected: boolean }[];
  modifier_groups: { id: string; name: string; exclusive: boolean; modifiers: { id: string; label: string }[] }[];
  ingredients: string[]; ingredients_label: string; allergens: { status: string; display: string; allergens: string[] };
  allergy_conflict: string[]; last_updated: string | null;
}
export interface Preview {
  coverage: { declared_restaurants: number; radius_km: number; display: string; waitlist: boolean };
  restaurants: { id: string; name: string; distance_display: string; dish_names: string[]; declared_dishes: number; total_dishes: number }[];
}
export interface Ring { label: string; display: string; fraction: number | null }
export interface DiaryItem { id: string; name: string; restaurant: string | null; component_label: string | null; serving_label: string | null; share_fraction: number; share_display: string; trust: Trust; energy: NutrientValue | null; protein: NutrientValue | null; allergens: { display: string } }
export interface DiaryEntry { id: string; meal_type: string; eaten_at: string; restaurant: string | null; items: DiaryItem[]; energy_display: string | null }
export interface Day {
  date: string; entries: DiaryEntry[]; totals: Nutrients; rings: Record<"energy" | "protein" | "carbs" | "fat", Ring> | null;
  energy_value: number | null; energy_caption: string | null; remaining_display: string | null; read_only: boolean;
}
export interface Coords { lat: number; lng: number }

const loc = (c: Coords) => `lat=${c.lat}&lng=${c.lng}`;

export const useProfile = () => useQuery({ queryKey: ["profile"], queryFn: () => api<Profile>("/me/profile") });
export const usePreview = (c: Coords | null) => useQuery({ queryKey: ["preview", c], enabled: !!c, queryFn: () => api<Preview>(`/preview/nearby?${loc(c!)}`) });
export const useNearby = (c: Coords | null) => useQuery({ queryKey: ["nearby", c], enabled: !!c, queryFn: () => api<{ restaurants: RestaurantCard[]; meal_budget_display: string | null }>(`/restaurants/nearby?${loc(c!)}`) });
export const useRestaurant = (id: string, c: Coords | null) => useQuery({ queryKey: ["restaurant", id, c], queryFn: () => api<RestaurantPage>(`/restaurants/${id}${c ? `?${loc(c)}` : ""}`) });
export const useDish = (id: string) => useQuery({ queryKey: ["dish", id], queryFn: () => api<DishPage>(`/dishes/${id}`) });
export const useDay = (date: string) => useQuery({ queryKey: ["diary", date], queryFn: () => api<Day>(`/diary?date=${date}`) });

export interface SearchParams { q?: string; max_kcal?: number; min_protein?: number; max_price?: number; max_km?: number; trust?: string[] }
export const searchUrl = (c: Coords, p: SearchParams, cursor?: string) => {
  const parts = [loc(c)];
  Object.entries(p).forEach(([k, v]) => {
    if (v === undefined || v === "" || (Array.isArray(v) && !v.length)) return;
    if (Array.isArray(v)) v.forEach((x) => parts.push(`${k}=${encodeURIComponent(x)}`));
    else parts.push(`${k}=${encodeURIComponent(String(v))}`);
  });
  if (cursor) parts.push(`cursor=${encodeURIComponent(cursor)}`);
  return `/search?${parts.join("&")}`;
};
export const searchPage = (c: Coords, p: SearchParams, cursor?: string) =>
  api<{ dishes: DishCard[]; restaurants: RestaurantCard[]; next_cursor: string | null }>(searchUrl(c, p, cursor));

export const consumer = {
  saveProfile: (v: ProfileInput) => api<Profile>("/me/profile", { method: "PUT", body: v }),
  consent: (purpose: string, granted: boolean) => api<Profile>("/me/consents", { method: "POST", body: { purpose, granted } }),
  trial: (deviceId: string) => api("/billing/trial", { method: "POST", body: { device_id: deviceId } }),
  subscribe: (plan: "monthly" | "yearly", ref: string | null, key: string) =>
    api<{ mode: string; checkout: Record<string, unknown> | null }>("/billing/subscribe", { method: "POST", body: { plan, ref }, idempotencyKey: key }),
  cancel: () => api<{ access_until: string | null }>("/billing/cancel", { method: "POST" }),
  waitlist: (area: string) => api("/preview/waitlist", { method: "POST", body: { area } }),
  calculate: (id: string, v: { serving_option_id: string | null; share_fraction: number; modifier_ids: string[] }) =>
    api<DishNutrition>(`/dishes/${id}/calculate`, { method: "POST", body: v }),
  log: (v: { meal_type: string; items: { menu_item_id: string; serving_option_id?: string | null; share_fraction: number; modifier_ids?: string[]; component_label?: string | null }[] }, key: string) =>
    api<DiaryEntry>("/diary/entries", { method: "POST", body: v, idempotencyKey: key }),
  updateEntry: (id: string, v: { meal_type: string; shares?: Record<string, number>; remove_item_ids?: string[] }) =>
    api<DiaryEntry>(`/diary/entries/${id}`, { method: "PUT", body: v }),
  deleteEntry: (id: string) => api(`/diary/entries/${id}`, { method: "DELETE" }),
  deleteAccount: () => api("/me", { method: "DELETE", body: { confirm: "DELETE" } }),
};

// ------------------------------------------------------------------ phase 6: feedback, fingerprint, trends
export interface PendingCheckin { meal_entry_id: string; restaurant: string; eaten_at: string; dishes: string[]; menu: { id: string; name: string }[] }
export interface Fingerprint {
  consented: boolean; learned: { id: string; kind: string; value: string; display: string }[]; top_cuisines: string[];
  avg_protein_eating_out: string | null; most_repeated: string[]; note: string;
}
export interface WeekPoint { week_start: string; label: string; days_logged: number; avg_energy_kcal: number | null; avg_protein_g: number | null; energy_target: number | null; protein_target: number | null }
export interface Trends { weeks: WeekPoint[]; recap: { title: string; lines: string[] } | null }

export const usePendingCheckin = () => useQuery({ queryKey: ["checkin"], queryFn: () => api<PendingCheckin | null>("/checkins/pending") });
export const useFingerprint = () => useQuery({ queryKey: ["fingerprint"], queryFn: () => api<Fingerprint>("/me/fingerprint") });
export const useTrends = () => useQuery({ queryKey: ["trends"], queryFn: () => api<Trends>("/diary/trends?weeks=8") });

export const feedback = {
  checkin: (v: { meal_entry_id: string; felt?: string | null; recommend?: boolean | null; recommended_item_id?: string | null }) =>
    api("/checkins", { method: "POST", body: v }),
  report: (v: { menu_item_id: string; type: string; detail: string | null }) =>
    api<{ message: string }>("/reports", { method: "POST", body: v }),
  removeLearned: (id: string) => api(`/me/fingerprint/${id}`, { method: "DELETE" }),
};

// ------------------------------------------------------------------ phase 7: assistant and swaps
export interface CitedDish { id: string; name: string; restaurant: string | null; energy: string | null; protein: string | null; trust: string }
export interface AssistantMessage { role: "user" | "assistant"; content: string; cited: CitedDish[]; mode: string | null; at: string }
export interface Conversation { messages: AssistantMessage[]; remaining_today: number; limit: number; mode: "ai" | "basic" }
export interface Answer { answer: string; cited: CitedDish[]; mode: string; notice: string | null; remaining_today: number; limit: number }
export interface Swap { kind: "option" | "dish"; title: string; display: string; modifier_id: string | null; dish_id: string | null }

export const useConversation = () => useQuery({ queryKey: ["assistant"], queryFn: () => api<Conversation>("/assistant") });
export const useSwaps = (id: string) => useQuery({ queryKey: ["swaps", id], queryFn: () => api<{ swaps: Swap[]; note: string }>(`/dishes/${id}/swaps`) });
export const askAssistant = (question: string, c: Coords | null) =>
  api<Answer>("/assistant/query", { method: "POST", body: { question, lat: c?.lat ?? null, lng: c?.lng ?? null } });
