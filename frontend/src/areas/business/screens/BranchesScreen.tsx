import { useState } from "react";
import { LocateFixed, Plus } from "lucide-react";
import { calls, useAction, type BranchInput } from "../../../api/business";
import { platform } from "../../../platform";
import { Button, Card, Field, Sheet } from "../../../ui";
import { useBiz } from "../context";
import { ActionError, PageHeader } from "../shared";

export default function BranchesScreen() {
  const { business } = useBiz();
  const [form, setForm] = useState<Record<string, string> | null>(null);
  const add = useAction((v: BranchInput) => calls.addBranch(business.id, v), [["businesses"]]);
  const num = (v?: string) => (v && v.trim() !== "" ? Number(v) : null);
  const locate = async () => {
    const c = await platform.locate();
    if (c && form) setForm({ ...form, latitude: c.latitude.toFixed(6), longitude: c.longitude.toFixed(6) });
  };
  return (
    <>
      <PageHeader title="Branches" subtitle="Recipes are shared by all branches unless a branch has its own version."
        actions={<Button onClick={() => setForm({})}><Plus size={18} /> Branch</Button>} />
      <div className="grid gap-4 sm:grid-cols-2">
        {business.branches.map((b) => (
          <Card key={b.id} className="space-y-1">
            <p className="font-display text-lg font-bold">{b.name}</p>
            {b.address && <p className="text-sm text-muted">{b.address}</p>}
            <p className="text-sm">{b.region ? `Region: ${b.region}` : "No region set"}</p>
            <p className="text-sm text-muted">{b.latitude != null ? `${b.latitude.toFixed(4)}, ${b.longitude?.toFixed(4)}` : "No location yet"}</p>
            <p className="text-sm text-muted">QR code: /q/{b.code}{b.fssai_number ? ` · FSSAI ${b.fssai_number}` : ""}</p>
          </Card>
        ))}
      </div>
      <Sheet open={form !== null} onOpenChange={(o) => { if (!o) { setForm(null); add.reset(); } }} title="New branch">
        {form && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); add.mutate({
            name: form.name ?? "", address: form.address || null, region: form.region || null, fssai_number: form.fssai || null,
            latitude: num(form.latitude), longitude: num(form.longitude), cost_for_one_inr: num(form.cost) }, { onSuccess: () => setForm(null) }); }}>
            <Field label="Name" value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
            <Field label="Address" value={form.address ?? ""} onChange={(e) => setForm({ ...form, address: e.target.value })} />
            <Field label="City or region" value={form.region ?? ""} onChange={(e) => setForm({ ...form, region: e.target.value })} />
            <Button type="button" variant="secondary" onClick={locate}><LocateFixed size={18} /> Use my current location</Button>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Latitude" inputMode="decimal" value={form.latitude ?? ""} onChange={(e) => setForm({ ...form, latitude: e.target.value })} />
              <Field label="Longitude" inputMode="decimal" value={form.longitude ?? ""} onChange={(e) => setForm({ ...form, longitude: e.target.value })} />
            </div>
            <ActionError error={add.error} />
            <Button type="submit" block loading={add.isPending} disabled={!form.name?.trim()}>Add branch</Button>
          </form>
        )}
      </Sheet>
    </>
  );
}
