import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "./client";
import type { Entitlement, Me, PublicConfig, SessionOut } from "./types";

export const useConfig = () =>
  useQuery({ queryKey: ["config"], queryFn: () => api<PublicConfig>("/config"), staleTime: Infinity });

export const useMe = () =>
  useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      try { return await api<Me>("/me"); }
      catch (e) { if (e instanceof ApiError && e.status === 401) return null; throw e; }
    },
  });

export const useEntitlement = (enabled = true) =>
  useQuery({ queryKey: ["entitlement"], queryFn: () => api<Entitlement>("/me/entitlement"), enabled });

export const useRequestOtp = () =>
  useMutation({ mutationFn: (v: { email: string; role: "consumer" | "business" }) =>
    api<{ message: string; ttl_minutes: number }>("/auth/otp/request", { method: "POST", body: v }) });

export function useVerifyOtp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { email: string; code: string; role: "consumer" | "business"; device_id: string }) =>
      api<SessionOut>("/auth/otp/verify", { method: "POST", body: v }),
    onSuccess: (s) => { qc.setQueryData(["me"], s.user); qc.invalidateQueries({ queryKey: ["entitlement"] }); },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api("/auth/logout", { method: "POST" }),
    onSettled: () => { qc.setQueryData(["me"], null); qc.removeQueries({ queryKey: ["entitlement"] }); },
  });
}
