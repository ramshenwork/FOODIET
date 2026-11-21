import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { consumer, useProfile, type Profile, type ProfileInput } from "../../../api/consumer";
import { useAction } from "../../../api/business";
import { Banner, Button, Card, Chip, Field, Skeleton } from "../../../ui";
import { ActionError } from "../../business/shared";

type Draft = Omit<ProfileInput, "birth_year" | "height_cm" | "weight_kg" | "budget_per_meal_inr"> &
  { birth_year: string; height_cm: string; weight_kg: string; budget_per_meal_inr: string; adult: boolean };

const fromProfile = (p?: Profile): Draft => ({
  adult: !!p?.birth_year, birth_year: p?.birth_year?.toString() ?? "", sex_for_energy_estimate: p?.sex_for_energy_estimate ?? "",
  height_cm: p?.height_cm?.toString() ?? "", weight_kg: p?.weight_kg?.toString() ?? "", activity_level: p?.activity_level ?? "",
  goal: p?.goal ?? "", diet_type: p?.diet_type ?? "", restrictions: p?.restrictions ?? [], allergies: p?.allergies ?? [],
  cuisines: p?.cuisines ?? [], spice_level: p?.spice_level ?? null, budget_per_meal_inr: p?.budget_per_meal_inr?.toString() ?? "",
  health_data_consent: p?.consents.health_data ?? false,
});

function Choice({ options, value, onPick }: { options: [string, string][]; value: string | null; onPick: (v: string) => void }) {
  return <div className="grid gap-2">{options.map(([v, l]) => (
    <button key={v} type="button" onClick={() => onPick(v)} aria-pressed={value === v}
      className={`min-h-12 rounded-2xl border px-4 text-left font-medium transition-colors ${value === v ? "border-green bg-chip-green" : "border-line"}`}>{l}</button>
  ))}</div>;
}

function Multi({ options, value, onChange }: { options: [string, string][]; value: string[]; onChange: (v: string[]) => void }) {
  return <div className="flex flex-wrap gap-2">{options.map(([v, l]) => (
    <Chip key={v} tone="neutral" selected={value.includes(v)} onClick={() => onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v])}>{l}</Chip>
  ))}</div>;
}

