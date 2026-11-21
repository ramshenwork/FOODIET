import { lazy, Suspense } from "react";
import { Compass, Home as HomeIcon, MessageCircle, NotebookPen, UserRound } from "lucide-react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { useProfile } from "../../api/consumer";
import { useConfig, useEntitlement, useMe } from "../../api/hooks";
import type { Me } from "../../api/types";
import { useAreaTheme } from "../../app/theme";
import { ErrorState, Skeleton } from "../../ui";
import { AreaShell, type NavItem } from "../shared/AreaShell";
import { LocationProvider } from "./location";
import Home from "./screens/Home";

const Explore = lazy(() => import("./screens/Explore"));
const RestaurantScreen = lazy(() => import("./screens/RestaurantScreen"));
const DishScreen = lazy(() => import("./screens/DishScreen"));
const Diary = lazy(() => import("./screens/Diary"));
const Account = lazy(() => import("./screens/Account"));
const Onboarding = lazy(() => import("./screens/Onboarding"));
const Paywall = lazy(() => import("./screens/Paywall"));
const Welcome = lazy(() => import("./screens/Welcome"));
const Fingerprint = lazy(() => import("./screens/Fingerprint"));
const Trends = lazy(() => import("./screens/Trends"));
const Assistant = lazy(() => import("./screens/Assistant"));

const NAV: NavItem[] = [
  { to: "/", label: "Home", icon: HomeIcon, end: true },
  { to: "/explore", label: "Explore", icon: Compass },
  { to: "/diary", label: "Diary", icon: NotebookPen },
  { to: "/assistant", label: "Assistant", icon: MessageCircle },
  { to: "/profile", label: "Profile", icon: UserRound },
];
const Loading = () => <div className="mx-auto max-w-xl space-y-4 p-6"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-48" /></div>;

/** Chooses which screens to show from the access level the server reports. The server still checks every request. */
function SignedIn({ me }: { me: Me }) {
  const [theme, toggle] = useAreaTheme("consumer");
  const { data: config } = useConfig();
  const ent = useEntitlement();
  const profile = useProfile();
  const nav = useNavigate();
  if (ent.isPending || profile.isPending) return <Loading />;
  if (ent.isError) return <div className="p-6"><ErrorState error={ent.error} onRetry={() => ent.refetch()} /></div>;
  const can = ent.data.can;
  const full = can.nutrition;
  const needsProfile = full && !profile.data?.complete;
  return (
    <AreaShell brand={<span className="font-display text-xl font-extrabold">{config?.app_name}</span>} nav={NAV}>
      <Suspense fallback={<Skeleton className="h-96" />}>
        <Routes>
          <Route path="profile" element={<Account me={me} theme={theme} toggleTheme={toggle} />} />
          <Route path="diary" element={can.diary_read ? <Diary /> : <Paywall ent={ent.data} />} />
          <Route path="onboarding" element={full ? <Onboarding onDone={() => nav("/")} /> : <Navigate to="/" replace />} />
          {!full ? <Route path="*" element={<Paywall ent={ent.data} />} /> : needsProfile ? <Route path="*" element={<Onboarding />} /> : (
            <>
              <Route index element={<Home me={me} />} />
              <Route path="explore" element={<Explore />} />
              <Route path="restaurants/:id" element={<RestaurantScreen />} />
              <Route path="dishes/:id" element={<DishScreen />} />
              <Route path="trends" element={<Trends />} />
              <Route path="profile/fingerprint" element={<Fingerprint />} />
              <Route path="assistant" element={<Assistant />} />
            </>
          )}
        </Routes>
      </Suspense>
    </AreaShell>
  );
}

export default function ConsumerArea() {
  useAreaTheme("consumer");
  const me = useMe();
  try { const ref = new URLSearchParams(window.location.search).get("ref"); if (ref) sessionStorage.setItem("ref", ref); } catch { /* ignore */ }
  if (me.isPending) return <Loading />;
  if (me.isError) return <div className="p-6"><ErrorState error={me.error} onRetry={() => me.refetch()} /></div>;
  return (
    <LocationProvider>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="welcome" element={me.data ? <Navigate to="/" replace /> : <Welcome />} />
          <Route path="*" element={me.data ? <SignedIn me={me.data} /> : <Navigate to="/welcome" replace />} />
        </Routes>
      </Suspense>
    </LocationProvider>
  );
}
