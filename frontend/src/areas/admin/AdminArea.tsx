import { lazy, Suspense } from "react";
import { BookOpen, ClipboardCheck, Flag, LogOut, ScrollText, ShieldCheck, Users } from "lucide-react";
import { Route, Routes, useNavigate } from "react-router-dom";
import { useLogout } from "../../api/hooks";
import { useAreaTheme } from "../../app/theme";
import { EmptyState, Skeleton } from "../../ui";
import { AreaShell, type NavItem } from "../shared/AreaShell";
import { RequireSignIn } from "../shared/RequireSignIn";
import { ThemeToggle } from "../shared/ThemeToggle";

const ReviewQueue = lazy(() => import("./screens/ReviewQueue"));
const ReportsScreen = lazy(() => import("./screens/ReportsScreen"));
const ReferenceData = lazy(() => import("./screens/ReferenceData"));
const TrustScreen = lazy(() => import("./screens/TrustScreen"));
const AccountsScreen = lazy(() => import("./screens/AccountsScreen"));
const AuditScreen = lazy(() => import("./screens/AuditScreen"));

const NAV: NavItem[] = [
  { to: "/admin", label: "Review queue", icon: ClipboardCheck, end: true },
  { to: "/admin/reports", label: "Reports and disputes", icon: Flag },
  { to: "/admin/reference", label: "Reference data", icon: BookOpen },
  { to: "/admin/trust", label: "Trust", icon: ShieldCheck },
  { to: "/admin/accounts", label: "Accounts", icon: Users },
  { to: "/admin/audit", label: "Audit log and health", icon: ScrollText },
];

// The admin API checks the admin role on every request; this shell only lays out screens.
export default function AdminArea() {
  const [theme, toggle] = useAreaTheme("admin");
  const logout = useLogout();
  const nav = useNavigate();
  return (
    <RequireSignIn signInPath="/sign-in">
      {(me) => me.role !== "admin" ? (
        <div className="mx-auto max-w-xl p-6"><EmptyState title="Admin only" body="This area is for the platform team." /></div>
      ) : (
        <AreaShell bottomBar={false} nav={NAV}
          brand={<span className="font-display text-lg font-extrabold">Admin</span>}
          header={<div className="flex h-14 items-center justify-end gap-2 px-4 sm:px-8">
            <span className="mr-auto truncate text-sm text-muted">{me.email}</span>
            <ThemeToggle theme={theme} toggle={toggle} />
            <button className="grid size-11 place-items-center rounded-full text-muted hover:bg-chip-green" aria-label="Sign out"
              onClick={() => logout.mutate(undefined, { onSettled: () => nav("/sign-in", { replace: true }) })}><LogOut size={20} /></button>
          </div>}>
          <Suspense fallback={<Skeleton className="h-96" />}>
            <Routes>
              <Route index element={<ReviewQueue />} />
              <Route path="reports" element={<ReportsScreen />} />
              <Route path="reference" element={<ReferenceData />} />
              <Route path="trust" element={<TrustScreen />} />
              <Route path="accounts" element={<AccountsScreen />} />
              <Route path="audit" element={<AuditScreen />} />
            </Routes>
          </Suspense>
        </AreaShell>
      )}
    </RequireSignIn>
  );
}
