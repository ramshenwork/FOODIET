import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Send, Sparkles } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../../api/client";
import { askAssistant, useConversation, type AssistantMessage, type CitedDish } from "../../../api/consumer";
import { Banner, ErrorState, Skeleton, TrustLabel } from "../../../ui";
import type { TrustLabelKind } from "../../../api/types";
import { useLocationCtx } from "../location";

const SUGGESTIONS = ["High protein near me under 500 kcal", "How much do I have left today?", "Compare idli and masala dosa"];

function Cards({ cited }: { cited: CitedDish[] }) {
  if (!cited.length) return null;
  return (
    <div className="mt-2 grid gap-2">
      {cited.map((c) => (
        <Link key={c.id} to={`/dishes/${c.id}`} className="flex items-center justify-between gap-3 rounded-2xl border border-line bg-card p-3">
          <div className="min-w-0"><p className="truncate font-medium">{c.name}</p><p className="truncate text-xs text-muted">{c.restaurant}</p>
            <div className="mt-1"><TrustLabel kind={c.trust as TrustLabelKind} /></div></div>
          <div className="shrink-0 text-right text-sm"><p className="font-semibold text-orange-text">{c.energy}</p>{c.protein && <p className="text-xs text-muted">Protein {c.protein}</p>}</div>
        </Link>
      ))}
    </div>
  );
}

function Bubble({ m }: { m: AssistantMessage & { notice?: string | null } }) {
  const mine = m.role === "user";
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[88%] ${mine ? "rounded-[20px] rounded-br-md bg-orange px-4 py-2.5 text-ink" : ""}`}>
        {!mine && m.notice && <p className="mb-1 text-xs text-muted">{m.notice}</p>}
        <p className={mine ? "" : "card rounded-[20px] rounded-bl-md px-4 py-3"}>{m.content}</p>
        {!mine && <Cards cited={m.cited} />}
      </div>
    </motion.div>
  );
}

/** Answers come from the server, built only from catalogue and diary data; dishes are cited as cards. */
export default function Assistant() {
  const conv = useConversation();
  const { coords } = useLocationCtx();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [extra, setExtra] = useState<(AssistantMessage & { notice?: string | null })[]>([]);
  const [error, setError] = useState<unknown>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [extra, pending, conv.data]);

  const send = async (text: string) => {
    if (!text.trim() || pending) return;
    setPending(text); setQ(""); setError(null);
    try {
      const a = await askAssistant(text, coords);
      const now = new Date().toISOString();
      setExtra((x) => [...x, { role: "user", content: text, cited: [], mode: null, at: now },
        { role: "assistant", content: a.answer, cited: a.cited, mode: a.mode, at: now, notice: a.notice }]);
      qc.setQueryData(["assistant"], (old: typeof conv.data) => old && { ...old, remaining_today: a.remaining_today });
    } catch (e) { setError(e); } finally { setPending(null); }
  };

  if (conv.isPending) return <Skeleton className="h-96" />;
  if (conv.isError) return <ErrorState error={conv.error} onRetry={() => conv.refetch()} />;
  const all = [...conv.data.messages, ...extra];
  const limitHit = error instanceof ApiError && error.code === "assistant_limit";
  return (
    <div className="flex min-h-[70dvh] flex-col">
      <div className="mb-3 flex items-baseline justify-between">
        <h1 className="text-2xl font-extrabold">Assistant</h1>
        <span className="text-sm text-muted">{conv.data.remaining_today} of {conv.data.limit} questions left today</span>
      </div>
      {conv.data.mode === "basic" && <div className="mb-3"><Banner tone="note" title="Basic mode">I can answer simple questions about nearby dishes and what's left today.</Banner></div>}
      <div className="flex-1 space-y-4 pb-4">
        {all.length === 0 && !pending && (
          <div className="space-y-3 pt-6 text-center">
            <Sparkles className="mx-auto text-green-text" />
            <p className="text-muted">Ask about dishes near you, or how today is going.</p>
            <div className="flex flex-wrap justify-center gap-2">{SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => send(s)} className="min-h-11 rounded-full border border-line px-4 text-sm hover:bg-chip-green">{s}</button>
            ))}</div>
          </div>
        )}
        {all.map((m, i) => <Bubble key={i} m={m} />)}
        {pending && <><Bubble m={{ role: "user", content: pending, cited: [], mode: null, at: "" }} /><Skeleton className="h-16 w-2/3" /></>}
        {error ? (limitHit ? <Banner tone="note" title={(error as ApiError).message} /> : <ErrorState error={error} />) : null}
        <div ref={end} />
      </div>
      <form className="glass sticky bottom-[calc(64px+env(safe-area-inset-bottom))] -mx-4 flex gap-2 border-t border-line p-3 sm:bottom-0 sm:mx-0 sm:rounded-2xl sm:border"
        onSubmit={(e) => { e.preventDefault(); send(q); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} aria-label="Ask the assistant"
          placeholder={conv.data.remaining_today ? "Ask about dishes near you" : "No questions left today"} disabled={!conv.data.remaining_today}
          className="min-h-11 flex-1 rounded-full border border-line bg-card px-4 outline-none focus:border-green" />
        <button type="submit" aria-label="Send" disabled={!q.trim() || !!pending || !conv.data.remaining_today}
          className="grid size-11 place-items-center rounded-full bg-orange text-ink disabled:opacity-40"><Send size={18} /></button>
      </form>
      <p className="mt-2 text-center text-xs text-muted">Answers use the restaurant data shown in the app. Not medical advice.</p>
    </div>
  );
}
