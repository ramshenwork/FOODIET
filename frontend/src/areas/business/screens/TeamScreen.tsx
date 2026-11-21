import { useState } from "react";
import { UserPlus } from "lucide-react";
import { calls, planCalls, useAction, usePlan, useTeam } from "../../../api/business";
import { api } from "../../../api/client";
import { openCheckout } from "../../../api/payments";
import { Button, Card, ErrorState, Field, Select, Skeleton } from "../../../ui";
import { useBiz } from "../context";
import { ActionError, PageHeader } from "../shared";

export default function TeamScreen() {
  const { business } = useBiz();
  const team = useTeam(business.id);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("chef");
  const add = useAction(() => calls.addMember(business.id, { email, role }), [["team", business.id]]);
  const plan = usePlan(business.id, business.billing);
  const upgrade = useAction(async () => {
    const r = await planCalls.subscribe(business.id);
    if (r.checkout && (await openCheckout(r.checkout)) === "closed") return;
    for (let i = 0; i < 30; i++) {   // the server confirms by webhook; wait for it
      const b = await api<{ plan: string }>(`/business/${business.id}`);
      if (b.plan === "paid") return;
      await new Promise((res) => setTimeout(res, 2000));
    }
  }, [["businesses"], ["plan", business.id]]);
  const downgrade = useAction(() => planCalls.cancel(business.id), [["businesses"], ["plan", business.id]]);
  return (
    <>
      <PageHeader title={business.billing ? "Team and plan" : "Team"} subtitle={business.plan_label} />
      {business.billing && <Card className="mb-6 space-y-3">
        <h2 className="font-display text-lg font-bold">Plan</h2>
        {business.plan === "free" ? (
          <>
            <p className="text-sm text-muted">Free: one branch, owner only, summary insights. Paid adds many branches with shared recipes, team roles, detailed insights and recipe suggestions. Paying never changes ranking or trust labels.</p>
            {business.my_role === "owner" && <Button loading={upgrade.isPending} onClick={() => upgrade.mutate(undefined)}>Upgrade to paid</Button>}
            {plan.data?.mode === "mock" && <p className="text-xs text-muted">Test mode: no real payment is taken.</p>}
          </>
        ) : (
          <>
            <p className="text-sm">Paid plan{plan.data?.renews_until ? ` · current period ends ${new Date(plan.data.renews_until).toLocaleDateString("en-IN", { dateStyle: "medium" })}` : ""}</p>
            {business.my_role === "owner" && <Button variant="ghost" loading={downgrade.isPending} onClick={() => downgrade.mutate(undefined)}>Cancel at period end</Button>}
          </>
        )}
        <ActionError error={upgrade.error ?? downgrade.error} />
      </Card>}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-display text-lg font-bold">People</h2>
          {team.isPending ? <Skeleton className="h-24" /> : team.isError ? <ErrorState error={team.error} /> : (
            <ul className="divide-y divide-line">{team.data.map((m) => (
              <li key={m.user_id} className="flex justify-between py-2 text-sm"><span>{m.email}</span><span className="capitalize text-muted">{m.role}</span></li>
            ))}</ul>
          )}
        </Card>
        <Card>
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); add.mutate(undefined, { onSuccess: () => setEmail("") }); }}>
            <h2 className="font-display text-lg font-bold">Add someone</h2>
            <Field label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <Select label="Role" value={role} onChange={(e) => setRole(e.target.value)}
              options={[{ value: "manager", label: "Manager: everything except team" }, { value: "chef", label: "Chef: recipes" }, { value: "editor", label: "Editor: menu" }]} />
            <ActionError error={add.error} />
            <Button type="submit" loading={add.isPending} disabled={!email}><UserPlus size={18} /> Add</Button>
          </form>
        </Card>
      </div>
    </>
  );
}
