import { EmptyState } from "../../ui";

/** Placeholder for screens scheduled in a later build phase (spec section 14). */
export function Upcoming({ title, phase }: { title: string; phase: number }) {
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-extrabold">{title}</h1>
      <EmptyState title="Not built yet" body={`This screen is scheduled for build phase ${phase}.`} />
    </section>
  );
}
