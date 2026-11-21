import type { ReactNode } from "react";
import { Chip } from "../../ui";

export function Tabs<T extends string>({ value, onChange, tabs }: { value: T; onChange: (v: T) => void; tabs: [T, string][] }) {
  return (
    <div className="mb-5 flex flex-wrap gap-2" role="tablist">
      {tabs.map(([k, label]) => <Chip key={k} role="tab" aria-selected={value === k} tone="neutral" selected={value === k} onClick={() => onChange(k)}>{label}</Chip>)}
    </div>
  );
}

export function Pill({ tone, children }: { tone: "green" | "red" | "neutral"; children: ReactNode }) {
  const cls = tone === "green" ? "bg-chip-green text-green-text" : tone === "red" ? "bg-danger/10 text-danger-text" : "border border-line text-muted";
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}>{children}</span>;
}

export const fmtDate = (s: string | null) => (s ? new Date(s).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "–");

export function TextArea({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium">{label}</span>
      <textarea value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} rows={3}
        className="w-full rounded-[var(--radius-control)] border border-line bg-card p-3 text-text outline-none focus:border-green" />
    </label>
  );
}
