import { useState } from "react";
import { Check, Undo2 } from "lucide-react";
import { admin, useQueue, type QueueItem } from "../../../api/admin";
import { useAction } from "../../../api/business";
import { Banner, Button, Card, EmptyState, ErrorState, Skeleton } from "../../../ui";
import { ActionError, PageHeader } from "../../business/shared";
import { fmtDate, Pill, TextArea } from "../shared";

function Entry({ item }: { item: QueueItem }) {
  const [note, setNote] = useState("");
  const act = useAction((d: "approve" | "return") => admin.resolve(item.version_id, d, note), [["admin", "queue"], ["admin", "disputes"]]);
  const rows: [string, keyof QueueItem["new"]][] = [["Energy per 100 g", "energy_100g"], ["Protein per 100 g", "protein_100g"],
    ["Fat per 100 g", "fat_100g"], ["Cooked yield (g)", "cooked_yield_g"], ["Raw ingredients (g)", "raw_total_g"]];
  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="font-display text-lg font-bold">{item.recipe_name} · version {item.version_number}</h2>
          <p className="text-sm text-muted">{item.business_name} · submitted {fmtDate(item.declared_at)}</p>
        </div>
      </div>
      <div className="space-y-2">
        {item.flags.map((f) => <Banner key={f.id} tone="problem" title={f.rule.replace(/_/g, " ")}>{f.message}</Banner>)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <table className="dtable">
          <thead><tr><th>Value</th><th>Published (v{item.previous?.version_number ?? "–"})</th><th>New (v{item.new.version_number})</th></tr></thead>
          <tbody>{rows.map(([label, k]) => (
            <tr key={k}><td className="text-muted">{label}</td><td>{item.previous?.[k] ?? "–"}</td><td className="font-medium">{item.new[k] ?? "–"}</td></tr>
          ))}</tbody>
        </table>
        <div>
          <p className="mb-2 text-sm font-semibold">Ingredients</p>
          <ul className="space-y-1 text-sm text-muted">{item.lines.map((l, i) => <li key={i}>{l}</li>)}</ul>
        </div>
      </div>
      {item.disputes.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-semibold">What the restaurant says</p>
          {item.disputes.map((d) => <Banner key={d.id} tone="note" title={`${d.business_name ?? "Restaurant"} · ${fmtDate(d.created_at)}`}>{d.detail}</Banner>)}
        </div>
      )}
      <TextArea label="Note to the restaurant" value={note} onChange={setNote} placeholder="Required when returning: what should they fix?" />
      <ActionError error={act.error} />
      <div className="flex flex-wrap gap-2">
        <Button loading={act.isPending && act.variables === "approve"} onClick={() => act.mutate("approve")}><Check size={18} /> Approve and publish</Button>
        <Button variant="secondary" loading={act.isPending && act.variables === "return"} disabled={!note.trim()} onClick={() => act.mutate("return")}><Undo2 size={18} /> Return to restaurant</Button>
      </div>
    </Card>
  );
}

export default function ReviewQueue() {
  const q = useQueue();
  return (
    <>
      <PageHeader title="Review queue" subtitle="Recipe versions held by a check. Nothing here is visible to diners until approved." />
      {q.isPending ? <Skeleton className="h-64" /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> :
        q.data.length === 0 ? <EmptyState title="Nothing waiting" body="Held recipe versions appear here." /> :
          <div className="space-y-6">
            <p className="text-sm text-muted"><Pill tone="neutral">{q.data.length} waiting</Pill> Oldest first.</p>
            {q.data.map((i) => <Entry key={i.version_id} item={i} />)}
          </div>}
    </>
  );
}
