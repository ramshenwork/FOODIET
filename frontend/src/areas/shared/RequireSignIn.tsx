import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useMe } from "../../api/hooks";
import type { Me } from "../../api/types";
import { ErrorState, Skeleton } from "../../ui";

/** Routing only: whether to show the sign-in page. All data access is still checked by the server. */
export function RequireSignIn({ signInPath, children }: { signInPath: string; children: (me: Me) => ReactNode }) {
  const me = useMe();
  const loc = useLocation();
  if (me.isPending) return <div className="mx-auto max-w-xl space-y-4 p-6"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-40" /></div>;
  if (me.isError) return <div className="mx-auto max-w-xl p-6"><ErrorState error={me.error} onRetry={() => me.refetch()} /></div>;
  if (!me.data) return <Navigate to={signInPath} replace state={{ from: loc.pathname }} />;
  return <>{children(me.data)}</>;
}
