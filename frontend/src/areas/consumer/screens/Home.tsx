import { Link } from "react-router-dom";
import { useDay, useNearby } from "../../../api/consumer";
import type { Me } from "../../../api/types";
import { Card, CardSkeleton, EmptyState, ErrorState, MacroRings, Skeleton } from "../../../ui";
import { LocationPrompt } from "../LocationPrompt";
import { useLocationCtx } from "../location";
import { CheckinCard } from "../CheckinCard";
import { RestaurantCardView } from "../parts";

export function today(): string {
  // The calendar date in India; the server decides what that day contains.
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
}

export default function Home({ me }: { me: Me }) {
  const day = useDay(today());
  const { coords } = useLocationCtx();
  const nearby = useNearby(coords);
  const d = day.data;
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted">Hello, {me.email.split("@")[0]}</p>
      {day.isPending ? <Skeleton className="h-60" /> : day.isError ? <ErrorState error={day.error} onRetry={() => day.refetch()} /> :
        d?.rings ? (
          <Card>
            <MacroRings energyValue={d.energy_value} energyCaption={d.energy_caption ?? ""}
              energy={d.rings.energy} macros={[d.rings.protein, d.rings.carbs, d.rings.fat]} />
            <p className="mt-4 text-center font-medium">{d.remaining_display}</p>
          </Card>
        ) : <EmptyState title="Set your goal" body="Finish your profile to see today's targets." action={<Link className="text-green-text underline" to="/onboarding">Set up</Link>} />}
      <CheckinCard />
      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-xl font-bold">Fits you nearby</h2>
          {nearby.data?.meal_budget_display && <span className="text-sm text-muted">{nearby.data.meal_budget_display}</span>}
        </div>
        {!coords ? <LocationPrompt /> : nearby.isPending ? <div className="grid gap-4 sm:grid-cols-2"><CardSkeleton /><CardSkeleton /></div> :
          nearby.isError ? <ErrorState error={nearby.error} onRetry={() => nearby.refetch()} /> :
            nearby.data.restaurants.length === 0 ? <EmptyState title="No restaurants with menus nearby yet" /> :
              <div className="grid gap-4 sm:grid-cols-2">{nearby.data.restaurants.map((r) => <RestaurantCardView key={r.id} r={r} />)}</div>}
      </section>
    </div>
  );
}
