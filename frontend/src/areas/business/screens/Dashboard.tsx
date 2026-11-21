import { Link } from "react-router-dom";
import { useDashboard } from "../../../api/business";
import { Card, CountUp, ErrorState, Skeleton } from "../../../ui";
import { useBiz } from "../context";
import { PageHeader } from "../shared";

export default function Dashboard() {
  const { business } = useBiz();
  const q = useDashboard(business.id);
  if (q.isPending) return <div className="grid gap-4 sm:grid-cols-3">{[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-28" />)}</div>;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  const tiles: { label: string; value: number; to?: string; hint?: string; suffix?: string }[] = [
    { label: "Menu completion", value: d.menu_completion_pct, suffix: "%", hint: "dishes showing nutrition", to: "/business/menu" },
    { label: "Published dishes", value: d.published_dishes, hint: `of ${d.menu_items} on the menu`, to: "/business/menu" },
    { label: "Dishes awaiting recipes", value: d.awaiting_recipes, to: "/business/recipes" },
    { label: "Recipes expiring soon", value: d.recipes_expiring_soon, hint: "reconfirm within 14 days", to: "/business/menu" },
    { label: "Held for review", value: d.held_versions, hint: `${d.open_flags} open check${d.open_flags === 1 ? "" : "s"}`, to: "/business/recipes" },
    { label: "Declared recipes", value: d.with_declared_recipe, to: "/business/recipes" },
  ];
  return (
    <>
      <PageHeader title={business.name} subtitle={`${business.plan_label} · ${business.branches.length} branch${business.branches.length === 1 ? "" : "es"}`} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tiles.map((t) => {
          const body = (
            <Card className="h-full transition-transform duration-200 hover:-translate-y-0.5">
              <p className="text-sm text-muted">{t.label}</p>
              <p className="mt-2 font-display text-4xl font-extrabold"><CountUp value={t.value} />{t.suffix}</p>
              {t.hint && <p className="mt-1 text-sm text-muted">{t.hint}</p>}
            </Card>
          );
          return t.to ? <Link key={t.label} to={t.to} className="block rounded-[24px]">{body}</Link> : <div key={t.label}>{body}</div>;
        })}
      </div>
      <Card className="mt-6">
        <h2 className="font-display text-lg font-bold">Most-viewed dishes</h2>
        <p className="mt-1 text-sm text-muted">Diner views start counting when the diner app launches.</p>
      </Card>
    </>
  );
}
