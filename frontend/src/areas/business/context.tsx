import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Business } from "../../api/business";

interface Ctx { business: Business; branchId: string; setBranchId: (id: string) => void }
const BusinessCtx = createContext<Ctx | null>(null);

export function BusinessProvider({ business, children }: { business: Business; children: ReactNode }) {
  const key = `branch:${business.id}`;
  const first = business.branches[0]?.id ?? "";
  const [branchId, setBranch] = useState<string>(() => {
    try { const v = localStorage.getItem(key); return v && business.branches.some((b) => b.id === v) ? v : first; }
    catch { return first; }
  });
  useEffect(() => { if (!business.branches.some((b) => b.id === branchId)) setBranch(first); }, [business, branchId, first]);
  const setBranchId = (id: string) => { setBranch(id); try { localStorage.setItem(key, id); } catch { /* ignore */ } };
  return <BusinessCtx.Provider value={{ business, branchId, setBranchId }}>{children}</BusinessCtx.Provider>;
}

export function useBiz(): Ctx {
  const c = useContext(BusinessCtx);
  if (!c) throw new Error("useBiz outside BusinessProvider");
  return c;
}
