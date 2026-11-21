import { useInfiniteQuery } from "@tanstack/react-query";
import { auditPage, useHealth } from "../../../api/admin";
import { Button, Card, ErrorState, Skeleton } from "../../../ui";
import { PageHeader } from "../../business/shared";
import { fmtDate, Pill } from "../shared";

export default function AuditScreen() {
  const health = useHealth();
  const log = useInfiniteQuery({
    queryKey: ["admin", "audit"], initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => auditPage(pageParam), getNextPageParam: (p) => p.next_cursor ?? undefined,
  });
  const items = log.data?.pages.flatMap((p) => p.items) ?? [];
  const h = health.data;
  return (
    <>
      <PageHeader title="Audit log and health" subtitle="Who changed what, scheduled job runs, and AI spend." />
      {health.isPending ? <Skeleton className="h-28" /> : health.isError ? <ErrorState error={health.error} /> : h && (
        <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card><p className="text-sm text-muted">Database</p><p className="mt-1"><Pill tone={h.database ? "green" : "red"}>{h.database ? "OK" : "Down"}</Pill></p></Card>
          <Card><p className="text-sm text-muted">Payments</p><p className="mt-1 font-medium capitalize">{h.payments_mode}</p><p className="text-xs text-muted">{h.environment}</p></Card>
          <Card><p className="text-sm text-muted">Email / storage</p><p className="mt-1 text-sm">{h.email_configured ? "Email on" : "Email not configured"}</p><p className="text-sm">{h.storage}</p></Card>
          <Card><p className="text-sm text-muted">AI spend this month</p>
            <p className="mt-1 font-display text-2xl font-extrabold">₹{h.ai.spent_this_month_inr.toLocaleString("en-IN")}</p>
            <p className="text-xs text-muted">{h.ai.configured ? `of ₹${h.ai.monthly_budget_inr?.toLocaleString("en-IN") ?? "?"} cap` : "AI provider not configured"}</p></Card>
        </div>
      )}
      {h && (
        <Card className="mb-6">
          <h2 className="mb-2 font-display text-lg font-bold">Job runs</h2>
          {h.job_runs.length === 0 ? <p className="text-sm text-muted">No jobs have run yet.</p> : (
            <div className="overflow-x-auto"><table className="dtable"><thead><tr><th>Job</th><th>Started</th><th>Finished</th><th>Status</th></tr></thead>
              <tbody>{h.job_runs.map((j, i) => <tr key={i}><td>{j.name}</td><td>{fmtDate(j.started_at)}</td><td>{fmtDate(j.finished_at)}</td>
                <td><Pill tone={j.status === "ok" ? "green" : j.status === "failed" ? "red" : "neutral"}>{j.status}</Pill></td></tr>)}</tbody></table></div>
          )}
        </Card>
      )}
      <div className="card overflow-x-auto">
        <h2 className="px-4 pt-4 font-display text-lg font-bold">Audit log</h2>
        {log.isPending ? <div className="p-4"><Skeleton className="h-48" /></div> : log.isError ? <ErrorState error={log.error} /> : (
          <table className="dtable mt-2">
            <thead><tr><th>When</th><th>Who</th><th>What</th><th>Target</th><th>Detail</th></tr></thead>
            <tbody>{items.map((a) => (
              <tr key={a.id}>
                <td className="whitespace-nowrap text-sm">{fmtDate(a.at)}</td><td className="text-sm">{a.actor}</td>
                <td className="text-sm font-medium">{a.action.replace(/_/g, " ")}</td>
                <td className="text-sm text-muted">{a.target_type ? `${a.target_type} ${a.target_id ?? ""}` : "–"}</td>
                <td className="max-w-xs truncate text-xs text-muted">{a.detail ? JSON.stringify(a.detail) : ""}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
        {log.hasNextPage && <div className="p-4"><Button variant="secondary" loading={log.isFetchingNextPage} onClick={() => log.fetchNextPage()}>Load more</Button></div>}
      </div>
    </>
  );
}
