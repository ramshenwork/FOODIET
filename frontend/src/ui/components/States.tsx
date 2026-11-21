import { CloudOff, Lock, RefreshCw, SearchX } from "lucide-react";
import type { ReactNode } from "react";
import { ApiError } from "../../api/client";
import { Button } from "./Button";

function Shell({ icon, title, body, action }: { icon: ReactNode; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-start gap-3 p-6">
      <div className="grid size-11 place-items-center rounded-2xl bg-chip-green text-green-text">{icon}</div>
      <h3 className="font-display text-lg font-bold">{title}</h3>
      {body && <p className="text-sm text-muted">{body}</p>}
      {action}
    </div>
  );
}

export function EmptyState({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return <Shell icon={<SearchX size={20} />} title={title} body={body} action={action} />;
}

/** Handles the error, offline and paywall cases with one component. */
export function ErrorState({ error, onRetry, onPaywall }: { error: unknown; onRetry?: () => void; onPaywall?: () => void }) {
  if (error instanceof ApiError && error.isPaywall) {
    return <Shell icon={<Lock size={20} />} title="Part of the subscription"
      body={error.paywall?.message ?? error.message}
      action={onPaywall && <Button onClick={onPaywall}>{error.paywall?.trial_available ? "Start free trial" : "See plans"}</Button>} />;
  }
  if (error instanceof ApiError && error.isOffline) {
    return <Shell icon={<CloudOff size={20} />} title="You're offline" body="Check your connection and try again."
      action={onRetry && <Button variant="secondary" onClick={onRetry}><RefreshCw size={16} /> Retry</Button>} />;
  }
  const msg = error instanceof ApiError ? error.message : "Something went wrong.";
  const rid = error instanceof ApiError ? error.requestId : undefined;
  return (
    <div role="alert" className="card flex flex-col items-start gap-3 border-l-4 border-danger p-6">
      <h3 className="font-display text-lg font-bold">Couldn't load this</h3>
      <p className="text-sm text-muted">{msg}{rid ? ` (ref ${rid})` : ""}</p>
      {onRetry && <Button variant="secondary" onClick={onRetry}><RefreshCw size={16} /> Retry</Button>}
    </div>
  );
}
