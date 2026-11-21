import clsx from "clsx";

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton rounded-2xl", className)} aria-hidden />;
}

/** Shaped like a restaurant or dish card, never a spinner. */
export function CardSkeleton() {
  return (
    <div className="card overflow-hidden" aria-busy>
      <Skeleton className="h-36 rounded-none" />
      <div className="space-y-3 p-5">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-8 w-28 rounded-full" />
      </div>
    </div>
  );
}
