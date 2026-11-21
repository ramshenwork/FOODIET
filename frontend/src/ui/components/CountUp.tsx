import { animate, useReducedMotion } from "framer-motion";
import { useEffect, useRef } from "react";

/** Counts up to a server-provided figure. Purely visual. */
export function CountUp({ value, duration = 0.8 }: { value: number; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduce) { el.textContent = value.toLocaleString("en-IN"); return; }
    const ctl = animate(0, value, {
      duration, ease: "easeOut",
      onUpdate: (v) => { el.textContent = Math.round(v).toLocaleString("en-IN"); },
    });
    return () => ctl.stop();
  }, [value, duration, reduce]);
  return <span ref={ref}>{value.toLocaleString("en-IN")}</span>;
}
