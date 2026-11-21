import { useState } from "react";
import { motion } from "framer-motion";
import { LocateFixed } from "lucide-react";
import { calls, useAction } from "../../../api/business";
import { platform } from "../../../platform";
import { Banner, Button, Card, Field } from "../../../ui";
import { ActionError } from "../shared";

/** Sign-up steps: business details, first branch with location, plan. */
export default function Onboarding() {
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [branch, setBranch] = useState({ name: "", address: "", region: "", fssai_number: "", cost_for_one_inr: "", latitude: "", longitude: "" });
  const [locating, setLocating] = useState(false);
  const [locError, setLocError] = useState("");
  const create = useAction(calls.createBusiness, [["businesses"]]);
  const set = (k: keyof typeof branch) => (e: React.ChangeEvent<HTMLInputElement>) => setBranch({ ...branch, [k]: e.target.value });

  const locate = async () => {
    setLocating(true); setLocError("");
    const c = await platform.locate();
    setLocating(false);
    if (!c) { setLocError("Location wasn't shared. Type the coordinates instead, or try again at the outlet."); return; }
    setBranch((b) => ({ ...b, latitude: c.latitude.toFixed(6), longitude: c.longitude.toFixed(6) }));
  };
  const num = (v: string) => (v.trim() === "" ? null : Number(v));
  const submit = () => create.mutate({
    name, first_branch: {
      name: branch.name || name, address: branch.address || null, region: branch.region || null,
      fssai_number: branch.fssai_number || null, cost_for_one_inr: num(branch.cost_for_one_inr),
      latitude: num(branch.latitude), longitude: num(branch.longitude),
    },
  });

  const steps = ["Your business", "First branch", "Plan"];
  return (
    <main className="mx-auto max-w-xl px-4 py-10">
      <ol className="mb-8 flex gap-2" aria-label="Progress">
        {steps.map((s, i) => (
          <li key={s} className="flex-1">
            <div className={`h-1.5 rounded-full ${i <= step ? "bg-green" : "bg-line"}`} />
            <p className={`mt-2 text-xs ${i === step ? "font-semibold" : "text-muted"}`}>{s}</p>
          </li>
        ))}
      </ol>
      <motion.div key={step} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22 }}>
        {step === 0 && (
          <Card className="space-y-5">
            <h1 className="text-2xl font-extrabold">Set up your restaurant</h1>
            <Field label="Business name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Spice Route" autoFocus />
            <Button disabled={!name.trim()} onClick={() => setStep(1)}>Continue</Button>
          </Card>
        )}
        {step === 1 && (
          <Card className="space-y-4">
            <h1 className="text-2xl font-extrabold">Your first branch</h1>
            <Field label="Branch name" value={branch.name} onChange={set("name")} placeholder={`${name}, Banjara Hills`} />
            <Field label="Address" value={branch.address} onChange={set("address")} />
            <Field label="City or region" hint="Used to pick regional reference recipes, e.g. Hyderabad." value={branch.region} onChange={set("region")} />
            <div className="space-y-2">
              <p className="text-sm font-medium">Location</p>
              <Button type="button" variant="secondary" loading={locating} onClick={locate}><LocateFixed size={18} /> Use my current location</Button>
              {locError && <p className="text-sm text-muted">{locError}</p>}
              <div className="grid grid-cols-2 gap-3">
                <Field label="Latitude" inputMode="decimal" value={branch.latitude} onChange={set("latitude")} />
                <Field label="Longitude" inputMode="decimal" value={branch.longitude} onChange={set("longitude")} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="FSSAI number" hint="14 digits" inputMode="numeric" value={branch.fssai_number} onChange={set("fssai_number")} />
              <Field label="Cost for one (₹)" inputMode="numeric" value={branch.cost_for_one_inr} onChange={set("cost_for_one_inr")} />
            </div>
            <div className="flex gap-2"><Button variant="ghost" onClick={() => setStep(0)}>Back</Button><Button onClick={() => setStep(2)}>Continue</Button></div>
          </Card>
        )}
        {step === 2 && (
          <Card className="space-y-4">
            <h1 className="text-2xl font-extrabold">Choose a plan</h1>
            <div className="rounded-2xl border-2 border-green p-4">
              <p className="font-display font-bold">Free</p>
              <p className="text-sm text-muted">Listing, menu, recipe builder, nutrition, QR codes and basic stats for one branch.</p>
            </div>
            <div className="rounded-2xl border border-line p-4 opacity-70">
              <p className="font-display font-bold">Paid</p>
              <p className="text-sm text-muted">Many branches with shared recipes, team roles, detailed insights and recipe suggestions. Available once billing launches.</p>
            </div>
            <Banner tone="note" title="Ranking is never for sale">Paying never changes search ranking, trust labels or what diners can report.</Banner>
            <ActionError error={create.error} />
            <div className="flex gap-2"><Button variant="ghost" onClick={() => setStep(1)}>Back</Button>
              <Button loading={create.isPending} onClick={submit}>Start on the free plan</Button></div>
          </Card>
        )}
      </motion.div>
    </main>
  );
}
