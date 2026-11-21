import { forwardRef, type ButtonHTMLAttributes } from "react";
import clsx from "clsx";

type Variant = "primary" | "secondary" | "ghost" | "danger";

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant; loading?: boolean; block?: boolean;
}>(function Button({ variant = "primary", loading, block, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={clsx(
        "relative inline-flex min-h-11 items-center justify-center gap-2 rounded-[var(--radius-control)] px-5 font-display text-[15px] font-semibold",
        "transition-[transform,opacity,box-shadow] duration-200 ease-out active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100",
        variant === "primary" && "bg-orange text-ink hover:shadow-[0_8px_28px_-6px_rgba(255,122,26,0.55),0_0_0_1px_rgba(18,183,106,0.25)]",
        variant === "secondary" && "bg-chip-green text-green-text hover:opacity-90",
        variant === "ghost" && "text-text hover:bg-chip-green",
        variant === "danger" && "bg-danger text-white",
        block && "w-full",
        className,
      )}
      {...rest}
    >
      {loading && <span className="absolute inset-0 rounded-[inherit] skeleton opacity-40" aria-hidden />}
      <span className={clsx("inline-flex items-center gap-2", loading && "opacity-70")}>{children}</span>
    </button>
  );
});
