import { useId, type SelectHTMLAttributes } from "react";
import clsx from "clsx";

export function Select({ label, options, className, ...rest }: SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string; options: { value: string; label: string }[];
}) {
  const id = useId();
  const el = (
    <select id={id} className={clsx("min-h-11 w-full rounded-[var(--radius-control)] border border-line bg-card px-3 text-text outline-none focus:border-green", className)} {...rest}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  if (!label) return el;
  return <label htmlFor={id} className="block"><span className="mb-1.5 block text-sm font-medium">{label}</span>{el}</label>;
}
