import { forwardRef, useId, type InputHTMLAttributes } from "react";
import clsx from "clsx";

export const Field = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: string }>(
  function Field({ label, error, hint, className, ...rest }, ref) {
    const id = useId();
    return (
      <label htmlFor={id} className="block">
        <span className="mb-1.5 block text-sm font-medium">{label}</span>
        <input
          ref={ref}
          id={id}
          aria-invalid={!!error || undefined}
          aria-describedby={error || hint ? `${id}-msg` : undefined}
          className={clsx(
            "min-h-12 w-full rounded-[var(--radius-control)] border bg-card px-4 text-base text-text outline-none transition-colors",
            "placeholder:text-muted focus:border-green",
            error ? "border-danger" : "border-line",
            className,
          )}
          {...rest}
        />
        {(error || hint) && (
          <span id={`${id}-msg`} className={clsx("mt-1.5 block text-sm", error ? "text-danger-text" : "text-muted")}>{error ?? hint}</span>
        )}
      </label>
    );
  },
);
