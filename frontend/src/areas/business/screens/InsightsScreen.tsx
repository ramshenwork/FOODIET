import { Eye, Search, ThumbsUp } from "lucide-react";
import { useFeedbackInsights } from "../../../api/business";
import { Banner, Card, CountUp, ErrorState, Skeleton } from "../../../ui";
import { useBiz } from "../context";
import { PageHeader } from "../shared";

/** Aggregate statistics only, shown above a minimum number of people. Never an individual diner. */
export default function InsightsScreen() {
  const { business } = useBiz();
  const q = useFeedbackInsights(business.id);
  if (q.isPending) return <Skeleton className="h-96" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  return (
    <>
      <PageHeader title="Insights" subtitle={d.minimum_note} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Card><Eye size={20} className="text-green-text" /><p className="mt-2 text-sm text-muted">Dish views, last 7 days</p>
          <p className="font-display text-4xl font-extrabold"><CountUp value={d.total_views_7d} /></p></Card>
        <Card><ThumbsUp size={20} className="text-green-text" /><p className="mt-2 text-sm text-muted">Diner check-ins, last 30 days</p>
          <p className="font-medium">{d.checkins_30d}</p>{d.recommend_rate && <p className="mt-1 font-display text-xl font-bold">{d.recommend_rate}</p>}</Card>
        <Card><Search size={20} className="text-green-text" /><p className="mt-2 text-sm text-muted">Unmet demand nearby</p>
          <p className="font-medium">{d.unmet_summary}</p></Card>
      </div>
      {!d.detailed ? (
        <div className="mt-6"><Banner tone="note" title="Detailed insights come with the paid plan">Per-dish recommend rates, check-in feedback and exactly what nearby diners searched for and couldn't find.</Banner></div>
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <section className="card overflow-x-auto">
            <h2 className="px-4 pt-4 font-display text-lg font-bold">By dish</h2>
            {d.dishes.length === 0 ? <p className="p-4 text-sm text-muted">No dish activity yet.</p> : (
              <table className="dtable mt-2"><thead><tr><th>Dish</th><th>Views (7d)</th><th>Diners say</th></tr></thead>
                <tbody>{d.dishes.map((x) => (
                  <tr key={x.menu_item_id}><td className="font-medium">{x.name}</td><td>{x.views_7d}</td>
                    <td className="text-sm">{[x.recommend, x.felt].filter(Boolean).join(" · ") || <span className="text-muted">Not enough people yet</span>}</td></tr>
                ))}</tbody></table>
            )}
          </section>
          <section className="card p-4">
            <h2 className="font-display text-lg font-bold">Searched nearby, found nothing</h2>
            {d.unmet_demand.length === 0 ? <p className="mt-2 text-sm text-muted">Nothing above the minimum yet.</p> : (
              <ul className="mt-3 space-y-2">{d.unmet_demand.map((u) => <li key={u.display} className="rounded-2xl bg-chip-green p-3 text-sm">{u.display}</li>)}</ul>
            )}
          </section>
        </div>
      )}
    </>
  );
}
