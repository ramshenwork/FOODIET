// Response shapes from the backend. The client displays these; it never derives values from them.

export type AccessLevel = "free" | "preview" | "trial" | "subscriber" | "grace" | "lapsed";

export interface PublicConfig {
  app_name: string;
  environment: string;
  payments_enabled: boolean;
  payments_mode: string;
  trial_days: number;
  price_monthly_inr: number | null;
  price_yearly_inr: number | null;
}

export interface Me {
  id: string;
  email: string;
  role: "consumer" | "business" | "admin";
  age_confirmed: boolean;
  access_level: AccessLevel;
}

export interface SessionOut {
  user: Me;
  csrf_token: string;
}

export interface Entitlement {
  level: AccessLevel;
  source: string;
  period_end: string | null;
  grace_end: string | null;
  trial_available: boolean;
  cancelled: boolean;
  can: { nutrition: boolean; diary_write: boolean; diary_read: boolean; start_trial: boolean; subscribe: boolean; cancel: boolean; billing: boolean };
  display: { title: string; detail: string; period: string | null };
}

export interface Paywall {
  level: AccessLevel;
  trial_available: boolean;
  trial_days: number;
  message: string;
}

/** Every nutrition value arrives ready to display. `null` means unknown. */
export interface NutrientValue {
  low: number;
  mid: number;
  high: number;
  unit: string;
  display: string;
  display_mode: "single" | "band" | "range";
}

export type TrustLabelKind = "verified" | "declared" | "estimated" | "no_data";

export interface ApiErrorBody {
  error: { code: string; message: string; request_id: string };
  paywall?: Paywall;
  fields?: { field: string; message: string }[];
}
