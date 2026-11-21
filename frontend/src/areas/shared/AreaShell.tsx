import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import clsx from "clsx";
import type { LucideIcon } from "lucide-react";

export interface NavItem { to: string; label: string; icon: LucideIcon; end?: boolean }

/** Phones (<640 px): bottom bar. Wider: left rail, content capped at 1,200 px. */
export function AreaShell({ brand, nav, header, children, bottomBar = true }: {
  brand: ReactNode; nav: NavItem[]; header?: ReactNode; children: ReactNode; bottomBar?: boolean;
}) {
  const link = (n: NavItem, compact: boolean) => (
    <NavLink key={n.to} to={n.to} end={n.end}
      className={({ isActive }) => clsx(
        "flex min-h-11 items-center rounded-2xl transition-colors duration-200",
        compact ? "flex-1 flex-col justify-center gap-0.5 text-[11px] font-medium" : "gap-3 px-3 text-sm font-medium",
        isActive ? "text-green-text" + (compact ? "" : " bg-chip-green") : "text-muted hover:text-text",
      )}>
      <n.icon size={compact ? 22 : 20} strokeWidth={2} aria-hidden />
      <span>{n.label}</span>
    </NavLink>
  );

  return (
    <div className="min-h-dvh sm:flex">
      <aside className="glass sticky top-0 hidden h-dvh w-60 shrink-0 flex-col gap-1 border-r border-line p-4 sm:flex">
        <div className="mb-6 px-3 pt-2">{brand}</div>
        <nav className="flex flex-col gap-1" aria-label="Main">{nav.map((n) => link(n, false))}</nav>
      </aside>
      <div className="min-w-0 flex-1">
        {header && <header className="glass sticky top-0 z-30 border-b border-line">{header}</header>}
        <main className={clsx("mx-auto w-full max-w-[1200px] px-4 py-6 sm:px-8", bottomBar && "pb-28 sm:pb-10")}>{children}</main>
      </div>
      {bottomBar && (
        <nav aria-label="Main" className="glass fixed inset-x-0 bottom-0 z-30 flex border-t border-line px-2 pb-[env(safe-area-inset-bottom)] pt-1 sm:hidden">
          {nav.map((n) => link(n, true))}
        </nav>
      )}
    </div>
  );
}
