import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import type { ReactNode } from "react";
import clsx from "clsx";

/** Status messages. Orange is never used for warnings; problems use red, good news green, notes neutral. */
export function Banner({ tone, title, children }: { tone: "success" | "problem" | "note"; title: string; children?: ReactNode }) {
  const Icon = tone === "success" ? CheckCircle2 : tone === "problem" ? AlertTriangle : Info;
  return (
    <div role={tone === "problem" ? "alert" : "status"} className={clsx("flex gap-3 rounded-2xl border p-4 text-sm",
      tone === "success" && "border-green/40 bg-chip-green",
      tone === "problem" && "border-danger/40 bg-danger/5",
      tone === "note" && "border-line bg-card")}>
      <Icon size={18} className={clsx("mt-0.5 shrink-0", tone === "success" ? "text-green-text" : tone === "problem" ? "text-danger-text" : "text-muted")} />
      <div><p className="font-semibold">{title}</p>{children && <div className="mt-1 text-muted">{children}</div>}</div>
    </div>
  );
}
