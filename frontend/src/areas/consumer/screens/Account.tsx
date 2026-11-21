import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Download, LogOut } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { consumer, useProfile } from "../../../api/consumer";
import { useAction } from "../../../api/business";
import { useEntitlement, useLogout } from "../../../api/hooks";
import type { Me } from "../../../api/types";
import type { Theme } from "../../../app/theme";
import { Banner, Button, Card, Field, Sheet, Skeleton } from "../../../ui";
import { ActionError } from "../../business/shared";
import { ThemeToggle } from "../../shared/ThemeToggle";

export default function Account({ me, theme, toggleTheme }: { me: Me; theme: Theme; toggleTheme: () => void }) {
  const profile = useProfile();
  const ent = useEntitlement();
  const qc = useQueryClient();
  const nav = useNavigate();
  const logout = useLogout();
  const [confirmDelete, setConfirmDelete] = useState("");
  const [deleting, setDeleting] = useState(false);
  const cancel = useAction(() => consumer.cancel(), [["entitlement"]]);
  const withdraw = useAction(() => consumer.consent("health_data", false), [["profile"]]);
  const del = useAction(() => consumer.deleteAccount(), []);
  const p = profile.data;
  const e = ent.data;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-extrabold">Profile</h1>
      <Card className="space-y-1"><p className="text-sm text-muted">Signed in as</p><p className="font-medium">{me.email}</p></Card>
      {profile.isPending ? <Skeleton className="h-32" /> : p && (
        <Card className="space-y-2">
          <div className="flex items-center justify-between"><p className="font-display font-bold">Targets</p><Link className="text-sm text-green-text underline" to="/onboarding">Edit</Link></div>
          {p.targets ? <>
            <p className="font-display text-2xl font-extrabold text-orange-text">{p.targets.energy_kcal.toLocaleString("en-IN")} kcal</p>
            <p className="text-sm text-muted">Protein {p.targets.protein_g} g · Carbs {p.targets.carbs_g} g · Fat {p.targets.fat_g} g</p>
            <p className="text-xs text-muted">{p.targets.note}</p></> : <p className="text-sm text-muted">Not set.</p>}
          <p className="text-sm">{[p.diet_type && { veg: "Vegetarian", egg: "Eggetarian", non_veg: "Non-vegetarian" }[p.diet_type], ...p.restrictions, p.allergies.length ? `Allergies: ${p.allergies.join(", ")}` : null].filter(Boolean).join(" · ")}</p>
        </Card>
      )}
      {e && (
        <Card className="space-y-2">
          <p className="font-display font-bold">{e.can.billing ? "Subscription" : "Access"}</p>
          <p>{e.display.title}{e.display.period ? ` · ${e.display.period}` : ""}</p>
          <p className="text-sm text-muted">{e.display.detail}</p>
          {e.can.cancel && <Button variant="secondary" loading={cancel.isPending} onClick={() => cancel.mutate(undefined)}>Cancel renewal</Button>}
          {e.cancelled && <p className="text-sm text-muted">Renewal cancelled. You keep access until the end of the period.</p>}
          <ActionError error={cancel.error} />
        </Card>
      )}
      <Link to="/profile/fingerprint" className="card flex min-h-14 items-center justify-between p-5 font-medium">Food fingerprint<span className="text-sm text-muted">What we've learned</span></Link>
      <Card className="flex items-center justify-between"><span className="font-medium">{theme === "dark" ? "Dark mode" : "Light mode"}</span><ThemeToggle theme={theme} toggle={toggleTheme} /></Card>
      <Card className="space-y-3">
        <p className="font-display font-bold">Your data</p>
        <a href="/api/v1/me/export" download className="inline-block"><Button variant="secondary"><Download size={18} /> Export my data</Button></a>
        {p?.consents.health_data && <div className="space-y-2">
          <p className="text-sm text-muted">Withdrawing consent deletes your height, weight, targets, restrictions and allergies.</p>
          <Button variant="ghost" loading={withdraw.isPending} onClick={() => withdraw.mutate(undefined)}>Withdraw health-data consent</Button>
        </div>}
        <Button variant="ghost" onClick={() => setDeleting(true)}>Delete my account</Button>
      </Card>
      <Button variant="secondary" loading={logout.isPending} onClick={() => logout.mutate(undefined, { onSettled: () => nav("/welcome", { replace: true }) })}><LogOut size={18} /> Sign out</Button>
      <Sheet open={deleting} onOpenChange={setDeleting} title="Delete your account">
        <div className="space-y-4">
          <Banner tone="problem" title="This can't be undone">Your profile and personal data are deleted. Diary entries are kept only without your identity, for anonymous statistics.</Banner>
          <Field label='Type DELETE to confirm' value={confirmDelete} onChange={(ev) => setConfirmDelete(ev.target.value)} />
          <ActionError error={del.error} />
          <Button variant="danger" block disabled={confirmDelete !== "DELETE"} loading={del.isPending}
            onClick={() => del.mutate(undefined, { onSuccess: () => { qc.clear(); nav("/welcome", { replace: true }); } })}>Delete account</Button>
        </div>
      </Sheet>
    </div>
  );
}
