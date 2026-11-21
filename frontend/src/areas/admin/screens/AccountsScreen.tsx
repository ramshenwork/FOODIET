import { useState } from "react";
import { useBilling, useBusinessesAdmin, useUsers, admin, type UserRow } from "../../../api/admin";
import { useAction } from "../../../api/business";
import { Button, ErrorState, Field, Select, Sheet, Skeleton } from "../../../ui";
import { ActionError, PageHeader } from "../../business/shared";
import { fmtDate, Pill, Tabs, TextArea } from "../shared";

export default function AccountsScreen() {
  const [tab, setTab] = useState<"users" | "businesses" | "billing">("users");
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const users = useUsers(q || undefined, role || undefined);
  const biz = useBusinessesAdmin(q || undefined);
  const billing = useBilling();
  const [change, setChange] = useState<{ u: UserRow; reason: string } | null>(null);
  const setStatus = useAction(() => admin.setUserStatus(change!.u.id, change!.u.status === "active" ? "suspended" : "active", change!.reason), [["admin", "users"]]);

  return (
    <>
      <PageHeader title="Accounts" subtitle="People, restaurants, subscriptions and trial claims." />
      <Tabs value={tab} onChange={setTab} tabs={[["users", "People"], ["businesses", "Restaurants"], ["billing", "Subscriptions and trials"]]} />
      {tab !== "billing" && (
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div className="w-64"><Field label={tab === "users" ? "Search email" : "Search name"} value={q} onChange={(e) => setQ(e.target.value)} /></div>
          {tab === "users" && <div className="w-48"><Select label="Role" value={role} onChange={(e) => setRole(e.target.value)}
            options={[{ value: "", label: "All" }, { value: "consumer", label: "Diner" }, { value: "business", label: "Restaurant" }, { value: "admin", label: "Admin" }]} /></div>}
        </div>
      )}
      {tab === "users" && (users.isPending ? <Skeleton className="h-64" /> : users.isError ? <ErrorState error={users.error} /> : (
        <div className="card max-h-[70vh] overflow-auto">
          <table className="dtable">
            <thead><tr><th>Email</th><th>Role</th><th>Access</th><th>Status</th><th>Joined</th><th className="sr-only">Act</th></tr></thead>
            <tbody>{users.data.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td><td className="capitalize">{u.role}</td><td className="capitalize">{u.access_level}</td>
                <td><Pill tone={u.status === "active" ? "green" : "red"}>{u.status}</Pill></td><td className="text-sm">{fmtDate(u.created_at)}</td>
                <td>{u.role !== "admin" && <Button variant="ghost" onClick={() => setChange({ u, reason: "" })}>{u.status === "active" ? "Suspend" : "Reactivate"}</Button>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      ))}
      {tab === "businesses" && (biz.isPending ? <Skeleton className="h-64" /> : biz.isError ? <ErrorState error={biz.error} /> : (
        <div className="card max-h-[70vh] overflow-auto">
          <table className="dtable">
            <thead><tr><th>Restaurant</th><th>Owner</th><th>Plan</th><th>Branches</th><th>Team</th></tr></thead>
            <tbody>{biz.data.map((b) => <tr key={b.id}><td className="font-medium">{b.name}</td><td>{b.owner_email}</td><td className="capitalize">{b.plan}</td><td>{b.branches}</td><td>{b.members}</td></tr>)}</tbody>
          </table>
        </div>
      ))}
      {tab === "billing" && (billing.isPending ? <Skeleton className="h-40" /> : billing.isError ? <ErrorState error={billing.error} /> : (
        <div className="space-y-4">
          <div className="card p-5"><p className="text-sm text-muted">Trials claimed</p><p className="font-display text-3xl font-extrabold">{billing.data.trial_claims}</p>
            <p className="text-xs text-muted">Emails are stored only as hashes to enforce one trial per person.</p></div>
          <div className="card overflow-auto">
            {billing.data.subscriptions.length === 0 ? <p className="p-5 text-sm text-muted">No subscriptions yet. Billing arrives in phase 5.</p> : (
              <table className="dtable"><thead><tr><th>Plan</th><th>Status</th><th>Provider</th><th>Period ends</th></tr></thead>
                <tbody>{billing.data.subscriptions.map((s) => <tr key={s.id}><td>{s.plan}</td><td>{s.status}</td><td>{s.provider}</td><td>{fmtDate(s.current_period_end)}</td></tr>)}</tbody></table>
            )}
          </div>
        </div>
      ))}
      <Sheet open={change !== null} onOpenChange={(o) => { if (!o) { setChange(null); setStatus.reset(); } }} title={change?.u.status === "active" ? "Suspend account" : "Reactivate account"}>
        {change && (
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); setStatus.mutate(undefined, { onSuccess: () => setChange(null) }); }}>
            <p className="text-sm">{change.u.email}{change.u.status === "active" && " will be signed out everywhere and can't sign in until reactivated."}</p>
            <TextArea label="Reason (kept in the audit log)" value={change.reason} onChange={(reason) => setChange({ ...change, reason })} />
            <ActionError error={setStatus.error} />
            <Button type="submit" variant={change.u.status === "active" ? "danger" : "primary"} block loading={setStatus.isPending} disabled={!change.reason.trim()}>
              {change.u.status === "active" ? "Suspend" : "Reactivate"}</Button>
          </form>
        )}
      </Sheet>
    </>
  );
}
