import { useEffect, useId, useRef, useState } from "react";
import clsx from "clsx";

/** Server-backed autocomplete. `search` calls the API; nothing is filtered or ranked in the browser. */
export function Autocomplete<T extends { id: string; name: string }>({ label, placeholder, value, search, onPick, render, className }: {
  label?: string; placeholder?: string; value: string; search: (q: string) => Promise<T[]>;
  onPick: (hit: T) => void; render?: (hit: T) => React.ReactNode; className?: string;
}) {
  const [q, setQ] = useState(value);
  const [hits, setHits] = useState<T[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const id = useId();
  const seq = useRef(0);

  useEffect(() => setQ(value), [value]);
  useEffect(() => {
    if (!open || q.trim().length < 2) { setHits([]); return; }
    const n = ++seq.current;
    const t = setTimeout(() => {
      search(q).then((r) => { if (n === seq.current) { setHits(r); setActive(0); } }).catch(() => setHits([]));
    }, 180);
    return () => clearTimeout(t);
  }, [q, open, search]);

  const pick = (h: T) => { onPick(h); setQ(h.name); setOpen(false); };
  return (
    <div className={clsx("relative", className)}>
      {label && <label htmlFor={id} className="mb-1.5 block text-sm font-medium">{label}</label>}
      <input
        id={id} value={q} placeholder={placeholder} autoComplete="off" role="combobox" aria-expanded={open && hits.length > 0}
        aria-controls={`${id}-list`}
        className="min-h-11 w-full rounded-[var(--radius-control)] border border-line bg-card px-3 text-text outline-none focus:border-green"
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (!hits.length) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, hits.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          if (e.key === "Enter") { e.preventDefault(); pick(hits[active]); }
        }}
      />
      {open && hits.length > 0 && (
        <ul id={`${id}-list`} role="listbox" className="card absolute z-30 mt-1 max-h-72 w-full overflow-auto p-1">
          {hits.map((h, i) => (
            <li key={h.id} role="option" aria-selected={i === active}
              onMouseDown={(e) => { e.preventDefault(); pick(h); }}
              className={clsx("cursor-pointer rounded-xl px-3 py-2 text-sm", i === active && "bg-chip-green")}>
              {render ? render(h) : h.name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
