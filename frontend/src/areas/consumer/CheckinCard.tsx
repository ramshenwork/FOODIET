import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { feedback, usePendingCheckin } from "../../api/consumer";
import { Chip } from "../../ui";

const FELT: [string, string][] = [["lighter", "Lighter"], ["as_expected", "As expected"], ["heavier", "Heavier"]];

/** One card, three taps, swipe to dismiss. Answers feed anonymous statistics only. */
export function CheckinCard() {
  const q = usePendingCheckin();
  const qc = useQueryClient();
  const reduce = useReducedMotion();
  const [step, setStep] = useState(0);
  const [felt, setFelt] = useState<string | null>(null);
  const [recommend, setRecommend] = useState<boolean | null>(null);
  const [done, setDone] = useState(false);
  const [hidden, setHidden] = useState<string | null>(null);  // dismissed card id: hide at once, don't wait for a refetch
  const c = q.data;
  if (!c || hidden === c.meal_entry_id) return null;

  const send = async (body: Parameters<typeof feedback.checkin>[0], finished: boolean) => {
    try { await feedback.checkin(body); } catch { /* already answered elsewhere: just hide it */ }
    if (finished) {
      setDone(true);
      setTimeout(() => { setHidden(body.meal_entry_id); setDone(false); setStep(0); qc.invalidateQueries({ queryKey: ["checkin"] }); }, reduce ? 200 : 900);
    }
    else qc.invalidateQueries({ queryKey: ["checkin"] });
  };
  const dismiss = () => { setHidden(c.meal_entry_id); send({ meal_entry_id: c.meal_entry_id }, false); };
  const finish = (item: string | null) => send({ meal_entry_id: c.meal_entry_id, felt, recommend, recommended_item_id: item }, true);

  return (
    <AnimatePresence>
      <motion.section key={c.meal_entry_id} drag={done ? false : "x"} dragConstraints={{ left: 0, right: 0 }} dragElastic={0.6}
        onDragEnd={(_, info) => { if (Math.abs(info.offset.x) > 120) dismiss(); }}
        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: 200 }}
        className="card relative overflow-hidden p-5" aria-label="Quick check-in">
        <button onClick={dismiss} aria-label="Dismiss check-in" className="absolute right-2 top-2 grid size-11 place-items-center rounded-full text-muted hover:bg-chip-green"><X size={18} /></button>
        {done ? (
          <div className="relative py-6 text-center">
            {!reduce && [...Array(10)].map((_, i) => (
              <motion.span key={i} className="absolute left-1/2 top-1/2 size-2 rounded-full" style={{ background: i % 2 ? "var(--orange-500)" : "var(--green-500)" }}
                initial={{ x: 0, y: 0, opacity: 1 }} animate={{ x: Math.cos(i * 0.63) * 90, y: Math.sin(i * 0.63) * 50, opacity: 0 }} transition={{ duration: 0.7 }} />
            ))}
            <p className="font-display text-lg font-bold">Thanks, that helps other diners</p>
          </div>
        ) : (
          <>
            <p className="text-sm text-muted">{c.restaurant} · {c.dishes.join(", ")}</p>
            {step === 0 && <>
              <h2 className="mt-1 font-display text-lg font-bold">How did it feel?</h2>
              <div className="mt-3 flex flex-wrap gap-2">{FELT.map(([v, l]) => <Chip key={v} tone="neutral" onClick={() => { setFelt(v); setStep(1); }}>{l}</Chip>)}</div>
            </>}
            {step === 1 && <>
              <h2 className="mt-1 font-display text-lg font-bold">Would you recommend it?</h2>
              <div className="mt-3 flex gap-2">
                <Chip tone="green" onClick={() => { setRecommend(true); setStep(2); }}>Yes</Chip>
                <Chip tone="neutral" onClick={() => { setRecommend(false); setStep(2); }}>No</Chip>
              </div>
            </>}
            {step === 2 && <>
              <h2 className="mt-1 font-display text-lg font-bold">What would you recommend here?</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {c.menu.slice(0, 8).map((m) => <Chip key={m.id} tone="green" onClick={() => finish(m.id)}>{m.name}</Chip>)}
                <Chip tone="neutral" onClick={() => finish(null)}>Skip</Chip>
              </div>
            </>}
            <p className="mt-3 text-xs text-muted">Swipe away to skip. Restaurants only see totals, never you.</p>
          </>
        )}
      </motion.section>
    </AnimatePresence>
  );
}
