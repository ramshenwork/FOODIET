import { useState } from "react";
import { BadgeCheck, ShieldOff } from "lucide-react";
import { admin, findVersions, useVerified, type VersionHit } from "../../../api/admin";
import { useAction } from "../../../api/business";
import { Autocomplete, Button, Card, EmptyState, ErrorState, Field, Select, Sheet, Skeleton, TrustLabel } from "../../../ui";
import { ActionError, PageHeader } from "../../business/shared";
import { fmtDate, TextArea } from "../shared";

type Hit = VersionHit & { id: string; name: string };
const search = (q: string): Promise<Hit[]> =>
  findVersions(q).then((hs) => hs.map((h) => ({ ...h, id: h.version_id, name: `${h.recipe_name} v${h.version_number} · ${h.business_name}` })));

export default function TrustScreen() {
  const verified = useVerified();
  const [pick, setPick] = useState<Hit | null>(null);
  const [kind, setKind] = useState("lab_test");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [revoking, setRevoking] = useState<{ id: string; reason: string } | null>(null);
  const grant = useAction(() => admin.verify(pick!.version_id, kind, reference, notes), [["admin", "verified"]]);
  const revoke = useAction(() => admin.revoke(revoking!.id, revoking!.reason), [["admin", "verified"]]);

  return (
    <>
      <PageHeader title="Trust" subtitle="Grant or revoke the Verified label. It lasts 90 days, then falls back to Restaurant-declared." />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="card overflow-x-auto">
          <h2 className="px-4 pt-4 font-display text-lg font-bold">Verified now</h2>
          {verified.isPending ? <div className="p-4"><Skeleton className="h-32" /></div> : verified.isError ? <ErrorState error={verified.error} /> :
            verified.data.length === 0 ? <div className="p-4"><EmptyState title="Nothing verified yet" /></div> : (
              <table className="dtable mt-2">
                <thead><tr><th>Recipe</th><th>Restaurant</th><th>Evidence</th><th>Expires</th><th className="sr-only">Act</th></tr></thead>
                <tbody>{verified.data.map((v) => (
                  <tr key={v.version_id}>
                    <td>{v.recipe_name} <span className="text-muted">v{v.version_number}</span></td><td>{v.business_name}</td>
                    <td className="text-sm">{v.evidence?.kind === "lab_test" ? "Lab test" : "Audit"} {v.evidence?.reference}</td>
                    <td className="whitespace-nowrap text-sm">{fmtDate(v.expires_at)}</td>
                    <td><Button variant="ghost" onClick={() => setRevoking({ id: v.version_id, reason: "" })}><ShieldOff size={16} /> Revoke</Button></td>
                  </tr>
                ))}</tbody>
              </table>
            )}
        </div>
        <Card className="space-y-4">
          <h2 className="font-display text-lg font-bold">Grant Verified</h2>
          <Autocomplete label="Published recipe version" placeholder="Search recipe or restaurant" value={pick?.name ?? ""} search={search}
            onPick={setPick} render={(h) => <span className="flex items-center justify-between gap-2"><span>{h.name}</span><TrustLabel kind={h.label as "declared"} /></span>} />
          <Select label="Evidence" value={kind} onChange={(e) => setKind(e.target.value)} options={[{ value: "lab_test", label: "Lab test" }, { value: "audit", label: "Kitchen audit" }]} />
          <Field label="Report or audit reference" value={reference} onChange={(e) => setReference(e.target.value)} />
          <TextArea label="Notes" value={notes} onChange={setNotes} />
          <ActionError error={grant.error} />
          {grant.isSuccess && <p className="text-sm text-green-text">Verified label granted.</p>}
          <Button block loading={grant.isPending} disabled={!pick || !reference.trim()}
            onClick={() => grant.mutate(undefined, { onSuccess: () => { setPick(null); setReference(""); setNotes(""); } })}><BadgeCheck size={18} /> Grant Verified</Button>
        </Card>
      </div>
      <Sheet open={revoking !== null} onOpenChange={(o) => { if (!o) { setRevoking(null); revoke.reset(); } }} title="Revoke Verified">
        {revoking && (
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); revoke.mutate(undefined, { onSuccess: () => setRevoking(null) }); }}>
            <TextArea label="Reason (kept in the audit log)" value={revoking.reason} onChange={(reason) => setRevoking({ ...revoking, reason })} />
            <ActionError error={revoke.error} />
            <Button type="submit" variant="danger" block loading={revoke.isPending} disabled={!revoking.reason.trim()}>Revoke</Button>
          </form>
        )}
      </Sheet>
    </>
  );
}
