import { useState } from "react";
import { admin, useDisputes, useReports, type Dispute, type Report } from "../../../api/admin";
import { useAction } from "../../../api/business";
import { Button, EmptyState, ErrorState, Select, Sheet, Skeleton } from "../../../ui";
import { ActionError, PageHeader } from "../../business/shared";
import { fmtDate, Pill, Tabs, TextArea } from "../shared";

const TYPE: Record<Report["type"], string> = { allergen_concern: "Allergen concern", menu_changed: "Menu changed", portion_wrong: "Portion wrong" };

export default function ReportsScreen() {
  const [tab, setTab] = useState<"reports" | "disputes">("reports");
  const reports = useReports();
  const disputes = useDisputes();
  const [report, setReport] = useState<{ r: Report; status: string; note: string } | null>(null);
  const [dispute, setDispute] = useState<{ d: Dispute; status: "upheld" | "rejected"; note: string } | null>(null);
  const saveReport = useAction(() => admin.updateReport(report!.r.id, report!.status, report!.note), [["admin", "reports"]]);
  const saveDispute = useAction(() => admin.resolveDispute(dispute!.d.id, dispute!.status, dispute!.note), [["admin", "disputes"], ["admin", "queue"]]);
  const openDisputes = disputes.data?.filter((d) => d.status === "open").length ?? 0;

  return (
    <>
      <PageHeader title="Reports and disputes" subtitle="Allergen concerns first. Restaurants can explain, but never remove a report." />
      <Tabs value={tab} onChange={setTab} tabs={[["reports", `Diner reports`], ["disputes", `Restaurant disputes${openDisputes ? ` (${openDisputes})` : ""}`]]} />
      {tab === "reports" ? (reports.isPending ? <Skeleton className="h-64" /> : reports.isError ? <ErrorState error={reports.error} /> :
        reports.data.length === 0 ? <EmptyState title="No reports" body="Diner reports arrive once the diner app launches." /> : (
          <div className="card overflow-x-auto">
            <table className="dtable">
              <thead><tr><th>Type</th><th>Dish</th><th>Restaurant</th><th>Detail</th><th>Received</th><th>Status</th><th className="sr-only">Act</th></tr></thead>
              <tbody>{reports.data.map((r) => (
                <tr key={r.id}>
                  <td><Pill tone={r.type === "allergen_concern" ? "red" : "neutral"}>{TYPE[r.type]}</Pill></td>
                  <td>{r.menu_item_name}</td><td>{r.business_name}<p className="text-xs text-muted">{r.branch_name}</p></td>
                  <td className="max-w-xs text-sm">{r.detail}</td><td className="whitespace-nowrap text-sm">{fmtDate(r.created_at)}</td>
                  <td><Pill tone={r.status === "resolved" ? "green" : "neutral"}>{r.status}</Pill></td>
                  <td><Button variant="ghost" onClick={() => setReport({ r, status: r.status === "open" ? "reviewing" : r.status, note: r.resolution_note ?? "" })}>Update</Button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )) : (disputes.isPending ? <Skeleton className="h-64" /> : disputes.isError ? <ErrorState error={disputes.error} /> :
        disputes.data.length === 0 ? <EmptyState title="No disputes" body="Restaurants can explain a held recipe from their recipe builder." /> : (
          <div className="card overflow-x-auto">
            <table className="dtable">
              <thead><tr><th>Restaurant</th><th>What they say</th><th>Raised</th><th>Status</th><th className="sr-only">Act</th></tr></thead>
              <tbody>{disputes.data.map((d) => (
                <tr key={d.id}>
                  <td>{d.business_name}</td><td className="max-w-md text-sm">{d.detail}{d.resolution_note && <p className="mt-1 text-xs text-muted">Decision: {d.resolution_note}</p>}</td>
                  <td className="whitespace-nowrap text-sm">{fmtDate(d.created_at)}</td>
                  <td><Pill tone={d.status === "upheld" ? "green" : d.status === "rejected" ? "red" : "neutral"}>{d.status}</Pill></td>
                  <td>{d.status === "open" && <Button variant="ghost" onClick={() => setDispute({ d, status: "upheld", note: "" })}>Decide</Button>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ))}

      <Sheet open={report !== null} onOpenChange={(o) => { if (!o) { setReport(null); saveReport.reset(); } }} title="Update report">
        {report && (
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); saveReport.mutate(undefined, { onSuccess: () => setReport(null) }); }}>
            <p className="text-sm">{report.r.detail}</p>
            <Select label="Status" value={report.status} onChange={(e) => setReport({ ...report, status: e.target.value })}
              options={["open", "reviewing", "resolved", "dismissed"].map((s) => ({ value: s, label: s }))} />
            <TextArea label="Note" value={report.note} onChange={(note) => setReport({ ...report, note })} />
            <ActionError error={saveReport.error} />
            <Button type="submit" block loading={saveReport.isPending}>Save</Button>
          </form>
        )}
      </Sheet>
      <Sheet open={dispute !== null} onOpenChange={(o) => { if (!o) { setDispute(null); saveDispute.reset(); } }} title="Decide dispute">
        {dispute && (
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); saveDispute.mutate(undefined, { onSuccess: () => setDispute(null) }); }}>
            <p className="text-sm">{dispute.d.detail}</p>
            <Select label="Decision" value={dispute.status} onChange={(e) => setDispute({ ...dispute, status: e.target.value as "upheld" | "rejected" })}
              options={[{ value: "upheld", label: "Uphold: the restaurant is right" }, { value: "rejected", label: "Reject" }]} />
            <TextArea label="Note to the restaurant" value={dispute.note} onChange={(note) => setDispute({ ...dispute, note })} />
            <p className="text-xs text-muted">Upholding doesn't publish the recipe by itself; approve it in the review queue.</p>
            <ActionError error={saveDispute.error} />
            <Button type="submit" block loading={saveDispute.isPending} disabled={!dispute.note.trim()}>Save decision</Button>
          </form>
        )}
      </Sheet>
    </>
  );
}
