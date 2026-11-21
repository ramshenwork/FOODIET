// Development-only component gallery for design review. Values below are hard-coded samples
// shaped exactly like API responses; in the product they always come from the server.
import { useState } from "react";
import { Leaf, Flame } from "lucide-react";
import { ApiError } from "../../api/client";
import type { NutrientValue } from "../../api/types";
import { useAreaTheme } from "../../app/theme";
import { Button, Card, CardSkeleton, Chip, EmptyState, ErrorState, Field, MacroRings, RangeBar, Sheet, TrustLabel } from "../../ui";
import { ThemeToggle } from "./ThemeToggle";

const SAMPLE: Record<string, NutrientValue> = {
  single: { low: 505, mid: 520, high: 535, unit: "kcal", display: "520 kcal", display_mode: "single" },
  band: { low: 460, mid: 520, high: 580, unit: "kcal", display: "520 kcal, give or take 60", display_mode: "band" },
  range: { low: 450, mid: 580, high: 700, unit: "kcal", display: "450 to 700 kcal", display_mode: "range" },
};

export default function Gallery() {
  const [theme, toggle] = useAreaTheme("consumer");
  const [open, setOpen] = useState(false);
  const [chip, setChip] = useState("veg");
  return (
    <main className="mx-auto max-w-3xl space-y-8 px-4 py-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold">Component gallery</h1>
          <p className="text-sm text-muted">Development only. Sample values, shaped like API responses.</p>
        </div>
        <ThemeToggle theme={theme} toggle={toggle} />
      </header>

      <Card>
        <h2 className="mb-5 font-display text-lg font-bold">Macro rings</h2>
        <MacroRings energyValue={1240} energyCaption="of 1,900 kcal" energy={{ label: "Energy", display: "1,240 kcal", fraction: 0.65 }}
          macros={[{ label: "Protein", display: "62 / 90 g", fraction: 0.69 }, { label: "Carbs", display: "140 / 220 g", fraction: 0.64 }, { label: "Fat", display: "41 / 60 g", fraction: 0.68 }]} />
      </Card>

      <Card className="space-y-6">
        <h2 className="font-display text-lg font-bold">Range bar (three display modes, and unknown)</h2>
        <RangeBar label="Energy" value={SAMPLE.single} scaleMax={900} />
        <RangeBar label="Energy" value={SAMPLE.band} scaleMax={900} />
        <RangeBar label="Energy" value={SAMPLE.range} scaleMax={900} />
        <div><p className="mb-1 text-sm font-medium">Sodium</p><RangeBar label="Sodium" value={null} scaleMax={1} /></div>
      </Card>

      <Card className="space-y-3">
        <h2 className="font-display text-lg font-bold">Trust labels</h2>
        <div className="flex flex-wrap gap-2">
          <TrustLabel kind="verified" /><TrustLabel kind="declared" /><TrustLabel kind="estimated" /><TrustLabel kind="no_data" />
        </div>
        <p className="text-sm text-danger-text">Allergen status unknown</p>
      </Card>

      <Card className="space-y-3">
        <h2 className="font-display text-lg font-bold">Buttons and chips</h2>
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => setOpen(true)}>Open a sheet</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button loading>Saving</Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {["veg", "egg", "non-veg", "jain"].map((c) => (
            <Chip key={c} selected={chip === c} onClick={() => setChip(c)} icon={c === "veg" ? <Leaf size={16} /> : undefined}>{c}</Chip>
          ))}
          <Chip tone="orange" icon={<Flame size={16} />}>Under 500 kcal</Chip>
          <Chip tone="neutral">Under 2 km</Chip>
        </div>
      </Card>

      <Card className="space-y-4">
        <h2 className="font-display text-lg font-bold">Fields</h2>
        <Field label="Email" placeholder="you@example.com" />
        <Field label="Weight (kg)" error="Enter a number between 30 and 300." defaultValue="3000" />
      </Card>

      <section className="space-y-4">
        <h2 className="font-display text-lg font-bold">States</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <CardSkeleton />
          <EmptyState title="Nothing fits yet" body="Try widening the distance or energy filter." />
          <ErrorState error={new ApiError(500, "internal_error", "Something went wrong on our side.", "a1b2c3d4")} onRetry={() => undefined} />
          <ErrorState error={new ApiError(0, "offline", "You seem to be offline.")} onRetry={() => undefined} />
          <ErrorState onPaywall={() => undefined} error={new ApiError(402, "subscription_required", "", undefined,
            { level: "preview", trial_available: true, trial_days: 7, message: "Start your free trial to see outlet-specific nutrition." })} />
        </div>
      </section>

      <Sheet open={open} onOpenChange={setOpen} title="Choose a serving">
        <p className="text-muted">Bottom sheet on phones, dialog on wider screens.</p>
        <div className="mt-4 flex gap-2"><Chip selected>Full plate</Chip><Chip>Half</Chip><Chip>Katori</Chip></div>
      </Sheet>
    </main>
  );
}
