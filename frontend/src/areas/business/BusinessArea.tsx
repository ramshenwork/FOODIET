import { lazy, Suspense } from "react";
import { BarChart3, ChefHat, LayoutDashboard, LogOut, QrCode, Store, Upload, Users, UtensilsCrossed } from "lucide-react";
import { Route, Routes, useNavigate } from "react-router-dom";
import { useBusinesses } from "../../api/business";
import { useConfig, useLogout } from "../../api/hooks";
import { useAreaTheme } from "../../app/theme";
import { ErrorState, Skeleton } from "../../ui";
import { AreaShell, type NavItem } from "../shared/AreaShell";
import { RequireSignIn } from "../shared/RequireSignIn";
import { ThemeToggle } from "../shared/ThemeToggle";
import { BusinessProvider } from "./context";
import Dashboard from "./screens/Dashboard";
import MenuScreen from "./screens/MenuScreen";
import Onboarding from "./screens/Onboarding";

const RecipesScreen = lazy(() => import("./screens/RecipesScreen"));
const RecipeBuilder = lazy(() => import("./screens/RecipeBuilder"));
const ItemDetail = lazy(() => import("./screens/ItemDetail"));
const ImportScreen = lazy(() => import("./screens/ImportScreen"));
const BranchesScreen = lazy(() => import("./screens/BranchesScreen"));
const QrScreen = lazy(() => import("./screens/QrScreen"));
const TeamScreen = lazy(() => import("./screens/TeamScreen"));
const InsightsScreen = lazy(() => import("./screens/InsightsScreen"));

const NAV: NavItem[] = [
  { to: "/business", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/business/menu", label: "Menu", icon: UtensilsCrossed },
  { to: "/business/recipes", label: "Recipes", icon: ChefHat },
  { to: "/business/import", label: "Import", icon: Upload },
  { to: "/business/branches", label: "Branches", icon: Store },
  { to: "/business/qr", label: "QR codes", icon: QrCode },
  { to: "/business/team", label: "Team and plan", icon: Users },
  { to: "/business/insights", label: "Insights", icon: BarChart3 },
];

function Workspace({ email }: { email: string }) {
  const [theme, toggle] = useAreaTheme("business");
  const { data: config } = useConfig();
  const businesses = useBusinesses();
  const logout = useLogout();
  const nav = useNavigate();
  if (businesses.isPending) return <div className="mx-auto max-w-xl space-y-4 p-6"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-48" /></div>;
  if (businesses.isError) return <div className="mx-auto max-w-xl p-6"><ErrorState error={businesses.error} onRetry={() => businesses.refetch()} /></div>;
  if (businesses.data.length === 0) return <Onboarding />;
  return (
    <BusinessProvider business={businesses.data[0]}>
      <AreaShell bottomBar={false} nav={NAV}
        brand={<span className="font-display text-lg font-extrabold">{config?.app_name} <span className="text-green-text">Business</span></span>}
        header={
          <div className="no-print flex h-14 items-center justify-end gap-2 px-4 sm:px-8">
            <span className="mr-auto truncate text-sm text-muted">{businesses.data[0].name} · {email}</span>
            <ThemeToggle theme={theme} toggle={toggle} />
            <button className="grid size-11 place-items-center rounded-full text-muted hover:bg-chip-green" aria-label="Sign out"
              onClick={() => logout.mutate(undefined, { onSettled: () => nav("/business/sign-in", { replace: true }) })}><LogOut size={20} /></button>
          </div>
        }>
        <Suspense fallback={<Skeleton className="h-96" />}>
          <Routes>
            <Route index element={<Dashboard />} />
            <Route path="menu" element={<MenuScreen />} />
            <Route path="menu/:itemId" element={<ItemDetail />} />
            <Route path="recipes" element={<RecipesScreen />} />
            <Route path="recipes/:recipeId" element={<RecipeBuilder />} />
            <Route path="import" element={<ImportScreen />} />
            <Route path="branches" element={<BranchesScreen />} />
            <Route path="qr" element={<QrScreen />} />
            <Route path="team" element={<TeamScreen />} />
            <Route path="insights" element={<InsightsScreen />} />
          </Routes>
        </Suspense>
      </AreaShell>
    </BusinessProvider>
  );
}

export default function BusinessArea() {
  useAreaTheme("business");
  return <RequireSignIn signInPath="/business/sign-in">{(me) => <Workspace email={me.email} />}</RequireSignIn>;
}
