import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { useConfig } from "../api/hooks";
import { Skeleton } from "../ui";

// Each area is a separate bundle: a consumer never downloads business or admin code.
const ConsumerArea = lazy(() => import("../areas/consumer/ConsumerArea"));
const BusinessArea = lazy(() => import("../areas/business/BusinessArea"));
const AdminArea = lazy(() => import("../areas/admin/AdminArea"));
const SignIn = lazy(() => import("../areas/shared/SignIn"));
const Gallery = import.meta.env.DEV ? lazy(() => import("../areas/shared/Gallery")) : null;

function PageSkeleton() {
  return (
    <div className="mx-auto max-w-xl space-y-4 p-4 pt-10" aria-busy>
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-48" />
      <Skeleton className="h-24" />
    </div>
  );
}

function TitleFromConfig() {
  const { data } = useConfig();
  useEffect(() => { if (data) document.title = data.app_name; }, [data]);
  return null;
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <TitleFromConfig />
      <Suspense fallback={<PageSkeleton />}>
        <Routes>
          <Route path="/sign-in" element={<SignIn role="consumer" />} />
          <Route path="/business/sign-in" element={<SignIn role="business" />} />
          <Route path="/business/*" element={<BusinessArea />} />
          <Route path="/admin/*" element={<AdminArea />} />
          {Gallery && <Route path="/ui" element={<Gallery />} />}
          <Route path="/*" element={<ConsumerArea />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