/** One question per screen, then suggested targets the user can adjust. Targets are calculated by the server. */
export default function Onboarding({ onDone }: { onDone?: () => void }) {
  const profile = useProfile();
  const qc = useQueryClient();
  const [d, setD] = useState<Draft | null>(null);
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<Profile | null>(null);
  const [kcal, setKcal] = useState("");
  const draft = d ?? (profile.data ? fromProfile(profile.data) : null);
  const save = useAction((extra: Partial<ProfileInput>) => consumer.saveProfile({
    birth_year: Number(draft!.birth_year), sex_for_energy_estimate: draft!.sex_for_energy_estimate, height_cm: Number(draft!.height_cm),
    weight_kg: Number(draft!.weight_kg), activity_level: draft!.activity_level, goal: draft!.goal, diet_type: draft!.diet_type,
    restrictions: draft!.restrictions, allergies: draft!.allergies, cuisines: draft!.cuisines, spice_level: draft!.spice_level,
    budget_per_meal_inr: draft!.budget_per_meal_inr ? Number(draft!.budget_per_meal_inr) : null, health_data_consent: draft!.health_data_consent, ...extra,
  }), []);  // the profile is refreshed on "Done", so the targets screen stays up
  if (!draft) return <Skeleton className="h-96" />;
  const set = (p: Partial<Draft>) => setD({ ...draft, ...p });

  const steps: { title: string; body: React.ReactNode; ok: boolean }[] = [
    { title: "Are you 18 or older?", ok: draft.adult && Number(draft.birth_year) > 1900, body: <>
      <Choice options={[["yes", "Yes, I'm 18 or older"]]} value={draft.adult ? "yes" : null} onPick={() => set({ adult: true })} />
      <Field label="Year of birth" inputMode="numeric" value={draft.birth_year} onChange={(e) => set({ birth_year: e.target.value })} />
      <p className="text-xs text-muted">This service is for adults only.</p></> },
    { title: "What's your goal?", ok: !!draft.goal, body: <Choice value={draft.goal} onPick={(goal) => set({ goal })} options={[["lose", "Lose weight"], ["maintain", "Maintain"], ["gain", "Gain weight or muscle"]]} /> },
    { title: "For the energy estimate", ok: !!draft.sex_for_energy_estimate, body: <>
      <Choice value={draft.sex_for_energy_estimate} onPick={(v) => set({ sex_for_energy_estimate: v })} options={[["female", "Female"], ["male", "Male"]]} />
      <p className="text-xs text-muted">Used only in the standard energy equation.</p></> },
    { title: "Your height and weight", ok: Number(draft.height_cm) >= 100 && Number(draft.weight_kg) >= 30, body: <div className="grid grid-cols-2 gap-3">
      <Field label="Height (cm)" inputMode="decimal" value={draft.height_cm} onChange={(e) => set({ height_cm: e.target.value })} />
      <Field label="Weight (kg)" inputMode="decimal" value={draft.weight_kg} onChange={(e) => set({ weight_kg: e.target.value })} /></div> },
    { title: "How active are you?", ok: !!draft.activity_level, body: <Choice value={draft.activity_level} onPick={(v) => set({ activity_level: v })}
      options={[["sedentary", "Mostly sitting"], ["light", "Light: walks, 1–3 workouts a week"], ["moderate", "Moderate: 3–5 workouts a week"], ["active", "Active: daily exercise"], ["very_active", "Very active: physical job or training"]]} /> },
    { title: "What do you eat?", ok: !!draft.diet_type, body: <Choice value={draft.diet_type} onPick={(v) => set({ diet_type: v })} options={[["veg", "Vegetarian"], ["egg", "Vegetarian, with egg"], ["non_veg", "Non-vegetarian"]]} /> },
    { title: "Any of these?", ok: true, body: <>
      <Multi value={draft.restrictions} onChange={(restrictions) => set({ restrictions })} options={[["jain", "Jain"], ["no_onion_garlic", "No onion or garlic"], ["vrat", "Vrat"], ["halal", "Halal"]]} />
      <p className="text-xs text-muted">We only show dishes the restaurant has marked as suitable.</p></> },
    { title: "Allergies", ok: true, body: <>
      <Multi value={draft.allergies} onChange={(allergies) => set({ allergies })} options={[["milk", "Milk"], ["egg", "Egg"], ["peanut", "Peanut"], ["tree_nut", "Tree nuts"], ["gluten", "Gluten"], ["soy", "Soy"], ["sesame", "Sesame"], ["fish", "Fish"], ["crustacean", "Shellfish"], ["mustard", "Mustard"]]} />
      <p className="text-xs text-muted">Dishes declaring these are never shown to you. Dishes without a declared recipe show “allergen status unknown”.</p></> },
    { title: "Cuisines you like", ok: true, body: <Multi value={draft.cuisines} onChange={(cuisines) => set({ cuisines })} options={["North Indian", "South Indian", "Biryani", "Tandoor", "Snacks", "Chinese", "Continental"].map((c) => [c, c] as [string, string])} /> },
    { title: "Spice level", ok: true, body: <Choice value={draft.spice_level} onPick={(v) => set({ spice_level: v })} options={[["mild", "Mild"], ["medium", "Medium"], ["hot", "Hot"]]} /> },
    { title: "Usual budget per meal", ok: true, body: <Field label="₹ per meal (optional)" inputMode="numeric" value={draft.budget_per_meal_inr} onChange={(e) => set({ budget_per_meal_inr: e.target.value })} /> },
    { title: "Your consent", ok: draft.health_data_consent, body: <label className="flex gap-3 rounded-2xl border border-line p-4">
      <input type="checkbox" className="mt-1 size-5 accent-[var(--green-500)]" checked={draft.health_data_consent} onChange={(e) => set({ health_data_consent: e.target.checked })} />
      <span className="text-sm">I agree that my height, weight, targets, restrictions and allergies are stored (encrypted) to personalise results. I can withdraw this any time in Profile, which deletes them.</span></label> },
  ];

  if (result?.targets) {
    const t = result.targets;
    return (
      <Card className="mx-auto max-w-lg space-y-4">
        <h1 className="text-2xl font-extrabold">Your daily targets</h1>
        <p className="font-display text-5xl font-extrabold text-orange-text">{t.energy_kcal.toLocaleString("en-IN")} <span className="text-2xl">kcal</span></p>
        <p className="text-muted">Protein {t.protein_g} g · Carbs {t.carbs_g} g · Fat {t.fat_g} g</p>
        <Banner tone="note" title={t.note}>{t.floor_applied ? `Set to the minimum of ${result.calorie_floor_kcal} kcal.` : "You can adjust the energy target below."}</Banner>
        <form className="flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); save.mutate({ calorie_target: Number(kcal) }, { onSuccess: setResult }); }}>
          <div className="flex-1"><Field label="Adjust energy target (kcal)" inputMode="numeric" value={kcal} onChange={(e) => setKcal(e.target.value)}
            hint={result.calorie_floor_kcal ? `Not below ${result.calorie_floor_kcal} kcal` : undefined} /></div>
          <Button type="submit" variant="secondary" disabled={!kcal} loading={save.isPending}>Update</Button>
        </form>
        <ActionError error={save.error} />
        <Button block onClick={() => { qc.invalidateQueries({ queryKey: ["profile"] }); onDone?.(); }}>Done</Button>
      </Card>
    );
  }

  const s = steps[step];
  return (
    <div className="mx-auto max-w-lg overflow-x-hidden">  {/* the step slide must never cause sideways scrolling */}
      <div className="mb-6 h-1.5 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuenow={step + 1} aria-valuemax={steps.length}>
        <motion.div className="h-full bg-green" animate={{ width: `${((step + 1) / steps.length) * 100}%` }} />
      </div>
      <AnimatePresence mode="wait">
        <motion.div key={step} initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} transition={{ duration: 0.22 }} className="space-y-4">
          <h1 className="text-2xl font-extrabold">{s.title}</h1>
          {s.body}
        </motion.div>
      </AnimatePresence>
      <ActionError error={save.error} />
      <div className="mt-6 flex gap-2">
        {step > 0 && <Button variant="ghost" onClick={() => setStep(step - 1)}>Back</Button>}
        {step < steps.length - 1
          ? <Button disabled={!s.ok} onClick={() => setStep(step + 1)}>Continue</Button>
          : <Button disabled={!s.ok} loading={save.isPending} onClick={() => save.mutate({}, { onSuccess: (p) => { setResult(p); setKcal(String(p.targets?.energy_kcal ?? "")); } })}>See my targets</Button>}
      </div>
    </div>
  );
}
