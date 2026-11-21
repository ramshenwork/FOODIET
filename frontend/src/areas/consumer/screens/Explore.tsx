import { useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { searchPage, type SearchParams } from "../../../api/consumer";
import { Button, Chip, EmptyState, ErrorState, Skeleton } from "../../../ui";
import { LocationPrompt } from "../LocationPrompt";
import { useLocationCtx } from "../location";
import { DishRow, RestaurantCardView } from "../parts";

const ENERGY = [undefined, 400, 600, 800];
const PROTEIN = [undefined, 15, 25, 35];
const PRICE = [undefined, 150, 300, 500];
const DIST = [undefined, 1, 2, 5];

function Cycle<T>({ label, values, value, show, onChange }: { label: string; values: (T | undefined)[]; value: T | undefined; show: (v: T) => string; onChange: (v: T | undefined) => void }) {
  const next = values[(values.indexOf(value) + 1) % values.length];
  return <Chip tone={value === undefined ? "neutral" : "orange"} selected={value !== undefined} onClick={() => onChange(next)}>{value === undefined ? label : show(value)}</Chip>;
}

export default function Explore() {
  const { coords } = useLocationCtx();
  const [text, setText] = useState("");
  const [p, setP] = useState<SearchParams>({});
  const [view, setView] = useState<"dishes" | "restaurants">("dishes");
  const q = useInfiniteQuery({
    queryKey: ["search", coords, p], enabled: !!coords, initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => searchPage(coords!, p, pageParam), getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const dishes = q.data?.pages.flatMap((x) => x.dishes) ?? [];
  const restaurants = q.data?.pages[0]?.restaurants ?? [];
  const toggleTrust = (t: string) => setP({ ...p, trust: p.trust?.includes(t) ? p.trust.filter((x) => x !== t) : [...(p.trust ?? []), t] });

  return (
    <div className="space-y-4">
      <form onSubmit={(e) => { e.preventDefault(); setP({ ...p, q: text.trim() || undefined }); }} className="relative">
        <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Dishes or restaurants, e.g. dosa" aria-label="Search"
          className="min-h-12 w-full rounded-full border border-line bg-card pl-11 pr-4 outline-none focus:border-green" />
      </form>
      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
        <Cycle label="Energy" values={ENERGY} value={p.max_kcal} show={(v) => `Under ${v} kcal`} onChange={(v) => setP({ ...p, max_kcal: v })} />
        <Cycle label="Protein" values={PROTEIN} value={p.min_protein} show={(v) => `${v} g+ protein`} onChange={(v) => setP({ ...p, min_protein: v })} />
        <Cycle label="Price" values={PRICE} value={p.max_price} show={(v) => `Under ₹${v}`} onChange={(v) => setP({ ...p, max_price: v })} />
        <Cycle label="Distance" values={DIST} value={p.max_km} show={(v) => `Within ${v} km`} onChange={(v) => setP({ ...p, max_km: v })} />
        <Chip tone="neutral" selected={p.trust?.includes("verified")} onClick={() => toggleTrust("verified")}>Verified</Chip>
        <Chip tone="neutral" selected={p.trust?.includes("declared")} onClick={() => toggleTrust("declared")}>Restaurant-declared</Chip>
      </div>
      <p className="text-xs text-muted">Your diet, restrictions and allergies from your profile always apply.</p>
      <div className="flex gap-2">
        <Chip tone="green" selected={view === "dishes"} onClick={() => setView("dishes")}>Dishes</Chip>
        <Chip tone="green" selected={view === "restaurants"} onClick={() => setView("restaurants")}>Restaurants</Chip>
      </div>
      {!coords ? <LocationPrompt /> : q.isPending ? <div className="space-y-3"><Skeleton className="h-20" /><Skeleton className="h-20" /><Skeleton className="h-20" /></div> :
        q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : view === "dishes" ? (
          dishes.length === 0 ? <EmptyState title="Nothing matches" body="Try a wider energy, price or distance filter." /> : (
            <div className="space-y-3">
              {dishes.map((d) => <DishRow key={d.id} d={d} showRestaurant />)}
              {q.hasNextPage && <Button variant="secondary" block loading={q.isFetchingNextPage} onClick={() => q.fetchNextPage()}>More dishes</Button>}
            </div>
          )
        ) : restaurants.length === 0 ? <EmptyState title="No restaurants match" /> :
          <div className="grid gap-4 sm:grid-cols-2">{restaurants.map((r) => <RestaurantCardView key={r.id} r={r} />)}</div>}
    </div>
  );
}
